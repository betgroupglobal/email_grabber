"""
Engagement persistence store for PostgreSQL.

Provides CRUD operations for engagement data persistence.
"""
from __future__ import annotations

import json
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor, Json

from engagement_schema import initialize_engagement_schema


class EngagementStore:
    """PostgreSQL-based engagement store."""
    
    def __init__(self, postgres_dsn: str):
        """Initialize the engagement store with PostgreSQL connection."""
        self.conn = psycopg2.connect(postgres_dsn)
        self.conn.autocommit = True
        
        # Initialize schema
        initialize_engagement_schema(self.conn)
    
    def create_engagement(self, engagement_data: Dict[str, Any]) -> str:
        """Create a new engagement."""
        engagement_id = engagement_data.get('id', str(uuid.uuid4()))
        
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO engagements (
                    id, target, status, aggression_level, boundary_profile,
                    scan_session, attack_chains, opsec_reports, opsec_audit,
                    analysis_overseer, ai_summary, log, started_at, error
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                engagement_id,
                engagement_data.get('target'),
                engagement_data.get('status', 'pending'),
                engagement_data.get('aggression_level', 1),
                Json(engagement_data.get('boundary_profile')),
                Json(engagement_data.get('scan_session')),
                Json(engagement_data.get('attack_chains')),
                Json(engagement_data.get('opsec_reports')),
                Json(engagement_data.get('opsec_audit')),
                Json(engagement_data.get('analysis_overseer')),
                engagement_data.get('ai_summary'),
                Json(engagement_data.get('log', [])),
                engagement_data.get('started_at', datetime.utcnow()),
                engagement_data.get('error')
            ))
        
        return engagement_id
    
    def get_engagement(self, engagement_id: str) -> Optional[Dict[str, Any]]:
        """Get an engagement by ID."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM engagements WHERE id = %s", (engagement_id,))
            row = cur.fetchone()
            
            if not row:
                return None
            
            # Convert to dict and handle JSONB fields
            result = dict(row)
            for field in ['boundary_profile', 'scan_session', 'attack_chains', 
                         'opsec_reports', 'opsec_audit', 'analysis_overseer', 'log']:
                if result.get(field) is not None:
                    result[field] = dict(result[field]) if isinstance(result[field], dict) else result[field]
            
            return result
    
    def update_engagement(self, engagement_id: str, updates: Dict[str, Any]) -> bool:
        """Update an engagement."""
        if not updates:
            return False
        
        # Build dynamic UPDATE query
        set_clauses = []
        values = []
        
        for key, value in updates.items():
            if key in ['boundary_profile', 'scan_session', 'attack_chains', 
                      'opsec_reports', 'opsec_audit', 'analysis_overseer', 'log']:
                set_clauses.append(f"{key} = %s")
                values.append(Json(value))
            else:
                set_clauses.append(f"{key} = %s")
                values.append(value)
        
        if not set_clauses:
            return False
        
        values.append(engagement_id)
        
        query = f"""
            UPDATE engagements 
            SET {', '.join(set_clauses)} 
            WHERE id = %s
        """
        
        with self.conn.cursor() as cur:
            cur.execute(query, values)
            return cur.rowcount > 0
    
    def delete_engagement(self, engagement_id: str) -> bool:
        """Delete an engagement."""
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM engagements WHERE id = %s", (engagement_id,))
            return cur.rowcount > 0
    
    def list_engagements(
        self, 
        limit: int = 50, 
        offset: int = 0,
        status: Optional[str] = None,
        target: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List engagements with optional filters."""
        conditions = []
        values = []
        param_count = 0
        
        if status:
            param_count += 1
            conditions.append(f"status = ${param_count}")
            values.append(status)
        
        if target:
            param_count += 1
            conditions.append(f"target ILIKE ${param_count}")
            values.append(f"%{target}%")
        
        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)
        
        values.extend([limit, offset])
        
        query = f"""
            SELECT * FROM engagements 
            {where_clause}
            ORDER BY started_at DESC 
            LIMIT %s OFFSET %s
        """
        
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, values)
            rows = cur.fetchall()
            
            results = []
            for row in rows:
                result = dict(row)
                for field in ['boundary_profile', 'scan_session', 'attack_chains', 
                             'opsec_reports', 'opsec_audit', 'analysis_overseer', 'log']:
                    if result.get(field) is not None:
                        result[field] = dict(result[field]) if isinstance(result[field], dict) else result[field]
                results.append(result)
            
            return results
    
    def add_log_entry(self, engagement_id: str, log_entry: Dict[str, Any]) -> bool:
        """Add a log entry to an engagement's log."""
        engagement = self.get_engagement(engagement_id)
        if not engagement:
            return False
        
        logs = engagement.get('log', [])
        logs.append(log_entry)
        
        return self.update_engagement(engagement_id, {'log': logs})
    
    def update_status(self, engagement_id: str, status: str) -> bool:
        """Update engagement status."""
        updates = {'status': status}
        if status in ['complete', 'error']:
            updates['completed_at'] = datetime.utcnow()
        
        return self.update_engagement(engagement_id, updates)
    
    def get_active_engagements(self) -> List[Dict[str, Any]]:
        """Get all active (non-completed, non-error) engagements."""
        return self.list_engagements(
            limit=100,
            status='pending'  # You might want to use multiple statuses
        )
    
    def cleanup_old_engagements(self, days: int = 30) -> int:
        """Delete engagements older than specified days."""
        with self.conn.cursor() as cur:
            cur.execute("""
                DELETE FROM engagements 
                WHERE completed_at < NOW() - INTERVAL '%s days'
                OR (started_at < NOW() - INTERVAL '%s days' AND status = 'pending')
            """, (days, days))
            return cur.rowcount
    
    def get_engagement_stats(self) -> Dict[str, Any]:
        """Get engagement statistics."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                    COUNT(CASE WHEN status = 'scanning' THEN 1 END) as scanning,
                    COUNT(CASE WHEN status = 'building_vectors' THEN 1 END) as building_vectors,
                    COUNT(CASE WHEN status = 'complete' THEN 1 END) as complete,
                    COUNT(CASE WHEN status = 'error' THEN 1 END) as error,
                    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration_seconds
                FROM engagements
            """)
            return dict(cur.fetchone())
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()