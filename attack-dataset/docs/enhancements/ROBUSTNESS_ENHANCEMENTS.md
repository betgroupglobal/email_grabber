# OpsecAI Robustness Enhancements

## Overview

This document describes the comprehensive robustness enhancements implemented across the OpsecAI platform to improve system reliability, fault tolerance, and operational resilience.

## Enhancements Summary

### 1. Shared Robustness Library (`backend/shared/robustness.py`)

A comprehensive library providing enterprise-grade robustness patterns:

#### Circuit Breaker Pattern
- **Purpose**: Prevent cascading failures by automatically stopping calls to failing services
- **Features**:
  - Three states: CLOSED (normal), OPEN (rejecting requests), HALF_OPEN (testing recovery)
  - Configurable failure thresholds and recovery timeouts
  - Automatic state transitions based on success/failure rates
  - Per-service circuit breaker instances

```python
# Example usage
from shared.robustness import robustness_manager, CircuitBreakerConfig

# Get or create circuit breaker
postgres_circuit = robustness_manager.get_circuit_breaker(
    "postgres",
    CircuitBreakerConfig(failure_threshold=3, timeout=30.0)
)

# Execute with circuit breaker protection
result = await postgres_circuit.call(database_function, *args)
```

#### Retry Logic with Exponential Backoff
- **Purpose**: Automatically retry failed operations with intelligent delay
- **Features**:
  - Configurable max attempts and delay parameters
  - Exponential backoff to prevent overwhelming services
  - Random jitter to prevent thundering herd problems
  - Configurable retryable exception types

```python
# Example usage
from shared.robustness import retry_with_backoff, RetryConfig

config = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True
)

result = await retry_with_backoff(api_call, config, *args, **kwargs)
```

#### Timeout Handling
- **Purpose**: Prevent operations from hanging indefinitely
- **Features**:
  - Per-operation timeout configuration
  - Automatic timeout exception handling
  - Configurable default timeouts

```python
# Example usage
from shared.robustness import with_timeout

result = await with_timeout(long_running_operation, timeout=30.0, *args, **kwargs)
```

#### Decorators for Easy Integration
- `@circuit_breaker()`: Apply circuit breaker to async functions
- `@retry()`: Apply retry logic to async functions
- `@timeout()`: Apply timeout to async functions

```python
from shared.robustness import circuit_breaker, retry, timeout

@retry(max_attempts=3, base_delay=1.0)
@circuit_breaker(name="external_api", failure_threshold=5)
@timeout(seconds=30.0)
async def call_external_service(data):
    # Function will automatically retry, timeout, and circuit break
    return await external_api.call(data)
```

#### Service Health Checker
- **Purpose**: Centralized health monitoring for service dependencies
- **Features**:
  - Register health check functions for each dependency
  - Execute all health checks in parallel
  - Detailed timing and status reporting
  - Integration with circuit breaker status

```python
from shared.robustness import robustness_manager

async def check_database():
    try:
        # Database health check logic
        return True
    except Exception:
        return False

robustness_manager.register_health_check("database", check_database)
health_report = await robustness_manager.get_health_report()
```

### 2. Enhanced Error Handling (`backend/shared/error_handling.py`)

Standardized error handling with comprehensive error context:

#### Standardized Error Codes
- `INTERNAL_ERROR`: Generic internal errors
- `SERVICE_UNAVAILABLE`: Dependency service failures
- `CIRCUIT_BREAKER_OPEN`: Circuit breaker triggered
- `VALIDATION_ERROR`: Input validation failures
- `OPERATION_TIMEOUT`: Operation timeout
- `CONFIGURATION_ERROR`: Configuration issues

#### Error Severity Levels
- `LOW`: Minor issues that don't affect functionality
- `MEDIUM`: Issues that partially affect functionality
- `HIGH`: Major issues that significantly impact functionality
- `CRITICAL`: Critical issues that prevent service operation

#### Error Context Tracking
- Request ID for distributed tracing
- Timestamp for error correlation
- Service and endpoint identification
- User context when available
- Additional contextual information

```python
from shared.error_handling import (
    ErrorHandler, OpsecAIError, ErrorCode, ErrorSeverity,
    ServiceUnavailableError, OperationTimeoutError
)

# Create error handler
error_handler = ErrorHandler("my-service")

# Handle errors with context
try:
    result = await risky_operation()
except Exception as e:
    context = error_handler.create_error_context(request)
    return error_handler.handle_error(e, context)
```

#### Graceful Degradation
- **Purpose**: Provide fallback functionality when primary services fail
- **Features**:
  - Register fallback handlers for operations
  - Automatic fallback on primary failure
  - Fallback success/failure logging

