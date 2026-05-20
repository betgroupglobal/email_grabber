"""Unit tests for sqlmap integration plugin (mock CLI)."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend", "integrations"))

from plugin_system.base import PluginConfig, ExecutionContext
import importlib.util

_SQLMAP_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "backend",
    "integrations",
    "integrations",
    "sqlmap",
    "plugin.py",
)
_spec = importlib.util.spec_from_file_location("sqlmap_plugin", _SQLMAP_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
SqlmapPlugin = _mod.SqlmapPlugin


@pytest.fixture
def sqlmap_plugin(monkeypatch):
    monkeypatch.setenv("SQLMAP_MOCK", "1")
    config = PluginConfig.from_dict(
        {
            "name": "sqlmap",
            "version": "1.0.0",
            "category": "security_tools",
            "description": "test",
            "author": "test",
            "license": "MIT",
            "execution_types": ["local"],
            "execution": {"local": {"binary": "sqlmap", "timeout": 60}},
            "schemas": {},
            "opsec": {"enabled": True},
            "dependencies": [],
            "health_check": None,
            "hooks": {},
        }
    )
    return SqlmapPlugin(config)


@pytest.mark.asyncio
async def test_sqlmap_test_url_without_roe(sqlmap_plugin):
    await sqlmap_plugin.initialize()
    ctx = ExecutionContext(
        integration_id="sqlmap",
        engagement_id="test",
        target="http://example.com/page?id=1",
        parameters={"operation": "test_url", "roe_acknowledged": False},
        timeout=60,
        metadata={},
    )
    result = await sqlmap_plugin.execute(ctx)
    assert result.success
    assert result.output["operation"] == "test_url"


@pytest.mark.asyncio
async def test_sqlmap_test_url_mock_with_roe(sqlmap_plugin):
    await sqlmap_plugin.initialize()
    ctx = ExecutionContext(
        integration_id="sqlmap",
        engagement_id="test",
        target="http://example.com/page?id=1",
        parameters={"operation": "test_url", "roe_acknowledged": True},
        timeout=60,
        metadata={},
    )
    result = await sqlmap_plugin.execute(ctx)
    assert result.success
    assert result.output["operation"] == "test_url"


@pytest.mark.asyncio
async def test_sqlmap_allows_os_shell_flag(sqlmap_plugin):
    await sqlmap_plugin.initialize()
    ctx = ExecutionContext(
        integration_id="sqlmap",
        engagement_id="test",
        target="http://example.com",
        parameters={
            "operation": "test_url",
            "roe_acknowledged": True,
            "extra_args": "--os-shell",
        },
        timeout=60,
        metadata={},
    )
    result = await sqlmap_plugin.execute(ctx)
    assert result.success
    assert not result.output.get("blocked_reason")
