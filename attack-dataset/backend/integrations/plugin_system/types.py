"""
Type definitions for the plugin system.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel


class ExecutionType(str, Enum):
    """Types of execution supported by plugins."""
    LOCAL_BINARY = "local_binary"
    REMOTE_API = "remote_api"
    HYBRID = "hybrid"


class PluginStatus(str, Enum):
    """Status of a plugin."""
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"
    DISABLED = "disabled"


class ExecutionStatus(str, Enum):
    """Status of an execution."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class HealthStatus(str, Enum):
    """Health status of a plugin."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ExecutionContext:
    """Context for plugin execution."""
    integration_id: str
    engagement_id: str
    target: str
    parameters: Dict[str, Any]
    timeout: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_type: ExecutionType = ExecutionType.LOCAL_BINARY


@dataclass
class ExecutionResult:
    """Result of plugin execution."""
    success: bool
    output: Any
    error: Optional[str]
    artifacts: List[Dict[str, Any]]
    opsec_context: Optional[Dict[str, Any]]
    execution_time: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "artifacts": self.artifacts,
            "opsec_context": self.opsec_context,
            "execution_time": self.execution_time
        }


@dataclass
class PluginMetadata:
    """Metadata about a plugin."""
    name: str
    version: str
    category: str
    description: str
    author: str
    license: str
    execution_types: List[ExecutionType]
    status: PluginStatus = PluginStatus.LOADING


class OpSecConfig(BaseModel):
    """OpSec configuration for a plugin."""
    enabled: bool = False
    risk_level: str = "medium"
    noise_level: str = "medium"
    detection_methods: List[str] = []
    evasion_recommendations: List[str] = []


class HealthCheckConfig(BaseModel):
    """Health check configuration for a plugin."""
    enabled: bool = True
    endpoint: Optional[str] = None
    interval: int = 30
    timeout: int = 5


class DependencyConfig(BaseModel):
    """Dependency configuration for a plugin."""
    name: str
    version: Optional[str] = None
    install_url: Optional[str] = None


class PluginConfigModel(BaseModel):
    """Pydantic model for plugin configuration."""
    name: str
    version: str
    category: str
    description: str
    author: str
    license: str
    execution: Dict[str, Any]
    schemas: Dict[str, Any]
    opsec: Optional[OpSecConfig] = None
    dependencies: List[DependencyConfig] = []
    health_check: Optional[HealthCheckConfig] = None
    hooks: Dict[str, List[str]] = {}