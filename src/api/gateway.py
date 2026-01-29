"""FastAPI Gateway for Northbound Script Generator."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import uuid4
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from ..models.action_models import NetworkAction, ActionSequence, ActionType
from .models import (
    ActionRequest, ActionResponse, ActionStatus, ActionSummary,
    BatchActionRequest, BatchActionResponse, HealthStatus,
    ErrorResponse, ActionFilters
)
from .auth import AuthService, get_current_user, User
from .auth_routes import router as auth_router
from ..core.northbound_script import NorthboundScript

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state for tracking actions
action_tracker: Dict[str, Dict[str, Any]] = {}
northbound_instance: Optional[NorthboundScript] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global northbound_instance
    
    # Startup
    logger.info("Starting Northbound API Gateway...")
    try:
        northbound_instance = NorthboundScript()
        logger.info("Northbound Script instance initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Northbound Script: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Northbound API Gateway...")
    if northbound_instance:
        # Cleanup resources if needed
        pass

# Create FastAPI app
app = FastAPI(
    title="Northbound Script Generator API",
    description="REST API Gateway for network action processing via LLM integration",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include auth routes
app.include_router(auth_router)

# Security
security = HTTPBearer()
auth_service = AuthService()

def get_northbound_instance() -> NorthboundScript:
    """Get the northbound script instance."""
    if northbound_instance is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Northbound service not available"
        )
    return northbound_instance

async def process_action_background(action_id: str, action: NetworkAction):
    """Process action in background."""
    try:
        # Update status to executing
        if action_id in action_tracker:
            action_tracker[action_id]["status"] = ActionStatus.EXECUTING
            action_tracker[action_id]["updated_at"] = datetime.utcnow()
        
        # Get northbound instance and process action
        nb_instance = get_northbound_instance()
        result = nb_instance.process_action(action.dict())
        
        # Update status based on result
        if action_id in action_tracker:
            if result.get("success", False):
                action_tracker[action_id]["status"] = ActionStatus.COMPLETED
                action_tracker[action_id]["result"] = result
            else:
                action_tracker[action_id]["status"] = ActionStatus.FAILED
                action_tracker[action_id]["error"] = result.get("error", "Unknown error")
            action_tracker[action_id]["updated_at"] = datetime.utcnow()
            
    except Exception as e:
        logger.error(f"Error processing action {action_id}: {e}")
        if action_id in action_tracker:
            action_tracker[action_id]["status"] = ActionStatus.FAILED
            action_tracker[action_id]["error"] = str(e)
            action_tracker[action_id]["updated_at"] = datetime.utcnow()

@app.get("/health", response_model=HealthStatus)
async def health_check():
    """Health check endpoint."""
    try:
        nb_instance = get_northbound_instance()
        # Basic health check - could be expanded
        return HealthStatus(
            status="healthy",
            timestamp=datetime.utcnow(),
            version="1.0.0",
            services={
                "northbound": "healthy",
                "api_gateway": "healthy"
            }
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthStatus(
            status="unhealthy",
            timestamp=datetime.utcnow(),
            version="1.0.0",
            services={
                "northbound": "unhealthy",
                "api_gateway": "healthy"
            },
            error=str(e)
        )

@app.post("/api/v1/actions", response_model=ActionResponse)
async def submit_action(
    request: ActionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Submit a network action for processing."""
    try:
        # Generate unique action ID
        action_id = str(uuid4())
        
        # Create NetworkAction from request
        network_action = NetworkAction(
            id=action_id,
            type=ActionType(request.type),
            target=request.target,
            parameters=request.parameters,
            priority=request.priority,
            timeout=request.timeout,
            description=request.description
        )
        
        # Validate action
        validation_result = network_action.validate_action_parameters()
        if not validation_result["is_valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Action validation failed",
                    "issues": validation_result["issues"],
                    "warnings": validation_result.get("warnings", [])
                }
            )
        
        # Track action
        action_tracker[action_id] = {
            "id": action_id,
            "status": ActionStatus.PENDING,
            "action": network_action,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "created_by": current_user.username,
            "result": None,
            "error": None
        }
        
        # Process action in background
        background_tasks.add_task(process_action_background, action_id, network_action)
        
        logger.info(f"Action {action_id} submitted by user {current_user.username}")
        
        return ActionResponse(
            action_id=action_id,
            status=ActionStatus.PENDING,
            message="Action submitted successfully",
            estimated_completion=datetime.utcnow() + timedelta(seconds=network_action.estimate_execution_time())
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting action: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@app.get("/api/v1/actions/{action_id}", response_model=ActionStatus)
async def get_action_status(
    action_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get status of a specific action."""
    if action_id not in action_tracker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action not found"
        )
    
    action_data = action_tracker[action_id]
    
    return ActionStatus(
        action_id=action_id,
        status=action_data["status"],
        created_at=action_data["created_at"],
        updated_at=action_data["updated_at"],
        created_by=action_data["created_by"],
        result=action_data.get("result"),
        error=action_data.get("error")
    )

@app.get("/api/v1/actions", response_model=List[ActionSummary])
async def list_actions(
    status_filter: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user)
):
    """List actions with optional filtering."""
    actions = list(action_tracker.values())
    
    # Apply status filter
    if status_filter:
        try:
            status_enum = ActionStatus(status_filter)
            actions = [a for a in actions if a["status"] == status_enum]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter: {status_filter}"
            )
    
    # Apply pagination
    total = len(actions)
    actions = actions[offset:offset + limit]
    
    # Convert to ActionSummary
    summaries = []
    for action_data in actions:
        summaries.append(ActionSummary(
            action_id=action_data["id"],
            type=action_data["action"].type,
            target=action_data["action"].target,
            status=action_data["status"],
            created_at=action_data["created_at"],
            created_by=action_data["created_by"]
        ))
    
    return summaries

@app.delete("/api/v1/actions/{action_id}")
async def cancel_action(
    action_id: str,
    current_user: User = Depends(get_current_user)
):
    """Cancel a pending or executing action."""
    if action_id not in action_tracker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action not found"
        )
    
    action_data = action_tracker[action_id]
    
    # Check if action can be cancelled
    if action_data["status"] in [ActionStatus.COMPLETED, ActionStatus.FAILED, ActionStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel action in status: {action_data['status']}"
        )
    
    # Update status to cancelled
    action_tracker[action_id]["status"] = ActionStatus.CANCELLED
    action_tracker[action_id]["updated_at"] = datetime.utcnow()
    
    logger.info(f"Action {action_id} cancelled by user {current_user.username}")
    
    return {"message": "Action cancelled successfully"}

@app.post("/api/v1/actions/batch", response_model=BatchActionResponse)
async def submit_batch_actions(
    request: BatchActionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Submit multiple actions as a batch."""
    try:
        batch_id = str(uuid4())
        action_ids = []
        
        # Process each action in the batch
        for action_request in request.actions:
            action_id = str(uuid4())
            action_ids.append(action_id)
            
            # Create NetworkAction
            network_action = NetworkAction(
                id=action_id,
                type=ActionType(action_request.type),
                target=action_request.target,
                parameters=action_request.parameters,
                priority=action_request.priority,
                timeout=action_request.timeout,
                description=action_request.description
            )
            
            # Validate action
            validation_result = network_action.validate_action_parameters()
            if not validation_result["is_valid"]:
                # For batch operations, we might want to continue with valid actions
                # or fail the entire batch - this depends on requirements
                logger.warning(f"Action validation failed for batch {batch_id}: {validation_result['issues']}")
            
            # Track action
            action_tracker[action_id] = {
                "id": action_id,
                "batch_id": batch_id,
                "status": ActionStatus.PENDING,
                "action": network_action,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "created_by": current_user.username,
                "result": None,
                "error": None
            }
            
            # Process action in background
            background_tasks.add_task(process_action_background, action_id, network_action)
        
        logger.info(f"Batch {batch_id} with {len(action_ids)} actions submitted by user {current_user.username}")
        
        return BatchActionResponse(
            batch_id=batch_id,
            action_ids=action_ids,
            total_actions=len(action_ids),
            message="Batch actions submitted successfully"
        )
        
    except Exception as e:
        logger.error(f"Error submitting batch actions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@app.get("/metrics")
async def get_metrics():
    """Get Prometheus-style metrics."""
    # Basic metrics - can be expanded with proper Prometheus integration
    total_actions = len(action_tracker)
    status_counts = {}
    
    for action_data in action_tracker.values():
        status = action_data["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    
    metrics = []
    metrics.append(f"# HELP northbound_actions_total Total number of actions processed")
    metrics.append(f"# TYPE northbound_actions_total counter")
    metrics.append(f"northbound_actions_total {total_actions}")
    
    for status, count in status_counts.items():
        metrics.append(f"# HELP northbound_actions_by_status Actions by status")
        metrics.append(f"# TYPE northbound_actions_by_status gauge")
        metrics.append(f'northbound_actions_by_status{{status="{status}"}} {count}')
    
    return "\n".join(metrics)

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return ErrorResponse(
        error=exc.detail,
        status_code=exc.status_code,
        timestamp=datetime.utcnow()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}")
    return ErrorResponse(
        error="Internal server error",
        status_code=500,
        timestamp=datetime.utcnow()
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)