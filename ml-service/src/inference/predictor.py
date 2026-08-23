"""Inference service: single, batch and what-if scoring.

``RiskPredictor`` owns one loaded model version. ``get_predictor()`` returns a
process-wide singleton so the model, preprocessor and SHAP explainer are built
once at startup rather than per request.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.config import ALL_CATEGORICAL, ALL_NUMERIC, BASE_FEATURES, TRAINING_ONLY_FEATURES, settings
from src.data.preprocessing import prepare_features
from src.explain.narrative import generate_explanation, generate_simulation_narrative
from src.explain.shap_explainer import ShapExplainer
from src.fraud.detector import score_fraud
from src.models import registry
from src.models.evaluate import (
    RiskThresholds,
    confidence_from_probability,
    probability_to_score,
    score_to_risk_level,
)
from src.inference.adapter import imputed_field_names, normalize_payload
from src.utils.logging_config import get_logger, prediction_log

logger = get_logger(__name__)


class ModelNotLoadedError(RuntimeError):
    """Raised when scoring is attempted before a model has been trained."""


class RiskPredictor:
    """Scores loan applications with one registered model version."""

    def __init__(self, version: Optional[str] = None) -> None:
        artifacts, metadata = registry.load_model(version)
        self.version = metadata.version
        self.metadata = metadata
        self.preprocessor = artifacts["preprocessor"]
        self.model = artifacts["model"]
        self.base_estimator = artifacts["base_estimator"]
        self.algorithm = artifacts["algorithm"]
        self.feature_names = artifacts["feature_names"]
        self.input_columns = artifacts.get("input_columns", ALL_NUMERIC + ALL_CATEGORICAL)
        self.train_reference_sample = artifacts.get("train_reference_sample")

        thresholds = artifacts["thresholds"]
        self.thresholds = (
            thresholds if isinstance(thresholds, RiskThresholds)
            else RiskThresholds(**thresholds)
        )

        background = registry.load_background(self.version)
        self.explainer = ShapExplainer(
            base_estimator=self.base_estimator,
            feature_names=self.feature_names,
            background=background["matrix"] if isinstance(background, dict) else background,
            supports_tree=artifacts.get("supports_shap_tree", True),
        )
        self.loaded_at = time.time()
        logger.info("RiskPredictor ready: version=%s algorithm=%s", self.version, self.algorithm)

    # -- internals ---------------------------------------------------------
    def _records_to_matrix(self, records: List[Dict[str, Any]]) -> tuple[np.ndarray, pd.DataFrame]:
        raw = pd.DataFrame(records, columns=BASE_FEATURES)
        features = prepare_features(raw)
        matrix = self.preprocessor.transform(features[self.input_columns])
        return matrix, features

    def _score_matrix(self, matrix: np.ndarray) -> Dict[str, np.ndarray]:
        probabilities = self.model.predict_proba(matrix)[:, 1]
        scores = probability_to_score(probabilities, self.thresholds)
        return {
            "probability": probabilities,
            "riskScore": scores,
            "riskLevel": score_to_risk_level(scores),
            "confidence": confidence_from_probability(probabilities, self.thresholds),
        }

    # -- public API --------------------------------------------------------
    def predict(
        self,
        payload: Dict[str, Any],
        include_explanation: bool = True,
        include_fraud: bool = True,
        application_id: Optional[str] = None,
        top_k: int = 5,
        audience: str = "officer",
        log: bool = True,
    ) -> Dict[str, Any]:
        """Score one application and return the backend's RiskScore payload."""
        started = time.perf_counter()

        record = normalize_payload(payload)
        matrix, features = self._records_to_matrix([record])
        scored = self._score_matrix(matrix)

        probability = float(scored["probability"][0])
        risk_score = float(scored["riskScore"][0])
        risk_level = str(scored["riskLevel"][0])
        confidence = float(scored["confidence"][0])

        # Explanation values are read from the engineered frame so derived
        # features (loan-to-income, instalment ratios) can be quoted back with
        # their actual numbers.
        raw_values = {**record, **features.iloc[0].to_dict()}

        top_factors: List[Dict[str, Any]] = []
        explanation_meta: Dict[str, Any] = {}
        if include_explanation:
            explained = self.explainer.explain_row(matrix, raw_values, top_k=top_k)
            top_factors = explained["topFactors"]
            explanation_meta = {
                "method": explained["method"],
                "isExact": explained["isExact"],
            }

        fraud = score_fraud(record, application_id) if include_fraud else None

        narrative = (
            generate_explanation(
                risk_score=risk_score,
                risk_level=risk_level,
                probability=probability,
                confidence=confidence,
                top_factors=top_factors,
                fraud=fraud,
                audience=audience,
            )
            if include_explanation else []
        )

        # Attach a short description to each factor so the backend's topFactors
        # sub-document (which requires `description`) is satisfied directly.
        for factor in top_factors:
            factor["description"] = _factor_description(factor)

        latency_ms = (time.perf_counter() - started) * 1000.0
        response: Dict[str, Any] = {
            "riskScore": round(risk_score, 2),
            "riskLevel": risk_level,
            "probabilityOfDefault": round(probability, 6),
            "confidenceScore": round(confidence, 4),
            "topFactors": top_factors,
            "plainLanguageExplanation": narrative,
            "modelVersion": self.version,
            "algorithm": self.algorithm,
            "imputedFields": imputed_field_names(record),
            "latencyMs": round(latency_ms, 2),
        }
        if explanation_meta:
            response["explanationMethod"] = explanation_meta

        if fraud is not None:
            response["fraudFlag"] = fraud["fraudFlag"]
            response["fraudReason"] = fraud["reason"]
            response["fraudProbability"] = fraud["fraudProbability"]

        if log:
            prediction_log.write(
                event="predict",
                request={"applicationId": application_id, "normalized": record},
                response={
                    "riskScore": response["riskScore"],
                    "riskLevel": risk_level,
                    "probability": response["probabilityOfDefault"],
                    "fraudFlag": response.get("fraudFlag"),
                },
                model_version=self.version,
                latency_ms=latency_ms,
            )
        return response

    def predict_batch(
        self,
        payloads: List[Dict[str, Any]],
        include_explanation: bool = False,
        include_fraud: bool = True,
        top_k: int = 3,
    ) -> Dict[str, Any]:
        """Score many applications in one vectorised pass.

        Explanations are off by default: SHAP dominates the cost at batch sizes,
        and bulk scoring is normally used for portfolio triage where the score
        and band are what matter.
        """
        if not payloads:
            return {"count": 0, "predictions": []}

        started = time.perf_counter()
        records = [normalize_payload(p) for p in payloads]
        matrix, features = self._records_to_matrix(records)
        scored = self._score_matrix(matrix)

        grouped = self.explainer.grouped_contributions(matrix) if include_explanation else None
        sources = self.explainer.source_features if include_explanation else []
        # Same reasoning as ShapExplainer.explain_row: bureau/repayment-history
        # features are always population-imputed at inference (no live bureau
        # feed), so they're excluded from the presented top factors.
        presentable = [i for i, s in enumerate(sources) if s not in TRAINING_ONLY_FEATURES]

        predictions: List[Dict[str, Any]] = []
        for i, record in enumerate(records):
            item: Dict[str, Any] = {
                "index": i,
                "applicationId": payloads[i].get("applicationId") or payloads[i].get("_id"),
                "riskScore": round(float(scored["riskScore"][i]), 2),
                "riskLevel": str(scored["riskLevel"][i]),
                "probabilityOfDefault": round(float(scored["probability"][i]), 6),
                "confidenceScore": round(float(scored["confidence"][i]), 4),
            }

            if include_fraud:
                fraud = score_fraud(record, item["applicationId"], check_duplicates=False)
                item["fraudFlag"] = fraud["fraudFlag"]
                item["fraudReason"] = fraud["reason"]

            if grouped is not None:
                row = grouped[i]
                total = float(np.abs(row[presentable]).sum()) or 1.0
                full_order = np.argsort(-np.abs(row))
                order = [j for j in full_order if j in set(presentable)][:top_k]
                item["topFactors"] = [
                    {
                        "feature": sources[j],
                        "impact": "negative" if row[j] > 0 else "positive",
                        "weight": round(abs(float(row[j])) / total, 4),
                    }
                    for j in order
                ]
            predictions.append(item)

        latency_ms = (time.perf_counter() - started) * 1000.0
        levels = scored["riskLevel"]
        return {
            "count": len(predictions),
            "predictions": predictions,
            "summary": {
                "meanRiskScore": round(float(scored["riskScore"].mean()), 2),
                "riskLevelCounts": {
                    level: int((levels == level).sum()) for level in ("low", "medium", "high")
                },
                "flaggedForFraud": int(sum(1 for p in predictions if p.get("fraudFlag"))),
            },
            "modelVersion": self.version,
            "latencyMs": round(latency_ms, 2),
            "throughputPerSecond": round(len(predictions) / max(latency_ms / 1000.0, 1e-6), 1),
        }

    def simulate(
        self,
        payload: Dict[str, Any],
        adjustments: Dict[str, Any],
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """What-if scoring: rescore with adjusted inputs, persisting nothing.

        Returns both the baseline and adjusted results plus the delta, so the
        eligibility simulator can show the applicant the effect of each change.
        """
        baseline_record = normalize_payload(payload)
        adjusted_record = normalize_payload({**payload, **adjustments})

        matrix, features = self._records_to_matrix([baseline_record, adjusted_record])
        scored = self._score_matrix(matrix)

        baseline_score = float(scored["riskScore"][0])
        adjusted_score = float(scored["riskScore"][1])

        explained = self.explainer.explain_row(
            matrix[1:2], {**adjusted_record, **features.iloc[1].to_dict()}, top_k=top_k
        )
        for factor in explained["topFactors"]:
            factor["description"] = _factor_description(factor)

        changed = {
            k: v for k, v in adjusted_record.items()
            if baseline_record.get(k) != v and v is not None
        }

        return {
            "baseline": {
                "riskScore": round(baseline_score, 2),
                "riskLevel": str(scored["riskLevel"][0]),
                "probabilityOfDefault": round(float(scored["probability"][0]), 6),
            },
            "simulated": {
                "riskScore": round(adjusted_score, 2),
                "riskLevel": str(scored["riskLevel"][1]),
                "probabilityOfDefault": round(float(scored["probability"][1]), 6),
                "confidenceScore": round(float(scored["confidence"][1]), 4),
                "topFactors": explained["topFactors"],
            },
            "delta": {
                "riskScoreChange": round(adjusted_score - baseline_score, 2),
                "improved": adjusted_score < baseline_score,
                "changedFields": changed,
            },
            "explanation": generate_simulation_narrative(baseline_score, adjusted_score, changed),
            "persisted": False,
            "modelVersion": self.version,
        }

    def explain(self, payload: Dict[str, Any], top_k: int = 10) -> Dict[str, Any]:
        """Detailed SHAP breakdown for one application."""
        record = normalize_payload(payload)
        matrix, features = self._records_to_matrix([record])
        scored = self._score_matrix(matrix)
        raw_values = {**record, **features.iloc[0].to_dict()}

        explained = self.explainer.explain_row(matrix, raw_values, top_k=top_k)
        for factor in explained["topFactors"]:
            factor["description"] = _factor_description(factor)

        probability = float(scored["probability"][0])
        risk_score = float(scored["riskScore"][0])
        contributions = explained["allContributions"]

        return {
            "riskScore": round(risk_score, 2),
            "riskLevel": str(scored["riskLevel"][0]),
            "probabilityOfDefault": round(probability, 6),
            "confidenceScore": round(float(scored["confidence"][0]), 4),
            "topFactors": explained["topFactors"],
            "featureContributions": contributions,
            "positiveContributors": {k: v for k, v in contributions.items() if v < 0},
            "negativeContributors": {k: v for k, v in contributions.items() if v > 0},
            "plainLanguageExplanation": generate_explanation(
                risk_score=risk_score,
                risk_level=str(scored["riskLevel"][0]),
                probability=probability,
                confidence=float(scored["confidence"][0]),
                top_factors=explained["topFactors"],
                audience="applicant",
            ),
            "method": explained["method"],
            "isExact": explained["isExact"],
            "modelVersion": self.version,
        }

    def health(self) -> Dict[str, Any]:
        """Model version, headline metrics and configured thresholds."""
        metrics = self.metadata.metrics or {}
        return {
            "modelVersion": self.version,
            "algorithm": self.algorithm,
            "trainedAt": self.metadata.created_at,
            "datasetVersion": self.metadata.dataset_version,
            "datasetRows": self.metadata.dataset_rows,
            "featureCount": self.metadata.feature_count,
            "metrics": {
                "accuracy": metrics.get("accuracy"),
                "aucRoc": metrics.get("roc_auc"),
                "precision": metrics.get("precision"),
                "recall": metrics.get("recall"),
                "f1Score": metrics.get("f1"),
                "averagePrecision": metrics.get("average_precision"),
                "brierScore": metrics.get("brier_score"),
            },
            "confusionMatrix": metrics.get("confusion_matrix"),
            "riskBands": metrics.get("risk_bands"),
            "thresholds": self.thresholds.to_dict(),
            "scoreBands": {
                "low": f"< {settings.low_risk_cutoff}",
                "medium": f"{settings.low_risk_cutoff} - {settings.high_risk_cutoff - 1}",
                "high": f">= {settings.high_risk_cutoff}",
            },
            "baselineComparison": self.metadata.baseline_comparison,
            "meetsMinimumAuc": bool(
                (metrics.get("roc_auc") or 0) >= settings.min_acceptable_auc
            ),
        }


def _factor_description(factor: Dict[str, Any]) -> str:
    """One-line description stored on the backend's topFactors sub-document."""
    direction = "increases" if factor["impact"] == "negative" else "reduces"
    value = factor.get("value")
    share = factor.get("weight", 0)
    value_part = f" (value: {value})" if value is not None else ""
    return (
        f"{factor['feature']}{value_part} {direction} assessed risk, accounting for "
        f"{share:.0%} of the factors considered."
    )


# ---------------------------------------------------------------------------
# Process-wide singleton
# ---------------------------------------------------------------------------
_predictor: Optional[RiskPredictor] = None
_predictor_lock = threading.Lock()


def get_predictor(version: Optional[str] = None, reload: bool = False) -> RiskPredictor:
    """Return the shared predictor, loading it on first use."""
    global _predictor
    if _predictor is not None and not reload and (version is None or _predictor.version == version):
        return _predictor

    with _predictor_lock:
        if _predictor is None or reload or (version and _predictor.version != version):
            try:
                _predictor = RiskPredictor(version)
            except FileNotFoundError as exc:
                raise ModelNotLoadedError(str(exc)) from exc
    return _predictor


def is_model_available() -> bool:
    return registry.get_active_version() is not None
