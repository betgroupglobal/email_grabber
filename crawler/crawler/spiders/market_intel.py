"""Market-intel spider.

Extracts only *non-PII* commercial metadata from publicly accessible pages of
operator domains. Specifically:

- Operator name (from <title> / og:site_name)
- AU-facing signal (TLD heuristic + content keywords)
- License references (e.g. "NTRWC", "Curacao 8048", "Malta MGA/B2C/...")
- Software providers (e.g. "Pragmatic Play", "BetSoft", "Microgaming")
- Promo offers (free-text snippets near "bonus" / "free spins")

Hard rules:

- Respects ``robots.txt`` (via Scrapy's ``ROBOTSTXT_OBEY = True``).
- Stays on the start domain (no off-domain crawling).
- Caps depth via ``DEPTH_LIMIT`` in settings.
- Drops blacklisted domains via ``BlacklistMiddleware``.
- Never extracts emails, phone numbers, or personal names.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from urllib.parse import urlparse

import scrapy
import tldextract
from scrapy.http import Response
from scrapy.linkextractors import LinkExtractor

from ..items import OperatorItem
from ..middlewares import is_blacklisted

# License authority hints — match acronyms and short references, not personal data.
LICENSE_PATTERNS = [
    re.compile(r"\bNTRWC\b", re.I),
    re.compile(r"\bNorthern\s+Territory\s+Racing\s+Commission\b", re.I),
    re.compile(r"\bMGA\s*/?\s*[A-Z0-9/-]+", re.I),
    re.compile(r"\bMalta\s+Gaming\s+Authority\b", re.I),
    re.compile(r"\bCura[çc]ao\s+\d{3,5}/?[A-Z]{0,4}", re.I),
    re.compile(r"\bUKGC\b", re.I),
    re.compile(r"\bGibraltar\s+Licensing\s+Authority\b", re.I),
    re.compile(r"\bIsle\s+of\s+Man\s+GSC\b", re.I),
]

KNOWN_PROVIDERS = {
    "Pragmatic Play",
    "BetSoft",
    "Microgaming",
    "NetEnt",
    "Evolution",
    "Play'n GO",
    "Playson",
    "Yggdrasil",
    "Quickspin",
    "Push Gaming",
    "Hacksaw Gaming",
    "Nolimit City",
    "Big Time Gaming",
    "Relax Gaming",
    "ELK Studios",
    "Red Tiger",
    "Thunderkick",
    "iSoftBet",
    "Endorphina",
    "Wazdan",
}

AU_KEYWORDS = re.compile(
    r"\b(AFL|NRL|Melbourne\s+Cup|pokies|TAB|Sportsbet|Aussie|Australia(n)?)\b",
    re.I,
)

PROMO_HINTS = re.compile(
    r"(welcome\s+bonus|free\s+spins?|no\s+deposit|matched\s+deposit|cashback)",
    re.I,
)


class MarketIntelSpider(scrapy.Spider):
    name = "market_intel"

    custom_settings = {
        # No off-domain follows; LinkExtractor below also enforces this.
        "DEPTH_LIMIT": 3,
    }

    def __init__(self, start_url: str | None = None, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        if not start_url:
            raise ValueError(
                "market_intel spider requires `start_url` "
                "(e.g. -a start_url=https://example.com.au/)"
            )
        if is_blacklisted(start_url):
            raise ValueError(f"Refusing to crawl blacklisted domain: {start_url}")
        self.start_urls: list[str] = [start_url]
        self.allowed_domains: list[str] = [urlparse(start_url).netloc]
        self._link_extractor = LinkExtractor(
            allow_domains=self.allowed_domains,
            deny_extensions=["pdf", "zip", "exe", "jpg", "jpeg", "png", "gif", "mp4"],
            deny=(r"/api/", r"\?logout", r"\?track=", r"/admin/", r"/cart"),
        )

    def parse(self, response: Response) -> Iterator[scrapy.Request | OperatorItem]:
        if not isinstance(response, scrapy.http.TextResponse):
            return
        yield self._extract_operator(response)
        for link in self._link_extractor.extract_links(response):
            yield response.follow(link, callback=self.parse)

    # -- extraction helpers ----------------------------------------------------

    def _extract_operator(self, response: Response) -> OperatorItem:
        domain = self._registered_domain(response.url)
        text = " ".join(response.css("body *::text").getall())
        title = (response.css("title::text").get() or "").strip()
        og_site = response.css('meta[property="og:site_name"]::attr(content)').get()

        return OperatorItem(
            domain=domain,
            operator_name=(og_site or title or domain).strip()[:200] or None,
            is_au_facing=self._is_au_facing(domain, text),
            license_refs=sorted(self._find_licenses(text)),
            software_providers=sorted(self._find_providers(text)),
            promo_offers=self._find_promos(text),
            source_url=response.url,
        )

    @staticmethod
    def _registered_domain(url: str) -> str:
        ext = tldextract.extract(url)
        return f"{ext.domain}.{ext.suffix}".lower() if ext.suffix else ext.domain.lower()

    @staticmethod
    def _is_au_facing(domain: str, text: str) -> bool | None:
        if domain.endswith(".au"):
            return True
        if AU_KEYWORDS.search(text):
            return True
        return None

    @staticmethod
    def _find_licenses(text: str) -> set[str]:
        found: set[str] = set()
        for pattern in LICENSE_PATTERNS:
            for match in pattern.findall(text):
                # findall returns tuples for groups; flatten to a string.
                if isinstance(match, tuple):
                    match = " ".join(p for p in match if p)
                found.add(match.strip()[:80])
        return {f for f in found if f}

    @staticmethod
    def _find_providers(text: str) -> set[str]:
        return {p for p in KNOWN_PROVIDERS if re.search(rf"\b{re.escape(p)}\b", text, re.I)}

    @staticmethod
    def _find_promos(text: str) -> list[dict[str, str]]:
        offers: list[dict[str, str]] = []
        for match in PROMO_HINTS.finditer(text):
            start = max(0, match.start() - 60)
            end = min(len(text), match.end() + 80)
            snippet = re.sub(r"\s+", " ", text[start:end]).strip()
            offers.append({"keyword": match.group(0).lower(), "snippet": snippet[:240]})
            if len(offers) >= 10:
                break
        return offers
