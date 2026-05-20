"""
User management module for OpsecAI services.

Provides user CRUD operations, authentication, and session management.
"""
from __future__ import annotations

from typing import Optional, Dict, List
from datetime import datetime
from dataclasses import dataclass, field

from .auth import (
    User,
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    InvalidCredentialsError,
    UserInactiveError,
    Role
)


# ── User Store (In-Memory - Replace with Database in Production) ───────────────

@dataclass
class UserRecord:
    """Internal user record with password hash."""
    id: str
    username: str
    email: str
    password_hash: str
    role: str
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    api_keys: Dict[str, str] = field(default_factory=dict)


class UserStore:
    """In-memory user store (replace with database in production)."""
    
    def __init__(self):
        self.users: Dict[str, UserRecord] = {}
        self.username_index: Dict[str, str] = {}  # username -> user_id
        self.email_index: Dict[str, str] = {}     # email -> user_id
        self._initialize_default_users()
    
    def _initialize_default_users(self):
        """Create default admin user."""
        admin_password = "admin123"  # CHANGE IN PRODUCTION
        admin_user = UserRecord(
            id="admin-001",
            username="admin",
            email="admin@opsecai.local",
            password_hash=get_password_hash(admin_password),
            role=Role.ADMIN,
            is_active=True
        )
        self._add_user_record(admin_user)
        
        # Create default operator user
        operator_password = "operator123"  # CHANGE IN PRODUCTION
        operator_user = UserRecord(
            id="operator-001", 
            username="operator",
            email="operator@opsecai.local",
            password_hash=get_password_hash(operator_password),
            role=Role.OPERATOR,
            is_active=True
        )
        self._add_user_record(operator_user)
    
    def _add_user_record(self, user_record: UserRecord):
        """Add a user record to all indexes."""
        self.users[user_record.id] = user_record
        self.username_index[user_record.username] = user_record.id
        self.email_index[user_record.email] = user_record.id
    
    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: str = Role.ANALYST
    ) -> User:
        """Create a new user."""
        # Validate uniqueness
        if username in self.username_index:
            raise ValueError(f"Username '{username}' already exists")
        if email in self.email_index:
            raise ValueError(f"Email '{email}' already exists")
        
        # Validate role
        if role not in Role.all():
            raise ValueError(f"Invalid role: {role}")
        
        user_id = f"user-{datetime.utcnow().timestamp()}"
        user_record = UserRecord(
            id=user_id,
            username=username,
            email=email,
            password_hash=get_password_hash(password),
            role=role,
            is_active=True
        )
        
        self._add_user_record(user_record)
        return self._user_record_to_user(user_record)
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        user_record = self.users.get(user_id)
        return self._user_record_to_user(user_record) if user_record else None
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        user_id = self.username_index.get(username)
        return self.get_user_by_id(user_id) if user_id else None
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        user_id = self.email_index.get(email)
        return self.get_user_by_id(user_id) if user_id else None
    
    def authenticate_user(self, username: str, password: str) -> User:
        """Authenticate user with username/password."""
        user = self.get_user_by_username(username)
        if not user:
            raise InvalidCredentialsError("Invalid username or password")
        
        user_record = self.users[user.id]
        if not verify_password(password, user_record.password_hash):
            raise InvalidCredentialsError("Invalid username or password")
        
        if not user.is_active:
            raise UserInactiveError("User account is inactive")
        
        return user
    
    def update_user(
        self,
        user_id: str,
        email: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Optional[User]:
        """Update user fields."""
        user_record = self.users.get(user_id)
        if not user_record:
            return None
        
        if email is not None:
            # Remove old email index
            del self.email_index[user_record.email]
            user_record.email = email
            self.email_index[email] = user_id
        
        if role is not None:
            if role not in Role.all():
                raise ValueError(f"Invalid role: {role}")
            user_record.role = role
        
        if is_active is not None:
            user_record.is_active = is_active
        
        return self._user_record_to_user(user_record)
    
    def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        user_record = self.users.get(user_id)
        if not user_record:
            return False
        
        del self.users[user_id]
        del self.username_index[user_record.username]
        del self.email_index[user_record.email]
        return True
    
    def list_users(self, role: Optional[str] = None) -> List[User]:
        """List all users, optionally filtered by role."""
        users = [self._user_record_to_user(record) for record in self.users.values()]
        
        if role:
            users = [u for u in users if u.role == role]
        
        return users
    
    def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        """Change user password."""
        user_record = self.users.get(user_id)
        if not user_record:
            return False
        
        if not verify_password(old_password, user_record.password_hash):
            return False
        
        user_record.password_hash = get_password_hash(new_password)
        return True
    
    def generate_api_key(self, user_id: str) -> str:
        """Generate a new API key for user."""
        from .auth import generate_api_key
        
        user_record = self.users.get(user_id)
        if not user_record:
            raise ValueError("User not found")
        
        api_key = generate_api_key()
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        user_record.api_keys[api_key_hash] = api_key
        
        return api_key
    
    def _user_record_to_user(self, user_record: UserRecord) -> User:
        """Convert UserRecord to User."""
        return User(
            id=user_record.id,
            username=user_record.username,
            email=user_record.email,
            role=user_record.role,
            is_active=user_record.is_active,
            created_at=user_record.created_at
        )


# ── Authentication Service ─────────────────────────────────────────────────────

class AuthService:
    """Service for authentication operations."""
    
    def __init__(self, user_store: UserStore):
        self.user_store = user_store
    
    def login(self, username: str, password: str) -> Dict[str, str]:
        """
        Authenticate user and return tokens.
        
        Returns:
            Dict with access_token, refresh_token, and token_type
        """
        user = self.user_store.authenticate_user(username, password)
        
        token_data = {
            "sub": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    
    def refresh_token(self, refresh_token: str) -> Dict[str, str]:
        """
        Refresh access token using refresh token.
        
        Returns:
            Dict with new access_token and token_type
        """
        from .auth import decode_token
        
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise InvalidCredentialsError("Invalid refresh token")
        
        user_id = payload.get("sub")
        user = self.user_store.get_user_by_id(user_id)
        
        if not user or not user.is_active:
            raise InvalidCredentialsError("Invalid refresh token")
        
        token_data = {
            "sub": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active
        }
        
        access_token = create_access_token(token_data)
        
        return {
            "access_token": access_token,
            "token_type": "bearer"
        }


# ── Global Instances ───────────────────────────────────────────────────────────

# Global user store (replace with database in production)
user_store = UserStore()

# Global auth service
auth_service = AuthService(user_store)


# Import hashlib for API key hashing
import hashlib