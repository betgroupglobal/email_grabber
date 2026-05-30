"""
Plugin registry for managing plugin metadata and status.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from plugin_system.base import PluginConfig
from plugin_system.types import PluginStatus, HealthStatus


logger = logging.getLogger(__name__)


def _extract_capabilities(config: PluginConfig) -> List[str]:
    """Derive UI-friendly capability labels from plugin.yaml schemas."""
    schemas = config.schemas or {}
    props = (schemas.get("input") or {}).get("properties") or {}
    operation = props.get("operation") or {}
    if isinstance(operation.get("enum"), list):
        return [str(v) for v in operation["enum"]]
    scan_type = props.get("scan_type") or {}
    if isinstance(scan_type.get("enum"), list):
        return [f"scan:{v}" for v in scan_type["enum"]]
    if config.execution_types:
        return list(config.execution_types)
    return []


class PluginRegistry:
    """Registry for managing plugin metadata and status."""
    
    def __init__(self):
        self._plugins: Dict[str, Dict[str, any]] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize the registry."""
        self._initialized = True
        logger.info("Plugin registry initialized")
    
    async def register(self, plugin_name: str, config: PluginConfig):
        """Register a plugin in the registry."""
        self._plugins[plugin_name] = {
            "name": config.name,
            "version": config.version,
            "category": config.category,
            "description": config.description,
            "author": config.author,
            "license": config.license,
            "execution_types": config.execution_types,
            "capabilities": _extract_capabilities(config),
            "opsec_enabled": bool(config.opsec and config.opsec.get("enabled")),
            "status": PluginStatus.READY,
            "health_status": HealthStatus.UNKNOWN,
            "registered_at": datetime.utcnow().isoformat(),
            "last_health_check": None,
            "last_run": None,
        }
        logger.info(f"Plugin registered: {plugin_name}")
    
    async def unregister(self, plugin_name: str):
        """Unregister a plugin from the registry."""
        if plugin_name in self._plugins:
            del self._plugins[plugin_name]
            logger.info(f"Plugin unregistered: {plugin_name}")
    
    async def get_plugin_info(self, plugin_name: str) -> Optional[Dict]:
        """Get plugin information from registry."""
        return self._plugins.get(plugin_name)
    
    async def list_plugins(self) -> List[Dict]:
        """List all registered plugins."""
        return [
            {
                "name": info["name"],
                "version": info["version"],
                "category": info["category"],
                "description": info["description"],
                "author": info["author"],
                "license": info["license"],
                "status": info["status"].value,
                "health_status": info["health_status"].value,
                "capabilities": info.get("capabilities") or [],
                "execution_types": info.get("execution_types") or [],
                "opsec_enabled": info.get("opsec_enabled", False),
                "last_run": info.get("last_run"),
                "last_health_check": info.get("last_health_check"),
            }
            for info in self._plugins.values()
        ]

    async def record_last_run(self, plugin_name: str, timestamp: Optional[str] = None):
        """Record last successful or attempted execution time for catalog UI."""
        if plugin_name in self._plugins:
            self._plugins[plugin_name]["last_run"] = timestamp or datetime.utcnow().isoformat()
    
    async def update_status(self, plugin_name: str, status: PluginStatus):
        """Update plugin status."""
        if plugin_name in self._plugins:
            self._plugins[plugin_name]["status"] = status
    
    async def update_health_status(self, plugin_name: str, health_status: HealthStatus):
        """Update plugin health status."""
        if plugin_name in self._plugins:
            self._plugins[plugin_name]["health_status"] = health_status
            self._plugins[plugin_name]["last_health_check"] = datetime.utcnow().isoformat()
    
    async def get_status(self, plugin_name: str) -> Optional[PluginStatus]:
        """Get plugin status."""
        info = self._plugins.get(plugin_name)
        return info["status"] if info else None
    
    async def get_health_status(self, plugin_name: str) -> Optional[HealthStatus]:
        """Get plugin health status."""
        info = self._plugins.get(plugin_name)
        return info["health_status"] if info else None