"""
Enhanced robustness middleware for FastAPI services.

Provides request correlation, structured logging, metrics collection,
timeout handling, security headers, and standardized error handling.
"""

import time
import uuid
import logging
from typing import Optional, Callable, Dict, Any, List
from collections import defaultdict
from datetime import datetime

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .errors import (
    OpsecAIError,
    handle_exception,
    create_error_response,
    setup_fastapi_error_handlers,
)
from .robustness import RobustnessManager
from .health import setup_health_endpoints

logger = logging.getLogger(__name__)


# ── Metrics Collector ───────────────────────────────────────────────────────────

class MetricsCollector:
    """Collect request metrics for FastAPI services."""

    def __init__(self):
        self.request_counts: Dict[str, int] = defaultdict(int)
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.response_time_buckets: Dict[str, int] = defaultdict(int)
        self.active_requests = 0
        self.total_requests = 0
        self.start_time = time.time()

    def record_request(self, method: str, path: str, status_code: int, duration_ms: float):
        key = f"{method} {path}"
        self.request_counts[key] += 1
        self.total_requests += 1

        if status_code >= 400:
            self.error_counts[str(status_code)] += 1

        bucket = (
            "<100ms" if duration_ms < 100
            else "100-250ms" if duration_ms < 250
            else "250-500ms" if duration_ms < 500
            else "500ms-1s" if duration_ms < 1000
            else "1-2.5s" if duration_ms < 2500
            else "2.5-5s" if duration_ms < 5000
            else "5-10s" if duration_ms < 10000
            else ">10s"
        )
        self.response_time_buckets[bucket] += 1

    def increment_active(self):
        self.active_requests += 1

    def decrement_active(self):
        self.active_requests = max(0, self.active_requests - 1)

    def get_metrics(self) -> Dict[str, Any]:
        uptime = time.time() - self.start_time
        return {
            "uptime_seconds": round(uptime, 2),
            "total_requests": self.total_requests,
            "active_requests": self.active_requests,
            "request_counts": dict(self.request_counts),
            "error_counts": dict(self.error_counts),
            "response_time_buckets": dict(self.response_time_buckets),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }


# Global metrics collector
metrics_collector = MetricsCollector()


# ── Middleware ──────────────────────────────────────────────────────────────────

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Add correlation IDs to requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Request-ID"] = correlation_id
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests with structured format."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.time()
        correlation_id = getattr(request.state, "correlation_id", "unknown")

        try:
            response = await call_next(request)
        except Exception as exc:
            duration = (time.time() - start) * 1000
            logger.error(
                "Request failed",
                extra={
                    "correlation_id": correlation_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration, 2),
                    "error": str(exc),
                }
            )
            raise

        duration = (time.time() - start) * 1000
        status_code = response.status_code

        log_data = {
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "duration_ms": round(duration, 2),
            "user_agent": request.headers.get("user-agent"),
            "client_ip": request.headers.get("x-forwarded-for") or request.client.host if request.client else None,
        }

        if status_code >= 500:
            logger.error("Request completed with server error", extra=log_data)
        elif status_code >= 400:
            logger.warn("Request completed with client error", extra=log_data)
        else:
            logger.info("Request completed", extra=log_data)

        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """Collect metrics for all requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        metrics_collector.increment_active()
        start = time.time()

        try:
            response = await call_next(request)
        finally:
            duration = (time.time() - start) * 1000
            metrics_collector.decrement_active()
            metrics_collector.record_request(
                request.method,
                request.url.path,
                response.status_code if 'response' in dir() else 500,
                duration
            )

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none';"
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), "
            "gyroscope=(), magnetometer=(), microphone=(), "
            "payment=(), usb=()"
        )
        # Remove server fingerprinting
        if "server" in response.headers:
            del response.headers["server"]
        return response


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Add timeout protection to requests."""

    def __init__(self, app, timeout_seconds: float = 30.0):
        super().__init__(app)
        self.timeout_seconds = timeout_seconds

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        import asyncio
        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            correlation_id = getattr(request.state, "correlation_id", "unknown")
            logger.error(
                "Request timeout",
                extra={
                    "correlation_id": correlation_id,
                    "method": request.method,
                    "path": request.url.path,
                    "timeout_seconds": self.timeout_seconds,
                }
            )
            return JSONResponse(
                status_code=504,
                content={
                    "error": {
                        "code": "GATEWAY_TIMEOUT",
                        "message": f"Request timed out after {self.timeout_seconds}s",
                        "details": {"timeout_seconds": self.timeout_seconds},
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                    }
                }
            )


# ── Setup Functions ─────────────────────────────────────────────────────────────

def setup_robustness_middleware(
    app: FastAPI,
    service_name: str = "service",
    timeout_seconds: float = 30.0,
    version: str = "1.0.0",
    dependency_checks: Optional[List[Callable]] = None,
    custom_metrics: Optional[Dict[str, Any]] = None,
):
    """
    Setup all robustness middleware for a FastAPI application.

    This configures:
    - Correlation ID tracking
    - Request logging
    - Metrics collection
    - Security headers
    - Timeout protection
    - Standardized error handlers
    - Health check endpoints

    Args:
        app: FastAPI application instance
        service_name: Name of the service
        timeout_seconds: Request timeout in seconds
        version: Service version
        dependency_checks: List of dependency check functions
        custom_metrics: Additional metrics to include in health checks
    """

    # Add middleware in order (first added = first executed)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(TimeoutMiddleware, timeout_seconds=timeout_seconds)

    # Setup standardized error handlers
    setup_fastapi_error_handlers(app)

    # Setup health endpoints
    setup_health_endpoints(
        app,
        service_name=service_name,
        version=version,
        dependency_checks=dependency_checks,
        custom_metrics=custom_metrics,
    )

    # Add metrics endpoint
    @app.get("/metrics")
    async def metrics_endpoint():
        """Service metrics endpoint."""
        return metrics_collector.get_metrics()

    @app.get("/ready")
    async def ready_endpoint():
        """Readiness probe endpoint."""
        return {"ready": True, "timestamp": datetime.utcnow().isoformat() + "Z"}

    @app.get("/live")
    async def live_endpoint():
        """Liveness probe endpoint."""
        return {"alive": True, "timestamp": datetime.utcnow().isoformat() + "Z"}

    logger.info(f"Robustness middleware configured for {service_name}")
    return app


def get_correlation_id(request: Request) -> str:
    """Get correlation ID from request state."""
    return getattr(request.state, "correlation_id", "unknown")


def get_logger_with_correlation(request: Request):
    """Get a logger adapter with correlation ID."""
    correlation_id = get_correlation_id(request)

    class CorrelationLogger:
        def __init__(self, correlation_id: str):
            self.correlation_id = correlation_id

        def _log(self, level: str, msg: str, extra: Dict[str, Any] = None):
            extra = extra or {}
            extra["correlation_id"] = self.correlation_id
            getattr(logger, level)(msg, extra=extra)

        def debug(self, msg: str, extra: Dict[str, Any] = None):
            self._log("debug", msg, extra)

        def info(self, msg: str, extra: Dict[str, Any] = None):
            self._log("info", msg, extra)

        def warning(self, msg: str, extra: Dict[str, Any] = None):
            self._log("warning", msg, extra)

        def error(self, msg: str, extra: Dict[str, Any] = None):
            self._log("error", msg, extra)

        def critical(self, msg: str, extra: Dict[str, Any] = None):
            self._log("critical", msg, extra)

    return CorrelationLogger(correlation_id)
