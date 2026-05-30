"""
Configuration settings for the Integration Hub.
"""

from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    """Integration Hub settings."""
    
    # Service
    SERVICE_NAME: str = "integration-hub"
    SERVICE_HOST: str = "0.0.0.0"
    SERVICE_PORT: int = 8500
    
    # Environment
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    
    # Integration Configuration
    INTEGRATION_CONFIG_DIR: str = "/Users/adminuser/attack-dataset/backend/integrations/integrations"
    INTEGRATION_PLUGIN_DIR: str = "/Users/adminuser/attack-dataset/backend/integrations/integrations"
    
    # Service Authentication
    SERVICE_API_KEY: Optional[str] = None
    
    # Dependencies
    POSTGRES_DSN: Optional[str] = None
    REDIS_URL: str = "redis://localhost:6379"
    
    # Vault (optional)
    VAULT_URL: Optional[str] = None
    VAULT_TOKEN: Optional[str] = None
    
    # Docker (for sandboxed execution)
    DOCKER_HOST: Optional[str] = None
    
    # OpSec Integration
    OPSEC_MONITOR_URL: str = "http://localhost:8002"
    OPSEC_ASSESSMENT_ENABLED: bool = True
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()