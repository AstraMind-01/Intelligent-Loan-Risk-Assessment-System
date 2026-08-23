"""Data and prediction drift detection.

Population Stability Index (PSI) is the standard measure in credit risk, and the
0.10 / 0.25 thresholds used here are the conventional warn/alert bands. PSI is
computed per feature against the training reference sample, plus once over the
predicted risk-score distribution to catch prediction drift even when no single
input feature has moved.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from src.config import ALL_CATEGORICAL, ALL_NUMERIC, settings
from src.utils.logging_config import get_logger, prediction_log

logger = get_logger(__name__)

_EPS = 1e-6


def population_stability_index(expected: Sequence[float], actual: Sequence[float],
                               bins: int = 10) -> float:
    """PSI between a reference and a current numeric distribution.

    Bin edges come from the reference quantiles, so a stable population yields
    roughly uniform bin shares and a PSI near zero.
    """
    expected = np.asarray(expected, dtype="float64")
    actual = np.asarray(actual, dtype="float64")
    expected = expected[np.isfinite(expected)]
    actual = actual[np.isfinite(actual)]

    if len(expected) < bins or len(actual) == 0:
        return 0.0

    quantiles = np.linspace(0, 100, bins + 1)
    edges = np.unique(np.percentile(expected, quantiles))
    if len(edges) < 3:  # a near-constant reference cannot drift meaningfully
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf

    expected_share = np.histogram(expected, bins=edges)[0] / len(expected)
    actual_share = np.histogram(actual, bins=edges)[0] / len(actual)

    expected_share = np.clip(expected_share, _EPS, None)
    actual_share = np.clip(actual_share, _EPS, None)
    return float(np.sum((actual_share - expected_share) * np.log(actual_share / expected_share)))


def categorical_psi(expected: Sequence[Any], actual: Sequence[Any]) -> float:
    """PSI over category shares."""
    expected_counts = pd.Series(expected).astype("string").value_counts(normalize=True)
    actual_counts = pd.Series(actual).astype("string").value_counts(normalize=True)

    levels = expected_counts.index.union(actual_counts.index)
    expected_share = np.clip(expected_counts.reindex(levels, fill_value=0.0).to_numpy(), _EPS, None)
    actual_share = np.clip(actual_counts.reindex(levels, fill_value=0.0).to_numpy(), _EPS, None)
    return float(np.sum((actual_share - expected_share) * np.log(actual_share / expected_share)))


def _classify(psi: float) -> str:
    if psi >= settings.drift_psi_alert:
        return "alert"
    if psi >= settings.drift_psi_warn:
        return "warning"
    return "stable"


def detect_feature_drift(reference: pd.DataFrame, current: pd.DataFrame,
                         features: Optional[List[str]] = None) -> Dict[str, Any]:
    """Per-feature PSI between a training reference sample and recent traffic."""
    numeric = [c for c in (features or ALL_NUMERIC) if c in reference.columns and c in current.columns
               and c in ALL_NUMERIC]
    categorical = [c for c in (features or ALL_CATEGORICAL) if c in reference.columns
                   and c in current.columns and c in ALL_CATEGORICAL]

    results: Dict[str, Dict[str, Any]] = {}
    for column in numeric:
        psi = population_stability_index(
            pd.to_numeric(reference[column], errors="coerce"),
            pd.to_numeric(current[column], errors="coerce"),
        )
        results[column] = {"psi": round(psi, 4), "status": _classify(psi), "type": "numeric"}

    for column in categorical:
        psi = categorical_psi(reference[column], current[column])
        results[column] = {"psi": round(psi, 4), "status": _classify(psi), "type": "categorical"}

    drifted = [c for c, r in results.items() if r["status"] in ("warning", "alert")]
    alerting = [c for c, r in results.items() if r["status"] == "alert"]
    max_psi = max((r["psi"] for r in results.values()), default=0.0)

    return {
        "features": results,
        "featuresChecked": len(results),
        "driftedFeatures": drifted,
        "alertingFeatures": alerting,
        "maxPsi": round(max_psi, 4),
        "meanPsi": round(float(np.mean([r["psi"] for r in results.values()])), 4) if results else 0.0,
        "status": _classify(max_psi),
        "driftDetected": bool(alerting),
    }


def detect_prediction_drift(reference_scores: Sequence[float],
                            current_scores: Sequence[float]) -> Dict[str, Any]:
    """Shift in the risk-score distribution itself.

    Catches the case where individual features look stable but their combination
    has moved — the failure mode that per-feature monitoring alone misses.
    """
    reference_scores = np.asarray(reference_scores, dtype="float64")
    current_scores = np.asarray(current_scores, dtype="float64")

    if len(current_scores) == 0:
        return {"status": "no_data", "psi": 0.0, "driftDetected": False}

    psi = population_stability_index(reference_scores, current_scores)
    return {
        "psi": round(psi, 4),
        "status": _classify(psi),
        "driftDetected": psi >= settings.drift_psi_alert,
        "referenceMean": round(float(reference_scores.mean()), 2) if len(reference_scores) else None,
        "currentMean": round(float(current_scores.mean()), 2),
        "meanShift": (
            round(float(current_scores.mean() - reference_scores.mean()), 2)
            if len(reference_scores) else None
        ),
        "sampleSize": int(len(current_scores)),
    }


def drift_report_from_logs(predictor, window: int = 1000) -> Dict[str, Any]:
    """Build a drift report from the service's own prediction log.

    Uses the most recent ``window`` scored applications as the current
    population and the model's stored training sample as the reference, so drift
    monitoring needs no external data feed to start working.
    """
    records = prediction_log.read_all()
    recent = [r for r in records if r.get("event") == "predict"][-window:]

    if len(recent) < 30:
        return {
            "status": "insufficient_data",
            "message": f"Only {len(recent)} prediction(s) logged; at least 30 are needed.",
            "sampleSize": len(recent),
            "driftDetected": False,
        }

    current = pd.DataFrame([r["request"]["normalized"] for r in recent])
    current_scores = np.array([r["response"]["riskScore"] for r in recent], dtype="float64")

    reference = predictor.train_reference_sample
    feature_drift: Dict[str, Any] = {"status": "no_reference", "driftDetected": False}
    if reference is not None and len(reference):
        feature_drift = detect_feature_drift(reference, current)

    reference_scores = np.asarray(
        (predictor.metadata.metrics or {}).get("score_distribution_sample", []), dtype="float64"
    )
    if reference_scores.size == 0:
        # Fall back to the score distribution summary captured at training time.
        distribution = (predictor.metadata.metrics or {}).get("score_distribution", {})
        reference_scores = np.array(
            [distribution.get("p10", 10), distribution.get("p50", 30), distribution.get("p90", 70)],
            dtype="float64",
        ) if distribution else np.array([])

    prediction_drift = detect_prediction_drift(reference_scores, current_scores)

    overall = "alert" if (feature_drift.get("driftDetected") or prediction_drift.get("driftDetected")) \
        else "warning" if feature_drift.get("status") == "warning" else "stable"

    return {
        "status": overall,
        "driftDetected": overall == "alert",
        "sampleSize": len(recent),
        "windowStart": recent[0]["timestamp"],
        "windowEnd": recent[-1]["timestamp"],
        "featureDrift": feature_drift,
        "predictionDrift": prediction_drift,
        "thresholds": {"warn": settings.drift_psi_warn, "alert": settings.drift_psi_alert},
        "recommendation": (
            "Retrain the model against recent data." if overall == "alert"
            else "Monitor; no action required." if overall == "stable"
            else "Investigate the drifting features before the next scheduled retrain."
        ),
    }
