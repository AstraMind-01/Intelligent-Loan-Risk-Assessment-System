"""Retraining orchestration with challenger/champion promotion and rollback.

A retrain never overwrites the serving model. The new model is registered as a
*challenger* and only becomes active if it beats the incumbent by a configured
margin on the same held-out data. If it does not, it stays on disk for
inspection and the champion keeps serving.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.config import BASE_FEATURES, TARGET, settings
from src.data.validation import validate_dataframe
from src.models import registry
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

OUTCOMES_FILE = "loan_outcomes.jsonl"
JOB_STATE_FILE = "retraining_jobs.json"

_job_lock = threading.Lock()


@dataclass
class PromotionDecision:
    promoted: bool
    reason: str
    champion_version: Optional[str]
    challenger_version: str
    champion_auc: Optional[float]
    challenger_auc: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "promoted": self.promoted,
            "reason": self.reason,
            "championVersion": self.champion_version,
            "challengerVersion": self.challenger_version,
            "championAuc": self.champion_auc,
            "challengerAuc": self.challenger_auc,
        }


# ---------------------------------------------------------------------------
# Outcome ingestion
# ---------------------------------------------------------------------------
def _outcomes_path() -> Path:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.data_dir / OUTCOMES_FILE


def record_outcome(application: Dict[str, Any], defaulted: int,
                   application_id: Optional[str] = None) -> Dict[str, Any]:
    """Append a realised loan outcome to the retraining corpus.

    This is the feedback loop: the backend calls it once a loan's repayment
    status is known, and those rows are appended to the training data on the next
    retrain so the model learns from its own portfolio rather than only the
    historical dataset.
    """
    from src.inference.adapter import normalize_payload

    record = normalize_payload(application)
    record[TARGET] = int(bool(defaulted))
    entry = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "application_id": application_id,
        **record,
    }
    with open(_outcomes_path(), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, default=str) + "\n")
    return entry


def load_outcomes() -> pd.DataFrame:
    """All recorded outcomes as a training-ready frame."""
    path = _outcomes_path()
    if not path.exists():
        return pd.DataFrame(columns=BASE_FEATURES + [TARGET])

    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not rows:
        return pd.DataFrame(columns=BASE_FEATURES + [TARGET])
    return pd.DataFrame(rows).reindex(columns=BASE_FEATURES + [TARGET])


def build_retraining_dataset(include_outcomes: bool = True) -> tuple[pd.DataFrame, Dict[str, Any]]:
    """Historical dataset plus any realised outcomes collected since."""
    from src.data.loader import deduplicate, load_raw

    base = load_raw()
    stats = {"historical_rows": len(base), "outcome_rows": 0}

    if include_outcomes:
        outcomes = load_outcomes()
        outcomes = outcomes.dropna(subset=[TARGET])
        if len(outcomes):
            stats["outcome_rows"] = len(outcomes)
            base = pd.concat([base, outcomes], ignore_index=True)
            logger.info("Appended %d realised outcome(s) to the training set.", len(outcomes))

    combined = deduplicate(base)
    stats["total_rows"] = len(combined)
    return combined, stats


# ---------------------------------------------------------------------------
# Promotion
# ---------------------------------------------------------------------------
def compare_and_promote(challenger_version: str,
                        champion_version: Optional[str] = None) -> PromotionDecision:
    """Decide whether a freshly trained challenger should take over serving.

    Both models are judged on the AUC recorded against their own held-out test
    split. The comparison uses the same pipeline, seed and split ratios, so the
    splits are drawn identically; the guard is the required improvement margin,
    which stops a model being promoted on noise.
    """
    challenger_meta = registry.get_metadata(challenger_version)
    if challenger_meta is None:
        raise FileNotFoundError(f"No metadata for challenger '{challenger_version}'.")
    challenger_auc = (challenger_meta.metrics or {}).get("roc_auc")

    champion_version = champion_version or registry.get_active_pointer().get("previous_version") \
        or registry.get_active_version()

    if champion_version is None or champion_version == challenger_version:
        registry.set_active_version(challenger_version)
        return PromotionDecision(
            promoted=True,
            reason="No incumbent model; the challenger becomes the first active version.",
            champion_version=None,
            challenger_version=challenger_version,
            champion_auc=None,
            challenger_auc=challenger_auc,
        )

    champion_meta = registry.get_metadata(champion_version)
    champion_auc = (champion_meta.metrics or {}).get("roc_auc") if champion_meta else None

    if champion_auc is None:
        registry.set_active_version(challenger_version)
        return PromotionDecision(
            promoted=True,
            reason="Incumbent has no recorded AUC; promoting the challenger.",
            champion_version=champion_version,
            challenger_version=challenger_version,
            champion_auc=None,
            challenger_auc=challenger_auc,
        )

    gain = (challenger_auc or 0.0) - champion_auc
    if gain >= settings.promotion_min_auc_gain:
        registry.set_active_version(challenger_version)
        return PromotionDecision(
            promoted=True,
            reason=(f"Challenger AUC {challenger_auc:.4f} beats champion {champion_auc:.4f} "
                    f"by {gain:+.4f}, clearing the required margin of "
                    f"{settings.promotion_min_auc_gain:.4f}."),
            champion_version=champion_version,
            challenger_version=challenger_version,
            champion_auc=champion_auc,
            challenger_auc=challenger_auc,
        )

    # Not good enough: restore the incumbent as the serving model.
    registry.set_active_version(champion_version)
    return PromotionDecision(
        promoted=False,
        reason=(f"Challenger AUC {challenger_auc:.4f} does not beat champion {champion_auc:.4f} "
                f"by the required margin ({gain:+.4f} < "
                f"{settings.promotion_min_auc_gain:.4f}); the champion stays active."),
        champion_version=champion_version,
        challenger_version=challenger_version,
        champion_auc=champion_auc,
        challenger_auc=challenger_auc,
    )


def rollback_to_previous() -> Dict[str, Any]:
    """Restore the previously active model version."""
    previous = registry.rollback()
    return {
        "rolledBack": True,
        "activeVersion": previous,
        "message": f"Active model restored to {previous}.",
    }


# ---------------------------------------------------------------------------
# Job orchestration
# ---------------------------------------------------------------------------
def _jobs_path() -> Path:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    return settings.log_dir / JOB_STATE_FILE


def _write_job(job: Dict[str, Any]) -> None:
    path = _jobs_path()
    jobs = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    jobs = [j for j in jobs if j["jobId"] != job["jobId"]]
    jobs.append(job)
    path.write_text(json.dumps(jobs[-50:], indent=2, default=str), encoding="utf-8")


def get_jobs(limit: int = 20) -> List[Dict[str, Any]]:
    path = _jobs_path()
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))[-limit:]


def should_retrain() -> Dict[str, Any]:
    """Evaluate the automatic retraining triggers.

    Three independent triggers, any of which is sufficient: sustained data or
    prediction drift, measured performance degradation, or a large enough backlog
    of new realised outcomes to be worth learning from.
    """
    from src.inference.predictor import get_predictor, is_model_available
    from src.monitoring.drift import drift_report_from_logs
    from src.monitoring.performance import performance_trend

    reasons: List[str] = []

    if not is_model_available():
        return {"shouldRetrain": True, "reasons": ["No active model exists."], "triggers": {}}

    triggers: Dict[str, Any] = {}
    try:
        drift = drift_report_from_logs(get_predictor())
        triggers["drift"] = {"status": drift.get("status"), "detected": drift.get("driftDetected")}
        if drift.get("driftDetected"):
            reasons.append("Data or prediction drift exceeded the alert threshold.")
    except Exception as exc:  # noqa: BLE001
        triggers["drift"] = {"status": "unavailable", "error": str(exc)}

    trend = performance_trend()
    triggers["performance"] = {"status": trend.get("status"), "alert": trend.get("alert")}
    if trend.get("alert"):
        reasons.append(trend.get("recommendation", "Performance degradation detected."))

    outcomes = load_outcomes()
    triggers["newOutcomes"] = {"count": len(outcomes), "threshold": 1000}
    if len(outcomes) >= 1000:
        reasons.append(f"{len(outcomes)} new realised outcomes are available for training.")

    return {"shouldRetrain": bool(reasons), "reasons": reasons, "triggers": triggers}


def run_retraining_job(
    job_id: str,
    include_outcomes: bool = True,
    auto_promote: bool = True,
    triggered_by: str = "manual",
    notes: str = "",
) -> Dict[str, Any]:
    """Execute one retraining run end to end.

    Serialised behind a lock: two concurrent retrains would race on the registry's
    active pointer and could leave an untested model serving traffic.
    """
    if not _job_lock.acquire(blocking=False):
        return {"jobId": job_id, "status": "rejected",
                "message": "A retraining job is already running."}

    job: Dict[str, Any] = {
        "jobId": job_id,
        "status": "running",
        "triggeredBy": triggered_by,
        "startedAt": datetime.now(timezone.utc).isoformat(),
    }
    _write_job(job)

    try:
        from src.models.train import train

        champion_version = registry.get_active_version()

        dataset, stats = build_retraining_dataset(include_outcomes)
        report = validate_dataframe(dataset, require_target=True)
        report.raise_if_invalid()

        # Persist the merged corpus so the run is reproducible from disk.
        settings.raw_data_dir.mkdir(parents=True, exist_ok=True)
        merged_path = settings.raw_data_dir / f"retrain_{job_id}.csv"
        dataset.to_csv(merged_path, index=False)

        # Train without activating: promotion is a separate, guarded decision.
        result = train(
            source_path=str(merged_path),
            set_active=False,
            notes=notes or f"Retraining job {job_id} ({triggered_by}).",
        )

        decision = (
            compare_and_promote(result.version, champion_version)
            if auto_promote
            else PromotionDecision(
                promoted=False,
                reason="auto_promote disabled; challenger registered without activation.",
                champion_version=champion_version,
                challenger_version=result.version,
                champion_auc=(registry.get_metadata(champion_version).metrics or {}).get("roc_auc")
                if champion_version else None,
                challenger_auc=(result.metadata.metrics or {}).get("roc_auc"),
            )
        )

        if decision.promoted:
            from src.inference.predictor import get_predictor
            get_predictor(reload=True)  # swap the serving model in place

        job.update({
            "status": "completed",
            "finishedAt": datetime.now(timezone.utc).isoformat(),
            "challengerVersion": result.version,
            "datasetStats": stats,
            "promotion": decision.to_dict(),
            "activeVersion": registry.get_active_version(),
        })
        logger.info("Retraining job %s finished: %s", job_id, decision.reason)

    except Exception as exc:  # noqa: BLE001
        logger.exception("Retraining job %s failed.", job_id)
        job.update({
            "status": "failed",
            "finishedAt": datetime.now(timezone.utc).isoformat(),
            "error": str(exc),
        })
    finally:
        _write_job(job)
        _job_lock.release()

    return job
