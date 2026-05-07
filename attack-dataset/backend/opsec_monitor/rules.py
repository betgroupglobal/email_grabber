"""
OpSec rule definitions.

Each rule checks an aspect of operational security and returns
a list of findings with severity and remediation guidance.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable


@dataclass
class Finding:
    rule_id: str
    severity: str          # critical | high | medium | low | info
    title: str
    description: str
    remediation: str
    evidence: str = ""


RuleFunc = Callable[[Dict[str, Any]], List[Finding]]

# ── Rule registry ─────────────────────────────────────────────────────────────

RULES: List[RuleFunc] = []


def rule(fn: RuleFunc) -> RuleFunc:
    RULES.append(fn)
    return fn


# ── Rules ─────────────────────────────────────────────────────────────────────

@rule
def check_noisy_tools(ctx: Dict[str, Any]) -> List[Finding]:
    """Flag known noisy / detectable tools in a proposed attack."""
    noisy = {
        "nmap": "Nmap default scans generate high network noise and trigger IDS/IPS.",
        "metasploit": "Metasploit default payloads are heavily signatured by AV/EDR.",
        "sqlmap": "SQLMap's default user-agent and error payloads are widely fingerprinted.",
        "nikto": "Nikto generates very high request volume and has a distinct UA header.",
        "havij": "Havij is commercially signatured and detected by most WAFs.",
        "cobalt strike": "Default Cobalt Strike profiles are signatured by major EDRs.",
        "empire": "PowerShell Empire default stagers are heavily flagged.",
    }
    findings = []
    tools_raw: str = ctx.get("tools_used", "").lower()
    for tool, reason in noisy.items():
        if tool in tools_raw:
            findings.append(Finding(
                rule_id="OPSEC-001",
                severity="high",
                title=f"Noisy tool detected: {tool}",
                description=reason,
                remediation=(
                    f"Replace {tool} with a quieter alternative or customise its "
                    "fingerprint (user-agent, timing, payload encoding)."
                ),
                evidence=f"tools_used field contains: {tool}",
            ))
    return findings


@rule
def check_plaintext_exfil(ctx: Dict[str, Any]) -> List[Finding]:
    """Detect unencrypted data exfiltration techniques."""
    keywords = ["http exfil", "ftp exfil", "plaintext", "unencrypted transfer"]
    steps: str = ctx.get("attack_steps", "").lower()
    findings = []
    for kw in keywords:
        if kw in steps:
            findings.append(Finding(
                rule_id="OPSEC-002",
                severity="critical",
                title="Plaintext exfiltration channel",
                description="Data is being exfiltrated over an unencrypted channel.",
                remediation=(
                    "Use DNS tunnelling, HTTPS C2, or steganography to exfiltrate "
                    "data covertly. Encrypt all data before egress."
                ),
                evidence=f"Keyword '{kw}' found in attack steps.",
            ))
    return findings


@rule
def check_persistence_visibility(ctx: Dict[str, Any]) -> List[Finding]:
    """Detect high-visibility persistence mechanisms."""
    high_vis = {
        "startup folder": "Startup folder persistence is trivially detected by AV/EDR.",
        "cron job": "New cron jobs are logged and alerting tools monitor them.",
        "registry run": "Registry Run keys are a common persistence indicator scanned by EDR.",
        "scheduled task": "Scheduled tasks are enumerated by most endpoint monitoring tools.",
    }
    steps = ctx.get("attack_steps", "").lower() + " " + ctx.get("attack_type", "").lower()
    findings = []
    for mech, reason in high_vis.items():
        if mech in steps:
            findings.append(Finding(
                rule_id="OPSEC-003",
                severity="medium",
                title=f"High-visibility persistence: {mech}",
                description=reason,
                remediation=(
                    "Prefer lower-visibility mechanisms such as COM hijacking, "
                    "DLL side-loading, or WMI subscriptions with obfuscated payloads."
                ),
                evidence=f"Persistence mechanism '{mech}' identified.",
            ))
    return findings


@rule
def check_log_clearing(ctx: Dict[str, Any]) -> List[Finding]:
    """Ensure attack plan includes log clearing."""
    steps = ctx.get("attack_steps", "").lower()
    has_log_clear = any(kw in steps for kw in [
        "clear log", "wevtutil", "delete log", "flush log", "cover tracks",
    ])
    if not has_log_clear:
        return [Finding(
            rule_id="OPSEC-004",
            severity="medium",
            title="No log-clearing step detected",
            description="The attack plan does not include clearing forensic artefacts.",
            remediation=(
                "Add a post-exploitation log clearing step: wevtutil (Windows), "
                "bash history wipe, /var/log clearing (Linux), or cloud trail disabling."
            ),
        )]
    return []


@rule
def check_timing_awareness(ctx: Dict[str, Any]) -> List[Finding]:
    """Recommend timing strategies for stealth."""
    steps = ctx.get("attack_steps", "").lower()
    if "sleep" not in steps and "delay" not in steps and "timing" not in steps:
        return [Finding(
            rule_id="OPSEC-005",
            severity="low",
            title="No timing/delay strategy present",
            description=(
                "Automated attacks without random delays are easily detected by "
                "rate-based anomaly detection and behavioural analytics."
            ),
            remediation=(
                "Introduce randomised sleep intervals between requests "
                "(e.g. random.uniform(0.5, 3.0) seconds) and operate during "
                "legitimate business hours to blend with normal traffic."
            ),
        )]
    return []


@rule
def check_credential_exposure(ctx: Dict[str, Any]) -> List[Finding]:
    """Warn if credentials might be left in logs or temp files."""
    steps = ctx.get("attack_steps", "").lower()
    findings = []
    if any(kw in steps for kw in ["hardcoded password", "password in url", "plaintext cred"]):
        findings.append(Finding(
            rule_id="OPSEC-006",
            severity="high",
            title="Credential exposure risk",
            description="Credentials may appear in logs, URLs, or temp files.",
            remediation=(
                "Pass credentials via environment variables or encrypted vaults. "
                "Rotate any used credentials immediately post-engagement."
            ),
        ))
    return findings


@rule
def check_attribution_artefacts(ctx: Dict[str, Any]) -> List[Finding]:
    """Check for common attribution artefacts."""
    findings = []
    tools = ctx.get("tools_used", "").lower()
    steps = ctx.get("attack_steps", "").lower()
    text = tools + " " + steps

    if "burp suite" in text and "default" in text:
        findings.append(Finding(
            rule_id="OPSEC-007",
            severity="medium",
            title="Default Burp Suite fingerprint",
            description="Default Burp Suite headers are widely fingerprinted.",
            remediation="Customise Burp's User-Agent and match target site traffic patterns.",
        ))

    if any(kw in steps for kw in ["github.com", "raw.githubusercontent"]):
        findings.append(Finding(
            rule_id="OPSEC-007b",
            severity="high",
            title="Public GitHub payload hosting",
            description="Fetching payloads from public GitHub creates attribution trail.",
            remediation="Host payloads on disposable infrastructure with no operator links.",
        ))

    return findings
