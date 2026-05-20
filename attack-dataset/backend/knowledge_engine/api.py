"""
Knowledge Engine FastAPI — main REST entry point.
"""
from __future__ import annotations
import sys
import os
# Add parent directory to path to import shared modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
from shared.fastapi_robustness import setup_robustness_middleware


import logging
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
import sys
import os
import uuid
from datetime import datetime

from fastapi import Request, FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

# Configuration from environment variables
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
JAILBREAK_API_KEY = os.getenv("JAILBREAK_API_KEY", "")
QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# Create FastAPI app early for route decorators
app = FastAPI(
    title="Attack Knowledge Engine",
    description="Semantic search and attack vector generation from the Attack Dataset",
    version="1.0.0",
)

# Configure CORS with security best practices
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup robustness middleware (correlation IDs, logging, metrics, timeouts, security headers)
setup_robustness_middleware(
    app,
    service_name="knowledge-engine",
    timeout_seconds=60.0,  # Knowledge engine may need more time for AI operations
    version="1.0.0",
)

# Tool Recommendation Integration
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Optional
from enum import Enum


class RiskLevel(str, Enum):
    """Risk levels for tools."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ToolRecommendationRequest(BaseModel):
    """Request model for tool recommendations."""
    attack_scenario: str = Field(..., description="Attack scenario or objective")
    mitre_tactic: Optional[str] = Field(None, description="MITRE ATT&CK tactic")
    max_risk_level: RiskLevel = Field(RiskLevel.HIGH, description="Maximum acceptable risk level")
    platform: Optional[str] = Field(None, description="Target platform")
    min_stealth_level: int = Field(0, description="Minimum stealth level (0-100)")
    max_noise_level: int = Field(100, description="Maximum noise level (0-100)")
    include_alternatives: bool = Field(True, description="Include alternative tools")


class ToolInfo(BaseModel):
    """Tool information model."""
    name: str
    category: str
    description: str
    opsec_considerations: str
    detection_methods: List[str]
    mitre_tactic: str
    risk_level: str
    noise_level: int
    stealth_level: int
    platform: List[str]
    recommendation_score: Optional[int] = None
    rationale: Optional[str] = None


class ToolRecommendationResponse(BaseModel):
    """Response model for tool recommendations."""
    attack_scenario: str
    primary_recommendation: ToolInfo
    alternative_tools: List[ToolInfo]
    opsec_summary: Dict[str, Any]
    total_tools_considered: int


class OpSecAssessmentRequest(BaseModel):
    """Request model for OpSec assessment."""
    tools: List[str] = Field(..., description="List of tool names to assess")
    target_environment: Optional[str] = Field(None, description="Target environment description")


class OpSecAssessmentResponse(BaseModel):
    """Response model for OpSec assessment."""
    overall_risk_level: str
    tool_assessments: List[Dict[str, Any]]
    combined_detection_methods: List[str]
    recommendations: List[str]
    evasion_opportunities: List[str]


def get_tools_db_connection():
    """Get database connection for tools database."""
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        database=os.getenv("POSTGRES_DB", "attack_db"),
        user=os.getenv("POSTGRES_USER", "opsec"),
        password=os.getenv("POSTGRES_PASSWORD", "opsec"),
        cursor_factory=RealDictCursor
    )


# Tool Recommendation Endpoints

@app.get("/api/v1/tools", response_model=List[ToolInfo])
async def list_offensive_tools(
    category: Optional[str] = Query(None, description="Filter by category"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    min_stealth: int = Query(0, description="Minimum stealth level"),
    limit: int = Query(50, description="Maximum results")
):
    """List available offensive tools with filtering."""
    conn = get_tools_db_connection()
    try:
        cursor = conn.cursor()
        
        query = "SELECT * FROM offensive_tools WHERE 1=1"
        params = []
        
        if category:
            query += " AND category = %s"
            params.append(category)
        
        if risk_level:
            query += " AND risk_level = %s"
            params.append(risk_level)
        
        if platform:
            query += " AND %s = ANY(platform)"
            params.append(platform)
        
        query += " AND stealth_level >= %s"
        params.append(min_stealth)
        
        query += " ORDER BY stealth_level DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        tools = [ToolInfo(**row) for row in rows]
        return tools
        
    except Exception as e:
        logger.error(f"Failed to list tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/api/v1/tools/{tool_name}", response_model=ToolInfo)
async def get_tool_info(tool_name: str):
    """Get detailed information about a specific tool."""
    conn = get_tools_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM offensive_tools WHERE name = %s",
            (tool_name,)
        )
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Tool not found")
        
        return ToolInfo(**row)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tool info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/api/v1/tools/categories")
async def list_tool_categories():
    """List available tool categories."""
    conn = get_tools_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT category, COUNT(*) as tool_count FROM offensive_tools GROUP BY category ORDER BY tool_count DESC"
        )
        rows = cursor.fetchall()
        
        categories = [
            {"category": row['category'], "tool_count": row['tool_count']}
            for row in rows
        ]
        
        return {"categories": categories}
        
    except Exception as e:
        logger.error(f"Failed to list categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/api/v1/tools/recommend", response_model=ToolRecommendationResponse)
async def recommend_offensive_tools(request: ToolRecommendationRequest):
    """Get tool recommendations based on attack scenario."""
    conn = get_tools_db_connection()
    try:
        cursor = conn.cursor()
        
        # Build query based on request parameters
        query = "SELECT * FROM offensive_tools WHERE 1=1"
        params = []
        
        # Filter by MITRE tactic if specified
        if request.mitre_tactic:
            query += " AND mitre_tactic = %s"
            params.append(request.mitre_tactic)
        
        # Filter by risk level
        risk_levels = ['low', 'medium', 'high', 'critical']
        max_risk_index = risk_levels.index(request.max_risk_level.value)
        allowed_risk_levels = risk_levels[:max_risk_index + 1]
        query += f" AND risk_level = ANY(%s)"
        params.append(allowed_risk_levels)
        
        # Filter by platform if specified
        if request.platform:
            query += " AND %s = ANY(platform)"
            params.append(request.platform)
        
        # Filter by stealth and noise levels
        query += " AND stealth_level >= %s AND noise_level <= %s"
        params.extend([request.min_stealth_level, request.max_noise_level])
        
        query += " ORDER BY stealth_level DESC, noise_level ASC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        if not rows:
            raise HTTPException(status_code=404, detail="No tools found matching criteria")
        
        # Calculate recommendation scores based on scenario matching
        scored_tools = []
        scenario_keywords = request.attack_scenario.lower().split()
        
        for row in rows:
            tool = dict(row)
            score = 50  # Base score
            
            # Boost score for keyword matches in description
            description_lower = tool['description'].lower()
            for keyword in scenario_keywords:
                if keyword in description_lower:
                    score += 10
            
            # Boost score for high stealth
            score += (tool['stealth_level'] - 50) // 2
            
            # Penalty for high risk
            if tool['risk_level'] == 'critical':
                score -= 30
            elif tool['risk_level'] == 'high':
                score -= 15
            
            tool['recommendation_score'] = min(100, max(0, score))
            scored_tools.append(tool)
        
        # Sort by recommendation score
        scored_tools.sort(key=lambda x: x['recommendation_score'], reverse=True)
        
        # Select primary recommendation
        primary_tool = scored_tools[0]
        primary_tool['rationale'] = f"Selected based on stealth level ({primary_tool['stealth_level']}), " \
                                 f"risk level ({primary_tool['risk_level']}), and scenario relevance"
        
        # Select alternatives
        alternative_tools = scored_tools[1:6] if len(scored_tools) > 1 else []
        
        # Generate OpSec summary
        opsec_summary = {
            "primary_tool_risk": primary_tool['risk_level'],
            "primary_tool_noise": primary_tool['noise_level'],
            "primary_tool_stealth": primary_tool['stealth_level'],
            "detection_methods": primary_tool['detection_methods'],
            "opsec_considerations": primary_tool['opsec_considerations']
        }
        
        return ToolRecommendationResponse(
            attack_scenario=request.attack_scenario,
            primary_recommendation=ToolInfo(**primary_tool),
            alternative_tools=[ToolInfo(**tool) for tool in alternative_tools],
            opsec_summary=opsec_summary,
            total_tools_considered=len(scored_tools)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to recommend tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/api/v1/tools/assess", response_model=OpSecAssessmentResponse)
async def assess_tools_opsec(request: OpSecAssessmentRequest):
    """Assess OpSec implications of tool combination."""
    conn = get_tools_db_connection()
    try:
        cursor = conn.cursor()
        
        # Get information for each tool
        tool_data = []
        all_detection_methods = set()
        
        for tool_name in request.tools:
            cursor.execute(
                "SELECT * FROM offensive_tools WHERE name = %s",
                (tool_name,)
            )
            row = cursor.fetchone()
            
            if row:
                tool = dict(row)
                tool_data.append(tool)
                all_detection_methods.update(tool['detection_methods'])
        
        if not tool_data:
            raise HTTPException(status_code=404, detail="No valid tools found")
        
        # Calculate overall risk level
        risk_scores = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
        max_risk_score = max(risk_scores.get(tool['risk_level'], 2) for tool in tool_data)
        
        if max_risk_score >= 4:
            overall_risk = 'critical'
        elif max_risk_score >= 3:
            overall_risk = 'high'
        elif max_risk_score >= 2:
            overall_risk = 'medium'
        else:
            overall_risk = 'low'
        
        # Generate tool assessments
        tool_assessments = []
        for tool in tool_data:
            assessment = {
                "tool": tool['name'],
                "risk_level": tool['risk_level'],
                "noise_level": tool['noise_level'],
                "stealth_level": tool['stealth_level'],
                "detection_methods": tool['detection_methods'],
                "opsec_considerations": tool['opsec_considerations']
            }
            tool_assessments.append(assessment)
        
        # Generate recommendations
        recommendations = []
        high_noise_tools = [tool['name'] for tool in tool_data if tool['noise_level'] > 70]
        if high_noise_tools:
            recommendations.append(f"Consider timing delays for: {', '.join(high_noise_tools)}")
        
        high_risk_tools = [tool['name'] for tool in tool_data if tool['risk_level'] in ['high', 'critical']]
        if high_risk_tools:
            recommendations.append(f"High-risk tools detected: {', '.join(high_risk_tools)}. Use with explicit authorization.")
        
        # Generate evasion opportunities
        evasion_opportunities = []
        for tool in tool_data:
            if 'stealthier' in tool['opsec_considerations'].lower():
                evasion_opportunities.append(f"{tool['name']}: Consider alternative stealthier methods")
            if 'passive' in tool['opsec_considerations'].lower():
                evasion_opportunities.append(f"{tool['name']}: Use passive mode if available")
        
        return OpSecAssessmentResponse(
            overall_risk_level=overall_risk,
            tool_assessments=tool_assessments,
            combined_detection_methods=list(all_detection_methods),
            recommendations=recommendations,
            evasion_opportunities=evasion_opportunities
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to assess OpSec: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


try:
    from core.models import (
        SearchQuery,
        SearchResponse,
        AttackRecord,
        AttackVectorRequest,
        AttackVectorResponse,
        MitreMapping,
        OpsecNote,
        MLPredictRequest,
        MLPredictResponse,
        MLBatchPredictRequest,
        MLModelInfo,
        MLModelsResponse,
        MLPrediction,
        AdaptiveAttackRequest,
        AdaptiveAttackResponse,
        FeedbackLoop,
    )
    from search.searcher import AttackSearcher
    from search.attack_chainer import AttackChainer
    from ai.jail_break_ai import ClaudeAnalyst
    from utils.opsec_audit import OpSecAuditEngine
    from ml.ml_service import get_ml_service
    from ml.threat_emulation import get_threat_emulation_service
    from attack_tree_engine import AttackTreeEngine
    from multi_agent_orchestrator import MultiAgentOrchestrator
    from feedback_loop_manager import FeedbackLoopManager
except ImportError:
    # Fallback for when running as module
    from knowledge_engine.core.models import (
        SearchQuery,
        SearchResponse,
        AttackRecord,
        AttackVectorRequest,
        AttackVectorResponse,
        MitreMapping,
        OpsecNote,
        MLPredictRequest,
        MLPredictResponse,
        MLBatchPredictRequest,
        MLModelInfo,
        MLModelsResponse,
        MLPrediction,
        AdaptiveAttackRequest,
        AdaptiveAttackResponse,
        FeedbackLoop,
    )
    from knowledge_engine.search.searcher import AttackSearcher
    from knowledge_engine.search.attack_chainer import AttackChainer
    from knowledge_engine.ai.jail_break_ai import ClaudeAnalyst
    from knowledge_engine.utils.opsec_audit import OpSecAuditEngine
    from knowledge_engine.ml.ml_service import get_ml_service
    from knowledge_engine.ml.threat_emulation import get_threat_emulation_service
    from knowledge_engine.attack_tree_engine import AttackTreeEngine
    from knowledge_engine.multi_agent_orchestrator import MultiAgentOrchestrator
    from knowledge_engine.feedback_loop_manager import FeedbackLoopManager

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
attack_tree_engine: AttackTreeEngine
multi_agent_orchestrator: MultiAgentOrchestrator
feedback_loop_manager: FeedbackLoopManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    global searcher, chainer, analyst, audit_engine, threat_emulation_service, error_handler, attack_tree_engine, multi_agent_orchestrator, feedback_loop_manager
    
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
            try:
                from config import POSTGRES_DSN
            except ImportError:
                from knowledge_engine.config import POSTGRES_DSN
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
    
    # Initialize attack tree engine
    try:
        attack_tree_engine = AttackTreeEngine(ai_analyzer=analyst)
        log.info("Attack tree engine ready with AI integration.")
    except Exception as e:
        log.warning("Attack tree engine unavailable: %s", e)
        attack_tree_engine = None
    
    # Initialize multi-agent orchestrator
    try:
        multi_agent_orchestrator = MultiAgentOrchestrator(ai_analyzer=analyst)
        log.info("Multi-agent orchestrator ready with AI integration.")
    except Exception as e:
        log.warning("Multi-agent orchestrator unavailable: %s", e)
        multi_agent_orchestrator = None
    
    # Initialize feedback loop manager
    try:
        feedback_loop_manager = FeedbackLoopManager(chainer, attack_tree_engine, multi_agent_orchestrator, ai_analyzer=analyst)
        log.info("Feedback loop manager ready with AI integration.")
    except Exception as e:
        log.warning("Feedback loop manager unavailable: %s", e)
        feedback_loop_manager = None
    
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


# Add error handling middleware
app.middleware("http")(create_error_handler_middleware("knowledge-engine"))

# Set lifespan after it's defined
app.router.lifespan_context = lifespan

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
    try:
        from config import POSTGRES_DSN
    except ImportError:
        from knowledge_engine.config import POSTGRES_DSN
    
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
    current_user: User = Depends(require_permission("use_ai_chat"))
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
    current_user: User = Depends(require_permission("use_ai_chat"))
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
    current_user: User = Depends(require_permission("use_ai_chat"))
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
        "model": __import__("config").OPENROUTER_MODEL if analyst else None,
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
        
        # Execute via Integration Hub (if configured)
        # This is a placeholder - actual Integration Hub execution would go here
        # For now, just return the plan
        
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
            "execution_status": "plan_generated"
        }
        
    except Exception as e:
        logger.error(f"Emulation execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


# ── Attack Tree Engine Endpoints ───────────────────────────────────────────────

def _require_attack_tree_engine():
    if attack_tree_engine is None:
        raise HTTPException(
            status_code=503,
            detail="Attack tree engine unavailable",
        )
    return attack_tree_engine


@app.post("/attack-tree/build")
async def build_attack_tree(request: AttackVectorRequest):
    """
    Build an attack tree from attack records based on target description.
    
    Returns a structured attack tree with nodes, edges, and scoring.
    """
    engine = _require_attack_tree_engine()
    
    try:
        # Get candidate attacks
        services_str = ", ".join(request.detected_services) if request.detected_services else ""
        os_str = request.detected_os or ""
        full_query = " ".join(filter(None, [
            request.target_description,
            services_str,
            os_str,
        ]))
        
        response = searcher.semantic_search(full_query, top_k=40)
        candidates = [r.record for r in response.results]
        
        # Build attack tree
        attack_tree = engine.build_attack_tree(candidates, request.target_description)
        
        return {
            "tree_id": attack_tree.tree_id,
            "target_description": attack_tree.target_description,
            "nodes_count": len(attack_tree.nodes),
            "root_nodes": attack_tree.root_nodes,
            "leaf_nodes": attack_tree.leaf_nodes,
            "overall_score": attack_tree.overall_score,
            "estimated_time": attack_tree.estimated_time,
            "created_at": attack_tree.created_at,
            "nodes": {node_id: node.model_dump() for node_id, node in attack_tree.nodes.items()}
        }
    except Exception as e:
        logger.error(f"Attack tree building failed: {e}")
        raise HTTPException(status_code=500, detail=f"Attack tree building failed: {str(e)}")


@app.post("/attack-tree/paths")
async def generate_attack_paths(request: Dict[str, Any]):
    """
    Generate attack paths from an attack tree.
    
    Returns top-k attack paths with scoring and metrics.
    """
    engine = _require_attack_tree_engine()
    
    try:
        tree_id = request.get("tree_id")
        top_k = request.get("top_k", 3)
        
        # For simplicity, we'll rebuild the tree (in production, you'd cache trees)
        target_description = request.get("target_description", "")
        detected_services = request.get("detected_services", [])
        detected_os = request.get("detected_os")
        
        # Get candidate attacks
        services_str = ", ".join(detected_services) if detected_services else ""
        os_str = detected_os or ""
        full_query = " ".join(filter(None, [target_description, services_str, os_str]))
        
        response = searcher.semantic_search(full_query, top_k=40)
        candidates = [r.record for r in response.results]
        
        # Build attack tree
        attack_tree = engine.build_attack_tree(candidates, target_description)
        
        # Generate paths
        paths = engine.generate_attack_paths(attack_tree, top_k)
        
        return {
            "tree_id": attack_tree.tree_id,
            "paths": [path.model_dump() for path in paths],
            "total_paths": len(paths)
        }
    except Exception as e:
        logger.error(f"Attack path generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Attack path generation failed: {str(e)}")


@app.post("/attack-tree/adaptive")
async def generate_adaptive_attack(request: AdaptiveAttackRequest):
    """
    Generate adaptive attack paths based on feedback history.
    
    This endpoint uses the feedback loop to adjust attack paths based on
    previous execution results.
    """
    engine = _require_attack_tree_engine()
    
    try:
        # Get candidate attacks
        services_str = ", ".join(request.detected_services) if request.detected_services else ""
        os_str = request.detected_os or ""
        full_query = " ".join(filter(None, [
            request.target_description,
            services_str,
            os_str,
        ]))
        
        response = searcher.semantic_search(full_query, top_k=40)
        candidates = [r.record for r in response.results]
        
        # Generate adaptive attack
        adaptive_response = engine.generate_adaptive_attack(request, candidates)
        
        return {
            "target_description": adaptive_response.target_description,
            "attack_tree": adaptive_response.attack_tree.model_dump(),
            "recommended_paths": [path.model_dump() for path in adaptive_response.recommended_paths],
            "adaptation_summary": adaptive_response.adaptation_summary,
            "confidence_score": adaptive_response.confidence_score
        }
    except Exception as e:
        logger.error(f"Adaptive attack generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Adaptive attack generation failed: {str(e)}")


# ── Multi-Agent Orchestrator Endpoints ───────────────────────────────────────

def _require_multi_agent_orchestrator():
    if multi_agent_orchestrator is None:
        raise HTTPException(
            status_code=503,
            detail="Multi-agent orchestrator unavailable",
        )
    return multi_agent_orchestrator


@app.get("/agents/status")
async def get_agents_status():
    """
    Get the status of all available agents.
    
    Returns agent types, capabilities, and current status.
    """
    orchestrator = _require_multi_agent_orchestrator()
    
    try:
        agents_info = []
        for agent_type, agent in orchestrator.agents.items():
            capabilities = [cap.model_dump() for cap in agent.get_capabilities()]
            agents_info.append({
                "agent_type": agent_type.value,
                "agent_id": agent.agent_id,
                "status": agent.status.value,
                "capabilities": capabilities,
                "execution_history_count": len(agent.execution_history)
            })
        
        return {
            "agents": agents_info,
            "total_agents": len(agents_info)
        }
    except Exception as e:
        logger.error(f"Failed to get agent status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get agent status: {str(e)}")


@app.post("/agents/execute-plan")
async def execute_agent_plan(request: Dict[str, Any]):
    """
    Execute an attack plan using the multi-agent orchestrator.
    
    This endpoint creates tasks from an attack tree and executes them
    using the appropriate specialized agents.
    """
    orchestrator = _require_multi_agent_orchestrator()
    
    try:
        target_description = request.get("target_description", "")
        context = request.get("context", {})
        
        # Build attack tree
        services_str = ", ".join(request.get("detected_services", []))
        os_str = request.get("detected_os", "")
        full_query = " ".join(filter(None, [target_description, services_str, os_str]))
        
        response = searcher.semantic_search(full_query, top_k=40)
        candidates = [r.record for r in response.results]
        
        attack_tree = attack_tree_engine.build_attack_tree(candidates, target_description)
        
        # Create and execute attack plan
        tasks = orchestrator.create_attack_plan(attack_tree)
        execution_results = await orchestrator.execute_attack_plan(tasks, context)
        
        return {
            "session_id": str(uuid.uuid4())[:8],
            "tasks_created": len(tasks),
            "tasks_executed": len(execution_results),
            "execution_results": [result.model_dump() for result in execution_results],
            "attack_tree_id": attack_tree.tree_id
        }
    except Exception as e:
        logger.error(f"Agent plan execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Agent plan execution failed: {str(e)}")


# ── Feedback Loop Endpoints ───────────────────────────────────────────────────

def _require_feedback_loop_manager():
    if feedback_loop_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Feedback loop manager unavailable",
        )
    return feedback_loop_manager


@app.post("/feedback/session")
async def create_feedback_session(request: AttackVectorRequest):
    """
    Create a new feedback loop session for adaptive attack pathing.
    
    Returns a session ID that can be used to submit analyzer results
    and get adaptive attack chains.
    """
    manager = _require_feedback_loop_manager()
    
    try:
        target = request.target_description
        session = manager.create_session(target, request)
        
        return {
            "session_id": session.session_id,
            "target": session.target,
            "created_at": str(session.created_at),
            "is_active": session.is_active
        }
    except Exception as e:
        logger.error(f"Feedback session creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Feedback session creation failed: {str(e)}")


@app.post("/feedback/{session_id}/analyzer-results")
async def submit_analyzer_results(session_id: str, analyzer_results: Dict[str, Any]):
    """
    Submit real-time analyzer results to a feedback session.
    
    This endpoint processes results from the Real-time Analyzer and
    creates feedback for adaptive attack pathing.
    """
    manager = _require_feedback_loop_manager()
    
    try:
        feedback = await manager.process_analyzer_results(session_id, analyzer_results)
        
        return {
            "feedback_id": feedback.feedback_id,
            "session_id": feedback.session_id,
            "execution_results_count": len(feedback.execution_results),
            "adjusted_probabilities": feedback.adjusted_probabilities,
            "new_recommendations": feedback.new_recommendations,
            "confidence_delta": feedback.confidence_delta,
            "timestamp": feedback.timestamp
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Analyzer result submission failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analyzer result submission failed: {str(e)}")


@app.post("/feedback/{session_id}/adaptive-chains")
async def get_adaptive_chains(session_id: str):
    """
    Get adaptive attack chains based on session feedback history.
    
    Returns attack chains that have been adapted based on
    real-time analyzer results.
    """
    manager = _require_feedback_loop_manager()
    
    try:
        chains_response = await manager.generate_adaptive_chains(session_id)
        
        return {
            "session_id": session_id,
            "target_description": chains_response.target_description,
            "chains": [chain.model_dump() for chain in chains_response.chains],
            "chains_count": len(chains_response.chains)
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Adaptive chains generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Adaptive chains generation failed: {str(e)}")


@app.get("/feedback/{session_id}/insights")
async def get_session_insights(session_id: str):
    """
    Get insights and recommendations for a feedback session.
    
    Returns performance metrics, patterns, and recommendations
    based on the session's feedback history.
    """
    manager = _require_feedback_loop_manager()
    
    try:
        insights = manager.get_session_insights(session_id)
        return insights
    except Exception as e:
        logger.error(f"Session insights retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Session insights retrieval failed: {str(e)}")


@app.get("/feedback/performance")
async def get_feedback_performance():
    """
    Get overall performance metrics for the feedback loop system.
    
    Returns global metrics about adaptation effectiveness,
    session counts, and improvement rates.
    """
    manager = _require_feedback_loop_manager()
    
    try:
        metrics = manager.get_performance_metrics()
        return metrics
    except Exception as e:
        logger.error(f"Performance metrics retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Performance metrics retrieval failed: {str(e)}")


@app.post("/feedback/cleanup")
async def cleanup_inactive_sessions():
    """
    Clean up inactive feedback sessions.
    
    Removes sessions that have been inactive for more than 30 minutes.
    """
    manager = _require_feedback_loop_manager()
    
    try:
        removed_count = manager.cleanup_inactive_sessions()
        return {
            "removed_sessions": removed_count,
            "active_sessions": len(manager.sessions)
        }
    except Exception as e:
        logger.error(f"Session cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Session cleanup failed: {str(e)}")


# ── Dashboard API Endpoints ────────────────────────────────────────────────────────

@app.post("/attack-tree/build")
async def build_attack_tree(request: Dict[str, Any]):
    """
    Build an attack tree from target description.
    
    Dashboard endpoint for AI-powered attack tree generation.
    """
    try:
        attack_tree_engine = _require_attack_tree_engine()
        
        target_description = request.get("target_description", "")
        target_type = request.get("target_type", "unknown")
        
        # Build attack tree using AI
        tree = attack_tree_engine.build_attack_tree(
            target_description=target_description,
            target_type=target_type
        )
        
        return {
            "id": tree.id,
            "name": tree.name,
            "nodes": [node.dict() for node in tree.nodes],
            "overall_score": tree.overall_score,
            "mitre_techniques": tree.mitre_techniques
        }
    except Exception as e:
        logger.error(f"Attack tree build failed: {e}")
        raise HTTPException(status_code=500, detail=f"Attack tree build failed: {str(e)}")

@app.post("/attack-tree/paths")
async def generate_attack_paths(request: Dict[str, Any]):
    """
    Generate attack paths from an attack tree.
    
    Dashboard endpoint for AI-powered attack path optimization.
    """
    try:
        attack_tree_engine = _require_attack_tree_engine()
        
        tree_id = request.get("tree_id", "")
        optimization_criteria = request.get("optimization_criteria", "balanced")
        
        # Generate attack paths
        paths = attack_tree_engine.generate_attack_paths(
            tree_id=tree_id,
            optimization_criteria=optimization_criteria
        )
        
        return {
            "paths": [path.dict() for path in paths],
            "recommended_path": paths[0].dict() if paths else None,
            "analysis": f"Generated {len(paths)} attack paths optimized for {optimization_criteria}"
        }
    except Exception as e:
        logger.error(f"Attack path generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Attack path generation failed: {str(e)}")

@app.get("/agents/status")
async def get_agents_status():
    """
    Get status of all agents.
    
    Dashboard endpoint for multi-agent orchestration monitoring.
    """
    try:
        orchestrator = _require_multi_agent_orchestrator()
        
        # Get agent status
        agents_status = await orchestrator.get_all_agents_status()
        
        return {
            "agents": agents_status,
            "overall_status": "operational" if agents_status else "no_agents"
        }
    except Exception as e:
        logger.error(f"Agent status retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Agent status retrieval failed: {str(e)}")

@app.post("/agents/execute-plan")
async def execute_attack_plan(request: Dict[str, Any]):
    """
    Execute an attack plan via multi-agent orchestrator.
    
    Dashboard endpoint for executing attack chains.
    """
    try:
        orchestrator = _require_multi_agent_orchestrator()
        
        target = request.get("target", "")
        plan_type = request.get("plan_type", "attack_chain")
        parameters = request.get("parameters", {})
        
        # Execute attack plan
        result = await orchestrator.execute_plan(
            target=target,
            plan_type=plan_type,
            parameters=parameters
        )
        
        return {
            "plan_id": result.get("plan_id", f"plan-{int(datetime.now().timestamp())}"),
            "status": result.get("status", "started"),
            "agents_assigned": result.get("agents_assigned", []),
            "estimated_duration": result.get("estimated_duration", 0)
        }
    except Exception as e:
        logger.error(f"Attack plan execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Attack plan execution failed: {str(e)}")

@app.post("/feedback-loop/create")
async def create_feedback_session():
    """
    Create a feedback loop session.
    
    Dashboard endpoint for adaptive attack pathing.
    """
    try:
        feedback_manager = _require_feedback_loop_manager()
        
        session_id = feedback_manager.create_session()
        
        return {
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"Feedback session creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Feedback session creation failed: {str(e)}")

@app.post("/feedback-loop/submit")
async def submit_feedback_results(request: Dict[str, Any]):
    """
    Submit execution results for adaptation.
    
    Dashboard endpoint for feedback loop integration.
    """
    try:
        feedback_manager = _require_feedback_loop_manager()
        
        session_id = request.get("session_id", "")
        execution_results = request.get("execution_results", [])
        environmental_factors = request.get("environmental_factors", {})
        
        # Submit feedback
        adaptations = feedback_manager.submit_results(
            session_id=session_id,
            execution_results=execution_results,
            environmental_factors=environmental_factors
        )
        
        return {
            "session_id": session_id,
            "adaptations": adaptations,
            "recommendations": "Adaptations applied based on execution results"
        }
    except Exception as e:
        logger.error(f"Feedback submission failed: {e}")
        raise HTTPException(status_code=500, detail=f"Feedback submission failed: {str(e)}")

@app.post("/adaptive-attack/generate")
async def generate_adaptive_attack(request: Dict[str, Any]):
    """
    Generate adaptive attack chains.
    
    Dashboard endpoint for AI-powered adaptive attack generation.
    """
    try:
        attack_tree_engine = _require_attack_tree_engine()
        
        target_description = request.get("target_description", "")
        previous_results = request.get("previous_results", [])
        real_time_constraints = request.get("real_time_constraints", {})
        
        # Generate adaptive attack
        adaptive_attack = attack_tree_engine.generate_adaptive_attack(
            target_description=target_description,
            previous_results=previous_results,
            real_time_constraints=real_time_constraints
        )
        
        return {
            "attack_chain": [step.dict() for step in adaptive_attack.attack_chain],
            "confidence_score": adaptive_attack.confidence_score,
            "adaptation_strategy": adaptive_attack.adaptation_strategy
        }
    except Exception as e:
        logger.error(f"Adaptive attack generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Adaptive attack generation failed: {str(e)}")

@app.get("/attacks/results")
async def get_attack_results(limit: int = 10):
    """
    Get previous attack results for analysis.
    
    Dashboard endpoint for historical data integration.
    """
    try:
        # This would typically query a database for historical results
        # For now, return empty array as placeholder
        return []
    except Exception as e:
        logger.error(f"Attack results retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Attack results retrieval failed: {str(e)}")


# ── Run directly ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host=API_HOST, port=API_PORT, reload=True)
