"""
OpsecAI Integration Hub - Main FastAPI Application
"""

import sys
import os
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add parent directories to path for shared imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

# Import config.py directly to avoid conflict with config package
import importlib.util
spec = importlib.util.spec_from_file_location("config_module", os.path.join(os.path.dirname(__file__), "config.py"))
config_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config_module)
settings = config_module.settings
# Add current directory to path for plugin_system imports
sys.path.insert(0, os.path.dirname(__file__))
from plugin_system import PluginManager
from plugin_system.base import ExecutionContext
from plugin_system.types import ExecutionType
import shared.logging_config
import shared.health
import shared.config_validator
from shared.fastapi_robustness import setup_robustness_middleware


# Setup logging
shared.logging_config.setup_logging(
    service_name=settings.SERVICE_NAME,
    environment=settings.ENVIRONMENT,
    log_level=settings.LOG_LEVEL
)

logger = logging.getLogger(__name__)


# State management for operations and monitoring sessions
class OperationState:
    """Track active red team operations."""
    
    def __init__(self):
        self.operations: Dict[str, dict] = {}
        self.monitoring_sessions: Dict[str, dict] = {}
        self.execution_history: List[dict] = []
    
    def add_operation(
        self,
        operation_id: str,
        engagement_id: str,
        target: str,
        status: str = "running",
        operation_type: str = "automation",
        progress: int = 0,
    ):
        self.operations[operation_id] = {
            "operation_id": operation_id,
            "engagement_id": engagement_id,
            "target": target,
            "status": status,
            "type": operation_type,
            "operation_type": operation_type,
            "progress": progress,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
    
    def update_operation_status(self, operation_id: str, status: str):
        if operation_id in self.operations:
            self.operations[operation_id]["status"] = status
            self.operations[operation_id]["updated_at"] = datetime.now().isoformat()
    
    def add_monitoring_session(self, session_id: str, engagement_id: str, targets: List[str], interval: int, status: str = "active"):
        self.monitoring_sessions[session_id] = {
            "session_id": session_id,
            "engagement_id": engagement_id,
            "targets": targets,
            "interval": interval,
            "status": status,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
    
    def update_monitoring_status(self, session_id: str, status: str):
        if session_id in self.monitoring_sessions:
            self.monitoring_sessions[session_id]["status"] = status
            self.monitoring_sessions[session_id]["updated_at"] = datetime.now().isoformat()


# Global state instance
operation_state = OperationState()
MAX_EXECUTION_HISTORY = 100


def _extract_operation_from_parameters(parameters: dict) -> Optional[str]:
    if not parameters:
        return None
    return parameters.get("operation") or parameters.get("scan_type")


async def _maybe_run_opsec_assessment(
    plugin_name: str,
    target: str,
    parameters: dict,
    metadata: dict,
) -> Optional[Dict]:
    """Run OpSec assessor when dashboard requests pre/post assessment."""
    if not metadata.get("run_opsec_assessment"):
        return None
    try:
        from opsec.assessor import OpSecAssessor

        assessor = OpSecAssessor()
        assessment = await assessor.assess_execution(
            plugin_name=plugin_name,
            operation=_extract_operation_from_parameters(parameters),
            parameters=parameters,
            target=target,
            context=metadata,
        )
        return assessor.to_dict(assessment)
    except Exception as exc:
        logger.warning("OpSec assessment failed: %s", exc)
        return {"error": str(exc)}


def _record_execution(
    plugin_name: str,
    target: str,
    parameters: dict,
    success: bool,
    error: Optional[str] = None,
    execution_time: Optional[float] = None,
    operation_id: Optional[str] = None,
):
    """Persist recent execution for hub history API and plugin last_run."""
    entry = {
        "id": operation_id or f"exec_{int(datetime.now().timestamp() * 1000)}",
        "plugin_name": plugin_name,
        "operation": _extract_operation_from_parameters(parameters),
        "target": target,
        "success": success,
        "error": error,
        "execution_time": execution_time,
        "created_at": datetime.now().isoformat(),
    }
    operation_state.execution_history.insert(0, entry)
    if len(operation_state.execution_history) > MAX_EXECUTION_HISTORY:
        operation_state.execution_history = operation_state.execution_history[
            :MAX_EXECUTION_HISTORY
        ]

# Long-running routes use a higher HTTP timeout than quick plugin health checks
LONG_RUNNING_PATH_PREFIXES = (
    "/execute",
    "/integrations/execute",
    "/api/v1/automation/",
)


def _resolve_plugin_execute(operation: str, request: dict) -> tuple:
    """Map generic /execute requests to the correct plugin + parameters."""
    if request.get("plugin_name"):
        return request["plugin_name"], request.get("parameters") or request

    target = request.get("target") or "unknown"
    context = request.get("context") or {}

    if operation == "assistant_chat":
        return "jailbreak_ai", {
            "operation": "assistant_chat",
            "messages": request.get("messages") or [],
            "engagement_context": request.get("engagement_context"),
            "rag_context": request.get("rag_context"),
            "stream": request.get("stream", False),
            "temperature": request.get("temperature", 0.6),
            "max_tokens": request.get("max_tokens", 2048),
        }

    if operation == "execute_attack_step":
        step = request.get("step") or {}
        return "jailbreak_ai", {
            "operation": "execute_attack_step",
            "step": step,
            "target": target,
            "step_number": context.get("step_number"),
            "execution_id": context.get("execution_id"),
            "previous_results": context.get("previous_results", []),
            "isolated_attack": bool(
                (step or {}).get("isolated_attack") or context.get("isolated_attack")
            ),
            "isolated_attempt": (step or {}).get("isolated_attempt")
            or context.get("isolated_attempt"),
            "same_tool": (step or {}).get("tool") or context.get("same_tool"),
            "parent_method_id": context.get("parent_method_id"),
            "context": context,
        }

    scan_type = "quick" if operation in ("reconnaissance", "port_scan") else "default"
    if operation in ("reconnaissance", "vulnerability_scan", "port_scan", "scan"):
        nmap_params: Dict[str, Any] = {
            "target": target,
            "scan_type": request.get("scan_type") or scan_type,
        }
        if request.get("ports"):
            nmap_params["ports"] = request.get("ports")
        return "nmap", nmap_params

    metasploit_ops = {
        "metasploit_list_modules": "list_modules",
        "metasploit_auxiliary": "run_auxiliary",
        "metasploit_exploit": "run_exploit",
        "metasploit_payload": "generate_payload",
        "metasploit_modules": "list_modules",
    }
    if operation in metasploit_ops or (
        isinstance(operation, str) and operation.startswith("metasploit_")
    ):
        hub_params = request.get("hub_parameters") or request.get("parameters") or {}
        msf_op = metasploit_ops.get(operation) or hub_params.get("operation", "list_modules")
        msf_params: Dict[str, Any] = {
            "operation": msf_op,
            "target": target,
            "roe_acknowledged": bool(
                context.get("roe_acknowledged") or request.get("roe_acknowledged")
            ),
            "web_only": context.get("web_only", request.get("web_only", True)),
            "council_approved": bool(
                context.get("council_approved") or request.get("council_approved")
            ),
            "dry_run": hub_params.get("dry_run", request.get("dry_run", False)),
            **hub_params,
        }
        return "metasploit", msf_params

    web_scanner_ops = {
        "nuclei_scan": ("nuclei", "scan_target"),
        "nuclei_templates": ("nuclei", "list_templates"),
        "nuclei_list_templates": ("nuclei", "list_templates"),
        "ffuf_fuzz": ("ffuf", "fuzz_url"),
        "ffuf_vhost": ("ffuf", "fuzz_vhost"),
        "sqlmap_test": ("sqlmap", "test_url"),
        "sqlmap_crawl": ("sqlmap", "crawl_and_test"),
    }
    if operation in web_scanner_ops or (
        isinstance(operation, str)
        and operation.split("_")[0] in ("nuclei", "ffuf", "sqlmap")
    ):
        hub_params = request.get("hub_parameters") or request.get("parameters") or {}
        plugin_name, default_op = web_scanner_ops.get(
            operation, (operation.split("_")[0], hub_params.get("operation", "scan_target"))
        )
        if operation.startswith("nuclei"):
            plugin_name = "nuclei"
            default_op = hub_params.get("operation") or (
                "list_templates" if "template" in operation else "scan_target"
            )
        elif operation.startswith("ffuf"):
            plugin_name = "ffuf"
            default_op = hub_params.get("operation") or (
                "fuzz_vhost" if "vhost" in operation else "fuzz_url"
            )
        elif operation.startswith("sqlmap"):
            plugin_name = "sqlmap"
            default_op = hub_params.get("operation") or (
                "crawl_and_test" if "crawl" in operation else "test_url"
            )
        scanner_params: Dict[str, Any] = {
            "operation": default_op,
            "target": target,
            "roe_acknowledged": bool(
                context.get("roe_acknowledged") or request.get("roe_acknowledged")
            ),
            "web_only": context.get("web_only", request.get("web_only", True)),
            "council_approved": bool(
                context.get("council_approved") or request.get("council_approved")
            ),
            **hub_params,
        }
        return plugin_name, scanner_params

    if operation in ("exploitation", "exfiltration", "persistence", "chat"):
        return "jailbreak_ai", {
            "operation": "chat",
            "messages": request.get("messages")
            or [
                {
                    "role": "user",
                    "content": (
                        f"Authorized pentest guidance for {operation} against {target}. "
                        "Respond with concise operator steps."
                    ),
                }
            ],
            "temperature": 0.5,
            "max_tokens": 800,
        }

    if operation == "redteam_automation":
        return "jailbreak_ai", request

    return "jailbreak_ai", {**request, "operation": operation or "chat"}


async def _enrich_plugins_list(plugin_manager) -> List[Dict]:
    """Attach UI-friendly enabled/healthy flags; refresh health for loaded plugins."""
    from plugin_system.types import HealthStatus, PluginStatus

    plugins = await plugin_manager.list_plugins()
    enriched = []
    for p in plugins:
        name = p.get("name")
        try:
            health = await plugin_manager.health_check(name)
            p["healthy"] = bool(health.get("healthy"))
            p["health_status"] = (
                HealthStatus.HEALTHY.value
                if health.get("healthy")
                else HealthStatus.UNHEALTHY.value
            )
        except Exception:
            p["healthy"] = False
        p["enabled"] = p.get("status") != PluginStatus.DISABLED.value
        enriched.append(p)
    return enriched


# Pydantic models for request/response
class MultiTargetRequest(BaseModel):
    engagement_id: str
    targets: List[str]
    aggression_level: int = 5
    parallel: bool = True
    evasion_level: str = "medium"
    max_parallel_tasks: int = 5


class MonitoringStartRequest(BaseModel):
    engagement_id: str
    targets: List[str]
    interval: int = 300


class ReplanningRequest(BaseModel):
    operation_id: str
    failed_step: dict
    context: dict


class OperationControlRequest(BaseModel):
    operation_id: str
    action: str  # pause, resume, abort


class MonitoringControlRequest(BaseModel):
    session_id: str
    action: str  # pause, resume, stop


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Integration Hub...")
    
    # Validate configuration
    # try:
    #     shared.config_validation.validate_config()
    #     logger.info("Configuration validated successfully")
    # except Exception as e:
    #     logger.error(f"Configuration validation failed: {e}")
    #     raise
    
    # Initialize plugin manager
    try:
        plugin_manager = PluginManager(config_dir=settings.INTEGRATION_CONFIG_DIR)
        await plugin_manager.initialize()
        app.state.plugin_manager = plugin_manager
        logger.info("Plugin manager initialized")
    except Exception as e:
        logger.error(f"Failed to initialize plugin manager: {e}")
        raise
    
    logger.info("Integration Hub started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Integration Hub...")
    
    if hasattr(app.state, 'plugin_manager'):
        await app.state.plugin_manager.shutdown()
    
    logger.info("Integration Hub shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="OpsecAI Integration Hub",
    description="Plugin architecture for external tool and API integrations",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Setup robustness middleware (correlation IDs, logging, metrics, timeouts, security headers)
setup_robustness_middleware(
    app,
    service_name=settings.SERVICE_NAME,
    timeout_seconds=600.0,
    version="1.0.0",
    custom_metrics={
        "plugin_count": 0  # Will be updated dynamically
    }
)

# Setup health endpoints
# Note: setup_robustness_middleware already adds /health, /ready, /live, and /metrics
# We keep custom health checks for plugin-specific status


# Basic API routes
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "OpsecAI Integration Hub",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    plugin_count = 0
    plugins_ready = 0
    plugins_healthy = 0
    if hasattr(app.state, "plugin_manager"):
        plugins = await app.state.plugin_manager.list_plugins()
        plugin_count = len(plugins)
        plugins_ready = sum(1 for p in plugins if p.get("status") == "ready")
        plugins_healthy = sum(
            1 for p in plugins if p.get("health_status") == "healthy"
        )
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "plugin_count": plugin_count,
        "plugins_ready": plugins_ready,
        "plugins_healthy": plugins_healthy,
    }


@app.get("/integrations")
async def integrations_summary():
    """Hub summary for dashboards and service discovery."""
    if not hasattr(app.state, "plugin_manager"):
        return {
            "service": settings.SERVICE_NAME,
            "status": "degraded",
            "plugins": [],
            "count": 0,
            "error": "Plugin manager not initialized",
        }
    plugins = await _enrich_plugins_list(app.state.plugin_manager)
    return {
        "service": settings.SERVICE_NAME,
        "status": "healthy",
        "version": "1.0.0",
        "plugins": plugins,
        "count": len(plugins),
        "execution_history_count": len(operation_state.execution_history),
    }


@app.get("/api/v1/executions")
async def list_executions(limit: int = 50):
    """Recent plugin execution history for Integration Hub UI."""
    limit = max(1, min(limit, MAX_EXECUTION_HISTORY))
    items = operation_state.execution_history[:limit]
    return {"executions": items, "count": len(items)}


@app.get("/api/v1/plugins")
async def list_plugins(refresh_health: bool = False):
    """List all available plugins."""
    if not hasattr(app.state, 'plugin_manager'):
        return {"plugins": [], "error": "Plugin manager not initialized"}
    
    if refresh_health:
        plugins = await _enrich_plugins_list(app.state.plugin_manager)
    else:
        plugins = await app.state.plugin_manager.list_plugins()
        from plugin_system.types import PluginStatus
        for p in plugins:
            p["enabled"] = p.get("status") != PluginStatus.DISABLED.value
            p["healthy"] = p.get("health_status") == "healthy"
    return {"plugins": plugins, "count": len(plugins)}


@app.get("/api/v1/plugins/{plugin_name}")
async def get_plugin_info(plugin_name: str):
    """Get plugin information."""
    if not hasattr(app.state, 'plugin_manager'):
        return {"error": "Plugin manager not initialized"}, 503
    
    try:
        info = await app.state.plugin_manager.get_plugin_info(plugin_name)
        health = await app.state.plugin_manager.health_check(plugin_name)
        info = {**info, "health": health}
        if not info.get("capabilities") and info.get("execution_types"):
            info["capabilities"] = info["execution_types"]
        return info
    except ValueError as e:
        return {"error": str(e)}, 404


@app.get("/api/v1/plugins/{plugin_name}/health")
async def plugin_health_check(plugin_name: str):
    """Check plugin health."""
    if not hasattr(app.state, 'plugin_manager'):
        return {"error": "Plugin manager not initialized"}, 503
    
    try:
        health = await app.state.plugin_manager.health_check(plugin_name)
        return health
    except ValueError as e:
        return {"error": str(e)}, 404


@app.post("/api/v1/plugins/{plugin_name}/enable")
async def enable_plugin(plugin_name: str):
    """Enable a plugin."""
    if not hasattr(app.state, 'plugin_manager'):
        return {"error": "Plugin manager not initialized"}, 503
    
    try:
        from plugin_system.types import PluginStatus
        await app.state.plugin_manager.registry.update_status(plugin_name, PluginStatus.READY)
        return {"status": "enabled", "plugin": plugin_name}
    except ValueError as e:
        return {"error": str(e)}, 404


@app.post("/api/v1/plugins/{plugin_name}/disable")
async def disable_plugin(plugin_name: str):
    """Disable a plugin."""
    if not hasattr(app.state, 'plugin_manager'):
        return {"error": "Plugin manager not initialized"}, 503
    
    try:
        from plugin_system.types import PluginStatus
        await app.state.plugin_manager.registry.update_status(plugin_name, PluginStatus.DISABLED)
        return {"status": "disabled", "plugin": plugin_name}
    except ValueError as e:
        return {"error": str(e)}, 404


@app.post("/execute")
async def execute_operation(request: dict):
    """
    Execute an attack operation with jailbreak AI guidance.
    
    This endpoint is called by the orchestrator for step-by-step attack execution.
    """
    if not hasattr(app.state, 'plugin_manager'):
        return {"error": "Plugin manager not initialized"}, 503
    
    try:
        operation = request.get("operation")
        step = request.get("step")
        target = request.get("target")
        context = request.get("context", {})
        
        if not operation and not request.get("plugin_name"):
            raise HTTPException(status_code=400, detail="operation is required")

        plugin_name, parameters = _resolve_plugin_execute(operation or "", request)
        
        # Build execution context
        exec_context = ExecutionContext(
            integration_id=plugin_name,
            engagement_id=context.get("engagement_id", "unknown"),
            target=target or "unknown",
            parameters=parameters,
            timeout=300,  # 5 minute timeout
            metadata={"operation": operation}
        )
        
        track_ui = operation not in ("execute_attack_step",) and request.get("track", True)
        op_id = None
        if track_ui:
            op_id = f"exec_{int(datetime.now().timestamp())}"
            operation_state.add_operation(
                op_id,
                context.get("engagement_id", "dashboard"),
                target or "unknown",
                status="running",
                operation_type=operation or plugin_name,
            )

        metadata = context if isinstance(context, dict) else {}
        run_opsec = bool(
            request.get("run_opsec_assessment")
            or metadata.get("run_opsec_assessment")
        )
        if run_opsec:
            exec_context.metadata = {**exec_context.metadata, "run_opsec_assessment": True}

        result = await app.state.plugin_manager.execute(plugin_name, exec_context)

        await app.state.plugin_manager.registry.record_last_run(plugin_name)
        _record_execution(
            plugin_name,
            target or "unknown",
            parameters,
            result.success,
            error=result.error,
            execution_time=result.execution_time,
            operation_id=op_id,
        )

        if op_id:
            operation_state.update_operation_status(
                op_id, "completed" if result.success else "failed"
            )
            if result.success:
                operation_state.operations[op_id]["progress"] = 100

        opsec_assessment = None
        if run_opsec:
            opsec_assessment = await _maybe_run_opsec_assessment(
                plugin_name,
                target or "unknown",
                parameters,
                exec_context.metadata,
            )
        
        # Parse result for attack operations
        if operation == "execute_attack_step" and result.success:
            # Extract jailbreak guidance from result (flat + nested for orchestrator mappers)
            output = result.output if isinstance(result.output, dict) else {}
            return {
                "success": True,
                "guidance": output.get("guidance", "Standard execution"),
                "tools": output.get("tools", []),
                "attack_vectors": output.get("attack_vectors", []),
                "evasion_techniques": output.get("evasion_techniques", []),
                "output": output,
            }
        else:
            payload = {
                "success": result.success,
                "output": result.output,
                "error": result.error,
                "artifacts": result.artifacts,
                "opsec_context": result.opsec_context,
                "execution_time": result.execution_time,
                "plugin": plugin_name,
            }
            if op_id:
                payload["operation_id"] = op_id
            if opsec_assessment:
                payload["opsec_assessment"] = opsec_assessment
            return payload
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Operation execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/integrations/execute")
async def execute_plugin(request: dict):
    """
    Execute a plugin with given parameters.
    
    This is the main entry point for plugin execution.
    """
    if not hasattr(app.state, 'plugin_manager'):
        return {"error": "Plugin manager not initialized"}, 503
    
    try:
        plugin_name = request.get("plugin_name")
        if not plugin_name:
            return {"error": "plugin_name is required"}, 400
        
        engagement_id = request.get("engagement_id", "unknown")
        target = request.get("target", "unknown")
        parameters = request.get("parameters", {})
        timeout = request.get("timeout", 60)
        metadata = request.get("metadata", {})
        
        # Build execution context
        context = ExecutionContext(
            integration_id=plugin_name,
            engagement_id=engagement_id,
            target=target,
            parameters=parameters,
            timeout=timeout,
            metadata=metadata
        )
        
        run_opsec = bool(
            request.get("run_opsec_assessment")
            or metadata.get("run_opsec_assessment")
        )
        if run_opsec:
            metadata = {**metadata, "run_opsec_assessment": True}
            context.metadata = metadata

        # Execute plugin
        result = await app.state.plugin_manager.execute(plugin_name, context)

        await app.state.plugin_manager.registry.record_last_run(plugin_name)
        _record_execution(
            plugin_name,
            target,
            parameters,
            result.success,
            error=result.error,
            execution_time=result.execution_time,
        )

        opsec_assessment = None
        if run_opsec:
            opsec_assessment = await _maybe_run_opsec_assessment(
                plugin_name, target, parameters, metadata
            )

        payload = {
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "artifacts": result.artifacts,
            "opsec_context": result.opsec_context,
            "execution_time": result.execution_time,
            "plugin": plugin_name,
        }
        if opsec_assessment:
            payload["opsec_assessment"] = opsec_assessment
        return payload
        
    except ValueError as e:
        return {"error": str(e)}, 404
    except Exception as e:
        logger.error(f"Plugin execution failed: {e}")
        return {"error": str(e)}, 500


# Enhanced Automation API Endpoints

async def _run_multi_target_job(operation_id: str, request: MultiTargetRequest):
    """Background worker for multi-target automation."""
    try:
        context = ExecutionContext(
            integration_id="jailbreak_ai",
            engagement_id=request.engagement_id,
            target=",".join(request.targets[:5]),
            parameters={
                "operation": "multi_target_automation",
                "multi_target_config": {
                    "targets": request.targets,
                    "aggression_level": request.aggression_level,
                    "parallel": request.parallel,
                    "evasion_level": request.evasion_level,
                    "max_parallel_tasks": request.max_parallel_tasks,
                },
            },
            timeout=28800,
            metadata={"operation_id": operation_id},
        )
        result = await app.state.plugin_manager.execute("jailbreak_ai", context)
        operation_state.update_operation_status(
            operation_id, "completed" if result.success else "failed"
        )
    except Exception as exc:
        logger.error("Multi-target background job failed: %s", exc)
        operation_state.update_operation_status(operation_id, "failed")


@app.post("/api/v1/automation/multi-target")
async def multi_target_operation(request: MultiTargetRequest):
    """
    Execute multi-target red team operation.
    """
    if not hasattr(app.state, 'plugin_manager'):
        raise HTTPException(status_code=503, detail="Plugin manager not initialized")
    
    try:
        operation_id = f"multi_{request.engagement_id}_{int(datetime.now().timestamp())}"
        operation_state.add_operation(
            operation_id,
            request.engagement_id,
            ", ".join(request.targets),
            status="running",
            operation_type="multi_target",
            progress=0,
        )
        asyncio.create_task(_run_multi_target_job(operation_id, request))
        
        return {
            "success": True,
            "status": "running",
            "operation_id": operation_id,
            "targets": request.targets,
            "message": "Multi-target operation started",
        }
        
    except Exception as e:
        logger.error(f"Multi-target operation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/automation/monitoring/start")
async def start_monitoring(request: MonitoringStartRequest):
    """
    Start continuous monitoring for targets.
    """
    if not hasattr(app.state, 'plugin_manager'):
        raise HTTPException(status_code=503, detail="Plugin manager not initialized")
    
    try:
        # Generate session ID
        session_id = f"monitor_{request.engagement_id}_{datetime.now().timestamp()}"
        
        operation_state.add_monitoring_session(
            session_id,
            request.engagement_id,
            request.targets,
            request.interval,
        )

        async def _start_monitoring():
            try:
                context = ExecutionContext(
                    integration_id="jailbreak_ai",
                    engagement_id=request.engagement_id,
                    target="monitoring",
                    parameters={
                        "operation": "continuous_monitoring",
                        "monitor_config": {
                            "targets": request.targets,
                            "interval": request.interval,
                        },
                    },
                    timeout=120,
                    metadata={"session_id": session_id},
                )
                await app.state.plugin_manager.execute("jailbreak_ai", context)
            except Exception as exc:
                logger.warning("Monitoring plugin start: %s", exc)

        asyncio.create_task(_start_monitoring())

        return {
            "success": True,
            "status": "active",
            "session_id": session_id,
            "targets": request.targets,
            "interval": request.interval,
            "message": "Monitoring session started",
        }
        
    except Exception as e:
        logger.error(f"Monitoring start failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/automation/replanning")
async def adaptive_replanning(request: ReplanningRequest):
    """
    Execute AI-driven adaptive replanning for failed steps.
    """
    if not hasattr(app.state, 'plugin_manager'):
        raise HTTPException(status_code=503, detail="Plugin manager not initialized")
    
    try:
        # Execute via jailbreak_ai plugin
        context = ExecutionContext(
            integration_id="jailbreak_ai",
            engagement_id=request.context.get("engagement_id", "unknown"),
            target="adaptive",
            parameters={
                "operation": "adaptive_replanning",
                "operation_id": request.operation_id,
                "failed_step": request.failed_step,
                "context": request.context
            },
            timeout=120,
            metadata={"operation_id": request.operation_id}
        )
        
        result = await app.state.plugin_manager.execute("jailbreak_ai", context)
        
        return {
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "artifacts": result.artifacts,
            "opsec_context": result.opsec_context,
            "execution_time": result.execution_time
        }
        
    except Exception as e:
        logger.error(f"Adaptive replanning failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/automation/operation/control")
async def control_operation(request: OperationControlRequest):
    """
    Control running operations (pause, resume, abort).
    """
    try:
        if request.operation_id not in operation_state.operations:
            raise HTTPException(status_code=404, detail="Operation not found")

        action = request.action
        if action == "stop":
            action = "abort"

        operation_state.update_operation_status(request.operation_id, action)
        
        # Execute control action via jailbreak_ai plugin
        if hasattr(app.state, 'plugin_manager'):
            context = ExecutionContext(
                integration_id="jailbreak_ai",
                engagement_id=operation_state.operations[request.operation_id]["engagement_id"],
                target="control",
                parameters={
                    "operation": "control",
                    "control_action": request.action,
                    "operation_id": request.operation_id
                },
                timeout=30,
                metadata={"operation_id": request.operation_id}
            )
            
            result = await app.state.plugin_manager.execute("jailbreak_ai", context)
            
            return {
                "success": result.success,
                "output": result.output,
                "error": result.error,
                "operation_id": request.operation_id,
                "action": request.action,
                "status": operation_state.operations[request.operation_id]["status"]
            }
        
        return {
            "success": True,
            "operation_id": request.operation_id,
            "action": request.action,
            "status": operation_state.operations[request.operation_id]["status"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Operation control failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/automation/monitoring/control")
async def control_monitoring(request: MonitoringControlRequest):
    """
    Control monitoring sessions (pause, resume, stop).
    """
    try:
        if request.session_id not in operation_state.monitoring_sessions:
            raise HTTPException(status_code=404, detail="Monitoring session not found")
        
        # Update monitoring status
        operation_state.update_monitoring_status(request.session_id, request.action)
        
        return {
            "success": True,
            "session_id": request.session_id,
            "action": request.action,
            "status": operation_state.monitoring_sessions[request.session_id]["status"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Monitoring control failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/automation/operations")
async def list_operations():
    """
    List all operations.
    """
    ops = []
    for raw in operation_state.operations.values():
        ops.append(
            {
                **raw,
                "id": raw.get("operation_id"),
                "progress": raw.get("progress", 0),
            }
        )
    return {"operations": ops, "count": len(ops)}


@app.get("/api/v1/automation/monitoring/sessions")
async def list_monitoring_sessions():
    """
    List all monitoring sessions.
    """
    return {
        "sessions": list(operation_state.monitoring_sessions.values()),
        "count": len(operation_state.monitoring_sessions)
    }


@app.get("/api/v1/operation/{operation_id}")
async def get_operation_status(operation_id: str):
    """
    Get operation status by ID.
    """
    if operation_id not in operation_state.operations:
        raise HTTPException(status_code=404, detail="Operation not found")
    
    return operation_state.operations[operation_id]


@app.get("/api/v1/monitoring/{session_id}")
async def get_monitoring_status(session_id: str):
    """
    Get monitoring session status by ID.
    """
    if session_id not in operation_state.monitoring_sessions:
        raise HTTPException(status_code=404, detail="Monitoring session not found")
    
    return operation_state.monitoring_sessions[session_id]




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.SERVICE_HOST,
        port=settings.SERVICE_PORT,
        reload=settings.ENVIRONMENT == "development"
    )