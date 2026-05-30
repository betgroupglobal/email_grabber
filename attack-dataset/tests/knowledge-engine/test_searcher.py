"""
Tests for AttackSearcher - semantic and structured search functionality.
"""
import pytest
from searcher import AttackSearcher


# ── Initialization Tests ─────────────────────────────────────────────────────

@pytest.mark.integration
def test_searcher_initialization(searcher):
    """Test that AttackSearcher initializes correctly."""
    assert searcher is not None
    assert searcher.pg is not None
    assert searcher.qd is not None


@pytest.mark.integration
def test_searcher_embedding_disabled():
    """Test searcher behavior when embeddings are disabled."""
    # This test would require modifying config to disable embeddings
    # For now, we just test the basic initialization
    pass


# ── Semantic Search Tests ─────────────────────────────────────────────────────

@pytest.mark.integration
def test_semantic_search_basic(searcher, insert_test_records):
    """Test basic semantic search functionality."""
    response = searcher.semantic_search(
        query="SQL injection attack",
        top_k=5
    )
    
    assert response.query == "SQL injection attack"
    assert len(response.results) <= 5
    assert response.total == len(response.results)
    assert all(hasattr(r.record, 'id') for r in response.results)


@pytest.mark.integration
def test_semantic_search_with_category_filter(searcher, insert_test_records):
    """Test semantic search with category filter."""
    response = searcher.semantic_search(
        query="attack",
        top_k=10,
        category="Web Application"
    )
    
    # If embeddings are disabled, this will fall back to keyword search
    assert response.query == "attack"
    assert len(response.results) <= 10


@pytest.mark.integration
def test_semantic_search_with_attack_type_filter(searcher, insert_test_records):
    """Test semantic search with attack type filter."""
    response = searcher.semantic_search(
        query="attack",
        top_k=10,
        attack_type="Injection"
    )
    
    assert response.query == "attack"
    assert len(response.results) <= 10


@pytest.mark.integration
def test_semantic_search_with_mitre_filter(searcher, insert_test_records):
    """Test semantic search with MITRE technique filter."""
    response = searcher.semantic_search(
        query="attack",
        top_k=10,
        mitre="T1190"
    )
    
    assert response.query == "attack"
    assert len(response.results) <= 10


@pytest.mark.integration
def test_semantic_search_multiple_filters(searcher, insert_test_records):
    """Test semantic search with multiple filters."""
    response = searcher.semantic_search(
        query="attack",
        top_k=10,
        category="Web Application",
        attack_type="Injection",
        mitre="T1190"
    )
    
    assert response.query == "attack"
    assert len(response.results) <= 10


@pytest.mark.integration
def test_semantic_search_empty_query(searcher):
    """Test semantic search with empty query."""
    response = searcher.semantic_search(
        query="",
        top_k=5
    )
    
    # Should return empty results or handle gracefully
    assert response.total == len(response.results)


@pytest.mark.integration
def test_semantic_search_large_top_k(searcher, insert_test_records):
    """Test semantic search with large top_k value."""
    response = searcher.semantic_search(
        query="attack",
        top_k=50
    )
    
    assert len(response.results) <= 50


# ── Keyword Search Tests ─────────────────────────────────────────────────────

@pytest.mark.integration
def test_keyword_search_basic(searcher, insert_test_records):
    """Test basic keyword search."""
    results = searcher.keyword_search(
        keyword="SQL",
        limit=10
    )
    
    assert isinstance(results, list)
    assert len(results) <= 10
    assert all(hasattr(r, 'id') for r in results)


@pytest.mark.integration
def test_keyword_search_case_insensitive(searcher, insert_test_records):
    """Test that keyword search is case-insensitive."""
    results_lower = searcher.keyword_search("sql", limit=10)
    results_upper = searcher.keyword_search("SQL", limit=10)
    results_mixed = searcher.keyword_search("Sql", limit=10)
    
    # All should return results
    assert len(results_lower) > 0 or len(results_upper) > 0


