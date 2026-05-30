"""
OpsecAI Integration Plugin System

Provides a flexible plugin architecture for integrating external tools,
APIs, and services into the OpsecAI platform.
"""

from .base import (
    BasePlugin,
    PluginConfig,
    ExecutionContext,
    ExecutionResult
)
from .types import (
    PluginStatus,
    ExecutionStatus,
    HealthStatus,
    ExecutionType
)
from .manager import PluginManager

__version__ = "1.0.0"
__all__ = [
    "BasePlugin",
    "PluginConfig", 
    "ExecutionContext",
    "ExecutionResult",
    "ExecutionType",
    "PluginStatus",
    "ExecutionStatus",
    "HealthStatus",
    "PluginManager"
]