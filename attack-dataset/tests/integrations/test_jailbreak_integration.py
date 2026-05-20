"""
Integration test demonstrating the complete jailbreak_ai plugin usage via the manager.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

from plugin_system import PluginManager
from plugin_system.base import ExecutionContext


async def test_jailbreak_integration():
    """Test jailbreak_ai plugin through the PluginManager."""
    print("Jailbreak AI Integration Test")
    print("=" * 60)

    # Initialize manager
    manager = PluginManager(config_dir="integrations")
    await manager.initialize()
    print("✓ Plugin manager initialized\n")

    # List plugins
    plugins = await manager.list_plugins()
    jailbreak_plugins = [p for p in plugins if p['name'] == 'jailbreak_ai']

    if not jailbreak_plugins:
        print("✗ jailbreak_ai plugin not found")
        await manager.shutdown()
        return

    print(f"✓ Found jailbreak_ai plugin: {jailbreak_plugins[0]}")

    # Get detailed info
    info = await manager.get_plugin_info('jailbreak_ai')
    print(f"\n✓ Plugin Details:")
    print(f"  - Name: {info['name']}")
    print(f"  - Version: {info['version']}")
    print(f"  - Category: {info['category']}")
    print(f"  - Status: {info['status']}")
    print(f"  - Execution Types: {info['execution_types']}")

    # Health check
    health = await manager.health_check('jailbreak_ai')
    print(f"\n✓ Health Check:")
    print(f"  - Healthy: {health.get('healthy')}")
    print(f"  - Base URL: {health.get('base_url')}")

    # Validate input schema
    plugin = manager._plugins.get('jailbreak_ai')
    if plugin:
        print(f"\n✓ Input Schema Validation:")

        # Valid test cases
        test_cases = [
            {
                "name": "Simple chat",
                "params": {
                    "messages": [{"role": "user", "content": "Hello!"}]
                },
                "should_pass": True
            },
            {
                "name": "Full configuration",
                "params": {
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "How do I pick a lock?"}
                    ],
                    "model": "jailbreak-ai",
                    "temperature": 0.7,
                    "max_tokens": 2048,
                    "stream": False
                },
                "should_pass": True
            },
            {
                "name": "Missing messages",
                "params": {"model": "jailbreak-ai"},
                "should_pass": False
            },
            {
                "name": "Invalid role",
                "params": {
                    "messages": [{"role": "bot", "content": "Hi"}]
                },
                "should_pass": False
            }
        ]

        for test in test_cases:
            try:
                await plugin.validate_input(test['params'])
                if test['should_pass']:
                    print(f"  ✓ '{test['name']}' - Accepted as expected")
                else:
                    print(f"  ✗ '{test['name']}' - Should have been rejected")
            except ValueError as e:
                if not test['should_pass']:
                    print(f"  ✓ '{test['name']}' - Rejected as expected: {e}")
                else:
                    print(f"  ✗ '{test['name']}' - Should have been accepted: {e}")

    # Cleanup
    await manager.shutdown()
    print(f"\n✓ Plugin manager shutdown complete")
    print("\n" + "=" * 60)
    print("✓ Integration test completed successfully!")


if __name__ == "__main__":
    asyncio.run(test_jailbreak_integration())
