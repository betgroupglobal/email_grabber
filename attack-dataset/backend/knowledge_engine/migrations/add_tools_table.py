"""
Database migration to add offensive tools reference table.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_tools_table():
    """Create the offensive tools reference table."""
    
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'attack_db',
        'user': 'opsec',
        'password': 'opsec'
    }
    
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        # Create tools table
        create_table_query = """
        CREATE TABLE IF NOT EXISTS offensive_tools (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
            category VARCHAR(100) NOT NULL,
            subcategory VARCHAR(100),
            description TEXT,
            opsec_considerations TEXT,
            detection_methods TEXT[],
            mitre_tactic VARCHAR(100),
            mitre_technique_ids TEXT[],
            risk_level VARCHAR(20) DEFAULT 'medium',
            noise_level INTEGER DEFAULT 50,
            stealth_level INTEGER DEFAULT 50,
            popularity_score INTEGER DEFAULT 50,
            requires_auth BOOLEAN DEFAULT FALSE,
            platform VARCHAR(50)[],
            license_type VARCHAR(50),
            repository_url TEXT,
            documentation_url TEXT,
            alternatives TEXT[],
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        cursor.execute(create_table_query)
        logger.info("Created offensive_tools table")
        
        # Create indexes for common queries
        index_queries = [
            "CREATE INDEX IF NOT EXISTS idx_tools_category ON offensive_tools(category);",
            "CREATE INDEX IF NOT EXISTS idx_tools_mitre_tactic ON offensive_tools(mitre_tactic);",
            "CREATE INDEX IF NOT EXISTS idx_tools_risk_level ON offensive_tools(risk_level);",
            "CREATE INDEX IF NOT EXISTS idx_tools_platform ON offensive_tools USING GIN(platform);",
            "CREATE INDEX IF NOT EXISTS idx_tools_detection_methods ON offensive_tools USING GIN(detection_methods);"
        ]
        
        for index_query in index_queries:
            cursor.execute(index_query)
            logger.info(f"Created index: {index_query[:50]}...")
        
        # Create tool recommendations table
        create_recommendations_query = """
        CREATE TABLE IF NOT EXISTS tool_recommendations (
            id SERIAL PRIMARY KEY,
            attack_scenario VARCHAR(255) NOT NULL,
            tool_name VARCHAR(255) NOT NULL REFERENCES offensive_tools(name),
            recommendation_score INTEGER NOT NULL,
            rationale TEXT,
            alternative_tools TEXT[],
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        cursor.execute(create_recommendations_query)
        logger.info("Created tool_recommendations table")
        
        # Create tool_usage_patterns table for analytics
        create_usage_patterns_query = """
        CREATE TABLE IF NOT EXISTS tool_usage_patterns (
            id SERIAL PRIMARY KEY,
            tool_name VARCHAR(255) NOT NULL REFERENCES offensive_tools(name),
            usage_context VARCHAR(255),
            success_rate FLOAT,
            avg_detection_time FLOAT,
            common_defenses TEXT[],
            optimal_timing VARCHAR(100),
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        cursor.execute(create_usage_patterns_query)
        logger.info("Created tool_usage_patterns table")
        
        conn.commit()
        logger.info("Database migration completed successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    create_tools_table()