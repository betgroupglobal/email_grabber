"""
sqlmap integration — SQL injection detection. Risk guardrails removed for authorized red-team use.
"""

import logging
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from plugin_system.base import (
    BasePlugin,
    PluginConfig,
    ExecutionContext,
    ExecutionResult,
)
from utils.cli_runner import run_cli, env_path, clip_output_lines

logger = logging.getLogger(__name__)
PREFIX = "[sqlmap]"

SAFE_DEFAULT_LEVEL = 1
SAFE_DEFAULT_RISK = 1


class SqlmapPlugin(BasePlugin):
    """sqlmap SQL injection scanner plugin."""

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        local = (config.execution or {}).get("local") or {}
        self.binary = env_path("SQLMAP_PATH", local.get("binary", "sqlmap"))
        self.timeout = int(local.get("timeout", 600))
        self.max_crawl_depth = int(local.get("max_crawl_depth", 2))
        self._mock = os.environ.get("SQLMAP_MOCK", "").lower() in ("1", "true", "yes")

    async def initialize(self) -> None:
        if self._mock:
            self._initialized = True
            self.status = self.status.READY
            return
        try:
            out = await run_cli([self.binary, "--version"], timeout=30)
            if "sqlmap" not in out.lower():
                raise RuntimeError("sqlmap --version unexpected output")
            self._initialized = True
            self.status = self.status.READY
        except Exception as exc:
            logger.warning("sqlmap init degraded: %s", exc)
            self._initialized = True
            self.status = self.status.READY

    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        start = time.time()
        params = dict(context.parameters or {})
        operation = str(params.get("operation", "test_url")).lower()
        target = params.get("target") or context.target or "unknown"

        try:
            if operation == "crawl_and_test":
                output = await self._crawl_and_test(params, target)
            elif operation == "test_url":
                output = await self._test_url(params, target)
            else:
                raise ValueError(f"Unknown operation: {operation}")

            elapsed = time.time() - start
            success = output.get("success", True) and not output.get("blocked_reason")
            return ExecutionResult(
                success=success,
                output=output,
                error=output.get("blocked_reason"),
                artifacts=[{"type": "sqlmap_output", "value": output}],
                opsec_context=self._opsec(operation, target, output),
                execution_time=elapsed,
            )
        except Exception as exc:
            elapsed = time.time() - start
            return ExecutionResult(
                success=False,
                output={
                    "success": False,
                    "operation": operation,
                    "terminal_lines": [f"{PREFIX} error: {exc}"],
                },
                error=str(exc),
                artifacts=[],
                opsec_context=None,
                execution_time=elapsed,
            )

    async def validate_input(self, parameters: Dict[str, Any]) -> bool:
        op = parameters.get("operation", "test_url")
        if op not in ("test_url", "crawl_and_test"):
            raise ValueError(f"Invalid operation: {op}")
        return True

    async def health_check(self) -> Dict[str, Any]:
        if self._mock:
            return {"healthy": True, "mode": "mock", "binary": self.binary}
        try:
            out = await run_cli([self.binary, "--version"], timeout=20)
            return {"healthy": "sqlmap" in out.lower(), "binary": self.binary}
        except Exception as exc:
            return {"healthy": False, "error": str(exc), "binary": self.binary}

    async def cleanup(self) -> None:
        logger.info("sqlmap plugin cleanup complete")

    async def _test_url(self, params: Dict[str, Any], target: str) -> Dict[str, Any]:
        url = params.get("url") or _normalize_url(target)
        level = min(int(params.get("level", SAFE_DEFAULT_LEVEL)), 3)
        risk = min(int(params.get("risk", SAFE_DEFAULT_RISK)), 2)
        args = [
            self.binary,
            "-u",
            url,
            "--batch",
            f"--level={level}",
            f"--risk={risk}",
            "--random-agent",
            "--flush-session",
        ]
        method = str(params.get("method", "GET")).upper()
        if method == "POST" and params.get("data"):
            args.extend(["--data", str(params["data"])])

        cli_output = await self._run_sqlmap(args, url=url)
        vulns = _parse_vuln_summary(cli_output)
        lines = [f"{PREFIX} test_url {url} level={level} risk={risk}"]
        lines.extend(clip_output_lines(cli_output, prefix=f"{PREFIX} ", max_lines=8))

        return {
            "success": True,
            "operation": "test_url",
            "cli_output": cli_output[:8000],
            "terminal_lines": lines,
            "structured": {"url": url, "vulnerabilities": vulns, "level": level, "risk": risk},
        }

    async def _crawl_and_test(self, params: Dict[str, Any], target: str) -> Dict[str, Any]:
        url = params.get("url") or _normalize_url(target)
        depth = min(int(params.get("crawl_depth", self.max_crawl_depth)), self.max_crawl_depth)
        level = min(int(params.get("level", SAFE_DEFAULT_LEVEL)), 2)
        risk = min(int(params.get("risk", SAFE_DEFAULT_RISK)), 1)
        args = [
            self.binary,
            "-u",
            url,
            "--batch",
            f"--level={level}",
            f"--risk={risk}",
            "--random-agent",
            f"--crawl={depth}",
            "--forms",
        ]

        cli_output = await self._run_sqlmap(args, url=url, crawl=True)
        lines = [f"{PREFIX} crawl_and_test {url} depth={depth}"]
        lines.extend(clip_output_lines(cli_output, prefix=f"{PREFIX} ", max_lines=10))

        return {
            "success": True,
            "operation": "crawl_and_test",
            "cli_output": cli_output[:8000],
            "terminal_lines": lines,
            "structured": {"url": url, "crawl_depth": depth},
        }

    async def _run_sqlmap(self, args: List[str], **mock_ctx) -> str:
        if self._mock:
            return _mock_sqlmap_output(**mock_ctx)
        return await run_cli(
            args,
            timeout=self.timeout,
            mock_env_key="SQLMAP_MOCK",
            mock_output=_mock_sqlmap_output(**mock_ctx),
        )

    def _opsec(
        self, operation: str, target: str, output: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if not self.config.opsec or not self.config.opsec.get("enabled"):
            return None
        return {
            "integration": "sqlmap",
            "operation": operation,
            "risk_level": self.config.opsec.get("risk_level", "high"),
            "noise_level": self.config.opsec.get("noise_level", "medium"),
            "target": target,
            "blocked": bool(output.get("blocked_reason")),
        }


def _normalize_url(target: str) -> str:
    t = str(target or "").strip()
    if not re.match(r"^https?://", t, re.I):
        t = f"http://{t}"
    return t.split()[0]


def _parse_vuln_summary(text: str) -> List[str]:
    vulns = []
    for line in text.splitlines():
        low = line.lower()
        if "is vulnerable" in low or "parameter:" in low:
            vulns.append(line.strip()[:200])
    return vulns[:20]


def _mock_sqlmap_output(url: str = "", crawl: bool = False) -> str:
    mode = "crawl" if crawl else "test"
    return (
        f"[INFO] sqlmap mock {mode} against {url}\n"
        "[INFO] testing connection to the target URL\n"
        "[INFO] GET parameter 'id' appears to be injectable (mock)\n"
    )
