"""Ingests the real Home Credit Default Risk dataset and maps it onto the
service's canonical schema (the same Age/Income/LoanAmount/... columns the
rest of the pipeline, the API adapter and the real Node backend already agree
on — see backend/src/models/LoanApplication.js for the contract this must not
break).

Why this exists: the flat CSV this service originally trained on is synthetic
(zero missing values across 255k rows is not something real credit data does)
and has no real repayment history. Home Credit's data is real, messy in the
way real applications are, and — critically — carries genuine bureau credit
history and installment-level repayment behaviour, which is exactly what the
checklist's "repayment history" and "alternate data" feature requirements ask
for and the old dataset could not supply.

Two layers of output:
  1. The canonical intake fields (Age, Income, LoanAmount, ...) — derived from
     application_train.csv so the existing preprocessing/feature-engineering/
     fraud/fairness code needs no changes.
  2. A set of new engineered columns aggregated from the five satellite tables
     (bureau, previous applications, installment payments, POS and credit-card
     balances), one row per SK_ID_CURR. These carry real signal the synthetic
     dataset never had. A client with no bureau or prior-application history
     gets NaN here — which is honest thin-file behaviour, not a data bug — and
     the fitted imputer handles it exactly like any other missing field.

At inference time (a single application from the backend) none of the
satellite-table features can be populated — the backend does not run a bureau
pull — so they are always imputed, the same way MonthsEmployed/InterestRate/
HasMortgage already are today. They only add value at training time, where
they measurably describe applicants the model is scored against.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.utils.logging_config import get_logger

logger = get_logger(__name__)

CACHE_FILE = "_canonical_cache.parquet"
CACHE_HASH_FILE = "_canonical_cache.hash"

# ---------------------------------------------------------------------------
# Categorical vocabulary mapping: Home Credit's raw levels -> the canonical
# levels config.CATEGORICAL_LEVELS already defines (shared with the API
# adapter's backend-payload mapping, so the vocabulary must match exactly).
# ---------------------------------------------------------------------------
_EDUCATION_MAP = {
    "Secondary / secondary special": "High School",
    "Lower secondary": "High School",
    "Incomplete higher": "Bachelor's",
    "Higher education": "Bachelor's",
    "Academic degree": "PhD",
}

# NAME_INCOME_TYPE is the closest Home Credit field to an employment-type
# signal. Pensioner -> Part-time mirrors the API adapter's own
# retired -> Part-time approximation, so training and serving stay consistent.
_EMPLOYMENT_MAP = {
    "Working": "Full-time",
    "Commercial associate": "Full-time",
    "State servant": "Full-time",
    "Pensioner": "Part-time",
    "Businessman": "Self-employed",
    "Unemployed": "Unemployed",
    "Student": "Unemployed",
    "Maternity leave": "Unemployed",
}

# Separated/Widow both fold to Divorced, matching the adapter's own
# widowed -> Divorced approximation for the same reason: no better bucket.
_MARITAL_MAP = {
    "Married": "Married",
    "Civil marriage": "Married",
    "Single / not married": "Single",
    "Separated": "Divorced",
    "Widow": "Divorced",
}

_DPD_STATUSES = {"1", "2", "3", "4", "5"}  # bureau_balance codes for 1-30 ... 120+/written-off


def _cache_paths(raw_dir: Path) -> tuple[Path, Path]:
    return raw_dir / CACHE_FILE, raw_dir / CACHE_HASH_FILE


def _source_fingerprint(raw_dir: Path, files: list[str]) -> str:
    """Cheap fingerprint (name + size + mtime, not full content) of the source tables."""
    digest = hashlib.sha256()
    for name in sorted(files):
        stat = (raw_dir / name).stat()
        digest.update(f"{name}:{stat.st_size}:{stat.st_mtime_ns}".encode())
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Satellite-table aggregation: each returns one row per SK_ID_CURR.
# ---------------------------------------------------------------------------
def _aggregate_bureau(raw_dir: Path) -> pd.DataFrame:
    bureau = pd.read_csv(
        raw_dir / "bureau.csv",
        usecols=["SK_ID_CURR", "SK_ID_BUREAU", "CREDIT_ACTIVE", "CREDIT_DAY_OVERDUE",
                 "DAYS_CREDIT", "AMT_CREDIT_SUM", "AMT_CREDIT_SUM_DEBT"],
    )
    balance = pd.read_csv(raw_dir / "bureau_balance.csv", usecols=["SK_ID_BUREAU", "STATUS"])

    balance_agg = balance.groupby("SK_ID_BUREAU")["STATUS"].apply(
        lambda s: s.isin(_DPD_STATUSES).mean()
    ).rename("BureauBalanceDelinquencyRate")
    bureau = bureau.merge(balance_agg, on="SK_ID_BUREAU", how="left")

    bureau["_is_active"] = bureau["CREDIT_ACTIVE"] == "Active"
    bureau["_is_overdue"] = bureau["CREDIT_DAY_OVERDUE"] > 0

    agg = bureau.groupby("SK_ID_CURR").agg(
        BureauLoanCount=("SK_ID_BUREAU", "count"),
        BureauActiveLoanCount=("_is_active", "sum"),
        BureauOverdueLoanCount=("_is_overdue", "sum"),
        BureauTotalCreditSum=("AMT_CREDIT_SUM", "sum"),
        BureauTotalDebtSum=("AMT_CREDIT_SUM_DEBT", "sum"),
        BureauAvgDaysSinceCredit=("DAYS_CREDIT", "mean"),
        BureauBalanceDelinquencyRate=("BureauBalanceDelinquencyRate", "mean"),
    ).reset_index()

    agg["BureauDebtToCreditRatio"] = (
        agg["BureauTotalDebtSum"] / agg["BureauTotalCreditSum"].clip(lower=1.0)
    ).clip(0, 5)
    # DAYS_CREDIT is negative (days before the current application); flip so
    # larger = credit taken out longer ago, which reads naturally as a feature.
    agg["BureauAvgDaysSinceCredit"] = (-agg["BureauAvgDaysSinceCredit"]).clip(lower=0)
    agg["HasBureauHistory"] = 1.0

    return agg[[
        "SK_ID_CURR", "HasBureauHistory", "BureauLoanCount", "BureauActiveLoanCount",
        "BureauOverdueLoanCount", "BureauDebtToCreditRatio", "BureauAvgDaysSinceCredit",
        "BureauBalanceDelinquencyRate",
    ]]


def _aggregate_previous_applications(raw_dir: Path) -> pd.DataFrame:
    prev = pd.read_csv(
        raw_dir / "previous_application.csv",
        usecols=["SK_ID_CURR", "SK_ID_PREV", "NAME_CONTRACT_STATUS"],
    )
    prev["_approved"] = prev["NAME_CONTRACT_STATUS"] == "Approved"
    prev["_refused"] = prev["NAME_CONTRACT_STATUS"] == "Refused"

    agg = prev.groupby("SK_ID_CURR").agg(
        PriorApplicationCount=("SK_ID_PREV", "count"),
        _approved_count=("_approved", "sum"),
        _refused_count=("_refused", "sum"),
    ).reset_index()

    agg["PriorApprovalRate"] = agg["_approved_count"] / agg["PriorApplicationCount"].clip(lower=1)
    agg["PriorRefusalRate"] = agg["_refused_count"] / agg["PriorApplicationCount"].clip(lower=1)
    agg["HasPriorApplications"] = 1.0

    return agg[["SK_ID_CURR", "HasPriorApplications", "PriorApplicationCount",
                "PriorApprovalRate", "PriorRefusalRate"]]


def _aggregate_installments(raw_dir: Path) -> pd.DataFrame:
    inst = pd.read_csv(
        raw_dir / "installments_payments.csv",
        usecols=["SK_ID_CURR", "DAYS_INSTALMENT", "DAYS_ENTRY_PAYMENT", "AMT_INSTALMENT", "AMT_PAYMENT"],
    )
    # Positive = paid after it was due (late); NaN entry-payment means unpaid.
    days_late = (inst["DAYS_ENTRY_PAYMENT"] - inst["DAYS_INSTALMENT"]).clip(lower=0)
    payment_ratio = (inst["AMT_PAYMENT"] / inst["AMT_INSTALMENT"].clip(lower=1.0)).clip(0, 3)

    inst["_days_late"] = days_late
    inst["_late_flag"] = days_late > 0
    inst["_payment_ratio"] = payment_ratio

    agg = inst.groupby("SK_ID_CURR").agg(
        InstallmentCount=("AMT_INSTALMENT", "count"),
        InstallmentLatePaymentRate=("_late_flag", "mean"),
        InstallmentAvgDaysLate=("_days_late", "mean"),
        InstallmentAvgPaymentRatio=("_payment_ratio", "mean"),
    ).reset_index()

    return agg


def _aggregate_pos_cash(raw_dir: Path) -> pd.DataFrame:
    pos = pd.read_csv(raw_dir / "POS_CASH_balance.csv", usecols=["SK_ID_CURR", "SK_DPD"])
    agg = pos.groupby("SK_ID_CURR")["SK_DPD"].agg(
        PosAvgDaysPastDue="mean", PosMaxDaysPastDue="max"
    ).reset_index()
    return agg


def _aggregate_credit_card(raw_dir: Path) -> pd.DataFrame:
    cc = pd.read_csv(
        raw_dir / "credit_card_balance.csv",
        usecols=["SK_ID_CURR", "AMT_BALANCE", "AMT_CREDIT_LIMIT_ACTUAL", "SK_DPD"],
    )
    cc["_utilization"] = (cc["AMT_BALANCE"] / cc["AMT_CREDIT_LIMIT_ACTUAL"].clip(lower=1.0)).clip(0, 3)
    agg = cc.groupby("SK_ID_CURR").agg(
        CreditCardUtilizationRatio=("_utilization", "mean"),
        CreditCardMaxDaysPastDue=("SK_DPD", "max"),
    ).reset_index()
    return agg


# ---------------------------------------------------------------------------
# Main-table -> canonical schema
# ---------------------------------------------------------------------------
def _map_application_table(app: pd.DataFrame) -> pd.DataFrame:
    """application_train.csv -> the canonical Age/Income/LoanAmount/... schema."""
    out = pd.DataFrame(index=app.index)
    out["SK_ID_CURR"] = app["SK_ID_CURR"]
    out["Default"] = app["TARGET"].astype(int)

    # -- numeric -------------------------------------------------------
    out["Age"] = (-app["DAYS_BIRTH"] / 365.25).round(1)

    # 365243 is Home Credit's sentinel for "not currently employed"
    # (pensioners, unemployed) rather than a real day count.
    employed_days = app["DAYS_EMPLOYED"].where(app["DAYS_EMPLOYED"] != 365243, other=np.nan)
    out["MonthsEmployed"] = (-employed_days / 30.44).clip(lower=0)

    out["Income"] = app["AMT_INCOME_TOTAL"]
    out["LoanAmount"] = app["AMT_CREDIT"]

    # EXT_SOURCE_1/2/3 are Home Credit's own normalised (0-1) external
    # credit-bureau risk scores — the strongest predictors in this dataset.
    # Averaging the available ones and rescaling onto 300-850 gives a real
    # bureau-score analogue in the exact range the backend's intake form
    # already expects (LoanApplication.financialInfo.creditScore).
    ext_source_avg = app[["EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3"]].mean(axis=1, skipna=True)
    out["CreditScore"] = (300 + ext_source_avg.clip(0, 1) * 550).round(0)

    # Home Credit doesn't expose a per-line bureau count on the main table;
    # NumCreditLines is filled in later from the real bureau.csv aggregation
    # and left NaN here for applicants with no bureau record (genuine
    # thin-file signal, not a data gap).
    out["NumCreditLines"] = np.nan

    # No disclosed interest rate anywhere in this dataset (same gap the
    # backend has today — it doesn't collect one either). A column that is
    # 100% missing gets silently dropped by SimpleImputer(strategy="median"),
    # which would desync the feature schema everywhere else assumes
    # InterestRate exists (the SHAP explainer's feature grouping, the
    # validation schema, ALL_NUMERIC). A constant placeholder keeps the
    # column present with the same (zero) information a true NaN would carry
    # for a fitted median imputer.
    out["InterestRate"] = 0.0

    # Established engineered feature from this exact Kaggle competition:
    # credit / annuity approximates the number of instalments (ignoring
    # interest), i.e. the loan's term in months.
    out["LoanTerm"] = (app["AMT_CREDIT"] / app["AMT_ANNUITY"].replace(0, np.nan)).round(0).clip(1, 480)

    # Real DTI proxy: this loan's annuity against annual income — the
    # ANNUITY_INCOME_PERCENT feature well-established in this dataset's
    # public EDA. Dividing income by 12 first (i.e. comparing against monthly
    # income) looks intuitive but is wrong here: it inflates the ratio ~12x
    # and saturates most applicants at the clip bound, since AMT_ANNUITY in
    # this dataset is not simply "one month's payment".
    out["DTIRatio"] = (
        app["AMT_ANNUITY"] / app["AMT_INCOME_TOTAL"].replace(0, np.nan)
    ).clip(0, 1.5)

    # -- categorical -----------------------------------------------------
    out["Education"] = app["NAME_EDUCATION_TYPE"].map(_EDUCATION_MAP)
    out["EmploymentType"] = app["NAME_INCOME_TYPE"].map(_EMPLOYMENT_MAP)
    out["MaritalStatus"] = app["NAME_FAMILY_STATUS"].map(_MARITAL_MAP)

    # FLAG_OWN_REALTY is the closest available proxy for an existing
    # mortgage/property stake; there's no direct mortgage flag in this data.
    out["HasMortgage"] = np.where(app["FLAG_OWN_REALTY"] == "Y", "Yes", "No")
    out["HasDependents"] = np.where(app["CNT_CHILDREN"].fillna(0) > 0, "Yes", "No")

    # NAME_TYPE_SUITE records who accompanied the applicant; "not
    # unaccompanied" is a weak but real proxy for having support behind the
    # application. There is no genuine co-signer field in this dataset.
    out["HasCoSigner"] = np.where(
        app["NAME_TYPE_SUITE"].notna() & (app["NAME_TYPE_SUITE"] != "Unaccompanied"), "Yes", "No"
    )

    # Home Credit's main table carries no purpose for the *current* loan
    # (previous_application.NAME_CASH_LOAN_PURPOSE describes past loans, and
    # is >85% "XAP"/"XNA" - i.e. not recorded - even where present). Rather
    # than fabricate a proxy, every row gets the same placeholder category:
    # zero training signal (same as leaving it unset), but unlike a fully
    # missing column it survives SimpleImputer(strategy="most_frequent")
    # cleanly. A real applicant-supplied purpose at inference (LoanPurpose
    # isn't a required backend field, but may be sent) is simply an unseen
    # category to the fitted OneHotEncoder(handle_unknown="ignore") — ignored
    # gracefully, the same way any other unrecognised category already is.
    out["LoanPurpose"] = "Other"

    return out


def _build_canonical_frame(raw_dir: Path) -> pd.DataFrame:
    logger.info("Building canonical training frame from Home Credit source tables in %s", raw_dir)

    app = pd.read_csv(raw_dir / "application_train.csv")
    canonical = _map_application_table(app)
    del app

    for name, builder in (
        ("bureau", _aggregate_bureau),
        ("previous applications", _aggregate_previous_applications),
        ("installments", _aggregate_installments),
        ("POS/cash balances", _aggregate_pos_cash),
        ("credit card balances", _aggregate_credit_card),
    ):
        logger.info("Aggregating %s ...", name)
        satellite = builder(raw_dir)
        canonical = canonical.merge(satellite, on="SK_ID_CURR", how="left")

    canonical["HasBureauHistory"] = canonical["HasBureauHistory"].fillna(0.0)
    canonical["HasPriorApplications"] = canonical["HasPriorApplications"].fillna(0.0)

    # Real bureau credit-line count where available; applicants with no
    # bureau record keep the NaN NumCreditLines set above (imputed downstream).
    canonical["NumCreditLines"] = canonical["NumCreditLines"].fillna(canonical["BureauLoanCount"])

    # Kept (not dropped) as the service's ID_COLUMN, so loader.deduplicate()
    # and dataset-version metadata work the same way they did for LoanID.
    canonical = canonical.rename(columns={"SK_ID_CURR": "LoanID"})
    logger.info("Canonical frame built: %d rows x %d columns", *canonical.shape)
    return canonical


def load_home_credit(raw_dir: Path, use_cache: bool = True) -> pd.DataFrame:
    """Canonical training frame from the Home Credit tables, cached after the first build.

    Building this from scratch re-reads ~2.5GB across 7 files (dominated by
    the ~14M-row installment history), so the result is cached to parquet and
    only rebuilt when a source file's size or mtime changes.
    """
    required = [
        "application_train.csv", "bureau.csv", "bureau_balance.csv",
        "previous_application.csv", "POS_CASH_balance.csv",
        "credit_card_balance.csv", "installments_payments.csv",
    ]
    missing = [f for f in required if not (raw_dir / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing Home Credit source file(s) in {raw_dir}: {missing}"
        )

    cache_path, hash_path = _cache_paths(raw_dir)
    fingerprint = _source_fingerprint(raw_dir, required)

    if use_cache and cache_path.exists() and hash_path.exists():
        if hash_path.read_text().strip() == fingerprint:
            logger.info("Loading cached canonical frame from %s", cache_path)
            return pd.read_parquet(cache_path)
        logger.info("Source tables changed; rebuilding the canonical frame cache.")

    canonical = _build_canonical_frame(raw_dir)

    if use_cache:
        canonical.to_parquet(cache_path, index=False)
        hash_path.write_text(fingerprint)
        logger.info("Cached canonical frame to %s", cache_path)

    return canonical
