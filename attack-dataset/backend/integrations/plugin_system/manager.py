"""
Plugin manager - main entry point for plugin system.
"""

import logging
from typing import Dict, Optional, List, TYPE_CHECKING, Any

from .base import BasePlugin, ExecutionContext, ExecutionResult
from .loader import PluginLoader
from .registry import PluginRegistry
from .lifecycle import LifecycleManager

# Avoid circular import
if TYPE_CHECKING:
    from config.manager import ConfigurationManager


logger = logging.getLogger(__name__)


class PluginManager:
    """Manages plugin lifecycle and execution."""
    
    def __init__(self, config_dir: str = "integrations"):
        # Import here to avoid circular dependency
        from config.manager import ConfigurationManager
        self.config_manager = ConfigurationManager(config_dir=config_dir)
        self.loader = PluginLoader(self.config_manager)
        self.registry = PluginRegistry()
        self.lifecycle = LifecycleManager()
        self._plugins: Dict[str, BasePlugin] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize plugin manager."""
        if self._initialized:
            return
        
        # Initialize registry
        await self.registry.initialize()
        
        # Discover plugins
        await self.loader.discover_plugins()
        
        # Load all discovered plugins
        for plugin_name in self.loader.list_plugins():
            try:
                await self.load_plugin(plugin_name)
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_name}: {e}")
        
        self._initialized = True
        logger.info("Plugin manager initialized")
    
    async def load_plugin(self, plugin_name: str) -> BasePlugin:
        """Load and initialize a plugin."""
        if plugin_name in self._plugins:
            return self._plugins[plugin_name]
        
        # Load plugin configuration
        config = await self.loader.load_config(plugin_name)
        
        # Load plugin class
        plugin_class = await self.loader.load_plugin_class(plugin_name)
        
        # Instantiate plugin
        plugin = plugin_class(config)
        
        # Initialize plugin
        await plugin.initialize()
        
        # Update plugin status
        plugin.status = plugin.status.READY
        
        # Register plugin
        await self.registry.register(plugin_name, config)
        
        # Store plugin
        self._plugins[plugin_name] = plugin
        
        logger.info(f"Plugin loaded: {plugin_name}")
        return plugin
    
    async def unload_plugin(self, plugin_name: str):
        """Unload and cleanup a plugin."""
        if plugin_name in self._plugins:
            plugin = self._plugins[plugin_name]
            
            try:
                await plugin.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up plugin {plugin_name}: {e}")
            
            del self._plugins[plugin_name]
            await self.registry.unregister(plugin_name)
            
            logger.info(f"Plugin unloaded: {plugin_name}")
    
    async def execute(
        self,
        plugin_name: str,
        context: ExecutionContext
    ) -> ExecutionResult:
        """Execute a plugin with given context."""
        plugin = await self.get_plugin(plugin_name)
        
        # Validate input
        await plugin.validate_input(context.parameters)
        
        # Execute with lifecycle hooks
        result = await self.lifecycle.execute_with_hooks(plugin, context)
        
        return result
    
    async def get_plugin(self, plugin_name: str) -> BasePlugin:
        """Get a loaded plugin, load if necessary."""
        if plugin_name not in self._plugins:
            return await self.load_plugin(plugin_name)
        return self._plugins[plugin_name]
    
    async def list_plugins(self) -> List[Dict]:
        """List all available plugins."""
        return await self.registry.list_plugins()
    
    async def get_plugin_info(self, plugin_name: str) -> Dict:
        """Get plugin information."""
        info = await self.registry.get_plugin_info(plugin_name)
        if not info:
            raise ValueError(f"Plugin not found: {plugin_name}")
        return info
    
    async def health_check(self, plugin_name: str) -> Dict:
        """Check plugin health."""
        plugin = await self.get_plugin(plugin_name)
        
        try:
            health = await plugin.health_check()
            
            # Update registry
            from .types import HealthStatus
            health_status = HealthStatus.HEALTHY if health.get('healthy') else HealthStatus.UNHEALTHY
            await self.registry.update_health_status(plugin_name, health_status)
            
            return health
        except Exception as e:
            logger.error(f"Health check failed for {plugin_name}: {e}")
            return {"healthy": False, "error": str(e)}
    
    async def shutdown(self):
        """Shutdown plugin manager."""
        for plugin_name in list(self._plugins.keys()):
            try:
                await self.unload_plugin(plugin_name)
            except Exception as e:
                logger.error(f"Error unloading plugin {plugin_name}: {e}")
        
        self._initialized = False
        logger.info("Plugin manager shutdown complete")