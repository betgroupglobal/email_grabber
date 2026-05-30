"""
Configuration manager for plugin configurations.
"""

import yaml
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, TYPE_CHECKING
import time

from .schema import PluginConfigSchema

# Avoid circular import
if TYPE_CHECKING:
    from plugin_system.base import PluginConfig


logger = logging.getLogger(__name__)


class ConfigurationManager:
    """Manages plugin configuration loading and validation."""
    
    def __init__(
        self,
        config_dir: str = "integrations",
        vault_url: Optional[str] = None,
        vault_token: Optional[str] = None
    ):
        self.config_dir = Path(config_dir)
        self.vault_url = vault_url
        self.vault_token = vault_token
        self._cache: Dict[str, tuple] = {}  # (config, timestamp) - config is returned as dict
        self._cache_ttl = 300  # 5 minutes
        
        # Initialize Vault client if credentials provided
        self.vault_client = None
        if vault_url and vault_token:
            try:
                import hvac
                self.vault_client = hvac.Client(
                    url=vault_url,
                    token=vault_token
                )
                logger.info("Vault client initialized")
            except ImportError:
                logger.warning("hvac library not installed, Vault integration disabled")
            except Exception as e:
                logger.warning(f"Failed to initialize Vault client: {e}")
    
    async def load_plugin_config(self, plugin_name: str, use_cache: bool = True) -> Any:
        """Load and validate plugin configuration."""
        # Check cache first
        if use_cache:
            cached = self._get_from_cache(plugin_name)
            if cached:
                return cached
        
        # Load from file
        config_path = self.config_dir / plugin_name / "plugin.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Plugin config not found: {config_path}")
        
        # Load YAML file
        with open(config_path, 'r') as f:
            raw_config = yaml.safe_load(f)
        
        # Substitute environment variables
        raw_config = self._substitute_env_vars(raw_config)
        
        # Resolve secrets from Vault
        if self.vault_client:
            raw_config = await self._resolve_secrets(raw_config)
        
        # Validate against schema
        schema = PluginConfigSchema(**raw_config)
        
        # Convert to dict for caching
        config_dict = schema.dict()
        
        # Cache the result
        self._cache_config(plugin_name, config_dict)
        
        logger.info(f"Loaded plugin config: {plugin_name} v{config_dict.get('version')}")
        return config_dict
    
    def _substitute_env_vars(self, config: Any) -> Any:
        """Substitute environment variables in configuration."""
        if isinstance(config, dict):
            return {k: self._substitute_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._substitute_env_vars(item) for item in config]
        elif isinstance(config, str) and config.startswith('${') and config.endswith('}'):
            env_var = config[2:-1]
            return os.getenv(env_var, config)
        else:
            return config
    
    async def _resolve_secrets(self, config: Any) -> Any:
        """Resolve secrets from Vault."""
        if isinstance(config, dict):
            result = {}
            for k, v in config.items():
                if k == 'vault_secret':
                    secret_data = await self._get_vault_secret(v)
                    result.update(secret_data)
                else:
                    result[k] = await self._resolve_secrets(v)
            return result
        elif isinstance(config, list):
            return [await self._resolve_secrets(item) for item in config]
        else:
            return config
    
    async def _get_vault_secret(self, secret_path: str) -> Dict[str, Any]:
        """Get secret from Vault."""
        try:
            response = self.vault_client.secrets.kv.v2.read_secret_version(
                path=secret_path
            )
            return response['data']['data']
        except Exception as e:
            logger.error(f"Failed to get secret from Vault: {e}")
            return {}
    
    def _cache_config(self, plugin_name: str, config: Dict[str, Any]):
        """Cache plugin configuration."""
        self._cache[plugin_name] = (config, time.time())
    
    def _get_from_cache(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration from cache if valid."""
        if plugin_name in self._cache:
            config, timestamp = self._cache[plugin_name]
            if time.time() - timestamp < self._cache_ttl:
                return config
            else:
                # Cache expired
                del self._cache[plugin_name]
        return None
    
    def invalidate_cache(self, plugin_name: Optional[str] = None):
        """Invalidate cache for a specific plugin or all plugins."""
        if plugin_name:
            if plugin_name in self._cache:
                del self._cache[plugin_name]
        else:
            self._cache.clear()
        logger.info(f"Cache invalidated: {plugin_name or 'all'}")
    
    def list_available_plugins(self) -> List[str]:
        """List all available plugin configurations."""
        plugins = []
        
        if not self.config_dir.exists():
            return plugins
        
        for plugin_dir in self.config_dir.iterdir():
            if plugin_dir.is_dir() and (plugin_dir / "plugin.yaml").exists():
                plugins.append(plugin_dir.name)
        
        return plugins
    
    async def validate_plugin_config(self, plugin_name: str) -> bool:
        """Validate plugin configuration without loading."""
        try:
            await self.load_plugin_config(plugin_name, use_cache=False)
            return True
        except Exception as e:
            logger.error(f"Config validation failed for {plugin_name}: {e}")
            return False