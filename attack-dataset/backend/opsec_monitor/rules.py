"""
OpSec rule definitions.

Each rule checks an aspect of operational security and returns
a list of findings with severity and remediation guidance.
"""
from __future__ import annotations
import re
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

# ── Rule registry ─────────────────────────────────────────────────────────────────────────────

RULES: List[RuleFunc] = []


def rule(fn: RuleFunc) -> RuleFunc:
    RULES.append(fn)
    return fn


def _match(text: str, *patterns: str) -> list[str]:
    """Case-insensitive whole-word regex match. Returns list of matched patterns."""
    matched = []
    for pat in patterns:
        # Escape for regex and add word boundaries where appropriate
        escaped = re.escape(pat)
        # For multi-word phrases, use simple case-insensitive search
        # For single words, use word boundaries
        if " " in pat:
            if re.search(escaped, text, re.IGNORECASE):
                matched.append(pat)
        else:
            if re.search(r"\b" + escaped + r"\b", text, re.IGNORECASE):
                matched.append(pat)
    return matched


# ── Rules ────────────────────────────────────────────────────────────────────────────────────

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
        "msfvenom": "Msfvenom-generated payloads are signatured by most AV solutions.",
        "hydra": "Hydra generates high authentication noise detectable via brute-force alerts.",
        "aircrack": "Aircrack-ng creates detectable wireless probe patterns.",
    }
    findings = []
    tools_raw: str = ctx.get("tools_used", "").lower()
    steps_raw: str = ctx.get("attack_steps", "").lower()
    combined = tools_raw + " " + steps_raw
    for tool, reason in noisy.items():
        hits = _match(combined, tool)
        if hits:
            findings.append(Finding(
                rule_id="OPSEC-001",
                severity="high",
                title=f"Noisy tool detected: {tool}",
                description=reason,
                remediation=(
                    f"Replace {tool} with a quieter alternative or customise its "
                    "fingerprint (user-agent, timing, payload encoding)."
                ),
                evidence=f"Matched '{tool}' in: {'tools_used' if tool in tools_raw else 'attack_steps'}",
            ))
    return findings


@rule
def check_plaintext_exfil(ctx: Dict[str, Any]) -> List[Finding]:
    """Detect unencrypted data exfiltration techniques."""
    patterns = [
        (r"\bhttp\b.{0,20}exfil", "HTTP exfiltration"),
        (r"\bftp\b.{0,20}exfil", "FTP exfiltration"),
        (r"\bplaintext\b", "plaintext data"),
        (r"\bunencrypted\s+transfer\b", "unencrypted transfer"),
        (r"\btelnet\b.{0,20}(exfil|transfer|send)", "Telnet-based transfer"),
        (r"\bsmtp\b.{0,20}(exfil|attach|send).{0,20}(data|file|dump)", "SMTP data exfil"),
    ]
    steps: str = ctx.get("attack_steps", "").lower()
    findings = []
    for pattern, label in patterns:
        m = re.search(pattern, steps, re.IGNORECASE)
        if m:
            findings.append(Finding(
                rule_id="OPSEC-002",
                severity="critical",
                title="Plaintext exfiltration channel",
                description=f"Data may be exfiltrated over an unencrypted channel ({label}).",
                remediation=(
                    "Use DNS tunnelling, HTTPS C2, or steganography to exfiltrate "
                    "data covertly. Encrypt all data before egress."
                ),
                evidence=f"Pattern '{label}' matched: …{m.group(0)}…",
            ))
            break  # one finding per attack step is enough
    return findings


