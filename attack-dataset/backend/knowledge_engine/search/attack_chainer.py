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

from ..core.models import (
    AttackRecord,
    AttackResult,
    AttackChain,
    AttackStep,
    AttackVectorRequest,
    AttackVectorResponse,
    LiveReplanRequest,
    LiveReplanResponse,
    OpsecNote,
)
from .searcher import AttackSearcher
from .target_profiling import (
    infer_target_profile,
    enrich_search_query,
    filter_and_rerank_results,
)
from ..ml.ml_service import MLModelService

# Max MITRE phases per chain — avoids one unrelated technique per phase
MAX_STEPS_PER_CHAIN = 6

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
    "Reconnaissance": [
        "recon", "scan", "enum", "fingerprint", "osint", "discovery",
        "port scan", "banner grab", "whois", "dns lookup", "shodan",
        "nmap", "masscan", "censys", "passive recon",
    ],
    "Resource Development": [
        "staging", "infrastructure", "c2 setup", "domain registration",
        "vps", "command and control server", "payload development",
        "dropper", "implant develop",
    ],
    "Initial Access": [
        "exploit", "injection", "phish", "bypass", "login", "auth", "brute",
        "access", "entry", "initial", "spearphish", "watering hole",
        "supply chain", "valid account", "external remote", "drive-by",
        "public-facing application",
    ],
    "Execution": [
        "exec", "run", "payload", "shell", "code", "rce", "command",
        "script", "powershell", "wscript", "mshta", "macro",
        "user execution", "scheduled task exec",
    ],
    "Persistence": [
        "persist", "backdoor", "implant", "startup", "cron", "service",
        "registry run", "bootkit", "rootkit", "logon script",
        "web shell", "account creation",
    ],
    "Privilege Escalation": [
        "privilege", "escalat", "root", "admin", "sudo", "elevation",
        "uac bypass", "token impersonat", "exploit kernel",
        "setuid", "suid", "capabilities",
    ],
    "Defense Evasion": [
        "evad", "obfuscat", "stealth", "opsec", "bypass", "anti",
        "disable security", "clear log", "timestomp", "masquerad",
        "lolbin", "living off the land", "signed binary", "inject",
        "reflective", "process hollow",
    ],
    "Credential Access": [
        "credential", "password", "hash", "dump", "keylog", "token",
        "mimikatz", "hashdump", "lsass", "kerberoast", "pass the hash",
        "golden ticket", "silver ticket", "ntlm",
    ],
    "Discovery": [
        "discover", "survey", "network map", "host discover",
        "account discover", "file discover", "system info",
        "process list", "service discover", "share discover",
    ],
    "Lateral Movement": [
        "lateral", "pivot", "spread", "move", "relay",
        "pass-the-hash", "pth", "rdp", "ssh tunnel", "smb",
        "wmi", "psexec", "winrm", "dcom",
    ],
    "Collection": [
        "collect", "gather", "harvest", "screenshot", "clipboard",
        "keylog collect", "audio capture", "email collect", "data staged",
    ],
    "Exfiltration": [
        "exfil", "data theft", "leak", "extract", "out-of-band",
        "dns exfil", "https exfil", "ftp exfil", "steganograph",
        "covert channel", "data transfer",
    ],
    "Impact": [
        "drop", "delete", "ransom", "dos", "disrupt", "damage",
        "wipe", "encrypt files", "defac", "ddos", "destroy",
        "service stop", "data destruct",
    ],
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

    # Better fallback: check category field for a coarser match
    category_text = record.category.lower()
    if any(k in category_text for k in ["web", "injection", "xss", "sqli"]):
        return "Initial Access"
    if any(k in category_text for k in ["malware", "ransomware", "virus"]):
        return "Impact"
    if any(k in category_text for k in ["network", "traffic", "wireless"]):
        return "Reconnaissance"
    return "Execution"  # final default


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
        # Initialize ML service for enhanced attack classification
        try:
            self.ml_service = MLModelService()
            self.ml_enabled = True
        except Exception as e:
            print(f"Warning: ML service initialization failed: {e}")
            self.ml_service = None
            self.ml_enabled = False

    def build_chains(self, request: AttackVectorRequest) -> AttackVectorResponse:
        profile = infer_target_profile(
            request.target_description,
            request.detected_services,
        )
        full_query = enrich_search_query(
            request.target_description,
            request.detected_services,
            request.detected_os,
            profile,
        )

        # Pull candidate attacks via semantic search
        response = self.searcher.semantic_search(full_query, top_k=50)
        response.results = filter_and_rerank_results(response.results, profile)
        candidates: List[AttackRecord] = [r.record for r in response.results]

        if not candidates:
            return AttackVectorResponse(
                target_description=request.target_description,
                chains=[],
            )

        # Enhanced: ML-based classification and re-ranking (web targets: favor semantic match)
        ml_semantic_weight = (
            0.85
            if profile.target_class in ("web_application", "ecommerce")
            else 0.6
        )
        ml_weight = 1.0 - ml_semantic_weight

        if self.ml_enabled and self.ml_service and candidates:
            try:
                # Prepare text for ML prediction from attack records
                texts_for_ml = []
                for rec in candidates:
                    # Combine relevant fields for ML classification
                    text = f"{rec.title} {rec.attack_type} {rec.category} {rec.scenario_description[:200]}"
                    texts_for_ml.append(text)
                
                # Check if category model is available
                available_models = list(self.ml_service.models.keys())
                if not available_models:
                    print("Warning: No ML models available for enhancement")
                else:
                    # Use the first available model (likely 'category')
                    target_name = available_models[0]
                    
                    # Batch predict using ML service
                    ml_predictions = self.ml_service.batch_predict(target_name, texts_for_ml, top_k=1)
                    
                    # Combine semantic search scores with ML confidence scores
                    # Weight: 60% semantic + 40% ML confidence
                    enhanced_results = []
                    for idx, (rec, semantic_result) in enumerate(zip(candidates, response.results)):
                        semantic_score = semantic_result.score
                        
                        # Extract top prediction from ML results
                        ml_confidence = 0.0
                        ml_category = 'Unknown'
                        if idx < len(ml_predictions) and len(ml_predictions[idx]) > 0:
                            top_prediction = ml_predictions[idx][0]
                            ml_confidence = top_prediction.get('confidence', 0.0)
                            ml_category = top_prediction.get('label', 'Unknown')
                        
                        # Combined score calculation (profile-aware weights)
                        combined_score = (
                            ml_semantic_weight * semantic_score + ml_weight * ml_confidence
                        )
                        
                        # Store ML prediction info in the record for later use
                        rec.ml_category = ml_category
                        rec.ml_confidence = ml_confidence
                        rec.combined_score = combined_score
                        
                        enhanced_results.append(AttackResult(
                            record=rec,
                            score=combined_score
                        ))
                    
                    # Re-rank candidates by combined score, then re-apply target filter
                    enhanced_results.sort(key=lambda x: x.score, reverse=True)
                    response.results = filter_and_rerank_results(
                        enhanced_results, profile, max_candidates=25
                    )
                    candidates = [r.record for r in response.results]

                    print(
                        f"ML enhancement applied: {len(candidates)} candidates "
                        f"re-ranked using model '{target_name}' (profile={profile.target_class})"
                    )
            except Exception as e:
                print(f"Warning: ML enhancement failed, falling back to semantic search only: {e}")

        # Phase-classify every candidate
        phased: Dict[str, List[AttackRecord]] = {p: [] for p in PHASE_ORDER}
        score_by_id: Dict[int, float] = {
            r.record.id: r.score for r in response.results
        }
        for rec in candidates:
            phase = classify_phase(rec)
            phased[phase].append(rec)

        # Build `top_chains` chains — one relevant technique per populated phase, capped
        chains: List[AttackChain] = []
        for chain_idx in range(request.top_chains):
            steps: List[AttackStep] = []
            for phase in PHASE_ORDER:
                if len(steps) >= MAX_STEPS_PER_CHAIN:
                    break
                pool = phased[phase]
                if not pool:
                    continue
                # Prefer highest relevance within phase (offset per chain for diversity)
                pool_sorted = sorted(
                    pool,
                    key=lambda r: score_by_id.get(r.id, 0.0),
                    reverse=True,
                )
                pick_idx = chain_idx % len(pool_sorted)
                rec = pool_sorted[pick_idx]
                steps.append(AttackStep(
                    phase=phase,
                    attack=rec,
                    rationale=(
                        f"Selected for phase '{phase}' ({profile.target_class}) "
                        f"matching '{request.target_description[:60]}'"
                    ),
                    mitre_technique=rec.mitre_technique,
                ))

            if not steps:
                continue

            # Confidence from relevance scores and step count (not full MITRE coverage)
            step_scores = [score_by_id.get(s.attack.id, 0.0) for s in steps]
            avg_score = sum(step_scores) / max(len(step_scores), 1)
            step_factor = min(1.0, len(steps) / 5.0)
            confidence = round(avg_score * 0.75 + step_factor * 0.25, 3)
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

    def build_live_replan(self, request: LiveReplanRequest) -> LiveReplanResponse:
        """
        Rebuild attack chains using semantic search + ML re-rank, enriched with
        live execution feedback (failed steps, completed outputs).
        """
        ctx = request.execution_context
        feedback_parts: List[str] = ["LIVE EXECUTION FEEDBACK"]

        if ctx.from_phase:
            feedback_parts.append(f"resume_from_phase={ctx.from_phase}")
        if ctx.from_step_index:
            feedback_parts.append(f"from_step_index={ctx.from_step_index}")

        for step in (ctx.completed_steps or [])[-8:]:
            phase = step.get("phase") or step.get("step", {}).get("phase") or ""
            status = step.get("status") or "unknown"
            title = (
                step.get("attack", {}).get("title")
                or step.get("step", {}).get("attack", {}).get("title")
                or ""
            )
            feedback_parts.append(f"COMPLETED {phase} {title} status={status}")

        if ctx.last_failure:
            lf = ctx.last_failure
            tool = lf.get("tool") or lf.get("failed_tool") or "unknown"
            output_snip = str(lf.get("output") or "")[:2000]
            failure_class = lf.get("failure_class") or getattr(request, "failure_class", None) or "unknown"
            feedback_parts.append(
                f"FAILED phase={lf.get('phase')} tool={tool} "
                f"failure_class={failure_class} "
                f"method={lf.get('method_name') or lf.get('method_id')} "
                f"output={output_snip}"
            )
            if tool and tool != "unknown":
                feedback_parts.append(
                    f"prioritize alternate techniques avoiding sole reliance on {tool}"
                )

        completed_phases = set()
        for step in ctx.completed_steps or []:
            ph = step.get("phase") or (step.get("step") or {}).get("phase")
            if ph and step.get("status") == "success":
                completed_phases.add(ph)

        grounding_query = " ".join(
            filter(
                None,
                [
                    request.target_description,
                    " ".join(request.detected_services or []),
                    request.detected_os or "",
                    " ".join(feedback_parts),
                ],
            )
        )

        enriched = AttackVectorRequest(
            target_description=grounding_query,
            detected_services=request.detected_services,
            detected_os=request.detected_os,
            top_chains=max(request.top_chains, 2),
        )

        base = self.build_chains(enriched)
        failed_tool = None
        if ctx.last_failure:
            failed_tool = (
                ctx.last_failure.get("tool")
                or ctx.last_failure.get("failed_tool")
            )

        chains = list(base.chains or [])
        if failed_tool and failed_tool != "unknown":
            def chain_penalty(chain) -> float:
                penalty = 0.0
                for s in chain.steps or []:
                    tools = (s.attack.tools_used or "").lower()
                    if failed_tool.lower() in tools:
                        penalty += 0.35
                return penalty

            for c in chains:
                c.confidence = max(0.05, (c.confidence or 0.5) - chain_penalty(c))
            chains.sort(key=lambda c: c.confidence or 0, reverse=True)

        if completed_phases and chains:
            filtered = []
            for chain in chains:
                new_steps = [
                    s for s in (chain.steps or [])
                    if s.phase not in completed_phases
                ]
                if new_steps:
                    filtered.append(
                        chain.model_copy(update={"steps": new_steps})
                        if hasattr(chain, "model_copy")
                        else AttackChain(
                            chain_id=chain.chain_id,
                            target_description=chain.target_description,
                            confidence=chain.confidence,
                            steps=new_steps,
                            estimated_impact=chain.estimated_impact,
                            opsec_notes=chain.opsec_notes,
                        )
                    )
            if filtered:
                chains = filtered

        alternate_chain_scores = [round(c.confidence or 0.0, 3) for c in chains]
        dataset_hit_count = 0
        ml_top_label = None
        ml_top_confidence = None

        try:
            search_resp = self.searcher.semantic_search(grounding_query, top_k=15)
            dataset_hit_count = len(search_resp.results)
            if search_resp.results:
                top_rec = search_resp.results[0].record
                ml_top_label = getattr(top_rec, "ml_category", None) or top_rec.category
                ml_top_confidence = getattr(top_rec, "ml_confidence", None) or search_resp.results[0].score
        except Exception as e:
            print(f"Warning: live replan search metadata failed: {e}")

        return LiveReplanResponse(
            target_description=base.target_description,
            chains=chains,
            grounding_query=grounding_query,
            dataset_hit_count=dataset_hit_count,
            ml_top_label=ml_top_label,
            ml_top_confidence=ml_top_confidence,
            replan_reason="live_execution_feedback",
            alternate_chain_scores=alternate_chain_scores,
            failure_class=getattr(request, "failure_class", None)
            or (ctx.last_failure or {}).get("failure_class"),
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

        from ..core.models import AttackRecord
        rec = AttackRecord(**{k: (v or "") for k, v in row.items()})
        hints = extract_evasion_hints(rec)

        recommended = [
            "Ensure clean exit: wipe temp files, flush shell history",
            "Restore modified configs",
            "Use covert C2 channels"
        ]
        
        # Determine risk level based on attack characteristics
        risk_level = "medium"
        attack_text = (rec.attack_type + " " + rec.title + " " + rec.scenario_description).lower()
        
        high_risk_indicators = [
            "rce", "remote code", "code execution", "injection", "sql injection", 
            "bypass", "privilege escalation", "root", "administrator", "exploit",
            "shell", "backdoor", "malware", "ransomware", "credential theft"
        ]
        
        low_risk_indicators = [
            "reconnaissance", "enumeration", "scanning", "fingerprint", "discovery",
            "information gathering", "passive"
        ]
        
        if any(indicator in attack_text for indicator in high_risk_indicators):
            risk_level = "high"
        elif any(indicator in attack_text for indicator in low_risk_indicators):
            risk_level = "low"

        return OpsecNote(
            attack_id=attack_id,
            detection_method=rec.detection_method,
            risk_level=risk_level,
            recommendations=recommended,
        )
