"""API endpoint tests.

Endpoints that need a trained model are skipped when the registry is empty, so
the suite still runs on a fresh checkout. Run the training script first for full
coverage.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app
from src.models import registry

client = TestClient(app)

requires_model = pytest.mark.skipif(
    registry.get_active_version() is None,
    reason="No trained model registered; run `python scripts/train_model.py` first.",
)


# ---------------------------------------------------------------------------
# Always available
# ---------------------------------------------------------------------------
class TestServiceEndpoints:
    def test_health_is_always_up(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_root_lists_the_endpoints(self):
        body = client.get("/").json()
        assert "POST /predict" in body["endpoints"]

    def test_openapi_schema_is_generated(self):
        assert client.get("/openapi.json").status_code == 200

    def test_model_health_answers_even_without_a_model(self):
        response = client.get("/model-health")
        assert response.status_code == 200
        assert "status" in response.json()

    def test_registry_listing(self):
        response = client.get("/models")
        assert response.status_code == 200
        assert "versions" in response.json()

    def test_unknown_model_version_is_404(self):
        assert client.get("/models/v-does-not-exist").status_code == 404


class TestFraudEndpoint:
    """Fraud screening is rule-based, so it works without a trained model."""

    def test_clean_application_passes(self, sample_application):
        response = client.post("/fraud-check", json={
            "application": sample_application, "checkDuplicates": False,
        })
        assert response.status_code == 200
        body = response.json()
        assert body["fraudFlag"] is False
        assert 0.0 <= body["fraudProbability"] <= 1.0

    def test_contradictory_application_is_flagged_with_reasons(self):
        response = client.post("/fraud-check", json={
            "application": {
                "Age": 19, "Income": 130_000, "EmploymentType": "Unemployed",
                "MonthsEmployed": 180, "CreditScore": 830, "NumCreditLines": 4,
                "LoanAmount": 240_000,
            },
            "checkDuplicates": False,
        })
        body = response.json()
        assert body["fraudFlag"] is True
        assert body["reason"]
        assert len(body["triggeredRules"]) > 0

    def test_bare_application_at_the_top_level_is_accepted(self, backend_application):
        response = client.post("/fraud-check", json=backend_application)
        assert response.status_code == 200

    def test_empty_body_is_rejected(self):
        assert client.post("/fraud-check", json={}).status_code == 422


# ---------------------------------------------------------------------------
# Require a trained model
# ---------------------------------------------------------------------------
@requires_model
class TestPredictEndpoint:
    def test_returns_the_backend_contract(self, backend_application):
        response = client.post("/predict", json={"application": backend_application})
        assert response.status_code == 200
        body = response.json()

        for field in ("riskScore", "riskLevel", "confidenceScore", "topFactors",
                      "plainLanguageExplanation", "fraudFlag", "modelVersion"):
            assert field in body, field

    def test_score_is_within_zero_and_one_hundred(self, backend_application):
        body = client.post("/predict", json={"application": backend_application}).json()
        assert 0 <= body["riskScore"] <= 100

    def test_risk_level_is_one_of_three_values(self, backend_application):
        body = client.post("/predict", json={"application": backend_application}).json()
        assert body["riskLevel"] in ("low", "medium", "high")

    def test_confidence_is_a_probability(self, backend_application):
        body = client.post("/predict", json={"application": backend_application}).json()
        assert 0.0 <= body["confidenceScore"] <= 1.0

    def test_risk_level_agrees_with_the_score(self, backend_application):
        from src.config import settings

        body = client.post("/predict", json={"application": backend_application}).json()
        score, level = body["riskScore"], body["riskLevel"]
        if level == "low":
            assert score < settings.low_risk_cutoff
        elif level == "high":
            assert score >= settings.high_risk_cutoff
        else:
            assert settings.low_risk_cutoff <= score < settings.high_risk_cutoff

    def test_top_factors_match_the_backend_subdocument(self, backend_application):
        body = client.post("/predict", json={"application": backend_application}).json()
        assert len(body["topFactors"]) > 0
        for factor in body["topFactors"]:
            assert factor["impact"] in ("positive", "negative")
            assert isinstance(factor["description"], str) and factor["description"]
            assert 0.0 <= factor["weight"] <= 1.0

    def test_explanation_is_a_list_of_sentences(self, backend_application):
        body = client.post("/predict", json={"application": backend_application}).json()
        assert isinstance(body["plainLanguageExplanation"], list)
        assert all(isinstance(s, str) and s for s in body["plainLanguageExplanation"])

    def test_bare_application_at_the_top_level_is_accepted(self, backend_application):
        assert client.post("/predict", json=backend_application).status_code == 200

    def test_imputed_fields_are_reported(self, backend_application):
        body = client.post("/predict", json={"application": backend_application}).json()
        assert "InterestRate" in body["imputedFields"]

    def test_a_weak_profile_scores_worse_than_a_strong_one(self):
        strong = client.post("/predict", json={"application": {
            "Age": 45, "Income": 145_000, "LoanAmount": 20_000, "CreditScore": 830,
            "MonthsEmployed": 115, "NumCreditLines": 2, "InterestRate": 3.5,
            "LoanTerm": 12, "DTIRatio": 0.12, "Education": "PhD",
            "EmploymentType": "Full-time", "MaritalStatus": "Married",
            "HasMortgage": "Yes", "HasDependents": "No", "LoanPurpose": "Home",
            "HasCoSigner": "Yes",
        }}).json()

        weak = client.post("/predict", json={"application": {
            "Age": 22, "Income": 18_000, "LoanAmount": 240_000, "CreditScore": 320,
            "MonthsEmployed": 2, "NumCreditLines": 4, "InterestRate": 24.5,
            "LoanTerm": 60, "DTIRatio": 0.88, "Education": "High School",
            "EmploymentType": "Unemployed", "MaritalStatus": "Single",
            "HasMortgage": "No", "HasDependents": "Yes", "LoanPurpose": "Other",
            "HasCoSigner": "No",
        }}).json()

        assert weak["riskScore"] > strong["riskScore"]

    def test_scoring_is_deterministic(self, backend_application):
        first = client.post("/predict", json={"application": backend_application}).json()
        second = client.post("/predict", json={"application": backend_application}).json()
        assert first["riskScore"] == second["riskScore"]

    def test_explanation_can_be_switched_off(self, backend_application):
        body = client.post("/predict", json={
            "application": backend_application, "includeExplanation": False,
        }).json()
        assert body["topFactors"] == []

    def test_empty_application_is_rejected(self):
        assert client.post("/predict", json={"application": {}}).status_code == 422

    def test_out_of_range_credit_score_is_rejected(self):
        response = client.post("/predict", json={
            "application": {"Age": 40, "CreditScore": 5000, "Income": 50_000},
        })
        assert response.status_code == 422

    def test_underage_applicant_is_rejected(self):
        response = client.post("/predict", json={"application": {"Age": 12, "Income": 50_000}})
        assert response.status_code == 422

    def test_partial_application_still_scores(self):
        response = client.post("/predict", json={
            "application": {"Age": 35, "Income": 60_000, "LoanAmount": 50_000},
        })
        assert response.status_code == 200
        assert 0 <= response.json()["riskScore"] <= 100


@requires_model
class TestBatchEndpoint:
    def test_scores_every_application(self, backend_application, sample_application):
        response = client.post("/predict/batch", json={
            "applications": [backend_application, sample_application, sample_application],
        })
        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 3
        assert len(body["predictions"]) == 3

    def test_all_batch_scores_are_bounded(self, sample_application):
        body = client.post("/predict/batch", json={
            "applications": [sample_application] * 20,
        }).json()
        assert all(0 <= p["riskScore"] <= 100 for p in body["predictions"])

    def test_summary_counts_add_up(self, sample_application):
        body = client.post("/predict/batch", json={
            "applications": [sample_application] * 10,
        }).json()
        assert sum(body["summary"]["riskLevelCounts"].values()) == 10

    def test_batch_matches_single_prediction(self, sample_application):
        single = client.post("/predict", json={"application": sample_application}).json()
        batch = client.post("/predict/batch", json={"applications": [sample_application]}).json()
        assert batch["predictions"][0]["riskScore"] == pytest.approx(single["riskScore"], abs=0.01)

    def test_empty_batch_is_rejected(self):
        assert client.post("/predict/batch", json={"applications": []}).status_code == 422


@requires_model
class TestExplainEndpoint:
    def test_returns_contributions_and_narrative(self, backend_application):
        response = client.post("/explain", json={"application": backend_application})
        assert response.status_code == 200
        body = response.json()
        assert body["featureContributions"]
        assert body["plainLanguageExplanation"]

    def test_factor_weights_are_normalised(self, backend_application):
        body = client.post("/explain", json={"application": backend_application}).json()
        assert all(0.0 <= f["weight"] <= 1.0 for f in body["topFactors"])

    def test_factors_are_ordered_by_influence(self, backend_application):
        body = client.post("/explain", json={"application": backend_application}).json()
        weights = [f["weight"] for f in body["topFactors"]]
        assert weights == sorted(weights, reverse=True)

    def test_top_k_is_respected(self, backend_application):
        body = client.post("/explain", json={
            "application": backend_application, "topFactors": 3,
        }).json()
        assert len(body["topFactors"]) == 3

    def test_global_importance_endpoint(self):
        response = client.get("/explain/global?topK=10")
        assert response.status_code == 200
        assert len(response.json()["featureImportance"]) <= 10


@requires_model
class TestSimulateEndpoint:
    def test_returns_baseline_simulated_and_delta(self, backend_application):
        response = client.post("/simulate", json={
            "application": backend_application, "adjustments": {"CreditScore": 780},
        })
        assert response.status_code == 200
        body = response.json()
        assert {"baseline", "simulated", "delta"} <= set(body)

    def test_nothing_is_persisted(self, backend_application):
        body = client.post("/simulate", json={
            "application": backend_application, "adjustments": {"CreditScore": 780},
        }).json()
        assert body["persisted"] is False

    def test_a_better_credit_score_lowers_risk(self, backend_application):
        body = client.post("/simulate", json={
            "application": {**backend_application, "CreditScore": 480},
            "adjustments": {"CreditScore": 820},
        }).json()
        assert body["simulated"]["riskScore"] <= body["baseline"]["riskScore"]

    def test_no_adjustments_leaves_the_score_unchanged(self, backend_application):
        body = client.post("/simulate", json={
            "application": backend_application, "adjustments": {},
        }).json()
        assert body["delta"]["riskScoreChange"] == pytest.approx(0.0, abs=0.01)

    def test_simulated_score_is_bounded(self, backend_application):
        body = client.post("/simulate", json={
            "application": backend_application, "adjustments": {"LoanAmount": 10_000_000},
        })
        # An out-of-range adjustment must not produce an out-of-range score.
        if body.status_code == 200:
            assert 0 <= body.json()["simulated"]["riskScore"] <= 100


@requires_model
class TestFairnessEndpoint:
    def test_returns_a_report(self, sample_application):
        applications = [
            {**sample_application, "Age": age, "MaritalStatus": status}
            for age in (25, 35, 45, 55, 65)
            for status in ("Single", "Married", "Divorced")
            for _ in range(4)
        ]
        response = client.post("/fairness-check", json={"applications": applications})
        assert response.status_code == 200
        body = response.json()
        assert body["n_applications"] == len(applications)
        assert "attributes" in body and "bias_alert" in body

    def test_a_single_application_is_rejected(self, sample_application):
        response = client.post("/fairness-check", json={"applications": [sample_application]})
        assert response.status_code == 422

    def test_mismatched_outcomes_are_rejected(self, sample_application):
        response = client.post("/fairness-check", json={
            "applications": [sample_application] * 4, "outcomes": [0, 1],
        })
        assert response.status_code == 422


@requires_model
class TestMonitoringEndpoints:
    def test_model_health_reports_a_loaded_model(self):
        body = client.get("/model-health").json()
        assert body["modelLoaded"] is True
        assert body["modelVersion"]
        assert body["metrics"]["aucRoc"] is not None

    def test_drift_endpoint_responds(self):
        response = client.get("/monitoring/drift?window=100")
        assert response.status_code == 200
        assert "status" in response.json()

    def test_performance_endpoint_responds(self):
        assert client.get("/monitoring/performance").status_code == 200

    def test_agreement_endpoint(self):
        response = client.post("/monitoring/agreement", json={"decisions": [
            {"aiRecommendation": "approve", "finalDecision": "approve"},
            {"aiRecommendation": "reject", "finalDecision": "approve"},
        ]})
        assert response.json()["agreementRate"] == pytest.approx(0.5)

    def test_retrain_status_lists_triggers(self):
        body = client.get("/retrain/status").json()
        assert "triggers" in body and "jobs" in body