@rule
def check_persistence_visibility(ctx: Dict[str, Any]) -> List[Finding]:
    """Detect high-visibility persistence mechanisms."""
    high_vis = {
        r"\bstartup\s+folder\b": ("startup folder", "Startup folder persistence is trivially detected by AV/EDR."),
        r"\bcron\s+job\b": ("cron job", "New cron jobs are logged and alerting tools monitor them."),
        r"\bregistry\s+run\b": ("registry run key", "Registry Run keys are a common persistence indicator scanned by EDR."),
        r"\bscheduled\s+task\b": ("scheduled task", "Scheduled tasks are enumerated by most endpoint monitoring tools."),
        r"\b\.bashrc\b|\b\.profile\b": ("shell profile modification", "Shell profile modifications are easily detected by file integrity monitoring."),
        r"\brc\.local\b": ("rc.local persistence", "rc.local modifications are flagged by Linux security tooling."),
    }
    steps = ctx.get("attack_steps", "").lower() + " " + ctx.get("attack_type", "").lower()
    findings = []
    for pattern, (label, reason) in high_vis.items():
        m = re.search(pattern, steps, re.IGNORECASE)
        if m:
            findings.append(Finding(
                rule_id="OPSEC-003",
                severity="medium",
                title=f"High-visibility persistence: {label}",
                description=reason,
                remediation=(
                    "Prefer lower-visibility mechanisms such as COM hijacking, "
                    "DLL side-loading, or WMI subscriptions with obfuscated payloads."
                ),
                evidence=f"Matched pattern for '{label}': …{m.group(0)}…",
            ))
    return findings


@rule
def check_log_clearing(ctx: Dict[str, Any]) -> List[Finding]:
    """Ensure attack plan includes log clearing."""
    steps = ctx.get("attack_steps", "").lower()
    clear_patterns = [
        r"\bclear\s+(log|logs|event\s+log)\b",
        r"\bwevtutil\b",
        r"\bdelete\s+log\b",
        r"\bflush\s+log\b",
        r"\bcover\s+track\b",
        r"\bshred\b.{0,30}\blog\b",
        r"\brm\s+.{0,20}/var/log\b",
        r"\bhistory\s*-c\b",
        r"\bunset\s+histfile\b",
        r"\bcloudtrail\b.{0,20}(disable|delete|stop)",
    ]
    has_log_clear = any(re.search(p, steps, re.IGNORECASE) for p in clear_patterns)
    if not has_log_clear:
        return [Finding(
            rule_id="OPSEC-004",
            severity="medium",
            title="No log-clearing step detected",
            description="The attack plan does not include clearing forensic artefacts.",
            remediation=(
                "Add a post-exploitation log clearing step: wevtutil (Windows), "
                "bash history wipe (history -c; unset HISTFILE), "
                "/var/log clearing (Linux), or CloudTrail disabling (cloud)."
            ),
        )]
    return []


@rule
def check_timing_awareness(ctx: Dict[str, Any]) -> List[Finding]:
    """Recommend timing strategies for stealth."""
    steps = ctx.get("attack_steps", "").lower()
    timing_patterns = [
        r"\bsleep\b", r"\bdelay\b", r"\btiming\b", r"\bjitter\b",
        r"\brandom\s+(wait|interval|delay)\b", r"\bthrottle\b",
        r"\blow\s+and\s+slow\b", r"\boff.hours\b",
    ]
    has_timing = any(re.search(p, steps, re.IGNORECASE) for p in timing_patterns)
    if not has_timing:
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
                "(e.g. random.uniform(0.5, 3.0) seconds), add jitter to C2 beacons, "
                "and operate during legitimate business hours to blend with normal traffic."
            ),
        )]
    return []


@rule
def check_credential_exposure(ctx: Dict[str, Any]) -> List[Finding]:
    """Warn if credentials might be left in logs or temp files."""
    steps = ctx.get("attack_steps", "").lower()
    findings = []
    cred_patterns = [
        (r"\bhardcoded\s+password\b", "hardcoded password in code/script"),
        (r"\bpassword\s+in\s+(url|uri|query)\b", "password embedded in URL"),
        (r"\bplaintext\s+cred", "plaintext credential handling"),
        (r"\bbase64.{0,20}password\b", "base64-encoded password (not encrypted)"),
        (r"\becho.{0,30}password\b", "password echoed to stdout/logs"),
    ]
    for pattern, label in cred_patterns:
        m = re.search(pattern, steps, re.IGNORECASE)
        if m:
            findings.append(Finding(
                rule_id="OPSEC-006",
                severity="high",
                title="Credential exposure risk",
                description=f"Credentials at risk of exposure ({label}).",
                remediation=(
                    "Pass credentials via environment variables or encrypted vaults. "
                    "Rotate any used credentials immediately post-engagement."
                ),
                evidence=f"Matched: …{m.group(0)}…",
            ))
            break
    return findings


