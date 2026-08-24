"""Model evaluation, threshold tuning and the probability -> risk-score mapping."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

from src.config import settings
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class RiskThresholds:
    """Probability cut points separating the low / medium / high risk buckets."""

    low_cutoff: float   # P(default) below this -> low risk  -> score < 25
    high_cutoff: float  # P(default) above this -> high risk -> score > 75
    decision_threshold: float  # binary classification cut used for reported metrics

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


def classification_metrics(y_true: Sequence[int], y_prob: Sequence[float],
                           threshold: float = 0.5) -> Dict[str, float]:
    """Headline metrics at a given decision threshold.

    AUC-ROC and average precision are threshold-free and are the numbers to trust
    on an 11.6%-positive dataset; accuracy is reported only because stakeholders
    ask for it.
    """
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob, dtype="float64")
    y_pred = (y_prob >= threshold).astype(int)

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "average_precision": float(average_precision_score(y_true, y_prob)),
        "brier_score": float(brier_score_loss(y_true, y_prob)),
        "threshold": float(threshold),
        "confusion_matrix": {
            "true_negative": int(tn),
            "false_positive": int(fp),
            "false_negative": int(fn),
            "true_positive": int(tp),
        },
        "support": {
            "n": int(len(y_true)),
            "positives": int(y_true.sum()),
            "negatives": int(len(y_true) - y_true.sum()),
        },
    }


def curve_points(y_true: Sequence[int], y_prob: Sequence[float],
                 max_points: int = 200) -> Dict[str, List[Dict[str, float]]]:
    """Down-sampled ROC and precision-recall curves for the Admin dashboard."""
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob, dtype="float64")

    fpr, tpr, _ = roc_curve(y_true, y_prob)
    precision, recall, _ = precision_recall_curve(y_true, y_prob)

    def _thin(a: np.ndarray, b: np.ndarray) -> List[Dict[str, float]]:
        if len(a) <= max_points:
            idx = np.arange(len(a))
        else:
            idx = np.linspace(0, len(a) - 1, max_points).astype(int)
        return [{"x": float(a[i]), "y": float(b[i])} for i in idx]

    return {"roc": _thin(fpr, tpr), "precision_recall": _thin(recall, precision)}


def tune_thresholds(
    y_true: Sequence[int],
    y_prob: Sequence[float],
    target_recall: float = 0.95,
    high_risk_precision_multiple: float = 2.5,
) -> RiskThresholds:
    """Derive the low/medium/high probability cut points from a validation set.

    ``low_cutoff`` is the highest probability at which we still catch
    ``target_recall`` of real defaulters — below it, an application is genuinely
    safe to auto-approve.

    ``high_cutoff`` is the lowest probability at which the default rate among
    flagged applicants is ``high_risk_precision_multiple`` times the portfolio
    base rate — above it, auto-rejection is defensible.

    Both fall back to distribution quantiles when the data cannot support the
    target, so this never returns a degenerate threshold.
    """
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob, dtype="float64")
    base_rate = float(y_true.mean())

    precision, recall, thresholds = precision_recall_curve(y_true, y_prob)
    # precision_recall_curve returns one more point than thresholds.
    precision, recall = precision[:-1], recall[:-1]

    # -- low cutoff: preserve recall --------------------------------------
    recall_ok = np.flatnonzero(recall >= target_recall)
    if recall_ok.size:
        low_cutoff = float(thresholds[recall_ok[-1]])
    else:
        low_cutoff = float(np.quantile(y_prob, 0.25))
        logger.warning("Could not reach target recall %.2f; using 25th percentile for low cutoff.",
                       target_recall)

    # -- high cutoff: demand lift over the base rate -----------------------
    target_precision = min(0.95, base_rate * high_risk_precision_multiple)
    precision_ok = np.flatnonzero(precision >= target_precision)
    if precision_ok.size:
        high_cutoff = float(thresholds[precision_ok[0]])
    else:
        high_cutoff = float(np.quantile(y_prob, 0.95))
        logger.warning("Could not reach target precision %.3f; using 95th percentile for high cutoff.",
                       target_precision)

    # -- decision threshold: best F1 ---------------------------------------
    f1_scores = np.divide(
        2 * precision * recall, precision + recall,
        out=np.zeros_like(precision), where=(precision + recall) > 0,
    )
    decision_threshold = float(thresholds[int(np.argmax(f1_scores))]) if len(thresholds) else 0.5

    # Keep the buckets ordered and non-degenerate even on pathological inputs.
    low_cutoff = float(np.clip(low_cutoff, 1e-4, 0.98))
    high_cutoff = float(np.clip(high_cutoff, low_cutoff + 1e-3, 0.999))

    logger.info(
        "Tuned thresholds -> low %.4f | high %.4f | decision %.4f (base rate %.4f)",
        low_cutoff, high_cutoff, decision_threshold, base_rate,
    )
    return RiskThresholds(
        low_cutoff=low_cutoff,
        high_cutoff=high_cutoff,
        decision_threshold=decision_threshold,
    )


def probability_to_score(prob: np.ndarray | float, thresholds: RiskThresholds) -> np.ndarray:
    """Map P(default) onto the 0-100 risk score the backend consumes.

    Piecewise-linear and strictly monotonic, anchored so that the tuned low and
    high cut points land exactly on the backend's auto-approve (25) and
    auto-reject (75) thresholds. Without this anchoring, raw probabilities on an
    11%-default portfolio would cluster in the 0-40 band and the auto-reject rule
    would never fire.
    """
    prob = np.asarray(prob, dtype="float64").clip(0.0, 1.0)
    low_score = float(settings.low_risk_cutoff)
    high_score = float(settings.high_risk_cutoff)
    p_low, p_high = thresholds.low_cutoff, thresholds.high_cutoff

    score = np.empty_like(prob, dtype="float64")

    lower = prob <= p_low
    score[lower] = low_score * (prob[lower] / p_low)

    middle = (prob > p_low) & (prob <= p_high)
    span = max(p_high - p_low, 1e-9)
    score[middle] = low_score + (high_score - low_score) * (prob[middle] - p_low) / span

    upper = prob > p_high
    tail = max(1.0 - p_high, 1e-9)
    score[upper] = high_score + (100.0 - high_score) * (prob[upper] - p_high) / tail

    return np.clip(score, 0.0, 100.0)


def score_to_risk_level(score: np.ndarray | float) -> np.ndarray:
    """Bucket a 0-100 risk score into low / medium / high."""
    score = np.asarray(score, dtype="float64")
    levels = np.full(score.shape, "medium", dtype=object)
    levels[score < settings.low_risk_cutoff] = "low"
    levels[score >= settings.high_risk_cutoff] = "high"
    return levels


def confidence_from_probability(prob: np.ndarray | float,
                                thresholds: Optional[RiskThresholds] = None) -> np.ndarray:
    """How firmly the model separates this case from the bucket boundaries.

    Confidence is *not* the probability of default. A 50/50 case near a cut point
    is a low-confidence prediction whichever way it falls; a case deep in either
    tail is a high-confidence one. Officers use this to decide what to review by
    hand, so it must not simply mirror the score.
    """
    prob = np.asarray(prob, dtype="float64").clip(0.0, 1.0)

    # Distance from maximum uncertainty, normalised to [0, 1].
    separation = np.abs(prob - 0.5) * 2.0

    if thresholds is not None:
        boundaries = np.array([thresholds.low_cutoff, thresholds.high_cutoff])
        nearest = np.min(np.abs(prob[..., None] - boundaries), axis=-1)
        # A prediction sitting on a bucket edge is penalised; the 0.15 scale means
        # "within 15 probability points of a boundary" is where doubt kicks in.
        boundary_margin = np.clip(nearest / 0.15, 0.0, 1.0)
        confidence = 0.55 + 0.25 * separation + 0.20 * boundary_margin
    else:
        confidence = 0.55 + 0.45 * separation

    return np.clip(confidence, 0.0, 1.0)


def evaluate_model(model, X, y, thresholds: Optional[RiskThresholds] = None,
                   include_curves: bool = True) -> Dict[str, Any]:
    """Full evaluation bundle for a fitted classifier."""
    y_prob = model.predict_proba(X)[:, 1]
    threshold = thresholds.decision_threshold if thresholds else 0.5

    result: Dict[str, Any] = classification_metrics(y, y_prob, threshold)
    if include_curves:
        result["curves"] = curve_points(y, y_prob)

    if thresholds is not None:
        scores = probability_to_score(y_prob, thresholds)
        levels = score_to_risk_level(scores)
        y_true = np.asarray(y).astype(int)
        result["risk_bands"] = {
            level: {
                "count": int((levels == level).sum()),
                "share": float((levels == level).mean()),
                "observed_default_rate": (
                    float(y_true[levels == level].mean()) if (levels == level).any() else 0.0
                ),
            }
            for level in ("low", "medium", "high")
        }
        result["score_distribution"] = {
            "mean": float(scores.mean()),
            "p10": float(np.percentile(scores, 10)),
            "p50": float(np.percentile(scores, 50)),
            "p90": float(np.percentile(scores, 90)),
        }
    return result
