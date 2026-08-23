"""Data validation schema.

Checks a dataframe for the three failure modes that silently corrupt a credit
model: missing values, wrong types, and out-of-range values. Used by the
training pipeline (hard fail) and by the inference path (soft fail -> repair).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.config import (
    CATEGORICAL_FEATURES,
    CATEGORICAL_LEVELS,
    FEATURE_BOUNDS,
    NUMERIC_FEATURES,
    TARGET,
)
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationReport:
    """Outcome of a validation run."""

    n_rows: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    missing_counts: Dict[str, int] = field(default_factory=dict)
    out_of_range_counts: Dict[str, int] = field(default_factory=dict)
    unknown_categories: Dict[str, List[Any]] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "n_rows": self.n_rows,
            "errors": self.errors,
            "warnings": self.warnings,
            "missing_counts": self.missing_counts,
            "out_of_range_counts": self.out_of_range_counts,
            "unknown_categories": self.unknown_categories,
        }

    def raise_if_invalid(self) -> None:
        if not self.is_valid:
            raise ValueError("Data validation failed:\n  - " + "\n  - ".join(self.errors))


def validate_dataframe(df: pd.DataFrame, require_target: bool = True,
                       require_all_features: bool = True) -> ValidationReport:
    """Validate a dataframe against the canonical loan schema.

    Args:
        df: frame to check.
        require_target: whether the ``Default`` column must be present (training).
        require_all_features: whether every base feature must be present. Inference
            payloads may legitimately omit columns the backend cannot supply, which
            are imputed downstream, so this is relaxed there.
    """
    report = ValidationReport(n_rows=len(df))

    if df.empty:
        report.errors.append("Dataframe is empty.")
        return report

    # -- presence ----------------------------------------------------------
    expected = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    missing_cols = [c for c in expected if c not in df.columns]
    if missing_cols:
        message = f"Missing columns: {missing_cols}"
        (report.errors if require_all_features else report.warnings).append(message)

    if require_target:
        if TARGET not in df.columns:
            report.errors.append(f"Missing target column '{TARGET}'.")
        else:
            bad = set(pd.unique(df[TARGET].dropna())) - {0, 1}
            if bad:
                report.errors.append(f"Target '{TARGET}' must be binary 0/1, found {sorted(bad)}.")

    # -- types and ranges --------------------------------------------------
    for col in NUMERIC_FEATURES:
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        n_coerce_failures = int(series.isna().sum() - df[col].isna().sum())
        if n_coerce_failures > 0:
            report.errors.append(
                f"Column '{col}' has {n_coerce_failures} non-numeric value(s)."
            )

        n_missing = int(series.isna().sum())
        if n_missing:
            report.missing_counts[col] = n_missing

        low, high = FEATURE_BOUNDS[col]
        n_out = int(((series < low) | (series > high)).sum())
        if n_out:
            report.out_of_range_counts[col] = n_out
            report.warnings.append(
                f"Column '{col}' has {n_out} value(s) outside [{low}, {high}]; they will be clipped."
            )

    for col in CATEGORICAL_FEATURES:
        if col not in df.columns:
            continue
        n_missing = int(df[col].isna().sum())
        if n_missing:
            report.missing_counts[col] = n_missing

        allowed = set(CATEGORICAL_LEVELS[col])
        seen = set(df[col].dropna().astype(str).unique())
        unknown = sorted(seen - allowed)
        if unknown:
            report.unknown_categories[col] = unknown
            report.warnings.append(
                f"Column '{col}' has unrecognised level(s) {unknown}; they will be treated as missing."
            )

    # -- dataset-level sanity ---------------------------------------------
    if require_target and TARGET in df.columns:
        positive_rate = float(df[TARGET].mean())
        if positive_rate == 0 or positive_rate == 1:
            report.errors.append(f"Target has a single class (positive rate {positive_rate}).")
        elif positive_rate < 0.01:
            report.warnings.append(
                f"Severe class imbalance: positive rate is {positive_rate:.4f}."
            )

    total_missing = sum(report.missing_counts.values())
    if total_missing:
        logger.warning("Validation found %d missing value(s) across %d column(s).",
                       total_missing, len(report.missing_counts))

    return report


def repair_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce a frame into the canonical schema without dropping rows.

    Numerics are coerced and clipped to their allowed bounds; unknown categorical
    levels become NaN so the imputer can fill them with the training mode. This is
    what the inference path uses: a bad field degrades one feature, it does not
    reject the whole application.
    """
    out = df.copy()

    for col in NUMERIC_FEATURES:
        if col not in out.columns:
            out[col] = np.nan
            continue
        low, high = FEATURE_BOUNDS[col]
        out[col] = pd.to_numeric(out[col], errors="coerce").clip(low, high)

    for col in CATEGORICAL_FEATURES:
        if col not in out.columns:
            out[col] = None
            continue
        allowed = set(CATEGORICAL_LEVELS[col])

        def _clean(value: Any, allowed: set = allowed) -> Optional[str]:
            if value is None or (isinstance(value, float) and np.isnan(value)):
                return None
            text = str(value)
            return text if text in allowed else None

        # Plain ``None`` rather than pandas' nullable ``pd.NA``: scikit-learn's
        # SimpleImputer probes missingness with ``X != X`` on object arrays, and
        # that comparison raises on pd.NA ("boolean value of NA is ambiguous").
        out[col] = out[col].map(_clean).astype(object)

    return out
