"""
MCP Burp bridge plugin — Integration Hub discoverability.

Primary execution path: orchestrator toolExecutor → mcpClient.js (lower latency).
This plugin documents operations and returns mock/status when ORCHESTRATOR_URL is unset.
"""

import json
import logging
import os
import time
from typing import Any, Dict

import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from plugin_system.base import (
    BasePlugin,
    PluginConfig,
    ExecutionContext,
    ExecutionResult,
)

logger = logging.getLogger(__name__)

MOCK_TOOLS = [
    {"name": "send_http1_request", "description": "HTTP/1.1 request via Burp"},
    {"name": "get_proxy_http_history", "description": "Proxy HTTP history"},
    {"name": "get_scanner_issues", "description": "Scanner issues"},
]


def _truthy(key: str) -> bool:
    return os.environ.get(key, "").lower() in ("1", "true", "yes")


class McpBurpPlugin(BasePlugin):
    """Burp MCP — list/call tools (orchestrator-native preferred)."""

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.orchestrator_url = (
            os.environ.get("ORCHESTRATOR_URL") or "http://localhost:3001"
        ).rstrip("/")
        self._mock = _truthy("MCP_MOCK") or not _truthy("MCP_BURP_ENABLED")

    async def initialize(self) -> None:
        self._initialized = True
        self.status = self.status.READY
        logger.info(
            "mcp_burp plugin ready (mock=%s, burp_enabled=%s)",
            self._mock,
            _truthy("MCP_BURP_ENABLED"),
        )

    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        start = time.time()
        params = dict(context.parameters or {})
        operation = str(params.get("operation", "list_mcp_tools")).lower()

        try:
            if operation == "list_servers":
                output = await self._list_servers()
            elif operation == "list_mcp_tools":
                output = await self._list_tools(params.get("mcp_server", "burp"))
            elif operation == "call_mcp_tool":
                output = await self._call_tool(
                    params.get("mcp_server", "burp"),
                    params.get("mcp_tool") or params.get("tool"),
                    params.get("arguments") or {},
                )
            else:
                return ExecutionResult(
                    success=False,
                    error=f"Unknown operation: {operation}",
                    execution_time=time.time() - start,
                )

            lines = output.get("terminal_lines") or [
                f"[burp] {operation}: ok"
            ]
            return ExecutionResult(
                success=True,
                output={**output, "terminal_lines": lines},
                execution_time=time.time() - start,
            )
        except Exception as exc:
            logger.exception("mcp_burp execute failed")
            return ExecutionResult(
                success=False,
                error=str(exc),
                execution_time=time.time() - start,
            )

    async def _list_servers(self) -> Dict[str, Any]:
        if self._mock:
            return {
                "servers": [{"id": "burp", "name": "PortSwigger Burp MCP", "transport": "mock"}],
                "terminal_lines": ["[mcp] list_servers: mock"],
            }
        return {
            "servers": [{"id": "burp", "transport": "sse", "url": os.environ.get("MCP_BURP_URL", "http://127.0.0.1:9876")}],
            "note": "Use orchestrator MCP_BURP_* env for live calls",
            "terminal_lines": ["[mcp] list_servers: burp configured"],
        }

    async def _list_tools(self, server_id: str) -> Dict[str, Any]:
        if self._mock:
            return {
                "mcp_server": server_id,
                "tools": MOCK_TOOLS,
                "terminal_lines": [f"[mcp] list_mcp_tools({server_id}): {len(MOCK_TOOLS)} tools"],
            }
        return {
            "mcp_server": server_id,
            "tools": MOCK_TOOLS,
            "delegation": "orchestrator",
            "terminal_lines": [f"[mcp] list tools via orchestrator /mcp/status"],
        }

    async def _call_tool(
        self, server_id: str, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not tool_name:
            raise ValueError("mcp_tool is required for call_mcp_tool")
        if self._mock:
            return {
                "mcp_server": server_id,
                "mcp_tool": tool_name,
                "result": {"mock": True, "tool": tool_name, "arguments": arguments},
                "terminal_lines": [f"[burp] mock {tool_name}: ok"],
            }
        return {
            "mcp_server": server_id,
            "mcp_tool": tool_name,
            "delegation": self.orchestrator_url,
            "message": "Invoke via orchestrator plugin=mcp_burp for live MCP",
            "terminal_lines": [f"[burp] delegate {tool_name} to orchestrator"],
        }
