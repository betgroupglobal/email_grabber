FROM python:3.11-slim

WORKDIR /app

# System deps for psycopg2 + sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-download embedding model at build time so runtime is fast
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

EXPOSE 8000

# Ingest on first start, then serve
CMD ["sh", "-c", "python ingestor.py && uvicorn api:app --host 0.0.0.0 --port 8000"]
