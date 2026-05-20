"""Unit tests for ffuf integration plugin (mock CLI)."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend", "integrations"))

from plugin_system.base import PluginConfig, ExecutionContext
from integrations.ffuf.plugin import FfufPlugin


@pytest.fixture
def ffuf_plugin(monkeypatch):
    monkeypatch.setenv("FFUF_MOCK", "1")
    config = PluginConfig.from_dict(
        {
            "name": "ffuf",
            "version": "1.0.0",
            "category": "security_tools",
            "description": "test",
            "author": "test",
            "license": "MIT",
            "execution_types": ["local"],
            "execution": {"local": {"binary": "ffuf", "timeout": 60}},
            "schemas": {},
            "opsec": {"enabled": True},
            "dependencies": [],
            "health_check": None,
            "hooks": {},
        }
    )
    return FfufPlugin(config)


@pytest.mark.asyncio
async def test_ffuf_fuzz_url_mock(ffuf_plugin):
    await ffuf_plugin.initialize()
    ctx = ExecutionContext(
        integration_id="ffuf",
        engagement_id="test",
        target="https://example.com",
        parameters={"operation": "fuzz_url"},
        timeout=60,
        metadata={},
    )
    result = await ffuf_plugin.execute(ctx)
    assert result.success
    assert result.output["operation"] == "fuzz_url"
    assert len(result.output["structured"]["results"]) >= 1


@pytest.mark.asyncio
async def test_ffuf_fuzz_vhost_mock(ffuf_plugin):
    await ffuf_plugin.initialize()
    ctx = ExecutionContext(
        integration_id="ffuf",
        engagement_id="test",
        target="example.com",
        parameters={"operation": "fuzz_vhost", "vhost_domain": "example.com"},
        timeout=60,
        metadata={},
    )
    result = await ffuf_plugin.execute(ctx)
    assert result.success
    assert result.output["operation"] == "fuzz_vhost"
