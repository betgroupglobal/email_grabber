"""
Plugin loader for discovering and loading plugin implementations.
"""

import importlib
import importlib.util
import inspect
import logging
from pathlib import Path
from typing import Dict, Type, Optional, List, TYPE_CHECKING, Any
import sys

from .base import BasePlugin, PluginConfig

# Avoid circular import
if TYPE_CHECKING:
    from config.manager import ConfigurationManager


logger = logging.getLogger(__name__)


class PluginLoader:
    """Loads and discovers plugin implementations."""
    
    def __init__(self, config_manager: Any):
        self.config_manager = config_manager
        self._plugin_classes: Dict[str, Type[BasePlugin]] = {}
    
    async def discover_plugins(self) -> List[str]:
        """Discover all available plugins in the integrations directory."""
        plugins = self.config_manager.list_available_plugins()
        
        # Try to load plugin classes for each discovered plugin
        for plugin_name in plugins:
            try:
                await self._load_plugin_class(plugin_name)
            except Exception as e:
                logger.warning(f"Failed to load plugin class for {plugin_name}: {e}")
        
        logger.info(f"Discovered {len(plugins)} plugins")
        return plugins
    
    async def _load_plugin_class(self, plugin_name: str) -> Type[BasePlugin]:
        """Load the plugin class from the plugin module."""
        if plugin_name in self._plugin_classes:
            return self._plugin_classes[plugin_name]
        
        # Construct module path
        category_dir = self.config_manager.config_dir / plugin_name
        if not category_dir.exists():
            raise FileNotFoundError(f"Plugin directory not found: {category_dir}")
        
        # Try to import the plugin module
        try:
            # Add parent directory to path if needed
            parent_dir = str(category_dir.parent)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            
            # Import plugin module using direct file loading
            plugin_file = category_dir / "plugin.py"
            if not plugin_file.exists():
                raise FileNotFoundError(f"Plugin file not found: {plugin_file}")
            
            # Use spec_from_file_location to load the module directly
            spec = importlib.util.spec_from_file_location(
                f"{plugin_name}.plugin",
                str(plugin_file)
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"Failed to create spec for {plugin_file}")
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"{plugin_name}.plugin"] = module
            spec.loader.exec_module(module)
            
            # Find BasePlugin subclass in the module
            plugin_class = None
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, BasePlugin) and 
                    obj is not BasePlugin):
                    plugin_class = obj
                    break
            
            if plugin_class is None:
                raise ValueError(f"No BasePlugin subclass found in {plugin_file}")
            
            self._plugin_classes[plugin_name] = plugin_class
            logger.info(f"Loaded plugin class: {plugin_name}")
            return plugin_class
            
        except ImportError as e:
            raise ImportError(f"Failed to import plugin module for {plugin_name}: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to load plugin class for {plugin_name}: {e}")
    
    async def load_config(self, plugin_name: str) -> PluginConfig:
        """Load plugin configuration."""
        config_dict = await self.config_manager.load_plugin_config(plugin_name)
        return PluginConfig.from_dict(config_dict)
    
    async def load_plugin_class(self, plugin_name: str) -> Type[BasePlugin]:
        """Load the plugin class (with caching)."""
        if plugin_name not in self._plugin_classes:
            return await self._load_plugin_class(plugin_name)
        return self._plugin_classes[plugin_name]
    
    def list_plugins(self) -> List[str]:
        """List discovered plugins."""
        return list(self._plugin_classes.keys())
    
    def get_plugin_class(self, plugin_name: str) -> Optional[Type[BasePlugin]]:
        """Get plugin class by name."""
        return self._plugin_classes.get(plugin_name)