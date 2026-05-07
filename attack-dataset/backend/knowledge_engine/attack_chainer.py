"""
Attack Chainer — builds multi-stage attack graphs from dataset knowledge.

Given a target description (services, OS, context), it:
  1. Queries the searcher for relevant attacks
  2. Groups them into phases (Recon → Initial Access → Execution → Persistence → Exfil)
  3. Builds ranked chains with OpSec notes
"""
from __future__ import annotations

import hashlib
import uuid
from typing import List, Dict, Optional

from models import (
    AttackRecord,
    AttackChain,
    AttackStep,
    AttackVectorRequest,
    AttackVectorResponse,
    OpsecNote,
)
from searcher import AttackSearcher

# MITRE phase ordering — loosely mapped from tactic keywords
PHASE_ORDER = [
    "Reconnaissance",
    "Resource Development",
    "Initial Access",
    "Execution",
    "Persistence",
    "Privilege Escalation",
    "Defense Evasion",
    "Credential Access",
    "Discovery",
    "Lateral Movement",
    "Collection",
    "Exfiltration",
    "Impact",
]

PHASE_KEYWORDS: Dict[str, List[str]] = {
    "Reconnaissance": ["recon", "scan", "enum", "fingerprint", "osint", "discovery"],
    "Initial Access": [
        "exploit", "injection", "phish", "bypass", "login", "auth", "brute",
        "access", "entry", "initial",
    ],
    "Execution": ["exec", "run", "payload", "shell", "code", "rce", "command"],
    "Persistence": ["persist", "backdoor", "implant", "startup", "cron", "service"],
    "Privilege Escalation": ["privilege", "escalat", "root", "admin", "sudo", "elevation"],
    "Defense Evasion": ["evad", "obfuscat", "stealth", "opsec", "bypass", "anti"],
    "Credential Access": ["credential", "password", "hash", "dump", "keylog", "token"],
    "Lateral Movement": ["lateral", "pivot", "spread", "move", "relay"],
    "Exfiltration": ["exfil", "data theft", "leak", "extract", "out-of-band"],
    "Impact": ["drop", "delete", "ransom", "dos", "disrupt", "damage"],
}


def classify_phase(record: AttackRecord) -> str:
    text = (
        record.attack_type + " " +
        record.title + " " +
        record.mitre_technique + " " +
        record.tags
    ).lower()

    for phase in PHASE_ORDER:
        for kw in PHASE_KEYWORDS.get(phase, []):
            if kw in text:
                return phase

    return "Execution"  # default bucket


def extract_evasion_hints(record: AttackRecord) -> List[str]:
    hints = []
    detection = record.detection_method.lower()

    if "log" in detection:
        hints.append("Clear or redirect application/system logs after execution")
    if "waf" in detection or "firewall" in detection:
        hints.append("Encode payloads to bypass WAF signature detection")
    if "ids" in detection or "ips" in detection:
        hints.append("Fragment or time-delay traffic to evade IDS/IPS sensors")
    if "anomaly" in detection:
        hints.append("Blend traffic with normal baseline to avoid anomaly alerts")
    if "edr" in detection or "endpoint" in detection:
        hints.append("Use LOLBins or fileless techniques to avoid EDR telemetry")
    if "monitor" in detection:
        hints.append("Delay C2 callbacks to mimic idle connection patterns")
    if not hints:
        hints.append("Operate during high-traffic periods to reduce signal-to-noise ratio")

    return hints


def build_opsec_note(steps: List[AttackStep]) -> str:
    note_parts = []
    for step in steps:
        hints = extract_evasion_hints(step.attack)
        note_parts.append(f"[{step.phase}] " + "; ".join(hints[:2]))
    return " | ".join(note_parts)


def estimate_impact(steps: List[AttackStep]) -> str:
    impacts = [s.attack.impact for s in steps if s.attack.impact]
    if not impacts:
        return "Unknown"
    # Return the most impactful (longest) impact string as a proxy
    return max(impacts, key=len)[:200]


class AttackChainer:
    def __init__(self, searcher: AttackSearcher):
        self.searcher = searcher

    def build_chains(self, request: AttackVectorRequest) -> AttackVectorResponse:
        # Build a rich query from all target context
        services_str = ", ".join(request.detected_services) if request.detected_services else ""
        os_str = request.detected_os or ""
        full_query = " ".join(filter(None, [
            request.target_description,
            services_str,
            os_str,
        ]))

        # Pull candidate attacks via semantic search
        response = self.searcher.semantic_search(full_query, top_k=40)
        candidates: List[AttackRecord] = [r.record for r in response.results]

        if not candidates:
            return AttackVectorResponse(
                target_description=request.target_description,
                chains=[],
            )

        # Phase-classify every candidate
        phased: Dict[str, List[AttackRecord]] = {p: [] for p in PHASE_ORDER}
        for rec in candidates:
            phase = classify_phase(rec)
            phased[phase].append(rec)

        # Build `top_chains` chains by sampling differently from phased buckets
        chains: List[AttackChain] = []
        for chain_idx in range(request.top_chains):
            steps: List[AttackStep] = []
            for phase in PHASE_ORDER:
                pool = phased[phase]
                if not pool:
                    continue
                # Each chain picks a different attack per phase (round-robin)
                pick_idx = chain_idx % len(pool)
                rec = pool[pick_idx]
                steps.append(AttackStep(
                    phase=phase,
                    attack=rec,
                    rationale=(
                        f"Selected for phase '{phase}' based on semantic match "
                        f"to target context '{request.target_description[:60]}'"
                    ),
                    mitre_technique=rec.mitre_technique,
                ))

            if not steps:
                continue

            confidence = round(
                len(steps) / len(PHASE_ORDER) *
                (response.results[0].score if response.results else 0.5),
                3
            )
            chain_id = str(uuid.uuid4())[:8]

            chains.append(AttackChain(
                chain_id=chain_id,
                target_description=request.target_description,
                confidence=confidence,
                steps=steps,
                estimated_impact=estimate_impact(steps),
                opsec_notes=build_opsec_note(steps),
            ))

        return AttackVectorResponse(
            target_description=request.target_description,
            chains=chains,
        )

    def get_opsec_note(self, attack_id: int) -> Optional[OpsecNote]:
        with self.searcher.pg.cursor() as cur:
            cur.execute("SELECT * FROM attacks WHERE id = %s", (attack_id,))
            row = cur.fetchone()
        if not row:
            return None

        import psycopg2.extras
        with self.searcher.pg.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:
            cur.execute("SELECT * FROM attacks WHERE id = %s", (attack_id,))
            row = dict(cur.fetchone())

        from models import AttackRecord
        rec = AttackRecord(**{k: (v or "") for k, v in row.items()})
        hints = extract_evasion_hints(rec)

        recommended = (
            "Ensure clean exit: wipe temp files, flush shell history, "
            "restore modified configs, and use covert C2 channels."
        )

        return OpsecNote(
            attack_id=attack_id,
            detection_method=rec.detection_method,
            evasion_hints=hints,
            recommended_opsec=recommended,
        )
