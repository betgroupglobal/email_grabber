"""
Simple ingestor — loads Attack_Dataset.csv into PostgreSQL only (no embeddings).
"""
import csv
import logging
import os
import time
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://opsec:opsec@postgres:5432/attack_db")
DATASET_PATH = os.getenv("DATASET_PATH", "/data/Attack_Dataset.csv")

log = logging.getLogger("simple_ingestor")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

COLUMNS = [
    "id", "title", "category", "attack_type", "scenario_description",
    "tools_used", "attack_steps", "target_type", "vulnerability",
    "mitre_technique", "impact", "detection_method", "solution", "tags", "source",
]

BATCH_SIZE = 128


def pg_connect():
    """Connect to PostgreSQL."""
    return psycopg2.connect(POSTGRES_DSN)


def ensure_pg_schema(conn):
    """Create PostgreSQL table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS attacks (
                id INTEGER PRIMARY KEY,
                title TEXT,
                category TEXT,
                attack_type TEXT,
                scenario_description TEXT,
                tools_used TEXT,
                attack_steps TEXT,
                target_type TEXT,
                vulnerability TEXT,
                mitre_technique TEXT,
                impact TEXT,
                detection_method TEXT,
                solution TEXT,
                tags TEXT,
                source TEXT
            );
        """)
        # Create text search vector for keyword search
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_attacks_fts 
            ON attacks USING gin(to_tsvector('english', 
                title || ' ' || COALESCE(attack_type, '') || ' ' || COALESCE(scenario_description, '')
            ));
        """)
    conn.commit()


def pg_insert_batch(conn, rows):
    """Insert a batch of rows into PostgreSQL."""
    if not rows:
        return
    
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO attacks (id, title, category, attack_type, scenario_description,
                               tools_used, attack_steps, target_type, vulnerability,
                               mitre_technique, impact, detection_method, solution, tags, source)
            VALUES %s
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                category = EXCLUDED.category,
                attack_type = EXCLUDED.attack_type,
                scenario_description = EXCLUDED.scenario_description,
                tools_used = EXCLUDED.tools_used,
                attack_steps = EXCLUDED.attack_steps,
                target_type = EXCLUDED.target_type,
                vulnerability = EXCLUDED.vulnerability,
                mitre_technique = EXCLUDED.mitre_technique,
                impact = EXCLUDED.impact,
                detection_method = EXCLUDED.detection_method,
                solution = EXCLUDED.solution,
                tags = EXCLUDED.tags,
                source = EXCLUDED.source
            """,
            [(
                int(row.get("id", 0)),
                row.get("title", ""),
                row.get("category", ""),
                row.get("attack_type", ""),
                row.get("scenario_description", ""),
                row.get("tools_used", ""),
                row.get("attack_steps", ""),
                row.get("target_type", ""),
                row.get("vulnerability", ""),
                row.get("mitre_technique", ""),
                row.get("impact", ""),
                row.get("detection_method", ""),
                row.get("solution", ""),
                row.get("tags", ""),
                row.get("source", "")
            ) for row in rows]
        )
    conn.commit()


def ingest(dataset_path: str = DATASET_PATH, force: bool = False):
    """Ingest dataset into PostgreSQL only."""
    path = Path(dataset_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    log.info("Connecting to PostgreSQL…")
    pg_conn = pg_connect()
    ensure_pg_schema(pg_conn)

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
    batch = []

    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("id", "").strip().isdigit():
                continue
            batch.append(row)
            if len(batch) >= BATCH_SIZE:
                pg_insert_batch(pg_conn, batch)
                total += len(batch)
                log.info("  Ingested %d records…", total)
                batch = []

    if batch:
        pg_insert_batch(pg_conn, batch)
        total += len(batch)

    elapsed = time.time() - t0
    log.info("Ingestion complete: %d records in %.1fs.", total, elapsed)
    pg_conn.close()
    return total


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ingest attack dataset into PostgreSQL")
    parser.add_argument("--force", action="store_true", help="Re-ingest even if data exists")
    args = parser.parse_args()
    
    ingest(force=args.force)