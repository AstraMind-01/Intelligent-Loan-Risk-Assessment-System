# Loan Risk Assessment — ML Service

FastAPI microservice that scores loan applications for the Intelligent Loan
Risk Assessment System: risk scoring, SHAP explainability, rule-based fraud
screening, fairness auditing, drift/performance monitoring and a champion/
challenger retraining pipeline. Talks to the Node backend
(`backend/src/services/mlClientService.js`) over `POST /predict`,
`/explain`, `/fraud-check`, `/simulate`, `/fairness-check`, `/model-health`
and `/retrain`.

Full endpoint list and interactive docs: run the service and visit `/docs`.

## Data source

Trained on the real **[Home Credit Default Risk](https://www.kaggle.com/competitions/home-credit-default-risk)**
dataset (307,511 applications), not a synthetic one. Seven source tables are
aggregated into one canonical training frame:

| Table | What it adds |
|---|---|
| `application_train.csv` | Core applicant/loan fields |
| `bureau.csv` + `bureau_balance.csv` | Credit bureau history: active/overdue loans, debt-to-credit ratio, delinquency rate |
| `previous_application.csv` | Prior Home Credit applications: count, approval/refusal rate |
| `installments_payments.csv` | **Real repayment history**: late-payment rate, average days late, payment ratio |
| `POS_CASH_balance.csv` | POS/cash loan days-past-due |
| `credit_card_balance.csv` | Real credit-card utilisation, days-past-due |

`src/data/home_credit.py` builds this frame (cached to parquet after the
first ~4.5-minute build; rebuilds automatically if a source file changes) and
maps it onto the **same canonical schema** (`Age`, `Income`, `LoanAmount`,
`CreditScore`, `Education`, `EmploymentType`, ...) already used by
preprocessing, feature engineering, the fraud/fairness modules and the API
adapter — none of those needed to change. See the module docstring for the
full raw-column → canonical-field mapping and the reasoning behind each one
(e.g. why `CreditScore` is derived from `EXT_SOURCE_1/2/3` rather than a raw
field, why `DTIRatio` is `AMT_ANNUITY / AMT_INCOME_TOTAL` and not divided by
12, why `LoanPurpose` can't be derived from this dataset at all).

### Training-only features

18 of the engineered features (`BureauDebtToCreditRatio`,
`InstallmentLatePaymentRate`, `CreditCardUtilizationRatio`, etc. — the full
list is `config.TRAINING_ONLY_FEATURES`) come from the bureau/repayment
tables above. The real backend never runs a bureau pull for a live
application, so at inference time these are **always** the fitted imputer's
population median — never this applicant's own data. They still improve the
model (real signal at training time), but are deliberately excluded from
per-prediction `topFactors` and the plain-language explanation, so a score is
never explained to someone using a value that was never actually theirs.
Global feature importance (`GET /explain/global`) is unaffected, since that's
an honest statement about the model as a whole, not about one applicant.

### Known limitation: fairness

The trained model shows real, statistically significant approval-rate
disparities by age, marital status, education and employment type (see
`GET /fairness-check` or a training run's summary). This is genuine signal in
real credit data, not a bug — but it means the current model is not
production-ready as-is; a deliberate fairness-mitigation pass (e.g.
reweighting, a fairness-constrained objective, or dropping/dampening the most
disparity-driving features) would be needed before using it for real lending
decisions.

## Setup

```bash
pip install -r requirements.txt
```

Place the Kaggle Home Credit Default Risk CSVs at
`data/raw/home-credit/` (`application_train.csv`, `bureau.csv`,
`bureau_balance.csv`, `previous_application.csv`, `POS_CASH_balance.csv`,
`credit_card_balance.csv`, `installments_payments.csv`).

## Train

```bash
python scripts/train_model.py              # full tuning (5-fold CV, 25 search iterations)
python scripts/train_model.py --fast        # quick pass for iteration (3-fold, 6 iterations)
```

Trains a Logistic Regression baseline plus tuned Random Forest and XGBoost
candidates, calibrates the winner, tunes low/medium/high risk-band
thresholds, evaluates on a held-out test split, runs a fairness audit, and
registers + activates the model under `models/<version>/`.

## Run

```bash
uvicorn api.main:app --reload --port 8000
```

Docs at `http://localhost:8000/docs`.

## Test

```bash
pytest tests/ -q
```

## Architecture

```
src/
  config.py            canonical feature schema, thresholds, TRAINING_ONLY_FEATURES
  data/
    home_credit.py      Home Credit ingestion, aggregation, canonical mapping
    loader.py            raw/processed dataset loading + versioning
    validation.py         schema validation and repair
    preprocessing.py        fitted imputation/scaling/encoding pipeline
    feature_engineering.py    stateless derived-ratio features
  models/
    train.py             end-to-end training pipeline
    evaluate.py            metrics, threshold tuning, probability -> risk score
    registry.py               versioned model storage, active pointer, rollback
  explain/                SHAP explanations + plain-language narrative
  fraud/                  rule-based fraud screening (no fraud labels exist to train on)
  fairness/                demographic parity / disparate impact auditing
  monitoring/               drift (PSI) and performance tracking
  retraining/                champion/challenger promotion pipeline
  inference/
    adapter.py            backend payload -> canonical schema (the one contract that must not break)
    predictor.py            single/batch/what-if scoring
api/                      FastAPI app, routes, Pydantic schemas
```
