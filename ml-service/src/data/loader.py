"""Raw/processed data storage with dataset versioning.

Each processed dataset is written to ``data/processed/<version>/`` alongside a
metadata file recording the row count, class balance and a content hash of the
raw source. Model metadata then records which dataset version trained it, which
is the "data versioning" requirement in the checklist.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from src.config import ID_COLUMN, TARGET, settings
from src.data.validation import ValidationReport, validate_dataframe
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

_CHUNK = 1 << 20


@dataclass
class DatasetVersion:
    """Metadata describing one processed dataset snapshot."""

    version: str
    created_at: str
    source_file: str
    source_sha256: str
    n_rows: int
    n_columns: int
    positive_rate: float
    validation: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def file_sha256(path: Path) -> str:
    """Content hash of a file, computed in chunks so large CSVs stay off-heap."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def load_raw(path: Optional[Path] = None) -> pd.DataFrame:
    """Read the raw training dataset.

    With an explicit ``path`` (or ``settings.raw_dataset_path``), reads a flat
    CSV already in the canonical schema — this is the retraining pipeline's
    path, which merges realised outcomes into a canonical CSV rather than
    re-touching the Home Credit source tables. With neither, builds the
    canonical frame from the real Home Credit tables (cached after the first
    build; see src/data/home_credit.py).
    """
    source = Path(path) if path else settings.raw_dataset_path
    if source is not None:
        if not source.exists():
            raise FileNotFoundError(
                f"Raw dataset not found at {source}. Set RAW_DATASET_PATH or place the "
                f"CSV in {settings.raw_data_dir}."
            )
        logger.info("Loading raw dataset from %s", source)
        df = pd.read_csv(source)
        logger.info("Loaded %d rows x %d columns", len(df), df.shape[1])
        return df

    from src.data.home_credit import load_home_credit

    df = load_home_credit(settings.home_credit_dir)
    logger.info("Loaded %d rows x %d columns from Home Credit source", len(df), df.shape[1])
    return df


def make_version_tag(prefix: str = "ds") -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"


def _directory_fingerprint(directory: Path) -> str:
    """Cheap content fingerprint for a multi-file source (e.g. the Home Credit tables)."""
    digest = hashlib.sha256()
    for entry in sorted(directory.glob("*.csv")):
        stat = entry.stat()
        digest.update(f"{entry.name}:{stat.st_size}:{stat.st_mtime_ns}".encode())
    return digest.hexdigest()


def save_processed(df: pd.DataFrame, source_path: Optional[Path] = None, version: Optional[str] = None,
                   validation: Optional[ValidationReport] = None) -> DatasetVersion:
    """Persist a processed dataset under a new version directory."""
    version = version or make_version_tag()
    target_dir = settings.processed_data_dir / version
    target_dir.mkdir(parents=True, exist_ok=True)

    data_path = target_dir / "dataset.parquet"
    try:
        df.to_parquet(data_path, index=False)
    except (ImportError, ValueError):  # pyarrow not installed -> fall back to CSV
        data_path = target_dir / "dataset.csv"
        df.to_csv(data_path, index=False)
        logger.warning("Parquet unavailable, wrote CSV instead: %s", data_path)

    # source_path may be a single CSV (retraining's canonical merge file), a
    # directory of source tables (Home Credit), or None (default Home Credit
    # source, resolved the same way loader.load_raw resolves it).
    resolved_source = Path(source_path) if source_path else settings.home_credit_dir
    if resolved_source.is_file():
        source_label, source_hash = str(resolved_source), file_sha256(resolved_source)
    elif resolved_source.is_dir():
        source_label, source_hash = str(resolved_source), _directory_fingerprint(resolved_source)
    else:
        source_label, source_hash = str(resolved_source), ""

    meta = DatasetVersion(
        version=version,
        created_at=datetime.now(timezone.utc).isoformat(),
        source_file=source_label,
        source_sha256=source_hash,
        n_rows=len(df),
        n_columns=df.shape[1],
        positive_rate=float(df[TARGET].mean()) if TARGET in df.columns else -1.0,
        validation=validation.to_dict() if validation else {},
    )
    with open(target_dir / "metadata.json", "w", encoding="utf-8") as handle:
        json.dump(meta.to_dict(), handle, indent=2)

    logger.info("Saved processed dataset version %s (%d rows) to %s",
                version, len(df), target_dir)
    return meta


def load_processed(version: str) -> Tuple[pd.DataFrame, DatasetVersion]:
    """Load a previously saved processed dataset by version tag."""
    target_dir = settings.processed_data_dir / version
    if not target_dir.exists():
        raise FileNotFoundError(f"No processed dataset version '{version}'.")

    parquet_path, csv_path = target_dir / "dataset.parquet", target_dir / "dataset.csv"
    if parquet_path.exists():
        df = pd.read_parquet(parquet_path)
    elif csv_path.exists():
        df = pd.read_csv(csv_path)
    else:
        raise FileNotFoundError(f"Version '{version}' has no dataset file.")

    with open(target_dir / "metadata.json", "r", encoding="utf-8") as handle:
        meta = DatasetVersion(**json.load(handle))
    return df, meta


def list_dataset_versions() -> list[Dict[str, Any]]:
    """All processed dataset versions, newest first."""
    if not settings.processed_data_dir.exists():
        return []
    versions = []
    for entry in sorted(settings.processed_data_dir.iterdir(), reverse=True):
        meta_file = entry / "metadata.json"
        if entry.is_dir() and meta_file.exists():
            with open(meta_file, "r", encoding="utf-8") as handle:
                versions.append(json.load(handle))
    return versions


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Drop exact duplicate applications, keeping the first occurrence.

    Duplicate loan IDs are a data-integrity problem at training time; at scoring
    time the same signal is a fraud indicator (see src/fraud/detector.py).
    """
    before = len(df)
    if ID_COLUMN in df.columns:
        df = df.drop_duplicates(subset=[ID_COLUMN], keep="first")
    df = df.drop_duplicates(keep="first")
    removed = before - len(df)
    if removed:
        logger.info("Removed %d duplicate row(s).", removed)
    return df


def ingest(source_path: Optional[Path] = None, strict: bool = True) -> Tuple[pd.DataFrame, ValidationReport]:
    """Load, validate and deduplicate the raw dataset."""
    source = Path(source_path) if source_path else settings.raw_dataset_path
    df = load_raw(source)
    report = validate_dataframe(df, require_target=True)
    for warning in report.warnings:
        logger.warning("Validation: %s", warning)
    if strict:
        report.raise_if_invalid()
    return deduplicate(df), report
