"""E2E-style tests for live council pivot flow (orchestrator modules)."""

import subprocess
from pathlib import Path

ORCH = Path(__file__).resolve().parents[2] / "backend" / "orchestrator" / "live-attack"


def test_failure_taxonomy_node_tests_pass():
    result = subprocess.run(
        ["node", "--test", str(ORCH / "__tests__" / "failure-taxonomy.test.js")],
        capture_output=True,
        text=True,
        cwd=str(ORCH),
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_directive_applier_node_tests_pass():
    result = subprocess.run(
        ["node", "--test", str(ORCH / "__tests__" / "directive-applier.test.js")],
        capture_output=True,
        text=True,
        cwd=str(ORCH),
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_coordinator_node_tests_pass():
    result = subprocess.run(
        ["node", "--test", str(ORCH / "__tests__" / "coordinator.test.js")],
        capture_output=True,
        text=True,
        cwd=str(ORCH),
    )
    assert result.returncode == 0, result.stderr or result.stdout
