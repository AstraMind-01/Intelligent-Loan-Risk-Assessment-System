"""Unit tests for domain feature engineering and the backend payload adapter."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.config import ENGINEERED_CATEGORICAL, ENGINEERED_NUMERIC
from src.data.feature_engineering import (
    AGE_RISK_WEIGHTS,
    add_engineered_features,
    monthly_instalment,
)
from src.inference.adapter import derive_dti, imputed_field_names, normalize_payload


def frame_of(**overrides) -> pd.DataFrame:
    base = {
        "Age": 40, "Income": 100_000, "LoanAmount": 100_000, "CreditScore": 700,
        "MonthsEmployed": 60, "NumCreditLines": 3, "InterestRate": 10.0,
        "LoanTerm": 36, "DTIRatio": 0.4, "Education": "Bachelor's",
        "EmploymentType": "Full-time", "MaritalStatus": "Married",
        "HasMortgage": "Yes", "HasDependents": "No", "LoanPurpose": "Home",
        "HasCoSigner": "No",
    }
    base.update(overrides)
    return pd.DataFrame([base])


class TestMonthlyInstalment:
    def test_matches_the_amortisation_formula(self):
        # 100,000 at 12% nominal over 12 months -> ~8,884.88/month.
        result = monthly_instalment(pd.Series([100_000.0]), pd.Series([12.0]), pd.Series([12]))
        assert result.iloc[0] == pytest.approx(8_884.88, abs=1.0)

    def test_zero_rate_falls_back_to_straight_line(self):
        result = monthly_instalment(pd.Series([120_000.0]), pd.Series([0.0]), pd.Series([12]))
        assert result.iloc[0] == pytest.approx(10_000.0)

    def test_longer_term_lowers_the_payment(self):
        short = monthly_instalment(pd.Series([100_000.0]), pd.Series([10.0]), pd.Series([12]))
        long = monthly_instalment(pd.Series([100_000.0]), pd.Series([10.0]), pd.Series([60]))
        assert long.iloc[0] < short.iloc[0]

    def test_never_negative(self):
        result = monthly_instalment(
            pd.Series([0.0, 50_000.0]), pd.Series([0.0, 25.0]), pd.Series([1, 60])
        )
        assert (result >= 0).all()

    def test_handles_missing_inputs(self):
        result = monthly_instalment(
            pd.Series([np.nan]), pd.Series([np.nan]), pd.Series([np.nan])
        )
        assert np.isfinite(result.iloc[0])


class TestEngineeredFeatures:
    def test_all_declared_columns_are_produced(self):
        out = add_engineered_features(frame_of())
        for column in ENGINEERED_NUMERIC + ENGINEERED_CATEGORICAL:
            assert column in out.columns

    def test_no_infinities_are_produced(self):
        out = add_engineered_features(frame_of(Income=0, LoanAmount=50_000, NumCreditLines=0))
        numeric = out[ENGINEERED_NUMERIC].to_numpy(dtype="float64")
        assert not np.isinf(numeric).any()

    def test_loan_to_income_ratio(self):
        out = add_engineered_features(frame_of(Income=50_000, LoanAmount=150_000))
        assert out["LoanToIncomeRatio"].iloc[0] == pytest.approx(3.0)

    def test_zero_income_does_not_blow_up_the_ratio(self):
        out = add_engineered_features(frame_of(Income=0, LoanAmount=100_000))
        assert np.isfinite(out["LoanToIncomeRatio"].iloc[0])

    def test_total_debt_service_exceeds_existing_dti(self):
        out = add_engineered_features(frame_of(DTIRatio=0.3))
        assert out["TotalDebtServiceRatio"].iloc[0] > 0.3

    def test_employment_stability_rewards_tenure(self):
        short = add_engineered_features(frame_of(MonthsEmployed=1))["EmploymentStabilityScore"].iloc[0]
        long = add_engineered_features(frame_of(MonthsEmployed=120))["EmploymentStabilityScore"].iloc[0]
        assert long > short

    def test_employment_stability_rewards_full_time(self):
        unemployed = add_engineered_features(
            frame_of(EmploymentType="Unemployed"))["EmploymentStabilityScore"].iloc[0]
        full_time = add_engineered_features(
            frame_of(EmploymentType="Full-time"))["EmploymentStabilityScore"].iloc[0]
        assert full_time > unemployed

    def test_bounded_scores_stay_in_unit_interval(self):
        out = add_engineered_features(frame_of(MonthsEmployed=700, Age=69, NumCreditLines=4))
        for column in ("EmploymentStabilityScore", "ThinFileScore",
                       "AlternateDataScore", "CollateralSupportScore"):
            value = out[column].iloc[0]
            assert 0.0 <= value <= 1.0, column

    @pytest.mark.parametrize("age,expected", [(20, "18-25"), (30, "26-35"),
                                              (45, "36-50"), (60, "51-65"), (70, "65+")])
    def test_age_banding(self, age, expected):
        assert add_engineered_features(frame_of(Age=age))["AgeGroup"].iloc[0] == expected

    def test_age_risk_band_matches_the_weight_table(self):
        out = add_engineered_features(frame_of(Age=20))
        assert out["AgeRiskBand"].iloc[0] == pytest.approx(AGE_RISK_WEIGHTS["18-25"])

    def test_young_applicant_has_a_thinner_file(self):
        young = add_engineered_features(
            frame_of(Age=20, MonthsEmployed=6, NumCreditLines=1))["ThinFileScore"].iloc[0]
        established = add_engineered_features(
            frame_of(Age=50, MonthsEmployed=110, NumCreditLines=4))["ThinFileScore"].iloc[0]
        assert young > established

    def test_cosigner_raises_collateral_support(self):
        without = add_engineered_features(frame_of(HasCoSigner="No"))["CollateralSupportScore"].iloc[0]
        with_signer = add_engineered_features(frame_of(HasCoSigner="Yes"))["CollateralSupportScore"].iloc[0]
        assert with_signer > without

    def test_credit_score_band_is_ordinal_and_monotonic(self):
        low = add_engineered_features(frame_of(CreditScore=350))["CreditScoreBandOrdinal"].iloc[0]
        high = add_engineered_features(frame_of(CreditScore=820))["CreditScoreBandOrdinal"].iloc[0]
        assert high > low

    def test_input_frame_is_not_mutated(self):
        original = frame_of()
        before = original.copy()
        add_engineered_features(original)
        pd.testing.assert_frame_equal(original, before)

    def test_handles_a_completely_empty_row(self):
        empty = pd.DataFrame([{}])
        out = add_engineered_features(empty)
        assert len(out) == 1


class TestAdapter:
    def test_backend_payload_maps_to_canonical_fields(self, backend_application):
        record = normalize_payload(backend_application)
        assert record["Age"] == 42
        assert record["Income"] == 85_000
        assert record["LoanAmount"] == 120_000
        assert record["CreditScore"] == 640
        assert record["LoanTerm"] == 36
        assert record["Education"] == "Bachelor's"
        assert record["EmploymentType"] == "Full-time"
        assert record["MaritalStatus"] == "Married"
        assert record["LoanPurpose"] == "Home"
        assert record["HasDependents"] == "Yes"

    def test_dti_is_derived_from_debts_and_income(self, backend_application):
        record = normalize_payload(backend_application)
        assert record["DTIRatio"] == pytest.approx(35_700 / 85_000)

    def test_fields_the_backend_cannot_supply_are_left_for_imputation(self, backend_application):
        record = normalize_payload(backend_application)
        for field in ("MonthsEmployed", "NumCreditLines", "InterestRate",
                      "HasMortgage", "HasCoSigner"):
            assert record[field] is None
        assert set(imputed_field_names(record)) >= {"InterestRate", "HasMortgage"}

    def test_canonical_payload_passes_through_unchanged(self, sample_application):
        record = normalize_payload(sample_application)
        for key, value in sample_application.items():
            assert record[key] == value

    def test_canonical_keys_override_nested_ones(self, backend_application):
        record = normalize_payload({**backend_application, "CreditScore": 800})
        assert record["CreditScore"] == 800

    def test_flat_camel_case_is_accepted(self):
        record = normalize_payload({"age": 30, "income": 50_000, "creditScore": 700,
                                    "loanAmount": 20_000, "tenure": 24})
        assert record["Age"] == 30
        assert record["LoanTerm"] == 24

    @pytest.mark.parametrize("backend_value,expected", [
        ("high_school", "High School"), ("bachelors", "Bachelor's"),
        ("masters", "Master's"), ("doctorate", "PhD"), ("other", None),
    ])
    def test_education_mapping(self, backend_value, expected):
        record = normalize_payload({"personalInfo": {"education": backend_value}})
        assert record["Education"] == expected

    @pytest.mark.parametrize("backend_value,expected", [
        ("full_time", "Full-time"), ("part_time", "Part-time"),
        ("self_employed", "Self-employed"), ("contract", "Self-employed"),
        ("retired", "Part-time"), ("unemployed", "Unemployed"),
    ])
    def test_employment_mapping(self, backend_value, expected):
        record = normalize_payload({"personalInfo": {"employmentType": backend_value}})
        assert record["EmploymentType"] == expected

    @pytest.mark.parametrize("backend_value,expected", [
        ("home_purchase", "Home"), ("auto_loan", "Auto"), ("education", "Education"),
        ("business", "Business"), ("debt_consolidation", "Other"), ("medical", "Other"),
    ])
    def test_purpose_mapping(self, backend_value, expected):
        record = normalize_payload({"financialInfo": {"purpose": backend_value}})
        assert record["LoanPurpose"] == expected

    def test_widowed_maps_to_divorced(self):
        record = normalize_payload({"personalInfo": {"maritalStatus": "widowed"}})
        assert record["MaritalStatus"] == "Divorced"

    def test_unrecognised_enum_becomes_none(self):
        record = normalize_payload({"personalInfo": {"education": "wizard_school"}})
        assert record["Education"] is None

    def test_zero_dependents_means_no(self):
        assert normalize_payload({"personalInfo": {"dependents": 0}})["HasDependents"] == "No"

    def test_boolean_flags_are_normalised(self):
        record = normalize_payload({"HasMortgage": True, "HasCoSigner": "yes"})
        assert record["HasMortgage"] == "Yes"
        assert record["HasCoSigner"] == "Yes"

    def test_empty_payload_yields_all_nones(self):
        record = normalize_payload({})
        assert all(value is None for value in record.values())

    def test_derive_dti_prefers_an_explicit_value(self):
        assert derive_dti(50_000, 100_000, explicit=0.33) == pytest.approx(0.33)

    def test_derive_dti_returns_none_without_income(self):
        assert derive_dti(50_000, 0) is None

    def test_derive_dti_is_bounded(self):
        assert derive_dti(10_000_000, 10_000) == pytest.approx(1.5)
