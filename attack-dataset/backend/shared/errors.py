"""
Standardized error handling for OpsecAI services.

Provides consistent error responses, error types, and error handling middleware.
"""
from __future__ import annotations

from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime
import traceback


# ── Error Types ─────────────────────────────────────────────────────────────────

class ErrorCode(str, Enum):
    """Standardized error codes across all services."""
    
    # Authentication & Authorization
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    
    # Validation
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_FORMAT = "INVALID_FORMAT"
    
    # Resource Not Found
    NOT_FOUND = "NOT_FOUND"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    ENGAGEMENT_NOT_FOUND = "ENGAGEMENT_NOT_FOUND"
    
    # Conflict & Duplication
    CONFLICT = "CONFLICT"
    RESOURCE_ALREADY_EXISTS = "RESOURCE_ALREADY_EXISTS"
    DUPLICATE_ENTRY = "DUPLICATE_ENTRY"
    
    # Rate Limiting
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    TOO_MANY_REQUESTS = "TOO_MANY_REQUESTS"
    
    # Service Errors
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    DEPENDENCY_ERROR = "DEPENDENCY_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    
    # Business Logic
    BUSINESS_LOGIC_ERROR = "BUSINESS_LOGIC_ERROR"
    INVALID_STATE = "INVALID_STATE"
    OPERATION_NOT_ALLOWED = "OPERATION_NOT_ALLOWED"
    
    # System Errors
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ── Custom Exception Classes ───────────────────────────────────────────────────

class OpsecAIError(Exception):
    """Base exception for all OpsecAI errors."""
    
    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.INTERNAL_SERVER_ERROR,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        internal_message: Optional[str] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        self.severity = severity
        self.internal_message = internal_message or message
        self.timestamp = datetime.utcnow()
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for API responses."""
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "details": self.details,
                "timestamp": self.timestamp.isoformat(),
            }
        }
    
    def to_internal_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for internal logging."""
        return {
            "code": self.code.value,
            "message": self.internal_message,
            "severity": self.severity.value,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "traceback": traceback.format_exc()
        }


class AuthenticationError(OpsecAIError):
    """Authentication related errors."""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            code=ErrorCode.UNAUTHORIZED,
            status_code=401,
            details=details,
            severity=ErrorSeverity.HIGH
        )


class AuthorizationError(OpsecAIError):
    """Authorization related errors."""
    
    def __init__(
        self,
        message: str = "Insufficient permissions",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            code=ErrorCode.FORBIDDEN,
            status_code=403,
            details=details,
            severity=ErrorSeverity.HIGH
        )


