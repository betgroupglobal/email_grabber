"""
Structured logging configuration for OpsecAI services.

Provides JSON-formatted logging with correlation IDs for request tracing.
"""
from __future__ import annotations

import logging
import json
import uuid
import time
from typing import Dict, Any, Optional
from datetime import datetime
from contextvars import ContextVar
import threading


# ── Context Variables for Request Tracking ─────────────────────────────────────

# Context variable for correlation ID (works with async/await)
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)


# ── Thread-local storage for synchronous contexts ────────────────────────────────

_thread_local = threading.local()


def get_correlation_id() -> str:
    """Get the current correlation ID."""
    # Try context variable first (async)
    cid = correlation_id_var.get()
    if cid:
        return cid
    
    # Fall back to thread-local (sync)
    return getattr(_thread_local, 'correlation_id', None) or str(uuid.uuid4())


def set_correlation_id(cid: Optional[str] = None):
    """Set the correlation ID for the current context."""
    if cid is None:
        cid = str(uuid.uuid4())
    
    # Set in both context variable and thread-local
    correlation_id_var.set(cid)
    _thread_local.correlation_id = cid
    
    return cid


def get_user_id() -> Optional[str]:
    """Get the current user ID."""
    return user_id_var.get()


def set_user_id(user_id: str):
    """Set the user ID for the current context."""
    user_id_var.set(user_id)
    _thread_local.user_id = user_id


def get_request_id() -> Optional[str]:
    """Get the current request ID."""
    return request_id_var.get()


def set_request_id(request_id: str):
    """Set the request ID for the current context."""
    request_id_var.set(request_id)
    _thread_local.request_id = request_id


# ── Structured JSON Formatter ─────────────────────────────────────────────────

class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def __init__(
        self,
        service_name: str = "opsecai",
        environment: str = "development",
        include_extra_fields: bool = True
    ):
        super().__init__()
        self.service_name = service_name
        self.environment = environment
        self.include_extra_fields = include_extra_fields
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Create base log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
            "environment": self.environment,
        }
        
        # Add context information
        correlation_id = get_correlation_id()
        if correlation_id:
            log_entry["correlation_id"] = correlation_id
        
        user_id = get_user_id()
        if user_id:
            log_entry["user_id"] = user_id
        
        request_id = get_request_id()
        if request_id:
            log_entry["request_id"] = request_id
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }
        
        # Add standard record attributes
        if hasattr(record, 'pathname'):
            log_entry["file"] = record.pathname
            log_entry["line"] = record.lineno
            log_entry["function"] = record.funcName
        
        # Add extra fields if enabled
        if self.include_extra_fields and hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        # Add any custom attributes
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                           'filename', 'module', 'lineno', 'funcName', 'created', 
                           'msecs', 'relativeCreated', 'thread', 'threadName', 
                           'processName', 'process', 'message', 'exc_info', 'exc_text', 
                           'stack_info', 'exc_info', 'extra_fields']:
                if not key.startswith('_'):
                    log_entry[key] = value
        
        return json.dumps(log_entry, default=str)


# ── Logging Configuration ───────────────────────────────────────────────────────

def setup_logging(
    service_name: str = "opsecai",
    environment: str = "development",
    log_level: str = "INFO",
    log_format: str = "json",
    enable_console: bool = True,
    enable_file: bool = False,
    log_file_path: Optional[str] = None
) -> logging.Logger:
    """
    Setup structured logging for a service.
    
    Args:
        service_name: Name of the service
        environment: Environment (development, staging, production)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format type (json or text)
        enable_console: Enable console logging
        enable_file: Enable file logging
        log_file_path: Path to log file (required if enable_file=True)
    
    Returns:
        Configured root logger
    """
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create formatter
    if log_format == "json":
        formatter = StructuredFormatter(
            service_name=service_name,
            environment=environment
        )
    else:
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # Add console handler
    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # Add file handler
    if enable_file:
        if not log_file_path:
            raise ValueError("log_file_path is required when enable_file=True")
        
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Configure specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    
    return root_logger


# ── Logging Context Manager ───────────────────────────────────────────────────

class LoggingContext:
    """Context manager for logging with automatic correlation ID management."""
    
    def __init__(
        self,
        correlation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        extra_fields: Optional[Dict[str, Any]] = None
    ):
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.user_id = user_id
        self.request_id = request_id
        self.extra_fields = extra_fields or {}
        self._token = None
        self._user_token = None
        self._request_token = None
    
    def __enter__(self):
        # Set context variables
        self._token = correlation_id_var.set(self.correlation_id)
        if self.user_id:
            self._user_token = user_id_var.set(self.user_id)
        if self.request_id:
            self._request_token = request_id_var.set(self.request_id)
        
        # Set thread-local
        _thread_local.correlation_id = self.correlation_id
        if self.user_id:
            _thread_local.user_id = self.user_id
        if self.request_id:
            _thread_local.request_id = self.request_id
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Reset context variables
        if self._token:
            correlation_id_var.reset(self._token)
        if self._user_token:
            user_id_var.reset(self._user_token)
        if self._request_token:
            request_id_var.reset(self._request_token)
        
        # Clear thread-local
        if hasattr(_thread_local, 'correlation_id'):
            delattr(_thread_local, 'correlation_id')
        if hasattr(_thread_local, 'user_id'):
            delattr(_thread_local, 'user_id')
        if hasattr(_thread_local, 'request_id'):
            delattr(_thread_local, 'request_id')
        
        return False


# ── Logging Helper Functions ───────────────────────────────────────────────────

def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)


def log_with_context(
    logger: logging.Logger,
    level: str,
    message: str,
    correlation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    **kwargs
):
    """Log a message with context information."""
    with LoggingContext(
        correlation_id=correlation_id,
        user_id=user_id
    ):
        log_level = getattr(logging, level.upper(), logging.INFO)
        logger.log(log_level, message, extra=kwargs)


def log_function_call(logger: logging.Logger, func_name: str, **kwargs):
    """Log a function call with parameters."""
    with LoggingContext():
        logger.info(f"Calling function: {func_name}", extra={
            "function": func_name,
            "parameters": kwargs
        })


def log_function_return(logger: logging.Logger, func_name: str, result=None, duration_ms: float = 0):
    """Log a function return with result and duration."""
    with LoggingContext():
        logger.info(f"Function returned: {func_name}", extra={
            "function": func_name,
            "duration_ms": duration_ms,
            "result": str(result)[:200] if result else None
        })


def log_function_error(logger: logging.Logger, func_name: str, error: Exception, duration_ms: float = 0):
    """Log a function error."""
    with LoggingContext():
        logger.error(f"Function error: {func_name}", extra={
            "function": func_name,
            "duration_ms": duration_ms,
            "error_type": type(error).__name__,
            "error_message": str(error)
        }, exc_info=True)