@rule
def check_attribution_artefacts(ctx: Dict[str, Any]) -> List[Finding]:
    """Check for common attribution artefacts."""
    findings = []
    tools = ctx.get("tools_used", "").lower()
    steps = ctx.get("attack_steps", "").lower()
    text = tools + " " + steps

    burp_hits = _match(text, "burp suite", "burp")
    if burp_hits and re.search(r"\bdefault\b", text, re.IGNORECASE):
        findings.append(Finding(
            rule_id="OPSEC-007",
            severity="medium",
            title="Default Burp Suite fingerprint",
            description="Default Burp Suite headers are widely fingerprinted.",
            remediation="Customise Burp's User-Agent and match target site traffic patterns.",
            evidence="'burp' + 'default' detected in context",
        ))

    gh_patterns = [r"\bgithub\.com\b", r"\braw\.githubusercontent\b"]
    for pat in gh_patterns:
        m = re.search(pat, steps, re.IGNORECASE)
        if m:
            findings.append(Finding(
                rule_id="OPSEC-007b",
                severity="high",
                title="Public GitHub payload hosting",
                description="Fetching payloads from public GitHub creates attribution trail.",
                remediation="Host payloads on disposable infrastructure with no operator links.",
                evidence=f"GitHub URL matched: …{m.group(0)}…",
            ))
            break

    return findings


@rule
def check_lateral_movement_noise(ctx: Dict[str, Any]) -> List[Finding]:
    """Detect noisy lateral movement techniques."""
    steps = ctx.get("attack_steps", "").lower()
    noisy_lateral = {
        r"\bpsexec\b": "PsExec creates a named pipe and service, both monitored by EDR.",
        r"\bnet\s+use\b": "Net use commands are commonly logged and trigger SIEM rules.",
        r"\bwmic\b": "WMIC usage is heavily monitored by endpoint security solutions.",
        r"\bxfreerdp\b|\brdp\b.{0,20}(brute|scan|attack)": "RDP brute-force/scanning is easily detected.",
    }
    findings = []
    for pattern, reason in noisy_lateral.items():
        m = re.search(pattern, steps, re.IGNORECASE)
        if m:
            findings.append(Finding(
                rule_id="OPSEC-008",
                severity="medium",
                title="Noisy lateral movement technique",
                description=reason,
                remediation=(
                    "Use stealthier lateral movement: WMI with encoded payloads, "
                    "DCOM, or SSH tunnelling. Avoid net use and PsExec in monitored environments."
                ),
                evidence=f"Matched: …{m.group(0)}…",
            ))
    return findings


@rule
def check_c2_exposure(ctx: Dict[str, Any]) -> List[Finding]:
    """Detect poorly configured C2 infrastructure indicators."""
    steps = ctx.get("attack_steps", "").lower()
    tools = ctx.get("tools_used", "").lower()
    combined = steps + " " + tools
    findings = []

    c2_patterns = [
        (r"\bdefault\s+(profile|beacon|c2)\b", "Default C2 profile — signatured by threat intel feeds"),
        (r"\bhttp\b.{0,30}\bc2\b(?!s)", "HTTP C2 without encryption — plaintext beacon traffic"),
        (r"\bport\s+4444\b", "Port 4444 is the Metasploit default and widely blocked/alerted"),
        (r"\bport\s+1337\b", "Port 1337 is a known attacker port flagged by many firewalls"),
    ]
    for pattern, description in c2_patterns:
        m = re.search(pattern, combined, re.IGNORECASE)
        if m:
            findings.append(Finding(
                rule_id="OPSEC-009",
                severity="high",
                title="C2 infrastructure exposure risk",
                description=description,
                remediation=(
                    "Use domain fronting, HTTPS with valid certificates, custom C2 profiles, "
                    "and non-standard ports. Rotate C2 infrastructure regularly."
                ),
                evidence=f"Matched: …{m.group(0)}…",
            ))
    return findings


