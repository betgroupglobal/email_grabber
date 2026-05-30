#!/usr/bin/env python3
"""
OpsecAI - Comprehensive Live Endpoint Testing
Tests all service endpoints to verify functionality
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

# Service endpoints configuration
SERVICES = {
    "knowledge_engine": {
        "base_url": "http://localhost:8000",
        "health_endpoint": "/health",
        "endpoints": [
            {"path": "/health", "method": "GET", "description": "Health check"},
            {"path": "/search", "method": "POST", "description": "Semantic search", "body": {"query": "test attack"}},
            {"path": "/attack-vector", "method": "POST", "description": "Build attack chains", "body": {"target":"127.0.0.1","ip":"127.0.0.1","os":"unknown"}},
            {"path": "/categories", "method": "GET", "description": "Get categories"},
            {"path": "/ai/status", "method": "GET", "description": "AI provider status"},
            {"path": "/ml/status", "method": "GET", "description": "ML service status"}
        ]
    },
    "opsec_monitor": {
        "base_url": "http://localhost:8002",
        "health_endpoint": "/health",
        "endpoints": [
            {"path": "/health", "method": "GET", "description": "Health check"},
            {"path": "/assess", "method": "POST", "description": "Assess attack", "body": {"attack_steps":"test","tools_used":"test"}},
        ]
    },
    "realtime_analyzer": {
        "base_url": "http://localhost:8001",
        "health_endpoint": "/health",
        "endpoints": [
            {"path": "/health", "method": "GET", "description": "Health check"},
            {"path": "/scan", "method": "POST", "description": "Start scan", "body": {"target":"127.0.0.1"}}
        ]
    },
    "orchestrator": {
        "base_url": "http://localhost:3001",
        "health_endpoint": "/health",
        "endpoints": [
            {"path": "/health", "method": "GET", "description": "Health check"},
            {"path": "/engagements", "method": "GET", "description": "List engagements"},
            {"path": "/search", "method": "POST", "description": "Proxy search", "body": {"query":"test"}},
            {"path": "/opsec/chain", "method": "POST", "description": "Assess chain", "body": {"steps":[]}}
        ]
    },
    "integration_hub": {
        "base_url": "http://localhost:8500",
        "health_endpoint": "/health",
        "endpoints": [
            {"path": "/health", "method": "GET", "description": "Health check"},
            {"path": "/api/v1/plugins", "method": "GET", "description": "List plugins"},
            {"path": "/", "method": "GET", "description": "Root endpoint"}
        ]
    },
    "dashboard": {
        "base_url": "http://localhost:3000",
        "health_endpoint": "/",
        "endpoints": [
            {"path": "/", "method": "GET", "description": "Web interface"}
        ]
    }
}

INFRASTRUCTURE = {
    "postgres": {"host": "localhost", "port": 5432, "name": "PostgreSQL"},
    "qdrant": {"host": "localhost", "port": 6333, "name": "Qdrant"},
    "redis": {"host": "localhost", "port": 6379, "name": "Redis"}
}

class TestStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    ERROR = "ERROR"

@dataclass
class TestResult:
    service: str
    endpoint: str
    status: TestStatus
    response_time_ms: float
    status_code: int
    error_message: str = ""
    response_body: str = ""

@dataclass
class ServiceTestSummary:
    service: str
    total_tests: int
    passed: int
    failed: int
    skipped: int
    total_time_ms: float
    results: List[TestResult] = field(default_factory=list)

class OpsecEndpointTester:
    """Comprehensive endpoint tester for OpsecAI services."""
    
    def __init__(self):
        self.results: Dict[str, ServiceTestSummary] = {}
        self.start_time = datetime.now()
    
    async def test_endpoint(self, service_name: str, endpoint: dict, base_url: str) -> TestResult:
        """Test a single endpoint."""
        url = base_url + endpoint["path"]
        method = endpoint["method"]
        description = endpoint["description"]
        
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {}
                
                # Add service auth header if available
                if service_name == "knowledge_engine":
                    headers["X-Service-API-Key"] = "service-key-knowledge-engine-12345"
                elif service_name == "orchestrator":
                    headers["Authorization"] = "Bearer service-key-orchestrator-12345"
                elif service_name == "integration_hub":
                    headers["Authorization"] = "Bearer service-key-integration-hub-12345"
                
                if method == "GET":
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        response_time = (time.time() - start_time) * 1000
                        body = await response.text()
                        
                        return TestResult(
                            service=service_name,
                            endpoint=f"{method} {endpoint['path']} ({description})",
                            status=TestStatus.PASS if response.status == 200 else TestStatus.FAIL,
                            response_time_ms=response_time,
                            status_code=response.status,
                            response_body=body[:500] if body else ""
                        )
                
                elif method == "POST":
                    body = endpoint.get("body", {})
                    async with session.post(url, json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        response_time = (time.time() - start_time) * 1000
                        body = await response.text()
                        
                        return TestResult(
                            service=service_name,
                            endpoint=f"{method} {endpoint['path']} ({description})",
                            status=TestStatus.PASS if response.status == 200 else TestStatus.FAIL,
                            response_time_ms=response_time,
                            status_code=response.status,
                            response_body=body[:500] if body else ""
                        )
        
        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            return TestResult(
                service=service_name,
                endpoint=f"{method} {endpoint['path']} ({description})",
                status=TestStatus.ERROR,
                response_time_ms=response_time,
                status_code=0,
                error_message="Request timeout"
            )
        except aiohttp.ClientConnectorError:
            response_time = (time.time() - start_time) * 1000
            return TestResult(
                service=service_name,
                endpoint=f"{method} {endpoint['path']} ({description})",
                status=TestStatus.ERROR,
                response_time_ms=response_time,
                status_code=0,
                error_message="Connection refused - service not running"
            )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return TestResult(
                service=service_name,
                endpoint=f"{method} {endpoint['path']} ({description})",
                status=TestStatus.ERROR,
                response_time_ms=response_time,
                status_code=0,
                error_message=str(e)
            )
    
    async def test_service(self, service_name: str, config: dict) -> ServiceTestSummary:
        """Test all endpoints for a service."""
        print(f"\n{'='*60}")
        print(f"Testing {service_name.upper()}")
        print(f"{'='*60}")
        
        base_url = config["base_url"]
        endpoints = config["endpoints"]
        
        summary = ServiceTestSummary(
            service=service_name,
            total_tests=len(endpoints),
            passed=0,
            failed=0,
            skipped=0,
            total_time_ms=0.0
        )
        
        # Test each endpoint
        for endpoint in endpoints:
            result = await self.test_endpoint(service_name, endpoint, base_url)
            summary.results.append(result)
            summary.total_time_ms += result.response_time_ms
            
            if result.status == TestStatus.PASS:
                summary.passed += 1
                print(f"✓ PASS | {result.endpoint} | {result.response_time_ms:.0f}ms | Status: {result.status_code}")
            elif result.status == TestStatus.FAIL:
                summary.failed += 1
                print(f"✗ FAIL | {result.endpoint} | {result.response_time_ms:.0f}ms | Status: {result.status_code}")
            else:
                summary.failed += 1
                print(f"⚠️ ERROR | {result.endpoint} | {result.response_time_ms:.0f}ms | {result.error_message}")
        
        self.results[service_name] = summary
        return summary
    
    async def test_infrastructure(self) -> Dict[str, TestResult]:
        """Test infrastructure services connectivity."""
        print(f"\n{'='*60}")
        print("Testing Infrastructure Services")
        print(f"{'='*60}")
        
        results = {}
        
        for service_name, config in INFRASTRUCTURE.items():
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"http://{config['host']}:{config['port']}"
                    start_time = time.time()
                    
                    if service_name == "postgres":
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                            response_time = (time.time() - start_time) * 1000
                            result = TestResult(
                                service=service_name,
                                endpoint=f"Connectivity check",
                                status=TestStatus.PASS if response.status == 200 else TestStatus.FAIL,
                                response_time_ms=response_time,
                                status_code=response.status
                            )
                    elif service_name == "qdrant":
                        async with session.get(f"{url}/health", timeout=aiohttp.ClientTimeout(total=5)) as response:
                            response_time = (time.time() - start_time) * 1000
                            result = TestResult(
                                service=service_name,
                                endpoint=f"Connectivity check",
                                status=TestStatus.PASS if response.status == 200 else TestStatus.FAIL,
                                response_time_ms=response_time,
                                status_code=response.status
                            )
                    elif service_name == "redis":
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                            response_time = (time.time() - start_time) * 1000
                            result = TestResult(
                                service=service_name,
                                endpoint=f"Connectivity check",
                                status=TestStatus.PASS if response.status == 200 else TestStatus.FAIL,
                                response_time_ms=response_time,
                                status_code=response.status
                            )
                    
                    results[service_name] = result
                    
                    if result.status == TestStatus.PASS:
                        print(f"✓ PASS | {config['name']} | {result.response_time_ms:.0f}ms")
                    else:
                        print(f"✗ FAIL | {config['name']} | {result.response_time_ms:.0f}ms | Status: {result.status_code}")
                    
            except Exception as e:
                results[service_name] = TestResult(
                    service=service_name,
                    endpoint="Connectivity check",
                    status=TestStatus.ERROR,
                    response_time_ms=0,
                    status_code=0,
                    error_message=str(e)
                )
                print(f"⚠️ ERROR | {config['name']} | {str(e)}")
        
        return results
    
    async def run_all_tests(self):
        """Run comprehensive tests on all services."""
        print("="*60)
        print("OpsecAI - Comprehensive Endpoint Testing")
        print("="*60)
        print(f"Started at: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Test infrastructure first
        infra_results = await self.test_infrastructure()
        
        # Test each application service
        for service_name, config in SERVICES.items():
            await self.test_service(service_name, config)
        
        # Generate summary report
        self.generate_summary_report(infra_results)
    
    def generate_summary_report(self, infra_results: Dict[str, TestResult]):
        """Generate comprehensive summary report."""
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        
        print("\n" + "="*60)
        print("COMPREHENSIVE TEST REPORT")
        print("="*60)
        
        # Infrastructure summary
        print("\n📦 Infrastructure Services:")
        infra_pass = sum(1 for r in infra_results.values() if r.status == TestStatus.PASS)
        print(f"  Total: {len(infra_results)} | Passed: {infra_pass} | Failed: {len(infra_results) - infra_pass}")
        
        # Application services summary
        print("\n🔧 Application Services:")
        total_app_tests = sum(s.total_tests for s in self.results.values())
        total_app_passed = sum(s.passed for s in self.results.values())
        total_app_failed = sum(s.failed for s in self.results.values())
        
        print(f"  Total Tests: {total_app_tests}")
        print(f"  Passed: {total_app_passed}")
        print(f"  Failed: {total_app_failed}")
        
        # Per-service breakdown
        print("\n📊 Per-Service Breakdown:")
        for service_name, summary in self.results.items():
            status_icon = "✓" if summary.failed == 0 else "✗"
            print(f"  {status_icon} {service_name}: {summary.passed}/{summary.total_tests} passed ({summary.total_time_ms:.0f}ms total)")
        
        # Performance metrics
        print("\n⚡ Performance Metrics:")
        avg_response_time = sum(s.total_time_ms for s in self.results.values()) / max(1, len(self.results))
        print(f"  Average response time: {avg_response_time:.0f}ms")
        print(f"  Total test duration: {total_duration:.2f}s")
        
        # Overall status
        all_tests = total_app_tests + len(infra_results)
        all_passed = total_app_passed + infra_pass
        pass_rate = (all_passed / all_tests * 100) if all_tests > 0 else 0
        
        print(f"\n🎯 Overall Status:")
        print(f"  Pass Rate: {pass_rate:.1f}%")
        
        if pass_rate >= 80:
            print(f"  Status: ✅ HEALTHY")
        elif pass_rate >= 50:
            print(f"  Status: ⚠️ DEGRADED")
        else:
            print(f"  Status: 🔴 CRITICAL")
        
        print("\n" + "="*60)
        print(f"Test completed at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total duration: {total_duration:.2f}s")
        print("="*60)

async def main():
    """Main entry point."""
    tester = OpsecEndpointTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())