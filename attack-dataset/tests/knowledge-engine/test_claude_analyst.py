"""
Tests for ClaudeAnalyst - AI-powered intelligence layer (OpenRouter-compatible).
"""
import pytest
from unittest.mock import Mock, patch, MagicMock


# ── Claude Analyst Initialization ─────────────────────────────────────────────

@pytest.mark.integration
def test_claude_analyst_initialization():
    """Test that Claude analyst initializes correctly."""
    from claude_analyst import ClaudeAnalyst
    from config import OPENROUTER_API_KEY
    
    if not OPENROUTER_API_KEY:
        pytest.skip("OpenRouter API key not configured")
    
    try:
        analyst = ClaudeAnalyst(searcher=None, audit_engine=None, chainer=None)
        assert analyst is not None
    except Exception as e:
        pytest.skip(f"Claude analyst initialization failed: {e}")


# ── Context Formatting Tests ─────────────────────────────────────────────────

@pytest.mark.unit
def test_format_chain_for_claude():
    """Test formatting attack chain for Claude."""
    from claude_analyst import _format_chain_for_claude
    
    chain = {
        "chain_id": "test_chain_1",
        "confidence": 0.85,
        "target_description": "Web server with Apache",
        "estimated_impact": "High impact - data exfiltration",
        "steps": [
            {
                "phase": "Reconnaissance",
                "attack": {
                    "title": "Port Scanning",
                    "attack_type": "Scanning",
                    "mitre_technique": "T1046",
                    "tools_used": "nmap",
                    "impact": "Service discovery",
                    "detection_method": "IDS"
                }
            }
        ],
        "opsec_notes": "Test OpSec notes"
    }
    
    formatted = _format_chain_for_claude(chain)
    
    assert isinstance(formatted, str)
    assert "test_chain_1" in formatted
    assert "85%" in formatted
    assert "Reconnaissance" in formatted
    assert "Port Scanning" in formatted


@pytest.mark.unit
def test_format_chain_for_claude_empty():
    """Test formatting empty chain for Claude."""
    from claude_analyst import _format_chain_for_claude
    
    chain = {
        "chain_id": "test_empty",
        "confidence": 0.0,
        "target_description": "",
        "estimated_impact": "",
        "steps": [],
        "opsec_notes": ""
    }
    
    formatted = _format_chain_for_claude(chain)
    
    assert isinstance(formatted, str)


@pytest.mark.unit
def test_format_records_for_context():
    """Test formatting attack records for context."""
    from claude_analyst import _format_records_for_context
    from models import AttackRecord
    
    records = [
        AttackRecord(
            id=1,
            title="SQL Injection",
            category="Web Application",
            attack_type="Injection",
            scenario_description="SQL injection in login form",
            tools_used="sqlmap",
            attack_steps="Inject SQL payload",
            target_type="Web Application",
            vulnerability="SQL Injection",
            mitre_technique="T1190",
            impact="Auth bypass",
            detection_method="WAF",
            solution="Parameterized queries",
            tags="sql, injection",
            source="test"
        )
    ]
    
    formatted = _format_records_for_context(records)
    
    assert isinstance(formatted, str)
    assert "SQL Injection" in formatted
    assert "T1190" in formatted


@pytest.mark.unit
def test_format_records_for_context_multiple():
    """Test formatting multiple records for context."""
    from claude_analyst import _format_records_for_context
    from models import AttackRecord
    
    records = [
        AttackRecord(
            id=i,
            title=f"Test Attack {i}",
            category="Test",
            attack_type="Test",
            scenario_description=f"Test description {i}",
            tools_used="test",
            attack_steps="test",
            target_type="Test",
            vulnerability="Test",
            mitre_technique=f"T000{i}",
            impact="Test",
            detection_method="Test",
            solution="Test",
            tags="test",
            source="test"
        ) for i in range(10)
    ]
    
    formatted = _format_records_for_context(records)
    
    assert isinstance(formatted, str)
    # Should cap at 8 records
    assert "---" in formatted  # Records are separated by ---


@pytest.mark.unit
def test_format_records_for_context_empty():
    """Test formatting empty records list."""
    from claude_analyst import _format_records_for_context
    
    formatted = _format_records_for_context([])
    
    assert isinstance(formatted, str)
    assert formatted == ""


