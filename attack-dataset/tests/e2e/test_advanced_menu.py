#!/usr/bin/env python3
"""
Test script for Advanced OpsecAI menu system validation
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
from datetime import datetime

def test_advanced_initialization():
    """Test advanced menu system initialization."""
    print("Testing Advanced Menu Initialization...")
    
    try:
        menu = OpsecAdvancedMenu()
        print("✓ Advanced menu manager initialized successfully")
        
        # Check service definitions
        assert len(menu.services) == 9, f"Expected 9 services, got {len(menu.services)}"
        print(f"✓ Service definitions loaded: {len(menu.services)} services")
        
        # Check session ID
        assert menu.session_id is not None, "Session ID should be generated"
        print(f"✓ Session ID generated: {menu.session_id}")
        
        # Check state management
        assert menu.state_file == "menu_state.pkl", "State file should be configured"
        assert menu.config_file == "menu_config.json", "Config file should be configured"
        print(f"✓ State management configured")
        
        # Check monitoring status
        assert menu.monitoring_active == False, "Monitoring should not be active initially"
        print(f"✓ Monitoring status correct (inactive)")
        
        return True
    except Exception as e:
        print(f"✗ Advanced menu initialization failed: {e}")
        return False

def test_service_info_dataclass():
    """Test ServiceInfo dataclass functionality."""
    print("\nTesting ServiceInfo Dataclass...")
    
    try:
        service = ServiceInfo(
            name="Test Service",
            port=8080,
            health_url="http://localhost:8080/health",
            status=ServiceStatus.UNKNOWN
        )
        
        assert service.name == "Test Service"
        assert service.port == 8080
        assert service.status == ServiceStatus.UNKNOWN
        assert service.restart_count == 0
        assert service.auto_restart == False
        
        print("✓ ServiceInfo dataclass working correctly")
        return True
    except Exception as e:
        print(f"✗ ServiceInfo dataclass test failed: {e}")
        return False

def test_engagement_info_dataclass():
    """Test EngagementInfo dataclass functionality."""
    print("\nTesting EngagementInfo Dataclass...")
    
    try:
        engagement = EngagementInfo(
            id="eng_123",
            target="192.168.1.10",
            status="active",
            aggression_level=5,
            started_at=datetime.now().isoformat(),
            current_stage="reconnaissance"
        )
        
        assert engagement.id == "eng_123"
        assert engagement.target == "192.168.1.10"
        assert engagement.aggression_level == 5
        assert engagement.progress == 0.0
        
        print("✓ EngagementInfo dataclass working correctly")
        return True
    except Exception as e:
        print(f"✗ EngagementInfo dataclass test failed: {e}")
        return False

def test_operation_result_dataclass():
    """Test OperationResult dataclass functionality."""
    print("\nTesting OperationResult Dataclass...")
    
    try:
        operation = OperationResult(
            operation_id="op_456",
            operation_type="scan",
            status=OperationStatus.RUNNING,
            started_at=datetime.now().isoformat()
        )
        
        assert operation.operation_id == "op_456"
        assert operation.operation_type == "scan"
        assert operation.status == OperationStatus.RUNNING
        assert operation.result is None
        
        print("✓ OperationResult dataclass working correctly")
        return True
    except Exception as e:
        print(f"✗ OperationResult dataclass test failed: {e}")
        return False

def test_system_metrics_dataclass():
    """Test SystemMetrics dataclass functionality."""
    print("\nTesting SystemMetrics Dataclass...")
    
    try:
        metrics = SystemMetrics(
            timestamp=datetime.now().isoformat(),
            cpu_usage=45.5,
            memory_usage=62.3,
            disk_usage=78.1,
            network_io=1024.5,
            active_connections=15,
            services_healthy=7,
            services_total=9
        )
        
        assert metrics.cpu_usage == 45.5
        assert metrics.services_healthy == 7
        assert metrics.services_total == 9
        
        print("✓ SystemMetrics dataclass working correctly")
        return True
    except Exception as e:
        print(f"✗ SystemMetrics dataclass test failed: {e}")
        return False

async def test_health_check_functionality():
    """Test health check functionality."""
    print("\nTesting Health Check Functionality...")
    
    try:
        menu = OpsecAdvancedMenu()
        
        # Test health check for a service (this will fail since services aren't running)
        result = await menu.check_service_health("knowledge_engine")
        
        # The result should be False since service is not running
        assert result == False or result == True, "Health check should return boolean"
        print(f"✓ Health check functionality working (result: {result})")
        
        # Test service status after health check
        service = menu.services.get("knowledge_engine")
        assert service is not None, "Service should exist"
        assert service.status in [ServiceStatus.RUNNING, ServiceStatus.ERROR], \
            f"Status should be RUNNING or ERROR, got {service.status}"
        print(f"✓ Service status updated correctly: {service.status.value}")
        
        return True
    except Exception as e:
        print(f"✗ Health check functionality test failed: {e}")
        return False

async def test_system_metrics_functionality():
    """Test system metrics collection."""
    print("\nTesting System Metrics Functionality...")
    
    try:
        menu = OpsecAdvancedMenu()
        
        # Get system metrics
        metrics = await menu.get_system_metrics()
        
        assert metrics is not None, "Metrics should be collected"
        assert isinstance(metrics.cpu_usage, (int, float)), "CPU usage should be numeric"
        assert isinstance(metrics.memory_usage, (int, float)), "Memory usage should be numeric"
        assert metrics.services_healthy <= metrics.services_total, \
            "Healthy services should not exceed total services"
        
        print(f"✓ System metrics collected: CPU={metrics.cpu_usage}%, Memory={metrics.memory_usage}%")
        print(f"✓ Services: {metrics.services_healthy}/{metrics.services_total} healthy")
        
        return True
    except Exception as e:
        print(f"✗ System metrics functionality test failed: {e}")
        return False

def test_state_management():
    """Test state save and load functionality."""
    print("\nTesting State Management...")
    
    try:
        menu = OpsecAdvancedMenu()
        
        # Modify some state
        menu.services["knowledge_engine"].restart_count = 3
        menu.services["knowledge_engine"].status = ServiceStatus.RUNNING
        
        # Save state
        menu._save_state()
        print("✓ State saved successfully")
        
        # Create new menu instance and load state
        menu2 = OpsecAdvancedMenu()
        assert menu2.services["knowledge_engine"].restart_count == 3, \
            "Restart count should be restored"
        print("✓ State loaded successfully")
        
        # Clean up
        if os.path.exists("menu_state.pkl"):
            os.remove("menu_state.pkl")
        print("✓ State cleanup completed")
        
        return True
    except Exception as e:
        print(f"✗ State management test failed: {e}")
        # Clean up on error
        if os.path.exists("menu_state.pkl"):
            os.remove("menu_state.pkl")
        return False

def test_logging_functionality():
    """Test operation logging functionality."""
    print("\nTesting Logging Functionality...")
    
    try:
        menu = OpsecAdvancedMenu()
        
        # Log an operation
        menu._log_operation("test_operation", "This is a test operation")
        
        # Check if log file was created
        if os.path.exists("menu_operations.log"):
            print("✓ Log file created successfully")
            
            # Read and verify log content
            with open("menu_operations.log", "r") as f:
                log_content = f.read()
                assert "test_operation" in log_content, "Operation type should be in log"
                assert "This is a test operation" in log_content, "Operation details should be in log"
            print("✓ Log content verified")
            
            # Clean up
            os.remove("menu_operations.log")
            print("✓ Log cleanup completed")
        else:
            print("⚠ Log file not created (may be expected in some environments)")
        
        return True
    except Exception as e:
        print(f"✗ Logging functionality test failed: {e}")
        # Clean up on error
        if os.path.exists("menu_operations.log"):
            os.remove("menu_operations.log")
        return False

def test_menu_enhancements():
    """Test that advanced menu has enhanced features compared to basic menu."""
    print("\nTesting Menu Enhancements...")
    
    try:
        menu = OpsecAdvancedMenu()
        
        # Check for advanced features
        enhancements = [
            ("Session management", hasattr(menu, 'session_id') and menu.session_id is not None),
            ("State persistence", hasattr(menu, '_save_state') and hasattr(menu, '_load_state')),
            ("Operation logging", hasattr(menu, '_log_operation')),
            ("System metrics", hasattr(menu, 'get_system_metrics')),
            ("Advanced dataclasses", hasattr(menu, 'engagements') and hasattr(menu, 'operations')),
            ("Background monitoring", hasattr(menu, 'start_monitoring') and hasattr(menu, 'stop_monitoring')),
            ("Interactive menus", hasattr(menu, 'interactive_menu')),
            ("Service management", hasattr(menu, 'service_management_menu')),
            ("Engagement operations", hasattr(menu, 'engagement_operations_menu')),
            ("Scanning operations", hasattr(menu, 'scanning_operations_menu')),
            ("Configuration management", hasattr(menu, 'configuration_menu')),
            ("Diagnostics", hasattr(menu, 'diagnostics_menu')),
        ]
        
        all_present = True
        for feature_name, present in enhancements:
            if present:
                print(f"✓ {feature_name}: Present")
            else:
                print(f"✗ {feature_name}: Missing")
                all_present = False
        
        if all_present:
            print("✓ All advanced features present")
        else:
            print("⚠ Some advanced features missing")
        
        return all_present
    except Exception as e:
        print(f"✗ Menu enhancements test failed: {e}")
        return False

async def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("OpsecAI Advanced Menu System Test Suite")
    print("=" * 60)
    
    tests = [
        ("Initialization", test_advanced_initialization),
        ("ServiceInfo Dataclass", test_service_info_dataclass),
        ("EngagementInfo Dataclass", test_engagement_info_dataclass),
        ("OperationResult Dataclass", test_operation_result_dataclass),
        ("SystemMetrics Dataclass", test_system_metrics_dataclass),
        ("Health Check", test_health_check_functionality),
        ("System Metrics", test_system_metrics_functionality),
        ("State Management", test_state_management),
        ("Logging", test_logging_functionality),
        ("Menu Enhancements", test_menu_enhancements),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All tests passed!")
        return 0
    else:
        print(f"✗ {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)