# ── Production Dockerfile for Knowledge Engine ────────────────────────────────
# Build context: ./backend (includes knowledge_engine + shared packages)

FROM python:3.12-slim as base-builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

FROM base-builder as dependencies-builder

WORKDIR /app
COPY knowledge_engine/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

FROM dependencies-builder as app-builder

WORKDIR /app
COPY knowledge_engine ./knowledge_engine
COPY shared ./shared
ENV PYTHONPATH=/app

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

FROM python:3.12-slim as production

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY --from=dependencies-builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=dependencies-builder /usr/local/bin /usr/local/bin
COPY --from=app-builder --chown=appuser:appuser /app /app

RUN useradd -m -u 1000 appuser || true && mkdir -p /app/logs && chown -R appuser:appuser /app/logs
USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Full API: Attack_Dataset + Qdrant semantic search + trained ML models
CMD ["uvicorn", "knowledge_engine.core.api:app", "--host", "0.0.0.0", "--port", "8000"]
