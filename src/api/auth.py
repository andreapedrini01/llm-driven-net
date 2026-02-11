"""Authentication and authorization for API endpoints."""

import os
import secrets
from typing import Dict, Optional
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from jose import JWTError, jwt
import bcrypt

from ..config import get_settings
from ..utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# JWT configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    # Truncate password if necessary (bcrypt 72 byte limit)
    if len(plain_password.encode('utf-8')) > 72:
        plain_password = plain_password[:72]
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    """Hash a password."""
    # Truncate to 72 bytes if necessary (bcrypt limitation)
    if len(password.encode('utf-8')) > 72:
        password = password[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


# Simple in-memory user store (replace with database in production)
# Initialize with None and hash passwords lazily to avoid bcrypt initialization issues
_USERS_DB_TEMPLATE: Dict[str, Dict] = {
    "admin": {
        "username": "admin",
        "password": os.getenv("ADMIN_PASSWORD", "admin123"),
        "role": "admin",
        "permissions": ["read", "write", "admin"]
    },
    "operator": {
        "username": "operator",
        "password": os.getenv("OPERATOR_PASSWORD", "operator123"),
        "role": "operator",
        "permissions": ["read", "write"]
    },
    "viewer": {
        "username": "viewer",
        "password": os.getenv("VIEWER_PASSWORD", "viewer123"),
        "role": "viewer",
        "permissions": ["read"]
    }
}

USERS_DB: Dict[str, Dict] = {}

def _initialize_users():
    """Initialize user database with hashed passwords (lazy initialization)."""
    global USERS_DB
    if not USERS_DB:
        for username, user_data in _USERS_DB_TEMPLATE.items():
            USERS_DB[username] = {
                "username": user_data["username"],
                "hashed_password": get_password_hash(user_data["password"]),
                "role": user_data["role"],
                "permissions": user_data["permissions"]
            }
        logger.info("User database initialized")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    # Truncate password if necessary (bcrypt 72 byte limit)
    if len(plain_password.encode('utf-8')) > 72:
        plain_password = plain_password[:72]
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    """Hash a password."""
    # Truncate to 72 bytes if necessary (bcrypt limitation)
    if len(password.encode('utf-8')) > 72:
        password = password[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """
    Authenticate a user with username and password.
    
    Args:
        username: The username
        password: The plain text password
    
    Returns:
        User dict if authentication successful, None otherwise
    """
    _initialize_users()  # Ensure users are initialized
    user = USERS_DB.get(username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: The data to encode in the token
        expires_delta: Optional expiration time delta
    
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def verify_token(token: str) -> Dict:
    """
    Verify a JWT token and return the user information.
    
    Args:
        token: The JWT token to verify
    
    Returns:
        User information dict
    
    Raises:
        HTTPException: If token is invalid or expired
    """
    _initialize_users()  # Ensure users are initialized
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            logger.warning("Token validation failed: no username in payload")
            raise credentials_exception
        
        user = USERS_DB.get(username)
        if user is None:
            logger.warning("Token validation failed: user not found", username=username)
            raise credentials_exception
        
        return {
            "user_id": username,
            "username": username,
            "role": user["role"],
            "permissions": user["permissions"]
        }
        
    except JWTError as e:
        logger.warning("Token validation failed: JWT error", error=str(e))
        raise credentials_exception


def check_permission(user_info: Dict, required_permission: str) -> bool:
    """
    Check if a user has a specific permission.
    
    Args:
        user_info: User information dict from verify_token
        required_permission: The permission to check
    
    Returns:
        True if user has permission, False otherwise
    """
    return required_permission in user_info.get("permissions", [])


def require_permission(required_permission: str):
    """
    Decorator to require a specific permission for an endpoint.
    
    Args:
        required_permission: The permission required
    
    Returns:
        Decorator function
    """
    async def permission_checker(user_info: Dict = None):
        if not user_info or not check_permission(user_info, required_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{required_permission}' required"
            )
        return user_info
    
    return permission_checker
