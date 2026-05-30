-- Apply on existing Postgres volumes (init.sql only runs on first container create).
-- Example: docker compose exec postgres psql -U opsec -d attack_db -f /path/in/container
-- Or: psql "$POSTGRES_DSN" -f config/migrations/001_engagements_payload.sql

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Fresh table if missing entirely
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

ALTER TABLE engagements ADD COLUMN IF NOT EXISTS source VARCHAR(64);
ALTER TABLE engagements ADD COLUMN IF NOT EXISTS payload JSONB DEFAULT '{}'::jsonb;

-- Migrate legacy normalized JSONB columns into payload (if present from older orchestrator schema)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'engagements' AND column_name = 'attack_chains'
  ) THEN
    UPDATE engagements
    SET payload = COALESCE(payload, '{}'::jsonb) || jsonb_strip_nulls(jsonb_build_object(
      'id', id,
      'target', target,
      'status', status,
      'aggression_level', aggression_level,
      'boundary_profile', boundary_profile,
      'scan_session', scan_session,
      'attack_chains', attack_chains,
      'opsec_reports', opsec_reports,
      'opsec_audit', opsec_audit,
      'analysis_overseer', analysis_overseer,
      'ai_summary', ai_summary,
      'log', log,
      'started_at', started_at,
      'completed_at', completed_at,
      'error', error
    ))
    WHERE payload IS NULL OR payload = '{}'::jsonb;
  END IF;
END $$;

UPDATE engagements SET source = COALESCE(source, payload->>'source')
WHERE source IS NULL AND payload ? 'source';

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
