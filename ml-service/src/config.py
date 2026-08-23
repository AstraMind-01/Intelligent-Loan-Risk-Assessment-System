"""Central configuration for the ML service.

Everything tunable lives here: paths, feature lists, risk thresholds, fairness
limits and drift limits. Values can be overridden from the environment (.env),
so the same image runs in dev and prod without code changes.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SERVICE_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = SERVICE_ROOT.parent


class Settings(BaseSettings):
    """Runtime settings, overridable via environment variables or .env."""

    model_config = SettingsConfigDict(
        env_file=str(SERVICE_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    # -- service -----------------------------------------------------------
    app_name: str = "loan-risk-ml-service"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # -- storage -----------------------------------------------------------
    data_dir: Path = SERVICE_ROOT / "data"
    raw_data_dir: Path = SERVICE_ROOT / "data" / "raw"
    processed_data_dir: Path = SERVICE_ROOT / "data" / "processed"
    registry_dir: Path = SERVICE_ROOT / "models"
    log_dir: Path = SERVICE_ROOT / "logs"

    # Real Home Credit Default Risk source tables (application_train.csv,
    # bureau.csv, etc.) — see src/data/home_credit.py for how these are
    # aggregated into the canonical schema.
    home_credit_dir: Path = SERVICE_ROOT / "data" / "raw" / "home-credit"

    # Optional override: an explicit flat CSV in the canonical schema,
    # already-transformed rather than the raw Home Credit tables. Used by the
    # retraining pipeline, which merges realised outcomes into a canonical
    # CSV and retrains from that rather than re-touching the source tables.
    raw_dataset_path: Optional[Path] = None

    # -- training ----------------------------------------------------------
    random_seed: int = 42
    test_size: float = 0.15
    val_size: float = 0.15
    cv_folds: int = 5
    # "class_weight" keeps probabilities calibrated; "smote" oversamples the
    # minority class. See docs/imbalance note in README.
    imbalance_strategy: str = "class_weight"
    tuning_iterations: int = 25

    # -- risk banding ------------------------------------------------------
    # riskScore is 0-100, higher = riskier. These must stay in sync with the
    # backend's AUTO_APPROVE_THRESHOLD / AUTO_REJECT_THRESHOLD.
    low_risk_cutoff: int = 25
    high_risk_cutoff: int = 75

    # -- fraud -------------------------------------------------------------
    fraud_score_threshold: float = 0.55

    # -- fairness ----------------------------------------------------------
    # Four-fifths rule: a disparate impact ratio below this triggers an alert.
    disparate_impact_floor: float = 0.80
    demographic_parity_tolerance: float = 0.10

    # -- monitoring --------------------------------------------------------
    drift_psi_warn: float = 0.10
    drift_psi_alert: float = 0.25
    min_acceptable_auc: float = 0.68

    # -- retraining --------------------------------------------------------
    # A challenger must beat the champion by at least this much AUC to be promoted.
    promotion_min_auc_gain: float = 0.002


settings = Settings()


# ---------------------------------------------------------------------------
# Feature schema (canonical column names == the raw dataset's column names)
# ---------------------------------------------------------------------------
TARGET = "Default"
ID_COLUMN = "LoanID"

NUMERIC_FEATURES: List[str] = [
    "Age",
    "Income",
    "LoanAmount",
    "CreditScore",
    "MonthsEmployed",
    "NumCreditLines",
    "InterestRate",
    "LoanTerm",
    "DTIRatio",
]

CATEGORICAL_FEATURES: List[str] = [
    "Education",
    "EmploymentType",
    "MaritalStatus",
    "HasMortgage",
    "HasDependents",
    "LoanPurpose",
    "HasCoSigner",
]

BASE_FEATURES: List[str] = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Engineered features produced by src/data/feature_engineering.py
ENGINEERED_NUMERIC: List[str] = [
    "LoanToIncomeRatio",
    "MonthlyInstalment",
    "InstalmentToIncomeRatio",
    "TotalDebtServiceRatio",
    "CreditUtilizationProxy",
    "EmploymentStabilityScore",
    "CreditScoreBandOrdinal",
    "AgeRiskBand",
    "InterestBurden",
    "CreditLinesPerYearOfAge",
    "ThinFileScore",
    "AlternateDataScore",
    "CollateralSupportScore",
    # Real repayment-history / alternate-data features aggregated from the
    # Home Credit bureau, previous-application, installment, POS and
    # credit-card tables (src/data/home_credit.py). NaN for applicants with
    # no such history — a genuine thin-file signal, imputed like any other
    # missing field rather than treated as an error.
    "HasBureauHistory",
    "BureauLoanCount",
    "BureauActiveLoanCount",
    "BureauOverdueLoanCount",
    "BureauDebtToCreditRatio",
    "BureauAvgDaysSinceCredit",
    "BureauBalanceDelinquencyRate",
    "HasPriorApplications",
    "PriorApplicationCount",
    "PriorApprovalRate",
    "PriorRefusalRate",
    "InstallmentCount",
    "InstallmentLatePaymentRate",
    "InstallmentAvgDaysLate",
    "InstallmentAvgPaymentRatio",
    "PosAvgDaysPastDue",
    "PosMaxDaysPastDue",
    "CreditCardUtilizationRatio",
    "CreditCardMaxDaysPastDue",
]

ENGINEERED_CATEGORICAL: List[str] = [
    "AgeGroup",
    "IncomeQuartileBand",
]

ALL_NUMERIC = NUMERIC_FEATURES + ENGINEERED_NUMERIC
ALL_CATEGORICAL = CATEGORICAL_FEATURES + ENGINEERED_CATEGORICAL
ALL_FEATURES = ALL_NUMERIC + ALL_CATEGORICAL

# Engineered features the model is trained on but that no live applicant
# payload can ever supply — they come from a bureau pull and Home Credit's
# own historical records (src/data/home_credit.py), not from anything an
# applicant or loan officer fills in. At inference time they are always the
# fitted imputer's population median/mode, never this applicant's own data.
# They stay in the model (real signal at training time) but are excluded
# from per-prediction "top factors" and the plain-language narrative, so a
# score never gets explained to someone by a value that was never actually
# theirs. Global feature importance (across the training population) is
# unaffected — that's an honest statement about the model, not one applicant.
TRAINING_ONLY_FEATURES: List[str] = [
    "HasBureauHistory",
    "BureauLoanCount",
    "BureauActiveLoanCount",
    "BureauOverdueLoanCount",
    "BureauDebtToCreditRatio",
    "BureauAvgDaysSinceCredit",
    "BureauBalanceDelinquencyRate",
    "HasPriorApplications",
    "PriorApplicationCount",
    "PriorApprovalRate",
    "PriorRefusalRate",
    "InstallmentCount",
    "InstallmentLatePaymentRate",
    "InstallmentAvgDaysLate",
    "InstallmentAvgPaymentRatio",
    "PosAvgDaysPastDue",
    "PosMaxDaysPastDue",
    "CreditCardUtilizationRatio",
    "CreditCardMaxDaysPastDue",
]

# Attributes audited by the fairness module. Age is a genuine protected
# attribute under ECOA; the others are proxies worth monitoring.
PROTECTED_ATTRIBUTES: List[str] = ["AgeGroup", "MaritalStatus", "Education", "EmploymentType"]

# Validation bounds, used by the data-validation schema and API input checks.
FEATURE_BOUNDS: Dict[str, tuple] = {
    "Age": (18, 100),
    "Income": (0, 10_000_000),
    "LoanAmount": (100, 10_000_000),
    "CreditScore": (300, 850),
    "MonthsEmployed": (0, 720),
    "NumCreditLines": (0, 50),
    "InterestRate": (0.0, 60.0),
    "LoanTerm": (1, 480),
    "DTIRatio": (0.0, 1.5),
}

CATEGORICAL_LEVELS: Dict[str, List[str]] = {
    "Education": ["High School", "Bachelor's", "Master's", "PhD"],
    "EmploymentType": ["Full-time", "Part-time", "Self-employed", "Unemployed"],
    "MaritalStatus": ["Single", "Married", "Divorced"],
    "HasMortgage": ["Yes", "No"],
    "HasDependents": ["Yes", "No"],
    "LoanPurpose": ["Auto", "Business", "Education", "Home", "Other"],
    "HasCoSigner": ["Yes", "No"],
}

# Human-readable names used in explanations sent to applicants and officers.
FEATURE_LABELS: Dict[str, str] = {
    "Age": "Applicant age",
    "Income": "Annual income",
    "LoanAmount": "Requested loan amount",
    "CreditScore": "Credit score",
    "MonthsEmployed": "Months in current employment",
    "NumCreditLines": "Number of open credit lines",
    "InterestRate": "Offered interest rate",
    "LoanTerm": "Loan term (months)",
    "DTIRatio": "Debt-to-income ratio",
    "Education": "Education level",
    "EmploymentType": "Employment type",
    "MaritalStatus": "Marital status",
    "HasMortgage": "Existing mortgage",
    "HasDependents": "Dependents",
    "LoanPurpose": "Loan purpose",
    "HasCoSigner": "Co-signer present",
    "LoanToIncomeRatio": "Loan-to-income ratio",
    "MonthlyInstalment": "Estimated monthly instalment",
    "InstalmentToIncomeRatio": "Instalment-to-income ratio",
    "TotalDebtServiceRatio": "Total debt service ratio",
    "CreditUtilizationProxy": "Estimated credit utilisation",
    "EmploymentStabilityScore": "Employment stability",
    "CreditScoreBandOrdinal": "Credit score band",
    "AgeRiskBand": "Age risk band",
    "InterestBurden": "Annual interest burden",
    "CreditLinesPerYearOfAge": "Credit lines per year of adult life",
    "ThinFileScore": "Credit file thickness",
    "AlternateDataScore": "Alternate-data strength",
    "CollateralSupportScore": "Collateral and guarantor support",
    "AgeGroup": "Age group",
    "IncomeQuartileBand": "Income band",
    "HasBureauHistory": "Credit bureau history on file",
    "BureauLoanCount": "Number of credit bureau records",
    "BureauActiveLoanCount": "Active credit bureau loans",
    "BureauOverdueLoanCount": "Overdue credit bureau loans",
    "BureauDebtToCreditRatio": "Bureau debt-to-credit ratio",
    "BureauAvgDaysSinceCredit": "Average age of bureau credit lines",
    "BureauBalanceDelinquencyRate": "Bureau delinquency rate",
    "HasPriorApplications": "Prior applications on file",
    "PriorApplicationCount": "Number of prior applications",
    "PriorApprovalRate": "Prior application approval rate",
    "PriorRefusalRate": "Prior application refusal rate",
    "InstallmentCount": "Number of instalments on record",
    "InstallmentLatePaymentRate": "Share of instalments paid late",
    "InstallmentAvgDaysLate": "Average days late on instalments",
    "InstallmentAvgPaymentRatio": "Average instalment payment ratio",
    "PosAvgDaysPastDue": "Average days past due (POS/cash loans)",
    "PosMaxDaysPastDue": "Worst days past due (POS/cash loans)",
    "CreditCardUtilizationRatio": "Credit card utilisation",
    "CreditCardMaxDaysPastDue": "Worst days past due (credit card)",
}


def ensure_directories() -> None:
    """Create the storage directories the service writes into."""
    for path in (
        settings.data_dir,
        settings.raw_data_dir,
        settings.processed_data_dir,
        settings.registry_dir,
        settings.log_dir,
    ):
        os.makedirs(path, exist_ok=True)
