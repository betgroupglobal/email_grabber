"""
Tests for Ingestor - data ingestion from CSV to PostgreSQL and Qdrant.
"""
import pytest
import csv
import tempfile
from pathlib import Path
from ingestor import (
    clean,
    build_embedding_text,
    pg_connect,
    ensure_pg_schema,
    pg_insert_batch,
    ensure_qdrant_collection,
    qdrant_upsert_batch
)


# ── Helper Function Tests ───────────────────────────────────────────────────

@pytest.mark.unit
def test_clean_basic():
    """Test basic text cleaning."""
    text = "  Test String  "
    cleaned = clean(text)
    assert cleaned == "Test String"


@pytest.mark.unit
def test_clean_null():
    """Test cleaning None value."""
    cleaned = clean(None)
    assert cleaned == ""


@pytest.mark.unit
def test_clean_special_characters():
    """Test cleaning special characters."""
    text = "Test\x00String\x00"
    cleaned = clean(text)
    assert "\x00" not in cleaned


@pytest.mark.unit
def test_clean_empty_string():
    """Test cleaning empty string."""
    cleaned = clean("")
    assert cleaned == ""


@pytest.mark.unit
def test_build_embedding_text():
    """Test building embedding text from row."""
    row = {
        "title": "SQL Injection",
        "category": "Web Application",
        "attack_type": "Injection",
        "scenario_description": "SQL injection attack",
        "target_type": "Web",
        "vulnerability": "SQLi",
        "mitre_technique": "T1190",
        "tags": "web, sql"
    }
    
    embedding_text = build_embedding_text(row)
    
    assert isinstance(embedding_text, str)
    assert "SQL Injection" in embedding_text
    assert "Web Application" in embedding_text
    assert "T1190" in embedding_text


@pytest.mark.unit
def test_build_embedding_text_empty_fields():
    """Test building embedding text with empty fields."""
    row = {
        "title": "",
        "category": "",
        "attack_type": "",
        "scenario_description": "",
        "target_type": "",
        "vulnerability": "",
        "mitre_technique": "",
        "tags": ""
    }
    
    embedding_text = build_embedding_text(row)
    
    # Should handle empty fields gracefully
    assert isinstance(embedding_text, str)


@pytest.mark.unit
def test_build_embedding_text_missing_fields():
    """Test building embedding text with missing fields."""
    row = {
        "title": "SQL Injection"
        # Other fields missing
    }
    
    embedding_text = build_embedding_text(row)
    
    # Should handle missing fields gracefully
    assert isinstance(embedding_text, str)
    assert "SQL Injection" in embedding_text


# ── PostgreSQL Connection Tests ───────────────────────────────────────────────

@pytest.mark.integration
def test_pg_connect():
    """Test PostgreSQL connection."""
    conn = pg_connect()
    assert conn is not None
    conn.close()


@pytest.mark.integration
def test_pg_connect_autocommit():
    """Test that PostgreSQL connection has autocommit enabled."""
    conn = pg_connect()
    assert conn.autocommit == True
    conn.close()


# ── Schema Management Tests ─────────────────────────────────────────────────

