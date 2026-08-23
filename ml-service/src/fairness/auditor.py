"""Fairness and bias auditing.

Computes demographic parity, disparate impact and equal-opportunity gaps across
protected attributes, and raises an alert when a group falls outside the
four-fifths rule. The output feeds the Admin panel's fairness report.

Scope note: this measures *outcome disparity*, which is a necessary but not
sufficient fairness check. It cannot tell you whether a disparity is explained by
legitimate creditworthiness differences; that judgement stays with a human
reviewer, and the report is written to support that review rather than replace it.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from src.config import PROTECTED_ATTRIBUTES, settings
from src.models.evaluate import RiskThresholds, probability_to_score, score_to_risk_level
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

MIN_GROUP_SIZE = 30  # below this, rates are too noisy to act on
SIGNIFICANCE_Z = 1.959964  # two-tailed 95% critical value


def _rate_gap_is_significant(rate_a: float, n_a: int, rate_b: float, n_b: int) -> bool:
    """Two-proportion z-test: is this approval-rate gap distinguishable from noise?

    A raw threshold on two sampled approval rates flags plenty of gaps that are
    pure sampling variance, especially once several protected attributes are
    each tested against several groups. Requiring the gap to also clear a 95%
    significance test keeps the alert reserved for disparities a reviewer could
    actually defend investigating.
    """
    if n_a == 0 or n_b == 0:
        return False
    if rate_a == rate_b:
        return False
    pooled = (rate_a * n_a + rate_b * n_b) / (n_a + n_b)
    variance = pooled * (1 - pooled) * (1.0 / n_a + 1.0 / n_b)
    if variance <= 0:
        # Zero pooled variance only happens at a 0%-vs-100% split, which is
        # significant by construction.
        return True
    z = abs(rate_a - rate_b) / math.sqrt(variance)
    return z >= SIGNIFICANCE_Z


def _group_stats(approved: np.ndarray, y_true: Optional[np.ndarray],
                 mask: np.ndarray) -> Dict[str, Any]:
    n = int(mask.sum())
    stats: Dict[str, Any] = {
        "count": n,
        "approval_rate": float(approved[mask].mean()) if n else 0.0,
        "sufficient_sample": n >= MIN_GROUP_SIZE,
    }
    if y_true is not None and n:
        # Equal opportunity: among applicants who did NOT default, how many were
        # approved? A gap here means the model denies creditworthy people from one
        # group more often than another.
        creditworthy = mask & (y_true == 0)
        if creditworthy.sum():
            stats["true_negative_approval_rate"] = float(approved[creditworthy].mean())
        defaulted = mask & (y_true == 1)
        if defaulted.sum():
            stats["observed_default_rate"] = float(y_true[mask].mean())
            stats["defaulter_approval_rate"] = float(approved[defaulted].mean())
    return stats


def audit_attribute(df: pd.DataFrame, attribute: str, approved: np.ndarray,
                    y_true: Optional[np.ndarray] = None) -> Dict[str, Any]:
    """Fairness metrics for one protected attribute."""
    if attribute not in df.columns:
        return {"attribute": attribute, "available": False}

    values = df[attribute].astype("string").fillna("unknown")
    groups: Dict[str, Dict[str, Any]] = {}
    for level in sorted(values.dropna().unique().tolist()):
        mask = (values == level).to_numpy()
        if mask.sum() == 0:
            continue
        groups[str(level)] = _group_stats(approved, y_true, mask)

    usable = {k: v for k, v in groups.items() if v["sufficient_sample"]}
    if len(usable) < 2:
        return {
            "attribute": attribute,
            "available": True,
            "groups": groups,
            "note": f"Fewer than two groups with at least {MIN_GROUP_SIZE} applicants; "
                    "disparity not computed.",
            "bias_alert": False,
        }

    rates = {k: v["approval_rate"] for k, v in usable.items()}
    most_favoured = max(rates, key=rates.get)
    least_favoured = min(rates, key=rates.get)
    max_rate, min_rate = rates[most_favoured], rates[least_favoured]

    # Four-fifths rule (EEOC): the least-favoured group's selection rate divided
    # by the most-favoured group's rate should be at least 0.80.
    disparate_impact_ratio = float(min_rate / max_rate) if max_rate > 0 else 1.0
    demographic_parity_difference = float(max_rate - min_rate)

    equal_opportunity_gap = None
    tn_rates = {
        k: v["true_negative_approval_rate"]
        for k, v in usable.items() if "true_negative_approval_rate" in v
    }
    if len(tn_rates) >= 2:
        equal_opportunity_gap = float(max(tn_rates.values()) - min(tn_rates.values()))

    threshold_breached = (
        disparate_impact_ratio < settings.disparate_impact_floor
        or demographic_parity_difference > settings.demographic_parity_tolerance
    )
    # A breached threshold is necessary but not sufficient: on modest group
    # sizes, uniformly random scores will exceed these thresholds somewhere
    # just from sampling noise. Only alert when the gap between the two
    # extreme groups is also statistically distinguishable from noise.
    significant = threshold_breached and _rate_gap_is_significant(
        max_rate, usable[most_favoured]["count"], min_rate, usable[least_favoured]["count"]
    )

    return {
        "attribute": attribute,
        "available": True,
        "groups": groups,
        "approval_rates": rates,
        "most_favoured_group": most_favoured,
        "least_favoured_group": least_favoured,
        "disparate_impact_ratio": round(disparate_impact_ratio, 4),
        "demographic_parity_difference": round(demographic_parity_difference, 4),
        "equal_opportunity_gap": round(equal_opportunity_gap, 4) if equal_opportunity_gap is not None else None,
        "passes_four_fifths_rule": disparate_impact_ratio >= settings.disparate_impact_floor,
        "statistically_significant": bool(significant),
        "bias_alert": bool(significant),
    }


def build_fairness_report(
    df: pd.DataFrame,
    risk_scores: Sequence[float],
    y_true: Optional[Sequence[int]] = None,
    attributes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Full fairness report across every configured protected attribute.

    "Approved" means the risk score falls in the auto-approve band, i.e. the
    decision the model would drive if no officer intervened.
    """
    attributes = attributes or PROTECTED_ATTRIBUTES
    scores = np.asarray(risk_scores, dtype="float64")
    approved = (scores < settings.low_risk_cutoff).astype(float)
    y_array = np.asarray(y_true).astype(int) if y_true is not None else None

    per_attribute = {}
    alerts: List[str] = []
    for attribute in attributes:
        result = audit_attribute(df, attribute, approved, y_array)
        per_attribute[attribute] = result
        if result.get("bias_alert"):
            alerts.append(
                f"{attribute}: approval rate for '{result['least_favoured_group']}' is "
                f"{result['approval_rates'][result['least_favoured_group']]:.1%} vs "
                f"{result['approval_rates'][result['most_favoured_group']]:.1%} for "
                f"'{result['most_favoured_group']}' "
                f"(disparate impact ratio {result['disparate_impact_ratio']:.2f})."
            )

    return {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "n_applications": int(len(scores)),
        "overall_approval_rate": float(approved.mean()) if len(approved) else 0.0,
        "overall_mean_risk_score": float(scores.mean()) if len(scores) else 0.0,
        "thresholds": {
            "disparate_impact_floor": settings.disparate_impact_floor,
            "demographic_parity_tolerance": settings.demographic_parity_tolerance,
            "approval_band": f"risk score < {settings.low_risk_cutoff}",
        },
        "attributes": per_attribute,
        "bias_alert": bool(alerts),
        "alerts": alerts,
        "summary": (
            "No disparity beyond the configured tolerance was detected."
            if not alerts
            else f"{len(alerts)} attribute(s) exceeded the fairness tolerance and require review."
        ),
    }


def audit_training_fairness(
    X_raw: pd.DataFrame,
    y_true: Sequence[int],
    probabilities: Sequence[float],
    thresholds: RiskThresholds,
) -> Dict[str, Any]:
    """Fairness audit run at training time against the held-out test split."""
    scores = probability_to_score(np.asarray(probabilities), thresholds)
    report = build_fairness_report(X_raw, scores, y_true)
    levels = score_to_risk_level(scores)
    report["risk_level_distribution"] = {
        level: int((levels == level).sum()) for level in ("low", "medium", "high")
    }
    return report
