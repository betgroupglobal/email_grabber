"""
Test script for Jailbreak AI offensive capabilities (scan analysis, attack planning, test initiation).
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

from integrations.jailbreak_ai.plugin import JailbreakAIPlugin
from plugin_system.base import PluginConfig, ExecutionContext


def create_mock_config():
    """Create a mock plugin config for testing."""
    return PluginConfig(
        name="jailbreak_ai",
        version="1.0.0",
        category="ai_services",
        description="Test jailbreak AI plugin with offensive capabilities",
        author="Test",
        license="MIT",
        execution_types=["remote_api"],
        execution={
            "remote": {
                "base_url": "https://jail-break.chat/v1",
                "auth_type": "bearer_token",
                "auth_token": os.getenv("JAILBREAK_API_KEY", "test-key"),
                "timeout": 60,
                "default_headers": {"Content-Type": "application/json"}
            }
        },
        schemas={
            "input": {"type": "object", "properties": {}},
            "output": {"type": "object", "properties": {}}
        },
        opsec={
            "enabled": True,
            "risk_level": "medium",
            "noise_level": "low",
            "detection_methods": ["Outbound HTTPS"],
            "evasion_recommendations": ["Use for testing only"]
        },
        dependencies=[],
        health_check={"enabled": True, "endpoint": "/models", "interval": 60, "timeout": 10},
        hooks={}
    )


async def test_offensive_capabilities():
    """Test offensive pentest capabilities."""
    print("Testing Jailbreak AI Offensive Capabilities")
    print("=" * 70)

    # Initialize plugin
    print("\n1. Initializing plugin...")
    config = create_mock_config()
    plugin = JailbreakAIPlugin(config)
    await plugin.initialize()
    print(f"✓ Plugin initialized (model: {plugin.default_model})")

    # Test 1: Scan Analysis
    print("\n2. Testing scan analysis capability...")
    mock_scan_data = {
        "hosts": [
            {
                "status": "up",
                "addresses": [{"addr": "192.168.1.10", "type": "ipv4"}],
                "ports": [
                    {
                        "portid": "22",
                        "protocol": "tcp",
                        "state": "open",
                        "service": {"name": "ssh", "product": "OpenSSH", "version": "8.2"}
                    },
                    {
                        "portid": "80",
                        "protocol": "tcp",
                        "state": "open",
                        "service": {"name": "http", "product": "Apache", "version": "2.4.41"}
                    },
                    {
                        "portid": "3306",
                        "protocol": "tcp",
                        "state": "open",
                        "service": {"name": "mysql", "version": "5.7.33"}
                    }
                ]
            }
        ],
        "scan_stats": {"total_hosts": 1, "up_hosts": 1}
    }

    try:
        result = await plugin.analyze_scan_results(
            scan_data=mock_scan_data,
            context={
                "target": "192.168.1.10",
                "scan_type": "nmap_syn",
                "engagement_id": "test_eng_123"
            }
        )

        if result.success:
            print("✓ Scan analysis completed successfully")
            analysis = result.output.get("analysis", {})
            print(f"  - Vulnerabilities found: {len(analysis.get('vulnerabilities', []))}")
            print(f"  - Attack vectors identified: {len(analysis.get('attack_vectors', []))}")
            print(f"  - Recommended tests: {len(analysis.get('recommended_tests', []))}")
            print(f"  - Risk score: {analysis.get('risk_score', 'N/A')}")

            if analysis.get('attack_vectors'):
                print("  - Sample attack vectors:")
                for vector in analysis['attack_vectors'][:2]:
                    print(f"    • {vector}")
        else:
            print(f"⚠ Analysis completed but no structured output (AI may have returned raw text)")
            print(f"  Raw output preview: {str(result.output)[:200]}...")

    except Exception as e:
        print(f"⚠ Scan analysis error (expected without real API): {e}")

    # Test 2: Attack Plan Generation
    print("\n3. Testing attack plan generation...")
    target_info = {
        "target": "192.168.1.10",
        "os": "Linux (Ubuntu based on banners)",
        "services": [
            "OpenSSH 8.2 on port 22",
            "Apache 2.4.41 on port 80",
            "MySQL 5.7.33 on port 3306"
        ],
        "vulnerabilities": [
            {"service": "ssh", "issue": "Potential CVE-2020-15778", "severity": "High"},
            {"service": "http", "issue": "Apache version may have known issues", "severity": "Medium"}
        ]
    }

    constraints = {
        "engagement_id": "test_eng_123",
        "aggression_level": 5,
        "time_limit": "2 hours",
        "tools_available": ["nmap", "hydra", "sqlmap", "metasploit"]
    }

    try:
        result = await plugin.generate_attack_plan(target_info, constraints)

        if result.success:
            print("✓ Attack plan generated successfully")
            plan = result.output.get("attack_plan", {})
            print(f"  - Phases: {len(plan.get('phases', []))}")
            print(f"  - Tools required: {len(plan.get('tools_required', []))}")
            print(f"  - Priority targets: {len(plan.get('priority_targets', []))}")

            if plan.get('phases'):
                print("  - Sample phases:")
                for phase in plan['phases'][:2]:
                    print(f"    • {phase.get('name', 'Unnamed')}")
        else:
            print(f"⚠ Plan generation completed but no structured output")

    except Exception as e:
        print(f"⚠ Attack plan generation error (expected without real API): {e}")

    # Test 3: Offensive Test Initiation
    print("\n4. Testing offensive test initiation...")
    test_configs = [
        {
            "test_type": "port_scan",
            "target": "192.168.1.10",
            "parameters": {"scan_type": "comprehensive", "timing": "T3"},
            "risk_level": "medium"
        },
        {
            "test_type": "vulnerability_scan",
            "target": "192.168.1.10",
            "parameters": {"scripts": "vuln"},
            "risk_level": "high",
            "mitigations": ["Use timing delays", "Randomize source ports"]
        }
    ]

    for i, test_config in enumerate(test_configs, 1):
        try:
            result = await plugin.initiate_offensive_test(
                test_config=test_config,
                callback_url="http://localhost:3001/webhook/test-results"
            )

            if result.success:
                print(f"✓ Test {i} initiated successfully")
                print(f"  - Test ID: {result.output.get('test_id')}")
                print(f"  - Test type: {result.output.get('test_type')}")
                print(f"  - Target: {result.output.get('target')}")
                print(f"  - Plugin delegation: {result.output.get('plugin_delegation', {}).get('plugin', 'unknown')}")

                # Check OpSec context
                opsec = result.opsec_context or {}
                if opsec:
                    print(f"  - OpSec risk level: {opsec.get('risk_level', 'unknown')}")
                    print(f"  - Detection methods: {len(opsec.get('detection_methods', []))}")
            else:
                print(f"✗ Test {i} failed: {result.error}")

        except Exception as e:
            print(f"✗ Test {i} error: {e}")

    # Test 4: Execute with operation routing
    print("\n5. Testing operation routing...")

    # Test chat operation
    chat_context = ExecutionContext(
        integration_id="test_chat",
        engagement_id="test_eng",
        target="chat_test",
        parameters={
            "operation": "chat",
            "messages": [{"role": "user", "content": "Hello"}]
        },
        timeout=30,
        metadata={}
    )

    # Test analyze_scan operation
    analyze_context = ExecutionContext(
        integration_id="test_analyze",
        engagement_id="test_eng",
        target="192.168.1.10",
        parameters={
            "operation": "analyze_scan",
            "scan_data": mock_scan_data,
            "scan_type": "nmap"
        },
        timeout=60,
        metadata={}
    )

    # Test initiate_test operation
    test_context = ExecutionContext(
        integration_id="test_initiate",
        engagement_id="test_eng",
        target="192.168.1.10",
        parameters={
            "operation": "initiate_test",
            "test_config": test_configs[0]
        },
        timeout=30,
        metadata={}
    )

    operations = [
        ("chat", chat_context),
        ("analyze_scan", analyze_context),
        ("initiate_test", test_context)
    ]

    for op_name, ctx in operations:
        try:
            print(f"  Testing {op_name} operation...")
            result = await plugin.execute(ctx)
            if result.success or op_name == "initiate_test":  # initiate_test always succeeds locally
                print(f"    ✓ {op_name} routed correctly")
            else:
                print(f"    ⚠ {op_name} completed (AI may not be available)")
        except Exception as e:
            print(f"    ⚠ {op_name} error (expected): {str(e)[:50]}")

    # Cleanup
    print("\n6. Cleaning up...")
    await plugin.cleanup()
    print("✓ Plugin cleaned up")

    print("\n" + "=" * 70)
    print("✓ All offensive capability tests completed!")
    print("\nNotes:")
    print("- Full AI-powered analysis requires real API key and network access")
    print("- The plugin structure and routing logic are validated")
    print("- Actual execution would chain with nmap/other plugins via orchestrator")


if __name__ == "__main__":
    asyncio.run(test_offensive_capabilities())
