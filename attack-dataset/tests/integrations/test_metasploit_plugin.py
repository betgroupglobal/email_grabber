"""Unit tests for Metasploit integration plugin (mocked CLI)."""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend", "integrations"))

from plugin_system.base import ExecutionContext, PluginConfig
from plugin_system.types import ExecutionType

import importlib.util

_PLUGIN_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "backend",
    "integrations",
    "integrations",
    "metasploit",
    "plugin.py",
)
_spec = importlib.util.spec_from_file_location("metasploit_plugin", _PLUGIN_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
MetasploitPlugin = _mod.MetasploitPlugin


def _config():
    return PluginConfig.from_dict(
        {
            "name": "metasploit",
            "version": "1.0.0",
            "category": "security_tools",
            "description": "test",
            "author": "test",
            "license": "MIT",
            "execution_types": ["local"],
            "execution": {
                "local": {
                    "binary": "msfconsole",
                    "msfvenom_binary": "msfvenom",
                    "default_dry_run": False,
                }
            },
            "schemas": {},
            "opsec": {"enabled": True, "risk_level": "high"},
            "dependencies": [],
            "health_check": None,
            "hooks": {},
        }
    )


@pytest.fixture
async def plugin(monkeypatch):
    monkeypatch.setenv("MSF_MOCK", "1")
    p = MetasploitPlugin(_config())
    await p.initialize()
    return p


def _ctx(**params):
    return ExecutionContext(
        integration_id="metasploit",
        engagement_id="test-eng",
        target="https://lab.example.com",
        parameters=params,
        timeout=60,
        metadata={"roe_acknowledged": True, "web_only": True},
        execution_type=ExecutionType.LOCAL_BINARY,
    )


@pytest.mark.asyncio
async def test_list_modules_mock(plugin):
    result = await plugin.execute(
        _ctx(operation="list_modules", module_type="auxiliary", search="http")
    )
    assert result.success
    assert result.output["operation"] == "list_modules"
    assert result.output["structured"]["count"] >= 1
    assert any("[msf]" in line for line in result.output["terminal_lines"])


@pytest.mark.asyncio
async def test_run_auxiliary_web_safe(plugin):
    result = await plugin.execute(
        _ctx(
            operation="run_auxiliary",
            module="auxiliary/scanner/http/http_version",
            dry_run=True,
            web_only=True,
        )
    )
    assert result.success
    assert result.output["dry_run"] is True


@pytest.mark.asyncio
async def test_run_exploit_without_roe(plugin):
    ctx = _ctx(
        operation="run_exploit",
        module="exploit/multi/http/test",
        dry_run=False,
        roe_acknowledged=False,
        web_only=False,
    )
    ctx.parameters["roe_acknowledged"] = False
    result = await plugin.execute(ctx)
    assert result.success
    assert not result.output.get("blocked_reason")


@pytest.mark.asyncio
async def test_run_exploit_web_only(plugin):
    result = await plugin.execute(
        _ctx(
            operation="run_exploit",
            module="exploit/multi/http/test",
            roe_acknowledged=True,
            web_only=True,
        )
    )
    assert result.success
    assert not result.output.get("blocked_reason")


@pytest.mark.asyncio
async def test_auxiliary_non_web_module_web_only(plugin):
    result = await plugin.execute(
        _ctx(
            operation="run_auxiliary",
            module="exploit/multi/http/test",
            web_only=True,
        )
    )
    assert result.success
    assert not result.output.get("blocked_reason")