@pytest.mark.integration
def test_keyword_search_phrase(searcher, insert_test_records):
    """Test keyword search with multi-word phrase."""
    results = searcher.keyword_search(
        keyword="SQL injection",
        limit=10
    )
    
    assert isinstance(results, list)
    assert len(results) <= 10


@pytest.mark.integration
def test_keyword_search_no_results(searcher):
    """Test keyword search with no matching results."""
    results = searcher.keyword_search(
        keyword="nonexistent_attack_xyz123",
        limit=10
    )
    
    assert isinstance(results, list)
    # Should return empty list or very few results
    assert len(results) <= 1


@pytest.mark.integration
def test_keyword_search_limit(searcher, insert_test_records):
    """Test keyword search with different limit values."""
    results_5 = searcher.keyword_search("attack", limit=5)
    results_20 = searcher.keyword_search("attack", limit=20)
    
    assert len(results_5) <= 5
    assert len(results_20) <= 20
    assert len(results_5) <= len(results_20)


# ── MITRE Technique Tests ─────────────────────────────────────────────────────

@pytest.mark.integration
def test_get_by_mitre_technique(searcher, insert_test_records):
    """Test getting attacks by MITRE technique ID."""
    results = searcher.get_by_mitre(
        technique_id="T1190",
        limit=10
    )
    
    assert isinstance(results, list)
    assert len(results) <= 10
    # If results exist, they should contain the MITRE technique
    if results:
        assert "T1190" in results[0].mitre_technique


@pytest.mark.integration
def test_get_by_mitre_partial_match(searcher, insert_test_records):
    """Test getting attacks with partial MITRE technique match."""
    results = searcher.get_by_mitre(
        technique_id="T11",
        limit=10
    )
    
    assert isinstance(results, list)
    assert len(results) <= 10


@pytest.mark.integration
def test_get_by_mitre_no_results(searcher):
    """Test getting attacks with non-existent MITRE technique."""
    results = searcher.get_by_mitre(
        technique_id="T9999",
        limit=10
    )
    
    assert isinstance(results, list)
    # Should return empty list
    assert len(results) == 0


# ── Category Tests ───────────────────────────────────────────────────────────

@pytest.mark.integration
def test_get_by_category(searcher, insert_test_records):
    """Test getting attacks by category."""
    results = searcher.get_by_category(
        category="Web",
        limit=10
    )
    
    assert isinstance(results, list)
    assert len(results) <= 10


@pytest.mark.integration
def test_get_by_category_exact_match(searcher, insert_test_records):
    """Test getting attacks with exact category match."""
    results = searcher.get_by_category(
        category="Web Application",
        limit=10
    )
    
    assert isinstance(results, list)
    assert len(results) <= 10


@pytest.mark.integration
def test_get_by_category_no_results(searcher):
    """Test getting attacks with non-existent category."""
    results = searcher.get_by_category(
        category="NonExistentCategory",
        limit=10
    )
    
    assert isinstance(results, list)
    # Should return empty list
    assert len(results) == 0


# ── Target Type Tests ────────────────────────────────────────────────────────

@pytest.mark.integration
def test_get_by_target_type(searcher, insert_test_records):
    """Test getting attacks by target type."""
    results = searcher.get_by_target(
        target_type="Web",
        limit=10
    )
    
    assert isinstance(results, list)
    assert len(results) <= 10


@pytest.mark.integration
def test_get_by_target_type_exact(searcher, insert_test_records):
    """Test getting attacks with exact target type match."""
    results = searcher.get_by_target(
        target_type="Web Application",
        limit=10
    )
    
    assert isinstance(results, list)
    assert len(results) <= 10


@pytest.mark.integration
def test_get_by_target_type_no_results(searcher):
    """Test getting attacks with non-existent target type."""
    results = searcher.get_by_target(
        target_type="NonExistentTarget",
        limit=10
    )
    
    assert isinstance(results, list)
    # Should return empty list
    assert len(results) == 0


