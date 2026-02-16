"""Authentication routes for login and token management."""

from datetime import timedelta
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from .auth import authenticate_user, create_access_token, verify_token, ACCESS_TOKEN_EXPIRE_MINUTES
from ..utils.logging import get_logger

logger = get_logger(__name__)
security = HTTPBearer()

auth_router = APIRouter(tags=["authentication"])


class LoginRequest(BaseModel):
    """Login request model."""
    username: str = Field(..., min_length=1, description="Username")
    password: str = Field(..., min_length=1, description="Password")


class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserInfoResponse(BaseModel):
    """User information response."""
    username: str
    role: str
    permissions: list


@auth_router.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    Authenticate and get an access token.
    
    Default users:
    - admin/admin123 (full access)
    - operator/operator123 (read/write)
    - viewer/viewer123 (read only)
    
    Set custom passwords via environment variables:
    - ADMIN_PASSWORD
    - OPERATOR_PASSWORD
    - VIEWER_PASSWORD
    """
    user = authenticate_user(request.username, request.password)
    
    if not user:
        logger.warning("Login failed", username=request.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]},
        expires_delta=access_token_expires
    )
    
    logger.info("User logged in", username=request.username, role=user["role"])
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@auth_router.get("/auth/me", response_model=UserInfoResponse)
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user information from token."""
    user_info = await verify_token(credentials.credentials)
    
    return UserInfoResponse(
        username=user_info["username"],
        role=user_info["role"],
        permissions=user_info["permissions"]
    )


@auth_router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Refresh an access token."""
    user_info = await verify_token(credentials.credentials)
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_info["username"]},
        expires_delta=access_token_expires
    )
    
    logger.info("Token refreshed", username=user_info["username"])
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
