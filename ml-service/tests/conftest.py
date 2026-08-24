"""Shared pytest fixtures."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import BASE_FEATURES, TARGET  # noqa: E402
from src.models import registry  # noqa: E402


@pytest.fixture
def sample_application() -> dict:
    """A complete, well-formed application in canonical (dataset) form."""
    return {
        "Age": 42,
        "Income": 85_000,
        "LoanAmount": 120_000,
        "CreditScore": 640,
        "MonthsEmployed": 60,
        "NumCreditLines": 3,
        "InterestRate": 12.5,
        "LoanTerm": 36,
        "DTIRatio": 0.42,
        "Education": "Bachelor's",
        "EmploymentType": "Full-time",
        "MaritalStatus": "Married",
        "HasMortgage": "Yes",
        "HasDependents": "Yes",
        "LoanPurpose": "Home",
        "HasCoSigner": "No",
    }


@pytest.fixture
def backend_application() -> dict:
    """The payload shape the Node backend actually sends."""
    return {
        "applicationId": "test-app-001",
        "personalInfo": {
            "age": 42,
            "maritalStatus": "married",
            "employmentType": "full_time",
            "dependents": 2,
            "education": "bachelors",
        },
        "financialInfo": {
            "income": 85_000,
            "existingDebts": 35_700,
            "loanAmountRequested": 120_000,
            "tenure": 36,
            "creditScore": 640,
            "purpose": "home_purchase",
        },
    }


@pytest.fixture
def sample_frame(sample_application) -> pd.DataFrame:
    """A small synthetic frame with a target column."""
    rng = np.random.default_rng(7)
    rows = []
    for i in range(200):
        row = dict(sample_application)
        row["Age"] = int(rng.integers(18, 70))
        row["Income"] = int(rng.integers(20_000, 150_000))
        row["LoanAmount"] = int(rng.integers(5_000, 250_000))
        row["CreditScore"] = int(rng.integers(300, 850))
        row["MonthsEmployed"] = int(rng.integers(0, 120))
        row["NumCreditLines"] = int(rng.integers(1, 5))
        row["InterestRate"] = float(rng.uniform(2, 25))
        row["LoanTerm"] = int(rng.choice([12, 24, 36, 48, 60]))
        row["DTIRatio"] = float(rng.uniform(0.1, 0.9))
        row["EmploymentType"] = str(rng.choice(["Full-time", "Part-time", "Self-employed", "Unemployed"]))
        row[TARGET] = int(rng.integers(0, 2))
        rows.append(row)
    return pd.DataFrame(rows, columns=BASE_FEATURES + [TARGET])


@pytest.fixture(scope="session")
def has_trained_model() -> bool:
    return registry.get_active_version() is not None


requires_model = pytest.mark.skipif(
    registry.get_active_version() is None,
    reason="No trained model registered; run `python scripts/train_model.py` first.",
)
