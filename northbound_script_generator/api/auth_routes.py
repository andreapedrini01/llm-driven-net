"""Authentication routes for the API Gateway."""

from datetime import datetime, timedelta
from typing import List
import logging

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPAuthorizationCredentials

from .models import (
    LoginRequest, LoginResponse, TokenRefreshRequest, TokenRefreshResponse,
    ChangePasswordRequest, MFASetupRequest, MFASetupResponse, MFAVerifyRequest,
    APIKeyRequest, APIKeyResponse, APIKeyInfo, UserInfo
)
from .auth import (
    auth_service, get_current_user, require_permission, require_role,
    User, UserRole, Permission, ACCESS_TOKEN_EXPIRE_MINUTES
)
from .session import session_manager, create_session_for_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Authenticate user and return JWT tokens."""
    try:
        user = auth_service.authenticate_user(
            request.username, 
            request.password, 
            request.mfa_token
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Create tokens
        access_token = auth_service.create_access_token(
            data={"sub": user.username}
        )
        refresh_token = auth_service.create_refresh_token(
            data={"sub": user.username}
        )
        
        # Create session
        session_id = create_session_for_user(user.username)
        
        logger.info(f"User {user.username} logged in successfully with session {session_id}")
        
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user_info=UserInfo(
                username=user.username,
                email=user.email,
                roles=[role.value for role in user.roles],
                is_active=user.is_active,
                created_at=user.created_at,
                last_login=user.last_login
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_token(request: TokenRefreshRequest):
    """Refresh access token using refresh token."""
    try:
        payload = auth_service.verify_token(request.refresh_token, "refresh")
        username = payload.get("sub")
        
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        user = auth_service.get_user(username)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Create new access token
        access_token = auth_service.create_access_token(
            data={"sub": user.username}
        )
        
        return TokenRefreshResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return UserInfo(
        username=current_user.username,
        email=current_user.email,
        roles=[role.value for role in current_user.roles],
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        last_login=current_user.last_login
    )


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user)
):
    """Change user password."""
    # In a real implementation, verify current password and update
    # For demo purposes, just log the action
    logger.info(f"Password change requested for user {current_user.username}")
    return {"message": "Password changed successfully"}


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    request: MFASetupRequest,
    current_user: User = Depends(get_current_user)
):
    """Setup Multi-Factor Authentication."""
    try:
        mfa_data = auth_service.setup_mfa(current_user)
        
        return MFASetupResponse(
            secret_key=mfa_data["secret_key"],
            qr_code_url=mfa_data["qr_code_url"],
            backup_codes=mfa_data["backup_codes"]
        )
        
    except Exception as e:
        logger.error(f"MFA setup error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MFA setup failed"
        )


@router.post("/mfa/verify")
async def verify_mfa(
    request: MFAVerifyRequest,
    current_user: User = Depends(get_current_user)
):
    """Verify and enable MFA."""
    try:
        if auth_service.enable_mfa(current_user, request.token):
            return {"message": "MFA enabled successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid MFA token"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MFA verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MFA verification failed"
        )


@router.post("/mfa/disable")
async def disable_mfa(current_user: User = Depends(get_current_user)):
    """Disable Multi-Factor Authentication."""
    try:
        auth_service.disable_mfa(current_user)
        return {"message": "MFA disabled successfully"}
        
    except Exception as e:
        logger.error(f"MFA disable error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MFA disable failed"
        )


@router.post("/api-keys", response_model=APIKeyResponse)
async def create_api_key(
    request: APIKeyRequest,
    current_user: User = Depends(require_permission(Permission.WRITE_SYSTEM))
):
    """Create API key."""
    try:
        api_key_data = auth_service.create_api_key(
            name=request.name,
            created_by=current_user.username,
            description=request.description,
            expires_in_days=request.expires_in_days,
            permissions=[Permission(p) for p in request.permissions] if request.permissions else None
        )
        
        return APIKeyResponse(**api_key_data)
        
    except Exception as e:
        logger.error(f"API key creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key creation failed"
        )


@router.get("/api-keys", response_model=List[APIKeyInfo])
async def list_api_keys(
    current_user: User = Depends(require_permission(Permission.READ_SYSTEM))
):
    """List API keys."""
    try:
        api_keys = []
        for key_obj in auth_service.api_keys.values():
            api_keys.append(APIKeyInfo(
                key_id=key_obj.key_id,
                name=key_obj.name,
                description=key_obj.description,
                created_at=key_obj.created_at,
                expires_at=key_obj.expires_at,
                last_used=key_obj.last_used,
                permissions=[p.value for p in key_obj.permissions],
                is_active=key_obj.is_active
            ))
        
        return api_keys
        
    except Exception as e:
        logger.error(f"API key listing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key listing failed"
        )


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    current_user: User = Depends(require_permission(Permission.WRITE_SYSTEM))
):
    """Revoke API key."""
    try:
        if auth_service.revoke_api_key(key_id):
            return {"message": "API key revoked successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API key revocation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key revocation failed"
        )


@router.get("/users", response_model=List[UserInfo])
async def list_users(
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """List all users (admin only)."""
    try:
        users = []
        for user in auth_service.users.values():
            users.append(UserInfo(
                username=user.username,
                email=user.email,
                roles=[role.value for role in user.roles],
                is_active=user.is_active,
                created_at=user.created_at,
                last_login=user.last_login
            ))
        
        return users
        
    except Exception as e:
        logger.error(f"User listing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User listing failed"
        )


@router.post("/users")
async def create_user(
    username: str,
    password: str,
    email: str = None,
    roles: List[str] = None,
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Create new user (admin only)."""
    try:
        user_roles = [UserRole(role) for role in roles] if roles else [UserRole.VIEWER]
        
        user = auth_service.create_user(
            username=username,
            password=password,
            email=email,
            roles=user_roles
        )
        
        return {
            "message": "User created successfully",
            "username": user.username,
            "roles": [role.value for role in user.roles]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User creation failed"
        )


@router.get("/sessions")
async def list_user_sessions(
    current_user: User = Depends(get_current_user)
):
    """List current user's active sessions."""
    try:
        sessions = session_manager.get_user_sessions(current_user.username)
        
        session_info = []
        for session in sessions:
            session_info.append({
                "session_id": session.session_id,
                "created_at": session.created_at,
                "last_activity": session.last_activity,
                "expires_at": session.expires_at,
                "ip_address": session.ip_address,
                "user_agent": session.user_agent
            })
        
        return {"sessions": session_info}
        
    except Exception as e:
        logger.error(f"Session listing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session listing failed"
        )


@router.delete("/sessions/{session_id}")
async def invalidate_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Invalidate a specific session."""
    try:
        # Check if session belongs to current user
        session = session_manager.get_session(session_id)
        if not session or session.username != current_user.username:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        if session_manager.invalidate_session(session_id):
            return {"message": "Session invalidated successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to invalidate session"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session invalidation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session invalidation failed"
        )


@router.delete("/sessions")
async def invalidate_all_sessions(
    current_user: User = Depends(get_current_user)
):
    """Invalidate all sessions for current user."""
    try:
        count = session_manager.invalidate_user_sessions(current_user.username)
        return {"message": f"Invalidated {count} sessions"}
        
    except Exception as e:
        logger.error(f"Session invalidation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session invalidation failed"
        )


@router.get("/sessions/stats")
async def get_session_stats(
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Get session statistics (admin only)."""
    try:
        stats = session_manager.get_session_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Session stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Session stats failed"
        )