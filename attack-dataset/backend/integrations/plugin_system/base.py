"""
Base plugin class and interfaces.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

from .types import (
    ExecutionContext,
    ExecutionResult,
    PluginConfigModel,
    PluginStatus,
    HealthStatus
)


logger = logging.getLogger(__name__)


@dataclass
class PluginConfig:
    """Configuration for a plugin."""
    name: str
    version: str
    category: str
    description: str
    author: str
    license: str
    execution_types: List[str]
    execution: Dict[str, Any]
    schemas: Dict[str, Any]
    opsec: Optional[Dict[str, Any]]
    dependencies: List[Dict[str, Any]]
    health_check: Optional[Dict[str, Any]]
    hooks: Dict[str, List[str]]
    
    @classmethod
    def from_model(cls, model: PluginConfigModel) -> 'PluginConfig':
        """Create PluginConfig from Pydantic model."""
        return cls(
            name=model.name,
            version=model.version,
            category=model.category,
            description=model.description,
            author=model.author,
            license=model.license,
            execution_types=list(model.execution.keys()) if model.execution else [],
            execution=model.execution,
            schemas=model.schemas,
            opsec=model.opsec.dict() if model.opsec else None,
            dependencies=[d.dict() for d in model.dependencies] if model.dependencies else [],
            health_check=model.health_check.dict() if model.health_check else None,
            hooks=model.hooks
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PluginConfig':
        """Create PluginConfig from dictionary."""
        return cls(
            name=data.get('name', ''),
            version=data.get('version', ''),
            category=data.get('category', ''),
            description=data.get('description', ''),
            author=data.get('author', ''),
            license=data.get('license', ''),
            execution_types=data.get('execution_types', []),
            execution=data.get('execution', {}),
            schemas=data.get('schemas', {}),
            opsec=data.get('opsec'),
            dependencies=data.get('dependencies', []),
            health_check=data.get('health_check'),
            hooks=data.get('hooks', {})
        )


class BasePlugin(ABC):
    """Base class for all integration plugins."""
    
    def __init__(self, config: PluginConfig):
        self.config = config
        self._initialized = False
        self._status = PluginStatus.LOADING
        self.logger = logging.getLogger(f"plugin.{config.name}")
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the plugin (load dependencies, connect to services)."""
        pass
    
    @abstractmethod
    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        """Execute the integration with given context."""
        pass
    
    @abstractmethod
    async def validate_input(self, parameters: Dict[str, Any]) -> bool:
        """Validate input parameters against schema."""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check plugin health and availability."""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup resources before shutdown."""
        pass
    
    # Optional hooks with default implementations
    async def before_execution(self, context: ExecutionContext) -> ExecutionContext:
        """Hook called before execution. Can modify context."""
        return context
    
    async def after_execution(self, result: ExecutionResult, context: ExecutionContext) -> ExecutionResult:
        """Hook called after execution. Can modify result."""
        return result
    
    async def on_error(self, error: Exception, context: ExecutionContext) -> None:
        """Hook called on execution error."""
        self.logger.error(f"Execution error: {error}", exc_info=True)
    
    # Status management
    @property
    def status(self) -> PluginStatus:
        """Get current plugin status."""
        return self._status
    
    @status.setter
    def status(self, value: PluginStatus):
        """Set plugin status."""
        self._status = value
    
    @property
    def is_initialized(self) -> bool:
        """Check if plugin is initialized."""
        return self._initialized
    
    @property
    def name(self) -> str:
        """Get plugin name."""
        return self.config.name
    
    @property
    def version(self) -> str:
        """Get plugin version."""
        return self.config.version
    
    def get_info(self) -> Dict[str, Any]:
        """Get plugin information."""
        return {
            "name": self.config.name,
            "version": self.config.version,
            "category": self.config.category,
            "description": self.config.description,
            "author": self.config.author,
            "license": self.config.license,
            "status": self._status.value,
            "execution_types": self.config.execution_types
        }