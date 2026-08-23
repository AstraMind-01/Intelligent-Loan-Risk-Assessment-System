"""Unit tests for validation and preprocessing."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.config import ALL_CATEGORICAL, ALL_NUMERIC, TARGET
from src.data.preprocessing import (
    QuantileClipper,
    apply_imbalance_strategy,
    build_preprocessor,
    compute_scale_pos_weight,
    get_output_feature_names,
    prepare_features,
    split_data,
)
from src.data.validation import repair_dataframe, validate_dataframe


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
class TestValidation:
    def test_clean_frame_is_valid(self, sample_frame):
        assert validate_dataframe(sample_frame).is_valid

    def test_missing_target_is_an_error(self, sample_frame):
        report = validate_dataframe(sample_frame.drop(columns=[TARGET]))
        assert not report.is_valid
        assert any(TARGET in e for e in report.errors)

    def test_non_binary_target_is_an_error(self, sample_frame):
        frame = sample_frame.copy()
        frame.loc[0, TARGET] = 5
        assert not validate_dataframe(frame).is_valid

    def test_missing_values_are_counted(self, sample_frame):
        frame = sample_frame.copy()
        frame.loc[:9, "Income"] = np.nan
        report = validate_dataframe(frame)
        assert report.missing_counts["Income"] == 10

    def test_out_of_range_values_warn_but_do_not_fail(self, sample_frame):
        frame = sample_frame.copy()
        frame.loc[0, "CreditScore"] = 9999
        report = validate_dataframe(frame)
        assert report.is_valid
        assert report.out_of_range_counts["CreditScore"] == 1

    def test_non_numeric_value_is_an_error(self, sample_frame):
        frame = sample_frame.copy()
        frame["Income"] = frame["Income"].astype(object)
        frame.loc[0, "Income"] = "not-a-number"
        assert not validate_dataframe(frame).is_valid

    def test_unknown_category_warns(self, sample_frame):
        frame = sample_frame.copy()
        frame.loc[0, "Education"] = "Kindergarten"
        report = validate_dataframe(frame)
        assert "Kindergarten" in report.unknown_categories["Education"]

    def test_empty_frame_is_invalid(self):
        assert not validate_dataframe(pd.DataFrame()).is_valid

    def test_single_class_target_is_invalid(self, sample_frame):
        frame = sample_frame.copy()
        frame[TARGET] = 0
        assert not validate_dataframe(frame).is_valid


class TestRepair:
    def test_out_of_range_numerics_are_clipped(self, sample_frame):
        frame = sample_frame.copy()
        frame.loc[0, "CreditScore"] = 9999
        frame.loc[1, "CreditScore"] = -50
        repaired = repair_dataframe(frame)
        assert repaired.loc[0, "CreditScore"] == 850
        assert repaired.loc[1, "CreditScore"] == 300

    def test_unknown_categories_become_missing(self, sample_frame):
        frame = sample_frame.copy()
        frame.loc[0, "LoanPurpose"] = "Spaceship"
        assert pd.isna(repair_dataframe(frame).loc[0, "LoanPurpose"])

    def test_absent_columns_are_created(self, sample_frame):
        repaired = repair_dataframe(sample_frame.drop(columns=["InterestRate", "HasCoSigner"]))
        assert repaired["InterestRate"].isna().all()
        assert repaired["HasCoSigner"].isna().all()

    def test_repair_does_not_drop_rows(self, sample_frame):
        assert len(repair_dataframe(sample_frame)) == len(sample_frame)


# ---------------------------------------------------------------------------
# QuantileClipper
# ---------------------------------------------------------------------------
class TestQuantileClipper:
    def test_extreme_values_are_capped(self):
        data = pd.DataFrame({"a": list(range(100))})
        clipper = QuantileClipper(0.05, 0.95).fit(data)
        result = clipper.transform(pd.DataFrame({"a": [-500, 50, 500]}))
        assert result[0, 0] >= data["a"].quantile(0.05)
        assert result[2, 0] <= data["a"].quantile(0.95)

    def test_in_range_values_are_untouched(self):
        data = pd.DataFrame({"a": list(range(100))})
        clipper = QuantileClipper(0.0, 1.0).fit(data)
        assert clipper.transform(pd.DataFrame({"a": [42]}))[0, 0] == 42

    def test_feature_names_survive(self):
        data = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        clipper = QuantileClipper().fit(data)
        assert list(clipper.get_feature_names_out()) == ["a", "b"]


# ---------------------------------------------------------------------------
# Preprocessor
# ---------------------------------------------------------------------------
class TestPreprocessor:
    def test_produces_a_dense_finite_matrix(self, sample_frame):
        features = prepare_features(sample_frame)
        matrix = build_preprocessor().fit_transform(features, sample_frame[TARGET])
        assert matrix.shape[0] == len(sample_frame)
        assert np.isfinite(matrix).all()

    def test_missing_values_are_imputed_away(self, sample_frame):
        frame = sample_frame.copy()
        frame.loc[:19, "Income"] = np.nan
        frame.loc[:19, "Education"] = np.nan
        features = prepare_features(frame)
        matrix = build_preprocessor().fit_transform(features, frame[TARGET])
        assert not np.isnan(matrix).any()

    def test_numeric_features_are_standardised(self, sample_frame):
        features = prepare_features(sample_frame)
        matrix = build_preprocessor().fit_transform(features, sample_frame[TARGET])
        numeric_block = matrix[:, : len(ALL_NUMERIC)]
        assert np.abs(numeric_block.mean(axis=0)).max() < 1e-6

    def test_unseen_category_at_transform_time_does_not_raise(self, sample_frame):
        preprocessor = build_preprocessor()
        preprocessor.fit(prepare_features(sample_frame), sample_frame[TARGET])

        unseen = sample_frame.head(1).copy()
        unseen.loc[unseen.index[0], "LoanPurpose"] = "Cryptocurrency"
        matrix = preprocessor.transform(prepare_features(unseen))
        assert matrix.shape[0] == 1
        assert np.isfinite(matrix).all()

    def test_feature_names_match_matrix_width(self, sample_frame):
        preprocessor = build_preprocessor()
        matrix = preprocessor.fit_transform(prepare_features(sample_frame), sample_frame[TARGET])
        assert len(get_output_feature_names(preprocessor)) == matrix.shape[1]

    def test_prepare_features_returns_expected_columns(self, sample_frame):
        features = prepare_features(sample_frame)
        assert list(features.columns) == ALL_NUMERIC + ALL_CATEGORICAL

    def test_transform_is_deterministic(self, sample_frame):
        preprocessor = build_preprocessor()
        features = prepare_features(sample_frame)
        preprocessor.fit(features, sample_frame[TARGET])
        np.testing.assert_array_equal(
            preprocessor.transform(features), preprocessor.transform(features)
        )


# ---------------------------------------------------------------------------
# Splitting and imbalance
# ---------------------------------------------------------------------------
class TestSplitting:
    def test_splits_are_disjoint_and_complete(self, sample_frame):
        splits = split_data(sample_frame, test_size=0.2, val_size=0.2)
        total = sum(len(x) for x, _ in splits.values())
        assert total == len(sample_frame)

        indices = [set(x.index) for x, _ in splits.values()]
        assert not (indices[0] & indices[1])
        assert not (indices[0] & indices[2])
        assert not (indices[1] & indices[2])

    def test_class_balance_is_preserved(self, sample_frame):
        splits = split_data(sample_frame, test_size=0.2, val_size=0.2)
        overall = sample_frame[TARGET].mean()
        for _, y in splits.values():
            assert abs(y.mean() - overall) < 0.10

    def test_split_is_reproducible(self, sample_frame):
        first = split_data(sample_frame, seed=1)["train"][0].index.tolist()
        second = split_data(sample_frame, seed=1)["train"][0].index.tolist()
        assert first == second

    def test_target_is_not_a_feature(self, sample_frame):
        X, _ = split_data(sample_frame)["train"]
        assert TARGET not in X.columns


class TestImbalance:
    def test_class_weight_leaves_data_untouched(self, sample_frame):
        X = np.random.default_rng(0).normal(size=(100, 5))
        y = pd.Series([0] * 90 + [1] * 10)
        X_out, y_out = apply_imbalance_strategy(X, y, strategy="class_weight")
        assert len(y_out) == 100

    def test_smote_balances_the_classes(self):
        rng = np.random.default_rng(0)
        X = rng.normal(size=(300, 5))
        y = pd.Series([0] * 270 + [1] * 30)
        _, y_out = apply_imbalance_strategy(X, y, strategy="smote", seed=0)
        assert (y_out == 1).sum() == (y_out == 0).sum()

    def test_undersampling_shrinks_the_majority(self):
        rng = np.random.default_rng(0)
        X = rng.normal(size=(300, 5))
        y = pd.Series([0] * 270 + [1] * 30)
        _, y_out = apply_imbalance_strategy(X, y, strategy="undersample", seed=0)
        assert (y_out == 0).sum() == (y_out == 1).sum() == 30

    def test_unknown_strategy_raises(self):
        with pytest.raises(ValueError):
            apply_imbalance_strategy(np.zeros((10, 2)), pd.Series([0] * 9 + [1]), strategy="magic")

    def test_scale_pos_weight_is_the_negative_positive_ratio(self):
        assert compute_scale_pos_weight(pd.Series([0] * 90 + [1] * 10)) == pytest.approx(9.0)

    def test_scale_pos_weight_handles_no_positives(self):
        assert compute_scale_pos_weight(pd.Series([0] * 10)) == 1.0
