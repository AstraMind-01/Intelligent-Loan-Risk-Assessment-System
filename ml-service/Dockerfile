# ---------------------------------------------------------------------------
# ML service container
#
# Build:  docker build -t loan-risk-ml ./ml-service
# Run:    docker run -p 8000:8000 -v $(pwd)/ml-service/models:/app/models loan-risk-ml
#
# The model registry is mounted as a volume so retrained models survive a
# container restart and can be rolled back without a rebuild.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# libgomp is required by xgboost and scikit-learn's OpenMP-backed estimators.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first so the layer caches across source changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY api/ ./api/
COPY scripts/ ./scripts/

RUN mkdir -p /app/models /app/data/raw /app/data/processed /app/logs

# Run as a non-root user.
RUN useradd --create-home --shell /bin/bash mlservice \
    && chown -R mlservice:mlservice /app
USER mlservice

ENV PYTHONPATH=/app \
    HOST=0.0.0.0 \
    PORT=8000 \
    LOG_LEVEL=INFO \
    REGISTRY_DIR=/app/models \
    DATA_DIR=/app/data \
    LOG_DIR=/app/logs

EXPOSE 8000

# Hits the liveness probe, which answers even while a model is loading.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