# ── Listing Functions Tests ──────────────────────────────────────────────────

@pytest.mark.integration
def test_list_categories(searcher, insert_test_records):
    """Test listing all categories with counts."""
    categories = searcher.list_categories()
    
    assert isinstance(categories, list)
    assert len(categories) > 0
    # Each category should have 'category' and 'count' fields
    for cat in categories:
        assert 'category' in cat
        assert 'count' in cat


@pytest.mark.integration
def test_list_mitre_techniques(searcher, insert_test_records):
    """Test listing all MITRE techniques with counts."""
    techniques = searcher.list_mitre_techniques()
    
    assert isinstance(techniques, list)
    assert len(techniques) > 0
    # Each technique should have 'mitre_technique' and 'count' fields
    for tech in techniques:
        assert 'mitre_technique' in tech
        assert 'count' in tech


@pytest.mark.integration
def test_list_tools(searcher, insert_test_records):
    """Test listing all tools with frequencies."""
    tools = searcher.list_tools()
    
    assert isinstance(tools, list)
    assert len(tools) > 0
    # Each tool should have 'tool' and 'frequency' fields
    for tool in tools:
        assert 'tool' in tool
        assert 'frequency' in tool
        assert tool['frequency'] > 0


@pytest.mark.integration
def test_list_tools_sorted(searcher, insert_test_records):
    """Test that tools are sorted by frequency (descending)."""
    tools = searcher.list_tools()
    
    # Check that frequencies are in descending order
    frequencies = [tool['frequency'] for tool in tools]
    assert frequencies == sorted(frequencies, reverse=True)


# ── Edge Cases and Error Handling ─────────────────────────────────────────────

@pytest.mark.integration
def test_search_with_special_characters(searcher, insert_test_records):
    """Test search with special characters."""
    response = searcher.semantic_search(
        query="SQL injection'; DROP TABLE attacks; --",
        top_k=5
    )
    
    # Should handle SQL injection attempt gracefully
    assert response is not None


@pytest.mark.integration
def test_search_with_unicode(searcher, insert_test_records):
    """Test search with unicode characters."""
    response = searcher.semantic_search(
        query="attack ñ 中文",
        top_k=5
    )
    
    # Should handle unicode gracefully
    assert response is not None


@pytest.mark.integration
def test_keyword_search_empty_string(searcher):
    """Test keyword search with empty string."""
    results = searcher.keyword_search("", limit=10)
    
    # Should return empty list or handle gracefully
    assert isinstance(results, list)


@pytest.mark.integration
def test_embedding_cache(searcher, insert_test_records):
    """Test that embedding cache works (if embeddings enabled)."""
    if not searcher.use_embeddings:
        pytest.skip("Embeddings disabled, cache not applicable")
    
    # First search
    response1 = searcher.semantic_search("test query", top_k=5)
    # Second search with same query
    response2 = searcher.semantic_search("test query", top_k=5)
    
    # Results should be consistent
    assert len(response1.results) == len(response2.results)


# ── Data Integrity Tests ──────────────────────────────────────────────────────

@pytest.mark.integration
def test_attack_record_fields(searcher, insert_test_records):
    """Test that attack records have all required fields."""
    results = searcher.keyword_search("SQL", limit=1)
    
    if results:
        record = results[0]
        required_fields = [
            'id', 'title', 'category', 'attack_type', 
            'scenario_description', 'tools_used', 'attack_steps',
            'target_type', 'vulnerability', 'mitre_technique',
            'impact', 'detection_method', 'solution', 'tags', 'source'
        ]
        for field in required_fields:
            assert hasattr(record, field)


@pytest.mark.integration
def test_search_result_scores(searcher, insert_test_records):
    """Test that search results have valid scores."""
    response = searcher.semantic_search("attack", top_k=5)
    
    for result in response.results:
        assert hasattr(result, 'score')
        assert isinstance(result.score, (int, float))
        assert 0 <= result.score <= 1  # Scores should be between 0 and 1