"""Domain feature engineering for loan risk.

Every function here is stateless and deterministic: the exact same transform runs
during training and at inference time, which removes a whole class of
train/serve skew bugs. Nothing in this module learns from data — anything that
needs fitting (imputation, scaling, encoding) lives in preprocessing.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import ENGINEERED_CATEGORICAL, ENGINEERED_NUMERIC

# Age bands used for both risk scoring and the fairness audit.
AGE_BINS = [0, 25, 35, 50, 65, 200]
AGE_LABELS = ["18-25", "26-35", "36-50", "51-65", "65+"]

# Relative default propensity by age band, from credit-risk literature: young
# borrowers have thin files, near-retirement borrowers face income cliffs.
AGE_RISK_WEIGHTS = {"18-25": 1.00, "26-35": 0.55, "36-50": 0.35, "51-65": 0.45, "65+": 0.70}

# FICO-style bands, expressed as an ordinal so trees can split on them cheaply.
CREDIT_BINS = [0, 500, 580, 670, 740, 800, 900]
CREDIT_BAND_ORDINALS = [0, 1, 2, 3, 4, 5]  # 0 = deep subprime, 5 = exceptional

EDUCATION_RANK = {"High School": 0, "Bachelor's": 1, "Master's": 2, "PhD": 3}
EMPLOYMENT_STABILITY = {"Full-time": 1.0, "Self-employed": 0.6, "Part-time": 0.45, "Unemployed": 0.0}

_EPS = 1e-9


def _safe_divide(numerator: pd.Series, denominator: pd.Series, fill: float = 0.0) -> pd.Series:
    """Element-wise division that returns ``fill`` instead of inf/NaN."""
    result = numerator / denominator.replace(0, np.nan)
    return result.replace([np.inf, -np.inf], np.nan).fillna(fill)


def monthly_instalment(principal: pd.Series, annual_rate_pct: pd.Series,
                       term_months: pd.Series) -> pd.Series:
    """Amortised monthly payment for a fixed-rate instalment loan.

    Falls back to straight-line repayment when the rate is zero or missing.
    """
    principal = pd.to_numeric(principal, errors="coerce").fillna(0.0)
    rate = pd.to_numeric(annual_rate_pct, errors="coerce").fillna(0.0) / 100.0 / 12.0
    term = pd.to_numeric(term_months, errors="coerce").fillna(0.0).clip(lower=1)

    straight_line = principal / term
    with np.errstate(over="ignore", invalid="ignore"):
        growth = np.power(1.0 + rate, term)
        amortised = principal * rate * growth / (growth - 1.0)

    payment = pd.Series(
        np.where(rate.to_numpy() > _EPS, amortised, straight_line),
        index=principal.index,
        dtype="float64",
    )
    return payment.replace([np.inf, -np.inf], np.nan).fillna(straight_line).clip(lower=0.0)


def add_engineered_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of ``df`` with all engineered columns appended."""
    out = df.copy()

    num = lambda col, default=np.nan: pd.to_numeric(  # noqa: E731
        out[col], errors="coerce") if col in out.columns else pd.Series(default, index=out.index, dtype="float64")

    income = num("Income")
    loan_amount = num("LoanAmount")
    credit_score = num("CreditScore")
    months_employed = num("MonthsEmployed")
    credit_lines = num("NumCreditLines")
    interest_rate = num("InterestRate")
    loan_term = num("LoanTerm")
    dti = num("DTIRatio")
    age = num("Age")

    # -- affordability -----------------------------------------------------
    out["LoanToIncomeRatio"] = _safe_divide(loan_amount, income).clip(0, 50)

    instalment = monthly_instalment(loan_amount, interest_rate, loan_term)
    out["MonthlyInstalment"] = instalment
    monthly_income = income / 12.0
    out["InstalmentToIncomeRatio"] = _safe_divide(instalment, monthly_income).clip(0, 20)

    # Existing obligations (DTIRatio) plus the payment being applied for. This is
    # the number an underwriter actually cares about.
    out["TotalDebtServiceRatio"] = (dti.fillna(0.0) + out["InstalmentToIncomeRatio"]).clip(0, 20)

    # -- credit profile ----------------------------------------------------
    # True revolving utilisation needs balance/limit data the dataset does not
    # carry, so this is an explicit proxy: existing debt burden spread over the
    # number of open lines. Documented as a proxy so nobody mistakes it for the
    # bureau field of the same name.
    out["CreditUtilizationProxy"] = _safe_divide(dti, credit_lines.clip(lower=1)).clip(0, 5)

    out["CreditScoreBandOrdinal"] = pd.cut(
        credit_score, bins=CREDIT_BINS, labels=CREDIT_BAND_ORDINALS, right=False
    ).astype("float64")

    # Opening many lines early in adult life is a known distress signal.
    adult_years = (age - 18).clip(lower=1)
    out["CreditLinesPerYearOfAge"] = _safe_divide(credit_lines, adult_years).clip(0, 5)

    out["InterestBurden"] = (loan_amount * interest_rate / 100.0).fillna(0.0)

    # -- employment stability ---------------------------------------------
    # Saturating curve: tenure matters a lot up to ~5 years, then plateaus.
    tenure_component = 1.0 - np.exp(-months_employed.fillna(0.0) / 36.0)
    type_component = (
        out["EmploymentType"].map(EMPLOYMENT_STABILITY)
        if "EmploymentType" in out.columns
        else pd.Series(np.nan, index=out.index)
    ).astype("float64").fillna(0.5)
    out["EmploymentStabilityScore"] = (0.6 * tenure_component + 0.4 * type_component).clip(0, 1)

    # -- age banding -------------------------------------------------------
    age_group = pd.cut(age, bins=AGE_BINS, labels=AGE_LABELS, right=True)
    out["AgeGroup"] = age_group.astype(object)
    out["AgeRiskBand"] = age_group.map(AGE_RISK_WEIGHTS).astype("float64")

    # -- income banding ----------------------------------------------------
    # Fixed cut points (not data-dependent quantiles) so the transform stays
    # stateless and a single-row inference call bands identically to training.
    out["IncomeQuartileBand"] = pd.cut(
        income,
        bins=[-np.inf, 40_000, 75_000, 115_000, np.inf],
        labels=["low", "lower-mid", "upper-mid", "high"],
    ).astype(object)

    # -- thin-file / alternate data ---------------------------------------
    # Applicants with little bureau history get scored mostly on alternate
    # signals. ThinFileScore is 1.0 for the thinnest files.
    line_thinness = (1.0 - (credit_lines.fillna(0.0) / 4.0)).clip(0, 1)
    tenure_thinness = (1.0 - (months_employed.fillna(0.0) / 120.0)).clip(0, 1)
    youth = ((30.0 - age.fillna(45.0)) / 12.0).clip(0, 1)
    out["ThinFileScore"] = (0.4 * line_thinness + 0.35 * tenure_thinness + 0.25 * youth).clip(0, 1)

    # Alternate-data stand-ins available in this dataset: a serviced mortgage is
    # a de-facto repayment-history signal, stable employment is an income
    # signal, education correlates with earnings trajectory. When a richer
    # alternate feed (utility bills, transaction patterns) is connected, extend
    # this term rather than the model's feature list.
    # Fallbacks are Series, not bare floats: when every column feeding an
    # expression is absent, a bare-float fallback collapses the whole
    # expression to a scalar and ``.clip()`` on a plain float raises.
    zeros = pd.Series(0.0, index=out.index)
    has_mortgage = (out["HasMortgage"] == "Yes").astype(float) if "HasMortgage" in out.columns else zeros
    education_rank = (
        out["Education"].map(EDUCATION_RANK) if "Education" in out.columns else pd.Series(np.nan, index=out.index)
    ).astype("float64").fillna(1.0) / 3.0
    out["AlternateDataScore"] = (
        0.40 * has_mortgage
        + 0.35 * out["EmploymentStabilityScore"]
        + 0.25 * education_rank
    ).clip(0, 1)

    # -- collateral / guarantor -------------------------------------------
    has_cosigner = (out["HasCoSigner"] == "Yes").astype(float) if "HasCoSigner" in out.columns else zeros
    secured_purpose = (
        out["LoanPurpose"].isin(["Home", "Auto"]).astype(float)
        if "LoanPurpose" in out.columns else zeros
    )
    out["CollateralSupportScore"] = (
        0.45 * has_cosigner + 0.35 * secured_purpose + 0.20 * has_mortgage
    ).clip(0, 1)

    # Guarantee every declared engineered column exists, even for odd inputs.
    for col in ENGINEERED_NUMERIC:
        if col not in out.columns:
            out[col] = np.nan
        out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in ENGINEERED_CATEGORICAL:
        if col not in out.columns:
            out[col] = np.nan

    return out
