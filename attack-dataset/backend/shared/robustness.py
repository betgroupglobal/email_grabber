"""
Shared robustness utilities for OpsecAI services.

Provides retry logic, circuit breakers, timeout handling, and error recovery mechanisms.
"""

import asyncio
import logging
import time
from typing import Callable, Optional, TypeVar, Any, Dict, List, Awaitable
from functools import wraps
from dataclasses import dataclass, field
from enum import Enum
import random

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5        # Open circuit after N failures
    success_threshold: int = 2        # Close circuit after N successes in half-open
    timeout: float = 60.0             # Seconds to wait before trying half-open
    exception_types: tuple = (Exception,)  # Exceptions that trigger failures


@dataclass
class RetryConfig:
    """Configuration for retry logic."""
    max_attempts: int = 3
    base_delay: float = 1.0           # Base delay in seconds
    max_delay: float = 30.0           # Maximum delay in seconds
    exponential_base: float = 2.0     # Exponential backoff multiplier
    jitter: bool = True               # Add random jitter to prevent thundering herd
    retryable_exceptions: tuple = (Exception,)  # Exceptions that should trigger retry


@dataclass
class TimeoutConfig:
    """Configuration for timeout handling."""
    default_timeout: float = 30.0     # Default timeout in seconds
    per_operation_timeouts: Dict[str, float] = field(default_factory=dict)


class CircuitBreaker:
    """Circuit breaker implementation to prevent cascading failures."""
    
    def __init__(self, config: CircuitBreakerConfig, name: str = "circuit"):
        self.config = config
        self.name = name
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time >= self.config.timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    logger.info(f"Circuit breaker '{self.name}' transitioned to HALF_OPEN")
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Try again in {self.config.timeout - (time.time() - self.last_failure_time):.1f}s"
                    )
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except self.config.exception_types as e:
            await self._on_failure()
            raise
    
    async def _on_success(self):
        """Handle successful execution."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    logger.info(f"Circuit breaker '{self.name}' transitioned to CLOSED")
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0
    
    async def _on_failure(self):
        """Handle failed execution."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                logger.warning(f"Circuit breaker '{self.name}' transitioned to OPEN (half-open failure)")
            elif self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker '{self.name}' transitioned to OPEN "
                    f"(threshold: {self.config.failure_threshold} failures)"
                )
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


async def retry_with_backoff(
    func: Callable[..., T],
    config: RetryConfig,
    *args,
    **kwargs
) -> T:
    """
    Execute function with retry logic and exponential backoff.
    
    Args:
        func: Async function to execute
        config: Retry configuration
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func
        
    Returns:
        Result of func execution
        
    Raises:
        Last exception if all retries exhausted
    """
    last_exception = None
    
    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)
        except config.retryable_exceptions as e:
            last_exception = e
            
            if attempt < config.max_attempts - 1:
                delay = _calculate_delay(config, attempt)
                logger.warning(
                    f"Retry attempt {attempt + 1}/{config.max_attempts} failed: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"All {config.max_attempts} retry attempts exhausted. "
                    f"Last error: {e}"
                )
    
    raise last_exception


def _calculate_delay(config: RetryConfig, attempt: int) -> float:
    """Calculate delay with exponential backoff and optional jitter."""
    delay = min(
        config.base_delay * (config.exponential_base ** attempt),
        config.max_delay
    )
    
    if config.jitter:
        # Add up to 25% random jitter
        delay = delay * (0.75 + random.random() * 0.5)
    
    return delay


async def with_timeout(
    func: Callable[..., T],
    timeout: float,
    *args,
    **kwargs
) -> T:
    """
    Execute function with timeout.
    
    Args:
        func: Async function to execute
        timeout: Timeout in seconds
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func
        
    Returns:
        Result of func execution
        
    Raises:
        asyncio.TimeoutError if timeout exceeded
    """
    try:
        return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(f"Operation timed out after {timeout}s")
        raise


