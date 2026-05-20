"""
Knowledge Engine FastAPI — main REST entry point.
"""
from __future__ import annotations
import sys
import os
# Add parent directory to path to import shared modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import Request
from shared.auth import Role, User, verify_service_token
from shared.middleware import require_role, require_permission
from shared.users import auth_service, user_store
from shared.graceful_shutdown import setup_graceful_shutdown_fastapi, close_database_connection
from shared.robustness import (
    retry_with_backoff, with_timeout, CircuitBreakerConfig, 
    RetryConfig, robustness_manager, CircuitBreakerOpenError
)
from shared.error_handling import (
    ErrorHandler, OpsecAIError, ErrorCode, ErrorSeverity,
    create_error_handler_middleware, ServiceUnavailableError,
    OperationTimeoutError
)
from shared.config_validator import (
    ConfigValidator, validate_service_config, validate_database_url, ValidationSeverity
)


import logging
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
import sys
import os
import uuid

from fastapi import Request,  Request,  Request,  FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from ..utils.config import API_HOST, API_PORT, JAILBREAK_API_KEY, QDRANT_HOST, QDRANT_PORT, EMBEDDING_MODEL, OPENROUTER_MODEL
from .models import (
    SearchQuery,
    SearchResponse,
    AttackRecord,
    AttackVectorRequest,
    AttackVectorResponse,
    LiveReplanRequest,
    LiveReplanResponse,
    MitreMapping,
    OpsecNote,
    MLPredictRequest,
    MLPredictResponse,
    MLBatchPredictRequest,
    MLModelInfo,
    MLModelsResponse,
    MLPrediction,
)
from ..search.searcher import AttackSearcher
from ..search.attack_chainer import AttackChainer
from ..ai.jail_break_ai import ClaudeAnalyst
from ..utils.opsec_audit import OpSecAuditEngine
from ..ml.ml_service import get_ml_service
from ..ml.threat_emulation import get_threat_emulation_service

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
log = logger

searcher: AttackSearcher
chainer: AttackChainer
analyst: Optional[ClaudeAnalyst] = None
audit_engine: OpSecAuditEngine
threat_emulation_service: Optional[Any] = None
error_handler: ErrorHandler


