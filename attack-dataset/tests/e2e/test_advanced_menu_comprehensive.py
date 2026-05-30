#!/usr/bin/env python3
"""
Comprehensive test suite for all OpsecAI advanced menu functions
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from opsec_menu_advanced import (
    OpsecAdvancedMenu, 
    ServiceStatus, 
    OperationStatus,
    ServiceInfo,
    EngagementInfo,
    OperationResult,
    SystemMetrics
)
import asyncio
import tempfile
import shutil
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import json

class TestOpsecAdvancedMenuComprehensive:
    """Comprehensive test suite for all menu functions"""
    
    def __init__(self):
        self.test_results = []
        self.temp_dir = None
        
    def setup(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        os.chdir(self.temp_dir)
        
    def teardown(self):
        """Cleanup test environment"""
        os.chdir("/Users/adminuser/attack-dataset")
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        
        # Clean up any test files
        for file in ["menu_state.pkl", "menu_config.json", "menu_operations.log"]:
            if os.path.exists(file):
                os.remove(file)
    
    def record_result(self, test_name, passed, message=""):
        """Record test result"""
        self.test_results.append((test_name, passed, message))
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
        if message:
            print(f"  {message}")
    
    async def test_initialization(self):
        """Test menu initialization"""
        try:
            menu = OpsecAdvancedMenu()
            
            assert menu is not None, "Menu should be initialized"
            assert len(menu.services) == 9, f"Expected 9 services, got {len(menu.services)}"
            assert menu.session_id is not None, "Session ID should be generated"
            assert menu.monitoring_active == False, "Monitoring should be inactive initially"
            
            self.record_result("Initialization", True)
            return True
        except Exception as e:
            self.record_result("Initialization", False, str(e))
            return False
    
    async def test_service_initialization(self):
        """Test service initialization"""
        try:
            menu = OpsecAdvancedMenu()
            
            # Check all services are properly initialized
            expected_services = [
                "postgres", "qdrant", "redis", "knowledge_engine",
                "opsec_monitor", "realtime_analyzer", "orchestrator",
                "dashboard", "integration_hub"
            ]
            
            for service_name in expected_services:
                assert service_name in menu.services, f"Service {service_name} should exist"
                service = menu.services[service_name]
                assert isinstance(service, ServiceInfo), f"Service should be ServiceInfo instance"
                assert service.status == ServiceStatus.UNKNOWN, f"Service status should be UNKNOWN initially"
                assert service.restart_count == 0, f"Restart count should be 0 initially"
            
            self.record_result("Service Initialization", True)
            return True
        except Exception as e:
            self.record_result("Service Initialization", False, str(e))
            return False
    
    async def test_check_service_health(self):
        """Test service health check function"""
        try:
            menu = OpsecAdvancedMenu()
            
            # Test health check (will likely fail since services aren't running)
            result = await menu.check_service_health("knowledge_engine")
            
            # Result should be boolean
            assert isinstance(result, bool), "Health check should return boolean"
            
            # Service status should be updated
            service = menu.services["knowledge_engine"]
            assert service.status in [ServiceStatus.RUNNING, ServiceStatus.ERROR], \
                f"Status should be RUNNING or ERROR, got {service.status}"
            
            self.record_result("Check Service Health", True)
            return True
        except Exception as e:
            self.record_result("Check Service Health", False, str(e))
            return False
    
    async def test_check_service_health_with_retry(self):
        """Test service health check with retry logic"""
        try:
            menu = OpsecAdvancedMenu()
            
            # Test with retry
            result = await menu.check_service_health_with_retry("knowledge_engine", max_retries=2)
            
            # Result should be boolean
            assert isinstance(result, bool), "Health check with retry should return boolean"
            
            self.record_result("Check Service Health with Retry", True)
            return True
        except Exception as e:
            self.record_result("Check Service Health with Retry", False, str(e))
            return False
    
    async def test_get_system_metrics(self):
        """Test system metrics collection"""
        try:
            menu = OpsecAdvancedMenu()
            
            metrics = await menu.get_system_metrics()
            
            assert isinstance(metrics, SystemMetrics), "Should return SystemMetrics instance"
            assert isinstance(metrics.cpu_usage, (int, float)), "CPU usage should be numeric"
            assert isinstance(metrics.memory_usage, (int, float)), "Memory usage should be numeric"
            assert isinstance(metrics.disk_usage, (int, float)), "Disk usage should be numeric"
            assert isinstance(metrics.services_healthy, int), "Healthy services count should be integer"
            assert isinstance(metrics.services_total, int), "Total services count should be integer"
            assert metrics.services_healthy <= metrics.services_total, "Healthy <= total"
            
            self.record_result("Get System Metrics", True)
            return True
        except Exception as e:
            self.record_result("Get System Metrics", False, str(e))
            return False
    
    async def test_fetch_engagements(self):
        """Test fetching engagements from orchestrator"""
        try:
            menu = OpsecAdvancedMenu()
            
            # This will likely fail if orchestrator is not running, but should not crash
            await menu.fetch_engagements()
            
            # engagements dict should exist (may be empty)
            assert isinstance(menu.engagements, dict), "Engagements should be a dict"
            
            self.record_result("Fetch Engagements", True)
            return True
        except Exception as e:
            self.record_result("Fetch Engagements", False, str(e))
            return False
    
    async def test_start_service_mock(self):
        """Test start service function with mocked docker"""
        try:
            menu = OpsecAdvancedMenu()
            
            # Mock the subprocess.run to simulate successful docker start
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0, stdout="Started", stderr="")
                
                # Mock health check to return True
                with patch.object(menu, 'check_service_health_with_retry', new_callable=AsyncMock) as mock_health:
                    mock_health.return_value = True
                    
                    result = await menu.start_service("knowledge_engine")
                    
                    assert result == True, "Start service should return True"
                    assert menu.services["knowledge_engine"].status == ServiceStatus.RUNNING
            
            self.record_result("Start Service (Mocked)", True)
            return True
        except Exception as e:
            self.record_result("Start Service (Mocked)", False, str(e))
            return False
    
    async def test_stop_service_mock(self):
        """Test stop service function with mocked docker"""
        try:
            menu = OpsecAdvancedMenu()
            
            # Mock the subprocess.run to simulate successful docker stop
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0, stdout="Stopped", stderr="")
                
                result = await menu.stop_service("knowledge_engine")
                
                assert result == True, "Stop service should return True"
                assert menu.services["knowledge_engine"].status == ServiceStatus.STOPPED
            
            self.record_result("Stop Service (Mocked)", True)
            return True
        except Exception as e:
            self.record_result("Stop Service (Mocked)", False, str(e))
            return False
    
    async def test_restart_service_mock(self):
        """Test restart service function"""
        try:
            menu = OpsecAdvancedMenu()
            
            # Mock both stop and start
            with patch.object(menu, 'stop_service', new_callable=AsyncMock) as mock_stop, \
                 patch.object(menu, 'start_service', new_callable=AsyncMock) as mock_start:
                
                mock_stop.return_value = True
                mock_start.return_value = True
                
                result = await menu.restart_service("knowledge_engine")
                
                assert result == True, "Restart service should return True"
                mock_stop.assert_called_once_with("knowledge_engine")
                mock_start.assert_called_once_with("knowledge_engine")
            
            self.record_result("Restart Service (Mocked)", True)
            return True
        except Exception as e:
            self.record_result("Restart Service (Mocked)", False, str(e))
            return False
    
    async def test_start_all_services_mock(self):
        """Test start all services function"""
        try:
            menu = OpsecAdvancedMenu()
            
            # Mock individual service starts
            with patch.object(menu, 'start_service', new_callable=AsyncMock) as mock_start:
                mock_start.return_value = True
                
                results = await menu.start_all_services()
                
                assert isinstance(results, dict), "Results should be a dict"
                # Should attempt to start services in dependency order
                assert len(results) > 0, "Should attempt to start services"
            
            self.record_result("Start All Services (Mocked)", True)
            return True
        except Exception as e:
            self.record_result("Start All Services (Mocked)", False, str(e))
            return False
    
    async def test_stop_all_services_mock(self):
        """Test stop all services function"""
        try:
            menu = OpsecAdvancedMenu()
            
            # Mock individual service stops
            with patch.object(menu, 'stop_service', new_callable=AsyncMock) as mock_stop:
                mock_stop.return_value = True
                
                results = await menu.stop_all_services()
                
                assert isinstance(results, dict), "Results should be a dict"
                assert len(results) > 0, "Should attempt to stop services"
            
            self.record_result("Stop All Services (Mocked)", True)
            return True
        except Exception as e:
            self.record_result("Stop All Services (Mocked)", False, str(e))
            return False
    
    async def test_create_engagement_mock(self):
        """Test create engagement function structure"""
        try:
            menu = OpsecAdvancedMenu()
            
            # Test that the function exists and can be called (will fail without actual services)
            # We just verify it doesn't crash and handles errors gracefully
            result = await menu.create_engagement("192.168.1.10", 5)
            
            # Should return None (since services aren't actually running)
            assert result is None or isinstance(result, str), "Should return None or engagement ID"
            
            self.record_result("Create Engagement (Structure)", True)
            return True
        except Exception as e:
            self.record_result("Create Engagement (Structure)", False, str(e))
            return False
    
    async def test_run_scan_mock(self):
        """Test run scan function structure"""
        try:
            menu = OpsecAdvancedMenu()
            
            # Test that the function exists and can be called (will fail without actual services)
            # We just verify it doesn't crash and handles errors gracefully
            result = await menu.run_scan("192.168.1.10")
            
            # Should return None (since services aren't actually running)
            assert result is None or isinstance(result, str), "Should return None or scan ID"
            
            self.record_result("Run Scan (Structure)", True)
            return True
        except Exception as e:
            self.record_result("Run Scan (Structure)", False, str(e))
            return False
    
    def test_start_monitoring(self):
        """Test start monitoring function"""
        try:
            menu = OpsecAdvancedMenu()
            
            # Start monitoring
            menu.start_monitoring(interval=1)
            
            assert menu.monitoring_active == True, "Monitoring should be active"
            assert menu.monitoring_thread is not None, "Monitoring thread should exist"
            
            # Stop monitoring
            menu.stop_monitoring()
            
            assert menu.monitoring_active == False, "Monitoring should be inactive"
            
            self.record_result("Start/Stop Monitoring", True)
            return True
        except Exception as e:
            self.record_result("Start/Stop Monitoring", False, str(e))
            return False
    
    def test_save_state(self):
        """Test state save function"""
        try:
            menu = OpsecAdvancedMenu()
            
            # Modify some state
            menu.services["knowledge_engine"].restart_count = 5
            menu.services["knowledge_engine"].status = ServiceStatus.RUNNING
            
            # Save state
            menu._save_state()
            
            assert os.path.exists("menu_state.pkl"), "State file should be created"
            
            self.record_result("Save State", True)
            return True
        except Exception as e:
            self.record_result("Save State", False, str(e))
            return False
    
    def test_load_state(self):
        """Test state load function"""
        try:
            menu = OpsecAdvancedMenu()
            
            # Modify and save state
            menu.services["knowledge_engine"].restart_count = 3
            menu.services["knowledge_engine"].status = ServiceStatus.RUNNING
            menu._save_state()
            
            # Create new menu and load state
            menu2 = OpsecAdvancedMenu()
            
            assert menu2.services["knowledge_engine"].restart_count == 3, \
                "Restart count should be restored"
            assert menu2.services["knowledge_engine"].status == ServiceStatus.RUNNING, \
                "Status should be restored"
            
            self.record_result("Load State", True)
            return True
        except Exception as e:
            self.record_result("Load State", False, str(e))
            return False
    
    def test_log_operation(self):
        """Test operation logging function"""
        try:
            menu = OpsecAdvancedMenu()
            
            # Log an operation
            menu._log_operation("test_operation", "Test operation details")
            
            assert os.path.exists("menu_operations.log"), "Log file should be created"
            
            # Verify log content
            with open("menu_operations.log", "r") as f:
                log_content = f.read()
                assert "test_operation" in log_content, "Operation type should be in log"
                assert "Test operation details" in log_content, "Details should be in log"
                assert menu.session_id in log_content, "Session ID should be in log"
            
            self.record_result("Log Operation", True)
            return True
        except Exception as e:
            self.record_result("Log Operation", False, str(e))
            return False
    
    def test_calculate_uptime(self):
        """Test uptime calculation function"""
        try:
            menu = OpsecAdvancedMenu()
            
            uptime = menu._calculate_uptime()
            
            assert isinstance(uptime, str), "Uptime should be string"
            # Uptime format should be "Xh Ym" or "Unknown"
            assert uptime == "Unknown" or "h" in uptime, "Uptime should be in expected format"
            
            self.record_result("Calculate Uptime", True)
            return True
        except Exception as e:
            self.record_result("Calculate Uptime", False, str(e))
            return False
    
    async def test_monitor_services_background(self):
        """Test background service monitoring"""
        try:
            menu = OpsecAdvancedMenu()
            
            # Start monitoring briefly
            menu.start_monitoring(interval=1)
            await asyncio.sleep(2)  # Let it run for a bit
            menu.stop_monitoring()
            
            # Check that metrics were collected
            assert len(menu.system_metrics) > 0, "Should have collected some metrics"
            
            self.record_result("Background Service Monitoring", True)
            return True
        except Exception as e:
            self.record_result("Background Service Monitoring", False, str(e))
            return False
    
    async def test_full_health_check_mock(self):
        """Test full health check function structure"""
        try:
            menu = OpsecAdvancedMenu()
            
            # Just test that the function exists and can be called without crashing
            # We don't mock here since the function should handle missing services gracefully
            await menu.full_health_check()
            
            self.record_result("Full Health Check (Structure)", True)
            return True
        except Exception as e:
            self.record_result("Full Health Check (Structure)", False, str(e))
            return False
    
    async def test_dependency_check(self):
        """Test service dependency check function structure"""
        try:
            menu = OpsecAdvancedMenu()
            
            # This function should not crash even if services aren't running
            await menu.dependency_check()
            
            self.record_result("Dependency Check (Structure)", True)
            return True
        except Exception as e:
            self.record_result("Dependency Check (Structure)", False, str(e))
            return False
    
    async def test_network_test(self):
        """Test network connectivity test function structure"""
        try:
            menu = OpsecAdvancedMenu()
            
            # This function should not crash even if services aren't running
            await menu.network_test()
            
            self.record_result("Network Test (Structure)", True)
            return True
        except Exception as e:
            self.record_result("Network Test (Structure)", False, str(e))
            return False
    
    async def test_performance_analysis(self):
        """Test performance analysis function structure"""
        try:
            menu = OpsecAdvancedMenu()
            
            # Add some metrics first
            for _ in range(5):
                metrics = await menu.get_system_metrics()
                menu.system_metrics.append(metrics)
            
            # This function should not crash
            await menu.performance_analysis()
            
            self.record_result("Performance Analysis (Structure)", True)
            return True
        except Exception as e:
            self.record_result("Performance Analysis (Structure)", False, str(e))
            return False
    
    def test_error_log_analysis(self):
        """Test error log analysis function structure"""
        try:
            menu = OpsecAdvancedMenu()
            
            # This function should not crash even if no logs exist
            menu.error_log_analysis()
            
            self.record_result("Error Log Analysis (Structure)", True)
            return True
        except Exception as e:
            self.record_result("Error Log Analysis (Structure)", False, str(e))
            return False
    
    async def test_generate_diagnostic_report(self):
        """Test diagnostic report generation function structure"""
        try:
            menu = OpsecAdvancedMenu()
            
            # Generate report
            await menu.generate_diagnostic_report()
            
            # Check that report file was created
            report_files = [f for f in os.listdir('.') if f.startswith('diagnostic_report_')]
            assert len(report_files) > 0, "Diagnostic report file should be created"
            
            # Clean up report file
            for report_file in report_files:
                os.remove(report_file)
            
            self.record_result("Generate Diagnostic Report (Structure)", True)
            return True
        except Exception as e:
            self.record_result("Generate Diagnostic Report (Structure)", False, str(e))
            return False
    
    def test_signal_handlers(self):
        """Test signal handler setup"""
        try:
            menu = OpsecAdvancedMenu()
            
            # Signal handlers should be set up
            # We can't easily test the actual signal handling without sending signals
            # but we can verify the setup doesn't crash
            
            self.record_result("Signal Handlers Setup", True)
            return True
        except Exception as e:
            self.record_result("Signal Handlers Setup", False, str(e))
            return False
    
    def test_service_info_dataclass(self):
        """Test ServiceInfo dataclass"""
        try:
            service = ServiceInfo(
                name="Test Service",
                port=8080,
                health_url="http://localhost:8080/health",
                status=ServiceStatus.RUNNING,
                pid=12345,
                cpu_usage=50.5,
                memory_usage=60.3,
                uptime=3600.0,
                auto_restart=True,
                restart_count=2
            )
            
            assert service.name == "Test Service"
            assert service.port == 8080
            assert service.status == ServiceStatus.RUNNING
            assert service.pid == 12345
            assert service.cpu_usage == 50.5
            assert service.auto_restart == True
            assert service.restart_count == 2
            
            self.record_result("ServiceInfo Dataclass", True)
            return True
        except Exception as e:
            self.record_result("ServiceInfo Dataclass", False, str(e))
            return False
    
    def test_engagement_info_dataclass(self):
        """Test EngagementInfo dataclass"""
        try:
            engagement = EngagementInfo(
                id="eng_123",
                target="192.168.1.10",
                status="active",
                aggression_level=7,
                started_at="2024-01-01T00:00:00",
                current_stage="exploitation",
                progress=75.5,
                attack_chains_count=10,
                opsec_findings_count=5
            )
            
            assert engagement.id == "eng_123"
            assert engagement.target == "192.168.1.10"
            assert engagement.aggression_level == 7
            assert engagement.progress == 75.5
            assert engagement.attack_chains_count == 10
            
            self.record_result("EngagementInfo Dataclass", True)
            return True
        except Exception as e:
            self.record_result("EngagementInfo Dataclass", False, str(e))
            return False
    
    def test_operation_result_dataclass(self):
        """Test OperationResult dataclass"""
        try:
            operation = OperationResult(
                operation_id="op_456",
                operation_type="scan",
                status=OperationStatus.COMPLETED,
                result={"target": "192.168.1.10", "findings": 5},
                error=None,
                started_at="2024-01-01T00:00:00",
                completed_at="2024-01-01T00:05:00",
                duration_seconds=300.0
            )
            
            assert operation.operation_id == "op_456"
            assert operation.operation_type == "scan"
            assert operation.status == OperationStatus.COMPLETED
            assert operation.result is not None
            assert operation.duration_seconds == 300.0
            
            self.record_result("OperationResult Dataclass", True)
            return True
        except Exception as e:
            self.record_result("OperationResult Dataclass", False, str(e))
            return False
    
    def test_system_metrics_dataclass(self):
        """Test SystemMetrics dataclass"""
        try:
            metrics = SystemMetrics(
                timestamp="2024-01-01T00:00:00",
                cpu_usage=45.5,
                memory_usage=62.3,
                disk_usage=78.1,
                network_io=1024.5,
                active_connections=15,
                services_healthy=7,
                services_total=9
            )
            
            assert metrics.cpu_usage == 45.5
            assert metrics.memory_usage == 62.3
            assert metrics.services_healthy == 7
            assert metrics.services_total == 9
            
            self.record_result("SystemMetrics Dataclass", True)
            return True
        except Exception as e:
            self.record_result("SystemMetrics Dataclass", False, str(e))
            return False
    
    async def run_all_tests(self):
        """Run all tests"""
        print("=" * 70)
        print("OpsecAI Advanced Menu - Comprehensive Function Test Suite")
        print("=" * 70)
        
        self.setup()
        
        try:
            # Core functionality tests
            await self.test_initialization()
            await self.test_service_initialization()
            await self.test_check_service_health()
            await self.test_check_service_health_with_retry()
            await self.test_get_system_metrics()
            await self.test_fetch_engagements()
            
            # Service management tests
            await self.test_start_service_mock()
            await self.test_stop_service_mock()
            await self.test_restart_service_mock()
            await self.test_start_all_services_mock()
            await self.test_stop_all_services_mock()
            
            # Operation tests
            await self.test_create_engagement_mock()
            await self.test_run_scan_mock()
            
            # Monitoring tests
            self.test_start_monitoring()
            await self.test_monitor_services_background()
            
            # State management tests
            self.test_save_state()
            self.test_load_state()
            self.test_log_operation()
            
            # Utility tests
            self.test_calculate_uptime()
            self.test_signal_handlers()
            
            # Diagnostics tests
            try:
                await self.test_full_health_check_mock()
            except Exception as e:
                self.record_result("Full Health Check (Structure)", False, f"Exception: {str(e)}")
            
            try:
                await self.test_dependency_check()
            except Exception as e:
                self.record_result("Dependency Check (Structure)", False, f"Exception: {str(e)}")
            
            try:
                await self.test_network_test()
            except Exception as e:
                self.record_result("Network Test (Structure)", False, f"Exception: {str(e)}")
            
            try:
                await self.test_performance_analysis()
            except Exception as e:
                self.record_result("Performance Analysis (Structure)", False, f"Exception: {str(e)}")
            
            try:
                self.test_error_log_analysis()
            except Exception as e:
                self.record_result("Error Log Analysis (Structure)", False, f"Exception: {str(e)}")
            
            try:
                await self.test_generate_diagnostic_report()
            except Exception as e:
                self.record_result("Generate Diagnostic Report (Structure)", False, f"Exception: {str(e)}")
            
            # Dataclass tests
            try:
                self.test_service_info_dataclass()
            except Exception as e:
                self.record_result("ServiceInfo Dataclass", False, f"Exception: {str(e)}")
            
            try:
                self.test_engagement_info_dataclass()
            except Exception as e:
                self.record_result("EngagementInfo Dataclass", False, f"Exception: {str(e)}")
            
            try:
                self.test_operation_result_dataclass()
            except Exception as e:
                self.record_result("OperationResult Dataclass", False, f"Exception: {str(e)}")
            
            try:
                self.test_system_metrics_dataclass()
            except Exception as e:
                self.record_result("SystemMetrics Dataclass", False, f"Exception: {str(e)}")
            
        finally:
            self.teardown()
        
        # Print summary
        print("\n" + "=" * 70)
        print("Test Summary")
        print("=" * 70)
        
        passed = sum(1 for _, result, _ in self.test_results if result)
        total = len(self.test_results)
        
        for test_name, result, message in self.test_results:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"{status}: {test_name}")
            if message and not result:
                print(f"  Error: {message}")
        
        print(f"\nTotal: {passed}/{total} tests passed")
        
        if passed == total:
            print("✓ All tests passed!")
            return 0
        else:
            print(f"✗ {total - passed} test(s) failed")
            return 1

async def main():
    """Main entry point"""
    tester = TestOpsecAdvancedMenuComprehensive()
    return await tester.run_all_tests()

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)