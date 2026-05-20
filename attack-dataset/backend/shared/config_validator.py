"""
Configuration validation for OpsecAI services.

Provides configuration schema validation, runtime checks, and environment variable validation.
"""

import os
import logging
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity of validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationResult:
    """Result of configuration validation."""
    is_valid: bool
    issues: List[Dict[str, Any]]
    
    def add_issue(
        self,
        severity: ValidationSeverity,
        field: str,
        message: str,
        suggested_value: Optional[Any] = None
    ):
        """Add a validation issue."""
        self.issues.append({
            "severity": severity.value,
            "field": field,
            "message": message,
            "suggested_value": suggested_value
        })
        
        if severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]:
            self.is_valid = False
    
    def get_issues_by_severity(self, severity: ValidationSeverity) -> List[Dict[str, Any]]:
        """Get issues filtered by severity."""
        return [issue for issue in self.issues if issue["severity"] == severity.value]
    
    def has_critical_issues(self) -> bool:
        """Check if there are critical issues."""
        return any(
            issue["severity"] == ValidationSeverity.CRITICAL.value
            for issue in self.issues
        )


class ConfigValidator:
    """Configuration validator."""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.validators: Dict[str, List[Callable]] = {}
        self.required_fields: List[str] = []
        self.optional_fields: Dict[str, Any] = {}
    
    def add_validator(self, field: str, validator: Callable[[Any], Optional[str]]):
        """
        Add a validator function for a field.
        
        Args:
            field: Field name
            validator: Function that takes field value and returns error message if invalid, None if valid
        """
        if field not in self.validators:
            self.validators[field] = []
        self.validators[field].append(validator)
    
    def require_field(self, field: str, default_value: Any = None):
        """
        Mark a field as required.
        
        Args:
            field: Field name
            default_value: Default value if field is missing (None means no default)
        """
        self.required_fields.append(field)
        if default_value is not None:
            self.optional_fields[field] = default_value
    
    def optional_field(self, field: str, default_value: Any):
        """
        Mark a field as optional with default value.
        
        Args:
            field: Field name
            default_value: Default value
        """
        self.optional_fields[field] = default_value
    
    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """
        Validate configuration dictionary.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            ValidationResult with any issues found
        """
        result = ValidationResult(is_valid=True, issues=[])
        
        # Check required fields
        for field in self.required_fields:
            if field not in config or config[field] is None:
                if field in self.optional_fields:
                    result.add_issue(
                        severity=ValidationSeverity.WARNING,
                        field=field,
                        message=f"Required field '{field}' is missing, using default value",
                        suggested_value=self.optional_fields[field]
                    )
                    config[field] = self.optional_fields[field]
                else:
                    result.add_issue(
                        severity=ValidationSeverity.CRITICAL,
                        field=field,
                        message=f"Required field '{field}' is missing"
                    )
        
        # Run field validators
        for field, validators in self.validators.items():
            if field in config:
                value = config[field]
                for validator in validators:
                    error_message = validator(value)
                    if error_message:
                        result.add_issue(
                            severity=ValidationSeverity.ERROR,
                            field=field,
                            message=error_message
                        )
        
        return result
    
    def validate_env_vars(self, env_vars: Dict[str, str]) -> ValidationResult:
        """
        Validate environment variables.
        
        Args:
            env_vars: Environment variables dictionary
            
        Returns:
            ValidationResult with any issues found
        """
        result = ValidationResult(is_valid=True, issues=[])
        
        # Check required environment variables
        for field in self.required_fields:
            env_key = field.upper()
            if env_key not in env_vars or not env_vars[env_key]:
                if field in self.optional_fields:
                    result.add_issue(
                        severity=ValidationSeverity.WARNING,
                        field=env_key,
                        message=f"Required environment variable '{env_key}' is missing, using default value",
                        suggested_value=self.optional_fields[field]
                    )
                else:
                    result.add_issue(
                        severity=ValidationSeverity.CRITICAL,
                        field=env_key,
                        message=f"Required environment variable '{env_key}' is missing"
                    )
        
        return result


def create_common_validators() -> Dict[str, List[Callable]]:
    """Create common validation functions."""
    return {
        "port": [
            lambda x: None if isinstance(x, int) and 1 <= x <= 65535 else "Port must be between 1 and 65535"
        ],
        "url": [
            lambda x: None if isinstance(x, str) and x.startswith(("http://", "https://")) else "URL must start with http:// or https://"
        ],
        "timeout": [
            lambda x: None if isinstance(x, (int, float)) and x > 0 else "Timeout must be positive"
        ],
        "api_key": [
            lambda x: None if isinstance(x, str) and len(x) >= 10 else "API key must be at least 10 characters"
        ],
        "log_level": [
            lambda x: None if x.upper() in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] else "Log level must be DEBUG, INFO, WARNING, ERROR, or CRITICAL"
        ],
        "environment": [
            lambda x: None if x.lower() in ["development", "staging", "production"] else "Environment must be development, staging, or production"
        ]
    }


