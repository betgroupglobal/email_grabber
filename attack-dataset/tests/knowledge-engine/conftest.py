"""
Pytest configuration and fixtures for Knowledge Engine tests.
"""
import os
import sys
import pytest
import asyncio
from typing import Generator, AsyncGenerator
from pathlib import Path

# Add parent directory to path for imports
_BACKEND = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(Path(__file__).parent.parent))

# Legacy tests import `config` — load utils/config without pulling qdrant via package __init__
import importlib.util
_config_path = _BACKEND / "knowledge_engine" / "utils" / "config.py"
_config_spec = importlib.util.spec_from_file_location("config", _config_path)
_ke_config = importlib.util.module_from_spec(_config_spec)
_config_spec.loader.exec_module(_ke_config)
# Repo has a top-level `config/` infra folder (namespace package) — always use KE utils.config
sys.modules["config"] = _ke_config

from fastapi.testclient import TestClient
import psycopg2
from psycopg2.extras import RealDictCursor


def _import_ke(name: str):
    import importlib
    return importlib.import_module(name)

# Configuration from environment variables
POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://opsec:opsec@localhost:5432/attack_db")
QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "attacks")


# ── Pytest Configuration ──────────────────────────────────────────────────────

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (require external services)"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests (no external services required)"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (may take longer to run)"
    )


# ── Database Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def pg_connection():
    """Create a PostgreSQL connection for the test session."""
    conn = psycopg2.connect(POSTGRES_DSN)
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="function")
def pg_cursor(pg_connection):
    """Create a PostgreSQL cursor for each test function."""
    cursor = pg_connection.cursor(cursor_factory=RealDictCursor)
    yield cursor
    cursor.close()


@pytest.fixture(scope="function")
def clean_database(pg_cursor):
    """Clean the database before and after each test."""
    # Clean before test
    pg_cursor.execute("DELETE FROM attacks WHERE id >= 90000")  # Only delete test data
    pg_cursor.execute("DELETE FROM users WHERE username LIKE 'test_%'")
    yield
    # Clean after test
    pg_cursor.execute("DELETE FROM attacks WHERE id >= 90000")
    pg_cursor.execute("DELETE FROM users WHERE username LIKE 'test_%'")


# ── Qdrant Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def qdrant_client():
    """Create a Qdrant client for the test session."""
    pytest.importorskip("qdrant_client")
    from qdrant_client import QdrantClient
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    yield client
    # No explicit close needed for Qdrant client


@pytest.fixture(scope="function")
def clean_qdrant(qdrant_client):
    """Clean test data from Qdrant before and after each test."""
    # Get collection info
    try:
        collection_info = qdrant_client.get_collection(QDRANT_COLLECTION)
        # Delete test points (IDs >= 90000)
        qdrant_client.delete(
            collection_name=QDRANT_COLLECTION,
            points_selector={
                "filter": {
                    "must": [
                        {"key": "id", "range": {"gte": 90000}}
                    ]
                }
            }
        )
    except Exception as e:
        # Collection might not exist, that's okay for some tests
        pass
    yield
    # Clean after test
    try:
        qdrant_client.delete(
            collection_name=QDRANT_COLLECTION,
            points_selector={
                "filter": {
                    "must": [
                        {"key": "id", "range": {"gte": 90000}}
                    ]
                }
            }
        )
    except Exception:
        pass


# ── Service Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def searcher(clean_database, clean_qdrant):
    """Create an AttackSearcher instance for testing."""
    AttackSearcher = _import_ke("knowledge_engine.search.searcher").AttackSearcher
    searcher = AttackSearcher()
    yield searcher
    searcher.pg.close()


@pytest.fixture(scope="function")
def chainer(searcher):
    """Create an AttackChainer instance for testing."""
    AttackChainer = _import_ke("knowledge_engine.search.attack_chainer").AttackChainer
    chainer = AttackChainer(searcher)
    return chainer


@pytest.fixture(scope="function")
def ml_service():
    """Create an ML service instance for testing."""
    try:
        get_ml_service = _import_ke("knowledge_engine.ml.ml_service").get_ml_service
        service = get_ml_service()
        return service
    except Exception as e:
        pytest.skip(f"ML service not available: {e}")


@pytest.fixture(scope="function")
def opsec_engine():
    """Create an OpSec audit engine for testing."""
    try:
        OpSecAuditEngine = _import_ke("knowledge_engine.utils.opsec_audit").OpSecAuditEngine
        engine = OpSecAuditEngine()
        return engine
    except Exception as e:
        pytest.skip(f"OpSec audit engine not available: {e}")


# ── FastAPI Test Client ───────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def client():
    """Create a FastAPI TestClient for API testing."""
    pytest.importorskip("qdrant_client")
    app = _import_ke("knowledge_engine.core.api").app
    with TestClient(app) as test_client:
        yield test_client


