"""API routes exposed to the Node backend."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import numpy as np
import pandas as pd
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from api.schemas import (
    AgreementRequest,
    BatchPredictRequest,
    BatchPredictResponse,
    ExplainRequest,
    ExplainResponse,
    FairnessCheckRequest,
    FairnessCheckResponse,
    FraudCheckRequest,
    FraudCheckResponse,
    ModelHealthResponse,
    OutcomeRequest,
    PredictRequest,
    PredictResponse,
    RetrainRequest,
    RetrainResponse,
    SimulateRequest,
    SimulateResponse,
)
from src.config import settings
from src.fairness.auditor import build_fairness_report
from src.fraud.detector import score_fraud
from src.inference.adapter import normalize_payload
from src.inference.predictor import ModelNotLoadedError, get_predictor, is_model_available
from src.models import registry
from src.monitoring.drift import drift_report_from_logs
from src.monitoring.performance import officer_agreement_rate, performance_trend, throughput_summary
from src.retraining import pipeline as retraining
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


def _predictor():
    """Fetch the loaded predictor or fail with a clear 503."""
    try:
        return get_predictor()
    except ModelNotLoadedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(f"{exc} Train a model with `python scripts/train_model.py` "
                    "before calling this endpoint."),
        ) from exc


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@router.get("/health", tags=["health"], summary="Liveness probe")
def health() -> Dict[str, Any]:
    """Uptime check for the container orchestrator.

    Intentionally does not touch the model: a liveness probe must answer even
    while a model is loading or missing, otherwise the container is killed in a
    loop. Model readiness is reported by /model-health.
    """
    return {
        "status": "ok",
        "service": settings.app_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "modelAvailable": is_model_available(),
    }


@router.get("/model-health", tags=["monitoring"], response_model=ModelHealthResponse,
            summary="Model version, metrics and drift status")
def model_health(includeDrift: bool = Query(True), window: int = Query(1000, ge=10, le=100_000)):
    if not is_model_available():
        return ModelHealthResponse(
            status="no_model",
            modelLoaded=False,
            alerts=["No trained model is registered. Run the training pipeline."],
            registry=registry.list_versions(),
        )

    predictor = _predictor()
    info = predictor.health()
    alerts: list[str] = []

    drift: Dict[str, Any] = {}
    if includeDrift:
        try:
            drift = drift_report_from_logs(predictor, window=window)
            if drift.get("driftDetected"):
                alerts.append("Data or prediction drift exceeded the alert threshold.")
        except Exception as exc:  # noqa: BLE001 - monitoring must not break health
            logger.warning("Drift computation failed: %s", exc)
            drift = {"status": "error", "error": str(exc)}

    trend = performance_trend()
    if trend.get("alert"):
        alerts.append(trend.get("recommendation", "Model performance has degraded."))
    if not info.get("meetsMinimumAuc"):
        alerts.append(
            f"Training AUC {info['metrics'].get('aucRoc')} is below the configured minimum "
            f"{settings.min_acceptable_auc}."
        )

    fairness = (predictor.metadata.fairness or {})
    if fairness.get("bias_alert"):
        alerts.append("Fairness audit flagged a disparity at training time; see /fairness-check.")

    return ModelHealthResponse(
        status="degraded" if alerts else "healthy",
        modelLoaded=True,
        modelVersion=info["modelVersion"],
        algorithm=info["algorithm"],
        trainedAt=info["trainedAt"],
        datasetVersion=info["datasetVersion"],
        metrics=info["metrics"],
        thresholds=info["thresholds"],
        scoreBands=info["scoreBands"],
        drift=drift,
        performanceTrend={k: v for k, v in trend.items() if k != "periods"},
        throughput=throughput_summary(window),
        registry=registry.list_versions(),
        alerts=alerts,
    )


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------
@router.post("/predict", tags=["inference"], response_model=PredictResponse,
             summary="Score a single application")
def predict(request: PredictRequest):
    """Risk score, level, confidence, top factors and a plain-language explanation."""
    predictor = _predictor()
    application = request.application
    try:
        result = predictor.predict(
            payload=application.as_payload(),
            include_explanation=request.includeExplanation,
            include_fraud=request.includeFraudCheck,
            application_id=application.applicationId,
            top_k=request.topFactors,
            audience=request.audience,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return PredictResponse(**result)


@router.post("/predict/batch", tags=["inference"], response_model=BatchPredictResponse,
             summary="Score many applications in one call")
def predict_batch(request: BatchPredictRequest):
    predictor = _predictor()
    result = predictor.predict_batch(
        payloads=[a.as_payload() for a in request.applications],
        include_explanation=request.includeExplanation,
        include_fraud=request.includeFraudCheck,
        top_k=request.topFactors,
    )
    return BatchPredictResponse(**result)


@router.post("/explain", tags=["explainability"], response_model=ExplainResponse,
             summary="Detailed SHAP explanation for one application")
def explain(request: ExplainRequest):
    predictor = _predictor()
    return ExplainResponse(**predictor.explain(
        payload=request.application.as_payload(), top_k=request.topFactors
    ))


@router.get("/explain/global", tags=["explainability"],
            summary="Global feature importance for the active model")
def explain_global(topK: int = Query(15, ge=1, le=50)):
    """Which features drive the model overall, averaged over the training sample."""
    predictor = _predictor()
    reference = predictor.train_reference_sample
    if reference is None or not len(reference):
        raise HTTPException(status_code=503, detail="No training reference sample stored with this model.")

    from src.data.preprocessing import prepare_features

    sample = reference.sample(min(500, len(reference)), random_state=settings.random_seed)
    matrix = predictor.preprocessor.transform(prepare_features(sample)[predictor.input_columns])
    return {
        "modelVersion": predictor.version,
        "algorithm": predictor.algorithm,
        "sampleSize": int(len(sample)),
        "featureImportance": predictor.explainer.global_importance(matrix, top_k=topK),
    }


@router.post("/simulate", tags=["inference"], response_model=SimulateResponse,
             summary="What-if simulation (nothing is persisted)")
def simulate(request: SimulateRequest):
    """Rescore an application with adjusted inputs.

    Nothing is written: no prediction log entry, no stored score. This backs the
    applicant-facing eligibility simulator, where a hypothetical must never be
    mistaken for a decision.
    """
    predictor = _predictor()
    return SimulateResponse(**predictor.simulate(
        payload=request.application.as_payload(),
        adjustments=request.adjustments,
        top_k=request.topFactors,
    ))


# ---------------------------------------------------------------------------
# Fraud
# ---------------------------------------------------------------------------
@router.post("/fraud-check", tags=["fraud"], response_model=FraudCheckResponse,
             summary="Fraud flag with reasons")
def fraud_check(request: FraudCheckRequest):
    record = normalize_payload(request.application.as_payload())
    application_id = request.applicationId or request.application.applicationId
    return FraudCheckResponse(**score_fraud(
        record, application_id=application_id, check_duplicates=request.checkDuplicates
    ))


# ---------------------------------------------------------------------------
# Fairness
# ---------------------------------------------------------------------------
@router.post("/fairness-check", tags=["fairness"], response_model=FairnessCheckResponse,
             summary="Bias and fairness metrics for a batch of applications")
def fairness_check(request: FairnessCheckRequest):
    """Demographic parity, disparate impact and equal-opportunity gaps.

    Pass ``outcomes`` (realised defaults) to unlock the equal-opportunity metric;
    without labels only selection-rate parity can be measured.
    """
    predictor = _predictor()
    payloads = [a.as_payload() for a in request.applications]
    records = [normalize_payload(p) for p in payloads]

    batch = predictor.predict_batch(payloads, include_explanation=False, include_fraud=False)
    scores = np.array([p["riskScore"] for p in batch["predictions"]], dtype="float64")

    from src.data.feature_engineering import add_engineered_features

    frame = add_engineered_features(pd.DataFrame(records))
    report = build_fairness_report(
        frame, scores, y_true=request.outcomes, attributes=request.attributes
    )
    report["risk_level_distribution"] = batch["summary"]["riskLevelCounts"]
    return FairnessCheckResponse(**report)


# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------
@router.get("/monitoring/drift", tags=["monitoring"], summary="Data and prediction drift report")
def drift(window: int = Query(1000, ge=30, le=100_000)):
    return drift_report_from_logs(_predictor(), window=window)


@router.get("/monitoring/performance", tags=["monitoring"], summary="Performance history")
def performance(limit: int = Query(100, ge=1, le=1000)):
    return performance_trend(limit)


@router.post("/monitoring/agreement", tags=["monitoring"],
             summary="Officer vs AI agreement rate")
def agreement(request: AgreementRequest):
    return officer_agreement_rate(request.decisions)


@router.post("/monitoring/outcome", tags=["monitoring"],
             summary="Record a realised loan outcome for retraining")
def record_outcome(request: OutcomeRequest):
    """Feed an actual repayment result back into the training corpus."""
    entry = retraining.record_outcome(
        application=request.application.as_payload(),
        defaulted=request.defaulted,
        application_id=request.applicationId or request.application.applicationId,
    )
    total = len(retraining.load_outcomes())
    return {
        "recorded": True,
        "applicationId": entry.get("application_id"),
        "totalOutcomesRecorded": total,
        "retrainThreshold": 1000,
    }


# ---------------------------------------------------------------------------
# Registry & retraining
# ---------------------------------------------------------------------------
@router.get("/models", tags=["registry"], summary="List registered model versions")
def list_models():
    return {"activeVersion": registry.get_active_version(), "versions": registry.list_versions()}


@router.get("/models/{version}", tags=["registry"], summary="Full metadata for one version")
def model_metadata(version: str):
    metadata = registry.get_metadata(version)
    if metadata is None:
        raise HTTPException(status_code=404, detail=f"No model version '{version}'.")
    return metadata.to_dict()


@router.post("/models/{version}/activate", tags=["registry"],
             summary="Make a specific version active (admin-only, via backend)")
def activate_model(version: str):
    try:
        registry.set_active_version(version)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    get_predictor(reload=True)
    return {"activeVersion": version, "message": f"Model {version} is now serving."}


@router.post("/models/rollback", tags=["registry"],
             summary="Roll back to the previously active model")
def rollback():
    try:
        result = retraining.rollback_to_previous()
    except (RuntimeError, FileNotFoundError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    get_predictor(reload=True)
    return result


@router.get("/retrain/status", tags=["retraining"], summary="Retraining triggers and job history")
def retrain_status():
    return {"triggers": retraining.should_retrain(), "jobs": retraining.get_jobs()}


@router.post("/retrain", tags=["retraining"], response_model=RetrainResponse,
             status_code=status.HTTP_202_ACCEPTED,
             summary="Trigger the retraining pipeline (admin-only, via backend)")
def retrain(request: RetrainRequest, background_tasks: BackgroundTasks):
    """Kick off a retraining run.

    The challenger is only promoted if it beats the incumbent by the configured
    AUC margin, so triggering this cannot by itself put a worse model in front of
    applicants.
    """
    job_id = f"job-{uuid.uuid4().hex[:12]}"

    if request.async_:
        background_tasks.add_task(
            retraining.run_retraining_job,
            job_id=job_id,
            include_outcomes=request.includeOutcomes,
            auto_promote=request.autoPromote,
            triggered_by="api",
            notes=request.notes,
        )
        return RetrainResponse(
            jobId=job_id,
            status="accepted",
            message="Retraining started in the background. Poll /retrain/status for progress.",
        )

    job = retraining.run_retraining_job(
        job_id=job_id,
        include_outcomes=request.includeOutcomes,
        auto_promote=request.autoPromote,
        triggered_by="api-sync",
        notes=request.notes,
    )
    if job["status"] == "completed":
        get_predictor(reload=True)
    return RetrainResponse(
        jobId=job_id,
        status=job["status"],
        message=job.get("promotion", {}).get("reason", job.get("error", "Retraining finished.")),
        detail=job,
    )
