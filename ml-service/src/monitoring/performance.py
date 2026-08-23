"""Performance tracking over time and officer/AI agreement.

Metrics are appended to ``logs/performance_history.jsonl`` so the Admin panel can
plot accuracy and AUC per period without a database round-trip, and so the
retraining trigger has a history to compare against.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from src.config import settings
from src.models.evaluate import classification_metrics
from src.utils.logging_config import get_logger, prediction_log

logger = get_logger(__name__)

HISTORY_FILE = "performance_history.jsonl"


def _history_path() -> Path:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    return settings.log_dir / HISTORY_FILE


def record_period_metrics(
    model_version: str,
    y_true: Sequence[int],
    y_prob: Sequence[float],
    period_label: Optional[str] = None,
    threshold: float = 0.5,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Score a period's realised outcomes and append them to the history file.

    Called once actual repayment outcomes are known for a cohort — this is the
    only way to measure whether the model is still working, as opposed to merely
    still running.
    """
    metrics = classification_metrics(y_true, y_prob, threshold)
    entry = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "period": period_label or datetime.now(timezone.utc).strftime("%Y-%m"),
        "model_version": model_version,
        "accuracy": metrics["accuracy"],
        "roc_auc": metrics["roc_auc"],
        "precision": metrics["precision"],
        "recall": metrics["recall"],
        "f1": metrics["f1"],
        "average_precision": metrics["average_precision"],
        "n_observations": metrics["support"]["n"],
        **(extra or {}),
    }

    with open(_history_path(), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")

    if metrics["roc_auc"] < settings.min_acceptable_auc:
        logger.warning(
            "Performance alert: AUC %.4f for period %s is below the minimum %.4f.",
            metrics["roc_auc"], entry["period"], settings.min_acceptable_auc,
        )
    return entry


def load_history(limit: int = 100) -> List[Dict[str, Any]]:
    path = _history_path()
    if not path.exists():
        return []
    entries: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries[-limit:]


def performance_trend(limit: int = 100) -> Dict[str, Any]:
    """Recent performance history plus a degradation check."""
    history = load_history(limit)
    if not history:
        return {"periods": [], "status": "no_history", "alert": False}

    latest = history[-1]
    aucs = [h["roc_auc"] for h in history if h.get("roc_auc") is not None]

    # Compare the latest period against the mean of the preceding ones.
    baseline = float(np.mean(aucs[:-1])) if len(aucs) > 1 else latest.get("roc_auc", 0.0)
    degradation = baseline - latest.get("roc_auc", 0.0)

    below_minimum = latest.get("roc_auc", 1.0) < settings.min_acceptable_auc
    significant_drop = degradation > 0.03

    return {
        "periods": history,
        "latest": latest,
        "baselineAuc": round(baseline, 4),
        "latestAuc": latest.get("roc_auc"),
        "aucDegradation": round(degradation, 4),
        "minimumAuc": settings.min_acceptable_auc,
        "belowMinimum": below_minimum,
        "significantDrop": significant_drop,
        "alert": bool(below_minimum or significant_drop),
        "status": "degraded" if (below_minimum or significant_drop) else "healthy",
        "recommendation": (
            "Trigger retraining: performance has fallen below the acceptable threshold."
            if below_minimum
            else "Investigate: AUC dropped materially versus the historical baseline."
            if significant_drop
            else "No action required."
        ),
    }


def officer_agreement_rate(decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """How often officers accept the AI recommendation.

    Each entry needs ``aiRecommendation`` and ``finalDecision`` (approve /
    reject / review). A falling agreement rate is an early warning that the model
    has drifted away from what underwriters consider sound — often before
    realised default data would show it.
    """
    comparable = [
        d for d in decisions
        if d.get("aiRecommendation") in ("approve", "reject")
        and d.get("finalDecision") in ("approve", "reject")
    ]
    if not comparable:
        return {"agreementRate": None, "sampleSize": 0, "status": "no_data"}

    agreements = [d["aiRecommendation"] == d["finalDecision"] for d in comparable]
    rate = float(np.mean(agreements))

    overrides = [d for d, agreed in zip(comparable, agreements) if not agreed]
    override_direction = {
        "ai_reject_officer_approve": sum(
            1 for d in overrides if d["aiRecommendation"] == "reject"
        ),
        "ai_approve_officer_reject": sum(
            1 for d in overrides if d["aiRecommendation"] == "approve"
        ),
    }

    return {
        "agreementRate": round(rate, 4),
        "sampleSize": len(comparable),
        "overrideCount": len(overrides),
        "overrideDirection": override_direction,
        "status": "healthy" if rate >= 0.80 else "review" if rate >= 0.65 else "concerning",
        "interpretation": (
            "Officers accept the model's recommendation in "
            f"{rate:.0%} of comparable decisions."
            + (
                " Officers overturn declines more often than approvals, which suggests the "
                "model is too conservative."
                if override_direction["ai_reject_officer_approve"]
                > override_direction["ai_approve_officer_reject"]
                else " Officers overturn approvals more often than declines, which suggests the "
                "model is too permissive."
                if override_direction["ai_approve_officer_reject"]
                > override_direction["ai_reject_officer_approve"]
                else ""
            )
        ),
    }


def throughput_summary(window: int = 1000) -> Dict[str, Any]:
    """Volume and latency from the prediction log."""
    records = [r for r in prediction_log.read_all() if r.get("event") == "predict"][-window:]
    if not records:
        return {"totalPredictions": 0, "avgLatencyMs": None}

    latencies = [r.get("latency_ms", 0.0) for r in records]
    scores = [r["response"].get("riskScore", 0.0) for r in records]
    levels = [r["response"].get("riskLevel") for r in records]

    return {
        "totalPredictions": len(records),
        "avgLatencyMs": round(float(np.mean(latencies)), 2),
        "p95LatencyMs": round(float(np.percentile(latencies, 95)), 2),
        "meanRiskScore": round(float(np.mean(scores)), 2),
        "riskLevelCounts": {
            level: levels.count(level) for level in ("low", "medium", "high")
        },
        "fraudFlagged": sum(1 for r in records if r["response"].get("fraudFlag")),
        "windowStart": records[0]["timestamp"],
        "windowEnd": records[-1]["timestamp"],
    }
