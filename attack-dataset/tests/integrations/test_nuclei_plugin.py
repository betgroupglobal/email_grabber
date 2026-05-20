"""Unit tests for Nuclei integration plugin (mock CLI)."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend", "integrations"))

from plugin_system.base import PluginConfig, ExecutionContext
from integrations.nuclei.plugin import NucleiPlugin


@pytest.fixture
def nuclei_plugin(monkeypatch):
    monkeypatch.setenv("NUCLEI_MOCK", "1")
    config = PluginConfig.from_dict(
        {
            "name": "nuclei",
            "version": "1.0.0",
            "category": "security_tools",
            "description": "test",
            "author": "test",
            "license": "MIT",
            "execution_types": ["local"],
            "execution": {"local": {"binary": "nuclei", "timeout": 60}},
            "schemas": {},
            "opsec": {"enabled": True},
            "dependencies": [],
            "health_check": None,
            "hooks": {},
        }
    )
    plugin = NucleiPlugin(config)
    return plugin


@pytest.mark.asyncio
async def test_nuclei_scan_target_mock(nuclei_plugin):
    await nuclei_plugin.initialize()
    ctx = ExecutionContext(
        integration_id="nuclei",
        engagement_id="test",
        target="https://example.com",
        parameters={"operation": "scan_target", "severity": "high"},
        timeout=60,
        metadata={},
    )
    result = await nuclei_plugin.execute(ctx)
    assert result.success
    assert result.output["operation"] == "scan_target"
    assert any("[nuclei]" in ln for ln in result.output.get("terminal_lines", []))
    assert result.output["structured"]["finding_count"] >= 0


@pytest.mark.asyncio
async def test_nuclei_list_templates_mock(nuclei_plugin):
    await nuclei_plugin.initialize()
    ctx = ExecutionContext(
        integration_id="nuclei",
        engagement_id="test",
        target="example.com",
        parameters={"operation": "list_templates"},
        timeout=60,
        metadata={},
    )
    result = await nuclei_plugin.execute(ctx)
    assert result.success
    assert result.output["structured"]["count"] >= 1
