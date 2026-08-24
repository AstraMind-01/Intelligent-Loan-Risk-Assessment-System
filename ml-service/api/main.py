"""FastAPI application entry point for the loan risk ML service.

Run locally:
    uvicorn api.main:app --reload --port 8000

Interactive docs at http://localhost:8000/docs
"""
from __future__ import annotations

import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

# Allow `python api/main.py` as well as `uvicorn api.main:app` from the service root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from api.routes import router  # noqa: E402
from src.config import ensure_directories, settings  # noqa: E402
from src.inference.predictor import get_predictor, is_model_available  # noqa: E402
from src.utils.logging_config import configure_logging, get_logger  # noqa: E402

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm the model at startup so the first real request is not the slow one."""
    ensure_directories()
    logger.info("Starting %s", settings.app_name)

    if is_model_available():
        try:
            predictor = get_predictor()
            logger.info("Model %s (%s) loaded and ready.", predictor.version, predictor.algorithm)
        except Exception as exc:  # noqa: BLE001
            # Start anyway: /health must stay up so the failure is visible in the
            # dashboard rather than as a crash-looping container.
            logger.error("Model failed to load at startup: %s", exc)
    else:
        logger.warning(
            "No trained model found in %s. Endpoints will return 503 until "
            "`python scripts/train_model.py` has been run.",
            settings.registry_dir,
        )

    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title="Loan Risk Assessment — ML Service",
    description=(
        "Credit risk scoring, SHAP explainability, fraud screening, fairness auditing, "
        "drift monitoring and retraining for the Intelligent Loan Risk Assessment System."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# The ML service is an internal component: only the backend should reach it.
# In production, keep it off the public network and restrict this list.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
    if elapsed_ms > 2000:
        logger.warning("Slow request: %s %s took %.0fms",
                       request.method, request.url.path, elapsed_ms)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Return a stable error shape and keep internals out of the response body."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error",
                 "detail": "The request could not be completed. See service logs."},
    )


@app.get("/", tags=["health"], summary="Service metadata")
def root():
    return {
        "service": settings.app_name,
        "version": app.version,
        "docs": "/docs",
        "modelAvailable": is_model_available(),
        "endpoints": [
            "POST /predict", "POST /predict/batch", "POST /explain", "GET /explain/global",
            "POST /fraud-check", "POST /simulate", "POST /fairness-check",
            "GET /model-health", "POST /retrain", "GET /health",
        ],
    }


app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.main:app", host=settings.host, port=settings.port, reload=False)
