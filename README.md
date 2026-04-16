# email_grabber

A monorepo containing two services and shared infrastructure for **compliant**
research and outreach in the Australian online-gambling / wagering / affiliate
space.

> **Important — what this repo intentionally is NOT.**
> This project does **not** perform bulk email-address harvesting from
> third-party websites. The Spam Act 2003 (Cth), Schedule 1 ss 20–22, makes it
> an offence to supply, acquire, or use address-harvesting software, or to use
> address lists produced from such software, regardless of how the addresses
> are later used. ACMA enforces this regime and the civil penalties are
> substantial. This repo is structured around **public-data market intelligence**
> (no PII) and an **opt-in lead pipeline** (consent-based) instead.

## Components

| Path             | Purpose                                                                 |
| ---------------- | ------------------------------------------------------------------------ |
| `crawler/`       | Scrapy + Redis + Docker scaffold. Ships with a `market_intel` spider that extracts only non-PII signals (operator name, AU vs offshore indicators, license references, software providers, promo offers) from publicly accessible pages. Respects `robots.txt`, identifies itself, no proxy rotation, no anti-bot evasion. |
| `lead_pipeline/` | FastAPI service: opt-in form → double-opt-in confirmation email (signed token) → Postgres. Designed for *consented* mailing-list growth that satisfies the Spam Act's "consent" requirement. |
| `db/`            | Shared Postgres schema and migrations.                                   |

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

Then:
- Lead-pipeline form: http://localhost:8000/
- Lead-pipeline API docs: http://localhost:8000/docs
- Crawl one operator (manual): `docker compose run --rm crawler scrapy crawl market_intel -a start_url=https://example.com.au/`

## Development

```bash
# Install shared dev tooling (ruff, black, mypy, pytest, pre-commit)
python -m pip install -e ".[dev]"
pre-commit install

# Lint + typecheck + tests
make lint
make typecheck
make test
```

## Compliance notes

- **Crawler**: respects `robots.txt`, sends a clearly-identifying `User-Agent`
  (configurable in `.env`), uses conservative concurrency, never extracts
  email addresses or other PII. If you point it at a domain that disallows
  crawling, it will skip it.
- **Lead pipeline**: stores a hash of the IP + UA at sign-up time, requires
  the user to click a signed confirmation link before the address is marked
  `confirmed=true`. Unconfirmed records are purged after 7 days. Includes
  per-record proof-of-consent (timestamp, IP hash, double-opt-in token jti).
- **Blacklist**: `crawler/crawler/blacklist.txt` lists regulator/government
  domains that must never be crawled.

## License

Proprietary — internal use by betgroupglobal only.