def validate_service_config(
    service_name: str,
    config: Dict[str, Any],
    required_fields: List[str],
    optional_fields: Optional[Dict[str, Any]] = None
) -> ValidationResult:
    """
    Validate service configuration with common rules.
    
    Args:
        service_name: Name of the service
        config: Configuration dictionary
        required_fields: List of required field names
        optional_fields: Dictionary of optional fields with default values
        
    Returns:
        ValidationResult
    """
    validator = ConfigValidator(service_name)
    
    # Add common validators
    common_validators = create_common_validators()
    for field, validators in common_validators.items():
        for validator_func in validators:
            validator.add_validator(field, validator_func)
    
    # Mark required fields
    for field in required_fields:
        validator.require_field(field)
    
    # Mark optional fields
    if optional_fields:
        for field, default_value in optional_fields.items():
            validator.optional_field(field, default_value)
    
    return validator.validate_config(config)


def validate_file_path(path: str, must_exist: bool = True, must_be_file: bool = True) -> Optional[str]:
    """
    Validate file path.
    
    Args:
        path: File path to validate
        must_exist: Whether the path must exist
        must_be_file: Whether the path must be a file (not a directory)
        
    Returns:
        Error message if invalid, None if valid
    """
    if not isinstance(path, str):
        return "Path must be a string"
    
    if must_exist:
        if not os.path.exists(path):
            return f"Path does not exist: {path}"
        
        if must_be_file and not os.path.isfile(path):
            return f"Path is not a file: {path}"
        
        if not must_be_file and os.path.isfile(path):
            return f"Path is a file, expected directory: {path}"
    
    return None


def validate_database_url(url: str) -> Optional[str]:
    """
    Validate database connection URL.
    
    Args:
        url: Database URL to validate
        
    Returns:
        Error message if invalid, None if valid
    """
    if not isinstance(url, str):
        return "Database URL must be a string"
    
    if not url.startswith(("postgresql://", "postgres://", "mysql://", "sqlite://")):
        return "Database URL must start with postgresql://, postgres://, mysql://, or sqlite://"
    
    return None


def validate_redis_url(url: str) -> Optional[str]:
    """
    Validate Redis connection URL.
    
    Args:
        url: Redis URL to validate
        
    Returns:
        Error message if invalid, None if valid
    """
    if not isinstance(url, str):
        return "Redis URL must be a string"
    
    if not url.startswith("redis://"):
        return "Redis URL must start with redis://"
    
    return None


class ConfigSanitizer:
    """Sanitize configuration by removing sensitive values."""
    
    SENSITIVE_KEYS = [
        "password", "passwd", "secret", "token", "api_key", "api_key",
        "private_key", "access_token", "refresh_token", "auth_token"
    ]
    
    @classmethod
    def sanitize(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize configuration by masking sensitive values.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Sanitized configuration dictionary
        """
        sanitized = {}
        
        for key, value in config.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in cls.SENSITIVE_KEYS):
                if isinstance(value, str) and len(value) > 0:
                    sanitized[key] = f"***{value[-4:]}" if len(value) > 4 else "***"
                else:
                    sanitized[key] = "***"
            elif isinstance(value, dict):
                sanitized[key] = cls.sanitize(value)
            else:
                sanitized[key] = value
        
        return sanitized
    
    @classmethod
    def sanitize_for_logging(cls, config: Dict[str, Any]) -> str:
        """
        Sanitize configuration for logging.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            String representation of sanitized configuration
        """
        sanitized = cls.sanitize(config)
        return str(sanitized)


def load_and_validate_config(
    config_path: str,
    service_name: str,
    required_fields: List[str],
    optional_fields: Optional[Dict[str, Any]] = None
) -> tuple[Dict[str, Any], ValidationResult]:
    """
    Load configuration from file and validate it.
    
    Args:
        config_path: Path to configuration file
        service_name: Name of the service
        required_fields: List of required field names
        optional_fields: Dictionary of optional fields with default values
        
    Returns:
        Tuple of (config_dict, validation_result)
    """
    import json
    
    # Load configuration
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        config = {}
    except json.JSONDecodeError as e:
        config = {}
        logger.error(f"Failed to parse configuration file: {e}")
    
    # Validate configuration
    result = validate_service_config(
        service_name,
        config,
        required_fields,
        optional_fields
    )
    
    return config, result