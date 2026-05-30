"""
Standardized health check endpoints for OpsecAI services.

Provides consistent health check responses and dependency checking.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from enum import Enum
import time


# ── Health Status Types ───────────────────────────────────────────────────────

class HealthStatus(str, Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class DependencyStatus(str, Enum):
    """Dependency status levels."""
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


# ── Health Check Data Structures ───────────────────────────────────────────────

class DependencyCheck:
    """Represents a health check for a dependency."""
    
    def __init__(
        self,
        name: str,
        status: DependencyStatus,
        response_time_ms: float,
        message: str = "",
        details: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.status = status
        self.response_time_ms = response_time_ms
        self.message = message
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "response_time_ms": round(self.response_time_ms, 2),
            "message": self.message,
            "details": self.details
        }


class HealthCheckResponse:
    """Standardized health check response."""
    
    def __init__(
        self,
        service_name: str,
        status: HealthStatus,
        version: str = "1.0.0",
        dependencies: Optional[List[DependencyCheck]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ):
        self.service_name = service_name
        self.status = status
        self.version = version
        self.dependencies = dependencies or []
        self.metrics = metrics or {}
        self.timestamp = timestamp or datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "service": self.service_name,
            "status": self.status.value,
            "version": self.version,
            "timestamp": self.timestamp.isoformat() + "Z",
            "dependencies": [dep.to_dict() for dep in self.dependencies],
            "metrics": self.metrics
        }
    
    def is_healthy(self) -> bool:
        """Check if the service is healthy."""
        return self.status == HealthStatus.HEALTHY


# ── Health Check Functions ─────────────────────────────────────────────────────

def check_dependency(
    check_func: Callable,
    timeout: float = 5.0
) -> DependencyCheck:
    """
    Run a dependency check function and return standardized result.
    
    Args:
        check_func: Function that performs the health check
        timeout: Timeout in seconds
    
    Returns:
        DependencyCheck with the result
    """
    start_time = time.time()
    
    try:
        # Run the check with timeout
        result = check_func()
        
        # Calculate response time
        response_time = (time.time() - start_time) * 1000
        
        # Determine status based on result
        if isinstance(result, bool):
            status = DependencyStatus.OK if result else DependencyStatus.ERROR
            message = "Check passed" if result else "Check failed"
        elif isinstance(result, dict):
            status = DependencyStatus(result.get("status", "ok"))
            message = result.get("message", "")
        elif isinstance(result, DependencyCheck):
            return result
        else:
            status = DependencyStatus.OK if result else DependencyStatus.ERROR
            message = str(result) if result else "Check completed"
        
        return DependencyCheck(
            name=check_func.__name__,
            status=status,
            response_time_ms=response_time,
            message=message
        )
    
    except TimeoutError:
        response_time = (time.time() - start_time) * 1000
        return DependencyCheck(
            name=check_func.__name__,
            status=DependencyStatus.TIMEOUT,
            response_time_ms=response_time,
            message=f"Check timed out after {timeout}s"
        )
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return DependencyCheck(
            name=check_func.__name__,
            status=DependencyStatus.ERROR,
            response_time_ms=response_time,
            message=f"Check failed: {str(e)}"
        )


def create_health_check(
    service_name: str,
    version: str = "1.0.0",
    dependency_checks: Optional[List[Callable]] = None,
    custom_metrics: Optional[Dict[str, Any]] = None
) -> Callable:
    """
    Create a health check function for a service.
    
    Args:
        service_name: Name of the service
        version: Version of the service
        dependency_checks: List of functions to check dependencies
        custom_metrics: Additional metrics to include
    
    Returns:
        Function that performs health check
    """
    def health_check() -> HealthCheckResponse:
        """Perform health check."""
        dependencies = []
        overall_status = HealthStatus.HEALTHY
        
        # Run dependency checks
        if dependency_checks:
            for check_func in dependency_checks:
                dep_result = check_dependency(check_func)
                dependencies.append(dep_result)
                
                # Determine overall status based on dependencies
                if dep_result.status == DependencyStatus.ERROR:
                    overall_status = HealthStatus.UNHEALTHY
                elif dep_result.status == DependencyStatus.TIMEOUT:
                    overall_status = HealthStatus.DEGRADED
        
        # Build metrics
        metrics = {
            "dependency_count": len(dependencies),
            "healthy_dependencies": sum(1 for d in dependencies if d.status == DependencyStatus.OK),
            "unhealthy_dependencies": sum(1 for d in dependencies if d.status == DependencyStatus.ERROR),
        }
        
        if custom_metrics:
            metrics.update(custom_metrics)
        
        return HealthCheckResponse(
            service_name=service_name,
            status=overall_status,
            version=version,
            dependencies=dependencies,
            metrics=metrics
        )
    
    return health_check


# ── Common Dependency Check Functions ───────────────────────────────────────────

def check_postgresql(connection_func, timeout: float = 5.0) -> DependencyCheck:
    """
    Check PostgreSQL connection.
    
    Args:
        connection_func: Function that returns a database connection
        timeout: Timeout in seconds
    """
    def check():
        try:
            conn = connection_func()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            conn.close()
            return True
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    return check_dependency(check, timeout)


def check_redis(redis_client, timeout: float = 2.0) -> DependencyCheck:
    """
    Check Redis connection.
    
    Args:
        redis_client: Redis client instance
        timeout: Timeout in seconds
    """
    def check():
        try:
            redis_client.ping()
            return True
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    return check_dependency(check, timeout)


def check_http_endpoint(url: str, timeout: float = 5.0) -> DependencyCheck:
    """
    Check HTTP endpoint availability.
    
    Args:
        url: URL to check
        timeout: Timeout in seconds
    """
    import httpx
    
    def check():
        try:
            response = httpx.get(url, timeout=timeout)
            return response.status_code == 200
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    return check_dependency(check, timeout)


def check_qdrant(host: str, port: int = 6333, timeout: float = 5.0) -> DependencyCheck:
    """
    Check Qdrant vector database connection.
    
    Args:
        host: Qdrant host
        port: Qdrant port
        timeout: Timeout in seconds
    """
    def check():
        try:
            from qdrant_client import QdrantClient
            client = QdrantClient(host=host, port=port)
            client.get_collections()
            return True
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    return check_dependency(check, timeout)


# ── Ready and Live Probes ───────────────────────────────────────────────────────

def create_readiness_probe(
    health_check_func: Callable,
    min_healthy_dependencies: int = 0
) -> Callable:
    """
    Create a readiness probe function.
    
    Args:
        health_check_func: Function that returns HealthCheckResponse
        min_healthy_dependencies: Minimum healthy dependencies required
    
    Returns:
        Function that returns readiness status
    """
    def readiness_check():
        health_result = health_check_func()
        
        healthy_deps = sum(1 for d in health_result.dependencies if d.status == DependencyStatus.OK)
        
        if healthy_deps >= min_healthy_dependencies:
            return {
                "ready": True,
                "healthy_dependencies": healthy_deps,
                "total_dependencies": len(health_result.dependencies)
            }
        else:
            return {
                "ready": False,
                "healthy_dependencies": healthy_deps,
                "total_dependencies": len(health_result.dependencies),
                "reason": f"Only {healthy_deps}/{len(health_result.dependencies)} dependencies healthy"
            }
    
    return readiness_check


def create_liveness_probe() -> Callable:
    """
    Create a liveness probe function.
    
    Liveness probe should be lightweight and just check if the service is running.
    """
    def liveness_check():
        return {
            "alive": True,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    
    return liveness_check


# ── FastAPI Integration ───────────────────────────────────────────────────────

def setup_health_endpoints(
    app,
    service_name: str,
    version: str = "1.0.0",
    dependency_checks: Optional[List[Callable]] = None,
    custom_metrics: Optional[Dict[str, Any]] = None
):
    """
    Setup standardized health endpoints for FastAPI application.
    
    Args:
        app: FastAPI application instance
        service_name: Name of the service
        version: Version of the service
        dependency_checks: List of dependency check functions
        custom_metrics: Additional metrics to include
    """
    from fastapi import APIRouter
    
    health_router = APIRouter()
    
    # Create health check function
    health_check = create_health_check(
        service_name=service_name,
        version=version,
        dependency_checks=dependency_checks,
        custom_metrics=custom_metrics
    )
    
    # Create readiness and liveness probes
    readiness_check = create_readiness_probe(health_check)
    liveness_check = create_liveness_probe()
    
    @health_router.get("/health")
    def health():
        """Main health check endpoint."""
        return health_check().to_dict()
    
    @health_router.get("/ready")
    def ready():
        """Readiness probe endpoint."""
        return readiness_check()
    
    @health_router.get("/live")
    def live():
        """Liveness probe endpoint."""
        return liveness_check()
    
    # Include router in app
    app.include_router(health_router)
    
    return app