"""Turns SHAP attributions into sentences a person can act on.

Two audiences, one generator: an applicant needs to know what to change, an
officer needs to know what drove the number. Templates are per-feature so the
wording stays accurate about *why* a value helped or hurt, rather than emitting
"CreditScore had a negative impact" for everything.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from src.config import FEATURE_LABELS, settings

# Feature -> (unfavourable phrasing, favourable phrasing). Each receives the
# applicant's value for that feature and returns a clause.
_Phrase = Callable[[Any], str]


def _fmt_money(value: Any) -> str:
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return "the amount provided"


def _fmt_num(value: Any, decimals: int = 0) -> str:
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return "the value provided"


TEMPLATES: Dict[str, Dict[str, _Phrase]] = {
    "CreditScore": {
        "negative": lambda v: f"a credit score of {_fmt_num(v)}, which is below the level associated with reliable repayment",
        "positive": lambda v: f"a credit score of {_fmt_num(v)}, which indicates a solid repayment record",
    },
    "DTIRatio": {
        "negative": lambda v: f"a debt-to-income ratio of {_fmt_num(v, 2)}, meaning a large share of income already services existing debt",
        "positive": lambda v: f"a manageable debt-to-income ratio of {_fmt_num(v, 2)}",
    },
    "TotalDebtServiceRatio": {
        "negative": lambda v: f"total debt payments (including this loan) consuming about {_pct(v)} of income",
        "positive": lambda v: f"total debt payments (including this loan) staying near {_pct(v)} of income",
    },
    "LoanToIncomeRatio": {
        "negative": lambda v: f"a requested amount worth {_fmt_num(v, 1)}x annual income",
        "positive": lambda v: f"a requested amount of only {_fmt_num(v, 1)}x annual income",
    },
    "InstalmentToIncomeRatio": {
        "negative": lambda v: f"a monthly instalment absorbing roughly {_pct(v)} of monthly income",
        "positive": lambda v: f"a monthly instalment of roughly {_pct(v)} of monthly income, which is comfortably affordable",
    },
    "Income": {
        "negative": lambda v: f"an annual income of {_fmt_money(v)}, which is low relative to the amount requested",
        "positive": lambda v: f"an annual income of {_fmt_money(v)} that supports the requested amount",
    },
    "LoanAmount": {
        "negative": lambda v: f"a requested amount of {_fmt_money(v)}, which is large for this profile",
        "positive": lambda v: f"a moderate requested amount of {_fmt_money(v)}",
    },
    "InterestRate": {
        "negative": lambda v: f"an offered interest rate of {_fmt_num(v, 2)}%, which raises the cost of servicing the loan",
        "positive": lambda v: f"a favourable interest rate of {_fmt_num(v, 2)}%",
    },
    "MonthsEmployed": {
        "negative": lambda v: f"only {_fmt_num(v)} months in the current job, which is a short employment history",
        "positive": lambda v: f"{_fmt_num(v)} months of continuous employment",
    },
    "EmploymentStabilityScore": {
        "negative": lambda v: "limited employment stability",
        "positive": lambda v: "a stable employment record",
    },
    "EmploymentType": {
        "negative": lambda v: f"'{v}' employment, which carries less predictable income",
        "positive": lambda v: f"'{v}' employment, which provides predictable income",
    },
    "Age": {
        "negative": lambda v: f"an age of {_fmt_num(v)}, a band that historically shows higher default rates",
        "positive": lambda v: f"an age of {_fmt_num(v)}, a band associated with stable repayment",
    },
    "AgeRiskBand": {
        "negative": lambda v: "an age band with a higher historical default rate",
        "positive": lambda v: "an age band with a lower historical default rate",
    },
    "NumCreditLines": {
        "negative": lambda v: f"{_fmt_num(v)} open credit lines, indicating obligations spread across several lenders",
        "positive": lambda v: f"a contained number of open credit lines ({_fmt_num(v)})",
    },
    "LoanTerm": {
        "negative": lambda v: f"a {_fmt_num(v)}-month term, which extends the window in which circumstances can change",
        "positive": lambda v: f"a {_fmt_num(v)}-month term that limits exposure",
    },
    "ThinFileScore": {
        "negative": lambda v: "a thin credit file, leaving little history to assess",
        "positive": lambda v: "a well-established credit file",
    },
    "AlternateDataScore": {
        "negative": lambda v: "few supporting signals outside the credit bureau record",
        "positive": lambda v: "supporting signals outside the credit bureau record, such as a serviced mortgage and stable employment",
    },
    "CollateralSupportScore": {
        "negative": lambda v: "no co-signer or secured purpose to offset the exposure",
        "positive": lambda v: "collateral or guarantor support that offsets the exposure",
    },
    "HasCoSigner": {
        "negative": lambda v: "no co-signer on the application",
        "positive": lambda v: "a co-signer supporting the application",
    },
    "HasMortgage": {
        "negative": lambda v: "no existing mortgage to evidence long-term repayment",
        "positive": lambda v: "an existing mortgage evidencing long-term repayment",
    },
    "HasDependents": {
        "negative": lambda v: "dependents adding to committed household expenditure",
        "positive": lambda v: "no dependents drawing on household income",
    },
    "CreditUtilizationProxy": {
        "negative": lambda v: "high estimated utilisation of available credit",
        "positive": lambda v: "low estimated utilisation of available credit",
    },
    "LoanPurpose": {
        "negative": lambda v: f"a '{v}' loan purpose, which carries higher historical loss rates",
        "positive": lambda v: f"a '{v}' loan purpose, which carries lower historical loss rates",
    },
    "Education": {
        "negative": lambda v: f"an education level of '{v}'",
        "positive": lambda v: f"an education level of '{v}'",
    },
    "MaritalStatus": {
        "negative": lambda v: f"a marital status of '{v}'",
        "positive": lambda v: f"a marital status of '{v}'",
    },
}


def _pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "a significant share"


def _clause(factor: Dict[str, Any]) -> str:
    raw = factor.get("rawFeature", "")
    impact = factor.get("impact", "negative")
    value = factor.get("value")

    template = TEMPLATES.get(raw, {}).get(impact)
    if template:
        return template(value)

    label = FEATURE_LABELS.get(raw, raw).lower()
    if value is None:
        return f"{label}"
    return f"{label} of {value}"


def _join(clauses: List[str]) -> str:
    if not clauses:
        return ""
    if len(clauses) == 1:
        return clauses[0]
    return ", ".join(clauses[:-1]) + " and " + clauses[-1]


def generate_explanation(
    risk_score: float,
    risk_level: str,
    probability: float,
    confidence: float,
    top_factors: List[Dict[str, Any]],
    fraud: Optional[Dict[str, Any]] = None,
    audience: str = "officer",
) -> List[str]:
    """Build the ``plainLanguageExplanation`` list the backend stores.

    Returns short standalone sentences rather than one paragraph so the frontend
    can render them as bullets in the risk report.
    """
    sentences: List[str] = []

    # -- headline ----------------------------------------------------------
    level_wording = {
        "low": "low risk",
        "medium": "moderate risk",
        "high": "high risk",
    }.get(risk_level, f"{risk_level} risk")

    sentences.append(
        f"This application scores {risk_score:.0f} out of 100 and is classified as "
        f"{level_wording}, corresponding to an estimated {probability * 100:.1f}% "
        f"probability of default."
    )

    # -- what pushed the score up -----------------------------------------
    adverse = [f for f in top_factors if f.get("impact") == "negative"][:3]
    favourable = [f for f in top_factors if f.get("impact") == "positive"][:3]

    if adverse:
        sentences.append(
            "The main factors increasing risk are " + _join([_clause(f) for f in adverse]) + "."
        )
    if favourable:
        sentences.append(
            "Working in the applicant's favour: " + _join([_clause(f) for f in favourable]) + "."
        )

    # -- confidence --------------------------------------------------------
    if confidence >= 0.85:
        sentences.append(
            f"Model confidence is high ({confidence:.0%}); the profile sits well clear of the "
            "boundaries between risk bands."
        )
    elif confidence >= 0.70:
        sentences.append(f"Model confidence is moderate ({confidence:.0%}).")
    else:
        sentences.append(
            f"Model confidence is low ({confidence:.0%}) because this profile sits close to a "
            "risk-band boundary. Manual review is recommended before acting on the score."
        )

    # -- fraud -------------------------------------------------------------
    if fraud and fraud.get("fraudFlag"):
        sentences.append(
            "Automated screening raised a data-consistency flag on this application: "
            + " ".join(fraud.get("reasons", [])[:2])
            + " This must be resolved before a decision is issued."
        )

    # -- next step ---------------------------------------------------------
    if risk_level == "low":
        sentences.append(
            f"A score below {settings.low_risk_cutoff} falls inside the automatic approval band."
        )
    elif risk_level == "high":
        sentences.append(
            f"A score at or above {settings.high_risk_cutoff} falls inside the automatic decline "
            "band; an officer may still override with documented justification."
        )
    else:
        sentences.append(
            "This score falls between the automatic approval and decline bands, so the "
            "application is routed to an officer for review."
        )

    if audience == "applicant" and adverse:
        sentences.append(
            "The most effective way to improve this assessment would be to address "
            + _clause(adverse[0]) + "."
        )

    return sentences


def generate_simulation_narrative(
    baseline_score: float, new_score: float, changed_fields: Dict[str, Any]
) -> List[str]:
    """Explain a what-if simulation relative to the original application."""
    delta = new_score - baseline_score
    changes = ", ".join(
        f"{FEATURE_LABELS.get(k, k)} -> {v}" for k, v in changed_fields.items()
    ) or "no fields"

    if abs(delta) < 0.5:
        movement = "leaves the risk score essentially unchanged"
    elif delta < 0:
        movement = f"lowers the risk score by {abs(delta):.0f} points"
    else:
        movement = f"raises the risk score by {delta:.0f} points"

    return [
        f"Adjusting {changes} {movement}, from {baseline_score:.0f} to {new_score:.0f}.",
        "This is a hypothetical projection only. It is not stored against the application "
        "and does not constitute a lending decision.",
    ]
