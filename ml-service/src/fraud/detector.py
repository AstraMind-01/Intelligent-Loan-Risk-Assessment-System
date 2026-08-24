"""Rule-based fraud screening.

Deliberately not a learned model: the dataset carries no fraud labels, so a
supervised fraud classifier would be fabricated. These are auditable
consistency rules an underwriter can defend in writing, which is what a lender
actually needs at the application-screening stage. Each rule contributes a
weighted amount to a 0-1 fraud probability and states its own reason.

Wire a labelled fraud feed into ``score_fraud`` later and the rule score becomes
one feature of a supervised model rather than the whole answer.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.config import settings
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# Fields whose exact repetition across applications indicates a resubmission.
# Income and LoanAmount are deliberately excluded: those are exactly the fields
# a resubmission may inflate, and including them in the fingerprint would let a
# changed income dodge duplicate detection instead of triggering it.
IDENTITY_FIELDS = ["Age", "EmploymentType", "MaritalStatus", "Education", "HasDependents"]


@dataclass
class FraudRule:
    code: str
    weight: float
    reason: str


class DuplicateApplicationIndex:
    """In-memory index of recently seen application fingerprints.

    A fingerprint is a hash of the applicant's stable attributes. Two
    applications sharing one within the retention window are the same person
    applying twice — legitimate when re-submitting a corrected form, suspicious
    when the financial details changed.

    Backed by a dict so the service stays dependency-free; swap for Redis when
    the ML service runs more than one replica, since this index is per-process.
    """

    def __init__(self, max_entries: int = 50_000) -> None:
        self._seen: Dict[str, Dict[str, Any]] = {}
        self.max_entries = max_entries

    @staticmethod
    def fingerprint(record: Dict[str, Any]) -> str:
        parts = [str(record.get(field, "")).strip().lower() for field in IDENTITY_FIELDS]
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]

    def check_and_register(self, record: Dict[str, Any],
                           application_id: Optional[str] = None) -> Dict[str, Any]:
        key = self.fingerprint(record)
        previous = self._seen.get(key)

        entry = {
            "application_id": application_id,
            "seen_at": datetime.now(timezone.utc).isoformat(),
            "loan_amount": record.get("LoanAmount"),
            "income": record.get("Income"),
            "count": (previous["count"] + 1) if previous else 1,
        }

        if len(self._seen) >= self.max_entries and key not in self._seen:
            self._seen.pop(next(iter(self._seen)))  # simple FIFO eviction
        self._seen[key] = entry

        if not previous:
            return {"is_duplicate": False, "occurrences": 1, "fingerprint": key}

        income_changed = _pct_change(previous.get("income"), record.get("Income"))
        amount_changed = _pct_change(previous.get("loan_amount"), record.get("LoanAmount"))
        return {
            "is_duplicate": True,
            "occurrences": entry["count"],
            "fingerprint": key,
            "previous_application_id": previous.get("application_id"),
            "previous_seen_at": previous.get("seen_at"),
            "income_change_pct": income_changed,
            "loan_amount_change_pct": amount_changed,
        }


def _pct_change(old: Any, new: Any) -> Optional[float]:
    try:
        old_val, new_val = float(old), float(new)
    except (TypeError, ValueError):
        return None
    if old_val == 0:
        return None
    return round(100.0 * (new_val - old_val) / abs(old_val), 2)


duplicate_index = DuplicateApplicationIndex()


def _consistency_rules(record: Dict[str, Any]) -> List[FraudRule]:
    """Cross-field checks: values that cannot all be true at once."""
    rules: List[FraudRule] = []

    def number(key: str, default: float = np.nan) -> float:
        try:
            value = float(record.get(key, default))
            return default if np.isnan(value) else value
        except (TypeError, ValueError):
            return default

    age = number("Age", 40)
    income = number("Income", 0)
    loan_amount = number("LoanAmount", 0)
    credit_score = number("CreditScore", 600)
    months_employed = number("MonthsEmployed", 0)
    credit_lines = number("NumCreditLines", 0)
    dti = number("DTIRatio", 0)
    employment = str(record.get("EmploymentType", "") or "")

    # --- income vs. employment -------------------------------------------
    if employment == "Unemployed" and income > 75_000:
        rules.append(FraudRule(
            "INCOME_EMPLOYMENT_MISMATCH", 0.35,
            f"Declared income of {income:,.0f} is inconsistent with 'Unemployed' employment status.",
        ))
    if employment == "Part-time" and income > 120_000:
        rules.append(FraudRule(
            "INCOME_EMPLOYMENT_MISMATCH", 0.20,
            f"Declared income of {income:,.0f} is unusually high for part-time employment.",
        ))

    # --- tenure vs. age ---------------------------------------------------
    working_months_available = max((age - 16.0) * 12.0, 0.0)
    if months_employed > working_months_available:
        rules.append(FraudRule(
            "TENURE_EXCEEDS_AGE", 0.40,
            f"Employment tenure of {months_employed:.0f} months is impossible for an applicant aged {age:.0f}.",
        ))

    # --- credit file vs. age ---------------------------------------------
    if age < 22 and credit_lines >= 4:
        rules.append(FraudRule(
            "CREDIT_HISTORY_AGE_MISMATCH", 0.25,
            f"{credit_lines:.0f} open credit lines is atypical for an applicant aged {age:.0f}.",
        ))
    if age < 21 and credit_score > 780:
        rules.append(FraudRule(
            "CREDIT_SCORE_AGE_MISMATCH", 0.30,
            f"A credit score of {credit_score:.0f} is not attainable with the credit history "
            f"length available to an applicant aged {age:.0f}.",
        ))

    # --- affordability ----------------------------------------------------
    if income > 0 and loan_amount / income > 8:
        rules.append(FraudRule(
            "IMPLAUSIBLE_LOAN_TO_INCOME", 0.25,
            f"Requested amount is {loan_amount / income:.1f}x declared annual income.",
        ))
    if income <= 0 and loan_amount > 0:
        rules.append(FraudRule(
            "ZERO_INCOME_WITH_LOAN_REQUEST", 0.35,
            "A loan is requested against zero declared income.",
        ))

    # --- internal contradiction ------------------------------------------
    if dti > 0.85 and credit_score > 760:
        rules.append(FraudRule(
            "DTI_CREDIT_SCORE_CONTRADICTION", 0.20,
            f"A debt-to-income ratio of {dti:.2f} is not consistent with a credit score of {credit_score:.0f}.",
        ))
    if credit_lines == 0 and credit_score > 720:
        rules.append(FraudRule(
            "SCORE_WITHOUT_CREDIT_FILE", 0.25,
            f"A credit score of {credit_score:.0f} is reported with no open credit lines.",
        ))

    # --- round-number heuristic ------------------------------------------
    # Fabricated figures are far more likely to be exactly round than real ones.
    if income > 0 and income % 10_000 == 0 and loan_amount > 0 and loan_amount % 10_000 == 0:
        rules.append(FraudRule(
            "SUSPICIOUSLY_ROUND_FIGURES", 0.10,
            "Both income and loan amount are exact multiples of 10,000.",
        ))

    return rules


def score_fraud(record: Dict[str, Any], application_id: Optional[str] = None,
                check_duplicates: bool = True) -> Dict[str, Any]:
    """Screen a single application and return a flag, score and reasons."""
    rules = _consistency_rules(record)

    duplicate_info: Dict[str, Any] = {"is_duplicate": False}
    if check_duplicates:
        duplicate_info = duplicate_index.check_and_register(record, application_id)
        if duplicate_info["is_duplicate"]:
            occurrences = duplicate_info["occurrences"]
            income_delta = duplicate_info.get("income_change_pct")
            # A resubmission with materially inflated income is the strongest
            # single signal in this rule set.
            if income_delta is not None and income_delta > 20:
                rules.append(FraudRule(
                    "DUPLICATE_WITH_INFLATED_INCOME", 0.55,
                    f"An application with matching applicant details was already submitted, "
                    f"with declared income {income_delta:.0f}% lower.",
                ))
            else:
                rules.append(FraudRule(
                    "DUPLICATE_APPLICATION", 0.25 if occurrences == 2 else 0.40,
                    f"Matching applicant details were seen in {occurrences - 1} previous "
                    f"application(s).",
                ))

    # Combine weights so that no single rule saturates the score, but several
    # weak signals together still clear the threshold.
    combined_miss = float(np.prod([1.0 - rule.weight for rule in rules])) if rules else 1.0
    fraud_probability = round(1.0 - combined_miss, 4)
    fraud_flag = fraud_probability >= settings.fraud_score_threshold

    reasons = [rule.reason for rule in rules]
    return {
        "fraudFlag": bool(fraud_flag),
        "fraudProbability": fraud_probability,
        "reason": (" ".join(reasons) if fraud_flag else None),
        "reasons": reasons,
        "triggeredRules": [
            {"code": rule.code, "weight": rule.weight, "reason": rule.reason} for rule in rules
        ],
        "duplicateCheck": duplicate_info,
        "threshold": settings.fraud_score_threshold,
        "riskTier": (
            "high" if fraud_probability >= 0.55
            else "medium" if fraud_probability >= 0.25
            else "low"
        ),
    }


def score_fraud_batch(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Screen a batch, including duplicates *within* the batch itself."""
    results = []
    for index, record in enumerate(records):
        results.append(score_fraud(record, application_id=f"batch-{index}"))
    return results


def detect_duplicates_in_frame(df: pd.DataFrame) -> Dict[str, Any]:
    """Find applications inside one dataframe that share an identity fingerprint."""
    available = [field for field in IDENTITY_FIELDS if field in df.columns]
    if not available:
        return {"duplicate_groups": 0, "duplicate_rows": 0, "groups": []}

    keys = df[available].astype(str).agg("|".join, axis=1)
    counts = keys.value_counts()
    duplicated = counts[counts > 1]

    groups = [
        {"fingerprint": hashlib.sha256(key.encode()).hexdigest()[:16],
         "row_indices": df.index[keys == key].tolist()[:20],
         "occurrences": int(count)}
        for key, count in duplicated.head(50).items()
    ]
    return {
        "duplicate_groups": int(len(duplicated)),
        "duplicate_rows": int(duplicated.sum()),
        "groups": groups,
    }
