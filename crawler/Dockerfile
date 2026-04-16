FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps for psycopg + lxml
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libxml2-dev \
        libxslt1-dev \
 && rm -rf /var/lib/apt/lists/*

COPY crawler/requirements.txt /app/crawler/requirements.txt
RUN pip install --no-cache-dir -r /app/crawler/requirements.txt

COPY crawler /app/crawler
COPY db /app/db

WORKDIR /app/crawler
