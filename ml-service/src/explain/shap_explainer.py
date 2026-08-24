"""SHAP-based explanations.

Explains predictions in terms of the *original* features rather than the
one-hot-encoded matrix: contributions from ``Education_PhD``,
``Education_Master's`` and so on are summed back into a single ``Education``
attribution, which is what an officer or applicant needs to see.

Sign convention throughout: a positive SHAP value pushes P(default) up, i.e. it
counts *against* the applicant. That maps to ``impact = "negative"`` in the API,
matching the backend's RiskScore schema.
"""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from src.config import ALL_CATEGORICAL, ALL_NUMERIC, FEATURE_LABELS, TRAINING_ONLY_FEATURES
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def build_feature_group_map(output_names: Sequence[str]) -> Dict[str, str]:
    """Map each encoded column back to the source feature it came from."""
    numeric = set(ALL_NUMERIC)
    mapping: Dict[str, str] = {}
    for name in output_names:
        if name in numeric:
            mapping[name] = name
            continue
        source = next(
            (col for col in ALL_CATEGORICAL if name.startswith(f"{col}_")),
            None,
        )
        mapping[name] = source or name
    return mapping


class ShapExplainer:
    """Lazily-built SHAP explainer bound to one model version.

    Building a TreeExplainer costs a few hundred milliseconds, so it is created
    once on first use and reused. The lock keeps concurrent requests from
    building it several times over.
    """

    def __init__(self, base_estimator: Any, feature_names: Sequence[str],
                 background: Optional[np.ndarray] = None,
                 supports_tree: bool = True) -> None:
        self.base_estimator = base_estimator
        self.feature_names = list(feature_names)
        self.background = background
        self.supports_tree = supports_tree
        self.group_map = build_feature_group_map(self.feature_names)
        self._explainer: Any = None
        self._kind: str = "none"
        self._lock = threading.Lock()

    # -- construction ------------------------------------------------------
    def _ensure_explainer(self) -> None:
        if self._explainer is not None or self._kind == "unavailable":
            return
        with self._lock:
            if self._explainer is not None or self._kind == "unavailable":
                return
            try:
                import shap
            except ImportError:
                logger.warning("shap is not installed; falling back to model-native importances.")
                self._kind = "unavailable"
                return

            try:
                if self.supports_tree:
                    self._explainer = shap.TreeExplainer(self.base_estimator)
                    self._kind = "tree"
                elif hasattr(self.base_estimator, "coef_"):
                    data = self.background if self.background is not None else np.zeros(
                        (1, len(self.feature_names))
                    )
                    self._explainer = shap.LinearExplainer(self.base_estimator, data)
                    self._kind = "linear"
                else:
                    self._kind = "unavailable"
                logger.info("SHAP explainer ready (%s).", self._kind)
            except Exception as exc:  # noqa: BLE001 - never break scoring over explanations
                logger.warning("Could not build SHAP explainer (%s); using fallback.", exc)
                self._kind = "unavailable"

    # -- core --------------------------------------------------------------
    def raw_shap_values(self, X: np.ndarray) -> Optional[np.ndarray]:
        """SHAP values for the positive class, shaped (n_samples, n_features)."""
        self._ensure_explainer()
        if self._explainer is None:
            return None

        try:
            values = self._explainer.shap_values(X, check_additivity=False)
        except TypeError:  # LinearExplainer has no check_additivity kwarg
            values = self._explainer.shap_values(X)
        except Exception as exc:  # noqa: BLE001
            logger.warning("SHAP computation failed (%s); using fallback.", exc)
            return None

        values = np.asarray(values)
        if values.ndim == 3:
            # (n_samples, n_features, n_classes) or (n_classes, n_samples, n_features)
            values = values[..., 1] if values.shape[-1] == 2 else values[1]
        return np.atleast_2d(values)

    def _fallback_contributions(self, X: np.ndarray) -> np.ndarray:
        """Global importance * signed deviation, when SHAP is unavailable.

        Not a true Shapley decomposition — it is a monotone proxy that keeps the
        ranking and direction sensible so the API degrades rather than fails.
        """
        importances = getattr(self.base_estimator, "feature_importances_", None)
        if importances is None:
            coefficients = getattr(self.base_estimator, "coef_", None)
            importances = np.abs(coefficients[0]) if coefficients is not None else np.ones(X.shape[1])
        importances = np.asarray(importances, dtype="float64")

        reference = (
            np.mean(self.background, axis=0)
            if self.background is not None and len(self.background)
            else np.zeros(X.shape[1])
        )
        return (X - reference) * importances

    def grouped_contributions(self, X: np.ndarray) -> np.ndarray:
        """Contributions aggregated to source features.

        Returns shape (n_samples, n_source_features), ordered by
        ``self.source_features``.
        """
        values = self.raw_shap_values(X)
        approximate = values is None
        if approximate:
            values = self._fallback_contributions(X)

        sources = self.source_features
        index = {name: position for position, name in enumerate(sources)}
        grouped = np.zeros((values.shape[0], len(sources)), dtype="float64")
        for column, name in enumerate(self.feature_names):
            grouped[:, index[self.group_map[name]]] += values[:, column]

        self._last_was_approximate = approximate
        return grouped

    @property
    def source_features(self) -> List[str]:
        seen: List[str] = []
        for name in self.feature_names:
            source = self.group_map[name]
            if source not in seen:
                seen.append(source)
        return seen

    @property
    def is_exact(self) -> bool:
        self._ensure_explainer()
        return self._kind in ("tree", "linear")

    # -- public API --------------------------------------------------------
    def explain_row(self, X_row: np.ndarray, raw_values: Optional[Dict[str, Any]] = None,
                    top_k: int = 5) -> Dict[str, Any]:
        """Per-prediction explanation for a single application."""
        X_row = np.atleast_2d(X_row)
        grouped = self.grouped_contributions(X_row)[0]
        sources = self.source_features

        # allContributions keeps every feature, training-only ones included,
        # for full transparency about what the model actually computed.
        full_order = np.argsort(-np.abs(grouped))

        # topFactors excludes TRAINING_ONLY_FEATURES: those are always the
        # fitted imputer's population median/mode at inference time (no live
        # bureau feed backs them), so presenting one as "why this applicant
        # scored the way they did" would explain a real decision with a value
        # that was never actually theirs. Weight is renormalised over the
        # remaining presentable factors so it still reads as a share of 1.
        presentable = [i for i in range(len(sources)) if sources[i] not in TRAINING_ONLY_FEATURES]
        presentable_order = [i for i in full_order if i in set(presentable)]
        total = float(np.abs(grouped[presentable]).sum()) if presentable else 0.0

        factors: List[Dict[str, Any]] = []
        for position in presentable_order[:top_k]:
            feature = sources[position]
            contribution = float(grouped[position])
            factors.append({
                "feature": FEATURE_LABELS.get(feature, feature),
                "rawFeature": feature,
                # A positive SHAP value raises default probability, which is bad
                # news for the applicant.
                "impact": "negative" if contribution > 0 else "positive",
                "weight": round(abs(contribution) / total, 4) if total > 0 else 0.0,
                "shapValue": round(contribution, 6),
                "value": _present_value(raw_values, feature),
            })

        return {
            "topFactors": factors,
            "allContributions": {
                sources[position]: round(float(grouped[position]), 6)
                for position in full_order
            },
            "method": "shap" if self.is_exact else "importance-weighted approximation",
            "isExact": self.is_exact,
        }

    def global_importance(self, X: np.ndarray, top_k: int = 15) -> List[Dict[str, Any]]:
        """Mean |contribution| per source feature — the global ranking."""
        grouped = np.abs(self.grouped_contributions(X)).mean(axis=0)
        sources = self.source_features
        total = float(grouped.sum())

        order = np.argsort(-grouped)[:top_k]
        return [
            {
                "feature": FEATURE_LABELS.get(sources[position], sources[position]),
                "rawFeature": sources[position],
                "importance": round(float(grouped[position]), 6),
                "relativeImportance": round(float(grouped[position]) / total, 4) if total else 0.0,
            }
            for position in order
        ]


def _present_value(raw_values: Optional[Dict[str, Any]], feature: str) -> Any:
    if not raw_values or feature not in raw_values:
        return None
    value = raw_values[feature]
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return round(value, 4)
    if isinstance(value, (np.integer, int)):
        return int(value)
    return None if value is None or (isinstance(value, float) and np.isnan(value)) else str(value)