@asynccontextmanager
async def lifespan(app: FastAPI):
    global searcher, chainer, analyst, audit_engine, threat_emulation_service, error_handler
    
    # Initialize error handler
    error_handler = ErrorHandler("knowledge-engine")
    
    # Validate configuration
    log.info("Validating configuration...")
    config_validator = ConfigValidator("knowledge-engine")
    config_validator.require_field("POSTGRES_DSN")
    config_validator.require_field("QDRANT_HOST")
    config_validator.require_field("QDRANT_PORT")
    config_validator.add_validator("QDRANT_PORT", lambda x: None if isinstance(x, int) and 1 <= x <= 65535 else "Invalid port")
    
    # Validate environment variables
    env_config = {
        "POSTGRES_DSN": os.getenv("POSTGRES_DSN"),
        "QDRANT_HOST": os.getenv("QDRANT_HOST"),
        "QDRANT_PORT": os.getenv("QDRANT_PORT"),
        "JAILBREAK_API_KEY": os.getenv("JAILBREAK_API_KEY")
    }
    validation_result = config_validator.validate_env_vars(env_config)
    
    if not validation_result.is_valid:
        critical_issues = validation_result.get_issues_by_severity(ValidationSeverity.CRITICAL)
        if critical_issues:
            log.error(f"Configuration validation failed: {critical_issues}")
            raise ValueError("Invalid configuration")
    
    # Setup circuit breakers for external dependencies
    log.info("Setting up circuit breakers...")
    postgres_circuit = robustness_manager.get_circuit_breaker(
        "postgres",
        CircuitBreakerConfig(failure_threshold=3, timeout=30.0)
    )
    qdrant_circuit = robustness_manager.get_circuit_breaker(
        "qdrant",
        CircuitBreakerConfig(failure_threshold=3, timeout=30.0)
    )
    openrouter_circuit = robustness_manager.get_circuit_breaker(
        "openrouter",
        CircuitBreakerConfig(failure_threshold=5, timeout=60.0)
    )
    
    # Register health checks
    async def check_postgres():
        try:
            import psycopg2
            from ..utils.config import POSTGRES_DSN
            conn = psycopg2.connect(POSTGRES_DSN)
            conn.close()
            return True
        except Exception as e:
            log.error(f"PostgreSQL health check failed: {e}")
            return False
    
    async def check_qdrant():
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://{QDRANT_HOST}:{QDRANT_PORT}/", timeout=5.0)
                return response.status_code == 200
        except Exception as e:
            log.error(f"Qdrant health check failed: {e}")
            return False
    
    robustness_manager.register_health_check("postgres", check_postgres)
    robustness_manager.register_health_check("qdrant", check_qdrant)
    
    log.info("Initialising searcher and chainer…")
    searcher = AttackSearcher()
    chainer = AttackChainer(searcher)
    
    try:
        audit_engine = OpSecAuditEngine()
        log.info("OpSec audit engine ready.")
    except Exception as e:
        log.warning("OpSec audit engine unavailable: %s", e)
        audit_engine = None
    
    if JAILBREAK_API_KEY:
        try:
            analyst = ClaudeAnalyst(
                searcher,
                audit_engine=audit_engine,
                chainer=chainer,
            )
            log.info("Claude analyst ready.")
        except Exception as e:
            log.warning("Claude analyst unavailable: %s", e)
    else:
        log.warning("JAILBREAK_API_KEY not set — AI endpoints disabled.")
    
    # Initialize threat emulation service
    try:
        ml_service = get_ml_service()
        threat_emulation_service = get_threat_emulation_service(ml_service)
        log.info("Threat emulation service ready.")
    except Exception as e:
        log.warning("Threat emulation service unavailable: %s", e)
        threat_emulation_service = None
    
    log.info("Knowledge Engine ready.")
    
    # Setup graceful shutdown
    shutdown_manager = setup_graceful_shutdown_fastapi(
        app,
        service_name="knowledge-engine",
        timeout=30.0,
        on_shutdown=lambda: close_database_connection(searcher.pg)
    )
    app.state.shutdown_manager = shutdown_manager
    
    yield
    
    # Cleanup on shutdown
    log.info("Shutting down Knowledge Engine...")
    searcher.pg.close()
    log.info("Knowledge Engine shutdown complete")


app = FastAPI(
    title="Attack Knowledge Engine",
    description="Semantic search and attack vector generation from the Attack Dataset",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS with security best practices
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add error handling middleware
app.middleware("http")(create_error_handler_middleware("knowledge-engine"))

# ── Service Authentication Middleware ────────────────────────────────────────────

@app.middleware("http")
async def service_auth_middleware(request: Request, call_next):
    """
    Middleware to handle service-to-service authentication.
    Sets request.state.service_authenticated if valid service credentials are provided.
    """
    # Check for service authentication headers
    service_token = request.headers.get("X-Service-API-Key")
    service_name = request.headers.get("X-Service-Name")
    
    if service_token and service_name:
        # Verify service credentials
        if verify_service_token(service_token, service_name):
            request.state.service_authenticated = True
        else:
            request.state.service_authenticated = False
    else:
        request.state.service_authenticated = False
    
    # Continue processing the request
    response = await call_next(request)
    return response

# ── API Endpoints ────────────────────────────────────────────────────────────────

# ── Authentication Dependencies ───────────────────────────────────────────────

async def get_current_user_or_service(request: Request):
    """
    Dependency that returns the current user if authenticated via JWT,
    or allows the request if authenticated via service API key.
    
    Returns User object for JWT auth, or None for service auth (but allows request).
    Raises HTTPException if neither authentication method is valid.
    """
    # Check if service authentication succeeded
    if getattr(request.state, 'service_authenticated', False):
        # Service authentication is valid, allow request
        return None
    
    # Fall back to user authentication
    # Extract Authorization header manually for user auth
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )
    
    # Verify JWT token
    from shared.auth import decode_token, verify_token
    token = auth_header.replace("Bearer ", "")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )
    
    user_id = payload.get("sub")
    username = payload.get("username")
    email = payload.get("email")
    role = payload.get("role")
    
    if not all([user_id, username, role]):
        raise HTTPException(
            status_code=401,
            detail="Invalid token payload"
        )
    
    return User(
        id=user_id,
        username=username,
        email=email or "",
        role=role,
        is_active=payload.get("is_active", True)
    )


