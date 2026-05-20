-- Initialize PostgreSQL database for OpsecAI
-- This script runs when the postgres container is first created.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

GRANT ALL PRIVILEGES ON DATABASE attack_db TO opsec;

-- Persistent engagements (orchestrator attacks / assessments)
CREATE TABLE IF NOT EXISTS engagements (
    id VARCHAR(255) PRIMARY KEY,
    target VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    source VARCHAR(64),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_engagements_target ON engagements(target);
CREATE INDEX IF NOT EXISTS idx_engagements_status ON engagements(status);
CREATE INDEX IF NOT EXISTS idx_engagements_source ON engagements(source);
CREATE INDEX IF NOT EXISTS idx_engagements_started_at ON engagements(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_engagements_updated_at ON engagements(updated_at DESC);

CREATE OR REPLACE FUNCTION update_engagements_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_engagements_updated_at ON engagements;
CREATE TRIGGER trg_engagements_updated_at
    BEFORE UPDATE ON engagements
    FOR EACH ROW EXECUTE FUNCTION update_engagements_updated_at();
