"""Scrapy items. Strictly non-PII."""

from __future__ import annotations

import scrapy


class OperatorItem(scrapy.Item):
    """A summary of one operator domain.

    No emails. No phone numbers. No personal names. Only public commercial
    metadata that an analyst could write down by visiting the homepage.
    """

    domain = scrapy.Field()  # str, e.g. "example.com.au"
    operator_name = scrapy.Field()  # str | None
    is_au_facing = scrapy.Field()  # bool | None
    license_refs = scrapy.Field()  # list[str]
    software_providers = scrapy.Field()  # list[str]
    promo_offers = scrapy.Field()  # list[dict[str, str]]
    source_url = scrapy.Field()  # str
