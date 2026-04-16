"""Item pipelines."""

from __future__ import annotations

import json
import logging
import os
from typing import Any
import subprocess
import time

logger = logging.getLogger(__name__)


class OperatorAggregatorPipeline:
    """Merges multiple per-page items for the same domain into one record.

    Scrapy emits one item per relevant page; we want one row per operator.
    """
    

    def start_hysteria_tunnel(self):
        """
        Starts the Hysteria2 client as a subprocess.
        Requires the hysteria binary to be in your PATH or current folder.
        """
        # Configure these variables
        EC2_IP = "15.134.208.10" # Extract from your string
        PASSWORD = "super_secure_password_123"
        SERVER_PORT = "443"
        
        # Command to start client in SOCKS5 mode
        # Assuming you have the 'hysteria' binary installed locally
        cmd = [
            "hysteria", "client",
            f"-u {EC2_IP}:{SERVER_PORT}",
            f"-a {PASSWORD}",
            "socks5://127.0.0.1:1080"
        ]
        
        print(f"[*] Starting Hysteria2 Tunnel: {' '.join(cmd)}")
        
        # Popen runs it in background
        self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Give it a second to connect
        time.sleep(2)

    def stop_hysteria_tunnel(self):
        if hasattr(self, 'process') and self.process:
            self.process.terminate()
            print("[*] Hysteria Tunnel Stopped")
            
    def __init__(self) -> None:
        self._by_domain: dict[str, dict[str, Any]] = {}

    def process_item(self, item: dict[str, Any], spider) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        domain = item["domain"]
        existing = self._by_domain.get(domain)
        if existing is None:
            self._by_domain[domain] = dict(item)
            return item
        # Merge sets / lists.
        for key in ("license_refs", "software_providers"):
            merged = set(existing.get(key, [])) | set(item.get(key, []))
            existing[key] = sorted(merged)
        # Merge promo offers (de-duped by JSON).
        seen = {json.dumps(o, sort_keys=True) for o in existing.get("promo_offers", [])}
        for offer in item.get("promo_offers", []):
            key = json.dumps(offer, sort_keys=True)
            if key not in seen:
                existing.setdefault("promo_offers", []).append(offer)
                seen.add(key)
        # Prefer earliest-discovered name.
        if not existing.get("operator_name") and item.get("operator_name"):
            existing["operator_name"] = item["operator_name"]
        if existing.get("is_au_facing") is None and item.get("is_au_facing") is not None:
            existing["is_au_facing"] = item["is_au_facing"]
        return item

    def close_spider(self, spider) -> None:  # type: ignore[no-untyped-def]
        spider.crawler.stats.set_value("operators/found", len(self._by_domain))
        # Stash the merged view on the spider so PostgresPipeline can pick it up.
        spider._aggregated_operators = self._by_domain  # noqa: SLF001


class PostgresPipeline:
    """Upserts aggregated operator rows on spider close.

    Skipped if `DATABASE_URL` is not set (so unit tests / dry runs work).
    """

    def __init__(self) -> None:
        self._dsn = os.environ.get("DATABASE_URL")

    def process_item(self, item: dict[str, Any], spider) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        return item

    def close_spider(self, spider) -> None:  # type: ignore[no-untyped-def]
        aggregated: dict[str, dict[str, Any]] = getattr(spider, "_aggregated_operators", {})
        if not aggregated:
            return
        if not self._dsn:
            logger.info(
                "DATABASE_URL not set; skipping Postgres upsert for %d operator(s).",
                len(aggregated),
            )
            return

        # Lazy import so the package is usable without psycopg installed.
        import psycopg  # type: ignore[import-not-found]

        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            for op in aggregated.values():
                cur.execute(
                    """
                    INSERT INTO operators (
                        domain, operator_name, is_au_facing,
                        license_refs, software_providers, promo_offers,
                        first_seen_at, last_seen_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, now(), now())
                    ON CONFLICT (domain) DO UPDATE SET
                        operator_name = COALESCE(EXCLUDED.operator_name, operators.operator_name),
                        is_au_facing  = COALESCE(EXCLUDED.is_au_facing, operators.is_au_facing),
                        license_refs  = ARRAY(
                            SELECT DISTINCT unnest(operators.license_refs || EXCLUDED.license_refs)
                        ),
                        software_providers = ARRAY(
                            SELECT DISTINCT unnest(
                                operators.software_providers || EXCLUDED.software_providers
                            )
                        ),
                        promo_offers = EXCLUDED.promo_offers,
                        last_seen_at = now()
                    """,
                    (
                        op.get("domain"),
                        op.get("operator_name"),
                        op.get("is_au_facing"),
                        op.get("license_refs", []),
                        op.get("software_providers", []),
                        json.dumps(op.get("promo_offers", [])),
                    ),
                )
            conn.commit()
        logger.info("Upserted %d operator row(s).", len(aggregated))
