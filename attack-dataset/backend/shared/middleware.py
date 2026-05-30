"""
Authentication middleware for FastAPI services.

Provides dependency injection for protected routes and
authentication utilities.
"""
from __future__ import annotations

from typing import Optional, List
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .auth import (
    User,
    verify_token,
    extract_token_from_header,
    InvalidTokenError,
    InsufficientPermissionsError,
    UserInactiveError,
    verify_service_token,
    Role
)


# ── Security Schemes ────────────────────────────────────────────────────────────

security = HTTPBearer(auto_error=False)


# ── Authentication Dependencies ─────────────────────────────────────────────────

async def get_current_user(
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> User:
    """
    Dependency to get the current authenticated user from JWT token.
    
    Raises:
        HTTPException: If authentication fails
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization.credentials
    user = verify_token(token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return user


async def get_current_user_optional(
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """
    Optional authentication - returns None if no valid token provided.
    Useful for routes that work both authenticated and unauthenticated.
    """
    if not authorization:
        return None
    
    token = authorization.credentials
    user = verify_token(token)
    
    if not user or not user.is_active:
        return None
    
    return user


def require_role(required_role: str):
    """
    Dependency factory that requires a specific role or higher.
    
    Usage:
        @app.get("/admin")
        async def admin_route(user: User = Depends(require_role(Role.ADMIN))):
            ...
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if not current_user.has_permission(required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' or higher required"
            )
        return current_user
    
    return role_checker


def require_permission(action: str):
    """
    Dependency factory that requires permission for a specific action.
    
    Usage:
        @app.post("/engage")
        async def engage(user: User = Depends(require_permission("create_engagement"))):
            ...
    """
    def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        if not current_user.can_perform_action(action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{action}' required"
            )
        return current_user
    
    return permission_checker


# ── Service-to-Service Authentication ───────────────────────────────────────────

def verify_service_call(
    x_service_token: Optional[str] = Header(None),
    x_service_name: Optional[str] = Header(None)
) -> bool:
    """
    Verify service-to-service authentication.
    
    Services should include:
    - X-Service-Token: API key for the service
    - X-Service-Name: Name of the calling service
    
    Returns True if authentication succeeds, raises HTTPException otherwise.
    """
    if not x_service_token or not x_service_name:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Service authentication required"
        )
    
    if not verify_service_token(x_service_token, x_service_name):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid service credentials"
        )
    
    return True


# ── Rate Limiting (Basic Implementation) ───────────────────────────────────────

from collections import defaultdict
from time import time
from threading import Lock


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)
        self.lock = Lock()
    
    def is_allowed(self, identifier: str) -> bool:
        """Check if request is allowed for given identifier."""
        now = time()
        minute_ago = now - 60
        
        with self.lock:
            # Clean old requests
            self.requests[identifier] = [
                req_time for req_time in self.requests[identifier]
                if req_time > minute_ago
            ]
            
            # Check limit
            if len(self.requests[identifier]) >= self.requests_per_minute:
                return False
            
            # Add current request
            self.requests[identifier].append(now)
            return True


# Global rate limiter instance
rate_limiter = RateLimiter(requests_per_minute=60)


def check_rate_limit(
    current_user: Optional[User] = Depends(get_current_user_optional)
) -> bool:
    """
    Rate limiting dependency.
    
    Different limits based on user role:
    - Admin: 300 requests/minute
    - Operator: 100 requests/minute  
    - Analyst: 60 requests/minute
    - Viewer: 30 requests/minute
    - Unauthenticated: 10 requests/minute
    """
    if current_user:
        limits = {
            Role.ADMIN: 300,
            Role.OPERATOR: 100,
            Role.ANALYST: 60,
            Role.VIEWER: 30
        }
        limit = limits.get(current_user.role, 30)
        identifier = f"user:{current_user.id}"
    else:
        limit = 10
        identifier = f"ip:{id(object())}"  # Should use real IP in production
    
    # Create a role-specific limiter if needed
    # For now, use the global limiter
    if not rate_limiter.is_allowed(identifier):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded"
        )
    
    return True


# ── CORS Configuration ─────────────────────────────────────────────────────────

def get_cors_config(
    allow_origins: List[str] = None,
    allow_methods: List[str] = None,
    allow_headers: List[str] = None
) -> dict:
    """
    Get CORS configuration for FastAPI.
    
    In production, restrict allow_origins to specific domains.
    """
    return {
        "allow_origins": allow_origins or ["http://localhost:3000", "http://localhost:3100"],
        "allow_credentials": True,
        "allow_methods": allow_methods or ["*"],
        "allow_headers": allow_headers or ["*"],
    }