#!/usr/bin/env python3
"""
Test script for OpsecAI menu system validation
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from opsec_menu import OpsecStartupManager
from module_analyzer import ModuleAnalyzer
import asyncio

def test_menu_initialization():
    """Test menu system initialization."""
    print("Testing Menu System Initialization...")
    
    try:
        manager = OpsecStartupManager()
        print("✓ Menu manager initialized successfully")
        
        # Check service definitions
        assert len(manager.services) == 9, f"Expected 9 services, got {len(manager.services)}"
        print(f"✓ Service definitions loaded: {len(manager.services)} services")
        
        # Check environment loading
        assert manager.root_dir, "Root directory not set"
        print(f"✓ Root directory: {manager.root_dir}")
        
        return True
    except Exception as e:
        print(f"✗ Menu initialization failed: {e}")
        return False

def test_analyzer_initialization():
    """Test module analyzer initialization."""
    print("\nTesting Module Analyzer Initialization...")
    
    try:
        analyzer = ModuleAnalyzer()
        print("✓ Module analyzer initialized successfully")
        
        # Check module metrics
        assert len(analyzer.module_metrics) == 8, f"Expected 8 modules, got {len(analyzer.module_metrics)}"
        print(f"✓ Module metrics loaded: {len(analyzer.module_metrics)} modules")
        
        # Check dependency graph
        assert len(analyzer.dependency_graph) > 0, "Dependency graph is empty"
        print(f"✓ Dependency graph built: {len(analyzer.dependency_graph)} nodes")
        
        return True
    except Exception as e:
        print(f"✗ Analyzer initialization failed: {e}")
        return False

def test_system_health_check():
    """Test system health check functionality."""
    print("\nTesting System Health Check...")
    
    try:
        manager = OpsecStartupManager()
        results = asyncio.run(manager.system_health_check())
        
        print("✓ System health check completed")
        print(f"  Health checks passed: {sum(1 for v in results.values() if v is True)}")
        print(f"  Health checks failed: {sum(1 for v in results.values() if v is False)}")
        
        return True
    except Exception as e:
        print(f"✗ System health check failed: {e}")
        return False

def test_configuration_validation():
    """Test configuration validation."""
    print("\nTesting Configuration Validation...")
    
    try:
        manager = OpsecStartupManager()
        is_valid = manager.validate_configuration()
        
        print("✓ Configuration validation completed")
        print(f"  Configuration valid: {is_valid}")
        
        return True
    except Exception as e:
        print(f"✗ Configuration validation failed: {e}")
        return False

def test_module_metrics_update():
    """Test module metrics update."""
    print("\nTesting Module Metrics Update...")
    
    try:
        analyzer = ModuleAnalyzer()
        
        # Update system metrics
        analyzer.update_system_metrics()
        print("✓ System metrics updated")
        print(f"  CPU: {analyzer.system_metrics.cpu_percent:.1f}%")
        print(f"  Memory: {analyzer.system_metrics.memory_percent:.1f}%")
        
        # Update module metrics
        for module_name in analyzer.module_metrics:
            analyzer.update_module_metrics(module_name)
        print("✓ Module metrics updated")
        
        return True
    except Exception as e:
        print(f"✗ Module metrics update failed: {e}")
        return False

def test_dependency_graph():
    """Test dependency graph structure."""
    print("\nTesting Dependency Graph Structure...")
    
    try:
        analyzer = ModuleAnalyzer()
        
        # Check for critical dependencies
        assert "postgres" in analyzer.dependency_graph, "PostgreSQL not in dependency graph"
        assert "knowledge_engine" in analyzer.dependency_graph, "Knowledge engine not in dependency graph"
        assert "orchestrator" in analyzer.dependency_graph, "Orchestrator not in dependency graph"
        
        print("✓ Dependency graph structure validated")
        
        # Check dependency relationships
        ke_deps = analyzer.dependency_graph["knowledge_engine"].depends_on
        assert "postgres" in ke_deps or "qdrant" in ke_deps, "Knowledge engine missing core dependencies"
        print("✓ Dependency relationships validated")
        
        return True
    except Exception as e:
        print(f"✗ Dependency graph test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("="*60)
    print("OpsecAI Menu System - Test Suite")
    print("="*60)
    
    tests = [
        ("Menu Initialization", test_menu_initialization),
        ("Analyzer Initialization", test_analyzer_initialization),
        ("System Health Check", test_system_health_check),
        ("Configuration Validation", test_configuration_validation),
        ("Module Metrics Update", test_module_metrics_update),
        ("Dependency Graph", test_dependency_graph)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())