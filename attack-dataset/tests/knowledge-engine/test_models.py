"""
Tests for Pydantic models - data validation and serialization.
"""
import pytest
from pydantic import ValidationError
from knowledge_engine.core.models import (
    AttackRecord,
    SearchQuery,
    SearchResponse,
    AttackResult,
    AttackVectorRequest,
    AttackVectorResponse,
    AttackStep,
    AttackChain,
    MitreMapping,
    ToolRecommendation,
    OpsecNote,
    MLPrediction,
    MLPredictRequest,
    MLPredictResponse,
    MLBatchPredictRequest,
    MLModelInfo,
    MLModelsResponse
)


# ── AttackRecord Tests ───────────────────────────────────────────────────────

@pytest.mark.unit
def test_attack_record_valid():
    """Test creating a valid AttackRecord."""
    record = AttackRecord(
        id=1,
        title="SQL Injection",
        category="Web Application",
        attack_type="Injection",
        scenario_description="SQL injection attack",
        tools_used="sqlmap",
        attack_steps="Inject payload",
        target_type="Web",
        vulnerability="SQLi",
        mitre_technique="T1190",
        impact="Data theft",
        detection_method="WAF",
        solution="Parameterized queries",
        tags="sql, injection",
        source="test"
    )
    
    assert record.id == 1
    assert record.title == "SQL Injection"
    assert record.category == "Web Application"


@pytest.mark.unit
def test_attack_record_with_ml_fields():
    """Test AttackRecord with ML enhancement fields."""
    record = AttackRecord(
        id=1,
        title="SQL Injection",
        category="Web Application",
        attack_type="Injection",
        scenario_description="SQL injection attack",
        tools_used="sqlmap",
        attack_steps="Inject payload",
        target_type="Web",
        vulnerability="SQLi",
        mitre_technique="T1190",
        impact="Data theft",
        detection_method="WAF",
        solution="Parameterized queries",
        tags="sql, injection",
        source="test",
        ml_category="Injection",
        ml_confidence=0.95,
        combined_score=0.88
    )
    
    assert record.ml_category == "Injection"
    assert record.ml_confidence == 0.95
    assert record.combined_score == 0.88


@pytest.mark.unit
def test_attack_record_missing_required_field():
    """Test that AttackRecord validation fails with missing required field."""
    with pytest.raises(ValidationError):
        AttackRecord(
            # Missing required 'id' field
            title="SQL Injection",
            category="Web Application",
            attack_type="Injection",
            scenario_description="SQL injection attack",
            tools_used="sqlmap",
            attack_steps="Inject payload",
            target_type="Web",
            vulnerability="SQLi",
            mitre_technique="T1190",
            impact="Data theft",
            detection_method="WAF",
            solution="Parameterized queries",
            tags="sql, injection",
            source="test"
        )


@pytest.mark.unit
def test_attack_record_from_dict():
    """Test creating AttackRecord from dictionary."""
    data = {
        "id": 1,
        "title": "SQL Injection",
        "category": "Web Application",
        "attack_type": "Injection",
        "scenario_description": "SQL injection attack",
        "tools_used": "sqlmap",
        "attack_steps": "Inject payload",
        "target_type": "Web",
        "vulnerability": "SQLi",
        "mitre_technique": "T1190",
        "impact": "Data theft",
        "detection_method": "WAF",
        "solution": "Parameterized queries",
        "tags": "sql, injection",
        "source": "test"
    }
    
    record = AttackRecord(**data)
    assert record.id == 1
    assert record.title == "SQL Injection"


# ── SearchQuery Tests ───────────────────────────────────────────────────────

@pytest.mark.unit
def test_search_query_valid():
    """Test creating a valid SearchQuery."""
    query = SearchQuery(
        query="SQL injection attack",
        top_k=10,
        category_filter="Web Application",
        attack_type_filter="Injection",
        mitre_filter="T1190"
    )
    
    assert query.query == "SQL injection attack"
    assert query.top_k == 10
    assert query.category_filter == "Web Application"


@pytest.mark.unit
def test_search_query_minimal():
    """Test creating SearchQuery with minimal parameters."""
    query = SearchQuery(query="test")
    
    assert query.query == "test"
    assert query.top_k == 10  # Default value
    assert query.category_filter is None


@pytest.mark.unit
def test_search_query_top_k_validation():
    """Test SearchQuery top_k validation."""
    # Valid range: 1-50
    SearchQuery(query="test", top_k=1)
    SearchQuery(query="test", top_k=50)
    
    # Invalid: too low
    with pytest.raises(ValidationError):
        SearchQuery(query="test", top_k=0)
    
    # Invalid: too high
    with pytest.raises(ValidationError):
        SearchQuery(query="test", top_k=51)


@pytest.mark.unit
def test_search_query_missing_query():
    """Test that SearchQuery validation fails without query."""
    with pytest.raises(ValidationError):
        SearchQuery(top_k=10)


# ── SearchResponse Tests ────────────────────────────────────────────────────

