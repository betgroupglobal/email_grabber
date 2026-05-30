"""Unit tests for target profiling and relevance filtering (no Qdrant import)."""
import importlib.util
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "backend"

_models_path = _BACKEND / "knowledge_engine" / "core" / "models.py"
_mspec = importlib.util.spec_from_file_location("ke_models_prof", _models_path)
_models = importlib.util.module_from_spec(_mspec)
_mspec.loader.exec_module(_models)
AttackRecord = _models.AttackRecord
AttackResult = _models.AttackResult

_prof_path = _BACKEND / "knowledge_engine" / "search" / "target_profiling.py"
_spec = importlib.util.spec_from_file_location("target_profiling", _prof_path)
_mod = importlib.util.module_from_spec(_spec)
# Inject models before loading (relative import in module uses ..core.models)
sys.modules["knowledge_engine.core.models"] = _models
_spec.loader.exec_module(_mod)

infer_target_profile = _mod.infer_target_profile
enrich_search_query = _mod.enrich_search_query
keyword_relevance = _mod.keyword_relevance
filter_and_rerank_results = _mod.filter_and_rerank_results
combined_relevance = _mod.combined_relevance


def _record(title: str, category: str = "", tags: str = "") -> AttackRecord:
    return AttackRecord(
        id=1,
        title=title,
        category=category or "General",
        attack_type="Test",
        scenario_description=f"Scenario for {title}",
        tools_used="",
        attack_steps="",
        target_type="",
        vulnerability="",
        mitre_technique="T1190",
        impact="",
        detection_method="",
        solution="",
        tags=tags,
        source="test",
    )


@pytest.mark.unit
def test_infer_web_ecommerce_from_domain():
    profile = infer_target_profile(
        "Target mobileciti.com.au — e-commerce / online retail",
        ["https port:443", "http port:80"],
    )
    assert profile.target_class in ("web_application", "ecommerce")


@pytest.mark.unit
def test_keyword_relevance_excludes_satellite_for_web():
    profile = infer_target_profile(
        "Target shop.example.com web application HTTPS",
        ["https port:443"],
    )
    web_rec = _record("SQL Injection in login form", category="Web Application Security", tags="web sqli")
    sat_rec = _record("Satellite GPS jamming for firefighting aircraft", category="Physical", tags="satellite gps")

    assert keyword_relevance(web_rec, profile) > 0.3
    assert keyword_relevance(sat_rec, profile) < 0


@pytest.mark.unit
def test_filter_and_rerank_prefers_web_records():
    profile = infer_target_profile(
        "Target mobileciti.com.au public web application OWASP",
        ["https port:443", "http port:80"],
    )
    results = [
        AttackResult(record=_record("Z-Wave motion sensor replay", tags="z-wave iot"), score=0.9),
        AttackResult(record=_record("IMSI catcher passive capture", tags="imsi cellular"), score=0.85),
        AttackResult(
            record=_record("Cross-site scripting in storefront", category="Web Application", tags="xss web"),
            score=0.55,
        ),
        AttackResult(
            record=_record("Subdomain enumeration and DNS recon", category="Reconnaissance", tags="dns osint"),
            score=0.5,
        ),
    ]
    filtered = filter_and_rerank_results(results, profile, min_score=0.2, max_candidates=10)
    titles = [r.record.title.lower() for r in filtered]
    assert not any("z-wave" in t for t in titles)
    assert not any("imsi" in t for t in titles)
    assert any("xss" in t or "subdomain" in t or "dns" in t for t in titles)


@pytest.mark.unit
def test_enrich_search_query_includes_web_hints():
    profile = infer_target_profile("Target example.com", ["https port:443"])
    q = enrich_search_query("Target example.com", ["https port:443"], "unknown", profile)
    assert "owasp" in q.lower() or "web application" in q.lower()


@pytest.mark.unit
def test_combined_relevance_negative_for_excluded():
    profile = infer_target_profile("Target shop.com web", ["http port:80"])
    rec = _record("AR spoofing attack against responders")
    assert combined_relevance(0.95, rec, profile) < 0


@pytest.mark.unit
def test_keyword_relevance_excludes_emoji_vote_scam():
    profile = infer_target_profile(
        "Target mobileciti.com.au public web application",
        ["https port:443"],
    )
    scam = _record(
        "Emoji vote scam on Instagram to boost product reviews",
        category="Social Engineering",
        tags="emoji vote scam instagram",
    )
    web = _record("SQL injection in checkout API", category="Web Application", tags="sqli web")
    assert keyword_relevance(scam, profile) < 0
    assert keyword_relevance(web, profile) > 0.3
