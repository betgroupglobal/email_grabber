-- Schema for email_grabber. Loaded by docker-entrypoint-initdb.d on first start.

-- ---------------------------------------------------------------------------
-- Lead pipeline (consented opt-in mailing list)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS leads (
    id              BIGSERIAL PRIMARY KEY,
    email           CITEXT      NOT NULL UNIQUE,
    name            TEXT,
    company         TEXT,
    -- consent / proof-of-consent fields (Spam Act 2003 (Cth))
    confirmed       BOOLEAN     NOT NULL DEFAULT FALSE,
    consent_source  TEXT        NOT NULL,           -- e.g. "web_form:/signup"
    ip_hash         TEXT        NOT NULL,           -- sha256(ip + secret)
    user_agent      TEXT        NOT NULL,
    token_jti       TEXT        NOT NULL UNIQUE,    -- the confirmation token id
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    confirmed_at    TIMESTAMPTZ,
    unsubscribed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS leads_confirmed_idx
    ON leads (confirmed) WHERE confirmed IS TRUE;

CREATE INDEX IF NOT EXISTS leads_unconfirmed_created_idx
    ON leads (created_at) WHERE confirmed IS FALSE;

-- citext for case-insensitive email uniqueness
CREATE EXTENSION IF NOT EXISTS citext;

-- ---------------------------------------------------------------------------
-- Market-intel crawler (non-PII)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS operators (
    id              BIGSERIAL PRIMARY KEY,
    domain          TEXT        NOT NULL UNIQUE,
    operator_name   TEXT,
    is_au_facing    BOOLEAN,                          -- best-guess from TLD/content
    license_refs    TEXT[]      NOT NULL DEFAULT '{}',-- e.g. {"NTRWC", "Curacao 8048"}
    software_providers TEXT[]   NOT NULL DEFAULT '{}',-- e.g. {"Pragmatic Play", "BetSoft"}
    promo_offers    JSONB       NOT NULL DEFAULT '[]'::jsonb,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS operators_au_facing_idx ON operators (is_au_facing);

CREATE TABLE IF NOT EXISTS crawl_runs (
    id              BIGSERIAL PRIMARY KEY,
    spider          TEXT        NOT NULL,
    start_url       TEXT        NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    pages_crawled   INTEGER     NOT NULL DEFAULT 0,
    operators_found INTEGER     NOT NULL DEFAULT 0
);