# ── Authentication Fixtures ────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def test_user_token(client):
    """Create a test user and return authentication token."""
    # Create test user
    user_data = {
        "username": "test_analyst",
        "email": "test@example.com",
        "password": "test123",
        "role": "analyst"
    }
    
    # First try to login (user might already exist)
    login_response = client.post("/auth/login", json={
        "username": "test_analyst",
        "password": "test123"
    })
    
    if login_response.status_code == 200:
        return login_response.json()["access_token"]
    
    # If login failed, try to create the user (might need admin token)
    # For now, we'll skip if we can't create users
    pytest.skip("Could not create test user - admin access required")


@pytest.fixture(scope="function")
def admin_token(client):
    """Get admin authentication token."""
    # Try to login with default admin credentials
    response = client.post("/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    
    if response.status_code == 200:
        return response.json()["access_token"]
    
    pytest.skip("Admin credentials not configured")


@pytest.fixture(scope="function")
def service_auth_headers():
    """Return service authentication headers."""
    return {
        "X-Service-API-Key": os.getenv("SERVICE_API_KEY_ORCHESTRATOR", "test-service-key")
    }


# ── Test Data Fixtures ────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def sample_attack_record():
    """Return a sample attack record for testing."""
    return {
        "id": 90001,
        "title": "SQL Injection Attack",
        "category": "Web Application",
        "attack_type": "Injection",
        "scenario_description": "SQL injection vulnerability in login form allows authentication bypass",
        "tools_used": "sqlmap, burp suite",
        "attack_steps": "1. Identify vulnerable parameter\n2. Craft SQL injection payload\n3. Execute payload to bypass authentication",
        "target_type": "Web Application",
        "vulnerability": "SQL Injection",
        "mitre_technique": "T1190",
        "impact": "Authentication bypass, data exfiltration",
        "detection_method": "WAF signature detection, log analysis",
        "solution": "Use parameterized queries, input validation",
        "tags": "sql, injection, web",
        "source": "test"
    }


@pytest.fixture(scope="function")
def sample_attack_records():
    """Return multiple sample attack records for testing."""
    return [
        {
            "id": 90001,
            "title": "SQL Injection Attack",
            "category": "Web Application",
            "attack_type": "Injection",
            "scenario_description": "SQL injection vulnerability in login form",
            "tools_used": "sqlmap",
            "attack_steps": "Craft and execute SQL payload",
            "target_type": "Web Application",
            "vulnerability": "SQL Injection",
            "mitre_technique": "T1190",
            "impact": "Authentication bypass",
            "detection_method": "WAF",
            "solution": "Parameterized queries",
            "tags": "sql, injection",
            "source": "test"
        },
        {
            "id": 90002,
            "title": "Port Scanning",
            "category": "Network Reconnaissance",
            "attack_type": "Scanning",
            "scenario_description": "Network port scanning to identify open services",
            "tools_used": "nmap",
            "attack_steps": "Run nmap scan against target",
            "target_type": "Network",
            "vulnerability": "Open ports",
            "mitre_technique": "T1046",
            "impact": "Service discovery",
            "detection_method": "IDS",
            "solution": "Firewall rules",
            "tags": "recon, scanning",
            "source": "test"
        },
        {
            "id": 90003,
            "title": "Brute Force Attack",
            "category": "Credential Access",
            "attack_type": "Brute Force",
            "scenario_description": "Brute force password attack on SSH service",
            "tools_used": "hydra",
            "attack_steps": "Run dictionary attack against SSH",
            "target_type": "SSH Service",
            "vulnerability": "Weak passwords",
            "mitre_technique": "T1110",
            "impact": "Unauthorized access",
            "detection_method": "Log analysis",
            "solution": "Strong passwords, rate limiting",
            "tags": "brute, credentials",
            "source": "test"
        }
    ]


@pytest.fixture(scope="function")
def insert_test_records(pg_cursor, qdrant_client, sample_attack_records):
    """Insert test records into PostgreSQL and Qdrant."""
    # Insert into PostgreSQL
    for record in sample_attack_records:
        pg_cursor.execute(
            """
            INSERT INTO attacks 
            (id, title, category, attack_type, scenario_description, tools_used, 
             attack_steps, target_type, vulnerability, mitre_technique, impact, 
             detection_method, solution, tags, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                title=EXCLUDED.title,
                category=EXCLUDED.category,
                attack_type=EXCLUDED.attack_type,
                scenario_description=EXCLUDED.scenario_description,
                tools_used=EXCLUDED.tools_used,
                attack_steps=EXCLUDED.attack_steps,
                target_type=EXCLUDED.target_type,
                vulnerability=EXCLUDED.vulnerability,
                mitre_technique=EXCLUDED.mitre_technique,
                impact=EXCLUDED.impact,
                detection_method=EXCLUDED.detection_method,
                solution=EXCLUDED.solution,
                tags=EXCLUDED.tags,
                source=EXCLUDED.source
            """,
            (
                record["id"], record["title"], record["category"], record["attack_type"],
                record["scenario_description"], record["tools_used"], record["attack_steps"],
                record["target_type"], record["vulnerability"], record["mitre_technique"],
                record["impact"], record["detection_method"], record["solution"],
                record["tags"], record["source"]
            )
        )
    
    # Note: Qdrant insertion skipped in fixture to avoid embedding model dependency
    # Tests that need Qdrant data should handle it separately
    
    return sample_attack_records


# ── Async Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()