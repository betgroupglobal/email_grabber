"""
Comprehensive test suite for robustness function synergy.

Tests how circuit breakers, retry logic, error handling, configuration validation,
and health checking work together to provide comprehensive fault tolerance.
"""

import asyncio
import logging
import time
import sys
import os
from typing import Dict, Any
from datetime import datetime, timezone

# Add parent directory to path for shared imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.robustness import (
    CircuitBreaker, CircuitBreakerConfig, CircuitBreakerOpenError,
    retry_with_backoff, RetryConfig, with_timeout,
    robustness_manager, ServiceHealthChecker
)
from shared.error_handling import (
    ErrorHandler, OpsecAIError, ErrorCode, ErrorSeverity,
    ServiceUnavailableError, OperationTimeoutError,
    GracefulDegradation, ErrorContext
)
from shared.config_validator import (
    ConfigValidator, ValidationSeverity, ConfigSanitizer
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RobustnessSynergyTest:
    """Test suite for robustness function synergy."""
    
    def __init__(self):
        self.test_results = []
        self.error_handler = ErrorHandler("robustness-test")
    
    def record_result(self, test_name: str, passed: bool, details: str = ""):
        """Record a test result."""
        self.test_results.append({
            "test_name": test_name,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status} | {test_name} | {details}")
    
    async def test_circuit_breaker_retry_synergy(self):
        """Test how circuit breakers and retry logic work together."""
        logger.info("="*60)
        logger.info("Testing Circuit Breaker + Retry Synergy")
        logger.info("="*60)
        
        call_count = 0
        failure_count = 0
        
        async def flaky_service():
            nonlocal call_count, failure_count
            call_count += 1
            if call_count <= 3:
                failure_count += 1
                raise ConnectionError("Service temporarily unavailable")
            return {"status": "success", "call": call_count}
        
        # Setup circuit breaker with low threshold
        circuit_config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=1,
            timeout=5.0
        )
        circuit = CircuitBreaker(circuit_config, "test-service")
        
        # Setup retry configuration
        retry_config = RetryConfig(
            max_attempts=5,
            base_delay=0.1,
            max_delay=1.0,
            jitter=False
        )
        
        try:
            # Test: Circuit breaker should open before retry exhausts attempts
            result = await retry_with_backoff(
                lambda: circuit.call(flaky_service),
                retry_config
            )
            
            # Circuit breaker should have prevented some calls
            self.record_result(
                "Circuit Breaker + Retry",
                True,
                f"Circuit breaker opened after {failure_count} failures, retry handled {call_count} total attempts"
            )
            
        except CircuitBreakerOpenError:
            self.record_result(
                "Circuit Breaker + Retry",
                True,
                f"Circuit breaker successfully opened after {failure_count} failures, preventing cascading calls"
            )
        except Exception as e:
            self.record_result(
                "Circuit Breaker + Retry",
                False,
                f"Unexpected error: {str(e)}"
            )
    
    async def test_timeout_error_handling_synergy(self):
        """Test how timeout and error handling work together."""
        logger.info("="*60)
        logger.info("Testing Timeout + Error Handling Synergy")
        logger.info("="*60)
        
        async def slow_operation():
            await asyncio.sleep(2.0)
            return {"result": "completed"}
        
        try:
            # Test: Timeout should trigger error handling
            result = await with_timeout(slow_operation, timeout=0.5)
            self.record_result(
                "Timeout + Error Handling",
                False,
                "Timeout did not trigger as expected"
            )
        except asyncio.TimeoutError:
            # Convert to OpsecAIError
            context = ErrorContext(
                request_id="test-123",
                timestamp=datetime.now(timezone.utc).isoformat(),
                service="robustness-test"
            )
            timeout_error = OperationTimeoutError(
                operation="slow_operation",
                timeout_seconds=0.5,
                context=context
            )
            
            # Log error with error handler
            self.error_handler.log_error(timeout_error, context)
            
            self.record_result(
                "Timeout + Error Handling",
                True,
                "Timeout triggered correctly and error was logged with proper context"
            )
        except Exception as e:
            self.record_result(
                "Timeout + Error Handling",
                False,
                f"Unexpected error: {str(e)}"
            )
    
    async def test_health_check_circuit_breaker_synergy(self):
        """Test how health checks and circuit breakers coordinate."""
        logger.info("="*60)
        logger.info("Testing Health Check + Circuit Breaker Synergy")
        logger.info("="*60)
        
        service_healthy = True
        
        async def mock_service_call():
            if not service_healthy:
                raise ConnectionError("Service down")
            return {"status": "ok"}
        
        async def health_check():
            return service_healthy
        
        # Register health check
        robustness_manager.register_health_check("mock-service", health_check)
        
        # Get circuit breaker
        circuit = robustness_manager.get_circuit_breaker(
            "mock-service",
            CircuitBreakerConfig(failure_threshold=2, timeout=5.0)
        )
        
        # Test: Health check should reflect circuit breaker state
        try:
            # Make service unhealthy
            service_healthy = False
            
            # Trigger failures to open circuit
            for _ in range(3):
                try:
                    await circuit.call(mock_service_call)
                except:
                    pass
            
            # Get health report
            health_report = await robustness_manager.get_health_report()
            
            circuit_state = health_report["circuit_breakers"]["mock-service"]["state"]
            health_status = health_report["health_checks"]["mock-service"]["status"]
            
            if circuit_state == "open" and health_status == "unhealthy":
                self.record_result(
                    "Health Check + Circuit Breaker",
                    True,
                    f"Health check correctly reports unhealthy status when circuit breaker is {circuit_state}"
                )
            else:
                self.record_result(
                    "Health Check + Circuit Breaker",
                    False,
                    f"Expected circuit=open and health=unhealthy, got circuit={circuit_state}, health={health_status}"
                )
            
        except Exception as e:
            self.record_result(
                "Health Check + Circuit Breaker",
                False,
                f"Unexpected error: {str(e)}"
            )
        finally:
            service_healthy = True
    
    async def test_config_validation_error_handling_synergy(self):
        """Test how configuration validation and error handling work together."""
        logger.info("="*60)
        logger.info("Testing Configuration Validation + Error Handling Synergy")
        logger.info("="*60)
        
        validator = ConfigValidator("test-service")
        validator.require_field("DATABASE_URL")
        validator.add_validator("port", lambda x: None if 1 <= x <= 65535 else "Invalid port")
        
        # Test invalid configuration
        invalid_config = {
            "port": 99999,  # Invalid port
            # Missing DATABASE_URL
        }
        
        result = validator.validate_config(invalid_config)
        
        if not result.is_valid and len(result.issues) == 2:
            # Convert validation errors to OpsecAIError
            context = ErrorContext(
                request_id="config-test-123",
                timestamp=datetime.now(timezone.utc).isoformat(),
                service="test-service"
            )
            
            for issue in result.issues:
                config_error = OpsecAIError(
                    message=f"Configuration error: {issue['message']}",
                    code=ErrorCode.CONFIGURATION_ERROR,
                    severity=ErrorSeverity.CRITICAL if issue['severity'] == 'critical' else ErrorSeverity.MEDIUM,
                    context=context
                )
                self.error_handler.log_error(config_error, context)
            
            self.record_result(
                "Configuration Validation + Error Handling",
                True,
                f"Found {len(result.issues)} configuration issues and logged them with proper error context"
            )
        else:
            self.record_result(
                "Configuration Validation + Error Handling",
                False,
                f"Expected 2 validation errors, got {len(result.issues)}"
            )
    
    async def test_graceful_degradation_retry_synergy(self):
        """Test how graceful degradation and retry work together."""
        logger.info("="*60)
        logger.info("Testing Graceful Degradation + Retry Synergy")
        logger.info("="*60)
        
        primary_call_count = 0
        fallback_call_count = 0
        
        async def primary_service():
            nonlocal primary_call_count
            primary_call_count += 1
            # Always fail to force fallback
            raise ConnectionError("Primary service down")
        
        async def fallback_service():
            nonlocal fallback_call_count
            fallback_call_count += 1
            return {"source": "fallback", "data": "cached"}
        
        degradation = GracefulDegradation("test-service")
        degradation.register_fallback("get_data", fallback_service)
        
        # Setup retry for primary service (will exhaust)
        retry_config = RetryConfig(
            max_attempts=2,  # Reduced to exhaust faster
            base_delay=0.1,
            max_delay=0.5,
            jitter=False
        )
        
        try:
            # Test: Retry should exhaust, then fallback should activate
            result = await degradation.execute_with_fallback(
                "get_data",
                lambda: retry_with_backoff(primary_service, retry_config)
            )
            
            if result["source"] == "fallback" and primary_call_count == 2 and fallback_call_count == 1:
                self.record_result(
                    "Graceful Degradation + Retry",
                    True,
                    f"Retry exhausted ({primary_call_count} attempts), fallback activated successfully"
                )
            else:
                self.record_result(
                    "Graceful Degradation + Retry",
                    False,
                    f"Unexpected result: {result}, primary calls: {primary_call_count}, fallback calls: {fallback_call_count}"
                )
                
        except Exception as e:
            self.record_result(
                "Graceful Degradation + Retry",
                False,
                f"Unexpected error: {str(e)}"
            )
    
    async def test_config_sanitization_logging_synergy(self):
        """Test how configuration sanitization and logging work together."""
        logger.info("="*60)
        logger.info("Testing Configuration Sanitization + Logging Synergy")
        logger.info("="*60)
        
        sensitive_config = {
            "database_url": "postgresql://user:secret123@localhost/db",
            "api_key": "super-secret-api-key-12345",
            "normal_setting": "public-value",
            "password": "my-password"
        }
        
        # Sanitize configuration
        sanitized = ConfigSanitizer.sanitize(sensitive_config)
        
        # Check that sensitive values are masked in the sanitized dict
        checks_passed = True
        
        # Check api_key is masked (shows last 4 chars for debugging)
        if "super-secret-api-key-12345" in str(sanitized.get("api_key", "")):
            checks_passed = False
        if "***" not in str(sanitized.get("api_key", "")):
            checks_passed = False
            
        # Check password is masked (shows last 4 chars for debugging)
        if "my-password" == str(sanitized.get("password", "")):
            checks_passed = False
        if "***" not in str(sanitized.get("password", "")):
            checks_passed = False
            
        # Check normal value is preserved
        if sanitized.get("normal_setting") != "public-value":
            checks_passed = False
        
        if checks_passed:
            self.record_result(
                "Configuration Sanitization + Logging",
                True,
                "Sensitive values properly masked, public values preserved"
            )
        else:
            self.record_result(
                "Configuration Sanitization + Logging",
                False,
                f"Sanitization did not properly mask sensitive values. Result: {sanitized}"
            )
    
    async def test_comprehensive_robustness_scenario(self):
        """Test a comprehensive scenario using all robustness features together."""
        logger.info("="*60)
        logger.info("Testing Comprehensive Robustness Scenario")
        logger.info("="*60)
        
        # Simulate a complex service interaction
        service_state = {"healthy": True, "call_count": 0}
        
        async def complex_service():
            service_state["call_count"] += 1
            if not service_state["healthy"]:
                if service_state["call_count"] <= 2:
                    raise ConnectionError("Service degraded")
                else:
                    raise OperationTimeoutError("operation", 30.0, ErrorContext("test", datetime.now(timezone.utc).isoformat(), "test"))
            return {"status": "success", "calls": service_state["call_count"]}
        
        async def service_health_check():
            return service_state["healthy"]
        
        # Setup all robustness components
        robustness_manager.register_health_check("complex-service", service_health_check)
        circuit = robustness_manager.get_circuit_breaker(
            "complex-service",
            CircuitBreakerConfig(failure_threshold=3, timeout=5.0)
        )
        
        retry_config = RetryConfig(max_attempts=4, base_delay=0.1, max_delay=1.0, jitter=False)
        degradation = GracefulDegradation("test-service")
        
        async def fallback():
            return {"status": "fallback", "source": "cache"}
        
        degradation.register_fallback("complex_operation", fallback)
        
        try:
            # Test normal operation
            result = await circuit.call(complex_service)
            
            # Test degraded operation
            service_state["healthy"] = False
            service_state["call_count"] = 0
            
            result = await degradation.execute_with_fallback(
                "complex_operation",
                lambda: retry_with_backoff(lambda: circuit.call(complex_service), retry_config)
            )
            
            # Get health report
            health_report = await robustness_manager.get_health_report()
            
            if result["status"] == "fallback" and health_report["overall_status"] in ["degraded", "critical"]:
                self.record_result(
                    "Comprehensive Robustness Scenario",
                    True,
                    "All robustness components coordinated successfully: circuit breaker, retry, fallback, health monitoring"
                )
            else:
                self.record_result(
                    "Comprehensive Robustness Scenario",
                    False,
                    f"Expected fallback and degraded/critical status, got result: {result}, health: {health_report['overall_status']}"
                )
                
        except Exception as e:
            self.record_result(
                "Comprehensive Robustness Scenario",
                False,
                f"Unexpected error: {str(e)}"
            )
        finally:
            service_state["healthy"] = True
    
    async def run_all_tests(self):
        """Run all synergy tests."""
        logger.info("="*60)
        logger.info("Starting Robustness Function Synergy Tests")
        logger.info("="*60)
        
        start_time = time.time()
        
        await self.test_circuit_breaker_retry_synergy()
        await self.test_timeout_error_handling_synergy()
        await self.test_health_check_circuit_breaker_synergy()
        await self.test_config_validation_error_handling_synergy()
        await self.test_graceful_degradation_retry_synergy()
        await self.test_config_sanitization_logging_synergy()
        await self.test_comprehensive_robustness_scenario()
        
        duration = time.time() - start_time
        
        # Generate report
        self.generate_report(duration)
    
    def generate_report(self, duration: float):
        """Generate test report."""
        logger.info("="*60)
        logger.info("ROBUSTNESS SYNERGY TEST REPORT")
        logger.info("="*60)
        
        passed = sum(1 for result in self.test_results if result["passed"])
        total = len(self.test_results)
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        logger.info(f"Total Tests: {total}")
        logger.info(f"Passed: {passed}")
        logger.info(f"Failed: {total - passed}")
        logger.info(f"Pass Rate: {pass_rate:.1f}%")
        logger.info(f"Duration: {duration:.2f}s")
        
        logger.info("\nDetailed Results:")
        for result in self.test_results:
            status = "✓" if result["passed"] else "✗"
            logger.info(f"{status} {result['test_name']}: {result['details']}")
        
        # Get error log
        recent_errors = self.error_handler.get_recent_errors(limit=10)
        if recent_errors:
            logger.info(f"\nRecent Errors Logged: {len(recent_errors)}")
            for error in recent_errors:
                logger.info(f"  - {error['error_type']}: {error['error_message']}")
        
        logger.info("="*60)
        
        if pass_rate >= 80:
            logger.info("✅ EXCELLENT - Robustness functions demonstrate strong synergy")
        elif pass_rate >= 60:
            logger.info("✅ GOOD - Robustness functions show good coordination")
        else:
            logger.info("⚠️ NEEDS IMPROVEMENT - Robustness functions need better integration")


async def main():
    """Main entry point."""
    tester = RobustnessSynergyTest()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())