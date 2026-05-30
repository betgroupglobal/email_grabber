#!/usr/bin/env python3
"""
Test script for Enhanced OpsecAI menu system validation
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from opsec_menu_enhanced import (
    OpsecStartupManagerEnhanced, 
    ServiceStatus, 
    CircuitBreaker,
    HealthCheckResult
)
import asyncio
from datetime import datetime

def test_enhanced_initialization():
    """Test enhanced menu system initialization."""
    print("Testing Enhanced Menu Initialization...")
    
    try:
        manager = OpsecStartupManagerEnhanced()
        print("✓ Enhanced menu manager initialized successfully")
        
        # Check service definitions
        assert len(manager.services) == 9, f"Expected 9 services, got {len(manager.services)}"
        print(f"✓ Service definitions loaded: {len(manager.services)} services")
        
        # Check circuit breakers
        assert len(manager.circuit_breakers) == 9, f"Expected 9 circuit breakers, got {len(manager.circuit_breakers)}"
        print(f"✓ Circuit breakers initialized: {len(manager.circuit_breakers)}")
        
        # Check historical metrics
        assert len(manager.historical_metrics) == 9, f"Expected 9 metric collections, got {len(manager.historical_metrics)}"
        print(f"✓ Historical metrics initialized: {len(manager.historical_metrics)}")
        
        # Check service profiles
        assert len(manager.service_profiles) == 4, f"Expected 4 profiles, got {len(manager.service_profiles)}"
        print(f"✓ Service profiles loaded: {len(manager.service_profiles)}")
        
        # Check log buffers
        assert len(manager.log_buffers) == 9, f"Expected 9 log buffers, got {len(manager.log_buffers)}"
        print(f"✓ Log buffers initialized: {len(manager.log_buffers)}")
        
        # Check shortcuts
        assert len(manager.shortcuts) == 10, f"Expected 10 shortcuts, got {len(manager.shortcuts)}"
        print(f"✓ Keyboard shortcuts defined: {len(manager.shortcuts)}")
        
        return True
    except Exception as e:
        print(f"✗ Enhanced initialization failed: {e}")
        return False

def test_circuit_breaker():
    """Test circuit breaker functionality."""
    print("\nTesting Circuit Breaker...")
    
    try:
        cb = CircuitBreaker(failure_threshold=3, timeout=10)
        print("✓ Circuit breaker created")
        
        # Test initial state
        assert cb.state == "closed", f"Expected closed state, got {cb.state}"
        print(f"✓ Initial state: {cb.state}")
        
        # Test success
        cb.record_success()
        assert cb.state == "closed", "State should remain closed after success"
        assert cb.failures == 0, "Failures should be reset after success"
        print("✓ Success recording works")
        
        # Test failures
        for i in range(3):
            cb.record_failure()
        
        assert cb.state == "open", f"Expected open state after 3 failures, got {cb.state}"
        assert cb.failures == 3, f"Expected 3 failures, got {cb.failures}"
        print("✓ Failure recording and state transition works")
        
        # Test circuit open
        assert not cb.can_attempt(), "Should not allow attempts when circuit is open"
        print("✓ Circuit blocks attempts when open")
        
        # Test timeout recovery
        cb.last_failure_time = datetime.now()
        cb.timeout = -1  # Negative timeout to force immediate recovery
        assert cb.can_attempt(), "Should allow attempt after timeout"
        assert cb.state == "half-open", "Should transition to half-open after timeout"
        print("✓ Timeout recovery works")
        
        return True
    except Exception as e:
        print(f"✗ Circuit breaker test failed: {e}")
        return False

def test_service_profiles():
    """Test service profile functionality."""
    print("\nTesting Service Profiles...")
    
    try:
        manager = OpsecStartupManagerEnhanced()
        
        # Check profile definitions
        assert "full" in manager.service_profiles, "Missing 'full' profile"
        assert "core" in manager.service_profiles, "Missing 'core' profile"
        assert "minimal" in manager.service_profiles, "Missing 'minimal' profile"
        assert "development" in manager.service_profiles, "Missing 'development' profile"
        print("✓ All required profiles defined")
        
        # Check profile structure
        full_profile = manager.service_profiles["full"]
        assert full_profile.name == "Full Stack", "Profile name mismatch"
        assert len(full_profile.services) == 9, f"Expected 9 services in full profile, got {len(full_profile.services)}"
        print("✓ Full profile structure correct")
        
        minimal_profile = manager.service_profiles["minimal"]
        assert len(minimal_profile.services) == 3, f"Expected 3 services in minimal profile, got {len(minimal_profile.services)}"
        print("✓ Minimal profile structure correct")
        
        # Check auto-restart settings
        dev_profile = manager.service_profiles["development"]
        assert dev_profile.auto_restart, "Development profile should have auto-restart enabled"
        print("✓ Auto-restart settings correct")
        
        return True
    except Exception as e:
        print(f"✗ Service profiles test failed: {e}")
        return False

def test_keyboard_shortcuts():
    """Test keyboard shortcuts."""
    print("\nTesting Keyboard Shortcuts...")
    
    try:
        manager = OpsecStartupManagerEnhanced()
        
        # Check shortcut definitions
        expected_shortcuts = ['q', 'h', 's', 'a', 'x', 'm', 'l', 'c', 'p', 'r']
        for shortcut in expected_shortcuts:
            assert shortcut in manager.shortcuts, f"Missing shortcut: {shortcut}"
        print(f"✓ All expected shortcuts defined: {len(manager.shortcuts)}")
        
        # Check shortcut mappings
        assert manager.shortcuts['q'] == 'quit', "Quit shortcut mismatch"
        assert manager.shortcuts['a'] == 'start_all', "Start all shortcut mismatch"
        assert manager.shortcuts['x'] == 'stop_all', "Stop all shortcut mismatch"
        print("✓ Shortcut mappings correct")
        
        return True
    except Exception as e:
        print(f"✗ Keyboard shortcuts test failed: {e}")
        return False

def test_health_check_caching():
    """Test health check caching mechanism."""
    print("\nTesting Health Check Caching...")
    
    try:
        manager = OpsecStartupManagerEnhanced()
        
        # Check cache initialization
        assert hasattr(manager, 'health_cache'), "Health cache not initialized"
        assert manager.cache_ttl == 5.0, f"Expected cache TTL of 5.0, got {manager.cache_ttl}"
        print("✓ Health cache initialized correctly")
        
        # Test cache key generation
        hash1 = manager._get_cached_env_hash()
        hash2 = manager._get_cached_env_hash()
        assert hash1 == hash2, "Cache hash should be consistent"
        print("✓ Cache key generation works")
        
        return True
    except Exception as e:
        print(f"✗ Health check caching test failed: {e}")
        return False

def test_historical_metrics():
    """Test historical metrics tracking."""
    print("\nTesting Historical Metrics...")
    
    try:
        manager = OpsecStartupManagerEnhanced()
        
        # Check metrics initialization
        for service_key in manager.services:
            assert service_key in manager.historical_metrics, f"Missing metrics for {service_key}"
            assert manager.historical_metrics[service_key].maxlen == 100, f"Expected maxlen 100, got {manager.historical_metrics[service_key].maxlen}"
        print("✓ Historical metrics initialized for all services")
        
        # Test metric recording
        manager.historical_metrics["knowledge_engine"].append({
            'timestamp': datetime.now(),
            'cpu': 50.0,
            'memory': 100.0,
            'healthy': True,
            'response_time': 100.0
        })
        
        assert len(manager.historical_metrics["knowledge_engine"]) == 1, "Metric not recorded"
        print("✓ Metric recording works")
        
        # Test maxlen constraint
        for i in range(150):
            manager.historical_metrics["knowledge_engine"].append({
                'timestamp': datetime.now(),
                'cpu': i,
                'memory': i,
                'healthy': True,
                'response_time': i
            })
        
        assert len(manager.historical_metrics["knowledge_engine"]) == 100, f"Expected maxlen 100, got {len(manager.historical_metrics['knowledge_engine'])}"
        print("✓ Max length constraint works")
        
        return True
    except Exception as e:
        print(f"✗ Historical metrics test failed: {e}")
        return False

def test_log_buffers():
    """Test log buffer functionality."""
    print("\nTesting Log Buffers...")
    
    try:
        manager = OpsecStartupManagerEnhanced()
        
        # Check buffer initialization
        for service_key in manager.services:
            assert service_key in manager.log_buffers, f"Missing log buffer for {service_key}"
        print("✓ Log buffers initialized for all services")
        
        # Test log recording
        manager.log_buffers["knowledge_engine"].append("[12:00:00] Test log message")
        assert len(manager.log_buffers["knowledge_engine"]) == 1, "Log not recorded"
        print("✓ Log recording works")
        
        return True
    except Exception as e:
        print(f"✗ Log buffers test failed: {e}")
        return False

def test_auto_restart_flags():
    """Test auto-restart flag functionality."""
    print("\nTesting Auto-Restart Flags...")
    
    try:
        manager = OpsecStartupManagerEnhanced()
        
        # Check initial state
        for service_key, service in manager.services.items():
            assert not service.auto_restart, f"Auto-restart should be disabled by default for {service_key}"
        print("✓ Auto-restart disabled by default")
        
        # Test toggling
        manager.toggle_auto_restart("knowledge_engine")
        assert manager.services["knowledge_engine"].auto_restart, "Auto-restart should be enabled after toggle"
        print("✓ Auto-restart toggle works")
        
        # Test restart counter
        assert manager.services["knowledge_engine"].restart_count == 0, "Restart count should be 0 initially"
        print("✓ Restart counter initialized")
        
        return True
    except Exception as e:
        print(f"✗ Auto-restart flags test failed: {e}")
        return False

def test_enhanced_status_table():
    """Test enhanced status table creation."""
    print("\nTesting Enhanced Status Table...")
    
    try:
        manager = OpsecStartupManagerEnhanced()
        
        # Mock some service data
        manager.services["knowledge_engine"].status = ServiceStatus.RUNNING
        manager.services["knowledge_engine"].pid = 12345
        manager.services["knowledge_engine"].uptime = 300.0
        manager.services["knowledge_engine"].restart_count = 2
        manager.services["knowledge_engine"].auto_restart = True
        
        # Create table
        table = manager.create_status_table()
        
        assert table is not None, "Status table should not be None"
        print("✓ Enhanced status table created")
        
        return True
    except Exception as e:
        print(f"✗ Enhanced status table test failed: {e}")
        return False

async def test_optimized_health_check():
    """Test optimized health check with circuit breaker."""
    print("\nTesting Optimized Health Check...")
    
    try:
        manager = OpsecStartupManagerEnhanced()
        
        # Test health check for a service
        result = await manager.check_service_health_optimized("knowledge_engine")
        
        assert isinstance(result, HealthCheckResult), "Should return HealthCheckResult"
        assert result.service == "knowledge_engine", "Service name mismatch"
        assert hasattr(result, 'healthy'), "Missing healthy attribute"
        assert hasattr(result, 'response_time_ms'), "Missing response_time_ms attribute"
        assert hasattr(result, 'timestamp'), "Missing timestamp attribute"
        print("✓ Optimized health check returns correct structure")
        
        # Test circuit breaker integration
        cb = manager.circuit_breakers["knowledge_engine"]
        initial_state = cb.state
        print(f"✓ Circuit breaker state: {initial_state}")
        
        return True
    except Exception as e:
        print(f"✗ Optimized health check test failed: {e}")
        return False

def test_state_persistence():
    """Test state persistence functionality."""
    print("\nTesting State Persistence...")
    
    try:
        manager = OpsecStartupManagerEnhanced()
        
        # Test state saving
        manager.active_profile = "development"
        manager._save_state()
        print("✓ State saved successfully")
        
        # Test state loading
        manager2 = OpsecStartupManagerEnhanced()
        assert manager2.active_profile == "development", f"Expected 'development', got {manager2.active_profile}"
        print("✓ State loaded successfully")
        
        # Clean up
        state_file = os.path.join(manager.root_dir, ".opsec_state.pkl")
        if os.path.exists(state_file):
            os.remove(state_file)
        
        return True
    except Exception as e:
        print(f"✗ State persistence test failed: {e}")
        return False

def main():
    """Run all enhanced tests."""
    print("="*60)
    print("OpsecAI Enhanced Menu System - Test Suite")
    print("="*60)
    
    tests = [
        ("Enhanced Initialization", test_enhanced_initialization),
        ("Circuit Breaker", test_circuit_breaker),
        ("Service Profiles", test_service_profiles),
        ("Keyboard Shortcuts", test_keyboard_shortcuts),
        ("Health Check Caching", test_health_check_caching),
        ("Historical Metrics", test_historical_metrics),
        ("Log Buffers", test_log_buffers),
        ("Auto-Restart Flags", test_auto_restart_flags),
        ("Enhanced Status Table", test_enhanced_status_table),
        ("Optimized Health Check", test_optimized_health_check),
        ("State Persistence", test_state_persistence)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = asyncio.run(test_func())
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("Enhanced Test Summary")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All enhanced tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())