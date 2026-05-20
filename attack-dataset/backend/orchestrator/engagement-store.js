/**
 * PostgreSQL engagement store — full document in payload JSONB.
 */

const { Pool } = require("pg");

const POSTGRES_DSN =
  process.env.POSTGRES_DSN || "postgresql://opsec:opsec@localhost:5432/attack_db";

const SCHEMA_SQL = `
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
`;

const LEGACY_MIGRATION_SQL = `
ALTER TABLE engagements ADD COLUMN IF NOT EXISTS source VARCHAR(64);
ALTER TABLE engagements ADD COLUMN IF NOT EXISTS payload JSONB DEFAULT '{}'::jsonb;
`;

function parsePayload(row) {
  if (!row) return null;
  let payload = row.payload;
  if (typeof payload === "string") {
    try {
      payload = JSON.parse(payload);
    } catch {
      payload = {};
    }
  }
  if (!payload || typeof payload !== "object") payload = {};
  const engagement = { ...payload, id: row.id || payload.id };
  if (!engagement.target) engagement.target = row.target;
  if (!engagement.status) engagement.status = row.status;
  if (!engagement.source && row.source) engagement.source = row.source;
  if (!engagement.started_at && row.started_at) {
    engagement.started_at =
      row.started_at instanceof Date ? row.started_at.toISOString() : row.started_at;
  }
  return engagement;
}

function extractIndexFields(engagement) {
  const id = String(engagement.id || "").trim();
  const target = String(engagement.target || "unknown").trim() || "unknown";
  const status = String(engagement.status || "pending").trim() || "pending";
  const source = engagement.source ? String(engagement.source).slice(0, 64) : null;
  let startedAt = engagement.started_at ? new Date(engagement.started_at) : new Date();
  if (Number.isNaN(startedAt.getTime())) startedAt = new Date();
  return { id, target, status, source, startedAt };
}

class EngagementStore {
  constructor() {
    this.pool = new Pool({
      connectionString: POSTGRES_DSN,
      max: 20,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 5000,
    });
    this.ready = this._bootstrap();
  }

  async _bootstrap(retries = 12, delayMs = 2000) {
    for (let attempt = 1; attempt <= retries; attempt++) {
      try {
        const client = await this.pool.connect();
        try {
          await client.query(SCHEMA_SQL);
          try {
            await client.query(LEGACY_MIGRATION_SQL);
          } catch {
            /* non-fatal */
          }
          console.log("[engagement-store] Schema ready");
          return;
        } finally {
          client.release();
        }
      } catch (error) {
        if (attempt === retries) {
          console.error("[engagement-store] Schema bootstrap failed:", error.message);
          throw error;
        }
        console.warn(
          `[engagement-store] Postgres not ready (attempt ${attempt}/${retries}), retrying…`
        );
        await new Promise((r) => setTimeout(r, delayMs));
      }
    }
  }

  async upsertEngagement(engagement) {
    await this.ready;
    const doc = { ...engagement };
    const { id, target, status, source, startedAt } = extractIndexFields(doc);
    if (!id) throw new Error("engagement.id is required");

    doc.id = id;
    doc.target = target;
    doc.status = status;
    if (source) doc.source = source;

    const query = `
      INSERT INTO engagements (id, target, status, source, payload, started_at, updated_at)
      VALUES ($1, $2, $3, $4, $5::jsonb, $6, NOW())
      ON CONFLICT (id) DO UPDATE SET
        target = EXCLUDED.target,
        status = EXCLUDED.status,
        source = EXCLUDED.source,
        payload = EXCLUDED.payload,
        updated_at = NOW()
      RETURNING *
    `;

    const result = await this.pool.query(query, [
      id,
      target,
      status,
      source,
      JSON.stringify(doc),
      startedAt,
    ]);
    return parsePayload(result.rows[0]);
  }

  /** @deprecated use upsertEngagement */
  async createEngagement(engagement) {
    return this.upsertEngagement(engagement);
  }

  async getEngagement(engagementId) {
    await this.ready;
    const result = await this.pool.query("SELECT * FROM engagements WHERE id = $1", [
      engagementId,
    ]);
    if (result.rows.length === 0) return null;
    return parsePayload(result.rows[0]);
  }

  async updateEngagement(engagementId, updates) {
    const existing = await this.getEngagement(engagementId);
    if (!existing) return false;
    return Boolean(await this.upsertEngagement({ ...existing, ...updates, id: engagementId }));
  }

  async deleteEngagement(engagementId) {
    await this.ready;
    const result = await this.pool.query("DELETE FROM engagements WHERE id = $1", [
      engagementId,
    ]);
    return result.rowCount > 0;
  }

  async listEngagements(options = {}) {
    await this.ready;
    const { limit = 1000, offset = 0, status, target } = options;
    const conditions = [];
    const values = [];
    let paramCount = 0;

    if (status) {
      paramCount++;
      conditions.push(`status = $${paramCount}`);
      values.push(status);
    }

    if (target) {
      paramCount++;
      conditions.push(`target ILIKE $${paramCount}`);
      values.push(`%${target}%`);
    }

    const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";
    values.push(limit, offset);

    const query = `
      SELECT * FROM engagements
      ${whereClause}
      ORDER BY COALESCE(started_at, updated_at) DESC
      LIMIT $${paramCount + 1} OFFSET $${paramCount + 2}
    `;

    const result = await this.pool.query(query, values);
    return result.rows.map(parsePayload);
  }

  async addLogEntry(engagementId, logEntry) {
    const engagement = await this.getEngagement(engagementId);
    if (!engagement) return false;
    const logs = Array.isArray(engagement.log) ? engagement.log : [];
    logs.push(logEntry);
    await this.upsertEngagement({ ...engagement, log: logs });
    return true;
  }

  async updateStatus(engagementId, status) {
    const engagement = await this.getEngagement(engagementId);
    if (!engagement) return false;
    const updates = { status };
    if (status === "complete" || status === "completed" || status === "error") {
      updates.completed_at = new Date().toISOString();
    }
    await this.upsertEngagement({ ...engagement, ...updates });
    return true;
  }

  async getEngagementStats() {
    await this.ready;
    const result = await this.pool.query(`
      SELECT
        COUNT(*)::int AS total,
        COUNT(*) FILTER (WHERE status IN ('pending', 'starting'))::int AS pending,
        COUNT(*) FILTER (WHERE status = 'scanning')::int AS scanning,
        COUNT(*) FILTER (WHERE status = 'building_vectors')::int AS building_vectors,
        COUNT(*) FILTER (WHERE status IN ('complete', 'completed'))::int AS complete,
        COUNT(*) FILTER (WHERE status IN ('error', 'failed'))::int AS error
      FROM engagements
    `);
    return result.rows[0];
  }

  async cleanupOldEngagements(days = 30) {
    await this.ready;
    const result = await this.pool.query(
      `DELETE FROM engagements
       WHERE (payload->>'completed_at')::timestamptz < NOW() - ($1::text || ' days')::interval
          OR (started_at < NOW() - ($1::text || ' days')::interval AND status IN ('pending', 'starting'))`,
      [String(days)]
    );
    return result.rowCount;
  }

  async close() {
    await this.pool.end();
  }
}

module.exports = EngagementStore;
