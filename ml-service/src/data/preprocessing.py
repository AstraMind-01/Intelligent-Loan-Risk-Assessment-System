"""Fitted preprocessing: imputation, outlier handling, scaling, encoding, splits.

Anything that learns parameters from the training set lives here and is persisted
with the model, so inference reuses the exact same statistics.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.config import ALL_CATEGORICAL, ALL_NUMERIC, TARGET, settings
from src.data.feature_engineering import add_engineered_features
from src.data.validation import repair_dataframe
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class QuantileClipper(BaseEstimator, TransformerMixin):
    """Winsorises numeric features at train-set quantiles.

    Capping rather than dropping keeps every application scorable — a genuine
    high earner must still get a decision, they just cannot drag the model around
    by sitting far outside the training distribution.
    """

    def __init__(self, lower_quantile: float = 0.005, upper_quantile: float = 0.995) -> None:
        self.lower_quantile = lower_quantile
        self.upper_quantile = upper_quantile

    def fit(self, X, y=None):  # noqa: N803
        frame = pd.DataFrame(X)
        self.feature_names_in_ = np.asarray(frame.columns, dtype=object)
        self.n_features_in_ = frame.shape[1]
        self.lower_bounds_ = frame.quantile(self.lower_quantile).to_numpy(dtype="float64")
        self.upper_bounds_ = frame.quantile(self.upper_quantile).to_numpy(dtype="float64")
        return self

    def transform(self, X):  # noqa: N803
        values = np.asarray(pd.DataFrame(X), dtype="float64")
        return np.clip(values, self.lower_bounds_, self.upper_bounds_)

    def get_feature_names_out(self, input_features=None):
        if input_features is not None:
            return np.asarray(input_features, dtype=object)
        return self.feature_names_in_


def build_preprocessor(scale_numeric: bool = True) -> ColumnTransformer:
    """Assemble the fitted preprocessing pipeline.

    Numeric: median imputation -> quantile clipping -> standardisation.
    Categorical: mode imputation -> one-hot with unknown levels ignored.

    Median imputation is deliberate: incomes and loan amounts are right-skewed,
    so the mean would drag imputed values upward and understate risk. Unknown
    categorical levels are ignored rather than erroring so a new loan purpose
    added by the product team cannot take the scoring service down.
    """
    numeric_steps: List[tuple] = [
        # keep_empty_features=True: a declared numeric feature that happens to
        # be 100% missing on a given training run (e.g. a bureau-derived
        # column when trained against a legacy CSV without one) would
        # otherwise be silently dropped by SimpleImputer instead of filled,
        # desyncing the feature schema everywhere else assumes ALL_NUMERIC is
        # complete (the SHAP explainer's feature grouping in particular).
        ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("clip", QuantileClipper()),
    ]
    if scale_numeric:
        numeric_steps.append(("scale", StandardScaler()))

    return ColumnTransformer(
        transformers=[
            ("num", Pipeline(numeric_steps), ALL_NUMERIC),
            (
                "cat",
                Pipeline([
                    ("impute", SimpleImputer(strategy="most_frequent", keep_empty_features=True)),
                    ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False,
                                             min_frequency=None, drop=None)),
                ]),
                ALL_CATEGORICAL,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Raw frame -> model-ready feature frame (pre-transform).

    Repairs the schema, adds engineered columns, and returns exactly the columns
    the preprocessor expects, in a stable order.
    """
    repaired = repair_dataframe(df)
    enriched = add_engineered_features(repaired)
    return enriched.reindex(columns=ALL_NUMERIC + ALL_CATEGORICAL)


def get_output_feature_names(preprocessor: ColumnTransformer) -> List[str]:
    """Column names after transformation, aligned with the model's inputs."""
    return [str(name) for name in preprocessor.get_feature_names_out()]


def split_data(
    df: pd.DataFrame,
    test_size: Optional[float] = None,
    val_size: Optional[float] = None,
    seed: Optional[int] = None,
) -> Dict[str, Tuple[pd.DataFrame, pd.Series]]:
    """Stratified train/validation/test split.

    Validation is used for threshold tuning and challenger-vs-champion checks;
    test is touched exactly once, for the final reported metrics.
    """
    test_size = settings.test_size if test_size is None else test_size
    val_size = settings.val_size if val_size is None else val_size
    seed = settings.random_seed if seed is None else seed

    y = df[TARGET].astype(int)
    X = df.drop(columns=[TARGET])

    X_temp, X_test, y_temp, y_test = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=seed
    )
    # val_size is expressed as a fraction of the full dataset, so rescale it
    # against what is left after the test split.
    relative_val = val_size / (1.0 - test_size)
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp, test_size=relative_val, stratify=y_temp, random_state=seed
    )

    logger.info(
        "Split -> train %d (%.2f%% pos) | val %d (%.2f%% pos) | test %d (%.2f%% pos)",
        len(X_train), 100 * y_train.mean(),
        len(X_val), 100 * y_val.mean(),
        len(X_test), 100 * y_test.mean(),
    )
    return {
        "train": (X_train, y_train),
        "val": (X_val, y_val),
        "test": (X_test, y_test),
    }


def apply_imbalance_strategy(
    X: np.ndarray,
    y: pd.Series,
    strategy: Optional[str] = None,
    seed: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Rebalance the training set.

    ``class_weight`` (the default) changes nothing here — the models carry the
    weighting internally, which preserves calibrated probabilities. Resampling
    strategies distort the base rate, so anything trained with them must be
    recalibrated before its probabilities are used as risk scores.
    """
    strategy = (strategy or settings.imbalance_strategy).lower()
    seed = settings.random_seed if seed is None else seed
    y_array = np.asarray(y).astype(int)

    if strategy in ("class_weight", "none"):
        return X, y_array

    if strategy == "smote":
        from imblearn.over_sampling import SMOTE

        sampler = SMOTE(random_state=seed, k_neighbors=5)
    elif strategy == "undersample":
        from imblearn.under_sampling import RandomUnderSampler

        sampler = RandomUnderSampler(random_state=seed)
    elif strategy == "smote_tomek":
        from imblearn.combine import SMOTETomek

        sampler = SMOTETomek(random_state=seed)
    else:
        raise ValueError(f"Unknown imbalance strategy '{strategy}'.")

    X_resampled, y_resampled = sampler.fit_resample(X, y_array)
    logger.info(
        "Imbalance strategy '%s': %d -> %d rows (positive rate %.4f -> %.4f)",
        strategy, len(y_array), len(y_resampled), y_array.mean(), y_resampled.mean(),
    )
    return X_resampled, y_resampled


def compute_scale_pos_weight(y: pd.Series) -> float:
    """XGBoost's ``scale_pos_weight``: ratio of negatives to positives."""
    y_array = np.asarray(y).astype(int)
    positives = int(y_array.sum())
    negatives = len(y_array) - positives
    return float(negatives / positives) if positives else 1.0
