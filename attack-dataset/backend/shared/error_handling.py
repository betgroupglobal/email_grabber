"""
Enhanced error handling for OpsecAI services.

Provides standardized error responses, exception classes, and error recovery mechanisms.
"""

import logging
import traceback
import uuid
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime, timezone
from dataclasses import dataclass
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)


class ErrorCode(Enum):
    """Standardized error codes."""
    # General errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    RATE_LIMITED = "RATE_LIMITED"
    
    # Service dependency errors
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    DEPENDENCY_TIMEOUT = "DEPENDENCY_TIMEOUT"
    CIRCUIT_BREAKER_OPEN = "CIRCUIT_BREAKER_OPEN"
    
    # Validation errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_PARAMETER = "INVALID_PARAMETER"
    MISSING_PARAMETER = "MISSING_PARAMETER"
    
    # Operation errors
    OPERATION_TIMEOUT = "OPERATION_TIMEOUT"
    OPERATION_FAILED = "OPERATION_FAILED"
    OPERATION_CANCELLED = "OPERATION_CANCELLED"
    
    # Configuration errors
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    MISSING_CONFIGURATION = "MISSING_CONFIGURATION"
    
    # Resource errors
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    RESOURCE_LOCKED = "RESOURCE_LOCKED"


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorContext:
    """Context information for errors."""
    request_id: str
    timestamp: str
    service: str
    endpoint: Optional[str] = None
    user_id: Optional[str] = None
    additional_context: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.additional_context is None:
            self.additional_context = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error context to dictionary."""
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "service": self.service,
            "endpoint": self.endpoint,
            "user_id": self.user_id,
            "additional_context": self.additional_context
        }


class OpsecAIError(Exception):
    """Base exception for OpsecAI errors."""
    
    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        context: Optional[ErrorContext] = None
    ):
        self.message = message
        self.code = code
        self.severity = severity
        self.status_code = status_code
        self.details = details or {}
        self.context = context
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary."""
        error_dict = {
            "error": self.code.value,
            "message": self.message,
            "severity": self.severity.value,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if self.details:
            error_dict["details"] = self.details
        
        if self.context:
            error_dict["request_id"] = self.context.request_id
            error_dict["service"] = self.context.service
            if self.context.endpoint:
                error_dict["endpoint"] = self.context.endpoint
            if self.context.user_id:
                error_dict["user_id"] = self.context.user_id
            if self.context.additional_context:
                error_dict["context"] = self.context.additional_context
        
        return error_dict


class ServiceUnavailableError(OpsecAIError):
    """Raised when a service dependency is unavailable."""
    
    def __init__(
        self,
        service_name: str,
        message: Optional[str] = None,
        context: Optional[ErrorContext] = None
    ):
        if message is None:
            message = f"Service '{service_name}' is unavailable"
        super().__init__(
            message=message,
            code=ErrorCode.SERVICE_UNAVAILABLE,
            severity=ErrorSeverity.HIGH,
            status_code=503,
            details={"service": service_name},
            context=context
        )


class ValidationError(OpsecAIError):
    """Raised when input validation fails."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        context: Optional[ErrorContext] = None
    ):
        details = {}
        if field:
            details["field"] = field
        super().__init__(
            message=message,
            code=ErrorCode.VALIDATION_ERROR,
            severity=ErrorSeverity.LOW,
            status_code=400,
            details=details,
            context=context
        )


class OperationTimeoutError(OpsecAIError):
    """Raised when an operation times out."""
    
    def __init__(
        self,
        operation: str,
        timeout_seconds: float,
        context: Optional[ErrorContext] = None
    ):
        super().__init__(
            message=f"Operation '{operation}' timed out after {timeout_seconds}s",
            code=ErrorCode.OPERATION_TIMEOUT,
            severity=ErrorSeverity.HIGH,
            status_code=504,
            details={
                "operation": operation,
                "timeout_seconds": timeout_seconds
            },
            context=context
        )


class CircuitBreakerError(OpsecAIError):
    """Raised when circuit breaker is open."""
    
    def __init__(
        self,
        service_name: str,
        message: Optional[str] = None,
        retry_after: Optional[float] = None,
        context: Optional[ErrorContext] = None
    ):
        if message is None:
            message = f"Circuit breaker for '{service_name}' is open"
        details = {"service": service_name}
        if retry_after is not None:
            details["retry_after_seconds"] = retry_after
        
        super().__init__(
            message=message,
            code=ErrorCode.CIRCUIT_BREAKER_OPEN,
            severity=ErrorSeverity.HIGH,
            status_code=503,
            details=details,
            context=context
        )


class ErrorHandler:
    """Centralized error handler."""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.error_log: List[Dict[str, Any]] = []
        self.max_log_size = 1000
    
    def create_error_context(
        self,
        request: Request,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> ErrorContext:
        """Create error context from request."""
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        return ErrorContext(
            request_id=request_id,
            timestamp=datetime.utcnow().isoformat(),
            service=self.service_name,
            endpoint=f"{request.method} {request.url.path}",
            user_id=request.headers.get("X-User-ID"),
            additional_context=additional_context
        )
    
    def log_error(
        self,
        error: Exception,
        context: Optional[ErrorContext] = None,
        include_traceback: bool = True
    ):
        """Log error with context."""
        error_info = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context.to_dict() if context else None
        }
        
        if include_traceback:
            error_info["traceback"] = traceback.format_exc()
        
        # Add to in-memory log
        self.error_log.append(error_info)
        if len(self.error_log) > self.max_log_size:
            self.error_log.pop(0)
        
        # Log based on severity
        if isinstance(error, OpsecAIError):
            if error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
                logger.error(f"OpsecAI Error: {error.message}", extra=error_info)
            else:
                logger.warning(f"OpsecAI Error: {error.message}", extra=error_info)
        else:
            logger.error(f"Unexpected error: {str(error)}", extra=error_info)
    
    def handle_error(
        self,
        error: Exception,
        context: Optional[ErrorContext] = None
    ) -> JSONResponse:
        """Handle error and return appropriate response."""
        self.log_error(error, context)
        
        if isinstance(error, OpsecAIError):
            status_code = error.status_code
            response_data = error.to_dict()
        elif isinstance(error, HTTPException):
            status_code = error.status_code
            response_data = {
                "error": ErrorCode.INTERNAL_ERROR.value,
                "message": error.detail,
                "severity": ErrorSeverity.MEDIUM.value,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            status_code = 500
            response_data = {
                "error": ErrorCode.INTERNAL_ERROR.value,
                "message": "An unexpected error occurred",
                "severity": ErrorSeverity.HIGH.value,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            if context:
                response_data["request_id"] = context.request_id
        
        return JSONResponse(
            status_code=status_code,
            content=response_data
        )
    
    def get_recent_errors(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent errors from log."""
        return self.error_log[-limit:]
    
    def clear_error_log(self):
        """Clear error log."""
        self.error_log.clear()


def create_error_handler_middleware(service_name: str):
    """Create FastAPI middleware for error handling."""
    error_handler = ErrorHandler(service_name)
    
    async def middleware(request: Request, call_next):
        try:
            # Add request ID to state
            request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
            request.state.request_id = request_id
            
            response = await call_next(request)
            return response
        
        except Exception as e:
            context = error_handler.create_error_context(request)
            return error_handler.handle_error(e, context)
    
    return middleware


def handle_errors(service_name: str):
    """Decorator to handle errors in async functions."""
    error_handler = ErrorHandler(service_name)
    
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except OpsecAIError:
                raise  # Re-raise OpsecAI errors as-is
            except Exception as e:
                # Convert to OpsecAIError
                raise OpsecAIError(
                    message=str(e),
                    code=ErrorCode.INTERNAL_ERROR,
                    severity=ErrorSeverity.HIGH,
                    context=ErrorContext(
                        request_id=str(uuid.uuid4()),
                        timestamp=datetime.utcnow().isoformat(),
                        service=service_name
                    )
                )
        
        return wrapper
    
    return decorator


class GracefulDegradation:
    """Handle graceful degradation when services are unavailable."""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.fallback_handlers: Dict[str, callable] = {}
    
    def register_fallback(self, operation: str, handler: callable):
        """Register a fallback handler for an operation."""
        self.fallback_handlers[operation] = handler
    
    async def execute_with_fallback(
        self,
        operation: str,
        primary_func: callable,
        *args,
        **kwargs
    ):
        """
        Execute operation with fallback if primary fails.
        
        Args:
            operation: Operation name
            primary_func: Primary function to execute
            *args: Arguments for primary function
            **kwargs: Keyword arguments for primary function
            
        Returns:
            Result from primary or fallback function
            
        Raises:
            Exception if both primary and fallback fail
        """
        try:
            return await primary_func(*args, **kwargs)
        except Exception as primary_error:
            logger.warning(
                f"Primary function for '{operation}' failed: {primary_error}. "
                f"Attempting fallback..."
            )
            
            if operation in self.fallback_handlers:
                try:
                    fallback_result = await self.fallback_handlers[operation](*args, **kwargs)
                    logger.info(f"Fallback for '{operation}' succeeded")
                    return fallback_result
                except Exception as fallback_error:
                    logger.error(
                        f"Both primary and fallback for '{operation}' failed. "
                        f"Primary: {primary_error}, Fallback: {fallback_error}"
                    )
                    raise
            else:
                logger.error(f"No fallback registered for '{operation}'")
                raise primary_error


# Global error handler instances (will be initialized per service)
_error_handlers: Dict[str, ErrorHandler] = {}


def get_error_handler(service_name: str) -> ErrorHandler:
    """Get or create error handler for service."""
    if service_name not in _error_handlers:
        _error_handlers[service_name] = ErrorHandler(service_name)
    return _error_handlers[service_name]