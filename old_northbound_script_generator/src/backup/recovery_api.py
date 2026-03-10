"""REST API endpoints for backup recovery operations."""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from .recovery_service import RecoveryService, RecoveryTrigger
from .models import BackupFilters

logger = logging.getLogger(__name__)

# This would be injected in a real application
recovery_service: Optional[RecoveryService] = None

def get_recovery_service() -> RecoveryService:
    """Get recovery service instance."""
    if recovery_service is None:
        raise HTTPException(status_code=503, detail="Recovery service not initialized")
    return recovery_service

def set_recovery_service(service: RecoveryService):
    """Set recovery service instance."""
    global recovery_service
    recovery_service = service


# Request/Response models
class RecoveryPointResponse(BaseModel):
    """Response model for recovery points."""
    backup_id: str = Field(..., description="Backup identifier")
    backup_type: str = Field(..., description="Type of backup")
    created_at: str = Field(..., description="Backup creation time")
    completed_at: Optional[str] = Field(None, description="Backup completion time")
    file_size_mb: float = Field(..., description="Backup file size in MB")
    compressed_size_mb: float = Field(..., description="Compressed file size in MB")
    is_encrypted: bool = Field(..., description="Whether backup is encrypted")
    database_name: str = Field(..., description="Database name")
    is_valid: bool = Field(..., description="Whether backup is valid")
    verification_time: str = Field(..., description="Last verification time")
    recovery_score: float = Field(..., description="Recovery recommendation score (0-100)")
    estimated_recovery_time_minutes: int = Field(..., description="Estimated recovery time")
    recommendation: str = Field(..., description="Recovery recommendation text")


class StartRecoveryRequest(BaseModel):
    """Request model for starting recovery."""
    backup_id: str = Field(..., description="Backup ID to restore from")
    force: bool = Field(default=False, description="Force recovery even if risky")


class RecoveryOperationResponse(BaseModel):
    """Response model for recovery operations."""
    operation_id: str = Field(..., description="Recovery operation ID")
    trigger: str = Field(..., description="What triggered the recovery")
    selected_backup_id: Optional[str] = Field(None, description="Selected backup ID")
    status: str = Field(..., description="Current operation status")
    started_at: str = Field(..., description="Operation start time")
    completed_at: Optional[str] = Field(None, description="Operation completion time")
    duration_seconds: float = Field(..., description="Operation duration")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    progress_percentage: int = Field(..., description="Progress percentage (0-100)")
    current_step: str = Field(..., description="Current operation step")
    logs: List[str] = Field(..., description="Recent log entries")


class RecoveryStatusResponse(BaseModel):
    """Response model for recovery system status."""
    auto_recovery_enabled: bool = Field(..., description="Whether auto recovery is enabled")
    health_monitoring_enabled: bool = Field(..., description="Whether health monitoring is enabled")
    recovery_attempts: int = Field(..., description="Number of recovery attempts made")
    max_recovery_attempts: int = Field(..., description="Maximum allowed recovery attempts")
    last_recovery_attempt: Optional[str] = Field(None, description="Last recovery attempt time")
    in_cooldown: bool = Field(..., description="Whether system is in recovery cooldown")
    cooldown_minutes: int = Field(..., description="Cooldown period in minutes")
    active_operations: int = Field(..., description="Number of active recovery operations")
    total_operations: int = Field(..., description="Total number of operations")


# Create router
router = APIRouter(prefix="/api/v1/recovery", tags=["Recovery"])


@router.get("/points", response_model=List[RecoveryPointResponse])
async def get_recovery_points(
    max_age_days: int = Query(default=30, ge=1, le=365, description="Maximum age of backups to consider"),
    service: RecoveryService = Depends(get_recovery_service)
):
    """Get available recovery points.
    
    Returns a list of available recovery points sorted by recommendation score.
    Each recovery point includes backup information, verification status, and
    a recommendation score to help select the best option.
    """
    try:
        recovery_points = service.get_recovery_points(max_age_days=max_age_days)
        
        return [
            RecoveryPointResponse(**rp.to_dict())
            for rp in recovery_points
        ]
        
    except Exception as e:
        logger.error(f"Failed to get recovery points: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recovery points: {str(e)}")


