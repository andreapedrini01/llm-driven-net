"""
FastAPI application factory for integration with SystemOrchestrator.

This module provides a factory function to create the FastAPI app
that can be used with the orchestrator.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import uuid4
import logging

from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from src.models.action_models import NetworkAction, ActionType
from src.api.models import (
    ActionRequest, ActionResponse, ActionStatus, ActionSummary,
    BatchActionRequest, BatchActionResponse, HealthStatus
)
from src.api.auth import get_current_user, User
from src.api.auth_routes import router as auth_router
from src.api.dashboard_routes import router as dashboard_router
from src.api.config_routes import router as config_router

logger = logging.getLogger(__name__)


def create_app(northbound_instance, monitoring_service, action_tracker: Dict) -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Args:
        northbound_instance: Northbound script instance
        monitoring_service: Monitoring service instance
        action_tracker: Shared action tracker dictionary
        
    Returns:
        Configured FastAPI application
    """
    
    app = FastAPI(
        title="Northbound Script Generator API",
        description="""
# Northbound Script Generator API

REST API Gateway for network action processing via LLM integration with ComnetsEMU and RYU Controller.

## Overview

This API allows Large Language Models (LLMs) and other clients to submit network actions that are applied to a ComnetsEMU/RYU controlled network.

## Authentication

All API endpoints (except `/health` and `/docs`) require authentication via JWT token or API key.

## Quick Start

1. **Login**: POST to `/api/v1/auth/login` with credentials
2. **Submit Action**: POST to `/api/v1/actions` with action details
3. **Check Status**: GET `/api/v1/actions/{action_id}` to track progress
        """,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(auth_router)
    app.include_router(dashboard_router)
    app.include_router(config_router)
    
    # Set dependencies for dashboard routes
    from src.api.dashboard_routes import set_monitoring_service, set_northbound_instance, set_action_tracker
    set_monitoring_service(monitoring_service)
    set_northbound_instance(northbound_instance)
    set_action_tracker(action_tracker)
    
    async def process_action_background(action_id: str, action: NetworkAction):
        """Process action in background."""
        try:
            if action_id in action_tracker:
                action_tracker[action_id]["status"] = ActionStatus.EXECUTING
                action_tracker[action_id]["updated_at"] = datetime.utcnow()
            
            result = northbound_instance.process_action(action.dict())
            
            if action_id in action_tracker:
                if result.get("success", False):
                    action_tracker[action_id]["status"] = ActionStatus.COMPLETED
                    action_tracker[action_id]["result"] = result
                    monitoring_service.record_action_success(result.get("duration_ms", 0))
                else:
                    action_tracker[action_id]["status"] = ActionStatus.FAILED
                    action_tracker[action_id]["error"] = result.get("error", "Unknown error")
                    monitoring_service.record_action_error(result.get("duration_ms", 0))
                action_tracker[action_id]["updated_at"] = datetime.utcnow()
                
        except Exception as e:
            logger.error(f"Error processing action {action_id}: {e}")
            if action_id in action_tracker:
                action_tracker[action_id]["status"] = ActionStatus.FAILED
                action_tracker[action_id]["error"] = str(e)
                action_tracker[action_id]["updated_at"] = datetime.utcnow()
            monitoring_service.record_action_error(0)
    
    @app.get("/health", response_model=HealthStatus, tags=["monitoring"])
    async def health_check():
        """Health check endpoint."""
        try:
            return HealthStatus(
                status="healthy",
                timestamp=datetime.utcnow(),
                version="1.0.0",
                services={
                    "northbound": "healthy",
                    "api_gateway": "healthy",
                    "monitoring": "healthy"
                }
            )
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return HealthStatus(
                status="unhealthy",
                timestamp=datetime.utcnow(),
                version="1.0.0",
                services={"api_gateway": "healthy"},
                error=str(e)
            )
    
    @app.post("/api/v1/actions", response_model=ActionResponse, tags=["actions"], 
              status_code=status.HTTP_202_ACCEPTED)
    async def submit_action(
        request: ActionRequest,
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_user)
    ):
        """Submit network action for processing."""
        try:
            action_id = str(uuid4())
            
            network_action = NetworkAction(
                id=action_id,
                type=ActionType(request.type),
                target=request.target,
                parameters=request.parameters,
                priority=request.priority,
                timeout=request.timeout,
                description=request.description
            )
            
            validation_result = network_action.validate_action_parameters()
            if not validation_result["is_valid"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "message": "Action validation failed",
                        "issues": validation_result["issues"]
                    }
                )
            
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
    
    @app.get("/api/v1/actions/{action_id}", response_model=ActionStatus, tags=["actions"])
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
    
    @app.get("/api/v1/actions", response_model=List[ActionSummary], tags=["actions"])
    async def list_actions(
        status_filter: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        current_user: User = Depends(get_current_user)
    ):
        """List actions with optional filtering."""
        actions = list(action_tracker.values())
        
        if status_filter:
            try:
                status_enum = ActionStatus(status_filter)
                actions = [a for a in actions if a["status"] == status_enum]
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status filter: {status_filter}"
                )
        
        total = len(actions)
        actions = actions[offset:offset + limit]
        
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
    
    @app.delete("/api/v1/actions/{action_id}", tags=["actions"])
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
        
        if action_data["status"] in [ActionStatus.COMPLETED, ActionStatus.FAILED, ActionStatus.CANCELLED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel action in status: {action_data['status']}"
            )
        
        action_tracker[action_id]["status"] = ActionStatus.CANCELLED
        action_tracker[action_id]["updated_at"] = datetime.utcnow()
        
        logger.info(f"Action {action_id} cancelled by user {current_user.username}")
        
        return {"message": "Action cancelled successfully"}
    
    @app.get("/metrics", tags=["monitoring"])
    async def get_metrics():
        """Get Prometheus-style metrics."""
        if monitoring_service:
            return monitoring_service.get_prometheus_metrics()
        
        # Fallback basic metrics
        total_actions = len(action_tracker)
        metrics = [
            f"# HELP northbound_actions_total Total number of actions processed",
            f"# TYPE northbound_actions_total counter",
            f"northbound_actions_total {total_actions}"
        ]
        return "\n".join(metrics)
    
    return app