```python
from shared.error_handling import GracefulDegradation

degradation = GracefulDegradation("my-service")

# Register fallback
async def cache_fallback(key):
    return await cache.get(key)

degradation.register_fallback("get_data", cache_fallback)

# Execute with fallback
result = await degradation.execute_with_fallback(
    "get_data",
    primary_database_call,
    "user_123"
)
```

### 3. Configuration Validation (`backend/shared/config_validator.py`)

Runtime configuration validation to prevent misconfiguration:

#### Configuration Validator
- **Purpose**: Validate configuration at startup and runtime
- **Features**:
  - Required field validation
  - Type and format validation
  - Custom validator functions
  - Default value handling
  - Severity-based issue reporting

```python
from shared.config_validator import ConfigValidator, ValidationSeverity

validator = ConfigValidator("my-service")
validator.require_field("DATABASE_URL")
validator.add_validator("port", lambda x: None if 1 <= x <= 65535 else "Invalid port")

result = validator.validate_config(config_dict)
if not result.is_valid:
    for issue in result.issues:
        print(f"{issue['severity']}: {issue['message']}")
```

#### Common Validators
- Port validation (1-65535)
- URL validation (http://, https://)
- Timeout validation (positive numbers)
- API key validation (minimum length)
- Log level validation
- Environment validation (development/staging/production)

#### Configuration Sanitization
- **Purpose**: Remove sensitive values from logs and error messages
- **Features**:
  - Automatic detection of sensitive keys
  - Configurable sensitive key patterns
  - Safe logging of configuration

```python
from shared.config_validator import ConfigSanitizer

# Sanitize configuration for logging
safe_config = ConfigSanitizer.sanitize(config_dict)
logger.info(f"Configuration: {safe_config}")
```

### 4. Knowledge Engine Integration

The Knowledge Engine has been enhanced with comprehensive robustness features:

#### Startup Configuration Validation
- Validates required environment variables
- Checks configuration format and types
- Prevents startup with invalid configuration
- Provides clear error messages for configuration issues

#### Circuit Breaker Setup
- **PostgreSQL Circuit**: Protects against database failures
- **Qdrant Circuit**: Protects against vector database failures
- **OpenRouter Circuit**: Protects against AI API failures
- Configurable thresholds and timeouts per service

#### Enhanced Health Monitoring
- Comprehensive health check endpoint
- Circuit breaker status monitoring
- Dependency health tracking
- Robustness metrics reporting

#### New Endpoints
- `GET /health`: Enhanced health check with circuit breaker status
- `GET /robustness`: Detailed robustness metrics and error logs
- `POST /robustness/errors/clear`: Clear error logs (admin)

#### Error Handling Middleware
- Automatic error context tracking
- Standardized error responses
- Request ID generation for distributed tracing
- Comprehensive error logging

## Usage Examples

### Basic Circuit Breaker Usage

```python
from shared.robustness import robustness_manager, CircuitBreakerConfig

# Setup circuit breaker
circuit = robustness_manager.get_circuit_breaker(
    "external_api",
    CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=2,
        timeout=60.0
    )
)

# Use circuit breaker
try:
    result = await circuit.call(external_api_function, data)
except CircuitBreakerOpenError as e:
    logger.error(f"Circuit breaker is open: {e}")
    # Handle fallback or error response
```

### Retry with Decorator

```python
from shared.robustness import retry

@retry(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    retryable_exceptions=(ConnectionError, TimeoutError)
)
async def call_external_api(data):
    # Will automatically retry on connection/timeout errors
    return await http_client.post(url, json=data)
```

### Comprehensive Error Handling

```python
from shared.error_handling import (
    ErrorHandler, OpsecAIError, ErrorCode, ErrorSeverity,
    create_error_handler_middleware
)

# Setup error handling middleware
app.middleware("http")(create_error_handler_middleware("my-service"))

# In your endpoints
@handle_errors("my-service")
async def my_endpoint(request: Request):
    # Errors are automatically caught and converted to OpsecAIError
    return {"data": "success"}
```

### Configuration Validation

```python
from shared.config_validator import ConfigValidator, validate_service_config

# Validate configuration
config = {
    "DATABASE_URL": "postgresql://localhost/mydb",
    "API_PORT": 8000,
    "LOG_LEVEL": "INFO"
}

result = validate_service_config(
    "my-service",
    config,
    required_fields=["DATABASE_URL", "API_PORT"],
    optional_fields={"LOG_LEVEL": "INFO"}
)

if not result.is_valid:
    for issue in result.issues:
        print(f"{issue['severity']}: {issue['field']} - {issue['message']}")
```

## Benefits

### Reliability Improvements
1. **Cascading Failure Prevention**: Circuit breakers prevent system-wide failures
2. **Automatic Recovery**: Retry logic handles transient failures automatically
3. **Graceful Degradation**: System continues operating with reduced functionality
4. **Configuration Safety**: Validation prevents misconfiguration issues

### Operational Benefits
1. **Better Monitoring**: Enhanced health checks provide deep visibility
2. **Error Tracking**: Comprehensive error logging with context
3. **Debugging Support**: Request IDs and error correlation
4. **Operational Insights**: Robustness metrics for capacity planning

### Developer Experience
1. **Easy Integration**: Decorators and utility functions simplify usage
2. **Consistent Patterns**: Standardized approach across all services
3. **Clear Documentation**: Comprehensive usage examples
4. **Type Safety**: Full type hints for better IDE support

## Testing

### Unit Testing
```python
import pytest
from shared.robustness import CircuitBreaker, CircuitBreakerConfig

@pytest.mark.asyncio
async def test_circuit_breaker_opens_on_failures():
    config = CircuitBreakerConfig(failure_threshold=3, timeout=60.0)
    circuit = CircuitBreaker(config, "test")
    
    async def failing_function():
        raise Exception("Test failure")
    
    # Trigger failures
    for _ in range(3):
        with pytest.raises(Exception):
            await circuit.call(failing_function)
    
    # Circuit should now be open
    with pytest.raises(CircuitBreakerOpenError):
        await circuit.call(failing_function)
```

### Integration Testing
```python
import pytest
from fastapi.testclient import TestClient
from api import app

client = TestClient(app)

def test_enhanced_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "robustness" in data["components"]
    assert "circuit_breakers" in data["components"]["robustness"]

def test_robustness_metrics():
    response = client.get("/robustness")
    assert response.status_code == 200
    data = response.json()
    assert "health_report" in data
    assert "recent_errors" in data
```

## Migration Guide

### For Existing Services

1. **Add Imports**:
```python
from shared.robustness import robustness_manager, CircuitBreakerConfig, RetryConfig
from shared.error_handling import ErrorHandler, create_error_handler_middleware
from shared.config_validator import ConfigValidator
```

2. **Initialize in Lifespan**:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize error handler
    error_handler = ErrorHandler("service-name")
    
    # Setup circuit breakers
    robustness_manager.get_circuit_breaker("dependency", CircuitBreakerConfig())
    
    # Register health checks
    robustness_manager.register_health_check("dependency", check_function)
    
    yield
```

3. **Add Middleware**:
```python
app.middleware("http")(create_error_handler_middleware("service-name"))
```

4. **Update Health Check**:
```python
@app.get("/health")
async def health_check():
    health_report = await robustness_manager.get_health_report()
    return {"status": health_report["overall_status"], "details": health_report}
```

## Future Enhancements

### Planned Features
1. **Distributed Tracing**: Integration with OpenTelemetry for end-to-end tracing
2. **Metrics Collection**: Prometheus metrics export for monitoring dashboards
3. **Rate Limiting**: Per-service rate limiting to prevent overload
4. **Connection Pooling**: Enhanced connection management for databases
5. **Load Balancing**: Client-side load balancing for service calls
6. **Service Discovery**: Dynamic service discovery and health-based routing

### Performance Optimization
1. **Async Circuit Breakers**: Fully async circuit breaker implementation
2. **Bulkhead Pattern**: Isolated thread pools for different operations
3. **Cache Integration**: Automatic caching for circuit-open responses
4. **Adaptive Timeouts**: Machine learning-based timeout optimization

## Monitoring and Alerting

### Key Metrics to Monitor
- Circuit breaker state changes
- Retry attempt counts and success rates
- Error rates by severity and type
- Health check failure rates
- Operation timeout rates

### Recommended Alerts
- Circuit breaker OPEN state
- High error rates (> 5%)
- Health check failures
- Configuration validation failures

## Conclusion

These robustness enhancements significantly improve the OpsecAI platform's reliability and operational resilience. The shared libraries provide consistent patterns across all services, while the comprehensive error handling and monitoring capabilities ensure quick detection and recovery from issues.

The modular design allows for easy adoption across existing services and provides a solid foundation for future enhancements.

## Related Documentation

- [AGENTS.md](../guides/AGENTS.md) - Main project documentation
- [ENHANCED_MONITORING_DESIGN.md](ENHANCED_MONITORING_DESIGN.md) - Monitoring system design
- [MAJOR_ENHANCEMENT_PLAN.md](../architecture/MAJOR_ENHANCEMENT_PLAN.md) - Overall enhancement roadmap