@router.post("/start", response_model=Dict[str, str])
async def start_manual_recovery(
    request: StartRecoveryRequest,
    service: RecoveryService = Depends(get_recovery_service)
):
    """Start manual recovery from a specific backup.
    
    Initiates a manual recovery operation using the specified backup.
    The operation runs asynchronously and can be monitored using the
    operation ID returned in the response.
    """
    try:
        # Validate backup exists and get recovery points
        recovery_points = service.get_recovery_points()
        selected_point = None
        
        for rp in recovery_points:
            if rp.backup_info.backup_id == request.backup_id:
                selected_point = rp
                break
        
        if not selected_point:
            raise HTTPException(status_code=404, detail="Backup not found or not available for recovery")
        
        # Check if backup is recommended
        if not request.force and selected_point.recovery_score < 50:
            raise HTTPException(
                status_code=400, 
                detail=f"Backup has low recovery score ({selected_point.recovery_score}). Use force=true to proceed anyway."
            )
        
        if not selected_point.verification_result.is_valid:
            raise HTTPException(status_code=400, detail="Backup verification failed. Cannot proceed with recovery.")
        
        # Start recovery
        operation_id = service.start_manual_recovery(request.backup_id)
        
        return {
            "operation_id": operation_id,
            "message": "Recovery operation started successfully",
            "estimated_time_minutes": selected_point.estimated_recovery_time_minutes
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start recovery: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start recovery: {str(e)}")


@router.post("/auto-start", response_model=Dict[str, str])
async def trigger_automatic_recovery(
    trigger: str = Query(..., description="Recovery trigger type"),
    service: RecoveryService = Depends(get_recovery_service)
):
    """Trigger automatic recovery.
    
    Manually triggers the automatic recovery process. The system will
    automatically select the best available backup and perform recovery.
    """
    try:
        # Validate trigger type
        try:
            recovery_trigger = RecoveryTrigger(trigger)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid trigger type: {trigger}")
        
        # Start automatic recovery
        operation_id = service.start_automatic_recovery(recovery_trigger)
        
        if not operation_id:
            raise HTTPException(
                status_code=409, 
                detail="Automatic recovery not started. Check if auto recovery is enabled and not in cooldown."
            )
        
        return {
            "operation_id": operation_id,
            "message": "Automatic recovery triggered successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger automatic recovery: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger automatic recovery: {str(e)}")


@router.get("/operations", response_model=List[RecoveryOperationResponse])
async def list_recovery_operations(
    include_completed: bool = Query(default=True, description="Include completed operations"),
    service: RecoveryService = Depends(get_recovery_service)
):
    """List recovery operations.
    
    Returns a list of recovery operations with their current status.
    Can optionally filter to only show active operations.
    """
    try:
        operations = service.list_operations(include_completed=include_completed)
        
        return [
            RecoveryOperationResponse(**op)
            for op in operations
        ]
        
    except Exception as e:
        logger.error(f"Failed to list recovery operations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list recovery operations: {str(e)}")


@router.get("/operations/{operation_id}", response_model=RecoveryOperationResponse)
async def get_recovery_operation(
    operation_id: str,
    service: RecoveryService = Depends(get_recovery_service)
):
    """Get recovery operation status.
    
    Returns detailed status information for a specific recovery operation,
    including progress, current step, and recent log entries.
    """
    try:
        operation = service.get_operation_status(operation_id)
        
        if not operation:
            raise HTTPException(status_code=404, detail="Recovery operation not found")
        
        return RecoveryOperationResponse(**operation)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get recovery operation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recovery operation: {str(e)}")


@router.delete("/operations/{operation_id}")
async def cancel_recovery_operation(
    operation_id: str,
    service: RecoveryService = Depends(get_recovery_service)
):
    """Cancel recovery operation.
    
    Attempts to cancel an active recovery operation. Operations that are
    already completed or failed cannot be cancelled.
    """
    try:
        success = service.cancel_operation(operation_id)
        
        if not success:
            raise HTTPException(
                status_code=409, 
                detail="Cannot cancel operation. It may not exist or already be completed."
            )
        
        return {"message": "Recovery operation cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel recovery operation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel recovery operation: {str(e)}")


@router.get("/status", response_model=RecoveryStatusResponse)
async def get_recovery_status(
    service: RecoveryService = Depends(get_recovery_service)
):
    """Get recovery system status.
    
    Returns overall status of the recovery system including configuration,
    current state, and statistics about recovery operations.
    """
    try:
        status = service.get_recovery_status()
        return RecoveryStatusResponse(**status)
        
    except Exception as e:
        logger.error(f"Failed to get recovery status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recovery status: {str(e)}")


@router.post("/health-monitoring/start")
async def start_health_monitoring(
    service: RecoveryService = Depends(get_recovery_service)
):
    """Start database health monitoring.
    
    Enables automatic health monitoring that can trigger recovery
    when database issues are detected.
    """
    try:
        service.start_health_monitoring()
        return {"message": "Health monitoring started successfully"}
        
    except Exception as e:
        logger.error(f"Failed to start health monitoring: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start health monitoring: {str(e)}")


@router.post("/health-monitoring/stop")
async def stop_health_monitoring(
    service: RecoveryService = Depends(get_recovery_service)
):
    """Stop database health monitoring.
    
    Disables automatic health monitoring. Manual recovery will still
    be available but automatic recovery won't be triggered by health checks.
    """
    try:
        service.stop_health_monitoring()
        return {"message": "Health monitoring stopped successfully"}
        
    except Exception as e:
        logger.error(f"Failed to stop health monitoring: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop health monitoring: {str(e)}")