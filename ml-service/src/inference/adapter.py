"""Translates backend application payloads into the model's feature schema.

The Node backend stores applications as ``{personalInfo, financialInfo}`` with
snake_case enums, while the model was trained on the raw dataset's column names
and label spellings. This module is the single place that reconciles the two, so
the mapping is reviewable rather than scattered through the serving code.

Three payload shapes are accepted:
  1. Backend shape  - {"personalInfo": {...}, "financialInfo": {...}}
  2. Canonical shape - {"Age": 45, "Income": 80000, ...} (raw dataset names)
  3. Flat camelCase  - {"age": 45, "income": 80000, ...}

Canonical keys always win, which lets a caller override any derived value.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np

from src.config import BASE_FEATURES
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Enum translation
# ---------------------------------------------------------------------------
EDUCATION_MAP = {
    "high_school": "High School",
    "bachelors": "Bachelor's",
    "masters": "Master's",
    "doctorate": "PhD",
    "other": None,  # unknown -> imputed from the training mode
}

# 'contract' maps to Self-employed: both are engagement-based income without an
# employer guarantee. 'retired' maps to Part-time: reduced but non-zero, usually
# fixed, income. Neither has an exact equivalent in the training data, so both
# are approximations recorded here rather than silently coded elsewhere.
EMPLOYMENT_MAP = {
    "full_time": "Full-time",
    "part_time": "Part-time",
    "self_employed": "Self-employed",
    "contract": "Self-employed",
    "retired": "Part-time",
    "unemployed": "Unemployed",
}

# 'widowed' maps to Divorced: the training data has no widowed level, and both
# describe a previously-married single-income household.
MARITAL_MAP = {
    "single": "Single",
    "married": "Married",
    "divorced": "Divorced",
    "widowed": "Divorced",
}

PURPOSE_MAP = {
    "home_purchase": "Home",
    "auto_loan": "Auto",
    "education": "Education",
    "business": "Business",
    "personal": "Other",
    "debt_consolidation": "Other",
    "medical": "Other",
    "other": "Other",
}

# Flat camelCase aliases accepted for convenience.
CAMEL_ALIASES = {
    "age": "Age",
    "income": "Income",
    "annualIncome": "Income",
    "loanAmount": "LoanAmount",
    "loanAmountRequested": "LoanAmount",
    "creditScore": "CreditScore",
    "monthsEmployed": "MonthsEmployed",
    "employmentMonths": "MonthsEmployed",
    "numCreditLines": "NumCreditLines",
    "creditLines": "NumCreditLines",
    "interestRate": "InterestRate",
    "loanTerm": "LoanTerm",
    "tenure": "LoanTerm",
    "dtiRatio": "DTIRatio",
    "education": "Education",
    "employmentType": "EmploymentType",
    "maritalStatus": "MaritalStatus",
    "hasMortgage": "HasMortgage",
    "hasDependents": "HasDependents",
    "loanPurpose": "LoanPurpose",
    "purpose": "LoanPurpose",
    "hasCoSigner": "HasCoSigner",
}

# Canonical values that may arrive already correctly spelled.
_CANONICAL_EDUCATION = {"High School", "Bachelor's", "Master's", "PhD"}
_CANONICAL_EMPLOYMENT = {"Full-time", "Part-time", "Self-employed", "Unemployed"}
_CANONICAL_MARITAL = {"Single", "Married", "Divorced"}
_CANONICAL_PURPOSE = {"Auto", "Business", "Education", "Home", "Other"}


def _yes_no(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("yes", "true", "y", "1"):
            return "Yes"
        if lowered in ("no", "false", "n", "0"):
            return "No"
        return None
    return "Yes" if bool(value) else "No"


def _lookup(value: Any, mapping: Dict[str, Optional[str]],
            canonical: set) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if text in canonical:
        return text
    return mapping.get(text.lower())


def _number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(result) else result


def derive_dti(existing_debts: Optional[float], income: Optional[float],
               explicit: Optional[float] = None) -> Optional[float]:
    """Estimate the debt-to-income ratio the model was trained on.

    The backend records ``existingDebts`` as an outstanding balance, whereas the
    training column is a ratio in [0.1, 0.9]. Dividing the balance by annual
    income is the standard back-of-envelope conversion; it is an approximation,
    and an explicit ``DTIRatio`` on the payload always takes precedence.
    """
    if explicit is not None:
        return float(np.clip(explicit, 0.0, 1.5))
    if not existing_debts or not income or income <= 0:
        return None
    return float(np.clip(existing_debts / income, 0.0, 1.5))


def normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a canonical single-application record.

    Fields that cannot be derived are left as ``None`` and filled downstream by
    the fitted imputer, so a partial application still receives a score.
    """
    record: Dict[str, Any] = {name: None for name in BASE_FEATURES}

    personal = payload.get("personalInfo") or {}
    financial = payload.get("financialInfo") or {}

    # -- 1. backend nested shape ------------------------------------------
    if personal or financial:
        record["Age"] = _number(personal.get("age"))
        record["Education"] = _lookup(personal.get("education"), EDUCATION_MAP, _CANONICAL_EDUCATION)
        record["EmploymentType"] = _lookup(
            personal.get("employmentType"), EMPLOYMENT_MAP, _CANONICAL_EMPLOYMENT
        )
        record["MaritalStatus"] = _lookup(
            personal.get("maritalStatus"), MARITAL_MAP, _CANONICAL_MARITAL
        )

        dependents = personal.get("dependents")
        if dependents is not None:
            record["HasDependents"] = "Yes" if _number(dependents) else "No"

        record["Income"] = _number(financial.get("income"))
        record["LoanAmount"] = _number(financial.get("loanAmountRequested"))
        record["CreditScore"] = _number(financial.get("creditScore"))
        record["LoanTerm"] = _number(financial.get("tenure"))
        record["LoanPurpose"] = _lookup(financial.get("purpose"), PURPOSE_MAP, _CANONICAL_PURPOSE)
        record["DTIRatio"] = derive_dti(
            _number(financial.get("existingDebts")),
            _number(financial.get("income")),
            _number(financial.get("dtiRatio")),
        )

    # -- 2. flat camelCase aliases ----------------------------------------
    for alias, canonical_name in CAMEL_ALIASES.items():
        if alias in payload and payload[alias] is not None:
            record[canonical_name] = payload[alias]

    # -- 3. canonical names win -------------------------------------------
    for name in BASE_FEATURES:
        if name in payload and payload[name] is not None:
            record[name] = payload[name]

    # -- coerce to the training vocabulary --------------------------------
    for name in ("Age", "Income", "LoanAmount", "CreditScore", "MonthsEmployed",
                 "NumCreditLines", "InterestRate", "LoanTerm", "DTIRatio"):
        record[name] = _number(record[name])

    record["Education"] = _lookup(record["Education"], EDUCATION_MAP, _CANONICAL_EDUCATION)
    record["EmploymentType"] = _lookup(record["EmploymentType"], EMPLOYMENT_MAP, _CANONICAL_EMPLOYMENT)
    record["MaritalStatus"] = _lookup(record["MaritalStatus"], MARITAL_MAP, _CANONICAL_MARITAL)
    record["LoanPurpose"] = _lookup(record["LoanPurpose"], PURPOSE_MAP, _CANONICAL_PURPOSE)
    for name in ("HasMortgage", "HasDependents", "HasCoSigner"):
        record[name] = _yes_no(record[name])

    # The backend never collects employment tenure (it's not a field on
    # LoanApplication.financialInfo), so MonthsEmployed is imputed to the
    # training population's median for every applicant regardless of
    # employment status. Left alone, that quietly credits an unemployed
    # applicant with a typical multi-year tenure. Someone cannot be both
    # unemployed and have months of current-job tenure, so this only forces
    # the value when the caller didn't explicitly supply one themselves.
    if record["EmploymentType"] == "Unemployed" and record["MonthsEmployed"] is None:
        record["MonthsEmployed"] = 0.0

    return record


def imputed_field_names(record: Dict[str, Any]) -> list[str]:
    """Fields the caller did not supply, which the model will impute.

    Surfaced on the API response so an officer can see the score rests partly on
    population averages rather than this applicant's own data.
    """
    return [name for name in BASE_FEATURES if record.get(name) is None]
