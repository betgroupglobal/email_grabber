"""
Metasploit Framework integration plugin.

Supports msfconsole resource scripts and optional RPC. Live execution by default;
risk guardrails removed for authorized red-team use.
"""

import asyncio
import json
import logging
import os
import re
import tempfile
import time
from typing import Any, Dict, List, Optional

import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from plugin_system.base import (
    BasePlugin,
    PluginConfig,
    ExecutionContext,
    ExecutionResult,
)

logger = logging.getLogger(__name__)

# Auxiliary modules safe for external web-only recon (non-destructive scanners)
WEB_SAFE_AUXILIARY_PREFIXES = (
    "auxiliary/scanner/http/",
    "auxiliary/scanner/ssl/",
    "auxiliary/scanner/https/",
    "auxiliary/scanner/wmap/",
    "auxiliary/gather/",
    "auxiliary/scanner/smb/smb_version",
)

POST_EXPLOIT_PREFIXES = (
    "exploit/",
    "post/",
    "payload/",
)


def _live_require_approval() -> bool:
    val = os.environ.get("LIVE_REQUIRE_APPROVAL", "")
    return val.lower() in ("1", "true", "yes")


def _allow_high_risk() -> bool:
    val = os.environ.get("ALLOW_HIGH_RISK", "true")
    return val.lower() not in ("0", "false", "no")


def _env_path(key: str, fallback: str) -> str:
    return os.environ.get(key) or fallback


