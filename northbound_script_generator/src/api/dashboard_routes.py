"""Dashboard API routes for real-time monitoring and control."""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse

from .auth import get_current_user, User
from .models import ActionStatus
from ..monitoring.monitoring_service import MonitoringService
from ..core.northbound_script import NorthboundScript

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

# Global instances (will be injected in main app)
monitoring_service: Optional[MonitoringService] = None
northbound_instance: Optional[NorthboundScript] = None
action_tracker: Dict[str, Dict[str, Any]] = {}

# WebSocket connection manager
class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception:
            self.disconnect(websocket)
    
    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        
        # Remove disconnected connections
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# Dashboard Models
from pydantic import BaseModel, Field

class SystemStatus(BaseModel):
    """System status overview."""
    status: str = Field(..., description="Overall system status")
    uptime_seconds: int = Field(..., description="System uptime in seconds")
    total_actions: int = Field(..., description="Total actions processed")
    active_actions: int = Field(..., description="Currently active actions")
    error_rate: float = Field(..., description="Error rate percentage")
    cpu_usage: float = Field(..., description="CPU usage percentage")
    memory_usage: float = Field(..., description="Memory usage percentage")
    network_connections: int = Field(..., description="Active network connections")
    last_updated: datetime = Field(..., description="Last update timestamp")

class NetworkTopology(BaseModel):
    """Network topology information."""
    switches: List[Dict[str, Any]] = Field(default_factory=list, description="Network switches")
    links: List[Dict[str, Any]] = Field(default_factory=list, description="Network links")
    hosts: List[Dict[str, Any]] = Field(default_factory=list, description="Network hosts")
    flows: List[Dict[str, Any]] = Field(default_factory=list, description="Active flows")
    last_updated: datetime = Field(..., description="Last topology update")

class ActionProgress(BaseModel):
    """Action progress information."""
    action_id: str = Field(..., description="Action identifier")
    status: ActionStatus = Field(..., description="Current status")
    progress_percent: float = Field(..., description="Progress percentage (0-100)")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    elapsed_time_seconds: int = Field(..., description="Elapsed time in seconds")
    remaining_time_seconds: Optional[int] = Field(None, description="Estimated remaining time")
    current_step: str = Field(..., description="Current execution step")
    total_steps: int = Field(..., description="Total number of steps")

class DashboardMetrics(BaseModel):
    """Dashboard metrics summary."""
    actions_per_minute: float = Field(..., description="Actions processed per minute")
    average_response_time: float = Field(..., description="Average response time in ms")
    success_rate: float = Field(..., description="Success rate percentage")
    active_users: int = Field(..., description="Number of active users")
    queue_size: int = Field(..., description="Current queue size")
    alerts_count: int = Field(..., description="Number of active alerts")
    timestamp: datetime = Field(..., description="Metrics timestamp")

class LogEntry(BaseModel):
    """Log entry model."""
    timestamp: datetime = Field(..., description="Log timestamp")
    level: str = Field(..., description="Log level")
    component: str = Field(..., description="Component name")
    message: str = Field(..., description="Log message")
    action_id: Optional[str] = Field(None, description="Related action ID")
    user_id: Optional[str] = Field(None, description="Related user ID")

class AlertInfo(BaseModel):
    """Alert information."""
    alert_id: str = Field(..., description="Alert identifier")
    severity: str = Field(..., description="Alert severity")
    title: str = Field(..., description="Alert title")
    message: str = Field(..., description="Alert message")
    created_at: datetime = Field(..., description="Alert creation time")
    acknowledged: bool = Field(default=False, description="Whether alert is acknowledged")
    acknowledged_by: Optional[str] = Field(None, description="User who acknowledged")

# Dependency injection helpers
def get_monitoring_service() -> MonitoringService:
    """Get monitoring service instance."""
    if monitoring_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Monitoring service not available"
        )
    return monitoring_service

def get_northbound_instance() -> NorthboundScript:
    """Get northbound instance."""
    if northbound_instance is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Northbound service not available"
        )
    return northbound_instance

# Dashboard API Endpoints

