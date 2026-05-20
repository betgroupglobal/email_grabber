"""
Test script to verify the plugin system works.
"""

import asyncio
import sys
import os

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

from plugin_system import PluginManager
from plugin_system.base import ExecutionContext


async def test_plugin_system():
    """Test the plugin system."""
    print("Testing OpsecAI Integration Plugin System...")
    
    # Initialize plugin manager
    print("1. Initializing plugin manager...")
    manager = PluginManager(config_dir="integrations")
    
    try:
        await manager.initialize()
        print("✓ Plugin manager initialized")
    except Exception as e:
        print(f"✗ Failed to initialize plugin manager: {e}")
        return
    
    # List plugins
    print("\n2. Listing available plugins...")
    try:
        plugins = await manager.list_plugins()
        print(f"✓ Found {len(plugins)} plugin(s):")
        for plugin in plugins:
            print(f"  - {plugin['name']} v{plugin['version']} ({plugin['category']})")
    except Exception as e:
        print(f"✗ Failed to list plugins: {e}")
        return
    
    if not plugins:
        print("No plugins found. Exiting.")
        return
    
    # Test plugin info
    plugin_name = plugins[0]['name']
    print(f"\n3. Getting plugin info for {plugin_name}...")
    try:
        info = await manager.get_plugin_info(plugin_name)
        print(f"✓ Plugin info:")
        print(f"  - Name: {info['name']}")
        print(f"  - Version: {info['version']}")
        print(f"  - Category: {info['category']}")
        print(f"  - Status: {info['status']}")
    except Exception as e:
        print(f"✗ Failed to get plugin info: {e}")
        return
    
    # Test plugin health
    print(f"\n4. Checking plugin health for {plugin_name}...")
    try:
        health = await manager.health_check(plugin_name)
        print(f"✓ Health check:")
        print(f"  - Healthy: {health.get('healthy')}")
        if health.get('version'):
            print(f"  - Version: {health.get('version')}")
    except Exception as e:
        print(f"✗ Failed health check: {e}")
    
    # Shutdown
    print("\n5. Shutting down plugin manager...")
    await manager.shutdown()
    print("✓ Plugin manager shutdown complete")
    
    print("\n✓ All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_plugin_system())