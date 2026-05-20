"""Shared async CLI runner for Integration Hub security-tool plugins."""

import asyncio
import os
from typing import List, Optional


async def run_cli(
    args: List[str],
    *,
    timeout: int = 120,
    mock_output: Optional[str] = None,
    mock_env_key: Optional[str] = None,
) -> str:
    """Run a CLI command with timeout; optional mock mode via env flag."""
    if mock_env_key and os.environ.get(mock_env_key, "").lower() in ("1", "true", "yes"):
        return mock_output or f"[mock] {' '.join(args[:4])}…\n[*] Done."

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"Command timed out after {timeout}s: {args[0]}")

    out = stdout.decode("utf-8", errors="ignore")
    err = stderr.decode("utf-8", errors="ignore")
    if proc.returncode != 0 and not out.strip():
        raise RuntimeError(err.strip() or f"Exit {proc.returncode}")
    return out + ("\n" + err if err.strip() else "")


def env_path(key: str, fallback: str) -> str:
    return os.environ.get(key) or fallback


def clip_output_lines(text: str, prefix: str = "", max_lines: int = 12) -> List[str]:
    lines = []
    for line in text.splitlines()[:max_lines]:
        s = line.strip()
        if s:
            lines.append(f"{prefix}{s[:200]}")
    return lines