@router.get("/status", response_model=SystemStatus)
async def get_system_status(
    current_user: User = Depends(get_current_user),
    monitoring: MonitoringService = Depends(get_monitoring_service)
):
    """Get overall system status."""
    try:
        # Get current metrics
        metrics = monitoring.get_current_metrics()
        
        # Calculate derived metrics
        total_actions = len(action_tracker)
        active_actions = len([a for a in action_tracker.values() 
                            if a["status"] in [ActionStatus.PENDING, ActionStatus.EXECUTING]])
        
        # Calculate error rate
        failed_actions = len([a for a in action_tracker.values() 
                            if a["status"] == ActionStatus.FAILED])
        error_rate = (failed_actions / total_actions * 100) if total_actions > 0 else 0
        
        return SystemStatus(
            status="healthy",  # Could be derived from health checks
            uptime_seconds=int(metrics.get("system", {}).get("uptime_seconds", 0)),
            total_actions=total_actions,
            active_actions=active_actions,
            error_rate=error_rate,
            cpu_usage=metrics.get("system", {}).get("cpu_usage_percent", 0),
            memory_usage=metrics.get("system", {}).get("memory_usage_percent", 0),
            network_connections=metrics.get("system", {}).get("network_connections", 0),
            last_updated=datetime.utcnow()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system status: {str(e)}"
        )

# User Management Endpoints

@router.get("/users", response_model=List[Dict[str, Any]])
async def get_users(
    current_user: User = Depends(get_current_user)
):
    """Get list of users (admin only)."""
    if "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    # Mock user data - in production this would come from a user service
    users = [
        {
            "id": "1",
            "username": "admin",
            "email": "admin@example.com",
            "roles": ["admin"],
            "is_active": True,
            "created_at": datetime.utcnow() - timedelta(days=30),
            "last_login": datetime.utcnow() - timedelta(hours=1)
        },
        {
            "id": "2", 
            "username": "operator",
            "email": "operator@example.com",
            "roles": ["operator"],
            "is_active": True,
            "created_at": datetime.utcnow() - timedelta(days=15),
            "last_login": datetime.utcnow() - timedelta(hours=2)
        }
    ]
    
    return users

@router.post("/users/{user_id}/toggle-status")
async def toggle_user_status(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """Toggle user active status (admin only)."""
    if "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    # In production, this would update the user in the database
    return {"message": f"User {user_id} status toggled successfully"}

@router.put("/users/{user_id}/roles")
async def update_user_roles(
    user_id: str,
    roles: List[str],
    current_user: User = Depends(get_current_user)
):
    """Update user roles (admin only)."""
    if "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    # Validate roles
    valid_roles = ["admin", "operator", "viewer"]
    if not all(role in valid_roles for role in roles):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid roles specified"
        )
    
    # In production, this would update the user in the database
    return {"message": f"User {user_id} roles updated successfully", "roles": roles}

# Enhanced Action Control Endpoints

@router.post("/actions/bulk-cancel")
async def bulk_cancel_actions(
    action_ids: List[str],
    current_user: User = Depends(get_current_user)
):
    """Cancel multiple actions at once."""
    if "admin" not in current_user.roles and "operator" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or admin access required"
        )
    
    cancelled_count = 0
    failed_cancellations = []
    
    for action_id in action_ids:
        if action_id in action_tracker:
            action_data = action_tracker[action_id]
            if action_data["status"] in [ActionStatus.PENDING, ActionStatus.EXECUTING]:
                action_tracker[action_id]["status"] = ActionStatus.CANCELLED
                action_tracker[action_id]["updated_at"] = datetime.utcnow()
                cancelled_count += 1
            else:
                failed_cancellations.append({
                    "action_id": action_id,
                    "reason": f"Cannot cancel action in status: {action_data['status']}"
                })
        else:
            failed_cancellations.append({
                "action_id": action_id,
                "reason": "Action not found"
            })
    
    # Broadcast bulk cancellation
    await manager.broadcast(json.dumps({
        "type": "bulk_action_cancelled",
        "cancelled_count": cancelled_count,
        "failed_count": len(failed_cancellations),
        "cancelled_by": current_user.username,
        "timestamp": datetime.utcnow().isoformat()
    }))
    
    return {
        "message": f"Cancelled {cancelled_count} actions",
        "cancelled_count": cancelled_count,
        "failed_cancellations": failed_cancellations
    }