@pytest.mark.unit
def test_search_response_valid():
    """Test creating a valid SearchResponse."""
    record = AttackRecord(
        id=1,
        title="Test",
        category="Test",
        attack_type="Test",
        scenario_description="Test",
        tools_used="test",
        attack_steps="test",
        target_type="Test",
        vulnerability="Test",
        mitre_technique="T0000",
        impact="Test",
        detection_method="Test",
        solution="Test",
        tags="test",
        source="test"
    )
    
    result = AttackResult(record=record, score=0.95)
    
    response = SearchResponse(
        query="test query",
        results=[result],
        total=1
    )
    
    assert response.query == "test query"
    assert len(response.results) == 1
    assert response.total == 1


@pytest.mark.unit
def test_search_response_empty():
    """Test creating SearchResponse with empty results."""
    response = SearchResponse(
        query="test query",
        results=[],
        total=0
    )
    
    assert response.total == 0
    assert len(response.results) == 0


# ── AttackVectorRequest Tests ───────────────────────────────────────────────

@pytest.mark.unit
def test_attack_vector_request_valid():
    """Test creating a valid AttackVectorRequest."""
    request = AttackVectorRequest(
        target_description="Web server with Apache",
        detected_services=["apache", "mysql"],
        detected_os="Linux",
        top_chains=3
    )
    
    assert request.target_description == "Web server with Apache"
    assert len(request.detected_services) == 2
    assert request.detected_os == "Linux"
    assert request.top_chains == 3


@pytest.mark.unit
def test_attack_vector_request_minimal():
    """Test creating AttackVectorRequest with minimal parameters."""
    request = AttackVectorRequest(target_description="Test target")
    
    assert request.target_description == "Test target"
    assert request.detected_services == []
    assert request.detected_os is None
    assert request.top_chains == 3  # Default value


@pytest.mark.unit
def test_attack_vector_request_top_chains_validation():
    """Test AttackVectorRequest top_chains validation."""
    # Valid range: 1-10
    AttackVectorRequest(target_description="test", top_chains=1)
    AttackVectorRequest(target_description="test", top_chains=10)
    
    # Invalid: too low
    with pytest.raises(ValidationError):
        AttackVectorRequest(target_description="test", top_chains=0)
    
    # Invalid: too high
    with pytest.raises(ValidationError):
        AttackVectorRequest(target_description="test", top_chains=11)


# ── AttackChain Tests ───────────────────────────────────────────────────────

@pytest.mark.unit
def test_attack_chain_valid():
    """Test creating a valid AttackChain."""
    record = AttackRecord(
        id=1,
        title="Test",
        category="Test",
        attack_type="Test",
        scenario_description="Test",
        tools_used="test",
        attack_steps="test",
        target_type="Test",
        vulnerability="Test",
        mitre_technique="T0000",
        impact="Test",
        detection_method="Test",
        solution="Test",
        tags="test",
        source="test"
    )
    
    step = AttackStep(
        phase="Reconnaissance",
        attack=record,
        rationale="Test rationale",
        mitre_technique="T0000"
    )
    
    chain = AttackChain(
        chain_id="test_chain_1",
        target_description="Test target",
        confidence=0.85,
        steps=[step],
        estimated_impact="High impact",
        opsec_notes="Test OpSec notes"
    )
    
    assert chain.chain_id == "test_chain_1"
    assert chain.confidence == 0.85
    assert len(chain.steps) == 1


@pytest.mark.unit
def test_attack_chain_confidence_validation():
    """Test that confidence is between 0 and 1."""
    record = AttackRecord(
        id=1,
        title="Test",
        category="Test",
        attack_type="Test",
        scenario_description="Test",
        tools_used="test",
        attack_steps="test",
        target_type="Test",
        vulnerability="Test",
        mitre_technique="T0000",
        impact="Test",
        detection_method="Test",
        solution="Test",
        tags="test",
        source="test"
    )
    
    step = AttackStep(
        phase="Reconnaissance",
        attack=record,
        rationale="Test",
        mitre_technique="T0000"
    )
    
    # Valid confidence values
    AttackChain(
        chain_id="test",
        target_description="test",
        confidence=0.0,
        steps=[step],
        estimated_impact="test",
        opsec_notes="test"
    )
    
    AttackChain(
        chain_id="test",
        target_description="test",
        confidence=1.0,
        steps=[step],
        estimated_impact="test",
        opsec_notes="test"
    )


# ── ML Prediction Tests ─────────────────────────────────────────────────────

@pytest.mark.unit
def test_ml_prediction_valid():
    """Test creating a valid MLPrediction."""
    prediction = MLPrediction(
        label="Injection",
        confidence=0.95,
        rank=1
    )
    
    assert prediction.label == "Injection"
    assert prediction.confidence == 0.95
    assert prediction.rank == 1


@pytest.mark.unit
def test_ml_prediction_confidence_validation():
    """Test that confidence is between 0 and 1."""
    # Valid confidence values
    MLPrediction(label="Test", confidence=0.0, rank=1)
    MLPrediction(label="Test", confidence=1.0, rank=1)
    MLPrediction(label="Test", confidence=0.5, rank=1)


