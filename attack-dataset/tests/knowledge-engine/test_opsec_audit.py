"""
Tests for OpSecAuditEngine - OpSec risk assessment and tool analysis.
"""
import pytest
from opsec_audit import (
    OpSecAuditEngine,
    RiskLevel,
    ToolRisk,
    StepRisk,
    ChainAuditResult
)


# ── OpSec Audit Engine Initialization ───────────────────────────────────────

@pytest.mark.integration
def test_opsec_engine_initialization(opsec_engine):
    """Test that OpSec audit engine initializes correctly."""
    assert opsec_engine is not None
    assert hasattr(opsec_engine, 'tool_data')
    assert hasattr(opsec_engine, 'tool_lookup')
    assert hasattr(opsec_engine, 'risk_keywords')


# ── Tool Extraction Tests ────────────────────────────────────────────────────

@pytest.mark.integration
def test_extract_tools_basic(opsec_engine):
    """Test basic tool extraction from text."""
    text = "Use nmap to scan ports and sqlmap for injection"
    tools = opsec_engine._extract_tools_from_text(text)
    
    assert isinstance(tools, list)
    assert 'nmap' in [t.lower() for t in tools] or 'nmap' in tools


@pytest.mark.integration
def test_extract_tools_case_insensitive(opsec_engine):
    """Test that tool extraction is case-insensitive."""
    text_lower = "use nmap to scan"
    text_upper = "use NMAP to scan"
    text_mixed = "use NmAp to scan"
    
    tools_lower = opsec_engine._extract_tools_from_text(text_lower)
    tools_upper = opsec_engine._extract_tools_from_text(text_upper)
    tools_mixed = opsec_engine._extract_tools_from_text(text_mixed)
    
    # All should find the tool
    assert len(tools_lower) > 0 or len(tools_upper) > 0


@pytest.mark.integration
def test_extract_tools_multiple(opsec_engine):
    """Test extracting multiple tools from text."""
    text = "Use nmap for scanning, sqlmap for injection, and hydra for brute force"
    tools = opsec_engine._extract_tools_from_text(text)
    
    assert isinstance(tools, list)
    assert len(tools) >= 1  # At least one tool should be found


@pytest.mark.integration
def test_extract_tools_no_tools(opsec_engine):
    """Test tool extraction with no recognizable tools."""
    text = "This is a generic text without any security tools"
    tools = opsec_engine._extract_tools_from_text(text)
    
    assert isinstance(tools, list)
    # Should return empty list or very few results
    assert len(tools) <= 1


@pytest.mark.integration
def test_extract_tools_partial_match(opsec_engine):
    """Test tool extraction with partial matches."""
    text = "Use nmap-scanner and sqlmap-tool"
    tools = opsec_engine._extract_tools_from_text(text)
    
    assert isinstance(tools, list)


# ── Tool Risk Assessment Tests ─────────────────────────────────────────────

@pytest.mark.integration
def test_assess_tool_risk_known_tool(opsec_engine):
    """Test risk assessment for a known tool."""
    risk = opsec_engine._assess_tool_risk("nmap")
    
    assert risk is not None
    assert isinstance(risk, ToolRisk)
    assert risk.tool_name == "nmap"
    assert hasattr(risk, 'risk_level')
    assert hasattr(risk, 'risk_factors')
    assert hasattr(risk, 'detection_methods')
    assert hasattr(risk, 'opsec_recommendations')


@pytest.mark.integration
def test_assess_tool_risk_unknown_tool(opsec_engine):
    """Test risk assessment for an unknown tool."""
    risk = opsec_engine._assess_tool_risk("unknown_tool_xyz123")
    
    assert risk is not None
    assert risk.tool_name == "unknown_tool_xyz123"
    assert risk.risk_level == RiskLevel.MEDIUM  # Default for unknown tools
    assert len(risk.risk_factors) > 0


@pytest.mark.integration
def test_assess_tool_risk_detection_methods(opsec_engine):
    """Test that detection methods are populated."""
    risk = opsec_engine._assess_tool_risk("nmap")
    
    assert risk is not None
    assert isinstance(risk.detection_methods, list)
    assert len(risk.detection_methods) > 0


@pytest.mark.integration
def test_assess_tool_risk_recommendations(opsec_engine):
    """Test that OpSec recommendations are provided."""
    risk = opsec_engine._assess_tool_risk("nmap")
    
    assert risk is not None
    assert isinstance(risk.opsec_recommendations, list)
    assert len(risk.opsec_recommendations) > 0


@pytest.mark.integration
def test_assess_tool_risk_substitution(opsec_engine):
    """Test that tool substitution alternatives are provided when available."""
    risk = opsec_engine._assess_tool_risk("nmap")
    
    assert risk is not None
    # substitution_alternative may be None if no substitution is defined
    assert risk.substitution_alternative is None or isinstance(risk.substitution_alternative, str)


# ── Risk Level Tests ────────────────────────────────────────────────────────

