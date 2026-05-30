"""
Clear offensive tools data from database.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clear_tools_data():
    """Clear all offensive tools data."""
    
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
        
        # Clear tables
        cursor.execute("DELETE FROM offensive_tools")
        deleted_count = cursor.rowcount
        logger.info(f"Deleted {deleted_count} tools from offensive_tools table")
        
        cursor.execute("DELETE FROM tool_recommendations")
        logger.info("Cleared tool_recommendations table")
        
        cursor.execute("DELETE FROM tool_usage_patterns")
        logger.info("Cleared tool_usage_patterns table")
        
        conn.commit()
        logger.info("Database cleared successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to clear database: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    clear_tools_data()