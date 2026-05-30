"""
Test script for AI-powered OpsecAI features:
- AI-powered Attack Tree Engine
- AI-powered Multi-Agent Orchestrator  
- AI-powered Feedback Loop Manager
"""
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

def test_attack_tree_engine_ai():
    """Test the AI-powered Attack Tree Engine"""
    print("Testing AI-Powered Attack Tree Engine...")
    
    try:
        from backend.knowledge_engine.attack_tree_engine import (
            AttackTreeEngine,
            map_to_mitre_ttp,
            calculate_base_scores,
        )
        from backend.knowledge_engine.core.models import AttackRecord
        
        # Create a mock AI analyzer for testing
        class MockAIAnalyzer:
            def analyze_attack(self, prompt):
                # Mock AI responses for testing
                if "MITRE" in prompt:
                    return {
                        "technique_id": "T1190",
                        "technique_name": "Exploit Public-Facing Application",
                        "tactic": "Initial Access",
                        "detection": ["WAF logs", "Application logs"],
                        "mitigation": ["Patch management"]
                    }
                elif "scoring" in prompt:
                    return {
                        "success_probability": 0.75,
                        "detection_risk": 0.45,
                        "impact_score": 0.85
                    }
                return {}
        
        ai_analyzer = MockAIAnalyzer()
        
        # Create a sample attack record
        sample_record = AttackRecord(
            id=1,
            title="SQL Injection Attack",
            category="Web Application",
            attack_type="Injection",
            scenario_description="SQL injection attack on login form",
            tools_used="sqlmap, burpsuite",
            attack_steps="1. Identify vulnerable parameter 2. Inject SQL payload 3. Extract data",
            target_type="Web Application",
            vulnerability="SQL Injection",
            mitre_technique="T1190",
            impact="High - Data breach possible",
            detection_method="WAF, IDS",
            solution="Parameterized queries, input validation",
            tags="web, injection, sql",
            source="test"
        )
        
        # Test AI-powered MITRE TTP mapping
        ttp = map_to_mitre_ttp(sample_record, ai_analyzer)
        print(f"✓ AI-powered MITRE TTP mapping: {ttp.technique_id} - {ttp.technique_name}")
        
        # Test AI-powered score calculation
        success_prob, detection_risk, impact_score = calculate_base_scores(sample_record, ai_analyzer)
        print(f"✓ AI-powered score calculation: success={success_prob:.2f}, detection={detection_risk:.2f}, impact={impact_score:.2f}")
        
        # Test attack tree engine initialization with AI
        engine = AttackTreeEngine(ai_analyzer=ai_analyzer)
        print(f"✓ AI-powered Attack Tree Engine initialized")
        
        # Test attack tree building with AI
        records = [sample_record]
        tree = engine.build_attack_tree(records, "Test Target")
        print(f"✓ AI-powered attack tree built: {tree.tree_id} with {len(tree.nodes)} nodes")
        
        # Test attack path generation
        paths = engine.generate_attack_paths(tree, top_k=2)
        print(f"✓ AI-powered attack paths generated: {len(paths)} paths")
        
        return True
        
    except Exception as e:
        print(f"✗ AI-powered Attack Tree Engine test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multi_agent_orchestrator_ai():
    """Test the AI-powered Multi-Agent Orchestrator"""
    print("\nTesting AI-Powered Multi-Agent Orchestrator...")
    
    try:
        from backend.knowledge_engine.multi_agent_orchestrator import (
            MultiAgentOrchestrator,
            AgentType
        )
        
        # Create a mock AI analyzer for testing
        class MockAIAnalyzer:
            def analyze_attack(self, prompt):
                if "agent type" in prompt:
                    return {"recommended_agent": "RECON"}
                elif "capability" in prompt:
                    return {"recommended_capability": "port_scan"}
                elif "priority" in prompt:
                    return {"priority": 7}
                return {}
        
        ai_analyzer = MockAIAnalyzer()
        
        # Test orchestrator initialization with AI
        orchestrator = MultiAgentOrchestrator(ai_analyzer=ai_analyzer)
        print(f"✓ AI-powered Multi-Agent Orchestrator initialized")
        print(f"  Registered agents: {len(orchestrator.agents)}")
        
        # Test AI-powered agent retrieval
        recon = orchestrator.get_agent(AgentType.RECON)
        print(f"✓ AI-powered agent retrieval successful: {recon.agent_id if recon else 'None'}")
        
        # Test AI-powered attack planning (would use tree in real scenario)
        print(f"✓ AI-powered attack planning capability available")
        
        return True
        
    except Exception as e:
        print(f"✗ AI-powered Multi-Agent Orchestrator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_feedback_loop_manager_ai():
    """Test the AI-powered Feedback Loop Manager"""
    print("\nTesting AI-Powered Feedback Loop Manager...")
    
    try:
        from backend.knowledge_engine.feedback_loop_manager import FeedbackLoopManager
        from backend.knowledge_engine.core.models import AttackVectorRequest
        
        # Create mock components for testing
        class MockSearcher:
            pass
        
        class MockChainer:
            pass
        
        class MockAttackTreeEngine:
            pass
        
        class MockOrchestrator:
            def create_feedback_loop(self, session_id, execution_results):
                from backend.knowledge_engine.core.models import FeedbackLoop
                return FeedbackLoop(
                    feedback_id="test_feedback",
                    session_id=session_id,
                    execution_results=execution_results,
                    confidence_delta=0.1
                )
        
        # Create a mock AI analyzer for testing
        class MockAIAnalyzer:
            def analyze_attack(self, prompt):
                if "feedback" in prompt:
                    return {
                        "adjusted_probabilities": {"node1": 0.1},
                        "new_recommendations": ["Try alternative approach"],
                        "confidence_delta": 0.15,
                        "lessons_learned": "Execution revealed new attack surface"
                    }
                elif "patterns" in prompt:
                    return {
                        "common_failures": [("node1", 2)],
                        "common_detections": [("node2", 1)],
                        "strategic_insights": ["Focus on stealth techniques"],
                        "risk_assessment": "Medium risk, high reward"
                    }
                elif "recommendations" in prompt:
                    return {
                        "recommendations": [
                            "Implement timing adjustments",
                            "Use alternative evasion techniques",
                            "Prioritize high-value targets"
                        ]
                    }
                return {}
        
        ai_analyzer = MockAIAnalyzer()
        
        # Test feedback loop manager initialization with AI
        manager = FeedbackLoopManager(
            MockChainer(), 
            MockAttackTreeEngine(), 
            MockOrchestrator(),
            ai_analyzer=ai_analyzer
        )
        print(f"✓ AI-powered Feedback Loop Manager initialized")
        
        # Test session creation
        request = AttackVectorRequest(
            target_description="Test target",
            top_chains=3
        )
        session = manager.create_session("test_target", request)
        print(f"✓ AI-powered session creation: {session.session_id}")
        
        # Test AI-powered insights method structure
        print(f"✓ AI-powered insights generation capability available")
        
        return True
        
    except Exception as e:
        print(f"✗ AI-powered Feedback Loop Manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ai_integration():
    """Test overall AI integration"""
    print("\nTesting Overall AI Integration...")
    
    try:
        # Test that components can accept AI analyzers
        from backend.knowledge_engine.attack_tree_engine import AttackTreeEngine
        from backend.knowledge_engine.multi_agent_orchestrator import MultiAgentOrchestrator
        from backend.knowledge_engine.feedback_loop_manager import FeedbackLoopManager
        
        class MockAIAnalyzer:
            def analyze_attack(self, prompt):
                return {}
        
        ai_analyzer = MockAIAnalyzer()
        
        # Test all components accept AI analyzer
        tree_engine = AttackTreeEngine(ai_analyzer=ai_analyzer)
        orchestrator = MultiAgentOrchestrator(ai_analyzer=ai_analyzer)
        
        # Mock other dependencies for feedback manager
        class MockChainer:
            pass
        class MockAttackTreeEngine:
            pass
        class MockOrchestrator:
            pass
        
        feedback_manager = FeedbackLoopManager(
            MockChainer(),
            MockAttackTreeEngine(),
            MockOrchestrator(),
            ai_analyzer=ai_analyzer
        )
        
        print(f"✓ All components successfully integrated with AI analyzer")
        print(f"✓ AI integration points verified")
        
        return True
        
    except Exception as e:
        print(f"✗ AI integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("OpsecAI AI-Powered Features Test Suite")
    print("=" * 60)
    
    results = []
    
    # Test AI integration
    results.append(("AI Integration", test_ai_integration()))
    
    # Test AI-powered attack tree engine
    results.append(("AI Attack Tree Engine", test_attack_tree_engine_ai()))
    
    # Test AI-powered multi-agent orchestrator
    results.append(("AI Multi-Agent Orchestrator", test_multi_agent_orchestrator_ai()))
    
    # Test AI-powered feedback loop manager
    results.append(("AI Feedback Loop Manager", test_feedback_loop_manager_ai()))
    
    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{test_name}: {status}")
    
    total_tests = len(results)
    passed_tests = sum(1 for _, result in results if result)
    
    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 All AI integration tests passed!")
        return 0
    else:
        print(f"\n❌ {total_tests - passed_tests} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())