def circuit_breaker(
    name: str = "circuit",
    failure_threshold: int = 5,
    success_threshold: int = 2,
    timeout: float = 60.0,
    exception_types: tuple = (Exception,)
):
    """
    Decorator to apply circuit breaker to async function.
    
    Args:
        name: Circuit breaker name
        failure_threshold: Open circuit after N failures
        success_threshold: Close circuit after N successes in half-open
        timeout: Seconds to wait before trying half-open
        exception_types: Exceptions that trigger failures
    """
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        success_threshold=success_threshold,
        timeout=timeout,
        exception_types=exception_types
    )
    circuit = CircuitBreaker(config, name)
    
    def decorator(func: Callable[..., T]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await circuit.call(func, *args, **kwargs)
        
        # Attach circuit breaker to function for inspection
        wrapper._circuit_breaker = circuit
        return wrapper
    
    return decorator


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple = (Exception,)
):
    """
    Decorator to apply retry logic with exponential backoff to async function.
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Exponential backoff multiplier
        jitter: Add random jitter to prevent thundering herd
        retryable_exceptions: Exceptions that should trigger retry
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        retryable_exceptions=retryable_exceptions
    )
    
    def decorator(func: Callable[..., T]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_with_backoff(func, config, *args, **kwargs)
        
        return wrapper
    
    return decorator


def timeout(seconds: float = 30.0):
    """
    Decorator to apply timeout to async function.
    
    Args:
        seconds: Timeout in seconds
    """
    def decorator(func: Callable[..., T]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await with_timeout(func, seconds, *args, **kwargs)
        
        return wrapper
    
    return decorator


class ServiceHealthChecker:
    """Health checker for service dependencies."""
    
    def __init__(self):
        self.checks: Dict[str, Callable[[], Awaitable[bool]]] = {}
    
    def register_check(self, name: str, check_func: Callable[[], Awaitable[bool]]):
        """Register a health check function."""
        self.checks[name] = check_func
    
    async def check_all(self) -> Dict[str, Dict[str, Any]]:
        """Execute all health checks."""
        results = {}
        
        for name, check_func in self.checks.items():
            try:
                start_time = time.time()
                is_healthy = await check_func()
                duration = (time.time() - start_time) * 1000
                
                results[name] = {
                    "status": "healthy" if is_healthy else "unhealthy",
                    "duration_ms": round(duration, 2)
                }
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return results
    
    async def check_single(self, name: str) -> Dict[str, Any]:
        """Execute a single health check."""
        if name not in self.checks:
            raise ValueError(f"Health check '{name}' not registered")
        
        try:
            start_time = time.time()
            is_healthy = await self.checks[name]()
            duration = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy" if is_healthy else "unhealthy",
                "duration_ms": round(duration, 2)
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }


class RobustnessManager:
    """Central manager for robustness features."""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.health_checker = ServiceHealthChecker()
    
    def get_circuit_breaker(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """Get or create circuit breaker."""
        if name not in self.circuit_breakers:
            if config is None:
                config = CircuitBreakerConfig()
            self.circuit_breakers[name] = CircuitBreaker(config, name)
        return self.circuit_breakers[name]
    
    def register_health_check(
        self,
        name: str,
        check_func: Callable[[], Awaitable[bool]]
    ):
        """Register a health check."""
        self.health_checker.register_check(name, check_func)
    
    async def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report."""
        health_results = await self.health_checker.check_all()
        
        circuit_states = {
            name: breaker.get_state()
            for name, breaker in self.circuit_breakers.items()
        }
        
        # Calculate overall health
        all_healthy = all(
            result.get("status") == "healthy"
            for result in health_results.values()
        )
        
        any_circuit_open = any(
            state["state"] == CircuitState.OPEN.value
            for state in circuit_states.values()
        )
        
        overall_status = "healthy"
        if not all_healthy:
            overall_status = "degraded"
        if any_circuit_open:
            overall_status = "critical"
        
        return {
            "overall_status": overall_status,
            "health_checks": health_results,
            "circuit_breakers": circuit_states,
            "timestamp": time.time()
        }


# Global robustness manager instance
robustness_manager = RobustnessManager()