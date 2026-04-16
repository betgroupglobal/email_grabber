"""Scrapy settings — conservative, identifying, robots-respecting."""

from __future__ import annotations

import os

BOT_NAME = "market_intel"

SPIDER_MODULES = ["crawler.spiders"]
NEWSPIDER_MODULE = "crawler.spiders"

# --- Compliance / politeness ---------------------------------------------------

# Always identify ourselves; never spoof a real browser.
USER_AGENT = os.environ.get(
    "CRAWLER_USER_AGENT",
    "BetGroupResearchBot/0.1 (+mailto:research@betgroupglobal.example)",
)

ROBOTSTXT_OBEY = True
HTTPERROR_ALLOWED_CODES: list[int] = []

CONCURRENT_REQUESTS = int(os.environ.get("CRAWLER_CONCURRENT_REQUESTS", "4"))
CONCURRENT_REQUESTS_PER_DOMAIN = 2
DOWNLOAD_DELAY = float(os.environ.get("CRAWLER_DOWNLOAD_DELAY", "1.0"))
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 10.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

# Cap depth so we don't accidentally crawl the entire web.
DEPTH_LIMIT = 3

# --- Caching -------------------------------------------------------------------

HTTPCACHE_ENABLED = False  # enable manually for development if useful

# --- Scrapy-Redis distributed queue (off by default) ---------------------------
# Enable by setting CRAWLER_USE_REDIS=1 in the environment. Off by default so
# `scrapy crawl market_intel -a start_url=...` works as a single-process job.

if os.environ.get("CRAWLER_USE_REDIS") == "1":
    SCHEDULER = "scrapy_redis.scheduler.Scheduler"
    DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"
    SCHEDULER_PERSIST = True
    REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

# --- Pipelines / middlewares ---------------------------------------------------

ITEM_PIPELINES = {
    "crawler.pipelines.OperatorAggregatorPipeline": 100,
    "crawler.pipelines.PostgresPipeline": 200,
}

SPIDER_MIDDLEWARES = {
    "crawler.middlewares.BlacklistMiddleware": 100,
}

# --- Feeds ---------------------------------------------------------------------
# Always also dump to JSONL so a run is inspectable without DB access.

FEEDS = {
    "data/operators-%(time)s.jsonl": {
        "format": "jsonlines",
        "encoding": "utf8",
        "store_empty": False,
    },
}

# Required for forwards-compatibility in Scrapy 2.11+
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"
LOG_LEVEL = os.environ.get("CRAWLER_LOG_LEVEL", "INFO")
