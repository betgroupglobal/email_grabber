"""
Test script for new OpsecAI features:
- Attack Tree Engine
- Multi-Agent Orchestrator  
- Feedback Loop Manager
"""
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

def test_attack_tree_engine():
    """Test the Attack Tree Engine basic functionality"""
    print("Testing Attack Tree Engine...")
    
    try:
        from backend.knowledge_engine.attack_tree_engine import (
            AttackTreeEngine,
            map_to_mitre_ttp,
            calculate_base_scores,
            extract_tools
        )
        from backend.knowledge_engine.core.models import AttackRecord
        
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
        
        # Test MITRE TTP mapping
        ttp = map_to_mitre_ttp(sample_record)
        print(f"✓ MITRE TTP mapping: {ttp.technique_id} - {ttp.technique_name}")
        
        # Test score calculation
        success_prob, detection_risk, impact_score = calculate_base_scores(sample_record)
        print(f"✓ Score calculation: success={success_prob:.2f}, detection={detection_risk:.2f}, impact={impact_score:.2f}")
        
        # Test tool extraction
        tools = extract_tools(sample_record)
        print(f"✓ Tool extraction: {tools}")
        
        # Test attack tree engine initialization
        engine = AttackTreeEngine()
        print(f"✓ Attack Tree Engine initialized")
        
        # Test attack tree building
        records = [sample_record]
        tree = engine.build_attack_tree(records, "Test Target")
        print(f"✓ Attack tree built: {tree.tree_id} with {len(tree.nodes)} nodes")
        
        # Test attack path generation
        paths = engine.generate_attack_paths(tree, top_k=2)
        print(f"✓ Attack paths generated: {len(paths)} paths")
        
        return True
        
    except Exception as e:
        print(f"✗ Attack Tree Engine test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multi_agent_orchestrator():
    """Test the Multi-Agent Orchestrator basic functionality"""
    print("\nTesting Multi-Agent Orchestrator...")
    
    try:
        from backend.knowledge_engine.multi_agent_orchestrator import (
            MultiAgentOrchestrator,
            ReconAgent,
            ExploitAgent,
            PostExploitationAgent,
            CleanupAgent,
            AgentType
        )
        
        # Test individual agent initialization
        recon_agent = ReconAgent()
        print(f"✓ Recon Agent initialized: {recon_agent.agent_id}")
        print(f"  Capabilities: {len(recon_agent.capabilities)}")
        
        exploit_agent = ExploitAgent()
        print(f"✓ Exploit Agent initialized: {exploit_agent.agent_id}")
        print(f"  Capabilities: {len(exploit_agent.capabilities)}")
        
        post_exploit_agent = PostExploitationAgent()
        print(f"✓ Post-Exploitation Agent initialized: {post_exploit_agent.agent_id}")
        print(f"  Capabilities: {len(post_exploit_agent.capabilities)}")
        
        cleanup_agent = CleanupAgent()
        print(f"✓ Cleanup Agent initialized: {cleanup_agent.agent_id}")
        print(f"  Capabilities: {len(cleanup_agent.capabilities)}")
        
        # Test orchestrator initialization
        orchestrator = MultiAgentOrchestrator()
        print(f"✓ Multi-Agent Orchestrator initialized")
        print(f"  Registered agents: {len(orchestrator.agents)}")
        
        # Test agent retrieval
        recon = orchestrator.get_agent(AgentType.RECON)
        print(f"✓ Agent retrieval successful: {recon.agent_id if recon else 'None'}")
        
        return True
        
    except Exception as e:
        print(f"✗ Multi-Agent Orchestrator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_models():
    """Test the new data models"""
    print("\nTesting New Data Models...")
    
    try:
        from backend.knowledge_engine.core.models import (
            MITRETTP,
            AttackTreeNode,
            AttackTree,
            AttackPath,
            ExecutionResult,
            FeedbackLoop,
            AdaptiveAttackRequest,
            AdaptiveAttackResponse
        )
        
        # Test MITRE TTP model
        ttp = MITRETTP(
            technique_id="T1190",
            technique_name="Exploit Public-Facing Application",
            tactic="Initial Access",
            detection=["WAF logs", "Application logs"],
            mitigation=["Patch management"],
            is_custom=False
        )
        print(f"✓ MITRETTP model: {ttp.technique_id}")
        
        # Test Attack Tree Node model
        node = AttackTreeNode(
            node_id="test_node",
            attack_record_id=1,
            mitre_ttp=ttp,
            phase="Initial Access",
            success_probability=0.7,
            detection_risk=0.5,
            impact_score=0.8
        )
        print(f"✓ AttackTreeNode model: {node.node_id}")
        
        # Test Attack Tree model
        tree = AttackTree(
            tree_id="test_tree",
            target_description="Test target",
            nodes={"test_node": node},
            root_nodes=["test_node"],
            leaf_nodes=["test_node"]
        )
        print(f"✓ AttackTree model: {tree.tree_id}")
        
        # Test Attack Path model
        path = AttackPath(
            path_id="test_path",
            tree_id="test_tree",
            node_sequence=["test_node"],
            cumulative_score=0.7,
            success_probability=0.7,
            detection_risk=0.5,
            estimated_time=60
        )
        print(f"✓ AttackPath model: {path.path_id}")
        
        # Test Execution Result model
        result = ExecutionResult(
            result_id="test_result",
            path_id="test_path",
            node_id="test_node",
            status="success",
            actual_time=45,
            detected=False
        )
        print(f"✓ ExecutionResult model: {result.result_id}")
        
        # Test Feedback Loop model
        feedback = FeedbackLoop(
            feedback_id="test_feedback",
            session_id="test_session",
            execution_results=[result]
        )
        print(f"✓ FeedbackLoop model: {feedback.feedback_id}")
        
        return True
        
    except Exception as e:
        print(f"✗ Data models test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("OpsecAI New Features Test Suite")
    print("=" * 60)
    
    results = []
    
    # Test data models
    results.append(("Data Models", test_models()))
    
    # Test attack tree engine
    results.append(("Attack Tree Engine", test_attack_tree_engine()))
    
    # Test multi-agent orchestrator
    results.append(("Multi-Agent Orchestrator", test_multi_agent_orchestrator()))
    
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
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n❌ {total_tests - passed_tests} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())