class ValidationError(OpsecAIError):
    """Validation related errors."""
    
    def __init__(
        self,
        message: str = "Validation failed",
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if field:
            details = details or {}
            details["field"] = field
        
        super().__init__(
            message=message,
            code=ErrorCode.VALIDATION_ERROR,
            status_code=400,
            details=details,
            severity=ErrorSeverity.LOW
        )


class NotFoundError(OpsecAIError):
    """Resource not found errors."""
    
    def __init__(
        self,
        message: str = "Resource not found",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id
        
        super().__init__(
            message=message,
            code=ErrorCode.NOT_FOUND,
            status_code=404,
            details=details,
            severity=ErrorSeverity.LOW
        )


class ConflictError(OpsecAIError):
    """Conflict / duplicate resource errors."""
    
    def __init__(
        self,
        message: str = "Resource conflict",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            code=ErrorCode.CONFLICT,
            status_code=409,
            details=details,
            severity=ErrorSeverity.MEDIUM
        )


class RateLimitError(OpsecAIError):
    """Rate limiting errors."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if retry_after:
            details["retry_after"] = retry_after
        
        super().__init__(
            message=message,
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            status_code=429,
            details=details,
            severity=ErrorSeverity.MEDIUM
        )


class ServiceUnavailableError(OpsecAIError):
    """Service unavailable errors."""
    
    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        service_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if service_name:
            details["service"] = service_name
        
        super().__init__(
            message=message,
            code=ErrorCode.SERVICE_UNAVAILABLE,
            status_code=503,
            details=details,
            severity=ErrorSeverity.HIGH
        )


class DatabaseError(OpsecAIError):
    """Database related errors."""
    
    def __init__(
        self,
        message: str = "Database operation failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            code=ErrorCode.DATABASE_ERROR,
            status_code=500,
            details=details,
            severity=ErrorSeverity.CRITICAL,
            internal_message=f"Database error: {details.get('original_error', 'unknown') if details else 'unknown'}"
        )


# ── Error Handler Functions ─────────────────────────────────────────────────────

def handle_exception(exc: Exception) -> OpsecAIError:
    """Convert any exception to an OpsecAIError."""
    if isinstance(exc, OpsecAIError):
        return exc
    
    # Handle common Python exceptions
    if isinstance(exc, ValueError):
        return ValidationError(
            message=str(exc),
            details={"original_error": type(exc).__name__}
        )
    
    if isinstance(exc, KeyError):
        return ValidationError(
            message=f"Missing required field: {exc}",
            details={"missing_field": str(exc)}
        )
    
    if isinstance(exc, PermissionError):
        return AuthorizationError(
            message=str(exc),
            details={"original_error": type(exc).__name__}
        )
    
    # Default to internal server error
    return OpsecAIError(
        message="An unexpected error occurred",
        code=ErrorCode.INTERNAL_SERVER_ERROR,
        status_code=500,
        details={"original_error": type(exc).__name__},
        internal_message=str(exc)
    )


def create_error_response(
    error: OpsecAIError,
    include_internal: bool = False
) -> Dict[str, Any]:
    """Create standardized error response."""
    if include_internal:
        return error.to_internal_dict()
    else:
        return error.to_dict()


# ── Error Context Manager ───────────────────────────────────────────────────────

class ErrorHandler:
    """Context manager for handling errors consistently."""
    
    def __init__(
        self,
        error_map: Optional[Dict[type, type[OpsecAIError]]] = None,
        default_message: str = "An error occurred",
        reraise: bool = True
    ):
        self.error_map = error_map or {}
        self.default_message = default_message
        self.reraise = reraise
        self.error: Optional[OpsecAIError] = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            return True
        
        # Map exception type to OpsecAIError
        error_class = self.error_map.get(exc_type, None)
        if error_class:
            self.error = error_class(
                message=str(exc_val),
                details={"original_error": type(exc_val).__name__}
            )
        else:
            self.error = handle_exception(exc_val)
        
        if self.reraise:
            raise self.error
        
        return True  # Suppress the original exception


# ── FastAPI Error Handler ───────────────────────────────────────────────────────

def setup_fastapi_error_handlers(app):
    """Setup standardized error handlers for FastAPI application."""
    from fastapi import Request
    from fastapi.responses import JSONResponse
    
    @app.exception_handler(OpsecAIError)
    async def opsecai_error_handler(request: Request, exc: OpsecAIError):
        """Handle OpsecAIError exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content=create_error_response(exc),
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle all other exceptions."""
        opsecai_error = handle_exception(exc)
        return JSONResponse(
            status_code=opsecai_error.status_code,
            content=create_error_response(opsecai_error),
        )
    
    return app


# ── Error Logging ───────────────────────────────────────────────────────────────

import logging

error_logger = logging.getLogger("errors")

def log_error(
    error: OpsecAIError,
    context: Optional[Dict[str, Any]] = None,
    level: str = "ERROR"
):
    """Log error with context."""
    log_data = error.to_internal_dict()
    if context:
        log_data["context"] = context
    
    log_level = getattr(logging, level.upper(), logging.ERROR)
    error_logger.log(log_level, str(error), extra={"error_data": log_data})