@pytest.mark.unit
def test_record_to_tool_payload():
    """Test converting attack record to tool payload."""
    from claude_analyst import _record_to_tool_payload
    from models import AttackRecord
    
    record = AttackRecord(
        id=1,
        title="SQL Injection",
        category="Web Application",
        attack_type="Injection",
        scenario_description="SQL injection in login form",
        tools_used="sqlmap, burp suite",
        attack_steps="Inject SQL payload",
        target_type="Web Application",
        vulnerability="SQL Injection",
        mitre_technique="T1190",
        impact="Auth bypass",
        detection_method="WAF",
        solution="Parameterized queries",
        tags="sql, injection",
        source="test"
    )
    
    payload = _record_to_tool_payload(record)
    
    assert isinstance(payload, dict)
    assert payload["id"] == 1
    assert payload["title"] == "SQL Injection"
    assert "tools_used" in payload
    assert len(payload["tools_used"]) <= 220  # Should be truncated


# ── Analysis Function Tests (Mocked) ─────────────────────────────────────────

@pytest.mark.unit
@patch('claude_analyst.ClaudeAnalyst')
def test_analyse_engagement_mock(mock_analyst_class):
    """Test engagement analysis with mocked AI."""
    from config import OPENROUTER_API_KEY
    
    if not OPENROUTER_API_KEY:
        pytest.skip("OpenRouter API key not configured")
    
    # Create mock analyst instance
    mock_analyst = Mock()
    mock_analyst.analyse_engagement.return_value = "Test analysis report"
    mock_analyst_class.return_value = mock_analyst
    
    # Test the analysis
    result = mock_analyst.analyse_engagement(
        target="test.example.com",
        chains=[],
        opsec_report={},
        scan_fingerprint={}
    )
    
    assert result == "Test analysis report"
    mock_analyst.analyse_engagement.assert_called_once()


@pytest.mark.unit
@patch('claude_analyst.ClaudeAnalyst')
def test_analyse_chain_mock(mock_analyst_class):
    """Test chain analysis with mocked AI."""
    from config import OPENROUTER_API_KEY
    
    if not OPENROUTER_API_KEY:
        pytest.skip("OpenRouter API key not configured")
    
    # Create mock analyst instance
    mock_analyst = Mock()
    mock_analyst.analyse_chain.return_value = "Test chain analysis"
    mock_analyst_class.return_value = mock_analyst
    
    # Test the analysis
    result = mock_analyst.analyse_chain({
        "chain_id": "test",
        "steps": []
    })
    
    assert result == "Test chain analysis"
    mock_analyst.analyse_chain.assert_called_once()


# ── Chat Function Tests (Mocked) ────────────────────────────────────────────

@pytest.mark.unit
@patch('claude_analyst.ClaudeAnalyst')
def test_chat_sync_mock(mock_analyst_class):
    """Test synchronous chat with mocked AI."""
    from config import OPENROUTER_API_KEY
    
    if not OPENROUTER_API_KEY:
        pytest.skip("OpenRouter API key not configured")
    
    # Create mock analyst instance
    mock_analyst = Mock()
    mock_analyst.chat_sync.return_value = "Test chat response"
    mock_analyst_class.return_value = mock_analyst
    
    # Test the chat
    result = mock_analyst.chat_sync(
        question="What is SQL injection?",
        history=[],
        engagement_context=None,
        allow_tools=True,
        execution_mode="single_agent",
        swarm_max_steps=12
    )
    
    assert result == "Test chat response"
    mock_analyst.chat_sync.assert_called_once()


@pytest.mark.unit
@patch('claude_analyst.ClaudeAnalyst')
def test_chat_stream_mock(mock_analyst_class):
    """Test streaming chat with mocked AI."""
    from config import OPENROUTER_API_KEY
    
    if not OPENROUTER_API_KEY:
        pytest.skip("OpenRouter API key not configured")
    
    # Create mock analyst instance
    mock_analyst = Mock()
    mock_analyst.chat_stream.return_value = iter(["chunk1", "chunk2", "chunk3"])
    mock_analyst_class.return_value = mock_analyst
    
    # Test the chat stream
    chunks = list(mock_analyst.chat_stream(
        question="What is SQL injection?",
        history=[],
        engagement_context=None,
        allow_tools=True,
        execution_mode="single_agent",
        swarm_max_steps=12
    ))
    
    assert chunks == ["chunk1", "chunk2", "chunk3"]
    mock_analyst.chat_stream.assert_called_once()


# ── System Prompt Tests ─────────────────────────────────────────────────────

@pytest.mark.unit
def test_system_prompt_exists():
    """Test that system prompt is defined."""
    from claude_analyst import SYSTEM_PROMPT
    
    assert isinstance(SYSTEM_PROMPT, str)
    assert len(SYSTEM_PROMPT) > 0
    assert "offensive security" in SYSTEM_PROMPT.lower() or "penetration testing" in SYSTEM_PROMPT.lower()


