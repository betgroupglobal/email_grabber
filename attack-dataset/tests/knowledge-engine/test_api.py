"""
Comprehensive API endpoint tests for Knowledge Engine.
Tests all FastAPI endpoints with various authentication scenarios.
"""
import pytest
from fastapi.testclient import TestClient


# ── Authentication Endpoints ───────────────────────────────────────────────────

@pytest.mark.integration
def test_login_success(client):
    """Test successful login with valid credentials."""
    response = client.post("/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "token_type" in data
    assert data["token_type"] == "bearer"


@pytest.mark.integration
def test_login_invalid_credentials(client):
    """Test login with invalid credentials."""
    response = client.post("/auth/login", json={
        "username": "invalid",
        "password": "wrong"
    })
    
    assert response.status_code == 401


@pytest.mark.integration
def test_login_missing_fields(client):
    """Test login with missing required fields."""
    response = client.post("/auth/login", json={
        "username": "admin"
        # Missing password
    })
    
    assert response.status_code == 422  # Validation error


@pytest.mark.integration
def test_refresh_token(client, admin_token):
    """Test token refresh with valid refresh token."""
    # First login to get refresh token
    login_response = client.post("/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    
    if login_response.status_code != 200:
        pytest.skip("Cannot get refresh token")
    
    tokens = login_response.json()
    refresh_token = tokens.get("refresh_token")
    
    if not refresh_token:
        pytest.skip("No refresh token in response")
    
    response = client.post("/auth/refresh", json={
        "refresh_token": refresh_token
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


@pytest.mark.integration
def test_refresh_token_invalid(client):
    """Test token refresh with invalid token."""
    response = client.post("/auth/refresh", json={
        "refresh_token": "invalid_token"
    })
    
    assert response.status_code == 401


@pytest.mark.integration
def test_get_current_user(client, admin_token):
    """Test getting current user information."""
    response = client.get("/auth/me", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "username" in data
    assert "email" in data
    assert "role" in data


@pytest.mark.integration
def test_get_current_user_no_auth(client):
    """Test getting current user without authentication."""
    response = client.get("/auth/me")
    
    assert response.status_code == 401


@pytest.mark.integration
def test_create_user_admin_only(client, admin_token):
    """Test user creation (admin only)."""
    response = client.post("/auth/users", 
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "username": "test_new_user",
            "email": "newuser@test.com",
            "password": "password123",
            "role": "analyst"
        }
    )
    
    # Might fail if user already exists
    assert response.status_code in [200, 400]


@pytest.mark.integration
def test_create_user_unauthorized(client, test_user_token):
    """Test user creation without admin privileges."""
    if not test_user_token:
        pytest.skip("No test user token available")
    
    response = client.post("/auth/users",
        headers={"Authorization": f"Bearer {test_user_token}"},
        json={
            "username": "test_new_user",
            "email": "newuser@test.com",
            "password": "password123",
            "role": "analyst"
        }
    )
    
    assert response.status_code == 403


@pytest.mark.integration
def test_list_users_admin(client, admin_token):
    """Test listing users (admin only)."""
    response = client.get("/auth/users", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.integration
def test_update_user_admin(client, admin_token):
    """Test updating user information (admin only)."""
    # First, try to get a user ID
    list_response = client.get("/auth/users", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    
    if list_response.status_code != 200 or not list_response.json():
        pytest.skip("No users to update")
    
    user_id = list_response.json()[0]["id"]
    
    response = client.put(f"/auth/users/{user_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": "updated@test.com"
        }
    )
    
    assert response.status_code == 200


@pytest.mark.integration
def test_delete_user_admin(client, admin_token):
    """Test deleting a user (admin only)."""
    # First create a test user
    create_response = client.post("/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "username": "test_delete_user",
            "email": "delete@test.com",
            "password": "password123",
            "role": "analyst"
        }
    )
    
    if create_response.status_code != 200:
        pytest.skip("Cannot create test user for deletion")
    
    user_id = create_response.json()["id"]
    
    response = client.delete(f"/auth/users/{user_id}", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    
    assert response.status_code == 200


# ── Search Endpoints ──────────────────────────────────────────────────────────

@pytest.mark.integration
def test_search_semantic(client, insert_test_records, service_auth_headers):
    """Test semantic search endpoint."""
    response = client.post("/search",
        headers=service_auth_headers,
        json={
            "query": "SQL injection attack",
            "top_k": 5
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "query" in data
    assert "results" in data
    assert "total" in data
    assert isinstance(data["results"], list)


@pytest.mark.integration
def test_search_with_filters(client, insert_test_records, service_auth_headers):
    """Test semantic search with category and attack type filters."""
    response = client.post("/search",
        headers=service_auth_headers,
        json={
            "query": "attack",
            "top_k": 10,
            "category_filter": "Web Application",
            "attack_type_filter": "Injection"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["results"], list)


@pytest.mark.integration
def test_search_unauthorized(client):
    """Test search without authentication."""
    response = client.post("/search", json={
        "query": "test",
        "top_k": 5
    })
    
    assert response.status_code == 401


@pytest.mark.integration
def test_keyword_search(client, insert_test_records):
    """Test keyword search endpoint."""
    response = client.get("/search/keyword?q=sql&limit=10")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.integration
def test_keyword_search_missing_param(client):
    """Test keyword search without required parameter."""
    response = client.get("/search/keyword")
    
    assert response.status_code == 422  # Validation error


# ── MITRE Endpoints ───────────────────────────────────────────────────────────

@pytest.mark.integration
def test_get_by_mitre(client, insert_test_records):
    """Test getting attacks by MITRE technique."""
    response = client.get("/mitre/T1190?limit=10")
    
    assert response.status_code in [200, 404]  # 404 if no results
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.integration
def test_list_mitre(client, insert_test_records):
    """Test listing MITRE techniques."""
    response = client.get("/mitre")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


# ── Category Endpoints ────────────────────────────────────────────────────────

@pytest.mark.integration
def test_list_categories(client, insert_test_records):
    """Test listing attack categories."""
    response = client.get("/categories")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.integration
def test_get_by_category(client, insert_test_records):
    """Test getting attacks by category."""
    response = client.get("/categories/Web?limit=10")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


# ── Target Endpoints ─────────────────────────────────────────────────────────

@pytest.mark.integration
def test_get_by_target(client, insert_test_records):
    """Test getting attacks by target type."""
    response = client.get("/targets/Web?limit=10")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


# ── Tools Endpoints ───────────────────────────────────────────────────────────

@pytest.mark.integration
def test_list_tools(client, insert_test_records):
    """Test listing tools."""
    response = client.get("/tools")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


# ── Attack Vector Builder Endpoints ───────────────────────────────────────────

@pytest.mark.integration
def test_build_attack_vector(client, insert_test_records, service_auth_headers):
    """Test building attack vectors."""
    response = client.post("/attack-vector",
        headers=service_auth_headers,
        json={
            "target_description": "Web server with Apache and MySQL",
            "detected_services": ["apache", "mysql"],
            "detected_os": "Linux",
            "top_chains": 2
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "target_description" in data
    assert "chains" in data
    assert isinstance(data["chains"], list)


@pytest.mark.integration
def test_build_attack_vector_minimal(client, insert_test_records, service_auth_headers):
    """Test building attack vectors with minimal parameters."""
    response = client.post("/attack-vector",
        headers=service_auth_headers,
        json={
            "target_description": "Test target"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "chains" in data


@pytest.mark.integration
def test_build_attack_vector_unauthorized(client):
    """Test building attack vectors without authentication."""
    response = client.post("/attack-vector", json={
        "target_description": "Test target"
    })
    
    assert response.status_code == 401


# ── OpSec Endpoints ─────────────────────────────────────────────────────────

@pytest.mark.integration
def test_get_opsec_note(client, insert_test_records):
    """Test getting OpSec notes for an attack."""
    response = client.get("/opsec/90001")
    
    # Might return 404 if attack not found
    assert response.status_code in [200, 404]
    if response.status_code == 200:
        data = response.json()
        assert "attack_id" in data
        assert "detection_method" in data
        assert "evasion_hints" in data


@pytest.mark.integration
def test_get_opsec_note_not_found(client):
    """Test getting OpSec notes for non-existent attack."""
    response = client.get("/opsec/99999")
    
    assert response.status_code == 404


# ── AI Status Endpoint ───────────────────────────────────────────────────────

@pytest.mark.integration
def test_ai_status(client):
    """Test AI analyst status check."""
    response = client.get("/ai/status")
    
    assert response.status_code == 200
    data = response.json()
    assert "available" in data
    assert isinstance(data["available"], bool)


# ── AI Analysis Endpoints ─────────────────────────────────────────────────────

@pytest.mark.integration
def test_ai_analyse_engagement(client, admin_token):
    """Test AI engagement analysis."""
    if not admin_token:
        pytest.skip("No admin token available")
    
    response = client.post("/ai/analyse/engagement",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "target": "test.example.com",
            "chains": [],
            "opsec_report": {},
            "scan_fingerprint": {}
        }
    )
    
    # Might return 503 if AI not available
    assert response.status_code in [200, 503]


@pytest.mark.integration
def test_ai_analyse_chain(client, admin_token):
    """Test AI chain analysis."""
    if not admin_token:
        pytest.skip("No admin token available")
    
    response = client.post("/ai/analyse/chain",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "chain": {
                "chain_id": "test",
                "steps": []
            }
        }
    )
    
    # Might return 503 if AI not available
    assert response.status_code in [200, 503]


@pytest.mark.integration
def test_ai_chat_sync(client, admin_token):
    """Test AI chat (non-streaming)."""
    if not admin_token:
        pytest.skip("No admin token available")
    
    response = client.post("/ai/chat",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "question": "What is SQL injection?",
            "stream": False
        }
    )
    
    # Might return 503 if AI not available
    assert response.status_code in [200, 503]


@pytest.mark.integration
def test_ai_chat_streaming(client, admin_token):
    """Test AI chat (streaming)."""
    if not admin_token:
        pytest.skip("No admin token available")
    
    response = client.post("/ai/chat",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "question": "What is SQL injection?",
            "stream": True
        }
    )
    
    # Might return 503 if AI not available
    assert response.status_code in [200, 503]


@pytest.mark.integration
def test_ai_chat_unauthorized(client):
    """Test AI chat without authentication."""
    response = client.post("/ai/chat", json={
        "question": "test",
        "stream": False
    })
    
    assert response.status_code == 401


# ── ML Service Endpoints ─────────────────────────────────────────────────────

@pytest.mark.integration
def test_ml_status(client):
    """Test ML service status."""
    response = client.get("/ml/status")
    
    assert response.status_code == 200
    data = response.json()
    assert "available" in data


@pytest.mark.integration
def test_ml_models(client):
    """Test listing ML models."""
    response = client.get("/ml/models")
    
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert "available_targets" in data


@pytest.mark.integration
def test_ml_predict(client):
    """Test ML single prediction."""
    response = client.post("/ml/predict", json={
        "text": "SQL injection attack on web application",
        "target": "category",
        "top_k": 3
    })
    
    # Might return 503 if ML not available
    assert response.status_code in [200, 503]


@pytest.mark.integration
def test_ml_batch_predict(client):
    """Test ML batch prediction."""
    response = client.post("/ml/batch-predict", json={
        "texts": [
            "SQL injection attack",
            "Port scanning",
            "Brute force attack"
        ],
        "target": "category",
        "top_k": 3
    })
    
    # Might return 503 if ML not available
    assert response.status_code in [200, 503]


# ── OpSec Audit Endpoints ───────────────────────────────────────────────────

@pytest.mark.integration
def test_opsec_audit(client):
    """Test OpSec chain audit."""
    response = client.post("/opsec/audit", json={
        "chain_id": "test_chain",
        "chain_description": "Test attack chain",
        "steps": [
            "Use nmap to scan ports",
            "Exploit SQL injection with sqlmap"
        ]
    })
    
    # Might return 503 if audit engine not available
    assert response.status_code in [200, 503]


@pytest.mark.integration
def test_tool_recommendation(client):
    """Test tool recommendation."""
    response = client.post("/opsec/tool-recommendation", json={
        "tool_name": "nmap"
    })
    
    # Might return 503 if audit engine not available
    assert response.status_code in [200, 503]


# ── CORS and General Tests ───────────────────────────────────────────────────

@pytest.mark.integration
def test_cors_headers(client):
    """Test that CORS headers are properly set."""
    response = client.get("/categories")
    
    # Check for CORS headers
    assert "access-control-allow-origin" in response.headers


@pytest.mark.integration
def test_health_check(client):
    """Test basic API health check."""
    # Use a simple endpoint to check if API is running
    response = client.get("/categories")
    
    assert response.status_code == 200


@pytest.mark.integration
def test_invalid_endpoint(client):
    """Test accessing invalid endpoint."""
    response = client.get("/invalid/endpoint")
    
    assert response.status_code == 404


# ── Service Authentication Tests ───────────────────────────────────────────────

@pytest.mark.integration
def test_service_auth_valid(client, service_auth_headers):
    """Test service authentication with valid key."""
    response = client.post("/search",
        headers=service_auth_headers,
        json={
            "query": "test",
            "top_k": 5
        }
    )
    
    assert response.status_code == 200


@pytest.mark.integration
def test_service_auth_invalid(client):
    """Test service authentication with invalid key."""
    response = client.post("/search",
        headers={"X-Service-API-Key": "invalid-key"},
        json={
            "query": "test",
            "top_k": 5
        }
    )
    
    assert response.status_code == 401


@pytest.mark.integration
def test_service_auth_missing(client):
    """Test request without service authentication."""
    response = client.post("/search", json={
        "query": "test",
        "top_k": 5
    })
    
    assert response.status_code == 401