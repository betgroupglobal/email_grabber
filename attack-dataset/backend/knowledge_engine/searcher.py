"""
Searcher — semantic + structured search over the attack knowledge base.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any

import psycopg2
import psycopg2.extras
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer

from config import (
    POSTGRES_DSN,
    QDRANT_HOST,
    QDRANT_PORT,
    QDRANT_COLLECTION,
    EMBEDDING_MODEL,
)
from models import AttackRecord, AttackResult, SearchResponse

log = logging.getLogger("searcher")


class AttackSearcher:
    def __init__(self):
        log.info("Loading embedding model…")
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        self.qd = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        self.pg = psycopg2.connect(POSTGRES_DSN)
        self.pg.autocommit = True
        log.info("AttackSearcher ready.")

    # ── internal helpers ──────────────────────────────────────────────────────

    def _row_to_record(self, row: Dict[str, Any]) -> AttackRecord:
        return AttackRecord(**{k: (v or "") for k, v in row.items()})

    def _fetch_by_ids(self, ids: List[int]) -> Dict[int, AttackRecord]:
        if not ids:
            return {}
        with self.pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM attacks WHERE id = ANY(%s)", (ids,)
            )
            return {r["id"]: self._row_to_record(dict(r)) for r in cur.fetchall()}

    def _build_qdrant_filter(
        self,
        category: Optional[str] = None,
        attack_type: Optional[str] = None,
        mitre: Optional[str] = None,
    ) -> Optional[Filter]:
        conditions = []
        if category:
            conditions.append(
                FieldCondition(key="category", match=MatchValue(value=category))
            )
        if attack_type:
            conditions.append(
                FieldCondition(key="attack_type", match=MatchValue(value=attack_type))
            )
        if mitre:
            conditions.append(
                FieldCondition(key="mitre_technique", match=MatchValue(value=mitre))
            )
        if not conditions:
            return None
        from qdrant_client.models import Filter, Must
        return Filter(must=conditions)

    # ── public API ────────────────────────────────────────────────────────────

    def semantic_search(
        self,
        query: str,
        top_k: int = 10,
        category: Optional[str] = None,
        attack_type: Optional[str] = None,
        mitre: Optional[str] = None,
    ) -> SearchResponse:
        """
        Embed the query and search Qdrant for nearest neighbours,
        then hydrate full records from PostgreSQL.
        """
        vec = self.model.encode([query])[0].tolist()
        filt = self._build_qdrant_filter(category, attack_type, mitre)

        hits = self.qd.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=vec,
            limit=top_k,
            query_filter=filt,
            with_payload=True,
        )

        ids = [int(h.id) for h in hits]
        records_map = self._fetch_by_ids(ids)

        results = []
        for hit in hits:
            rid = int(hit.id)
            if rid in records_map:
                results.append(
                    AttackResult(record=records_map[rid], score=round(hit.score, 4))
                )

        return SearchResponse(query=query, results=results, total=len(results))

    def keyword_search(self, keyword: str, limit: int = 20) -> List[AttackRecord]:
        """Full-text search via PostgreSQL tsvector."""
        with self.pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM attacks
                WHERE to_tsvector('english', title || ' ' || attack_type || ' ' || scenario_description)
                      @@ plainto_tsquery('english', %s)
                LIMIT %s
                """,
                (keyword, limit),
            )
            return [self._row_to_record(dict(r)) for r in cur.fetchall()]

    def get_by_mitre(self, technique_id: str, limit: int = 20) -> List[AttackRecord]:
        """Retrieve all attacks mapped to a MITRE technique."""
        with self.pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM attacks WHERE mitre_technique ILIKE %s LIMIT %s",
                (f"%{technique_id}%", limit),
            )
            return [self._row_to_record(dict(r)) for r in cur.fetchall()]

    def get_by_category(self, category: str, limit: int = 50) -> List[AttackRecord]:
        with self.pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM attacks WHERE category ILIKE %s LIMIT %s",
                (f"%{category}%", limit),
            )
            return [self._row_to_record(dict(r)) for r in cur.fetchall()]

    def get_by_target(self, target_type: str, limit: int = 30) -> List[AttackRecord]:
        with self.pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM attacks WHERE target_type ILIKE %s LIMIT %s",
                (f"%{target_type}%", limit),
            )
            return [self._row_to_record(dict(r)) for r in cur.fetchall()]

    def list_categories(self) -> List[Dict[str, Any]]:
        with self.pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT category, COUNT(*) AS count FROM attacks GROUP BY category ORDER BY count DESC"
            )
            return [dict(r) for r in cur.fetchall()]

    def list_mitre_techniques(self) -> List[Dict[str, Any]]:
        with self.pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT mitre_technique, COUNT(*) AS count FROM attacks GROUP BY mitre_technique ORDER BY count DESC LIMIT 100"
            )
            return [dict(r) for r in cur.fetchall()]

    def list_tools(self) -> List[Dict[str, str]]:
        """Extract and deduplicate tools across all records."""
        with self.pg.cursor() as cur:
            cur.execute("SELECT tools_used FROM attacks WHERE tools_used != ''")
            tool_freq: Dict[str, int] = {}
            for (tools_raw,) in cur.fetchall():
                for tool in tools_raw.split(","):
                    tool = tool.strip(" -•\n")
                    if len(tool) > 1:
                        tool_freq[tool] = tool_freq.get(tool, 0) + 1
        return [
            {"tool": t, "frequency": c}
            for t, c in sorted(tool_freq.items(), key=lambda x: -x[1])
        ]
