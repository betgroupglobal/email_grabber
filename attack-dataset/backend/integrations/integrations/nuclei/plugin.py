"""
Nuclei integration — template-based web vulnerability scanning.
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
PREFIX = "[nuclei]"


class NucleiPlugin(BasePlugin):
    """ProjectDiscovery Nuclei scanner plugin."""

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        local = (config.execution or {}).get("local") or {}
        self.binary = env_path("NUCLEI_PATH", local.get("binary", "nuclei"))
        self.timeout = int(local.get("timeout", 300))
        self._mock = os.environ.get("NUCLEI_MOCK", "").lower() in ("1", "true", "yes")

    async def initialize(self) -> None:
        if self._mock:
            self._initialized = True
            self.status = self.status.READY
            logger.info("Nuclei plugin initialized (NUCLEI_MOCK)")
            return
        try:
            out = await run_cli([self.binary, "-version"], timeout=30)
            if "Nuclei" not in out and "nuclei" not in out.lower():
                raise RuntimeError("nuclei -version did not return expected banner")
            self._initialized = True
            self.status = self.status.READY
        except Exception as exc:
            logger.warning("Nuclei init degraded: %s", exc)
            self._initialized = True
            self.status = self.status.READY

    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        start = time.time()
        params = dict(context.parameters or {})
        operation = str(params.get("operation", "scan_target")).lower()
        target = params.get("target") or context.target or "unknown"

        try:
            if operation == "list_templates":
                output = await self._list_templates(params, target)
            elif operation == "scan_target":
                output = await self._scan_target(params, target)
            else:
                raise ValueError(f"Unknown operation: {operation}")

            elapsed = time.time() - start
            return ExecutionResult(
                success=output.get("success", True),
                output=output,
                error=output.get("error"),
                artifacts=[{"type": "nuclei_output", "value": output}],
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
        op = parameters.get("operation", "scan_target")
        if op not in ("scan_target", "list_templates"):
            raise ValueError(f"Invalid operation: {op}")
        if op == "scan_target" and not parameters.get("target"):
            raise ValueError("target is required for scan_target")
        return True

    async def health_check(self) -> Dict[str, Any]:
        if self._mock:
            return {"healthy": True, "mode": "mock", "binary": self.binary}
        try:
            out = await run_cli([self.binary, "-version"], timeout=20)
            return {"healthy": "Nuclei" in out or "nuclei" in out.lower(), "binary": self.binary}
        except Exception as exc:
            return {"healthy": False, "error": str(exc), "binary": self.binary}

    async def cleanup(self) -> None:
        logger.info("Nuclei plugin cleanup complete")

    async def _scan_target(self, params: Dict[str, Any], target: str) -> Dict[str, Any]:
        url = _normalize_url(target)
        severity = params.get("severity") or "medium,high,critical"
        templates = params.get("templates")
        tags = params.get("tags")

        args = [self.binary, "-u", url, "-jsonl", "-silent", "-severity", severity]
        if templates:
            args.extend(["-t", str(templates)])
        if tags:
            args.extend(["-tags", str(tags)])

        if self._mock:
            cli_output = json.dumps(
                {
                    "template-id": "mock-cve-check",
                    "info": {"severity": "medium", "name": "Mock finding"},
                    "host": url,
                }
            )
        else:
            cli_output = await run_cli(
                args,
                timeout=self.timeout,
                mock_env_key="NUCLEI_MOCK",
                mock_output=cli_output_mock_scan(url),
            )

        findings = _parse_jsonl(cli_output)
        lines = [f"{PREFIX} scan_target {url} severity={severity}"]
        lines.extend(
            [
                f"{PREFIX}   [{f.get('severity', '?')}] {f.get('name', f.get('template-id', '?'))}"
                for f in findings[:15]
            ]
        )
        if len(findings) > 15:
            lines.append(f"{PREFIX}   … and {len(findings) - 15} more")

        return {
            "success": True,
            "operation": "scan_target",
            "cli_output": cli_output[:8000],
            "terminal_lines": lines,
            "structured": {
                "target": url,
                "severity_filter": severity,
                "findings": findings,
                "finding_count": len(findings),
            },
        }

    async def _list_templates(self, params: Dict[str, Any], target: str) -> Dict[str, Any]:
        tags = params.get("tags") or params.get("search") or ""
        args = [self.binary, "-tl", "-silent"]
        if tags:
            args.extend(["-tags", str(tags)])

        if self._mock:
            cli_output = "http/cves/mock-template.yaml\nhttp/technologies/mock-tech.yaml\n"
        else:
            cli_output = await run_cli(
                args,
                timeout=min(self.timeout, 120),
                mock_env_key="NUCLEI_MOCK",
                mock_output="http/cves/mock-template.yaml\n",
            )

        templates = [ln.strip() for ln in cli_output.splitlines() if ln.strip()][:200]
        lines = [f"{PREFIX} list_templates (target context: {target})"]
        lines.extend([f"{PREFIX}   {t}" for t in templates[:20]])
        if len(templates) > 20:
            lines.append(f"{PREFIX}   … {len(templates)} templates total")

        return {
            "success": True,
            "operation": "list_templates",
            "cli_output": cli_output[:8000],
            "terminal_lines": lines,
            "structured": {"templates": templates, "count": len(templates)},
        }

    def _opsec(self, operation: str, target: str) -> Optional[Dict[str, Any]]:
        if not self.config.opsec or not self.config.opsec.get("enabled"):
            return None
        return {
            "integration": "nuclei",
            "operation": operation,
            "risk_level": self.config.opsec.get("risk_level", "medium"),
            "noise_level": self.config.opsec.get("noise_level", "medium"),
            "target": target,
        }


def _normalize_url(target: str) -> str:
    t = str(target or "").strip()
    if not re.match(r"^https?://", t, re.I):
        t = f"https://{t}"
    return t.split()[0]


def _parse_jsonl(text: str) -> List[Dict[str, Any]]:
    findings = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("["):
            continue
        try:
            row = json.loads(line)
            info = row.get("info") or {}
            findings.append(
                {
                    "template-id": row.get("template-id") or row.get("templateID"),
                    "name": info.get("name") or row.get("template-id"),
                    "severity": info.get("severity") or row.get("severity"),
                    "host": row.get("host") or row.get("matched-at"),
                }
            )
        except json.JSONDecodeError:
            continue
    return findings


def cli_output_mock_scan(url: str) -> str:
    return json.dumps(
        {
            "template-id": "mock-http-check",
            "info": {"severity": "info", "name": "Mock nuclei scan"},
            "host": url,
        }
    ) + "\n"
