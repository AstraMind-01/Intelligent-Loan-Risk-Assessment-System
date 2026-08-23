"""Versioned model registry.

Layout on disk::

    models/
      active.json                  <- pointer to the serving version
      v20260823-101500/
        model.joblib               <- preprocessor + estimator + thresholds
        metadata.json              <- metrics, hyperparameters, dataset version
        background.joblib          <- SHAP background sample
      v20260822-090000/
        ...

The active pointer is what the inference service loads, which makes promotion and
rollback a single small file write rather than a redeploy.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib

from src.config import settings
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

ACTIVE_POINTER = "active.json"
MODEL_FILE = "model.joblib"
METADATA_FILE = "metadata.json"
BACKGROUND_FILE = "background.joblib"


@dataclass
class ModelMetadata:
    """Everything needed to reproduce and audit a trained model."""

    version: str
    created_at: str
    algorithm: str
    dataset_version: str
    dataset_rows: int
    feature_count: int
    feature_names: List[str] = field(default_factory=list)
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    thresholds: Dict[str, float] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    validation_metrics: Dict[str, Any] = field(default_factory=dict)
    cv_results: Dict[str, Any] = field(default_factory=dict)
    baseline_comparison: Dict[str, Any] = field(default_factory=dict)
    fairness: Dict[str, Any] = field(default_factory=dict)
    training_reference: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def make_version_tag() -> str:
    return f"v{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"


def version_dir(version: str) -> Path:
    return settings.registry_dir / version


def save_model(artifacts: Dict[str, Any], metadata: ModelMetadata,
               background: Any = None, set_active: bool = True) -> Path:
    """Persist a trained bundle under its version tag."""
    target = version_dir(metadata.version)
    target.mkdir(parents=True, exist_ok=True)

    joblib.dump(artifacts, target / MODEL_FILE, compress=3)
    if background is not None:
        joblib.dump(background, target / BACKGROUND_FILE, compress=3)

    with open(target / METADATA_FILE, "w", encoding="utf-8") as handle:
        json.dump(metadata.to_dict(), handle, indent=2, default=str)

    logger.info("Saved model version %s to %s", metadata.version, target)
    if set_active:
        set_active_version(metadata.version)
    return target


def set_active_version(version: str) -> None:
    """Point the serving pointer at ``version``."""
    if not (version_dir(version) / MODEL_FILE).exists():
        raise FileNotFoundError(f"Cannot activate '{version}': no model file found.")

    settings.registry_dir.mkdir(parents=True, exist_ok=True)
    previous = get_active_version()
    payload = {
        "active_version": version,
        "previous_version": previous,
        "activated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(settings.registry_dir / ACTIVE_POINTER, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    logger.info("Active model set to %s (was %s)", version, previous)


def get_active_pointer() -> Dict[str, Any]:
    pointer_path = settings.registry_dir / ACTIVE_POINTER
    if not pointer_path.exists():
        return {}
    with open(pointer_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def get_active_version() -> Optional[str]:
    return get_active_pointer().get("active_version")


def rollback() -> str:
    """Reactivate the previously active version.

    The safety valve for a bad promotion: if a challenger degrades in production,
    this restores the last known-good model without a rebuild.
    """
    pointer = get_active_pointer()
    previous = pointer.get("previous_version")
    if not previous:
        raise RuntimeError("No previous version recorded; nothing to roll back to.")
    if not (version_dir(previous) / MODEL_FILE).exists():
        raise FileNotFoundError(f"Previous version '{previous}' is no longer on disk.")
    set_active_version(previous)
    return previous


def load_model(version: Optional[str] = None) -> tuple[Dict[str, Any], ModelMetadata]:
    """Load a model bundle; defaults to the active version."""
    version = version or get_active_version()
    if not version:
        raise FileNotFoundError(
            "No active model. Run `python scripts/train_model.py` to train one."
        )

    target = version_dir(version)
    model_path = target / MODEL_FILE
    if not model_path.exists():
        raise FileNotFoundError(f"Model file missing for version '{version}'.")

    artifacts = joblib.load(model_path)
    with open(target / METADATA_FILE, "r", encoding="utf-8") as handle:
        metadata = ModelMetadata(**json.load(handle))
    logger.info("Loaded model version %s (%s)", version, metadata.algorithm)
    return artifacts, metadata


def load_background(version: Optional[str] = None) -> Any:
    """SHAP background sample stored alongside a model, if any."""
    version = version or get_active_version()
    if not version:
        return None
    path = version_dir(version) / BACKGROUND_FILE
    return joblib.load(path) if path.exists() else None


def list_versions() -> List[Dict[str, Any]]:
    """Registry contents, newest first, with the active one flagged."""
    if not settings.registry_dir.exists():
        return []

    active = get_active_version()
    versions: List[Dict[str, Any]] = []
    for entry in sorted(settings.registry_dir.iterdir(), reverse=True):
        meta_path = entry / METADATA_FILE
        if not (entry.is_dir() and meta_path.exists()):
            continue
        with open(meta_path, "r", encoding="utf-8") as handle:
            meta = json.load(handle)
        versions.append({
            "version": meta.get("version", entry.name),
            "created_at": meta.get("created_at"),
            "algorithm": meta.get("algorithm"),
            "dataset_version": meta.get("dataset_version"),
            "roc_auc": meta.get("metrics", {}).get("roc_auc"),
            "accuracy": meta.get("metrics", {}).get("accuracy"),
            "is_active": meta.get("version") == active,
        })
    return versions


def get_metadata(version: Optional[str] = None) -> Optional[ModelMetadata]:
    version = version or get_active_version()
    if not version:
        return None
    meta_path = version_dir(version) / METADATA_FILE
    if not meta_path.exists():
        return None
    with open(meta_path, "r", encoding="utf-8") as handle:
        return ModelMetadata(**json.load(handle))


def prune(keep: int = 5) -> List[str]:
    """Delete old versions, always keeping the active and previous ones."""
    pointer = get_active_pointer()
    protected = {pointer.get("active_version"), pointer.get("previous_version")} - {None}

    all_versions = [v["version"] for v in list_versions()]
    removed: List[str] = []
    for version in all_versions[keep:]:
        if version in protected:
            continue
        shutil.rmtree(version_dir(version), ignore_errors=True)
        removed.append(version)
    if removed:
        logger.info("Pruned %d old model version(s): %s", len(removed), removed)
    return removed
