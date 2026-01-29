"""Authentication and authorization service."""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
from enum import Enum

from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import pyotp

from .models import UserInfo, LoginResponse, APIKeyInfo

# Configure logging
logger = logging.getLogger(__name__)

# Security configuration
SECRET_KEY = "your-secret-key-change-in-production"  # Should be from environment
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme
security = HTTPBearer()


class UserRole(str, Enum):
    """User roles for RBAC."""
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"
    LLM_SERVICE = "llm_service"


class Permission(str, Enum):
    """System permissions."""
    READ_ACTIONS = "read:actions"
    WRITE_ACTIONS = "write:actions"
    DELETE_ACTIONS = "delete:actions"
    READ_USERS = "read:users"
    WRITE_USERS = "write:users"
    READ_SYSTEM = "read:system"
    WRITE_SYSTEM = "write:system"
    READ_METRICS = "read:metrics"


class User(BaseModel):
    """User model."""
    username: str
    email: Optional[str] = None
    roles: List[UserRole] = []
    is_active: bool = True
    created_at: datetime
    last_login: Optional[datetime] = None
    mfa_enabled: bool = False
    mfa_secret: Optional[str] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None


class APIKey(BaseModel):
    """API Key model."""
    key_id: str
    name: str
    description: Optional[str] = None
    hashed_key: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    permissions: List[Permission] = []
    is_active: bool = True
    created_by: str