@pytest.mark.integration
def test_ensure_pg_schema(pg_connection):
    """Test PostgreSQL schema creation."""
    ensure_pg_schema(pg_connection)
    
    # Check that table exists
    with pg_connection.cursor() as cur:
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'attacks'
            )
        """)
        exists = cur.fetchone()[0]
        assert exists == True


@pytest.mark.integration
def test_ensure_pg_schema_idempotent(pg_connection):
    """Test that schema creation is idempotent."""
    # Run twice - should not fail
    ensure_pg_schema(pg_connection)
    ensure_pg_schema(pg_connection)


# ── Data Insertion Tests ─────────────────────────────────────────────────────

@pytest.mark.integration
def test_pg_insert_batch(pg_connection, clean_database):
    """Test batch insertion into PostgreSQL."""
    ensure_pg_schema(pg_connection)
    
    rows = [
        {
            "id": 90001,
            "title": "Test Attack 1",
            "category": "Test",
            "attack_type": "Test",
            "scenario_description": "Test description",
            "tools_used": "test tool",
            "attack_steps": "Test steps",
            "target_type": "Test",
            "vulnerability": "Test",
            "mitre_technique": "T0000",
            "impact": "Test",
            "detection_method": "Test",
            "solution": "Test",
            "tags": "test",
            "source": "test"
        },
        {
            "id": 90002,
            "title": "Test Attack 2",
            "category": "Test",
            "attack_type": "Test",
            "scenario_description": "Test description 2",
            "tools_used": "test tool 2",
            "attack_steps": "Test steps 2",
            "target_type": "Test",
            "vulnerability": "Test",
            "mitre_technique": "T0000",
            "impact": "Test",
            "detection_method": "Test",
            "solution": "Test",
            "tags": "test",
            "source": "test"
        }
    ]
    
    pg_insert_batch(pg_connection, rows)
    
    # Verify insertion
    with pg_connection.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM attacks WHERE id >= 90000")
        count = cur.fetchone()[0]
        assert count == 2


@pytest.mark.integration
def test_pg_insert_batch_update(pg_connection, clean_database):
    """Test that batch insertion handles updates (ON CONFLICT)."""
    ensure_pg_schema(pg_connection)
    
    rows = [
        {
            "id": 90001,
            "title": "Original Title",
            "category": "Test",
            "attack_type": "Test",
            "scenario_description": "Original description",
            "tools_used": "test",
            "attack_steps": "test",
            "target_type": "Test",
            "vulnerability": "Test",
            "mitre_technique": "T0000",
            "impact": "Test",
            "detection_method": "Test",
            "solution": "Test",
            "tags": "test",
            "source": "test"
        }
    ]
    
    # First insert
    pg_insert_batch(pg_connection, rows)
    
    # Update with same ID
    rows[0]["title"] = "Updated Title"
    rows[0]["scenario_description"] = "Updated description"
    pg_insert_batch(pg_connection, rows)
    
    # Verify update
    with pg_connection.cursor() as cur:
        cur.execute("SELECT title, scenario_description FROM attacks WHERE id = 90001")
        result = cur.fetchone()
        assert result[0] == "Updated Title"
        assert result[1] == "Updated description"


@pytest.mark.integration
def test_pg_insert_batch_empty(pg_connection, clean_database):
    """Test batch insertion with empty list."""
    ensure_pg_schema(pg_connection)
    
    # Should not fail with empty list
    pg_insert_batch(pg_connection, [])


@pytest.mark.integration
def test_pg_insert_batch_special_characters(pg_connection, clean_database):
    """Test batch insertion with special characters."""
    ensure_pg_schema(pg_connection)
    
    rows = [
        {
            "id": 90001,
            "title": "Test with 'quotes' and \"double quotes\"",
            "category": "Test",
            "attack_type": "Test",
            "scenario_description": "Test with ; DROP TABLE attacks; --",
            "tools_used": "test",
            "attack_steps": "test",
            "target_type": "Test",
            "vulnerability": "Test",
            "mitre_technique": "T0000",
            "impact": "Test",
            "detection_method": "Test",
            "solution": "Test",
            "tags": "test",
            "source": "test"
        }
    ]
    
    # Should handle special characters safely
    pg_insert_batch(pg_connection, rows)


# ── Qdrant Collection Tests ─────────────────────────────────────────────────

@pytest.mark.integration
def test_ensure_qdrant_collection(qdrant_client):
    """Test Qdrant collection creation."""
    from config import QDRANT_COLLECTION, EMBEDDING_DIM
    
    ensure_qdrant_collection(qdrant_client)
    
    # Check that collection exists
    collections = qdrant_client.get_collections().collections
    collection_names = [c.name for c in collections]
    assert QDRANT_COLLECTION in collection_names


@pytest.mark.integration
def test_ensure_qdrant_collection_idempotent(qdrant_client):
    """Test that collection creation is idempotent."""
    # Run twice - should not fail
    ensure_qdrant_collection(qdrant_client)
    ensure_qdrant_collection(qdrant_client)


# ── Qdrant Upsert Tests ─────────────────────────────────────────────────────

@pytest.mark.integration
def test_qdrant_upsert_batch(qdrant_client, clean_qdrant):
    """Test batch upsert to Qdrant."""
    from config import QDRANT_COLLECTION, EMBEDDING_MODEL
    from fastembed import TextEmbedding
    
    # Skip if embeddings are disabled
    if EMBEDDING_MODEL == "disabled":
        pytest.skip("Embeddings disabled")
    
    try:
        model = TextEmbedding(model_name=EMBEDDING_MODEL)
    except Exception as e:
        pytest.skip(f"Cannot load embedding model: {e}")
    
    ensure_qdrant_collection(qdrant_client)
    
    rows = [
        {
            "id": 90001,
            "title": "Test Attack 1",
            "category": "Test",
            "attack_type": "Test",
            "scenario_description": "Test description",
            "target_type": "Test",
            "vulnerability": "Test",
            "mitre_technique": "T0000",
            "tags": "test",
            "tools_used": "test"
        }
    ]
    
    qdrant_upsert_batch(qdrant_client, model, rows)
    
    # Verify upsert
    results = qdrant_client.retrieve(
        collection_name=QDRANT_COLLECTION,
        ids=[90001]
    )
    assert len(results) == 1


@pytest.mark.integration
def test_qdrant_upsert_batch_update(qdrant_client, clean_qdrant):
    """Test that Qdrant upsert handles updates."""
    from config import QDRANT_COLLECTION, EMBEDDING_MODEL
    from fastembed import TextEmbedding
    
    if EMBEDDING_MODEL == "disabled":
        pytest.skip("Embeddings disabled")
    
    try:
        model = TextEmbedding(model_name=EMBEDDING_MODEL)
    except Exception as e:
        pytest.skip(f"Cannot load embedding model: {e}")
    
    ensure_qdrant_collection(qdrant_client)
    
    rows = [
        {
            "id": 90001,
            "title": "Original Title",
            "category": "Test",
            "attack_type": "Test",
            "scenario_description": "Original",
            "target_type": "Test",
            "vulnerability": "Test",
            "mitre_technique": "T0000",
            "tags": "test",
            "tools_used": "test"
        }
    ]
    
    # First upsert
    qdrant_upsert_batch(qdrant_client, model, rows)
    
    # Update with same ID
    rows[0]["title"] = "Updated Title"
    qdrant_upsert_batch(qdrant_client, model, rows)
    
    # Verify update
    results = qdrant_client.retrieve(
        collection_name=QDRANT_COLLECTION,
        ids=[90001]
    )
    assert len(results) == 1
    assert results[0].payload["title"] == "Updated Title"


# ── CSV Parsing Tests ───────────────────────────────────────────────────────

@pytest.mark.unit
def test_csv_parsing():
    """Test CSV parsing with sample data."""
    csv_content = """id,title,category,attack_type,scenario_description,tools_used,attack_steps,target_type,vulnerability,mitre_technique,impact,detection_method,solution,tags,source