class MetasploitPlugin(BasePlugin):
    """Metasploit Framework plugin (CLI + optional RPC)."""

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        local = (config.execution or {}).get("local") or {}
        remote = (config.execution or {}).get("remote") or {}
        self.msf_path = _env_path("MSF_PATH", local.get("binary", "msfconsole"))
        self.msfvenom_path = _env_path(
            "MSFVENOM_PATH", local.get("msfvenom_binary", "msfvenom")
        )
        self.timeout = int(local.get("timeout", 300))
        self.default_dry_run = bool(local.get("default_dry_run", False))
        self.rpc_host = _env_path("MSF_RPC_HOST", remote.get("rpc_host", "127.0.0.1"))
        self.rpc_port = int(_env_path("MSF_RPC_PORT", str(remote.get("rpc_port", 55553))))
        self.rpc_token = _env_path("MSF_RPC_TOKEN", remote.get("rpc_token", ""))
        self._mock_mode = os.environ.get("MSF_MOCK", "").lower() in ("1", "true", "yes")

    async def initialize(self) -> None:
        if self._mock_mode:
            self._initialized = True
            self.status = self.status.READY
            logger.info("Metasploit plugin initialized (MSF_MOCK mode)")
            return

        try:
            version_out = await self._run_cli([self.msf_path, "--version"], timeout=30)
            if "Framework" not in version_out and "Metasploit" not in version_out:
                raise RuntimeError("msfconsole --version did not return Framework banner")
            self._initialized = True
            self.status = self.status.READY
            logger.info("Metasploit plugin initialized: %s", self.msf_path)
        except Exception as exc:
            logger.warning("Metasploit plugin init degraded: %s", exc)
            self._initialized = True
            self.status = self.status.READY

    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        start = time.time()
        params = dict(context.parameters or {})
        metadata = context.metadata or {}
        operation = str(params.get("operation", "list_modules")).lower()
        target = params.get("target") or context.target or "unknown"

        if "roe_acknowledged" in params:
            roe_acknowledged = bool(params["roe_acknowledged"])
        else:
            roe_acknowledged = bool(metadata.get("roe_acknowledged"))

        if "web_only" in params:
            web_only = bool(params["web_only"])
        else:
            web_only = bool(metadata.get("web_only", True))

        if "council_approved" in params:
            council_approved = bool(params["council_approved"])
        else:
            council_approved = bool(metadata.get("council_approved"))
        dry_run = params.get("dry_run")
        if dry_run is None:
            dry_run = self.default_dry_run

        try:
            if operation == "list_modules":
                output = await self._list_modules(params, target)
            elif operation == "run_auxiliary":
                output = await self._run_auxiliary(
                    params, target, web_only=web_only, dry_run=dry_run
                )
            elif operation == "run_exploit":
                output = await self._run_exploit(
                    params, target, dry_run=bool(dry_run)
                )
            elif operation == "generate_payload":
                output = await self._generate_payload(
                    params, target, dry_run=bool(dry_run)
                )
            else:
                raise ValueError(f"Unknown operation: {operation}")

            elapsed = time.time() - start
            success = output.get("success", True) and not output.get("blocked_reason")
            opsec = self._build_opsec_context(operation, output, target)

            return ExecutionResult(
                success=success,
                output=output,
                error=output.get("blocked_reason"),
                artifacts=[
                    {
                        "type": "msf_output",
                        "value": output,
                        "description": f"Metasploit {operation} result",
                    }
                ],
                opsec_context=opsec,
                execution_time=elapsed,
            )
        except Exception as exc:
            elapsed = time.time() - start
            logger.error("Metasploit execution failed: %s", exc)
            return ExecutionResult(
                success=False,
                output={
                    "success": False,
                    "operation": operation,
                    "terminal_lines": [f"[msf] error: {exc}"],
                },
                error=str(exc),
                artifacts=[],
                opsec_context=None,
                execution_time=elapsed,
            )

    async def validate_input(self, parameters: Dict[str, Any]) -> bool:
        op = parameters.get("operation", "list_modules")
        if op not in (
            "list_modules",
            "run_auxiliary",
            "run_exploit",
            "generate_payload",
        ):
            raise ValueError(f"Invalid operation: {op}")
        if op in ("run_auxiliary", "run_exploit") and not parameters.get("module"):
            raise ValueError("module is required for run_auxiliary and run_exploit")
        if op == "generate_payload" and not parameters.get("payload"):
            raise ValueError("payload is required for generate_payload")
        return True

    async def health_check(self) -> Dict[str, Any]:
        if self._mock_mode:
            return {"healthy": True, "mode": "mock", "binary": self.msf_path}
        try:
            out = await self._run_cli([self.msf_path, "--version"], timeout=20)
            healthy = "Framework" in out or "Metasploit" in out
            return {
                "healthy": healthy,
                "binary": self.msf_path,
                "msfvenom": self.msfvenom_path,
                "rpc_configured": bool(self.rpc_token),
                "version": self._extract_version(out),
            }
        except Exception as exc:
            return {"healthy": False, "error": str(exc), "binary": self.msf_path}

    async def cleanup(self) -> None:
        logger.info("Metasploit plugin cleanup complete")

    async def _list_modules(
        self, params: Dict[str, Any], target: str
    ) -> Dict[str, Any]:
        search = params.get("search") or params.get("module_type") or ""
        module_type = params.get("module_type", "auxiliary")

        if self._mock_mode:
            modules = [
                "auxiliary/scanner/http/http_version",
                "auxiliary/scanner/http/crawler",
                "auxiliary/scanner/ssl/ssl_version",
            ]
            cli_output = "\n".join(modules)
        elif self.rpc_token:
            cli_output = await self._rpc_search(search or module_type)
            modules = _parse_module_list(cli_output)
        else:
            script = f"search {module_type} {search}\n".strip() + "\nexit -y\n"
            cli_output = await self._run_msf_resource(script)
            modules = _parse_module_list(cli_output)

        lines = [f"[msf] list_modules ({module_type}) target={target}"]
        lines.extend([f"[msf]   {m}" for m in modules[:40]])
        if len(modules) > 40:
            lines.append(f"[msf]   … and {len(modules) - 40} more")

        return {
            "success": True,
            "operation": "list_modules",
            "dry_run": False,
            "cli_output": cli_output[:8000],
            "terminal_lines": lines,
            "structured": {
                "target": target,
                "module_type": module_type,
                "search": search,
                "modules": modules,
                "count": len(modules),
            },
        }

    async def _run_auxiliary(
        self,
        params: Dict[str, Any],
        target: str,
        *,
        web_only: bool,
        dry_run: bool,
    ) -> Dict[str, Any]:
        module = str(params.get("module", ""))
        options = dict(params.get("options") or {})
        if "RHOSTS" not in options and target not in ("unknown", ""):
            options["RHOSTS"] = _host_from_target(target)

        script = _build_module_script(module, options, run=not dry_run)
        if self._mock_mode:
            cli_output = f"[*] Mock auxiliary {module} RHOSTS={options.get('RHOSTS')}\n[*] Done."
        else:
            cli_output = (
                f"[dry-run] Would execute:\n{script}"
                if dry_run
                else await self._run_msf_resource(script)
            )

        lines = [
            f"[msf] run_auxiliary {module} dry_run={dry_run}",
            f"[msf] RHOSTS={options.get('RHOSTS', '?')}",
        ]
        lines.extend(_clip_output_lines(cli_output, prefix="[msf] "))

        return {
            "success": True,
            "operation": "run_auxiliary",
            "dry_run": dry_run,
            "cli_output": cli_output[:8000],
            "terminal_lines": lines,
            "structured": {
                "module": module,
                "options": options,
                "target": target,
            },
        }

    async def _run_exploit(
        self, params: Dict[str, Any], target: str, *, dry_run: bool
    ) -> Dict[str, Any]:
        module = str(params.get("module", ""))
        options = dict(params.get("options") or {})
        if "RHOSTS" not in options:
            options["RHOSTS"] = _host_from_target(target)

        script = _build_module_script(module, options, run=not dry_run)
        if self._mock_mode:
            cli_output = f"[*] Mock exploit {module} (dry_run={dry_run})\n[*] Completed."
        elif dry_run:
            cli_output = f"[dry-run] Resource script:\n{script}"
        else:
            cli_output = await self._run_msf_resource(script)

        lines = [
            f"[msf] run_exploit {module} dry_run={dry_run}",
            f"[msf] target={options.get('RHOSTS')}",
        ]
        lines.extend(_clip_output_lines(cli_output, prefix="[msf] "))

        return {
            "success": True,
            "operation": "run_exploit",
            "dry_run": dry_run,
            "cli_output": cli_output[:8000],
            "terminal_lines": lines,
            "structured": {"module": module, "options": options},
        }

    async def _generate_payload(
        self, params: Dict[str, Any], target: str, *, dry_run: bool
    ) -> Dict[str, Any]:
        payload = str(params.get("payload", "linux/x64/shell_reverse_tcp"))
        fmt = params.get("format", "raw")
        lhost = params.get("lhost") or _host_from_target(target)
        lport = int(params.get("lport") or 4444)
        encoder = params.get("encoder")

        args = [
            self.msfvenom_path,
            "-p",
            payload,
            f"LHOST={lhost}",
            f"LPORT={lport}",
            "-f",
            fmt,
        ]
        if encoder:
            args.extend(["-e", encoder])

        if self._mock_mode or dry_run:
            cli_output = f"[dry-run] msfvenom {' '.join(args)}"
        else:
            cli_output = await self._run_cli(args, timeout=self.timeout)

        lines = [
            f"[msf] generate_payload {payload} dry_run={dry_run}",
            f"[msf] LHOST={lhost} LPORT={lport}",
        ]
        if not dry_run:
            lines.append("[msf] payload generated (output truncated in logs)")

        return {
            "success": True,
            "operation": "generate_payload",
            "dry_run": dry_run,
            "cli_output": cli_output[:2000],
            "terminal_lines": lines,
            "structured": {
                "payload": payload,
                "format": fmt,
                "lhost": lhost,
                "lport": lport,
            },
        }

    async def _run_msf_resource(self, script: str) -> str:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".rc", delete=False
        ) as tmp:
            tmp.write(script)
            rc_path = tmp.name
        try:
            return await self._run_cli(
                [self.msf_path, "-q", "-r", rc_path],
                timeout=self.timeout,
            )
        finally:
            try:
                os.unlink(rc_path)
            except OSError:
                pass

    async def _run_cli(self, args: List[str], timeout: int = 120) -> str:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError(f"Command timed out after {timeout}s: {args[0]}")

        out = stdout.decode("utf-8", errors="ignore")
        err = stderr.decode("utf-8", errors="ignore")
        if proc.returncode != 0 and not out.strip():
            raise RuntimeError(err.strip() or f"Exit {proc.returncode}")
        return out + ("\n" + err if err.strip() else "")

    async def _rpc_search(self, query: str) -> str:
        """Minimal Metasploit RPC module.search when token is configured."""
        try:
            import urllib.request

            url = f"http://{self.rpc_host}:{self.rpc_port}/api/"
            body = json.dumps(
                [
                    "module.search",
                    self.rpc_token,
                    query,
                ]
            ).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            loop = asyncio.get_event_loop()
            raw = await loop.run_in_executor(
                None, lambda: urllib.request.urlopen(req, timeout=30).read()
            )
            data = json.loads(raw.decode("utf-8"))
            if isinstance(data, list):
                return "\n".join(str(x) for x in data)
            return json.dumps(data)
        except Exception as exc:
            logger.warning("MSF RPC search failed, falling back to CLI: %s", exc)
            script = f"search {query}\nexit -y\n"
            return await self._run_msf_resource(script)

    def _build_opsec_context(
        self, operation: str, output: Dict[str, Any], target: str
    ) -> Dict[str, Any]:
        if not self.config.opsec or not self.config.opsec.get("enabled"):
            return None
        return {
            "integration": "metasploit",
            "operation": operation,
            "risk_level": self.config.opsec.get("risk_level", "high"),
            "noise_level": self.config.opsec.get("noise_level", "high"),
            "dry_run": output.get("dry_run", True),
            "blocked": bool(output.get("blocked_reason")),
            "target": target,
            "detection_methods": self.config.opsec.get("detection_methods", []),
            "evasion_recommendations": self.config.opsec.get(
                "evasion_recommendations", []
            ),
        }

    @staticmethod
    def _extract_version(text: str) -> str:
        match = re.search(r"Framework\s+([\d.]+)", text)
        return match.group(1) if match else "unknown"