class AuthService:
    """Authentication and authorization service."""
    
    def __init__(self):
        self.users: Dict[str, User] = {}
        self.api_keys: Dict[str, APIKey] = {}
        self.role_permissions: Dict[UserRole, List[Permission]] = {
            UserRole.ADMIN: list(Permission),
            UserRole.OPERATOR: [
                Permission.READ_ACTIONS, Permission.WRITE_ACTIONS,
                Permission.DELETE_ACTIONS, Permission.READ_SYSTEM,
                Permission.READ_METRICS
            ],
            UserRole.VIEWER: [
                Permission.READ_ACTIONS, Permission.READ_SYSTEM,
                Permission.READ_METRICS
            ],
            UserRole.LLM_SERVICE: [
                Permission.READ_ACTIONS, Permission.WRITE_ACTIONS
            ]
        }
        
        # Create default admin user
        self._create_default_admin()
    
    def _create_default_admin(self):
        """Create default admin user."""
        admin_user = User(
            username="admin",
            email="admin@example.com",
            roles=[UserRole.ADMIN],
            is_active=True,
            created_at=datetime.utcnow(),
            mfa_enabled=False
        )
        self.users["admin"] = admin_user
        logger.info("Default admin user created")
    
    def hash_password(self, password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password."""
        return pwd_context.verify(plain_password, hashed_password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    def create_refresh_token(self, data: dict) -> str:
        """Create JWT refresh token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    def verify_token(self, token: str, token_type: str = "access") -> Dict[str, Any]:
        """Verify JWT token."""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            if payload.get("type") != token_type:
                raise JWTError("Invalid token type")
            return payload
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    def get_user(self, username: str) -> Optional[User]:
        """Get user by username."""
        return self.users.get(username)
    
    def create_user(self, username: str, password: str, email: Optional[str] = None, 
                   roles: List[UserRole] = None) -> User:
        """Create a new user."""
        if username in self.users:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
        
        if roles is None:
            roles = [UserRole.VIEWER]
        
        user = User(
            username=username,
            email=email,
            roles=roles,
            is_active=True,
            created_at=datetime.utcnow()
        )
        
        self.users[username] = user
        # In a real implementation, you'd store the hashed password separately
        logger.info(f"User {username} created with roles {roles}")
        return user
    
    def authenticate_user(self, username: str, password: str, mfa_token: Optional[str] = None) -> Optional[User]:
        """Authenticate user with username/password and optional MFA."""
        user = self.get_user(username)
        if not user:
            return None
        
        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Account locked until {user.locked_until}"
            )
        
        # For demo purposes, accept "password" as password for all users
        # In production, verify against stored hashed password
        if password != "password":
            self._handle_failed_login(user)
            return None
        
        # Check MFA if enabled
        if user.mfa_enabled:
            if not mfa_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="MFA token required"
                )
            
            if not self.verify_mfa_token(user, mfa_token):
                self._handle_failed_login(user)
                return None
        
        # Reset failed attempts on successful login
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.utcnow()
        
        return user
    
    def _handle_failed_login(self, user: User):
        """Handle failed login attempt."""
        user.failed_login_attempts += 1
        
        # Lock account after 3 failed attempts
        if user.failed_login_attempts >= 3:
            user.locked_until = datetime.utcnow() + timedelta(minutes=15)
            logger.warning(f"Account {user.username} locked due to failed login attempts")
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account locked due to too many failed attempts"
            )
    
    def setup_mfa(self, user: User) -> Dict[str, Any]:
        """Setup MFA for user."""
        secret = pyotp.random_base32()
        user.mfa_secret = secret
        
        totp = pyotp.TOTP(secret)
        qr_url = totp.provisioning_uri(
            name=user.email or user.username,
            issuer_name="Northbound Script Generator"
        )
        
        # Generate backup codes
        backup_codes = [secrets.token_hex(4) for _ in range(10)]
        
        return {
            "secret_key": secret,
            "qr_code_url": qr_url,
            "backup_codes": backup_codes
        }
    
    def verify_mfa_token(self, user: User, token: str) -> bool:
        """Verify MFA token."""
        if not user.mfa_secret:
            return False
        
        totp = pyotp.TOTP(user.mfa_secret)
        return totp.verify(token, valid_window=1)
    
    def enable_mfa(self, user: User, verification_token: str) -> bool:
        """Enable MFA after verification."""
        if self.verify_mfa_token(user, verification_token):
            user.mfa_enabled = True
            logger.info(f"MFA enabled for user {user.username}")
            return True
        return False
    
    def disable_mfa(self, user: User) -> bool:
        """Disable MFA for user."""
        user.mfa_enabled = False
        user.mfa_secret = None
        logger.info(f"MFA disabled for user {user.username}")
        return True
    
    def create_api_key(self, name: str, created_by: str, description: Optional[str] = None,
                      expires_in_days: Optional[int] = None, 
                      permissions: List[Permission] = None) -> Dict[str, Any]:
        """Create API key."""
        key_id = secrets.token_urlsafe(16)
        api_key = secrets.token_urlsafe(32)
        hashed_key = hashlib.sha256(api_key.encode()).hexdigest()
        
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        if permissions is None:
            permissions = [Permission.READ_ACTIONS, Permission.WRITE_ACTIONS]
        
        api_key_obj = APIKey(
            key_id=key_id,
            name=name,
            description=description,
            hashed_key=hashed_key,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            permissions=permissions,
            is_active=True,
            created_by=created_by
        )
        
        self.api_keys[key_id] = api_key_obj
        logger.info(f"API key {name} created by {created_by}")
        
        return {
            "key_id": key_id,
            "api_key": api_key,
            "name": name,
            "created_at": api_key_obj.created_at,
            "expires_at": expires_at,
            "permissions": permissions
        }
    
    def verify_api_key(self, api_key: str) -> Optional[APIKey]:
        """Verify API key."""
        hashed_key = hashlib.sha256(api_key.encode()).hexdigest()
        
        for key_obj in self.api_keys.values():
            if (key_obj.hashed_key == hashed_key and 
                key_obj.is_active and
                (not key_obj.expires_at or key_obj.expires_at > datetime.utcnow())):
                
                # Update last used
                key_obj.last_used = datetime.utcnow()
                return key_obj
        
        return None
    
    def revoke_api_key(self, key_id: str) -> bool:
        """Revoke API key."""
        if key_id in self.api_keys:
            self.api_keys[key_id].is_active = False
            logger.info(f"API key {key_id} revoked")
            return True
        return False
    
    def get_user_permissions(self, user: User) -> List[Permission]:
        """Get all permissions for a user."""
        permissions = set()
        for role in user.roles:
            permissions.update(self.role_permissions.get(role, []))
        return list(permissions)
    
    def check_permission(self, user: User, permission: Permission) -> bool:
        """Check if user has specific permission."""
        user_permissions = self.get_user_permissions(user)
        return permission in user_permissions
    
    def check_api_key_permission(self, api_key: APIKey, permission: Permission) -> bool:
        """Check if API key has specific permission."""
        return permission in api_key.permissions


# Global auth service instance
auth_service = AuthService()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get current authenticated user."""
    token = credentials.credentials
    
    # Check if it's an API key (longer format)
    if len(token) > 50:  # API keys are longer
        api_key_obj = auth_service.verify_api_key(token)
        if not api_key_obj:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create a pseudo-user for API key
        return User(
            username=f"api_key_{api_key_obj.key_id}",
            roles=[UserRole.LLM_SERVICE],  # API keys typically have LLM service role
            is_active=True,
            created_at=api_key_obj.created_at
        )
    
    # Otherwise, treat as JWT token
    try:
        payload = auth_service.verify_token(token)
        username = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = auth_service.get_user(username)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


def require_permission(permission: Permission):
    """Decorator to require specific permission."""
    def permission_checker(current_user: User = Depends(get_current_user)):
        if not auth_service.check_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission}"
            )
        return current_user
    return permission_checker


def require_role(role: UserRole):
    """Decorator to require specific role."""
    def role_checker(current_user: User = Depends(get_current_user)):
        if role not in current_user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role required: {role}"
            )
        return current_user
    return role_checker