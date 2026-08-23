"""Pydantic request/response schemas for the ML service.

Input validation is deliberately permissive about *which* fields are present and
strict about the values that are: the backend cannot supply every column the
model trained on, so missing fields are imputed, but a credit score of 9000 is
rejected outright rather than silently clipped.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

RiskLevel = Literal["low", "medium", "high"]
Impact = Literal["positive", "negative"]


# ---------------------------------------------------------------------------
# Application input
# ---------------------------------------------------------------------------
class PersonalInfo(BaseModel):
    """Matches the backend's LoanApplication.personalInfo sub-document."""

    model_config = ConfigDict(extra="allow")

    age: Optional[float] = Field(None, ge=18, le=100)
    maritalStatus: Optional[str] = None
    employmentType: Optional[str] = None
    dependents: Optional[int] = Field(None, ge=0, le=20)
    education: Optional[str] = None


class FinancialInfo(BaseModel):
    """Matches the backend's LoanApplication.financialInfo sub-document."""

    model_config = ConfigDict(extra="allow")

    income: Optional[float] = Field(None, ge=0, le=10_000_000)
    existingDebts: Optional[float] = Field(None, ge=0)
    loanAmountRequested: Optional[float] = Field(None, ge=0, le=10_000_000)
    tenure: Optional[int] = Field(None, ge=1, le=480)
    creditScore: Optional[float] = Field(None, ge=300, le=850)
    purpose: Optional[str] = None


