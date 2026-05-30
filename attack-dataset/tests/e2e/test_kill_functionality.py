#!/usr/bin/env python3
"""
Test script for kill functionality
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from opsec_menu_enhanced import OpsecStartupManagerEnhanced

def test_kill_methods_exist():
    """Test that kill methods exist."""
    print("Testing Kill Methods Existence...")
    
    try:
        manager = OpsecStartupManagerEnhanced()
        
        # Check kill_all_services method exists
        assert hasattr(manager, 'kill_all_services'), "kill_all_services method not found"
        print("✓ kill_all_services method exists")
        
        # Check _kill_service method exists
        assert hasattr(manager, '_kill_service'), "_kill_service method not found"
        print("✓ _kill_service method exists")
        
        # Check kill shortcut exists
        assert 'k' in manager.shortcuts, "Kill shortcut 'k' not found"
        assert manager.shortcuts['k'] == 'kill_all', "Kill shortcut mapping incorrect"
        print("✓ Kill shortcut 'k' mapped correctly")
        
        return True
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

def test_menu_integration():
    """Test that kill option is integrated in menu."""
    print("\nTesting Menu Integration...")
    
    try:
        manager = OpsecStartupManagerEnhanced()
        
        # Test that handle_shortcut can handle kill action
        # We won't actually run it to avoid killing processes
        assert 'kill_all' in manager.shortcuts.values(), "kill_all action not in shortcuts"
        print("✓ Kill action integrated in shortcuts")
        
        return True
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

def test_service_termination_logic():
    """Test the service termination logic."""
    print("\nTesting Service Termination Logic...")
    
    try:
        manager = OpsecStartupManagerEnhanced()
        
        # Test that _kill_service method can be called without crashing
        # (it won't actually kill anything if no processes are running)
        manager._kill_service("knowledge_engine")
        print("✓ _kill_service can be called safely")
        
        # Verify service status is updated
        assert manager.services["knowledge_engine"].status.value == "stopped", "Service status not updated"
        print("✓ Service status updated to stopped")
        
        return True
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

def main():
    """Run all kill functionality tests."""
    print("="*60)
    print("OpsecAI Kill Functionality - Test Suite")
    print("="*60)
    
    tests = [
        ("Kill Methods Existence", test_kill_methods_exist),
        ("Menu Integration", test_menu_integration),
        ("Service Termination Logic", test_service_termination_logic)
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
        print("\n🎉 All kill functionality tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())