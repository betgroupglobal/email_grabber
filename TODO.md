# Email Grabber Combination Task - Progress Tracker

## Approved Plan Steps (from breakdown):

1. **[PENDING]** Create/Update `crawler/crawler/spiders/spider_hysteria.py` with ported TargetedSpider logic as Scrapy spider (TARGET_DOMAINS start_urls, email extraction/scoring, internal links, depth limit).
2. **[PENDING]** Edit `crawler/crawler/items.py` to add `EmailItem` (domain, email, priority_score, source_url, keywords).
3. **[PENDING]** Edit `run.py` to launch `scrapy crawl hysteria` with domains arg, keep banner.
4. **[PENDING]** Edit `crawler/crawler/settings.py` to add ITEM_PIPELINES/FEEDS for emails (vip_emails.jsonl + txt dedup).
5. **[PENDING]** Update `crawler/requirements.txt` for new deps (aiohttp, bs4, lxml if missing).
6. **[PENDING]** Test: `python run.py`, verify output on 1 domain.
7. **[PENDING]** Full run + Hysteria integration if needed.

**Next Action**: Implement step 1 (spider_hysteria.py). Mark complete upon confirmation.

**Status**: 0/7 complete
