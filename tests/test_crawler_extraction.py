"""Pure-function tests for the market_intel spider's extraction helpers.

These don't require Scrapy's twisted reactor or network — they only test
the regex/heuristic helpers and the blacklist.
"""

from __future__ import annotations


def test_blacklist_blocks_gov_au() -> None:
    from crawler.crawler.middlewares import is_blacklisted

    assert is_blacklisted("https://acma.gov.au/contact")
    assert is_blacklisted("https://www.acma.gov.au/contact")
    assert is_blacklisted("https://nsw.gov.au/")
    # Non-gov gambling site should not be blacklisted.
    assert not is_blacklisted("https://example.com.au/")


def test_license_extraction() -> None:
    from crawler.crawler.spiders.market_intel import MarketIntelSpider

    text = "Licensed by the Northern Territory Racing Commission (NTRWC). Curacao 8048/JAZ."
    found = MarketIntelSpider._find_licenses(text)
    assert any("NTRWC" in f for f in found)
    assert any("Curacao" in f or "Curaçao" in f for f in found)


def test_provider_extraction() -> None:
    from crawler.crawler.spiders.market_intel import MarketIntelSpider

    text = "Powered by Pragmatic Play, BetSoft and NetEnt."
    providers = MarketIntelSpider._find_providers(text)
    assert {"Pragmatic Play", "BetSoft", "NetEnt"}.issubset(providers)


def test_au_facing_signal() -> None:
    from crawler.crawler.spiders.market_intel import MarketIntelSpider

    assert MarketIntelSpider._is_au_facing("punter.com.au", "") is True
    assert MarketIntelSpider._is_au_facing("offshore.com", "Live AFL odds") is True
    assert MarketIntelSpider._is_au_facing("offshore.com", "Hello world") is None


def test_promo_extraction_caps_at_10() -> None:
    from crawler.crawler.spiders.market_intel import MarketIntelSpider

    text = "welcome bonus " * 50
    promos = MarketIntelSpider._find_promos(text)
    assert len(promos) <= 10
    assert all("snippet" in p for p in promos)