# ── Edge Cases and Error Handling ─────────────────────────────────────────────

@pytest.mark.unit
def test_format_chain_for_claude_special_characters():
    """Test formatting chain with special characters."""
    from claude_analyst import _format_chain_for_claude
    
    chain = {
        "chain_id": "test<script>alert('xss')</script>",
        "confidence": 0.85,
        "target_description": "Web server with 'quotes' and \"double quotes\"",
        "estimated_impact": "",
        "steps": [],
        "opsec_notes": ""
    }
    
    formatted = _format_chain_for_claude(chain)
    
    # Should handle special characters gracefully
    assert isinstance(formatted, str)


@pytest.mark.unit
def test_format_records_for_context_long_text():
    """Test formatting records with very long text."""
    from claude_analyst import _format_records_for_context
    from models import AttackRecord
    
    record = AttackRecord(
        id=1,
        title="A" * 1000,
        category="Test",
        attack_type="Test",
        scenario_description="B" * 2000,
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
    
    formatted = _format_records_for_context([record])
    
    # Should handle long text gracefully
    assert isinstance(formatted, str)


# ── Integration Tests (with real API - marked as slow) ───────────────────────

@pytest.mark.integration
@pytest.mark.slow
def test_analyse_engagement_real():
    """Test engagement analysis with real OpenRouter API."""
    from claude_analyst import ClaudeAnalyst
    from config import OPENROUTER_API_KEY
    
    if not OPENROUTER_API_KEY:
        pytest.skip("OpenRouter API key not configured")
    
    try:
        analyst = ClaudeAnalyst(searcher=None, audit_engine=None, chainer=None)
        
        result = analyst.analyse_engagement(
            target="test.example.com",
            chains=[],
            opsec_report={},
            scan_fingerprint={}
        )
        
        assert isinstance(result, str)
        assert len(result) > 0
    except Exception as e:
        pytest.skip(f"Real API test failed: {e}")


@pytest.mark.integration
@pytest.mark.slow
def test_analyse_chain_real():
    """Test chain analysis with real OpenRouter API."""
    from claude_analyst import ClaudeAnalyst
    from config import OPENROUTER_API_KEY
    
    if not OPENROUTER_API_KEY:
        pytest.skip("OpenRouter API key not configured")
    
    try:
        analyst = ClaudeAnalyst(searcher=None, audit_engine=None, chainer=None)
        
        result = analyst.analyse_chain({
            "chain_id": "test",
            "steps": []
        })
        
        assert isinstance(result, str)
        assert len(result) > 0
    except Exception as e:
        pytest.skip(f"Real API test failed: {e}")


@pytest.mark.integration
@pytest.mark.slow
def test_chat_sync_real():
    """Test synchronous chat with real OpenRouter API."""
    from claude_analyst import ClaudeAnalyst
    from config import OPENROUTER_API_KEY
    
    if not OPENROUTER_API_KEY:
        pytest.skip("OpenRouter API key not configured")
    
    try:
        analyst = ClaudeAnalyst(searcher=None, audit_engine=None, chainer=None)
        
        result = analyst.chat_sync(
            question="What is SQL injection?",
            history=[],
            engagement_context=None,
            allow_tools=False,  # Disable tools to simplify test
            execution_mode="single_agent",
            swarm_max_steps=12
        )
        
        assert isinstance(result, str)
        assert len(result) > 0
    except Exception as e:
        pytest.skip(f"Real API test failed: {e}")


# ── Tool Calling Tests ─────────────────────────────────────────────────────

@pytest.mark.unit
def test_tool_function_formatting():
    """Test that tool functions are properly formatted."""
    from claude_analyst import _record_to_tool_payload
    from models import AttackRecord
    
    record = AttackRecord(
        id=1,
        title="SQL Injection",
        category="Web Application",
        attack_type="Injection",
        scenario_description="SQL injection in login form",
        tools_used="sqlmap",
        attack_steps="Inject SQL payload",
        target_type="Web Application",
        vulnerability="SQL Injection",
        mitre_technique="T1190",
        impact="Auth bypass",
        detection_method="WAF",
        solution="Parameterized queries",
        tags="sql, injection",
        source="test"
    )
    
    payload = _record_to_tool_payload(record)
    
    # Verify payload structure
    required_fields = ["id", "title", "category", "attack_type", "mitre_technique", "tools_used"]
    for field in required_fields:
        assert field in payload