@rule
def check_av_evasion_missing(ctx: Dict[str, Any]) -> List[Finding]:
    """Check whether AV/EDR evasion is addressed when delivering payloads."""
    steps = ctx.get("attack_steps", "").lower()
    tools = ctx.get("tools_used", "").lower()
    detection = ctx.get("detection_method", "").lower()
    combined = steps + " " + tools

    # Only trigger if payload delivery is implied
    delivery_indicators = [r"\bpayload\b", r"\bexecutable\b", r"\b\.exe\b", r"\b\.dll\b", r"\bdropper\b", r"\bstager\b"]
    has_delivery = any(re.search(p, combined, re.IGNORECASE) for p in delivery_indicators)
    if not has_delivery:
        return []

    evasion_indicators = [
        r"\bobfuscat", r"\bencod", r"\bpack", r"\bencrypt.{0,20}payload",
        r"\bsign(ed)?\s+(binary|payload)\b", r"\bhollowing\b", r"\breflective\b",
        r"\blolbin\b", r"\bin.memory\b",
    ]
    has_evasion = any(re.search(p, combined, re.IGNORECASE) for p in evasion_indicators)
    if not has_evasion:
        return [Finding(
            rule_id="OPSEC-010",
            severity="medium",
            title="No AV/EDR evasion technique specified",
            description=(
                "Payload delivery without AV/EDR evasion will likely be caught "
                "by signature-based and behavioural detection."
            ),
            remediation=(
                "Apply payload obfuscation (encoding, packing, encryption), "
                "use LOLBins for in-memory execution, consider process hollowing "
                "or reflective DLL injection to bypass AV/EDR."
            ),
        )]
    return []


@rule
def check_network_tunneling_detection(ctx: Dict[str, Any]) -> List[Finding]:
    """Detect use of detectable tunneling methods."""
    steps = ctx.get("attack_steps", "").lower()
    findings = []

    tunnel_patterns = {
        r"\bicmp\s+tunnel\b": "ICMP tunnelling is detected by many NIDS/firewalls that rate-limit ICMP.",
        r"\bdns\s+tunnel\b.{0,50}(?!encr|obfusc)": "Unobfuscated DNS tunnelling has high-entropy queries detectable by DNS analytics.",
        r"\bngrok\b": "ngrok creates external tunnels that are flagged by DLP and proxy solutions.",
        r"\bchisel\b.{0,20}(http|default)": "Default chisel HTTP tunnelling matches known signatures.",
    }
    for pattern, reason in tunnel_patterns.items():
        m = re.search(pattern, steps, re.IGNORECASE)
        if m:
            findings.append(Finding(
                rule_id="OPSEC-011",
                severity="medium",
                title="Detectable tunneling technique",
                description=reason,
                remediation=(
                    "Prefer HTTPS-based tunnels with domain fronting, "
                    "obfuscate DNS queries with randomised subdomains, "
                    "and use legitimate cloud services as C2 fronts."
                ),
                evidence=f"Matched: …{m.group(0)}…",
            ))
    return findings


@rule
def check_long_dwell_time_risk(ctx: Dict[str, Any]) -> List[Finding]:
    """Assess if the attack maintains persistence without periodic check-ins."""
    steps = ctx.get("attack_steps", "").lower()
    detection = ctx.get("detection_method", "").lower()

    # Only relevant if persistence is involved
    if not any(re.search(p, steps, re.IGNORECASE) for p in [r"\bpersist", r"\bbackdoor\b", r"\bimplant\b"]):
        return []

    # Check if beacon interval is addressed
    beacon_patterns = [r"\bbeacon\s+interval\b", r"\bjitter\b", r"\bcheck.in\b", r"\bsleep\s+interval\b"]
    has_beacon_config = any(re.search(p, steps, re.IGNORECASE) for p in beacon_patterns)

    if not has_beacon_config:
        return [Finding(
            rule_id="OPSEC-012",
            severity="low",
            title="Persistent implant with no beacon interval specified",
            description=(
                "Persistent implants that beacon at fixed intervals are detectable "
                "by network traffic pattern analysis and anomaly detection."
            ),
            remediation=(
                "Configure a randomised beacon interval with jitter (e.g. 60s ± 30s), "
                "use asynchronous C2 (pull-based), and blend beacon traffic with "
                "legitimate HTTPS traffic patterns."
            ),
        )]
    return []
