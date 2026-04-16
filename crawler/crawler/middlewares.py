"""Spider middlewares."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

import tldextract
from scrapy import Request, Spider
from scrapy.exceptions import IgnoreRequest

logger = logging.getLogger(__name__)


def _load_blacklist() -> set[str]:
    path = Path(__file__).with_name("blacklist.txt")
    domains: set[str] = set()
    if not path.exists():
        return domains
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        domains.add(line.lower())
    return domains


_BLACKLIST = _load_blacklist()


def is_blacklisted(url: str) -> bool:
    """True if `url`'s registered domain (or any parent) is in the blacklist."""
    ext = tldextract.extract(url)
    parts: list[str] = []
    if ext.domain and ext.suffix:
        parts.append(f"{ext.domain}.{ext.suffix}".lower())
    if ext.suffix:
        parts.append(ext.suffix.lower())
    return any(p in _BLACKLIST for p in parts)


class BlacklistMiddleware:
    """Drops requests to blacklisted domains (regulators, gov.au, etc.)."""

    def process_start_requests(
        self, start_requests: Iterable[Request], spider: Spider
    ) -> Iterable[Request]:
        for req in start_requests:
            if is_blacklisted(req.url):
                logger.warning("Skipping blacklisted start URL: %s", req.url)
                continue
            yield req

    def process_spider_output(
        self,
        response,
        result,
        spider: Spider,  # type: ignore[no-untyped-def]
    ):
        for item_or_request in result:
            if isinstance(item_or_request, Request) and is_blacklisted(item_or_request.url):
                logger.debug("Dropping blacklisted link: %s", item_or_request.url)
                raise IgnoreRequest(f"blacklisted domain: {item_or_request.url}")
            yield item_or_request
