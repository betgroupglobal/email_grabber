"""
ffuf integration — directory, parameter, and vhost fuzzing.
"""

import json
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
PREFIX = "[ffuf]"


class FfufPlugin(BasePlugin):
    """ffuf web fuzzer plugin."""

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        local = (config.execution or {}).get("local") or {}
        self.binary = env_path("FFUF_PATH", local.get("binary", "ffuf"))
        self.default_wordlist = env_path(
            "FFUF_WORDLIST_PATH",
            local.get("default_wordlist", "/usr/share/wordlists/dirb/common.txt"),
        )
        self.timeout = int(local.get("timeout", 180))
        self._mock = os.environ.get("FFUF_MOCK", "").lower() in ("1", "true", "yes")

    async def initialize(self) -> None:
        if self._mock:
            self._initialized = True
            self.status = self.status.READY
            return
        try:
            out = await run_cli([self.binary, "-V"], timeout=20)
            if "ffuf" not in out.lower():
                raise RuntimeError("ffuf -V unexpected output")
            self._initialized = True
            self.status = self.status.READY
        except Exception as exc:
            logger.warning("ffuf init degraded: %s", exc)
            self._initialized = True
            self.status = self.status.READY

    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        start = time.time()
        params = dict(context.parameters or {})
        operation = str(params.get("operation", "fuzz_url")).lower()
        target = params.get("target") or context.target or "unknown"

        try:
            if operation == "fuzz_vhost":
                output = await self._fuzz_vhost(params, target)
            elif operation == "fuzz_url":
                output = await self._fuzz_url(params, target)
            else:
                raise ValueError(f"Unknown operation: {operation}")

            elapsed = time.time() - start
            return ExecutionResult(
                success=output.get("success", True),
                output=output,
                error=output.get("error"),
                artifacts=[{"type": "ffuf_output", "value": output}],
                opsec_context=self._opsec(operation, target),
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
        op = parameters.get("operation", "fuzz_url")
        if op not in ("fuzz_url", "fuzz_vhost"):
            raise ValueError(f"Invalid operation: {op}")
        return True

    async def health_check(self) -> Dict[str, Any]:
        if self._mock:
            return {"healthy": True, "mode": "mock", "binary": self.binary}
        try:
            out = await run_cli([self.binary, "-V"], timeout=15)
            return {"healthy": "ffuf" in out.lower(), "binary": self.binary}
        except Exception as exc:
            return {"healthy": False, "error": str(exc), "binary": self.binary}

    async def cleanup(self) -> None:
        logger.info("ffuf plugin cleanup complete")

    async def _fuzz_url(self, params: Dict[str, Any], target: str) -> Dict[str, Any]:
        wordlist = params.get("wordlist") or self.default_wordlist
        url = params.get("url") or _fuzz_url_from_target(target)
        extensions = params.get("extensions")
        args = [
            self.binary,
            "-u",
            url,
            "-w",
            wordlist,
            "-of",
            "json",
            "-noninteractive",
            "-t",
            "20",
        ]
        if extensions:
            args.extend(["-e", str(extensions).replace(" ", "")])

        cli_output = await self._run_ffuf(args, mock_kind="url", url=url)
        results = _parse_ffuf_json(cli_output)
        lines = [f"{PREFIX} fuzz_url {url}"]
        lines.extend([f"{PREFIX}   {r.get('status')} {r.get('url')}" for r in results[:12]])

        return {
            "success": True,
            "operation": "fuzz_url",
            "cli_output": cli_output[:8000],
            "terminal_lines": lines,
            "structured": {"url": url, "wordlist": wordlist, "results": results},
        }

    async def _fuzz_vhost(self, params: Dict[str, Any], target: str) -> Dict[str, Any]:
        wordlist = params.get("wordlist") or self.default_wordlist
        host = _host_from_target(target)
        domain = params.get("vhost_domain") or host
        base_url = f"http://{host}/"
        args = [
            self.binary,
            "-u",
            base_url,
            "-H",
            f"Host: FUZZ.{domain}",
            "-w",
            wordlist,
            "-of",
            "json",
            "-noninteractive",
            "-t",
            "15",
        ]

        cli_output = await self._run_ffuf(args, mock_kind="vhost", host=host)
        results = _parse_ffuf_json(cli_output)
        lines = [f"{PREFIX} fuzz_vhost {host} domain={domain}"]
        lines.extend([f"{PREFIX}   {r.get('input')} -> {r.get('status')}" for r in results[:12]])

        return {
            "success": True,
            "operation": "fuzz_vhost",
            "cli_output": cli_output[:8000],
            "terminal_lines": lines,
            "structured": {"host": host, "domain": domain, "results": results},
        }

    async def _run_ffuf(self, args: List[str], *, mock_kind: str, **mock_ctx) -> str:
        if self._mock:
            return _mock_ffuf_json(mock_kind, **mock_ctx)
        return await run_cli(
            args,
            timeout=self.timeout,
            mock_env_key="FFUF_MOCK",
            mock_output=_mock_ffuf_json(mock_kind, **mock_ctx),
        )

    def _opsec(self, operation: str, target: str) -> Optional[Dict[str, Any]]:
        if not self.config.opsec or not self.config.opsec.get("enabled"):
            return None
        return {
            "integration": "ffuf",
            "operation": operation,
            "risk_level": self.config.opsec.get("risk_level", "medium"),
            "noise_level": self.config.opsec.get("noise_level", "high"),
            "target": target,
        }


def _host_from_target(target: str) -> str:
    t = str(target or "").strip()
    t = re.sub(r"^https?://", "", t, flags=re.I)
    return t.split("/")[0].split(":")[0] or "127.0.0.1"


def _fuzz_url_from_target(target: str) -> str:
    t = str(target or "").strip()
    if "FUZZ" in t:
        return t
    if not re.match(r"^https?://", t, re.I):
        t = f"https://{t}"
    base = t.rstrip("/")
    return f"{base}/FUZZ"


def _parse_ffuf_json(text: str) -> List[Dict[str, Any]]:
    try:
        data = json.loads(text)
        return data.get("results") or []
    except json.JSONDecodeError:
        return []


def _mock_ffuf_json(kind: str, **ctx) -> str:
    if kind == "vhost":
        results = [{"input": "admin", "status": 200, "url": ctx.get("host", "")}]
    else:
        results = [
            {"url": f"{ctx.get('url', '')}".replace("FUZZ", "admin"), "status": 200, "input": "admin"},
            {"url": f"{ctx.get('url', '')}".replace("FUZZ", "api"), "status": 301, "input": "api"},
        ]
    return json.dumps({"results": results})
