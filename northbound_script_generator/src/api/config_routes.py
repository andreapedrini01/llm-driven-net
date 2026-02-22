"""API routes for configuration management."""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field

from ..config.config_manager import get_config_manager, ConfigChangeEvent
from ..config.centralized_config import get_centralized_config_manager
from ..config.distributed_config import get_distributed_config_manager
from .auth import get_current_user, require_admin


logger = logging.getLogger("ConfigRoutes")

router = APIRouter(prefix="/api/v1/config", tags=["configuration"])


# Request/Response Models

class ConfigUpdateRequest(BaseModel):
    """Configuration update request."""
    updates: Dict[str, Any] = Field(..., description="Configuration updates")
    comment: str = Field(default="", description="Update comment")


class ConfigValidationRequest(BaseModel):
    """Configuration validation request."""
    config: Dict[str, Any] = Field(..., description="Configuration to validate")


class ConfigRollbackRequest(BaseModel):
    """Configuration rollback request."""
    version_number: int = Field(..., description="Version to rollback to")
    comment: str = Field(default="", description="Rollback comment")


class ConfigResponse(BaseModel):
    """Configuration response."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


# Endpoints

@router.get("/current")
async def get_current_config(user: dict = Depends(get_current_user)):
    """Get current system configuration."""
    try:
        config_manager = get_config_manager()
        config = config_manager.get_config_dict()
        
        return ConfigResponse(
            success=True,
            message="Current configuration retrieved",
            data={"config": config}
        )
    
    except Exception as e:
        logger.error(f"Failed to get current config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update")
async def update_config(
    request: ConfigUpdateRequest,
    http_request: Request,
    user: dict = Depends(require_admin)
):
    """
    Update system configuration via API.
    Requires admin privileges.
    """
    try:
        config_manager = get_config_manager()
        
        # Update configuration
        event = config_manager.update_from_api(request.updates)
        
        # Create version in centralized manager
        centralized_manager = get_centralized_config_manager()
        new_config = config_manager.get_config_dict()
        
        version = centralized_manager.create_version(
            config_data=new_config,
            user=user['username'],
            comment=request.comment,
            ip_address=http_request.client.host,
            user_agent=http_request.headers.get('user-agent')
        )
        
        # Broadcast to distributed instances if available
        try:
            distributed_manager = get_distributed_config_manager(
                instance_id=config_manager.get_config().environment
            )
            distributed_manager.broadcast_update(
                version_number=version.version_number,
                config_data=new_config,
                user=user['username'],
                comment=request.comment
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast config update: {e}")
        
        return ConfigResponse(
            success=True,
            message=f"Configuration updated successfully",
            data={
                "version_number": version.version_number,
                "changes": event.changes
            }
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate")
async def validate_config(
    request: ConfigValidationRequest,
    user: dict = Depends(get_current_user)
):
    """Validate configuration without applying it."""
    try:
        config_manager = get_config_manager()
        is_valid, error_message = config_manager.validate_config(request.config)
        
        if is_valid:
            return ConfigResponse(
                success=True,
                message="Configuration is valid"
            )
        else:
            return ConfigResponse(
                success=False,
                message=f"Configuration validation failed: {error_message}"
            )
    
    except Exception as e:
        logger.error(f"Failed to validate config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_config_history(
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(get_current_user)
):
    """Get configuration change history."""
    try:
        # Get from config manager
        config_manager = get_config_manager()
        recent_history = config_manager.get_history(limit=min(limit, 50))
        
        # Get from centralized manager
        centralized_manager = get_centralized_config_manager()
        version_history = centralized_manager.get_version_history(
            limit=limit,
            offset=offset
        )
        
        return ConfigResponse(
            success=True,
            message="Configuration history retrieved",
            data={
                "recent_changes": recent_history,
                "version_history": version_history
            }
        )
    
    except Exception as e:
        logger.error(f"Failed to get config history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions/{version_number}")
async def get_config_version(
    version_number: int,
    user: dict = Depends(get_current_user)
):
    """Get specific configuration version."""
    try:
        centralized_manager = get_centralized_config_manager()
        version = centralized_manager.get_version(version_number)
        
        if not version:
            raise HTTPException(
                status_code=404,
                detail=f"Version {version_number} not found"
            )
        
        return ConfigResponse(
            success=True,
            message=f"Version {version_number} retrieved",
            data={
                "version_id": version.version_id,
                "version_number": version.version_number,
                "config_data": version.config_data,
                "created_at": version.created_at.isoformat(),
                "created_by": version.created_by,
                "operation": version.operation.value,
                "comment": version.comment,
                "checksum": version.checksum
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get version {version_number}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rollback")
async def rollback_config(
    request: ConfigRollbackRequest,
    http_request: Request,
    user: dict = Depends(require_admin)
):
    """
    Rollback to a previous configuration version.
    Requires admin privileges.
    """
    try:
        centralized_manager = get_centralized_config_manager()
        
        # Perform rollback
        rollback_version = centralized_manager.rollback_to_version(
            version_number=request.version_number,
            user=user['username'],
            comment=request.comment,
            ip_address=http_request.client.host,
            user_agent=http_request.headers.get('user-agent')
        )
        
        # Apply to config manager
        config_manager = get_config_manager()
        config_manager.update_from_api(rollback_version.config_data)
        
        # Broadcast to distributed instances
        try:
            distributed_manager = get_distributed_config_manager(
                instance_id=config_manager.get_config().environment
            )
            distributed_manager.broadcast_update(
                version_number=rollback_version.version_number,
                config_data=rollback_version.config_data,
                user=user['username'],
                comment=f"Rollback to version {request.version_number}"
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast rollback: {e}")
        
        return ConfigResponse(
            success=True,
            message=f"Rolled back to version {request.version_number}",
            data={
                "new_version_number": rollback_version.version_number,
                "rollback_to_version": request.version_number
            }
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to rollback config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit")
async def get_audit_trail(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    user_filter: Optional[str] = None,
    limit: int = 100,
    user: dict = Depends(require_admin)
):
    """
    Get configuration audit trail.
    Requires admin privileges.
    """
    try:
        centralized_manager = get_centralized_config_manager()
        
        # Parse timestamps
        start_dt = datetime.fromisoformat(start_time) if start_time else None
        end_dt = datetime.fromisoformat(end_time) if end_time else None
        
        # Get audit trail
        audit_entries = centralized_manager.get_audit_trail(
            start_time=start_dt,
            end_time=end_dt,
            user=user_filter,
            limit=limit
        )
        
        return ConfigResponse(
            success=True,
            message="Audit trail retrieved",
            data={"audit_entries": audit_entries}
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid timestamp format: {e}")
    except Exception as e:
        logger.error(f"Failed to get audit trail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_config_stats(user: dict = Depends(get_current_user)):
    """Get configuration management statistics."""
    try:
        config_manager = get_config_manager()
        centralized_manager = get_centralized_config_manager()
        
        stats = {
            "config_manager": config_manager.get_stats(),
            "centralized_manager": centralized_manager.get_stats()
        }
        
        # Add distributed stats if available
        try:
            distributed_manager = get_distributed_config_manager(
                instance_id=config_manager.get_config().environment
            )
            stats["distributed_manager"] = distributed_manager.get_stats()
            stats["connected_instances"] = distributed_manager.get_connected_instances()
        except Exception as e:
            logger.debug(f"Distributed config not available: {e}")
        
        return ConfigResponse(
            success=True,
            message="Configuration statistics retrieved",
            data=stats
        )
    
    except Exception as e:
        logger.error(f"Failed to get config stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export")
async def export_config(
    format: str = "yaml",
    user: dict = Depends(require_admin)
):
    """
    Export current configuration.
    Requires admin privileges.
    """
    try:
        if format not in ["yaml", "json"]:
            raise HTTPException(
                status_code=400,
                detail="Format must be 'yaml' or 'json'"
            )
        
        config_manager = get_config_manager()
        config_dict = config_manager.get_config_dict()
        
        return ConfigResponse(
            success=True,
            message=f"Configuration exported as {format}",
            data={
                "format": format,
                "config": config_dict
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sync-status")
async def get_sync_status(user: dict = Depends(get_current_user)):
    """Get distributed configuration sync status."""
    try:
        config_manager = get_config_manager()
        distributed_manager = get_distributed_config_manager(
            instance_id=config_manager.get_config().environment
        )
        
        sync_status = distributed_manager.get_sync_status()
        
        return ConfigResponse(
            success=True,
            message="Sync status retrieved",
            data=sync_status
        )
    
    except Exception as e:
        logger.warning(f"Failed to get sync status: {e}")
        return ConfigResponse(
            success=False,
            message="Distributed configuration not available",
            data={"error": str(e)}
        )