def require_permission_or_service_factory(permission: str):
    """
    Factory function to create a dependency that requires a specific permission for user auth,
    or allows the request if authenticated via service API key.
    """
    async def dependency(request: Request):
        # Check if service authentication succeeded
        if getattr(request.state, 'service_authenticated', False):
            # Service authentication is valid, allow request
            return None
        
        # Fall back to user authentication with permission check
        current_user = await get_current_user_or_service(request)
        if not current_user.can_perform_action(permission):
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions"
            )
        
        return current_user
    
    return dependency


# ── Health & Status Endpoints ───────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    components: Dict[str, Any]


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Enhanced health check endpoint for monitoring.
    Returns status of all system components including circuit breakers and dependency health.
    """
    from datetime import datetime
    import psycopg2
    from ..utils.config import POSTGRES_DSN
    
    components = {
        "api": {"status": "healthy", "details": "Knowledge Engine API running"},
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }
    
    # Get comprehensive health report from robustness manager
    health_report = await robustness_manager.get_health_report()
    components["robustness"] = {
        "overall_status": health_report["overall_status"],
        "health_checks": health_report["health_checks"],
        "circuit_breakers": health_report["circuit_breakers"]
    }
    
    # Check embedding model status
    try:
        if searcher and hasattr(searcher, 'model') and searcher.model:
            components["embedding_model"] = {
                "status": "healthy",
                "details": f"Model {EMBEDDING_MODEL} loaded successfully"
            }
        else:
            components["embedding_model"] = {
                "status": "unhealthy",
                "details": "Embedding model not loaded"
            }
    except Exception as e:
        components["embedding_model"] = {"status": "unhealthy", "details": str(e)}
    
    # Check ML service status
    try:
        ml = get_ml_service()
        if ml and ml.models:
            components["ml_service"] = {
                "status": "healthy",
                "details": f"ML service loaded with {len(ml.models)} model(s)"
            }
        else:
            components["ml_service"] = {"status": "unhealthy", "details": "ML service not available"}
    except Exception as e:
        components["ml_service"] = {"status": "unhealthy", "details": str(e)}
    
    # Determine overall status based on robustness report
    overall_status = health_report["overall_status"]
    
    return HealthResponse(
        status=overall_status,
        timestamp=components["timestamp"],
        version=components["version"],
        components=components
    )


@app.get("/robustness")
async def get_robustness_metrics():
    """
    Get detailed robustness metrics including circuit breaker status and error logs.
    """
    health_report = await robustness_manager.get_health_report()
    recent_errors = error_handler.get_recent_errors(limit=20)
    
    return {
        "health_report": health_report,
        "recent_errors": recent_errors,
        "error_log_size": len(error_handler.error_log)
    }


@app.post("/robustness/errors/clear")
async def clear_error_logs():
    """Clear error logs (admin only)."""
    error_handler.clear_error_log()
    return {"message": "Error logs cleared"}


# ── Authentication Endpoints ───────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


class UserCreateRequest(BaseModel):
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    password: str = Field(..., description="Password")
    role: str = Field("analyst", description="User role")


class UserUpdateRequest(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: Optional[str] = None


@app.post("/auth/login", response_model=TokenResponse)
def login(request: LoginRequest):
    """
    Authenticate user and return JWT tokens.
    
    Default credentials (CHANGE IN PRODUCTION):
    - admin / admin123 (admin role)
    - operator / operator123 (operator role)
    """
    try:
        tokens = auth_service.login(request.username, request.password)
        return TokenResponse(**tokens)
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=str(e)
        )


@app.post("/auth/refresh", response_model=TokenResponse)
def refresh_token(request: RefreshTokenRequest):
    """Refresh access token using refresh token."""
    try:
        tokens = auth_service.refresh_token(request.refresh_token)
        return TokenResponse(**tokens)
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=str(e)
        )


@app.get("/auth/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user_or_service)):
    """Get current authenticated user information."""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat() if current_user.created_at else None
    )


@app.post("/auth/users", response_model=UserResponse)
def create_user(
    request: UserCreateRequest,
    current_user: User = Depends(require_role(Role.ADMIN))
):
    """Create a new user (admin only)."""
    try:
        user = user_store.create_user(
            username=request.username,
            email=request.email,
            password=request.password,
            role=request.role
        )
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else None
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/auth/users", response_model=List[UserResponse])
def list_users(
    role: Optional[str] = None,
    current_user: User = Depends(require_role(Role.ADMIN))
):
    """List all users (admin only)."""
    users = user_store.list_users(role=role)
    return [
        UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else None
        )
        for user in users
    ]


@app.put("/auth/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    request: UserUpdateRequest,
    current_user: User = Depends(require_role(Role.ADMIN))
):
    """Update user information (admin only)."""
    user = user_store.update_user(
        user_id=user_id,
        email=request.email,
        role=request.role,
        is_active=request.is_active
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat() if user.created_at else None
    )


@app.delete("/auth/users/{user_id}")
def delete_user(
    user_id: str,
    current_user: User = Depends(require_role(Role.ADMIN))
):
    """Delete a user (admin only)."""
    if not user_store.delete_user(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully"}


# ── Search ────────────────────────────────────────────────────────────────────

@app.post("/search", response_model=SearchResponse)
def search(
    query: SearchQuery,
    current_user: Optional[User] = Depends(get_current_user_or_service)
):
    """
    Semantic search over the attack knowledge base.
    Supply a natural-language description of a target, service, vulnerability,
    or attack technique. Returns ranked attack records with similarity scores.
    
    Requires authentication (analyst role or higher) or service authentication.
    """
    # Check permissions (only for user auth, service auth skips this)
    if current_user and not current_user.can_perform_action("search_knowledge"):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions"
        )
    
    return searcher.semantic_search(
        query=query.query,
        top_k=query.top_k,
        category=query.category_filter,
        attack_type=query.attack_type_filter,
        mitre=query.mitre_filter,
    )


@app.get("/search/keyword", response_model=List[AttackRecord])
def keyword_search(
    q: str = Query(..., description="Keyword or phrase"),
    limit: int = Query(20, ge=1, le=100),
):
    return searcher.keyword_search(q, limit=limit)


# ── MITRE ─────────────────────────────────────────────────────────────────────

@app.get("/mitre/{technique_id}", response_model=List[AttackRecord])
def get_by_mitre(technique_id: str, limit: int = 20):
    results = searcher.get_by_mitre(technique_id, limit=limit)
    if not results:
        raise HTTPException(status_code=404, detail="No attacks found for that technique")
    return results


@app.get("/mitre", response_model=List[Dict[str, Any]])
def list_mitre():
    return searcher.list_mitre_techniques()


# ── Category ──────────────────────────────────────────────────────────────────

@app.get("/categories", response_model=List[Dict[str, Any]])
def list_categories():
    return searcher.list_categories()


@app.get("/categories/{category}", response_model=List[AttackRecord])
def get_by_category(category: str, limit: int = 50):
    return searcher.get_by_category(category, limit=limit)


# ── Target ────────────────────────────────────────────────────────────────────

@app.get("/targets/{target_type}", response_model=List[AttackRecord])
def get_by_target(target_type: str, limit: int = 30):
    return searcher.get_by_target(target_type, limit=limit)


# ── Tools ─────────────────────────────────────────────────────────────────────

@app.get("/tools", response_model=List[Dict[str, Any]])
def list_tools():
    return searcher.list_tools()


# ── Attack Vector Builder ─────────────────────────────────────────────────────

@app.post("/attack-vector", response_model=AttackVectorResponse)
def build_attack_vector(
    request: AttackVectorRequest,
    current_user: Optional[User] = Depends(require_permission_or_service_factory("search_knowledge"))
):
    """
    Given a target context (description, detected services, OS),
    generate multi-stage ranked attack chains with OpSec notes.
    
    Requires authentication (analyst role or higher) or service authentication.
    """
    return chainer.build_chains(request)


@app.post("/attack-vector/live-replan", response_model=LiveReplanResponse)
def build_live_attack_replan(
    request: LiveReplanRequest,
    current_user: Optional[User] = Depends(require_permission_or_service_factory("search_knowledge"))
):
    """
    Replan attack chains during live execution using the attack database
    (semantic search) and trained ML re-ranking, enriched with step results.
    """
    return chainer.build_live_replan(request)


# ── OpSec ─────────────────────────────────────────────────────────────────────

@app.get("/opsec/{attack_id}", response_model=OpsecNote)
def get_opsec_note(attack_id: int):
    """
    Retrieve OpSec/evasion notes for a specific attack record.
    """
    note = chainer.get_opsec_note(attack_id)
    if not note:
        raise HTTPException(status_code=404, detail="Attack record not found")
    return note


# ── AI (Claude) ───────────────────────────────────────────────────────────────

def _require_analyst():
    if analyst is None:
        raise HTTPException(
            status_code=503,
            detail="AI analyst unavailable — check JAILBREAK_API_KEY in .env",
        )
    return analyst


class EngagementAnalysisRequest(BaseModel):
    target: str
    chains: List[Dict[str, Any]] = Field(default_factory=list)
    opsec_report: Optional[Dict[str, Any]] = None
    scan_fingerprint: Optional[Dict[str, Any]] = None


class ChainAnalysisRequest(BaseModel):
    chain: Dict[str, Any]


class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    question: str
    history: List[ChatMessage] = Field(default_factory=list)
    engagement_context: Optional[Dict[str, Any]] = None
    stream: bool = True
    allow_tools: bool = True
    execution_mode: str = "single_agent"
    swarm_max_steps: int = Field(default=12, ge=1, le=50)


# ── OpSec Audit Models ─────────────────────────────────────────────────────────

class OpSecAuditRequest(BaseModel):
    chain_id: str
    chain_description: str
    steps: List[str]


class ToolRecommendationRequest(BaseModel):
    tool_name: str


@app.post("/ai/analyse/engagement")
def ai_analyse_engagement(
    request: EngagementAnalysisRequest,
    current_user: Optional[User] = Depends(require_permission_or_service_factory("use_ai_chat")),
):
    """
    Full engagement narrative analysis via Claude.
    Synthesises target fingerprint, attack chains, and OpSec report
    into an actionable intelligence report.
    
    Requires authentication (operator role or higher).
    """
    a = _require_analyst()
    report = a.analyse_engagement(
        target=request.target,
        chains=request.chains,
        opsec_report=request.opsec_report,
        scan_fingerprint=request.scan_fingerprint,
    )
    return {"report": report}


@app.post("/ai/analyse/chain")
def ai_analyse_chain(
    request: ChainAnalysisRequest,
    current_user: Optional[User] = Depends(require_permission_or_service_factory("use_ai_chat")),
):
    """
    Deep-dive analysis of a single attack chain via Claude.
    Returns phase-by-phase breakdown, tool recommendations,
    detection points, and OpSec hardening advice.
    
    Requires authentication (operator role or higher).
    """
    a = _require_analyst()
    report = a.analyse_chain(request.chain)
    return {"report": report}


@app.post("/ai/chat")
async def ai_chat(
    request: ChatRequest,
    current_user: Optional[User] = Depends(require_permission_or_service_factory("use_ai_chat")),
):
    """
    RAG-grounded chat with Claude.
    Retrieves relevant attack records from the knowledge base,
    injects them as context, then streams or returns Claude's response.
    
    Requires authentication (operator role or higher).
    """
    a = _require_analyst()
    history = [{"role": m.role, "content": m.content} for m in request.history]

    if request.stream:
        async def _event_stream():
            async for chunk in a.chat_stream(
                question=request.question,
                history=history,
                engagement_context=request.engagement_context,
                allow_tools=request.allow_tools,
                execution_mode=request.execution_mode,
                swarm_max_steps=request.swarm_max_steps,
            ):
                # Server-Sent Events format
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            _event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        answer = a.chat_sync(
            question=request.question,
            history=history,
            engagement_context=request.engagement_context,
            allow_tools=request.allow_tools,
            execution_mode=request.execution_mode,
            swarm_max_steps=request.swarm_max_steps,
        )
        return {"answer": answer}


@app.get("/ai/status")
def ai_status():
    """Check whether the AI analyst is available."""
    return {
        "available": analyst is not None,
        "model": OPENROUTER_MODEL if analyst else None,
        "provider": "OpenRouter" if analyst else None
    }


# ── OpSec Audit ─────────────────────────────────────────────────────────────────

def _require_audit_engine():
    if audit_engine is None:
        raise HTTPException(
            status_code=503,
            detail="OpSec audit engine unavailable — check tool_reference.json",
        )
    return audit_engine


@app.post("/opsec/audit")
def audit_chain(request: OpSecAuditRequest):
    """
    Audit an attack chain for OpSec risks.
    Returns detectability score, risk analysis per step, tool substitutions,
    and evasion recommendations.
    """
    engine = _require_audit_engine()
    result = engine.audit_chain(
        chain_id=request.chain_id,
        chain_description=request.chain_description,
        steps=request.steps
    )
    return {
        "chain_id": result.chain_id,
        "chain_description": result.chain_description,
        "overall_risk_score": result.overall_risk_score,
        "overall_risk_level": result.overall_risk_level.value,
        "step_risks": [
            {
                "step_index": sr.step_index,
                "step_description": sr.step_description,
                "tools_found": sr.tools_found,
                "tool_risks": [
                    {
                        "tool_name": tr.tool_name,
                        "risk_level": tr.risk_level.value,
                        "risk_factors": tr.risk_factors,
                        "detection_methods": tr.detection_methods,
                        "opsec_recommendations": tr.opsec_recommendations,
                        "substitution_alternative": tr.substitution_alternative
                    }
                    for tr in sr.tool_risks
                ],
                "overall_risk": sr.overall_risk.value,
                "recommendations": sr.recommendations
            }
            for sr in result.step_risks
        ],
        "critical_findings": result.critical_findings,
        "tool_substitutions": result.tool_substitutions,
        "evasive_techniques": result.evasive_techniques,
        "detection_coverage": result.detection_coverage
    }


@app.post("/opsec/audit/vector")
def audit_attack_vector(attack_vector: Dict[str, Any]):
    """
    Audit an attack vector from the knowledge engine for OpSec risks.
    """
    engine = _require_audit_engine()
    result = engine.audit_attack_vector(attack_vector)
    return {
        "chain_id": result.chain_id,
        "chain_description": result.chain_description,
        "overall_risk_score": result.overall_risk_score,
        "overall_risk_level": result.overall_risk_level.value,
        "step_risks": [
            {
                "step_index": sr.step_index,
                "step_description": sr.step_description,
                "tools_found": sr.tools_found,
                "tool_risks": [
                    {
                        "tool_name": tr.tool_name,
                        "risk_level": tr.risk_level.value,
                        "risk_factors": tr.risk_factors,
                        "detection_methods": tr.detection_methods,
                        "opsec_recommendations": tr.opsec_recommendations,
                        "substitution_alternative": tr.substitution_alternative
                    }
                    for tr in sr.tool_risks
                ],
                "overall_risk": sr.overall_risk.value,
                "recommendations": sr.recommendations
            }
            for sr in result.step_risks
        ],
        "critical_findings": result.critical_findings,
        "tool_substitutions": result.tool_substitutions,
        "evasive_techniques": result.evasive_techniques,
        "detection_coverage": result.detection_coverage
    }


@app.post("/opsec/tool/{tool_name}")
def get_tool_recommendations(tool_name: str):
    """
    Get OpSec recommendations for a specific tool.
    Returns risk level, detection methods, and best practices.
    """
    engine = _require_audit_engine()
    recommendations = engine.get_tool_recommendations(tool_name)
    return recommendations


# ── ML Prediction Endpoints ─────────────────────────────────────────────────────

@app.get("/ml/models", response_model=MLModelsResponse)
def get_available_models():
    """
    Get information about available ML models for attack pattern classification.
    Returns model types, accuracy metrics, and available targets.
    """
    ml_service = get_ml_service()
    models_info = ml_service.get_available_models()
    available_targets = list(ml_service.models.keys())
    
    return MLModelsResponse(
        models=models_info,
        available_targets=available_targets
    )


@app.get("/ml/models/{target_name}", response_model=MLModelInfo)
def get_model_info(target_name: str):
    """
    Get detailed information about a specific ML model.
    Includes accuracy, number of classes, and training metadata.
    """
    ml_service = get_ml_service()
    model_info = ml_service.get_model_info(target_name)
    
    if model_info is None:
        raise HTTPException(status_code=404, detail=f"Model '{target_name}' not found")
    
    return MLModelInfo(**model_info)


@app.post("/ml/predict", response_model=MLPredictResponse)
def predict_attack_pattern(request: MLPredictRequest):
    """
    Classify an attack pattern description using trained ML models.
    Returns predicted categories with confidence scores.
    
    Example:
    - text: "SQL injection attack on login form"
    - target: "category" (or "attack_type", "mitre_technique")
    - top_k: 3 (number of predictions to return)
    """
    ml_service = get_ml_service()
    
    try:
        predictions = ml_service.predict(
            target_name=request.target,
            text=request.text,
            top_k=request.top_k
        )
        
        return MLPredictResponse(
            text=request.text,
            target=request.target,
            predictions=[MLPrediction(**pred) for pred in predictions]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@app.post("/ml/batch-predict")
def batch_predict_attack_patterns(request: MLBatchPredictRequest):
    """
    Classify multiple attack pattern descriptions in a single request.
    Useful for bulk analysis and batch processing.
    """
    ml_service = get_ml_service()
    
    try:
        batch_predictions = ml_service.batch_predict(
            target_name=request.target,
            texts=request.texts,
            top_k=request.top_k
        )
        
        results = []
        for i, predictions in enumerate(batch_predictions):
            results.append({
                "text": request.texts[i],
                "target": request.target,
                "predictions": predictions
            })
        
        return {
            "results": results,
            "total": len(results)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch prediction failed: {str(e)}")


@app.get("/ml/status")
def get_ml_status():
    """
    Get the status of the ML service.
    Returns whether models are loaded and available for predictions.
    """
    ml_service = get_ml_service()
    
    return {
        "status": "available" if ml_service.models else "unavailable",
        "models_loaded": len(ml_service.models),
        "available_targets": list(ml_service.models.keys()),
        "models_directory": str(ml_service.models_dir)
    }


# ── Threat Emulation Models ─────────────────────────────────────────────────────

class ThreatEmulationRequest(BaseModel):
    """Request model for threat emulation plan generation."""
    target: str = Field(..., description="Target system or network")
    target_description: str = Field(..., description="Description of the target environment")
    threat_actor_id: Optional[str] = Field(None, description="Optional specific threat actor to emulate")


class ThreatEmulationResponse(BaseModel):
    """Response model for threat emulation plan."""
    target: str
    threat_actor: Dict[str, Any]
    ml_category: str
    ml_confidence: float
    attack_phases: List[Dict[str, Any]]
    recommended_tools: List[str]
    jailbreak_payload: Optional[Dict[str, Any]] = None


class ThreatActorListResponse(BaseModel):
    """Response model for listing available threat actor profiles."""
    threat_actors: List[Dict[str, Any]]


# ── Threat Emulation Endpoints ─────────────────────────────────────────────────

@app.get("/threat-emulation/actors", response_model=ThreatActorListResponse)
async def list_threat_actors():
    """List available threat actor profiles for emulation."""
    if not threat_emulation_service:
        raise HTTPException(status_code=503, detail="Threat emulation service unavailable")
    
    actors = []
    for actor_id, profile in threat_emulation_service.THREAT_ACTOR_PROFILES.items():
        actors.append({
            "id": actor_id,
            "name": profile.name,
            "type": profile.actor_type.value,
            "aggression_level": profile.aggression_level,
            "stealth_level": profile.stealth_level,
            "description": profile.description
        })
    
    return {"threat_actors": actors}


@app.post("/threat-emulation/generate-plan", response_model=ThreatEmulationResponse)
async def generate_emulation_plan(request: ThreatEmulationRequest):
    """Generate a threat emulation plan using ML classification and threat actor profiles."""
    if not threat_emulation_service:
        raise HTTPException(status_code=503, detail="Threat emulation service unavailable")
    
    try:
        # Generate emulation plan
        plan = threat_emulation_service.generate_emulation_plan(
            target=request.target,
            target_description=request.target_description,
            threat_actor_id=request.threat_actor_id
        )
        
        # Generate jailbreak.ai payload
        jailbreak_payload = threat_emulation_service.generate_jailbreak_payload(plan)
        
        # Convert threat actor profile to dict
        threat_actor_dict = {
            "name": plan.threat_actor.name,
            "type": plan.threat_actor.actor_type.value,
            "aggression_level": plan.threat_actor.aggression_level,
            "stealth_level": plan.threat_actor.stealth_level,
            "persistence_level": plan.threat_actor.persistence_level,
            "common_tools": plan.threat_actor.common_tools,
            "mitre_tactics": plan.threat_actor.mitre_tactics,
            "description": plan.threat_actor.description
        }
        
        return ThreatEmulationResponse(
            target=plan.target,
            threat_actor=threat_actor_dict,
            ml_category=plan.ml_category,
            ml_confidence=plan.ml_confidence,
            attack_phases=plan.attack_phases,
            recommended_tools=plan.recommended_tools,
            jailbreak_payload=jailbreak_payload
        )
        
    except Exception as e:
        logger.error(f"Emulation plan generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Plan generation failed: {str(e)}")


@app.post("/threat-emulation/classify-context")
async def classify_target_context(request: Dict[str, str]):
    """Classify target context using ML to predict likely attack categories."""
    if not threat_emulation_service:
        raise HTTPException(status_code=503, detail="Threat emulation service unavailable")
    
    target_description = request.get("target_description", "")
    if not target_description:
        raise HTTPException(status_code=400, detail="target_description is required")
    
    try:
        classification = threat_emulation_service.classify_target_context(target_description)
        return classification
    except Exception as e:
        logger.error(f"Context classification failed: {e}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")


@app.post("/threat-emulation/execute")
async def execute_emulation_plan(request: Dict[str, Any]):
    """
    Execute a threat emulation plan by generating it and sending to Integration Hub.
    
    This endpoint:
    1. Generates a threat emulation plan using ML classification
    2. Executes the jailbreak.ai payload via Integration Hub
    3. Returns the execution results
    """
    if not threat_emulation_service:
        raise HTTPException(status_code=503, detail="Threat emulation service unavailable")
    
    try:
        target = request.get("target")
        target_description = request.get("target_description", "")
        threat_actor_id = request.get("threat_actor_id")
        
        if not target:
            raise HTTPException(status_code=400, detail="target is required")
        
        # Generate emulation plan
        plan = threat_emulation_service.generate_emulation_plan(
            target=target,
            target_description=target_description,
            threat_actor_id=threat_actor_id
        )
        
        # Generate jailbreak.ai payload
        jailbreak_payload = threat_emulation_service.generate_jailbreak_payload(plan)

        execution_status = "plan_generated"
        hub_result = None
        hub_url = os.getenv("INTEGRATION_HUB_URL", "http://localhost:8500")
        via_hub = os.getenv("JAILBREAK_VIA_HUB", "true").lower() not in ("false", "0", "no")
        if via_hub or os.getenv("JAILBREAK_API_KEY"):
            try:
                import httpx
                hub_headers = {}
                hub_key = os.getenv("SERVICE_API_KEY_INTEGRATION_HUB", "")
                if hub_key:
                    hub_headers["X-Service-API-Key"] = hub_key
                    hub_headers["X-Service-Name"] = "knowledge-engine"
                async with httpx.AsyncClient(timeout=120.0) as client:
                    hub_resp = await client.post(
                        f"{hub_url.rstrip('/')}/integrations/execute",
                        json={
                            "plugin_name": "jailbreak_ai",
                            "engagement_id": request.get("engagement_id", "threat-emulation"),
                            "target": target,
                            "parameters": jailbreak_payload,
                            "timeout": 300,
                        },
                        headers=hub_headers,
                    )
                    if hub_resp.status_code == 200:
                        hub_result = hub_resp.json()
                        execution_status = (
                            "hub_executed" if hub_result.get("success") else "hub_failed"
                        )
                    else:
                        execution_status = f"hub_http_{hub_resp.status_code}"
            except Exception as hub_err:
                logger.warning("Threat emulation hub execution failed: %s", hub_err)
                execution_status = "hub_unavailable"

        # Convert threat actor profile to dict
        threat_actor_dict = {
            "name": plan.threat_actor.name,
            "type": plan.threat_actor.actor_type.value,
            "aggression_level": plan.threat_actor.aggression_level,
            "stealth_level": plan.threat_actor.stealth_level,
            "persistence_level": plan.threat_actor.persistence_level,
            "common_tools": plan.threat_actor.common_tools,
            "mitre_tactics": plan.threat_actor.mitre_tactics,
            "description": plan.threat_actor.description
        }
        
        return {
            "target": plan.target,
            "threat_actor": threat_actor_dict,
            "ml_category": plan.ml_category,
            "ml_confidence": plan.ml_confidence,
            "attack_phases": plan.attack_phases,
            "recommended_tools": plan.recommended_tools,
            "jailbreak_payload": jailbreak_payload,
            "execution_status": execution_status,
            "hub_result": hub_result,
        }
        
    except Exception as e:
        logger.error(f"Emulation execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


# ── Run directly ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host=API_HOST, port=API_PORT, reload=True)
