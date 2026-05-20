"""
Ingestor — reads Attack_Dataset.csv, cleans it, and writes to:
  1. PostgreSQL (full structured data)
  2. Qdrant    (vector embeddings for semantic search)
"""
from __future__ import annotations

import csv
import hashlib
import logging
import time
from pathlib import Path
from typing import List, Dict, Any

import psycopg2
from psycopg2.extras import execute_values
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    OptimizersConfigDiff,
)
from fastembed import TextEmbedding
from rich.progress import track

from ..utils.config import (
    POSTGRES_DSN,
    QDRANT_HOST,
    QDRANT_PORT,
    QDRANT_COLLECTION,
    EMBEDDING_MODEL,
    EMBEDDING_DIM,
    DATASET_PATH,
)

log = logging.getLogger("ingestor")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

COLUMNS = [
    "id", "title", "category", "attack_type", "scenario_description",
    "tools_used", "attack_steps", "target_type", "vulnerability",
    "mitre_technique", "impact", "detection_method", "solution", "tags", "source",
]

BATCH_SIZE = 128


# ── helpers ──────────────────────────────────────────────────────────────────

def clean(text: str) -> str:
    return (text or "").strip().replace("\x00", "")


def build_embedding_text(row: Dict[str, str]) -> str:
    """Concatenate key fields into a single string for embedding."""
    parts = [
        row.get("title", ""),
        row.get("category", ""),
        row.get("attack_type", ""),
        row.get("scenario_description", ""),
        row.get("target_type", ""),
        row.get("vulnerability", ""),
        row.get("mitre_technique", ""),
        row.get("tags", ""),
    ]
    return " | ".join(p for p in parts if p)


# ── PostgreSQL ────────────────────────────────────────────────────────────────

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS attacks (
    id               INTEGER PRIMARY KEY,
    title            TEXT,
    category         TEXT,
    attack_type      TEXT,
    scenario_description TEXT,
    tools_used       TEXT,
    attack_steps     TEXT,
    target_type      TEXT,
    vulnerability    TEXT,
    mitre_technique  TEXT,
    impact           TEXT,
    detection_method TEXT,
    solution         TEXT,
    tags             TEXT,
    source           TEXT
);

CREATE INDEX IF NOT EXISTS idx_attacks_category      ON attacks(category);
CREATE INDEX IF NOT EXISTS idx_attacks_attack_type   ON attacks(attack_type);
CREATE INDEX IF NOT EXISTS idx_attacks_mitre         ON attacks(mitre_technique);
CREATE INDEX IF NOT EXISTS idx_attacks_target        ON attacks(target_type);
CREATE INDEX IF NOT EXISTS idx_attacks_title_fts
    ON attacks USING gin(to_tsvector('english', title || ' ' || attack_type));
"""


def pg_connect():
    return psycopg2.connect(POSTGRES_DSN)


def ensure_pg_schema(conn):
    with conn.cursor() as cur:
        cur.execute(CREATE_TABLE_SQL)
    conn.commit()
    log.info("PostgreSQL schema ready.")


def pg_insert_batch(conn, rows: List[Dict[str, Any]]):
    values = [
        (
            int(r["id"]),
            clean(r["title"]),
            clean(r["category"]),
            clean(r["attack_type"]),
            clean(r["scenario_description"]),
            clean(r["tools_used"]),
            clean(r["attack_steps"]),
            clean(r["target_type"]),
            clean(r["vulnerability"]),
            clean(r["mitre_technique"]),
            clean(r["impact"]),
            clean(r["detection_method"]),
            clean(r["solution"]),
            clean(r["tags"]),
            clean(r["source"]),
        )
        for r in rows
    ]
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO attacks VALUES %s
            ON CONFLICT (id) DO UPDATE SET
                title=EXCLUDED.title,
                category=EXCLUDED.category,
                attack_type=EXCLUDED.attack_type,
                scenario_description=EXCLUDED.scenario_description,
                tools_used=EXCLUDED.tools_used,
                attack_steps=EXCLUDED.attack_steps,
                target_type=EXCLUDED.target_type,
                vulnerability=EXCLUDED.vulnerability,
                mitre_technique=EXCLUDED.mitre_technique,
                impact=EXCLUDED.impact,
                detection_method=EXCLUDED.detection_method,
                solution=EXCLUDED.solution,
                tags=EXCLUDED.tags,
                source=EXCLUDED.source
            """,
            values,
            template=None,
            page_size=BATCH_SIZE,
        )
    conn.commit()


# ── Qdrant ────────────────────────────────────────────────────────────────────

def ensure_qdrant_collection(client: QdrantClient):
    existing = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION not in existing:
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
            optimizers_config=OptimizersConfigDiff(indexing_threshold=10_000),
        )
        log.info("Qdrant collection '%s' created.", QDRANT_COLLECTION)
    else:
        log.info("Qdrant collection '%s' already exists.", QDRANT_COLLECTION)


def qdrant_upsert_batch(client: QdrantClient, model: TextEmbedding, rows: List[Dict]):
    texts = [build_embedding_text(r) for r in rows]
    vectors = [v.tolist() for v in model.embed(texts, batch_size=32)]
    points = []
    for row, vec in zip(rows, vectors):
        rid = int(row["id"])
        payload = {
            "title": clean(row["title"]),
            "category": clean(row["category"]),
            "attack_type": clean(row["attack_type"]),
            "target_type": clean(row["target_type"]),
            "mitre_technique": clean(row["mitre_technique"]),
            "tags": clean(row["tags"]),
            "tools_used": clean(row["tools_used"]),
        }
        points.append(PointStruct(id=rid, vector=vec, payload=payload))
    client.upsert(collection_name=QDRANT_COLLECTION, points=points, wait=True)


# ── Main ingest loop ──────────────────────────────────────────────────────────

def ingest(dataset_path: str = DATASET_PATH, force: bool = False):
    path = Path(dataset_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    log.info("Loading embedding model '%s'…", EMBEDDING_MODEL)
    try:
        model = TextEmbedding(model_name=EMBEDDING_MODEL)
        use_embeddings = True
        log.info("Embedding model loaded successfully.")
    except Exception as e:
        log.warning(f"Failed to load embedding model: {e}. Proceeding without embeddings.")
        model = None
        use_embeddings = False

    log.info("Connecting to PostgreSQL…")
    pg_conn = pg_connect()
    ensure_pg_schema(pg_conn)

    if use_embeddings:
        log.info("Connecting to Qdrant…")
        qd_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        ensure_qdrant_collection(qd_client)
    else:
        qd_client = None
        log.warning("Skipping Qdrant initialization (embeddings disabled).")

    # Check existing count
    with pg_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM attacks")
        existing = cur.fetchone()[0]

    if existing > 0 and not force:
        log.info(
            "Database already has %d records. Use --force to re-ingest.", existing
        )
        return existing

    log.info("Starting ingestion from %s…", path)
    t0 = time.time()
    total = 0
    batch: List[Dict] = []

    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("id", "").strip().isdigit():
                continue
            batch.append(row)
            if len(batch) >= BATCH_SIZE:
                pg_insert_batch(pg_conn, batch)
                if use_embeddings:
                    qdrant_upsert_batch(qd_client, model, batch)
                total += len(batch)
                log.info("  Ingested %d records…", total)
                batch = []

    if batch:
        pg_insert_batch(pg_conn, batch)
        if use_embeddings:
            qdrant_upsert_batch(qd_client, model, batch)
        total += len(batch)

    elapsed = time.time() - t0
    log.info("Ingestion complete: %d records in %.1fs.", total, elapsed)
    pg_conn.close()
    return total


if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    ingest(force=force)
