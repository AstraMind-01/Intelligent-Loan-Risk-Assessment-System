"""Model output sanity, threshold mapping, fraud and fairness logic."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.config import settings
from src.fairness.auditor import build_fairness_report
from src.fraud.detector import (
    DuplicateApplicationIndex,
    detect_duplicates_in_frame,
    score_fraud,
)
from src.models.evaluate import (
    RiskThresholds,
    classification_metrics,
    confidence_from_probability,
    probability_to_score,
    score_to_risk_level,
    tune_thresholds,
)
from src.monitoring.drift import (
    categorical_psi,
    detect_prediction_drift,
    population_stability_index,
)
from src.monitoring.performance import officer_agreement_rate

THRESHOLDS = RiskThresholds(low_cutoff=0.05, high_cutoff=0.30, decision_threshold=0.20)


# ---------------------------------------------------------------------------
# Score mapping — the checklist's "score always between 0-100" requirement
# ---------------------------------------------------------------------------
class TestScoreMapping:
    def test_scores_stay_within_zero_and_one_hundred(self):
        probabilities = np.linspace(0.0, 1.0, 1001)
        scores = probability_to_score(probabilities, THRESHOLDS)
        assert scores.min() >= 0.0
        assert scores.max() <= 100.0

    def test_extreme_and_invalid_probabilities_are_still_bounded(self):
        scores = probability_to_score(np.array([-5.0, 0.0, 1.0, 7.0]), THRESHOLDS)
        assert scores.min() >= 0.0 and scores.max() <= 100.0

    def test_mapping_is_monotonic(self):
        scores = probability_to_score(np.linspace(0, 1, 500), THRESHOLDS)
        assert np.all(np.diff(scores) >= -1e-9)

    def test_low_cutoff_lands_on_the_auto_approve_threshold(self):
        score = probability_to_score(np.array([THRESHOLDS.low_cutoff]), THRESHOLDS)[0]
        assert score == pytest.approx(settings.low_risk_cutoff, abs=1e-6)

    def test_high_cutoff_lands_on_the_auto_reject_threshold(self):
        score = probability_to_score(np.array([THRESHOLDS.high_cutoff]), THRESHOLDS)[0]
        assert score == pytest.approx(settings.high_risk_cutoff, abs=1e-6)

    def test_zero_probability_scores_zero(self):
        assert probability_to_score(np.array([0.0]), THRESHOLDS)[0] == pytest.approx(0.0)

    def test_certain_default_scores_one_hundred(self):
        assert probability_to_score(np.array([1.0]), THRESHOLDS)[0] == pytest.approx(100.0)

    def test_degenerate_thresholds_do_not_divide_by_zero(self):
        degenerate = RiskThresholds(low_cutoff=0.5, high_cutoff=0.5001, decision_threshold=0.5)
        scores = probability_to_score(np.linspace(0, 1, 100), degenerate)
        assert np.isfinite(scores).all()


class TestRiskLevels:
    @pytest.mark.parametrize("score,expected", [
        (0, "low"), (24.9, "low"), (25, "medium"), (50, "medium"),
        (74.9, "medium"), (75, "high"), (100, "high"),
    ])
    def test_banding_matches_the_backend_thresholds(self, score, expected):
        assert score_to_risk_level(np.array([score]))[0] == expected

    def test_every_score_gets_a_level(self):
        levels = score_to_risk_level(np.linspace(0, 100, 500))
        assert set(levels) <= {"low", "medium", "high"}
        assert len(levels) == 500


class TestConfidence:
    def test_confidence_is_a_probability(self):
        values = confidence_from_probability(np.linspace(0, 1, 200), THRESHOLDS)
        assert values.min() >= 0.0 and values.max() <= 1.0

    def test_a_certain_prediction_beats_a_coin_flip(self):
        certain = confidence_from_probability(np.array([0.01]), THRESHOLDS)[0]
        uncertain = confidence_from_probability(np.array([0.5]), THRESHOLDS)[0]
        assert certain > uncertain

    def test_confidence_dips_at_a_band_boundary(self):
        on_boundary = confidence_from_probability(
            np.array([THRESHOLDS.high_cutoff]), THRESHOLDS)[0]
        clear_of_boundary = confidence_from_probability(np.array([0.90]), THRESHOLDS)[0]
        assert clear_of_boundary > on_boundary

    def test_confidence_is_not_just_the_score(self):
        # Both tails are confident even though their risk scores are opposite.
        low = confidence_from_probability(np.array([0.01]), THRESHOLDS)[0]
        high = confidence_from_probability(np.array([0.99]), THRESHOLDS)[0]
        assert low > 0.7 and high > 0.7


class TestThresholdTuning:
    def test_cutoffs_are_ordered_and_within_range(self):
        rng = np.random.default_rng(0)
        y = rng.binomial(1, 0.12, 5000)
        prob = np.clip(rng.beta(2, 12, 5000) + y * 0.15, 0, 1)
        thresholds = tune_thresholds(y, prob)
        assert 0 < thresholds.low_cutoff < thresholds.high_cutoff < 1

    def test_low_cutoff_preserves_most_defaulters(self):
        rng = np.random.default_rng(1)
        y = rng.binomial(1, 0.15, 8000)
        prob = np.clip(rng.beta(2, 10, 8000) + y * 0.25, 0, 1)
        thresholds = tune_thresholds(y, prob, target_recall=0.95)
        assert (prob[y == 1] >= thresholds.low_cutoff).mean() >= 0.90

    def test_high_band_defaults_more_than_the_base_rate(self):
        rng = np.random.default_rng(2)
        y = rng.binomial(1, 0.12, 8000)
        prob = np.clip(rng.beta(2, 12, 8000) + y * 0.30, 0, 1)
        thresholds = tune_thresholds(y, prob)
        flagged = prob >= thresholds.high_cutoff
        if flagged.sum() > 20:
            assert y[flagged].mean() > y.mean()


class TestClassificationMetrics:
    def test_perfect_predictions_score_perfectly(self):
        y = np.array([0, 0, 1, 1])
        metrics = classification_metrics(y, np.array([0.0, 0.1, 0.9, 1.0]), threshold=0.5)
        assert metrics["roc_auc"] == pytest.approx(1.0)
        assert metrics["accuracy"] == pytest.approx(1.0)

    def test_confusion_matrix_totals_the_sample(self):
        rng = np.random.default_rng(3)
        y = rng.binomial(1, 0.3, 500)
        metrics = classification_metrics(y, rng.uniform(size=500))
        cm = metrics["confusion_matrix"]
        assert sum(cm.values()) == 500

    def test_metrics_are_bounded(self):
        rng = np.random.default_rng(4)
        y = rng.binomial(1, 0.2, 400)
        metrics = classification_metrics(y, rng.uniform(size=400))
        for key in ("accuracy", "precision", "recall", "f1", "roc_auc", "average_precision"):
            assert 0.0 <= metrics[key] <= 1.0


# ---------------------------------------------------------------------------
# Fraud
# ---------------------------------------------------------------------------
class TestFraudDetection:
    def test_a_clean_application_is_not_flagged(self, sample_application):
        result = score_fraud(sample_application, check_duplicates=False)
        assert result["fraudFlag"] is False
        assert result["fraudProbability"] < settings.fraud_score_threshold

    def test_probability_is_always_a_probability(self, sample_application):
        for application in (sample_application, {"Age": 19, "Income": 0, "LoanAmount": 500_000}):
            result = score_fraud(application, check_duplicates=False)
            assert 0.0 <= result["fraudProbability"] <= 1.0

    def test_unemployed_with_high_income_is_flagged(self, sample_application):
        application = {**sample_application, "EmploymentType": "Unemployed", "Income": 140_000}
        result = score_fraud(application, check_duplicates=False)
        assert any(r["code"] == "INCOME_EMPLOYMENT_MISMATCH" for r in result["triggeredRules"])

    def test_tenure_longer_than_a_working_life_is_flagged(self, sample_application):
        application = {**sample_application, "Age": 20, "MonthsEmployed": 200}
        result = score_fraud(application, check_duplicates=False)
        assert any(r["code"] == "TENURE_EXCEEDS_AGE" for r in result["triggeredRules"])

    def test_implausible_loan_to_income_is_flagged(self, sample_application):
        application = {**sample_application, "Income": 20_000, "LoanAmount": 240_000}
        result = score_fraud(application, check_duplicates=False)
        assert any(r["code"] == "IMPLAUSIBLE_LOAN_TO_INCOME" for r in result["triggeredRules"])

    def test_several_contradictions_clear_the_threshold(self):
        application = {
            "Age": 19, "Income": 130_000, "EmploymentType": "Unemployed",
            "MonthsEmployed": 180, "CreditScore": 820, "NumCreditLines": 4,
            "LoanAmount": 240_000, "DTIRatio": 0.9,
        }
        result = score_fraud(application, check_duplicates=False)
        assert result["fraudFlag"] is True
        assert result["reason"]
        assert result["riskTier"] == "high"

    def test_a_flagged_application_always_states_a_reason(self):
        result = score_fraud(
            {"Age": 19, "Income": 130_000, "EmploymentType": "Unemployed",
             "MonthsEmployed": 180, "CreditScore": 830, "NumCreditLines": 4},
            check_duplicates=False,
        )
        if result["fraudFlag"]:
            assert result["reason"] and len(result["reasons"]) > 0

    def test_missing_fields_do_not_raise(self):
        result = score_fraud({}, check_duplicates=False)
        assert 0.0 <= result["fraudProbability"] <= 1.0


class TestDuplicateDetection:
    def test_first_submission_is_not_a_duplicate(self, sample_application):
        index = DuplicateApplicationIndex()
        assert index.check_and_register(sample_application, "a1")["is_duplicate"] is False

    def test_resubmission_is_detected(self, sample_application):
        index = DuplicateApplicationIndex()
        index.check_and_register(sample_application, "a1")
        second = index.check_and_register(sample_application, "a2")
        assert second["is_duplicate"] is True
        assert second["previous_application_id"] == "a1"

    def test_different_applicants_do_not_collide(self, sample_application):
        index = DuplicateApplicationIndex()
        index.check_and_register(sample_application, "a1")
        other = {**sample_application, "Age": 55, "Income": 42_000}
        assert index.check_and_register(other, "a2")["is_duplicate"] is False

    def test_income_inflation_on_resubmission_is_measured(self, sample_application):
        index = DuplicateApplicationIndex()
        index.check_and_register({**sample_application, "Income": 50_000}, "a1")
        second = index.check_and_register({**sample_application, "Income": 100_000}, "a2")
        assert second["income_change_pct"] == pytest.approx(100.0)

    def test_frame_level_duplicate_detection(self, sample_application):
        frame = pd.DataFrame([sample_application] * 3 + [{**sample_application, "Age": 61}])
        result = detect_duplicates_in_frame(frame)
        assert result["duplicate_groups"] == 1
        assert result["duplicate_rows"] == 3


# ---------------------------------------------------------------------------
# Fairness
# ---------------------------------------------------------------------------
class TestFairness:
    def _frame(self, n=400):
        rng = np.random.default_rng(0)
        return pd.DataFrame({
            "AgeGroup": rng.choice(["26-35", "36-50", "51-65"], n),
            "MaritalStatus": rng.choice(["Single", "Married", "Divorced"], n),
            "Education": rng.choice(["High School", "Bachelor's", "PhD"], n),
            "EmploymentType": rng.choice(["Full-time", "Part-time"], n),
        })

    def test_an_unbiased_population_raises_no_alert(self):
        rng = np.random.default_rng(1)
        frame = self._frame()
        report = build_fairness_report(frame, rng.uniform(0, 100, len(frame)))
        assert report["bias_alert"] is False

    def test_an_engineered_disparity_is_caught(self):
        frame = self._frame(600)
        # Everyone in one group is scored as high risk, everyone else as low.
        scores = np.where(frame["MaritalStatus"] == "Divorced", 90.0, 10.0)
        report = build_fairness_report(frame, scores)
        assert report["bias_alert"] is True
        assert report["attributes"]["MaritalStatus"]["disparate_impact_ratio"] < 0.8
        assert report["attributes"]["MaritalStatus"]["passes_four_fifths_rule"] is False

    def test_report_carries_the_required_shape(self):
        frame = self._frame()
        report = build_fairness_report(frame, np.full(len(frame), 30.0))
        for key in ("n_applications", "overall_approval_rate", "attributes",
                    "bias_alert", "alerts", "summary", "thresholds"):
            assert key in report

    def test_tiny_groups_are_not_judged(self):
        frame = pd.DataFrame({"MaritalStatus": ["Single"] * 200 + ["Divorced"] * 3})
        scores = np.concatenate([np.full(200, 10.0), np.full(3, 95.0)])
        result = build_fairness_report(frame, scores)["attributes"]["MaritalStatus"]
        assert result["bias_alert"] is False
        assert "note" in result

    def test_outcomes_enable_the_equal_opportunity_metric(self):
        rng = np.random.default_rng(2)
        frame = self._frame(600)
        scores = rng.uniform(0, 100, len(frame))
        outcomes = rng.binomial(1, 0.15, len(frame))
        report = build_fairness_report(frame, scores, y_true=outcomes)
        assert report["attributes"]["MaritalStatus"]["equal_opportunity_gap"] is not None


# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------
class TestDrift:
    def test_identical_distributions_have_near_zero_psi(self):
        rng = np.random.default_rng(0)
        data = rng.normal(size=5000)
        assert population_stability_index(data, data) < 0.01

    def test_a_shifted_distribution_registers_drift(self):
        rng = np.random.default_rng(1)
        reference = rng.normal(0, 1, 5000)
        shifted = rng.normal(2.5, 1, 5000)
        assert population_stability_index(reference, shifted) > settings.drift_psi_alert

    def test_psi_is_never_negative(self):
        rng = np.random.default_rng(2)
        for _ in range(10):
            value = population_stability_index(rng.normal(size=1000), rng.normal(size=1000))
            assert value >= 0

    def test_categorical_psi_detects_a_composition_change(self):
        reference = ["a"] * 800 + ["b"] * 200
        current = ["a"] * 200 + ["b"] * 800
        assert categorical_psi(reference, current) > settings.drift_psi_alert

    def test_empty_current_window_is_reported_not_raised(self):
        result = detect_prediction_drift(np.array([1.0, 2.0, 3.0]), np.array([]))
        assert result["status"] == "no_data"
        assert result["driftDetected"] is False

    def test_prediction_drift_reports_the_mean_shift(self):
        rng = np.random.default_rng(3)
        result = detect_prediction_drift(rng.normal(30, 10, 2000), rng.normal(60, 10, 2000))
        assert result["meanShift"] > 20


class TestAgreementRate:
    def test_full_agreement(self):
        decisions = [{"aiRecommendation": "approve", "finalDecision": "approve"}] * 10
        assert officer_agreement_rate(decisions)["agreementRate"] == pytest.approx(1.0)

    def test_mixed_agreement(self):
        decisions = (
            [{"aiRecommendation": "approve", "finalDecision": "approve"}] * 7
            + [{"aiRecommendation": "reject", "finalDecision": "approve"}] * 3
        )
        result = officer_agreement_rate(decisions)
        assert result["agreementRate"] == pytest.approx(0.7)
        assert result["overrideDirection"]["ai_reject_officer_approve"] == 3

    def test_review_recommendations_are_excluded(self):
        decisions = [
            {"aiRecommendation": "review", "finalDecision": "approve"},
            {"aiRecommendation": "approve", "finalDecision": "approve"},
        ]
        assert officer_agreement_rate(decisions)["sampleSize"] == 1

    def test_no_comparable_decisions(self):
        assert officer_agreement_rate([])["status"] == "no_data"
