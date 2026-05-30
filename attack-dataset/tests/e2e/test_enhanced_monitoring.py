#!/usr/bin/env python3
"""
Test script for enhanced monitoring visualization
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from module_analyzer_enhanced import ModuleAnalyzerEnhanced

def test_enhanced_initialization():
    """Test enhanced module analyzer initialization."""
    print("Testing Enhanced Module Analyzer Initialization...")
    
    try:
        analyzer = ModuleAnalyzerEnhanced()
        print("✓ Enhanced module analyzer initialized successfully")
        
        # Check module metrics
        assert len(analyzer.module_metrics) == 8, f"Expected 8 modules, got {len(analyzer.module_metrics)}"
        print(f"✓ Module metrics loaded: {len(analyzer.module_metrics)} modules")
        
        # Check dependency graph
        assert len(analyzer.dependency_graph) > 0, "Dependency graph is empty"
        print(f"✓ Dependency graph built: {len(analyzer.dependency_graph)} nodes")
        
        # Check monitoring interval
        assert analyzer.monitoring_interval == 1.0, f"Expected 1.0s interval, got {analyzer.monitoring_interval}"
        print("✓ Enhanced monitoring interval set (1.0s)")
        
        return True
    except Exception as e:
        print(f"✗ Enhanced initialization failed: {e}")
        return False

def test_visual_components():
    """Test that visual components can be created."""
    print("\nTesting Visual Components...")
    
    try:
        analyzer = ModuleAnalyzerEnhanced()
        
        # Test system metrics update
        analyzer.update_system_metrics()
        print("✓ System metrics updated successfully")
        
        # Test module metrics update
        for module_name in analyzer.module_metrics:
            analyzer.update_module_metrics(module_name)
        print("✓ Module metrics updated successfully")
        
        # Test header creation
        if analyzer.console:
            header = analyzer.create_enhanced_header()
            assert header is not None, "Header creation failed"
            print("✓ Enhanced header created successfully")
        
        # Test system overview panel
        if analyzer.console:
            overview = analyzer.create_system_overview_panel()
            assert overview is not None, "Overview panel creation failed"
            print("✓ System overview panel created successfully")
        
        # Test enhanced module table
        if analyzer.console:
            table = analyzer.create_enhanced_module_table()
            assert table is not None, "Module table creation failed"
            print("✓ Enhanced module table created successfully")
        
        # Test dependency tree
        if analyzer.console:
            tree = analyzer.create_enhanced_dependency_tree()
            assert tree is not None, "Dependency tree creation failed"
            print("✓ Enhanced dependency tree created successfully")
        
        # Test performance panel
        if analyzer.console:
            perf = analyzer.create_enhanced_performance_panel()
            assert perf is not None, "Performance panel creation failed"
            print("✓ Enhanced performance panel created successfully")
        
        # Test stats summary
        if analyzer.console:
            stats = analyzer.create_stats_summary_panel()
            assert stats is not None, "Stats summary creation failed"
            print("✓ Stats summary panel created successfully")
        
        return True
    except Exception as e:
        print(f"✗ Visual components test failed: {e}")
        return False

def test_progress_bars():
    """Test progress bar generation."""
    print("\nTesting Progress Bar Generation...")
    
    try:
        analyzer = ModuleAnalyzerEnhanced()
        
        # Test various progress bar values
        test_values = [0, 25, 50, 75, 100]
        for value in test_values:
            bar = analyzer._create_progress_bar(value)
            assert len(bar) == 20, f"Expected bar length 20, got {len(bar)}"
            assert "█" in bar or value == 0, f"Bar should contain filled characters for value {value}"
        
        print("✓ Progress bar generation works for all test values")
        return True
    except Exception as e:
        print(f"✗ Progress bar test failed: {e}")
        return False

def main():
    """Run all enhanced monitoring tests."""
    print("="*60)
    print("OpsecAI Enhanced Monitoring - Test Suite")
    print("="*60)
    
    tests = [
        ("Enhanced Initialization", test_enhanced_initialization),
        ("Visual Components", test_visual_components),
        ("Progress Bars", test_progress_bars)
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
        print("\n🎉 All enhanced monitoring tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())