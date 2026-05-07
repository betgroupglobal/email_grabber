"""
OpSec Monitor — FastAPI service.

Accepts attack context (attack_steps, tools_used, mitre_technique, etc.)
and returns a full OpSec assessment with prioritised findings.
"""
from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from rules import RULES, Finding

log = logging.getLogger("opsec_monitor")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="OpSec Monitor",
    description="Operational security assessment for live pentest attack plans",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Models ────────────────────────────────────────────────────────────────────

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


class AttackContext(BaseModel):
    attack_id: Optional[int] = None
    title: str = ""
    attack_type: str = ""
    attack_steps: str = Field(..., description="Full attack steps text")
    tools_used: str = ""
    mitre_technique: str = ""
    detection_method: str = ""
    tags: str = ""


class OpsecFinding(BaseModel):
    rule_id: str
    severity: str
    title: str
    description: str
    remediation: str
    evidence: str = ""


class OpsecReport(BaseModel):
    attack_id: Optional[int]
    title: str
    total_findings: int
    critical: int
    high: int
    medium: int
    low: int
    info: int
    risk_score: float = Field(..., description="0-100 composite risk score")
    findings: List[OpsecFinding]
    summary: str


class ChainOpsecRequest(BaseModel):
    steps: List[AttackContext]


class ChainOpsecReport(BaseModel):
    total_findings: int
    risk_score: float
    per_step: List[OpsecReport]
    global_findings: List[OpsecFinding]


# ── helpers ───────────────────────────────────────────────────────────────────

def run_rules(ctx: Dict[str, Any]) -> List[Finding]:
    findings = []
    for rule_fn in RULES:
        findings.extend(rule_fn(ctx))
    return sorted(findings, key=lambda f: SEVERITY_ORDER.get(f.severity, 99))


def score(findings: List[Finding]) -> float:
    weights = {"critical": 40, "high": 20, "medium": 10, "low": 5, "info": 1}
    raw = sum(weights.get(f.severity, 0) for f in findings)
    return min(100.0, round(raw, 1))


def build_report(ctx: AttackContext) -> OpsecReport:
    data = ctx.model_dump()
    findings = run_rules(data)

    counts: Dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    risk = score(findings)
    summary = (
        f"Risk score {risk}/100. "
        f"{counts['critical']} critical, {counts['high']} high, "
        f"{counts['medium']} medium, {counts['low']} low findings."
    )
    if risk >= 70:
        summary += " This attack plan has significant OpSec exposure — review findings before executing."
    elif risk >= 40:
        summary += " Moderate OpSec risk — address high/critical issues before proceeding."
    else:
        summary += " OpSec posture is acceptable; apply low-priority remediations when possible."

    return OpsecReport(
        attack_id=ctx.attack_id,
        title=ctx.title or ctx.attack_type,
        total_findings=len(findings),
        critical=counts["critical"],
        high=counts["high"],
        medium=counts["medium"],
        low=counts["low"],
        info=counts.get("info", 0),
        risk_score=risk,
        findings=[OpsecFinding(**f.__dict__) for f in findings],
        summary=summary,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "opsec-monitor"}


@app.post("/assess", response_model=OpsecReport)
def assess(ctx: AttackContext):
    """
    Assess a single attack step for OpSec risks.
    """
    return build_report(ctx)


@app.post("/assess/chain", response_model=ChainOpsecReport)
def assess_chain(request: ChainOpsecRequest):
    """
    Assess a full multi-step attack chain.
    Returns per-step reports plus aggregated global findings.
    """
    per_step = [build_report(step) for step in request.steps]

    # Aggregate all findings
    all_findings: List[Finding] = []
    for step_data in request.steps:
        all_findings.extend(run_rules(step_data.model_dump()))

    # Deduplicate by rule_id
    seen = set()
    unique_findings = []
    for f in all_findings:
        if f.rule_id not in seen:
            seen.add(f.rule_id)
            unique_findings.append(f)

    global_score = score(all_findings)

    return ChainOpsecReport(
        total_findings=len(all_findings),
        risk_score=global_score,
        per_step=per_step,
        global_findings=[OpsecFinding(**f.__dict__) for f in unique_findings],
    )


@app.get("/rules")
def list_rules():
    """List all active OpSec rules."""
    return [
        {
            "rule_id": f"OPSEC-{str(i+1).zfill(3)}",
            "name": fn.__name__,
            "description": (fn.__doc__ or "").strip(),
        }
        for i, fn in enumerate(RULES)
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("monitor:app", host="0.0.0.0", port=8002, reload=True)
