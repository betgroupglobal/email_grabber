"""
Minimal Knowledge Engine API - simplified version for testing
"""
import sys
import os
import logging

# Add parent directory to path to import shared modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from shared.fastapi_robustness import setup_robustness_middleware

# Configuration
POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://opsec:opsec@postgres:5432/attack_db")
QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("simple_api")

app = FastAPI(title="Knowledge Engine API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup robustness middleware
setup_robustness_middleware(
    app,
    service_name="knowledge-engine",
    timeout_seconds=30.0,
    version="1.0.0",
)

# Health check endpoint (robustness middleware already adds /health, /ready, /live, /metrics)
# Keeping this for backward compatibility with orchestrator health aggregation

# Root endpoint
@app.get("/")
async def root():
    return {"message": "OpsecAI Knowledge Engine API", "version": "1.0.0"}

# Attack vector endpoint for orchestrator
from pydantic import BaseModel

class AttackVectorRequest(BaseModel):
    target_description: str
    detected_services: list = []
    os_guess: str = "unknown"

class AttackChain(BaseModel):
    steps: list = []
    confidence: float = 0.0

class AttackVectorResponse(BaseModel):
    chains: list = []
    summary: str = ""

@app.post("/attack-vector")
async def build_attack_vector(request: AttackVectorRequest):
    """Simple attack vector builder - returns basic attack chains based on detected services"""
    chains = []
    
    # Generate simple attack chains based on detected services.
    # "attack" is an object with a "title" field to match the realtime analyzer's
    # AttackRecord struct (Go) and maintain consistency with the full API.
    if "http" in request.detected_services or "80" in request.detected_services or "443" in request.detected_services:
        chains.append(AttackChain(
            steps=[
                {"attack": {"title": "Web Application Scanning", "mitre_technique": "T1190", "detection_method": "WAF logs"}, "mitre_technique": "T1190"},
                {"attack": {"title": "SQL Injection", "mitre_technique": "T1190", "detection_method": "Input validation"}, "mitre_technique": "T1190"},
                {"attack": {"title": "Cross-Site Scripting", "mitre_technique": "T1059", "detection_method": "CSP headers"}, "mitre_technique": "T1059"}
            ],
            confidence=0.8
        ))

    if "ssh" in request.detected_services or "22" in request.detected_services:
        chains.append(AttackChain(
            steps=[
                {"attack": {"title": "SSH Brute Force", "mitre_technique": "T1111", "detection_method": "Failed login logs"}, "mitre_technique": "T1111"},
                {"attack": {"title": "SSH Key Theft", "mitre_technique": "T1021", "detection_method": "Key monitoring"}, "mitre_technique": "T1021"}
            ],
            confidence=0.7
        ))

    # Default chain if no specific services detected
    if not chains:
        chains.append(AttackChain(
            steps=[
                {"attack": {"title": "Network Reconnaissance", "mitre_technique": "T1018", "detection_method": "Network monitoring"}, "mitre_technique": "T1018"},
                {"attack": {"title": "Port Scanning", "mitre_technique": "T1046", "detection_method": "IDS alerts"}, "mitre_technique": "T1046"}
            ],
            confidence=0.6
        ))
    
    return AttackVectorResponse(
        chains=chains,
        summary=f"Generated {len(chains)} attack chain(s) for {request.target_description} with services: {', '.join(request.detected_services) if request.detected_services else 'none detected'}"
    )


# ── Full engine (dataset + trained model) — lazy load ─────────────────────────
_chainer = None
_searcher = None
_ml_service = None


def _load_full_engine():
    global _chainer, _searcher, _ml_service
    if _chainer is not None:
        return _searcher, _chainer, _ml_service
    try:
        from knowledge_engine.search.searcher import AttackSearcher
        from knowledge_engine.search.attack_chainer import AttackChainer
        from knowledge_engine.ml.ml_service import get_ml_service

        _searcher = AttackSearcher()
        _chainer = AttackChainer(_searcher)
        _ml_service = get_ml_service()
        log.info("Full AttackChainer + ML service loaded")
        return _searcher, _chainer, _ml_service
    except Exception as exc:
        log.warning("Full knowledge engine unavailable: %s", exc)
        return None, None, None


class SearchBody(BaseModel):
    query: str
    top_k: int = 15


@app.post("/search")
async def semantic_search(body: SearchBody):
    """Semantic search over attack database (Qdrant + Postgres)."""
    searcher, _, _ = _load_full_engine()
    if searcher is None:
        return {"query": body.query, "results": [], "total": 0, "note": "stub_mode"}
    resp = searcher.semantic_search(body.query, top_k=body.top_k)
    return {
        "query": resp.query,
        "total": resp.total,
        "results": [
            {
                "score": r.score,
                "record": r.record.model_dump() if hasattr(r.record, "model_dump") else dict(r.record),
            }
            for r in resp.results
        ],
    }


class MLPredictBody(BaseModel):
    text: str
    target: str = "category"
    top_k: int = 5


@app.post("/ml/predict")
async def ml_predict(body: MLPredictBody):
    """Trained model classification for live council grounding."""
    _, _, ml = _load_full_engine()
    if ml is None:
        return {
            "text": body.text,
            "target": body.target,
            "predictions": [{"label": "Network Security", "confidence": 0.5, "rank": 1}],
            "note": "stub_mode",
        }
    preds = ml.predict(target_name=body.target, text=body.text, top_k=body.top_k)
    return {
        "text": body.text,
        "target": body.target,
        "predictions": preds,
    }


class ExecutionFeedbackContext(BaseModel):
    completed_steps: list = []
    last_failure: Optional[dict] = None
    from_phase: Optional[str] = None
    from_step_index: int = 0
    prior_directive_ids: list = []


class LiveReplanRequest(BaseModel):
    target_description: str
    detected_services: list = []
    detected_os: Optional[str] = None
    top_chains: int = 2
    execution_context: ExecutionFeedbackContext = ExecutionFeedbackContext()


@app.post("/attack-vector/live-replan")
async def live_replan_attack_vector(request: LiveReplanRequest):
    """
    Replan chains using attack database + trained ML model and live step feedback.
    """
    _, chainer, _ = _load_full_engine()
    if chainer is not None:
        try:
            from knowledge_engine.core.models import LiveReplanRequest as FullLiveReplanRequest
            from knowledge_engine.core.models import ExecutionFeedbackContext as FullCtx

            full_req = FullLiveReplanRequest(
                target_description=request.target_description,
                detected_services=request.detected_services,
                detected_os=request.detected_os,
                top_chains=request.top_chains,
                execution_context=FullCtx(**request.execution_context.model_dump()),
            )
            resp = chainer.build_live_replan(full_req)
            return resp.model_dump()
        except Exception as exc:
            log.error("live-replan full engine failed: %s", exc)

    # Stub fallback when chainer unavailable
    base = await build_attack_vector(
        AttackVectorRequest(
            target_description=request.target_description + " LIVE_REPLAN_FALLBACK",
            detected_services=request.detected_services,
        )
    )
    failed_tool = (request.execution_context.last_failure or {}).get("tool", "")
    alt_title = f"Alternate vector (avoid {failed_tool})" if failed_tool else "Alternate vector"
    extra_steps = [{"attack": {"title": alt_title, "mitre_technique": "T1190"}, "phase": "Execution"}]
    if base.chains:
        base.chains[0].steps = (base.chains[0].steps or []) + extra_steps
    return {
        "target_description": request.target_description,
        "chains": [c.model_dump() if hasattr(c, "model_dump") else c for c in base.chains],
        "grounding_query": request.target_description,
        "dataset_hit_count": 0,
        "ml_top_label": None,
        "ml_top_confidence": None,
        "replan_reason": "live_execution_feedback_stub",
    }


# OpSec assessment endpoints
class OpSecAssessmentRequest(BaseModel):
    attack_chains: list = []
    target: str = "unknown"

class OpSecAssessmentResponse(BaseModel):
    target: str = "unknown"
    risk_score: int = 0
    attack_chains: dict = {}
    recommendations: list = []

@app.post("/opsec/assess")
async def opsec_assess(request: OpSecAssessmentRequest):
    """Simple OpSec assessment - returns basic risk score and recommendations"""
    target = request.target or "unknown"
    source_chains = request.attack_chains or []
    if source_chains:
        chains = source_chains
    else:
        chains = [
            {
                "chain_id": f"opsec-{target}-recon",
                "target_description": target,
                "confidence": 0.72,
                "estimated_impact": "Security assessment identifies likely exposure and validation path",
                "opsec_notes": "Run only against authorized assets; prefer rate-limited and logged validation.",
                "steps": [
                    {
                        "phase": "reconnaissance",
                        "attack": {
                            "title": "Passive target profiling",
                            "mitre_technique": "T1595",
                            "description": f"Collect non-invasive context for {target}",
                        },
                        "rationale": "Establish target context before active validation.",
                        "mitre_technique": "T1595",
                    },
                    {
                        "phase": "scanning",
                        "attack": {
                            "title": "Service exposure validation",
                            "mitre_technique": "T1046",
                            "description": "Validate exposed services with conservative timing.",
                        },
                        "rationale": "Identify reachable services that may require hardening.",
                        "mitre_technique": "T1046",
                    },
                    {
                        "phase": "exploitation",
                        "attack": {
                            "title": "Safe vulnerability verification",
                            "mitre_technique": "T1190",
                            "description": "Confirm suspected issues with non-destructive checks.",
                        },
                        "rationale": "Prioritize remediations without performing destructive actions.",
                        "mitre_technique": "T1190",
                    },
                ],
            }
        ]

    # Calculate simple risk score based on number of chains and steps
    total_steps = sum(len(chain.get("steps", [])) for chain in chains)
    risk_score = min(100, total_steps * 10)  # Simple risk calculation
    
    recommendations = [
        "Use encrypted communications when possible",
        "Limit attack surface by disabling unnecessary services",
        "Implement proper authentication and authorization",
        "Monitor system logs for suspicious activity"
    ]
    
    return OpSecAssessmentResponse(
        target=target,
        risk_score=risk_score,
        attack_chains={"chains": chains},
        recommendations=recommendations[:3]  # Return top 3 recommendations
    )

class OpSecAuditRequest(BaseModel):
    attack_vector: dict = {}

class OpSecAuditResponse(BaseModel):
    audit_results: dict = {}
    warnings: list = []

@app.post("/opsec/audit")
async def opsec_audit(request: OpSecAuditRequest):
    """Simple OpSec audit - returns basic audit results"""
    audit_results = {
        "stealth_score": 70,
        "noise_level": "medium",
        "detection_risk": "moderate"
    }
    
    warnings = [
        "Consider using timing-based evasion techniques",
        "Attack chains could benefit from additional obfuscation",
        "Some attack steps may generate significant network noise"
    ]
    
    return OpSecAuditResponse(
        audit_results=audit_results,
        warnings=warnings[:2]
    )

@app.post("/opsec/audit/vector")
async def opsec_audit_vector(request: OpSecAuditRequest):
    """Simple OpSec audit for attack vectors - returns basic audit results"""
    audit_results = {
        "stealth_score": 70,
        "noise_level": "medium",
        "detection_risk": "moderate",
        "overall_opsec_score": 68
    }
    
    warnings = [
        "Consider using timing-based evasion techniques",
        "Attack chains could benefit from additional obfuscation"
    ]
    
    return OpSecAuditResponse(
        audit_results=audit_results,
        warnings=warnings[:2]
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)