class ApplicationInput(BaseModel):
    """One loan application.

    Accepts the backend's nested shape, flat camelCase, or the raw dataset's
    column names. Unknown keys are kept so the adapter can read them.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    applicationId: Optional[str] = None
    personalInfo: Optional[PersonalInfo] = None
    financialInfo: Optional[FinancialInfo] = None

    # Optional canonical overrides for fields the backend does not collect.
    Age: Optional[float] = Field(None, ge=18, le=100)
    Income: Optional[float] = Field(None, ge=0, le=10_000_000)
    LoanAmount: Optional[float] = Field(None, ge=0, le=10_000_000)
    CreditScore: Optional[float] = Field(None, ge=300, le=850)
    MonthsEmployed: Optional[float] = Field(None, ge=0, le=720)
    NumCreditLines: Optional[float] = Field(None, ge=0, le=50)
    InterestRate: Optional[float] = Field(None, ge=0, le=60)
    LoanTerm: Optional[float] = Field(None, ge=1, le=480)
    DTIRatio: Optional[float] = Field(None, ge=0, le=1.5)
    Education: Optional[str] = None
    EmploymentType: Optional[str] = None
    MaritalStatus: Optional[str] = None
    HasMortgage: Optional[str] = None
    HasDependents: Optional[str] = None
    LoanPurpose: Optional[str] = None
    HasCoSigner: Optional[str] = None

    @model_validator(mode="after")
    def require_some_signal(self) -> "ApplicationInput":
        """Reject an application with nothing to score.

        Without this, an empty body would be fully imputed and returned as a
        confident-looking population-average score, which is worse than an error.
        """
        payload = self.model_dump(exclude_none=True)
        payload.pop("applicationId", None)
        if not payload:
            raise ValueError(
                "Application payload is empty. Provide at least personalInfo/financialInfo "
                "or the applicant's core fields."
            )
        return self

    def as_payload(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True, by_alias=True)


# ---------------------------------------------------------------------------
# /predict
# ---------------------------------------------------------------------------
class PredictRequest(BaseModel):
    application: Optional[ApplicationInput] = None
    includeExplanation: bool = True
    includeFraudCheck: bool = True
    topFactors: int = Field(5, ge=1, le=20)
    audience: Literal["officer", "applicant"] = "officer"

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def accept_bare_application(self) -> "PredictRequest":
        """Allow the application fields to be posted at the top level.

        The backend forwards its stored application document directly, so
        ``{"personalInfo": ..., "financialInfo": ...}`` must work as well as
        ``{"application": {...}}``.
        """
        if self.application is None:
            extras = self.__pydantic_extra__ or {}
            if not extras:
                raise ValueError("No application provided.")
            self.application = ApplicationInput(**extras)
        return self


class TopFactor(BaseModel):
    feature: str
    rawFeature: Optional[str] = None
    impact: Impact
    weight: float
    description: str
    shapValue: Optional[float] = None
    value: Optional[Any] = None


class PredictResponse(BaseModel):
    riskScore: float = Field(..., ge=0, le=100)
    riskLevel: RiskLevel
    probabilityOfDefault: float = Field(..., ge=0, le=1)
    confidenceScore: float = Field(..., ge=0, le=1)
    topFactors: List[TopFactor] = []
    plainLanguageExplanation: List[str] = []
    fraudFlag: Optional[bool] = None
    fraudReason: Optional[str] = None
    fraudProbability: Optional[float] = None
    modelVersion: str
    algorithm: Optional[str] = None
    imputedFields: List[str] = []
    latencyMs: Optional[float] = None
    explanationMethod: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# /predict/batch
# ---------------------------------------------------------------------------
class BatchPredictRequest(BaseModel):
    applications: List[ApplicationInput] = Field(..., min_length=1, max_length=5000)
    includeExplanation: bool = False
    includeFraudCheck: bool = True
    topFactors: int = Field(3, ge=1, le=10)


class BatchPredictResponse(BaseModel):
    count: int
    predictions: List[Dict[str, Any]]
    summary: Dict[str, Any]
    modelVersion: str
    latencyMs: float
    throughputPerSecond: float


# ---------------------------------------------------------------------------
# /explain
# ---------------------------------------------------------------------------
class ExplainRequest(BaseModel):
    application: Optional[ApplicationInput] = None
    topFactors: int = Field(10, ge=1, le=30)

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def accept_bare_application(self) -> "ExplainRequest":
        if self.application is None:
            extras = self.__pydantic_extra__ or {}
            if not extras:
                raise ValueError("No application provided.")
            self.application = ApplicationInput(**extras)
        return self


class ExplainResponse(BaseModel):
    riskScore: float
    riskLevel: RiskLevel
    probabilityOfDefault: float
    confidenceScore: float
    topFactors: List[TopFactor]
    featureContributions: Dict[str, float]
    positiveContributors: Dict[str, float]
    negativeContributors: Dict[str, float]
    plainLanguageExplanation: List[str]
    method: str
    isExact: bool
    modelVersion: str


# ---------------------------------------------------------------------------
# /fraud-check
# ---------------------------------------------------------------------------
class FraudCheckRequest(BaseModel):
    application: Optional[ApplicationInput] = None
    applicationId: Optional[str] = None
    checkDuplicates: bool = True

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def accept_bare_application(self) -> "FraudCheckRequest":
        if self.application is None:
            extras = self.__pydantic_extra__ or {}
            if not extras:
                raise ValueError("No application provided.")
            self.application = ApplicationInput(**extras)
        return self


class FraudCheckResponse(BaseModel):
    fraudFlag: bool
    fraudProbability: float
    reason: Optional[str] = None
    reasons: List[str] = []
    triggeredRules: List[Dict[str, Any]] = []
    duplicateCheck: Dict[str, Any] = {}
    riskTier: str
    threshold: float


# ---------------------------------------------------------------------------
# /simulate
# ---------------------------------------------------------------------------
class SimulateRequest(BaseModel):
    application: ApplicationInput
    adjustments: Dict[str, Any] = Field(
        ...,
        description="Fields to override, e.g. {'CreditScore': 720, 'LoanAmount': 90000}.",
    )
    topFactors: int = Field(5, ge=1, le=20)


class SimulateResponse(BaseModel):
    baseline: Dict[str, Any]
    simulated: Dict[str, Any]
    delta: Dict[str, Any]
    explanation: List[str]
    persisted: bool
    modelVersion: str


# ---------------------------------------------------------------------------
# /fairness-check
# ---------------------------------------------------------------------------
class FairnessCheckRequest(BaseModel):
    applications: List[ApplicationInput] = Field(..., min_length=2, max_length=20000)
    outcomes: Optional[List[int]] = Field(
        None, description="Optional realised default labels (0/1), enabling equal-opportunity metrics."
    )
    attributes: Optional[List[str]] = None

    @model_validator(mode="after")
    def outcomes_align(self) -> "FairnessCheckRequest":
        if self.outcomes is not None and len(self.outcomes) != len(self.applications):
            raise ValueError("`outcomes` must have the same length as `applications`.")
        return self


class FairnessCheckResponse(BaseModel):
    generated_at: str
    n_applications: int
    overall_approval_rate: float
    overall_mean_risk_score: float
    thresholds: Dict[str, Any]
    attributes: Dict[str, Any]
    bias_alert: bool
    alerts: List[str]
    summary: str
    risk_level_distribution: Optional[Dict[str, int]] = None


# ---------------------------------------------------------------------------
# /model-health, /retrain
# ---------------------------------------------------------------------------
class ModelHealthResponse(BaseModel):
    status: str
    modelLoaded: bool
    modelVersion: Optional[str] = None
    algorithm: Optional[str] = None
    trainedAt: Optional[str] = None
    datasetVersion: Optional[str] = None
    metrics: Dict[str, Any] = {}
    thresholds: Dict[str, Any] = {}
    scoreBands: Dict[str, Any] = {}
    drift: Dict[str, Any] = {}
    performanceTrend: Dict[str, Any] = {}
    throughput: Dict[str, Any] = {}
    registry: List[Dict[str, Any]] = []
    alerts: List[str] = []


class RetrainRequest(BaseModel):
    includeOutcomes: bool = True
    autoPromote: bool = True
    async_: bool = Field(True, alias="async")
    notes: str = ""

    model_config = ConfigDict(populate_by_name=True)


class RetrainResponse(BaseModel):
    jobId: str
    status: str
    message: str
    detail: Optional[Dict[str, Any]] = None


class OutcomeRequest(BaseModel):
    application: ApplicationInput
    defaulted: int = Field(..., ge=0, le=1)
    applicationId: Optional[str] = None


class AgreementRequest(BaseModel):
    decisions: List[Dict[str, Any]] = Field(
        ...,
        description="Entries with `aiRecommendation` and `finalDecision` (approve/reject/review).",
    )


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
