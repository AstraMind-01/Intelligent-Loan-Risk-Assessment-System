"""End-to-end training pipeline.

Ingest -> validate -> engineer -> split -> fit preprocessing -> benchmark a
logistic-regression baseline against tuned tree ensembles -> calibrate -> tune
risk thresholds -> evaluate -> fairness audit -> register.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.stats import loguniform, randint, uniform
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold, cross_validate

from src.config import ALL_CATEGORICAL, ALL_NUMERIC, TARGET, ensure_directories, settings
from src.data import loader
from src.data.preprocessing import (
    apply_imbalance_strategy,
    build_preprocessor,
    compute_scale_pos_weight,
    get_output_feature_names,
    prepare_features,
    split_data,
)
from src.models import registry
from src.models.evaluate import evaluate_model, tune_thresholds
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class TrainingResult:
    version: str
    metadata: registry.ModelMetadata
    artifacts: Dict[str, Any]


# ---------------------------------------------------------------------------
# Model zoo
# ---------------------------------------------------------------------------
def _xgboost_available() -> bool:
    try:
        import xgboost  # noqa: F401
        return True
    except ImportError:
        return False


def _build_calibrator(estimator) -> CalibratedClassifierCV:
    """Isotonic calibrator that will *not* refit the already-trained estimator.

    scikit-learn 1.6 deprecated ``cv="prefit"`` in favour of ``FrozenEstimator``.
    Both spellings mean "leave this model alone and only learn the calibration
    map"; picking the wrong one for the installed version would silently refit
    the champion on the validation split, so the choice is explicit.
    """
    try:
        from sklearn.frozen import FrozenEstimator

        return CalibratedClassifierCV(FrozenEstimator(estimator), method="isotonic")
    except ImportError:  # scikit-learn < 1.6
        return CalibratedClassifierCV(estimator, method="isotonic", cv="prefit")


def build_candidates(scale_pos_weight: float, use_class_weight: bool) -> Dict[str, Dict[str, Any]]:
    """Candidate estimators and their search spaces.

    The logistic regression is the mandated benchmark: an advanced model that
    cannot beat it is not worth the operational cost or the loss of
    interpretability.
    """
    class_weight = "balanced" if use_class_weight else None
    seed = settings.random_seed

    candidates: Dict[str, Dict[str, Any]] = {
        "logistic_regression": {
            "estimator": LogisticRegression(
                max_iter=2000, class_weight=class_weight, random_state=seed, solver="lbfgs"
            ),
            "param_distributions": {"C": loguniform(1e-3, 1e2)},
            "n_iter": 8,
            "is_baseline": True,
            "supports_shap_tree": False,
        },
        "random_forest": {
            "estimator": RandomForestClassifier(
                random_state=seed, class_weight=class_weight, n_jobs=-1
            ),
            "param_distributions": {
                "n_estimators": randint(200, 500),
                "max_depth": randint(6, 20),
                "min_samples_leaf": randint(10, 120),
                "max_features": uniform(0.3, 0.6),
            },
            "n_iter": max(6, settings.tuning_iterations // 2),
            "is_baseline": False,
            "supports_shap_tree": True,
        },
    }

    if _xgboost_available():
        from xgboost import XGBClassifier

        candidates["xgboost"] = {
            "estimator": XGBClassifier(
                objective="binary:logistic",
                eval_metric="auc",
                tree_method="hist",
                random_state=seed,
                n_jobs=-1,
                scale_pos_weight=scale_pos_weight if use_class_weight else 1.0,
            ),
            "param_distributions": {
                "n_estimators": randint(250, 700),
                "max_depth": randint(3, 9),
                "learning_rate": loguniform(0.01, 0.25),
                "subsample": uniform(0.6, 0.4),
                "colsample_bytree": uniform(0.6, 0.4),
                "min_child_weight": randint(1, 40),
                "gamma": uniform(0.0, 4.0),
                "reg_lambda": loguniform(0.5, 20.0),
                "reg_alpha": loguniform(1e-3, 5.0),
            },
            "n_iter": settings.tuning_iterations,
            "is_baseline": False,
            "supports_shap_tree": True,
        }
    else:
        logger.warning("xgboost is not installed; training will use random forest as the advanced model.")

    return candidates


def tune_and_fit(
    name: str,
    spec: Dict[str, Any],
    X_train: np.ndarray,
    y_train: np.ndarray,
    cv_folds: int,
    tuning_sample: Optional[int] = None,
) -> Tuple[Any, Dict[str, Any]]:
    """Randomised hyperparameter search with stratified CV, then refit on all data."""
    cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=settings.random_seed)

    # Hyperparameter ranking is stable on a large subsample and this keeps the
    # search from dominating total training time on a 255k-row dataset.
    if tuning_sample and len(y_train) > tuning_sample:
        rng = np.random.default_rng(settings.random_seed)
        idx = rng.choice(len(y_train), size=tuning_sample, replace=False)
        X_search, y_search = X_train[idx], y_train[idx]
        logger.info("[%s] tuning on a %d-row stratified subsample", name, tuning_sample)
    else:
        X_search, y_search = X_train, y_train

    search = RandomizedSearchCV(
        estimator=spec["estimator"],
        param_distributions=spec["param_distributions"],
        n_iter=spec["n_iter"],
        scoring="roc_auc",
        cv=cv,
        n_jobs=-1,
        random_state=settings.random_seed,
        refit=False,
        error_score="raise",
        verbose=0,
    )

    started = time.perf_counter()
    search.fit(X_search, y_search)
    elapsed = time.perf_counter() - started

    best_params = search.best_params_
    logger.info("[%s] best CV AUC %.4f in %.1fs | params: %s",
                name, search.best_score_, elapsed, best_params)

    # Refit the winning configuration on the complete training set.
    final_estimator = spec["estimator"].__class__(**{**spec["estimator"].get_params(), **best_params})
    final_estimator.fit(X_train, y_train)

    # Honest generalisation estimate for the chosen configuration.
    cv_scores = cross_validate(
        final_estimator, X_search, y_search, cv=cv,
        scoring=["roc_auc", "average_precision", "f1"], n_jobs=-1,
    )
    cv_summary = {
        "best_params": {k: (v.item() if hasattr(v, "item") else v) for k, v in best_params.items()},
        "search_best_auc": float(search.best_score_),
        "cv_roc_auc_mean": float(np.mean(cv_scores["test_roc_auc"])),
        "cv_roc_auc_std": float(np.std(cv_scores["test_roc_auc"])),
        "cv_average_precision_mean": float(np.mean(cv_scores["test_average_precision"])),
        "cv_f1_mean": float(np.mean(cv_scores["test_f1"])),
        "n_folds": cv_folds,
        "tuning_seconds": round(elapsed, 2),
    }
    return final_estimator, cv_summary


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
def train(
    source_path: Optional[str] = None,
    imbalance_strategy: Optional[str] = None,
    cv_folds: Optional[int] = None,
    tuning_sample: Optional[int] = 60_000,
    set_active: bool = True,
    save_processed: bool = True,
    notes: str = "",
) -> TrainingResult:
    """Run the full training pipeline and register the resulting model."""
    ensure_directories()
    started = time.perf_counter()
    cv_folds = cv_folds or settings.cv_folds
    imbalance_strategy = (imbalance_strategy or settings.imbalance_strategy).lower()

    # -- 1. ingest & validate ---------------------------------------------
    logger.info("=== Stage 1/8: ingest & validate ===")
    raw_df, validation_report = loader.ingest(source_path, strict=True)

    # -- 2. feature engineering -------------------------------------------
    logger.info("=== Stage 2/8: feature engineering ===")
    features = prepare_features(raw_df)
    processed = features.copy()
    processed[TARGET] = raw_df[TARGET].to_numpy()

    if save_processed:
        dataset_meta = loader.save_processed(
            processed,
            source_path=settings.raw_dataset_path if source_path is None else source_path,
            validation=validation_report,
        )
        dataset_version = dataset_meta.version
    else:
        dataset_version = "unversioned"

    # -- 3. split ----------------------------------------------------------
    logger.info("=== Stage 3/8: train/val/test split ===")
    splits = split_data(processed)
    X_train_raw, y_train = splits["train"]
    X_val_raw, y_val = splits["val"]
    X_test_raw, y_test = splits["test"]

    # -- 4. preprocessing --------------------------------------------------
    logger.info("=== Stage 4/8: fit preprocessing ===")
    preprocessor = build_preprocessor()
    X_train = preprocessor.fit_transform(X_train_raw[ALL_NUMERIC + ALL_CATEGORICAL], y_train)
    X_val = preprocessor.transform(X_val_raw[ALL_NUMERIC + ALL_CATEGORICAL])
    X_test = preprocessor.transform(X_test_raw[ALL_NUMERIC + ALL_CATEGORICAL])
    feature_names = get_output_feature_names(preprocessor)
    logger.info("Feature matrix: %s -> %d encoded features", X_train.shape, len(feature_names))

    use_class_weight = imbalance_strategy in ("class_weight", "none")
    X_train_bal, y_train_bal = apply_imbalance_strategy(
        X_train, y_train, strategy=imbalance_strategy
    )
    scale_pos_weight = compute_scale_pos_weight(y_train)

    # -- 5. train candidates ----------------------------------------------
    logger.info("=== Stage 5/8: train & tune candidates ===")
    candidates = build_candidates(scale_pos_weight, use_class_weight)
    trained: Dict[str, Any] = {}
    cv_results: Dict[str, Any] = {}

    for name, spec in candidates.items():
        logger.info("--- %s ---", name)
        estimator, summary = tune_and_fit(
            name, spec, X_train_bal, y_train_bal, cv_folds, tuning_sample
        )
        val_metrics = evaluate_model(estimator, X_val, y_val, include_curves=False)
        summary["val_roc_auc"] = val_metrics["roc_auc"]
        summary["val_average_precision"] = val_metrics["average_precision"]
        logger.info("[%s] validation AUC %.4f | AP %.4f",
                    name, val_metrics["roc_auc"], val_metrics["average_precision"])
        trained[name] = estimator
        cv_results[name] = summary

    # -- 6. select champion ------------------------------------------------
    logger.info("=== Stage 6/8: model selection ===")
    best_name = max(cv_results, key=lambda n: cv_results[n]["val_roc_auc"])
    best_estimator = trained[best_name]
    baseline_name = next(n for n, s in candidates.items() if s["is_baseline"])
    baseline_auc = cv_results[baseline_name]["val_roc_auc"]
    best_auc = cv_results[best_name]["val_roc_auc"]

    logger.info("Selected '%s' (val AUC %.4f) over baseline '%s' (val AUC %.4f); lift %+.4f",
                best_name, best_auc, baseline_name, baseline_auc, best_auc - baseline_auc)

    # -- 7. calibrate + tune thresholds -----------------------------------
    logger.info("=== Stage 7/8: calibration & threshold tuning ===")
    # Class weighting and resampling both distort predicted probabilities. Risk
    # scores are only meaningful if P(default) means what it says, so the
    # champion is calibrated on the held-out validation set before scoring.
    calibrated = _build_calibrator(best_estimator)
    calibrated.fit(X_val, y_val)

    val_prob = calibrated.predict_proba(X_val)[:, 1]
    thresholds = tune_thresholds(y_val, val_prob)

    # -- 8. evaluate on the untouched test set -----------------------------
    logger.info("=== Stage 8/8: final evaluation ===")
    test_metrics = evaluate_model(calibrated, X_test, y_test, thresholds, include_curves=True)
    val_metrics_final = evaluate_model(calibrated, X_val, y_val, thresholds, include_curves=False)
    logger.info("TEST -> AUC %.4f | AP %.4f | F1 %.4f | precision %.4f | recall %.4f",
                test_metrics["roc_auc"], test_metrics["average_precision"],
                test_metrics["f1"], test_metrics["precision"], test_metrics["recall"])

    baseline_comparison = {
        "baseline_model": baseline_name,
        "baseline_val_roc_auc": baseline_auc,
        "selected_model": best_name,
        "selected_val_roc_auc": best_auc,
        "auc_lift_over_baseline": float(best_auc - baseline_auc),
        "all_candidates": {n: s["val_roc_auc"] for n, s in cv_results.items()},
    }

    # -- fairness audit ----------------------------------------------------
    from src.fairness.auditor import audit_training_fairness

    fairness_report = audit_training_fairness(
        X_test_raw, y_test, calibrated.predict_proba(X_test)[:, 1], thresholds
    )
    if fairness_report.get("bias_alert"):
        logger.warning("Fairness alert on the test set: %s", fairness_report.get("alerts"))

    # -- SHAP background ---------------------------------------------------
    rng = np.random.default_rng(settings.random_seed)
    background_idx = rng.choice(len(X_train), size=min(500, len(X_train)), replace=False)
    background = {
        "matrix": X_train[background_idx],
        "expected_probability": float(np.mean(y_train)),
    }

    # -- register ----------------------------------------------------------
    version = registry.make_version_tag()
    artifacts = {
        "preprocessor": preprocessor,
        "model": calibrated,
        "base_estimator": best_estimator,
        "algorithm": best_name,
        "supports_shap_tree": candidates[best_name]["supports_shap_tree"],
        "thresholds": thresholds,
        "feature_names": feature_names,
        "input_columns": ALL_NUMERIC + ALL_CATEGORICAL,
        "training_medians": X_train_raw[ALL_NUMERIC].median().to_dict(),
        "training_modes": {
            col: (X_train_raw[col].mode().iloc[0] if not X_train_raw[col].mode().empty else None)
            for col in ALL_CATEGORICAL
        },
        "train_reference_sample": X_train_raw.sample(
            min(5000, len(X_train_raw)), random_state=settings.random_seed
        ),
    }

    metadata = registry.ModelMetadata(
        version=version,
        created_at=datetime.now(timezone.utc).isoformat(),
        algorithm=best_name,
        dataset_version=dataset_version,
        dataset_rows=len(processed),
        feature_count=len(feature_names),
        feature_names=feature_names,
        hyperparameters=cv_results[best_name]["best_params"],
        thresholds=thresholds.to_dict(),
        metrics=test_metrics,
        validation_metrics=val_metrics_final,
        cv_results=cv_results,
        baseline_comparison=baseline_comparison,
        fairness=fairness_report,
        training_reference={
            "imbalance_strategy": imbalance_strategy,
            "calibration": "isotonic (prefit on validation split)",
            "train_rows": int(len(y_train)),
            "val_rows": int(len(y_val)),
            "test_rows": int(len(y_test)),
            "positive_rate": float(processed[TARGET].mean()),
            "training_seconds": round(time.perf_counter() - started, 1),
            "random_seed": settings.random_seed,
        },
        notes=notes,
    )

    registry.save_model(artifacts, metadata, background=background, set_active=set_active)
    logger.info("Training complete in %.1fs -> version %s",
                time.perf_counter() - started, version)
    return TrainingResult(version=version, metadata=metadata, artifacts=artifacts)