@pytest.mark.integration
def test_risk_level_comparison():
    """Test RiskLevel comparison operators."""
    assert RiskLevel.LOW < RiskLevel.MEDIUM
    assert RiskLevel.MEDIUM < RiskLevel.HIGH
    assert RiskLevel.HIGH < RiskLevel.CRITICAL
    assert RiskLevel.INFO < RiskLevel.LOW
    
    assert RiskLevel.CRITICAL > RiskLevel.HIGH
    assert RiskLevel.HIGH > RiskLevel.MEDIUM
    assert RiskLevel.MEDIUM > RiskLevel.LOW


@pytest.mark.integration
def test_risk_level_values():
    """Test RiskLevel enum values."""
    assert RiskLevel.INFO.value == "info"
    assert RiskLevel.LOW.value == "low"
    assert RiskLevel.MEDIUM.value == "medium"
    assert RiskLevel.HIGH.value == "high"
    assert RiskLevel.CRITICAL.value == "critical"


# ── Chain Auditing Tests ───────────────────────────────────────────────────

@pytest.mark.integration
def test_audit_chain_basic(opsec_engine):
    """Test basic chain auditing."""
    steps = [
        "Use nmap to scan ports",
        "Exploit SQL injection with sqlmap",
        "Establish reverse shell with netcat"
    ]
    
    result = opsec_engine.audit_chain(
        chain_id="test_chain_1",
        chain_description="Test attack chain",
        steps=steps
    )
    
    assert result is not None
    assert isinstance(result, ChainAuditResult)
    assert result.chain_id == "test_chain_1"
    assert result.chain_description == "Test attack chain"
    assert hasattr(result, 'overall_risk_score')
    assert hasattr(result, 'overall_risk_level')
    assert hasattr(result, 'step_risks')
    assert hasattr(result, 'critical_findings')
    assert hasattr(result, 'tool_substitutions')
    assert hasattr(result, 'evasive_techniques')


@pytest.mark.integration
def test_audit_chain_empty_steps(opsec_engine):
    """Test chain auditing with empty steps."""
    result = opsec_engine.audit_chain(
        chain_id="test_chain_empty",
        chain_description="Empty chain",
        steps=[]
    )
    
    assert result is not None
    assert len(result.step_risks) == 0
    assert result.overall_risk_score == 0.0


@pytest.mark.integration
def test_audit_chain_single_step(opsec_engine):
    """Test chain auditing with single step."""
    steps = ["Use nmap to scan ports"]
    
    result = opsec_engine.audit_chain(
        chain_id="test_chain_single",
        chain_description="Single step chain",
        steps=steps
    )
    
    assert result is not None
    assert len(result.step_risks) == 1


@pytest.mark.integration
def test_audit_chain_many_steps(opsec_engine):
    """Test chain auditing with many steps."""
    steps = [
        f"Use tool{i} for attack{i}" for i in range(10)
    ]
    
    result = opsec_engine.audit_chain(
        chain_id="test_chain_many",
        chain_description="Many steps chain",
        steps=steps
    )
    
    assert result is not None
    assert len(result.step_risks) == 10


@pytest.mark.integration
def test_audit_chain_risk_score(opsec_engine):
    """Test that overall risk score is calculated correctly."""
    steps = [
        "Use nmap to scan ports",
        "Exploit with highly detectable tool"
    ]
    
    result = opsec_engine.audit_chain(
        chain_id="test_chain_score",
        chain_description="Test score calculation",
        steps=steps
    )
    
    assert result is not None
    assert isinstance(result.overall_risk_score, (int, float))
    assert 0 <= result.overall_risk_score <= 100


@pytest.mark.integration
def test_audit_chain_risk_level(opsec_engine):
    """Test that overall risk level is determined correctly."""
    steps = ["Use nmap to scan ports"]
    
    result = opsec_engine.audit_chain(
        chain_id="test_chain_level",
        chain_description="Test risk level",
        steps=steps
    )
    
    assert result is not None
    assert isinstance(result.overall_risk_level, RiskLevel)


@pytest.mark.integration
def test_audit_chain_critical_findings(opsec_engine):
    """Test that critical findings are identified."""
    steps = [
        "Use highly signatured tool for attack",
        "Perform heavily monitored action"
    ]
    
    result = opsec_engine.audit_chain(
        chain_id="test_chain_critical",
        chain_description="Test critical findings",
        steps=steps
    )
    
    assert result is not None
    assert isinstance(result.critical_findings, list)


@pytest.mark.integration
def test_audit_chain_tool_substitutions(opsec_engine):
    """Test that tool substitutions are identified."""
    steps = ["Use nmap to scan ports"]
    
    result = opsec_engine.audit_chain(
        chain_id="test_chain_subs",
        chain_description="Test substitutions",
        steps=steps
    )
    
    assert result is not None
    assert isinstance(result.tool_substitutions, dict)


@pytest.mark.integration
def test_audit_chain_evasive_techniques(opsec_engine):
    """Test that evasive techniques are identified."""
    steps = [
        "Use passive scanning to avoid detection",
        "Encode payload to bypass WAF",
        "Use LOLBin technique for execution"
    ]
    
    result = opsec_engine.audit_chain(
        chain_id="test_chain_evasive",
        chain_description="Test evasive techniques",
        steps=steps
    )
    
    assert result is not None
    assert isinstance(result.evasive_techniques, list)
    # Should identify at least some evasive techniques
    assert len(result.evasive_techniques) > 0


