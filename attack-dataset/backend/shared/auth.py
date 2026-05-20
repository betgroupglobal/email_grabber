"""
Authentication and authorization library for OpsecAI services.

Provides JWT-based authentication, role-based access control (RBAC),
and password hashing utilities.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import os
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from dotenv import load_dotenv

import jwt as pyjwt
import bcrypt

# Load environment variables
load_dotenv()


# ── Configuration ──────────────────────────────────────────────────────────────

# JWT Configuration
JWT_SECRET_KEY = secrets.token_urlsafe(64)  # In production, load from environment
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60
JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing
def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password_hash(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


# ── User Roles ──────────────────────────────────────────────────────────────────

class Role:
    """User roles with permission levels."""
    ADMIN = "admin"          # Full access to all operations
    OPERATOR = "operator"    # Can run engagements and view results
    ANALYST = "analyst"      # Read-only access to knowledge base
    VIEWER = "viewer"        # Limited read access
    
    @classmethod
    def all(cls) -> List[str]:
        return [cls.ADMIN, cls.OPERATOR, cls.ANALYST, cls.VIEWER]
    
    @classmethod
    def hierarchy(cls) -> Dict[str, int]:
        """Role hierarchy (higher = more permissions)."""
        return {
            cls.VIEWER: 1,
            cls.ANALYST: 2,
            cls.OPERATOR: 3,
            cls.ADMIN: 4
        }


# ── User Model ─────────────────────────────────────────────────────────────────

@dataclass
class User:
    """User model for authentication."""
    id: str
    username: str
    email: str
    role: str
    is_active: bool = True
    created_at: Optional[datetime] = None
    
    def has_permission(self, required_role: str) -> bool:
        """Check if user has required role or higher."""
        user_level = Role.hierarchy().get(self.role, 0)
        required_level = Role.hierarchy().get(required_role, 999)
        return user_level >= required_level
    
    def can_perform_action(self, action: str) -> bool:
        """Check if user can perform specific action."""
        # Define action permissions
        action_permissions = {
            # Engagement operations
            "create_engagement": Role.OPERATOR,
            "view_engagement": Role.OPERATOR,
            "delete_engagement": Role.ADMIN,
            
            # Knowledge base operations
            "search_knowledge": Role.ANALYST,
            "view_attack_details": Role.ANALYST,
            
            # OpSec operations
            "run_opsec_audit": Role.OPERATOR,
            "view_opsec_results": Role.OPERATOR,
            
            # AI operations
            "use_ai_chat": Role.OPERATOR,
            "generate_ai_reports": Role.OPERATOR,
            
            # Admin operations
            "manage_users": Role.ADMIN,
            "view_system_metrics": Role.ADMIN,
            "configure_system": Role.ADMIN,
        }
        
        required_role = action_permissions.get(action, Role.ADMIN)
        return self.has_permission(required_role)


# ── Password Utilities ──────────────────────────────────────────────────────────

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return verify_password_hash(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    # Truncate password to 72 bytes to avoid bcrypt limitation
    if len(password) > 72:
        password = password[:72]
    return hash_password(password)


def generate_api_key() -> str:
    """Generate a secure API key."""
    return secrets.token_urlsafe(32)


def verify_api_key(api_key: str, stored_hash: str) -> bool:
    """Verify an API key against its hash."""
    return hmac.compare_digest(
        hashlib.sha256(api_key.encode()).hexdigest(),
        stored_hash
    )


# ── JWT Token Management ────────────────────────────────────────────────────────

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })
    
    encoded_jwt = pyjwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })
    
    encoded_jwt = pyjwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT token."""
    try:
        payload = pyjwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except pyjwt.PyJWTError:
        return None


def verify_token(token: str) -> Optional[User]:
    """Verify a JWT token and return the user."""
    payload = decode_token(token)
    if not payload:
        return None
    
    user_id = payload.get("sub")
    username = payload.get("username")
    email = payload.get("email")
    role = payload.get("role")
    
    if not all([user_id, username, role]):
        return None
    
    return User(
        id=user_id,
        username=username,
        email=email or "",
        role=role,
        is_active=payload.get("is_active", True)
    )


# ── Authentication Errors ───────────────────────────────────────────────────────

class AuthError(Exception):
    """Base authentication error."""
    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class InvalidCredentialsError(AuthError):
    """Invalid username or password."""
    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(message, 401)


class InvalidTokenError(AuthError):
    """Invalid or expired token."""
    def __init__(self, message: str = "Invalid or expired token"):
        super().__init__(message, 401)


class InsufficientPermissionsError(AuthError):
    """User lacks required permissions."""
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, 403)


class UserInactiveError(AuthError):
    """User account is inactive."""
    def __init__(self, message: str = "User account is inactive"):
        super().__init__(message, 403)


# ── Token Extractors ───────────────────────────────────────────────────────────

def extract_token_from_header(authorization: str) -> Optional[str]:
    """Extract JWT token from Authorization header."""
    if not authorization:
        return None
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            return None
        return token
    except ValueError:
        return None


def extract_token_from_query(token: str) -> Optional[str]:
    """Extract JWT token from query parameter."""
    return token if token else None


# ── Service-to-Service Authentication ───────────────────────────────────────────

# Service API keys loaded from environment variables
SERVICE_API_KEYS = {
    "orchestrator": os.getenv("SERVICE_API_KEY_ORCHESTRATOR", ""),
    "analyzer": os.getenv("SERVICE_API_KEY_ANALYZER", ""),
    "monitor": os.getenv("SERVICE_API_KEY_MONITOR", ""),
    "knowledge-engine": os.getenv("SERVICE_API_KEY_KNOWLEDGE_ENGINE", ""),
}


def get_service_api_key(service_name: str) -> str:
    """Get API key for a service."""
    return SERVICE_API_KEYS.get(service_name, "")


def verify_service_token(token: str, service_name: str) -> bool:
    """Verify service-to-service authentication token."""
    expected_key = get_service_api_key(service_name)
    if not expected_key:
        return False
    
    return hmac.compare_digest(
        hashlib.sha256(token.encode()).hexdigest(),
        hashlib.sha256(expected_key.encode()).hexdigest()
    )


def verify_service_api_key(api_key: str) -> Optional[str]:
    """
    Verify a service API key and return the service name.
    
    Args:
        api_key: The API key to verify
        
    Returns:
        Service name if valid, None otherwise
    """
    if not api_key:
        return None
    
    for service_name, expected_key in SERVICE_API_KEYS.items():
        if expected_key and hmac.compare_digest(api_key, expected_key):
            return service_name
    
    return None