@router.post("/actions/{action_id}/priority")
async def update_action_priority(
    action_id: str,
    priority: int,
    current_user: User = Depends(get_current_user)
):
    """Update action priority (admin/operator only)."""
    if "admin" not in current_user.roles and "operator" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator or admin access required"
        )
    
    if action_id not in action_tracker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action not found"
        )
    
    if not (1 <= priority <= 10):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Priority must be between 1 and 10"
        )
    
    action_data = action_tracker[action_id]
    if action_data["status"] not in [ActionStatus.PENDING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only update priority for pending actions"
        )
    
    # Update priority
    action_tracker[action_id]["action"].priority = priority
    action_tracker[action_id]["updated_at"] = datetime.utcnow()
    
    return {"message": "Action priority updated successfully"}

# System Control Endpoints

@router.post("/system/emergency-stop")
async def emergency_stop(
    current_user: User = Depends(get_current_user)
):
    """Emergency stop all actions (admin only)."""
    if "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    stopped_count = 0
    for action_id, action_data in action_tracker.items():
        if action_data["status"] in [ActionStatus.PENDING, ActionStatus.EXECUTING]:
            action_tracker[action_id]["status"] = ActionStatus.CANCELLED
            action_tracker[action_id]["updated_at"] = datetime.utcnow()
            stopped_count += 1
    
    # Broadcast emergency stop
    await manager.broadcast(json.dumps({
        "type": "emergency_stop",
        "stopped_count": stopped_count,
        "initiated_by": current_user.username,
        "timestamp": datetime.utcnow().isoformat()
    }))
    
    return {
        "message": f"Emergency stop executed - {stopped_count} actions cancelled",
        "stopped_count": stopped_count
    }

@router.get("/system/health-detailed")
async def get_detailed_health(
    current_user: User = Depends(get_current_user),
    monitoring: MonitoringService = Depends(get_monitoring_service)
):
    """Get detailed system health information."""
    try:
        health = await monitoring.health_check()
        
        # Add additional system information
        health["action_queue"] = {
            "total": len(action_tracker),
            "pending": len([a for a in action_tracker.values() if a["status"] == ActionStatus.PENDING]),
            "executing": len([a for a in action_tracker.values() if a["status"] == ActionStatus.EXECUTING]),
            "failed": len([a for a in action_tracker.values() if a["status"] == ActionStatus.FAILED])
        }
        
        return health
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system health: {str(e)}"
        )

# Critical Error Notification Endpoints