@pytest.mark.unit
def test_ml_predict_request_valid():
    """Test creating a valid MLPredictRequest."""
    request = MLPredictRequest(
        text="SQL injection attack",
        target="category",
        top_k=3
    )
    
    assert request.text == "SQL injection attack"
    assert request.target == "category"
    assert request.top_k == 3


@pytest.mark.unit
def test_ml_predict_request_defaults():
    """Test MLPredictRequest default values."""
    request = MLPredictRequest(text="test")
    
    assert request.target == "category"  # Default
    assert request.top_k == 3  # Default


@pytest.mark.unit
def test_ml_batch_predict_request_valid():
    """Test creating a valid MLBatchPredictRequest."""
    request = MLBatchPredictRequest(
        texts=["SQL injection", "XSS", "Brute force"],
        target="category",
        top_k=3
    )
    
    assert len(request.texts) == 3
    assert request.target == "category"


# ── ML Model Info Tests ─────────────────────────────────────────────────────

@pytest.mark.unit
def test_ml_model_info_valid():
    """Test creating a valid MLModelInfo."""
    info = MLModelInfo(
        target="category",
        model_type="MultinomialNB",
        num_classes=63,
        accuracy=0.81,
        num_samples=13974,
        embedding_method="TF-IDF",
        timestamp="2024-01-01"
    )
    
    assert info.target == "category"
    assert info.model_type == "MultinomialNB"
    assert info.num_classes == 63


@pytest.mark.unit
def test_ml_model_info_optional_fields():
    """Test MLModelInfo with optional fields."""
    info = MLModelInfo(
        target="category",
        model_type="MultinomialNB",
        num_classes=63
    )
    
    assert info.accuracy is None
    assert info.num_samples is None
    assert info.embedding_method is None


# ── OpSec Note Tests ───────────────────────────────────────────────────────

@pytest.mark.unit
def test_opsec_note_valid():
    """Test creating a valid OpsecNote."""
    note = OpsecNote(
        attack_id=1,
        detection_method="WAF signature detection",
        risk_level="high",
        recommendations=["Use encoding", "Rate limiting"]
    )
    
    assert note.attack_id == 1
    assert note.risk_level == "high"
    assert len(note.recommendations) == 2


# ── Serialization Tests ───────────────────────────────────────────────────────

@pytest.mark.unit
def test_attack_record_serialization():
    """Test AttackRecord JSON serialization."""
    record = AttackRecord(
        id=1,
        title="SQL Injection",
        category="Web Application",
        attack_type="Injection",
        scenario_description="SQL injection attack",
        tools_used="sqlmap",
        attack_steps="Inject payload",
        target_type="Web",
        vulnerability="SQLi",
        mitre_technique="T1190",
        impact="Data theft",
        detection_method="WAF",
        solution="Parameterized queries",
        tags="sql, injection",
        source="test"
    )
    
    # Test model_dump (Pydantic v2)
    data = record.model_dump()
    assert data["id"] == 1
    assert data["title"] == "SQL Injection"


@pytest.mark.unit
def test_attack_record_deserialization():
    """Test AttackRecord JSON deserialization."""
    data = {
        "id": 1,
        "title": "SQL Injection",
        "category": "Web Application",
        "attack_type": "Injection",
        "scenario_description": "SQL injection attack",
        "tools_used": "sqlmap",
        "attack_steps": "Inject payload",
        "target_type": "Web",
        "vulnerability": "SQLi",
        "mitre_technique": "T1190",
        "impact": "Data theft",
        "detection_method": "WAF",
        "solution": "Parameterized queries",
        "tags": "sql, injection",
        "source": "test"
    }
    
    record = AttackRecord(**data)
    assert record.id == 1
    assert record.title == "SQL Injection"


# ── Edge Cases and Error Handling ─────────────────────────────────────────────

@pytest.mark.unit
def test_attack_record_with_none_values():
    """Test AttackRecord with None values for optional fields."""
    record = AttackRecord(
        id=1,
        title="Test",
        category="Test",
        attack_type="Test",
        scenario_description="Test",
        tools_used="test",
        attack_steps="test",
        target_type="Test",
        vulnerability="Test",
        mitre_technique="T0000",
        impact="Test",
        detection_method="Test",
        solution="Test",
        tags="test",
        source="test",
        ml_category=None,
        ml_confidence=None,
        combined_score=None
    )
    
    assert record.ml_category is None
    assert record.ml_confidence is None
    assert record.combined_score is None


@pytest.mark.unit
def test_search_query_with_special_characters():
    """Test SearchQuery with special characters."""
    query = SearchQuery(
        query="SQL injection'; DROP TABLE attacks; --",
        top_k=10
    )
    
    assert query.query == "SQL injection'; DROP TABLE attacks; --"


@pytest.mark.unit
def test_attack_vector_request_with_unicode():
    """Test AttackVectorRequest with unicode characters."""
    request = AttackVectorRequest(
        target_description="Web server ñ 中文"
    )
    
    assert request.target_description == "Web server ñ 中文"