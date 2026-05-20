"""
Engagement persistence schema for PostgreSQL.

Defines the database schema for storing engagement data
persistently instead of in-memory.
"""

# ── Engagement Table Schema ─────────────────────────────────────────────────────

ENGAGEMENT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS engagements (
    id VARCHAR(255) PRIMARY KEY,
    target VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    aggression_level INTEGER DEFAULT 1,
    boundary_profile JSONB,
    scan_session JSONB,
    attack_chains JSONB,
    opsec_reports JSONB,
    opsec_audit JSONB,
    analysis_overseer JSONB,
    ai_summary TEXT,
    log JSONB DEFAULT '[]'::jsonb,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_engagements_target ON engagements(target);
CREATE INDEX IF NOT EXISTS idx_engagements_status ON engagements(status);
CREATE INDEX IF NOT EXISTS idx_engagements_started_at ON engagements(started_at);
CREATE INDEX IF NOT EXISTS idx_engagements_user_id ON engagements((boundary_profile->>'user_id'));

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER IF NOT EXISTS update_engagements_updated_at 
    BEFORE UPDATE ON engagements 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
"""

# ── User Sessions Table Schema (for future session management) ─────────────────

USER_SESSIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS user_sessions (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    engagement_id VARCHAR(255),
    session_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    FOREIGN KEY (engagement_id) REFERENCES engagements(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_engagement_id ON user_sessions(engagement_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at);
"""

# ── API Keys Table Schema (for future API key management) ───────────────────────

API_KEYS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS api_keys (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255),
    scopes JSONB DEFAULT '[]'::jsonb,
    is_active BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON api_keys(is_active);
"""

# ── Audit Log Table Schema (for security auditing) ────────────────────────────

AUDIT_LOG_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS audit_logs (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255),
    engagement_id VARCHAR(255),
    action VARCHAR(255) NOT NULL,
    resource_type VARCHAR(255),
    resource_id VARCHAR(255),
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    FOREIGN KEY (engagement_id) REFERENCES engagements(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_engagement_id ON audit_logs(engagement_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
"""

# ── Schema Initialization Function ───────────────────────────────────────────────

def initialize_engagement_schema(conn):
    """Initialize all engagement-related database tables."""
    with conn.cursor() as cur:
        # Create engagements table
        cur.execute(ENGAGEMENT_TABLE_SQL)
        
        # Create user sessions table (for future use)
        cur.execute(USER_SESSIONS_TABLE_SQL)
        
        # Create API keys table (for future use)
        cur.execute(API_KEYS_TABLE_SQL)
        
        # Create audit log table (for future use)
        cur.execute(AUDIT_LOG_TABLE_SQL)
    
    conn.commit()
    print("Engagement schema initialized successfully")