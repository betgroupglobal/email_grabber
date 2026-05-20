"""
Configuration schema validation.
"""

from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional, List
from plugin_system.types import (
    OpSecConfig,
    HealthCheckConfig,
    DependencyConfig
)


class PluginConfigSchema(BaseModel):
    """Schema for plugin configuration validation."""
    name: str = Field(..., pattern=r"^[a-z0-9_]+$", description="Plugin name (lowercase, alphanumeric, underscores)")
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$", description="Semantic version (x.y.z)")
    category: str = Field(..., description="Plugin category")
    description: str = Field(..., min_length=10, description="Plugin description (min 10 chars)")
    author: str = Field(..., description="Plugin author")
    license: str = Field(..., description="Plugin license")
    execution: Dict[str, Any] = Field(..., description="Execution configuration")
    schemas: Dict[str, Any] = Field(..., description="Input/output schemas")
    opsec: Optional[OpSecConfig] = Field(None, description="OpSec configuration")
    dependencies: List[DependencyConfig] = Field(default_factory=list, description="Plugin dependencies")
    health_check: Optional[HealthCheckConfig] = Field(None, description="Health check configuration")
    hooks: Dict[str, List[str]] = Field(default_factory=dict, description="Event hooks")
    
    @validator('execution')
    def validate_execution_config(cls, v):
        """Validate that execution config has local or remote section."""
        if not isinstance(v, dict):
            raise ValueError("Execution config must be a dictionary")
        
        if 'local' not in v and 'remote' not in v:
            raise ValueError("Execution config must include 'local' or 'remote' section")
        
        return v
    
    @validator('schemas')
    def validate_schemas(cls, v):
        """Validate that schemas include input and output."""
        if not isinstance(v, dict):
            raise ValueError("Schemas must be a dictionary")
        
        if 'input' not in v:
            raise ValueError("Schemas must include 'input' schema")
        
        if 'output' not in v:
            raise ValueError("Schemas must include 'output' schema")
        
        return v
    
    class Config:
        extra = "forbid"  # Reject additional fields