1,Test Attack,Test,Test,Test description,test tool,test steps,Test,Test,T0000,Test,Test,Test,test,test
2,Another Test,Test,Test,Another description,test tool,test steps,Test,Test,T0000,Test,Test,Test,test,test"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content)
        temp_path = f.name
    
    try:
        with open(temp_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
            assert len(rows) == 2
            assert rows[0]['title'] == "Test Attack"
            assert rows[1]['title'] == "Another Test"
    finally:
        Path(temp_path).unlink()


@pytest.mark.unit
def test_csv_parsing_with_special_characters():
    """Test CSV parsing with special characters."""
    csv_content = """id,title,category
1,Test "quoted" value,Test
2,Test,with,commas,Test
3,Test,Newline,Test"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content)
        temp_path = f.name
    
    try:
        with open(temp_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
            # CSV parsing behavior may vary, just check it doesn't crash
            assert len(rows) >= 2
    finally:
        Path(temp_path).unlink()


# ── End-to-End Ingestion Tests ───────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.slow
def test_full_ingestion_flow(pg_connection, qdrant_client, clean_database, clean_qdrant):
    """Test full ingestion flow from CSV to PostgreSQL and Qdrant."""
    from config import EMBEDDING_MODEL
    from fastembed import TextEmbedding
    
    # Create test CSV
    csv_content = """id,title,category,attack_type,scenario_description,tools_used,attack_steps,target_type,vulnerability,mitre_technique,impact,detection_method,solution,tags,source
90001,Test Attack 1,Test,Test,Test description 1,test tool 1,test steps 1,Test,Test,T0000,Test,Test,Test,test,test
90002,Test Attack 2,Test,Test,Test description 2,test tool 2,test steps 2,Test,Test,T0000,Test,Test,Test,test,test
90003,Test Attack 3,Test,Test,Test description 3,test tool 3,test steps 3,Test,Test,T0000,Test,Test,Test,test,test"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content)
        temp_path = f.name
    
    try:
        # Setup
        ensure_pg_schema(pg_connection)
        
        if EMBEDDING_MODEL != "disabled":
            try:
                model = TextEmbedding(model_name=EMBEDDING_MODEL)
                ensure_qdrant_collection(qdrant_client)
                use_embeddings = True
            except Exception:
                use_embeddings = False
        else:
            use_embeddings = False
        
        # Read CSV and insert
        with open(temp_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
            # Filter out rows without valid IDs
            valid_rows = [r for r in rows if r.get('id', '').strip().isdigit()]
            
            # Insert into PostgreSQL
            pg_insert_batch(pg_connection, valid_rows)
            
            # Insert into Qdrant if embeddings enabled
            if use_embeddings:
                qdrant_upsert_batch(qdrant_client, model, valid_rows)
        
        # Verify PostgreSQL insertion
        with pg_connection.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM attacks WHERE id >= 90000")
            pg_count = cur.fetchone()[0]
            assert pg_count == 3
        
        # Verify Qdrant insertion (if embeddings enabled)
        if use_embeddings:
            from config import QDRANT_COLLECTION
            results = qdrant_client.retrieve(
                collection_name=QDRANT_COLLECTION,
                ids=[90001, 90002, 90003]
            )
            assert len(results) == 3
            
    finally:
        Path(temp_path).unlink()


# ── Error Handling Tests ─────────────────────────────────────────────────────

@pytest.mark.integration
def test_pg_insert_batch_invalid_data(pg_connection, clean_database):
    """Test batch insertion with invalid data."""
    ensure_pg_schema(pg_connection)
    
    # Row with missing required fields
    rows = [
        {
            "id": 90001,
            # Missing other fields
        }
    ]
    
    # Should handle gracefully or raise appropriate error
    try:
        pg_insert_batch(pg_connection, rows)
    except Exception:
        # Expected to fail with invalid data
        pass


@pytest.mark.unit
def test_build_embedding_text_none_values():
    """Test building embedding text with None values."""
    row = {
        "title": None,
        "category": None,
        "attack_type": "Test",
        "scenario_description": None,
        "target_type": None,
        "vulnerability": None,
        "mitre_technique": None,
        "tags": None
    }
    
    embedding_text = build_embedding_text(row)
    
    # Should handle None values gracefully
    assert isinstance(embedding_text, str)