def _host_from_target(target: str) -> str:
    t = str(target or "").strip()
    t = re.sub(r"^https?://", "", t, flags=re.I)
    t = t.split("/")[0].split(":")[0]
    return t or "127.0.0.1"


def _is_web_safe_auxiliary(module: str) -> bool:
    m = str(module or "")
    if not m.startswith("auxiliary/"):
        return False
    return any(m.startswith(prefix) for prefix in WEB_SAFE_AUXILIARY_PREFIXES)


def _is_post_exploit_module(module: str) -> bool:
    m = str(module or "")
    return any(m.startswith(prefix) for prefix in POST_EXPLOIT_PREFIXES)


def _build_module_script(
    module: str, options: Dict[str, Any], *, run: bool
) -> str:
    lines = [f"use {module}"]
    for key, val in options.items():
        lines.append(f"set {key} {val}")
    if run:
        lines.append("run")
    else:
        lines.append("# dry-run — run skipped")
    lines.append("exit -y")
    return "\n".join(lines) + "\n"


def _parse_module_list(text: str) -> List[str]:
    modules = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "[", "=")):
            continue
        match = re.search(
            r"(auxiliary|exploit|post|payload)/[\w./-]+", line
        )
        if match:
            modules.append(match.group(0))
    return list(dict.fromkeys(modules))


def _clip_output_lines(text: str, prefix: str = "", max_lines: int = 12) -> List[str]:
    lines = []
    for line in text.splitlines()[:max_lines]:
        s = line.strip()
        if s:
            lines.append(f"{prefix}{s[:200]}")
    return lines
