"""Tests for live replan enhancements in AttackChainer."""

import importlib
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Stub search/ml deps so attack_chainer loads without qdrant, fastembed, or joblib
_searcher = types.ModuleType("knowledge_engine.search.searcher")
_searcher.AttackSearcher = MagicMock
sys.modules["knowledge_engine.search.searcher"] = _searcher

_profiling = types.ModuleType("knowledge_engine.search.target_profiling")
_profiling.infer_target_profile = lambda *a, **k: {}
_profiling.enrich_search_query = lambda q, *a, **k: q
_profiling.filter_and_rerank_results = lambda results, *a, **k: results
sys.modules["knowledge_engine.search.target_profiling"] = _profiling

_ml_service = types.ModuleType("knowledge_engine.ml.ml_service")
_ml_service.MLModelService = MagicMock
sys.modules["knowledge_engine.ml.ml_service"] = _ml_service

from knowledge_engine.core.models import (
    AttackChain,
    AttackRecord,
    AttackStep,
    ExecutionFeedbackContext,
    LiveReplanRequest,
)

AttackChainer = importlib.import_module("knowledge_engine.search.attack_chainer").AttackChainer


def _make_record(rid: int, title: str, tools: str, phase_hint: str = "exploitation") -> AttackRecord:
    return AttackRecord(
        id=rid,
        title=title,
        category="Network Security",
        attack_type=phase_hint,
        scenario_description=f"Test {title}",
        tools_used=tools,
        attack_steps="step1",
        target_type="web",
        vulnerability="x",
        mitre_technique="T1190",
        impact="high",
        detection_method="logs",
        solution="patch",
        tags="test",
        source="dataset",
    )


def _make_chain(steps, confidence=0.8, chain_id="c1") -> AttackChain:
    return AttackChain(
        chain_id=chain_id,
        target_description="test target",
        confidence=confidence,
        steps=steps,
        estimated_impact="medium",
        opsec_notes="test",
    )


@pytest.fixture
def chainer():
    searcher = MagicMock()
    return AttackChainer(searcher)


def test_build_live_replan_penalizes_failed_tool(chainer):
    sqlmap_step = AttackStep(
        phase="exploitation",
        attack=_make_record(1, "SQLi", "sqlmap"),
        rationale="sqlmap",
        mitre_technique="T1190",
    )
    nuclei_step = AttackStep(
        phase="exploitation",
        attack=_make_record(2, "Web scan", "nuclei"),
        rationale="nuclei",
        mitre_technique="T1190",
    )
    chain_sqlmap = _make_chain([sqlmap_step], confidence=0.9, chain_id="a")
    chain_nuclei = _make_chain([nuclei_step], confidence=0.7, chain_id="b")

    with patch.object(chainer, "build_chains") as mock_build:
        mock_build.return_value = MagicMock(
            target_description="test",
            chains=[chain_sqlmap, chain_nuclei],
        )
        chainer.searcher.semantic_search.return_value = MagicMock(results=[])

        req = LiveReplanRequest(
            target_description="target",
            execution_context=ExecutionFeedbackContext(
                last_failure={
                    "tool": "sqlmap",
                    "output": "failed",
                    "failure_class": "tool_blocked",
                },
                completed_steps=[{"phase": "reconnaissance", "status": "success"}],
            ),
            failure_class="tool_blocked",
        )
        resp = chainer.build_live_replan(req)

    assert resp.chains[0].confidence <= 0.9
    assert resp.alternate_chain_scores
    assert resp.failure_class == "tool_blocked"
    assert "failure_class=tool_blocked" in resp.grounding_query


def test_build_live_replan_filters_completed_phases(chainer):
    recon = AttackStep(
        phase="reconnaissance",
        attack=_make_record(10, "Recon", "nmap"),
        rationale="recon",
        mitre_technique="T1595",
    )
    exploit = AttackStep(
        phase="exploitation",
        attack=_make_record(11, "Exploit", "nuclei"),
        rationale="exploit",
        mitre_technique="T1190",
    )
    chain = _make_chain([recon, exploit], confidence=0.85)

    with patch.object(chainer, "build_chains") as mock_build:
        mock_build.return_value = MagicMock(target_description="test", chains=[chain])
        chainer.searcher.semantic_search.return_value = MagicMock(results=[])

        req = LiveReplanRequest(
            target_description="target",
            execution_context=ExecutionFeedbackContext(
                completed_steps=[
                    {"phase": "reconnaissance", "status": "success", "attack": {"title": "Recon"}},
                ],
            ),
        )
        resp = chainer.build_live_replan(req)

    assert len(resp.chains) == 1
    phases = [s.phase for s in resp.chains[0].steps]
    assert "reconnaissance" not in phases
    assert "exploitation" in phases