@router.post("/notifications/critical-error")
async def notify_critical_error(
    error_details: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Notify about critical system errors."""
    # Create critical error notification
    error_notification = {
        "type": "critical_error",
        "severity": "critical",
        "title": error_details.get("title", "Critical System Error"),
        "message": error_details.get("message", "A critical error has occurred"),
        "component": error_details.get("component", "unknown"),
        "timestamp": datetime.utcnow().isoformat(),
        "reported_by": current_user.username
    }
    
    # Broadcast to all connected clients
    await manager.broadcast(json.dumps(error_notification))
    
    # In production, this would also:
    # - Send email notifications to administrators
    # - Create tickets in issue tracking system
    # - Log to external monitoring systems
    
    return {"message": "Critical error notification sent"}

@router.get("/notifications/status")
async def get_notification_status(
    current_user: User = Depends(get_current_user)
):
    """Get notification system status."""
    return {
        "connected_clients": len(manager.active_connections),
        "notification_channels": ["websocket", "email", "webhook"],
        "last_notification": datetime.utcnow() - timedelta(minutes=5),
        "status": "operational"
    }

@router.get("/topology", response_model=NetworkTopology)
async def get_network_topology(
    current_user: User = Depends(get_current_user),
    nb_instance: NorthboundScript = Depends(get_northbound_instance)
):
    """Get current network topology."""
    try:
        # Get topology from northbound instance
        # This would need to be implemented in the northbound script
        topology_data = {
            "switches": [
                {"id": "s1", "name": "Switch 1", "dpid": "0000000000000001", "status": "active"},
                {"id": "s2", "name": "Switch 2", "dpid": "0000000000000002", "status": "active"}
            ],
            "links": [
                {"id": "l1", "source": "s1", "target": "s2", "status": "active", "bandwidth": "1Gbps"}
            ],
            "hosts": [
                {"id": "h1", "name": "Host 1", "ip": "10.0.0.1", "mac": "00:00:00:00:00:01", "switch": "s1"},
                {"id": "h2", "name": "Host 2", "ip": "10.0.0.2", "mac": "00:00:00:00:00:02", "switch": "s2"}
            ],
            "flows": [
                {"id": "f1", "switch": "s1", "priority": 100, "match": "ip", "actions": "output:2"}
            ]
        }
        
        return NetworkTopology(
            switches=topology_data["switches"],
            links=topology_data["links"],
            hosts=topology_data["hosts"],
            flows=topology_data["flows"],
            last_updated=datetime.utcnow()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get network topology: {str(e)}"
        )

@router.get("/actions/progress", response_model=List[ActionProgress])
async def get_actions_progress(
    current_user: User = Depends(get_current_user)
):
    """Get progress information for all active actions."""
    try:
        progress_list = []
        
        for action_id, action_data in action_tracker.items():
            if action_data["status"] in [ActionStatus.PENDING, ActionStatus.EXECUTING]:
                # Calculate progress based on status and elapsed time
                created_at = action_data["created_at"]
                elapsed = (datetime.utcnow() - created_at).total_seconds()
                
                # Estimate progress based on status
                if action_data["status"] == ActionStatus.PENDING:
                    progress = 10.0
                    current_step = "Queued for execution"
                elif action_data["status"] == ActionStatus.EXECUTING:
                    # Estimate based on elapsed time and expected duration
                    expected_duration = action_data["action"].estimate_execution_time()
                    progress = min(90.0, (elapsed / expected_duration) * 80 + 10)
                    current_step = "Executing network action"
                else:
                    progress = 0.0
                    current_step = "Unknown"
                
                # Estimate completion time
                if action_data["status"] == ActionStatus.EXECUTING and progress > 10:
                    remaining_time = int((100 - progress) / progress * elapsed)
                    estimated_completion = datetime.utcnow() + timedelta(seconds=remaining_time)
                else:
                    remaining_time = None
                    estimated_completion = None
                
                progress_list.append(ActionProgress(
                    action_id=action_id,
                    status=action_data["status"],
                    progress_percent=progress,
                    estimated_completion=estimated_completion,
                    elapsed_time_seconds=int(elapsed),
                    remaining_time_seconds=remaining_time,
                    current_step=current_step,
                    total_steps=3  # Validation, Execution, Completion
                ))
        
        return progress_list
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get action progress: {str(e)}"
        )

@router.get("/metrics", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    current_user: User = Depends(get_current_user),
    monitoring: MonitoringService = Depends(get_monitoring_service)
):
    """Get dashboard metrics summary."""
    try:
        metrics = monitoring.get_current_metrics()
        alerts = monitoring.get_active_alerts()
        
        # Calculate actions per minute
        now = datetime.utcnow()
        one_minute_ago = now - timedelta(minutes=1)
        recent_actions = [a for a in action_tracker.values() 
                         if a["created_at"] >= one_minute_ago]
        
        return DashboardMetrics(
            actions_per_minute=len(recent_actions),
            average_response_time=metrics.get("business", {}).get("avg_response_time_ms", 0),
            success_rate=100 - metrics.get("business", {}).get("error_rate_percent", 0),
            active_users=metrics.get("business", {}).get("active_users", 0),
            queue_size=metrics.get("business", {}).get("queue_size", 0),
            alerts_count=len(alerts),
            timestamp=datetime.utcnow()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dashboard metrics: {str(e)}"
        )

@router.get("/logs", response_model=List[LogEntry])
async def get_logs(
    level: Optional[str] = None,
    component: Optional[str] = None,
    action_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user)
):
    """Get system logs with filtering."""
    try:
        # This would typically read from a log aggregation system
        # For now, return mock data
        logs = [
            LogEntry(
                timestamp=datetime.utcnow() - timedelta(minutes=i),
                level="INFO",
                component="api_gateway",
                message=f"Action {uuid4()} processed successfully",
                action_id=str(uuid4()) if i % 3 == 0 else None
            )
            for i in range(limit)
        ]
        
        # Apply filters
        if level:
            logs = [log for log in logs if log.level.lower() == level.lower()]
        if component:
            logs = [log for log in logs if component.lower() in log.component.lower()]
        if action_id:
            logs = [log for log in logs if log.action_id == action_id]
        
        # Apply pagination
        return logs[offset:offset + limit]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get logs: {str(e)}"
        )

@router.get("/alerts", response_model=List[AlertInfo])
async def get_alerts(
    severity: Optional[str] = None,
    acknowledged: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    monitoring: MonitoringService = Depends(get_monitoring_service)
):
    """Get system alerts."""
    try:
        alerts = monitoring.get_active_alerts()
        
        # Convert to AlertInfo format
        alert_infos = []
        for alert in alerts:
            alert_info = AlertInfo(
                alert_id=alert.get("id", str(uuid4())),
                severity=alert.get("severity", "unknown"),
                title=alert.get("title", "System Alert"),
                message=alert.get("message", ""),
                created_at=alert.get("created_at", datetime.utcnow()),
                acknowledged=alert.get("acknowledged", False),
                acknowledged_by=alert.get("acknowledged_by")
            )
            alert_infos.append(alert_info)
        
        # Apply filters
        if severity:
            alert_infos = [a for a in alert_infos if a.severity.lower() == severity.lower()]
        if acknowledged is not None:
            alert_infos = [a for a in alert_infos if a.acknowledged == acknowledged]
        
        return alert_infos
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get alerts: {str(e)}"
        )

@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    monitoring: MonitoringService = Depends(get_monitoring_service)
):
    """Acknowledge an alert."""
    try:
        success = monitoring.acknowledge_alert(alert_id, current_user.username)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )
        
        # Broadcast alert acknowledgment
        await manager.broadcast(json.dumps({
            "type": "alert_acknowledged",
            "alert_id": alert_id,
            "acknowledged_by": current_user.username,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        return {"message": "Alert acknowledged successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to acknowledge alert: {str(e)}"
        )

# WebSocket endpoint for real-time updates
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Send periodic updates
            await asyncio.sleep(5)  # Update every 5 seconds
            
            # Get current system status
            if monitoring_service:
                metrics = monitoring_service.get_current_metrics()
                update_data = {
                    "type": "metrics_update",
                    "data": metrics,
                    "timestamp": datetime.utcnow().isoformat()
                }
                await manager.send_personal_message(json.dumps(update_data), websocket)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# Utility functions for dependency injection
def set_monitoring_service(service: MonitoringService):
    """Set the monitoring service instance."""
    global monitoring_service
    monitoring_service = service

def set_northbound_instance(instance: NorthboundScript):
    """Set the northbound instance."""
    global northbound_instance
    northbound_instance = instance

def set_action_tracker(tracker: Dict[str, Dict[str, Any]]):
    """Set the action tracker."""
    global action_tracker
    action_tracker = tracker

# Background task for broadcasting updates
async def broadcast_action_update(action_id: str, status: ActionStatus):
    """Broadcast action status update to all connected clients."""
    update_data = {
        "type": "action_update",
        "action_id": action_id,
        "status": status,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast(json.dumps(update_data))

async def broadcast_system_alert(alert: Dict[str, Any]):
    """Broadcast system alert to all connected clients."""
    alert_data = {
        "type": "system_alert",
        "alert": alert,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast(json.dumps(alert_data))