"""API models for the Northbound Script Generator."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ActionStatus(str, Enum):
    """Status of an action."""
    PENDING = "pending"
    VALIDATING = "validating"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class ActionRequest(BaseModel):
    """Request model for submitting an action."""
    type: str = Field(..., description="Type of network action")
    target: str = Field(..., description="Target resource for the action")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    priority: int = Field(default=1000, ge=0, le=65535, description="Action priority")
    timeout: int = Field(default=30, ge=1, le=3600, description="Timeout in seconds")
    description: Optional[str] = Field(None, description="Action description")


class ActionResponse(BaseModel):
    """Response model for action submission."""
    action_id: str = Field(..., description="Unique action identifier")
    status: ActionStatus = Field(..., description="Current action status")
    message: str = Field(..., description="Response message")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")


class ActionStatusResponse(BaseModel):
    """Response model for action status."""
    action_id: str = Field(..., description="Action identifier")
    status: ActionStatus = Field(..., description="Current status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: str = Field(..., description="User who created the action")
    result: Optional[Dict[str, Any]] = Field(None, description="Action result data")
    error: Optional[str] = Field(None, description="Error message if failed")


class ActionSummary(BaseModel):
    """Summary model for action listing."""
    action_id: str = Field(..., description="Action identifier")
    type: str = Field(..., description="Action type")
    target: str = Field(..., description="Target resource")
    status: ActionStatus = Field(..., description="Current status")
    created_at: datetime = Field(..., description="Creation timestamp")
    created_by: str = Field(..., description="User who created the action")


class BatchActionRequest(BaseModel):
    """Request model for batch action submission."""
    actions: List[ActionRequest] = Field(..., description="List of actions to execute")
    execution_mode: str = Field(default="parallel", description="Execution mode: parallel or sequential")


class BatchActionResponse(BaseModel):
    """Response model for batch action submission."""
    batch_id: str = Field(..., description="Unique batch identifier")
    action_ids: List[str] = Field(..., description="List of action IDs in the batch")
    total_actions: int = Field(..., description="Total number of actions in batch")
    message: str = Field(..., description="Response message")


class ActionFilters(BaseModel):
    """Filters for action listing."""
    status: Optional[ActionStatus] = Field(None, description="Filter by status")
    created_by: Optional[str] = Field(None, description="Filter by creator")
    created_after: Optional[datetime] = Field(None, description="Filter by creation date")
    created_before: Optional[datetime] = Field(None, description="Filter by creation date")
    action_type: Optional[str] = Field(None, description="Filter by action type")


class HealthStatus(BaseModel):
    """Health status response."""
    status: str = Field(..., description="Overall health status")
    timestamp: datetime = Field(..., description="Health check timestamp")
    version: str = Field(..., description="API version")
    services: Dict[str, str] = Field(..., description="Status of individual services")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str = Field(..., description="Error message")
    status_code: int = Field(..., description="HTTP status code")
    timestamp: datetime = Field(..., description="Error timestamp")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class MetricsResponse(BaseModel):
    """Metrics response model."""
    total_actions: int = Field(..., description="Total number of actions processed")
    actions_by_status: Dict[str, int] = Field(..., description="Actions grouped by status")
    actions_per_minute: float = Field(..., description="Actions processed per minute")
    average_execution_time: float = Field(..., description="Average execution time in seconds")
    error_rate: float = Field(..., description="Error rate percentage")


class UserInfo(BaseModel):
    """User information model."""
    username: str = Field(..., description="Username")
    email: Optional[str] = Field(None, description="User email")
    roles: List[str] = Field(default_factory=list, description="User roles")
    is_active: bool = Field(default=True, description="Whether user is active")
    created_at: datetime = Field(..., description="User creation timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")


class LoginRequest(BaseModel):
    """Login request model."""
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")
    mfa_token: Optional[str] = Field(None, description="MFA token if required")


class LoginResponse(BaseModel):
    """Login response model."""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user_info: UserInfo = Field(..., description="User information")


class TokenRefreshRequest(BaseModel):
    """Token refresh request model."""
    refresh_token: str = Field(..., description="Refresh token")


class TokenRefreshResponse(BaseModel):
    """Token refresh response model."""
    access_token: str = Field(..., description="New JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class ChangePasswordRequest(BaseModel):
    """Change password request model."""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., description="New password")


class MFASetupRequest(BaseModel):
    """MFA setup request model."""
    mfa_type: str = Field(default="totp", description="MFA type (totp)")


class MFASetupResponse(BaseModel):
    """MFA setup response model."""
    secret_key: str = Field(..., description="Secret key for TOTP")
    qr_code_url: str = Field(..., description="QR code URL for easy setup")
    backup_codes: List[str] = Field(..., description="Backup codes")


class MFAVerifyRequest(BaseModel):
    """MFA verification request model."""
    token: str = Field(..., description="MFA token")


class APIKeyRequest(BaseModel):
    """API key creation request model."""
    name: str = Field(..., description="API key name")
    description: Optional[str] = Field(None, description="API key description")
    expires_in_days: Optional[int] = Field(None, description="Expiration in days")
    permissions: List[str] = Field(default_factory=list, description="API key permissions")


class APIKeyResponse(BaseModel):
    """API key creation response model."""
    key_id: str = Field(..., description="API key identifier")
    api_key: str = Field(..., description="The actual API key")
    name: str = Field(..., description="API key name")
    created_at: datetime = Field(..., description="Creation timestamp")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")
    permissions: List[str] = Field(..., description="API key permissions")


class APIKeyInfo(BaseModel):
    """API key information model."""
    key_id: str = Field(..., description="API key identifier")
    name: str = Field(..., description="API key name")
    description: Optional[str] = Field(None, description="API key description")
    created_at: datetime = Field(..., description="Creation timestamp")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")
    last_used: Optional[datetime] = Field(None, description="Last usage timestamp")
    permissions: List[str] = Field(..., description="API key permissions")
    is_active: bool = Field(..., description="Whether key is active")