@pytest.mark.integration
def test_audit_chain_detection_coverage(opsec_engine):
    """Test that detection coverage is tracked."""
    steps = ["Use nmap to scan ports"]
    
    result = opsec_engine.audit_chain(
        chain_id="test_chain_coverage",
        chain_description="Test detection coverage",
        steps=steps
    )
    
    assert result is not None
    assert isinstance(result.detection_coverage, dict)


# ── Step Risk Tests ─────────────────────────────────────────────────────────

@pytest.mark.integration
def test_step_risk_structure(opsec_engine):
    """Test that step risks have proper structure."""
    steps = ["Use nmap to scan ports"]
    
    result = opsec_engine.audit_chain(
        chain_id="test_step_structure",
        chain_description="Test step structure",
        steps=steps
    )
    
    assert result is not None
    if result.step_risks:
        step_risk = result.step_risks[0]
        assert hasattr(step_risk, 'step_index')
        assert hasattr(step_risk, 'step_description')
        assert hasattr(step_risk, 'tools_found')
        assert hasattr(step_risk, 'tool_risks')
        assert hasattr(step_risk, 'overall_risk')
        assert hasattr(step_risk, 'recommendations')


# ── Tool Recommendation Tests ───────────────────────────────────────────────

@pytest.mark.integration
def test_get_tool_recommendations_known(opsec_engine):
    """Test getting recommendations for a known tool."""
    recommendations = opsec_engine.get_tool_recommendations("nmap")
    
    assert recommendations is not None
    assert recommendations['tool'] == "nmap"
    assert recommendations['found'] == True
    assert 'description' in recommendations
    assert 'risk_level' in recommendations
    assert 'opsec_recommendations' in recommendations


@pytest.mark.integration
def test_get_tool_recommendations_unknown(opsec_engine):
    """Test getting recommendations for an unknown tool."""
    recommendations = opsec_engine.get_tool_recommendations("unknown_tool_xyz123")
    
    assert recommendations is not None
    assert recommendations['tool'] == "unknown_tool_xyz123"
    assert recommendations['found'] == False
    assert 'message' in recommendations


@pytest.mark.integration
def test_get_tool_recommendations_structure(opsec_engine):
    """Test structure of tool recommendations."""
    recommendations = opsec_engine.get_tool_recommendations("nmap")
    
    if recommendations['found']:
        required_fields = [
            'tool', 'found', 'description', 'tactic', 'subcategory',
            'risk_level', 'risk_factors', 'detection_methods',
            'opsec_recommendations', 'substitution_alternative'
        ]
        for field in required_fields:
            assert field in recommendations


# ── Edge Cases and Error Handling ─────────────────────────────────────────────

@pytest.mark.integration
def test_audit_chain_special_characters(opsec_engine):
    """Test chain auditing with special characters."""
    steps = [
        "Use nmap'; DROP TABLE attacks; --",
        "Exploit with <script>alert('xss')</script>"
    ]
    
    result = opsec_engine.audit_chain(
        chain_id="test_chain_special",
        chain_description="Test special chars",
        steps=steps
    )
    
    # Should handle special characters gracefully
    assert result is not None


@pytest.mark.integration
def test_audit_chain_unicode(opsec_engine):
    """Test chain auditing with unicode characters."""
    steps = [
        "Use nmap to scan ñ 中文",
        "Exploit with unicode characters"
    ]
    
    result = opsec_engine.audit_chain(
        chain_id="test_chain_unicode",
        chain_description="Test unicode",
        steps=steps
    )
    
    assert result is not None


@pytest.mark.integration
def test_extract_tools_empty_text(opsec_engine):
    """Test tool extraction with empty text."""
    tools = opsec_engine._extract_tools_from_text("")
    
    assert isinstance(tools, list)
    assert len(tools) == 0


@pytest.mark.integration
def test_risk_keywords_detection(opsec_engine):
    """Test that risk keywords are properly detected."""
    # Test with a tool that has known risk keywords
    risk = opsec_engine._assess_tool_risk("nmap")
    
    assert risk is not None
    assert isinstance(risk.risk_factors, list)


# ── Attack Vector Auditing Tests ────────────────────────────────────────────

@pytest.mark.integration
def test_audit_attack_vector(opsec_engine):
    """Test auditing an attack vector dict."""
    attack_vector = {
        'id': 'test_vector_1',
        'description': 'Test attack vector',
        'steps': [
            {'description': 'Use nmap to scan ports'},
            {'description': 'Exploit SQL injection'}
        ]
    }
    
    result = opsec_engine.audit_attack_vector(attack_vector)
    
    assert result is not None
    assert isinstance(result, ChainAuditResult)


@pytest.mark.integration
def test_audit_attack_vector_missing_fields(opsec_engine):
    """Test auditing attack vector with missing fields."""
    attack_vector = {
        'id': 'test_vector_2'
        # Missing description and steps
    }
    
    result = opsec_engine.audit_attack_vector(attack_vector)
    
    # Should handle missing fields gracefully
    assert result is not None