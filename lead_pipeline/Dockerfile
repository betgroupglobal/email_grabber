FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

COPY lead_pipeline/requirements.txt /app/lead_pipeline/requirements.txt
RUN pip install --no-cache-dir -r /app/lead_pipeline/requirements.txt

COPY lead_pipeline /app/lead_pipeline
COPY db /app/db

EXPOSE 8000

CMD ["uvicorn", "lead_pipeline.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
