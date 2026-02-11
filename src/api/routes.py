"""API routes for intent submission and real-time updates."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from ..services.intent_parser import IntentParser
from ..services.context_analyzer import ContextAnalyzer
from ..services.chatgpt_client import ChatGPTClient
from ..services.prompt_engineering import PromptEngineer
from ..services.action_sequencer import ActionSequencer
from ..services.validator import Validator
from ..services.action_output import ActionOutputService
from ..services.state_file_reader import StateFileReader
from ..config import get_settings
from ..utils.logging import get_logger
from .websocket_manager import ConnectionManager
from .auth import verify_token

logger = get_logger(__name__)
settings = get_settings()

# Security
security = HTTPBearer()

# Routers
intent_router = APIRouter(tags=["intents"])
health_router = APIRouter(tags=["health"])

# WebSocket connection manager
ws_manager = ConnectionManager()


# Request/Response models
class IntentRequest(BaseModel):
    """Request model for intent submission."""
    text: str = Field(..., min_length=1, max_length=1000, description="Natural language intent")
    user_id: str = Field(..., description="User identifier")
    priority: Optional[int] = Field(1, ge=1, le=10, description="Intent priority (1-10)")


class IntentResponse(BaseModel):
    """Response model for intent submission."""
    intent_id: str
    status: str
    message: str
    confidence: Optional[float] = None
    clarification_needed: bool = False
    clarification_questions: Optional[List[str]] = None


class ActionStatusResponse(BaseModel):
    """Response model for action status."""
    intent_id: str
    status: str
    actions_generated: int
    actions_validated: int
    actions_executed: int
    errors: Optional[List[str]] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    components: dict


# Dependency injection
async def get_intent_parser() -> IntentParser:
    """Get intent parser instance."""
    return IntentParser()


async def get_context_analyzer() -> ContextAnalyzer:
    """Get context analyzer instance."""
    state_reader = StateFileReader()
    return ContextAnalyzer(state_reader)


async def get_chatgpt_client() -> ChatGPTClient:
    """Get ChatGPT client instance."""
    return ChatGPTClient()


async def get_action_sequencer() -> ActionSequencer:
    """Get action sequencer instance."""
    return ActionSequencer()


async def get_validator() -> Validator:
    """Get validator instance."""
    return Validator()


async def get_action_output() -> ActionOutputService:
    """Get action output service instance."""
    return ActionOutputService()


# Intent submission endpoint
@intent_router.post("/intents", response_model=IntentResponse, status_code=status.HTTP_201_CREATED)
async def submit_intent(
    request: IntentRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    parser: IntentParser = Depends(get_intent_parser),
    analyzer: ContextAnalyzer = Depends(get_context_analyzer),
    chatgpt: ChatGPTClient = Depends(get_chatgpt_client),
    sequencer: ActionSequencer = Depends(get_action_sequencer),
    validator: Validator = Depends(get_validator),
    output_service: ActionOutputService = Depends(get_action_output)
):
    """
    Submit a natural language intent for processing.
    
    This endpoint:
    1. Authenticates the request
    2. Parses the natural language intent
    3. Analyzes network context
    4. Generates actions using ChatGPT
    5. Validates and sequences actions
    6. Outputs actions for future execution
    7. Returns status and any clarification requests
    """
    try:
        # Verify authentication
        user_info = await verify_token(credentials.credentials)
        logger.info("Intent submitted", user_id=request.user_id, intent_text=request.text[:50])
        
        # Parse intent
        intent_obj = parser.parse_intent(request.text, request.user_id)
        
        # Check if clarification is needed
        if intent_obj.confidence < settings.intent_confidence_threshold:
            clarification_questions = parser.generate_clarification_questions(intent_obj)
            return IntentResponse(
                intent_id=intent_obj.id,
                status="clarification_needed",
                message="Intent requires clarification",
                confidence=intent_obj.confidence,
                clarification_needed=True,
                clarification_questions=clarification_questions
            )
        
        # Analyze context
        contextualized_intent = analyzer.analyze_context(intent_obj)
        
        # Generate actions using ChatGPT
        prompt_engineer = PromptEngineer()
        prompt = prompt_engineer.build_action_generation_prompt(contextualized_intent)
        chatgpt_response = await chatgpt.generate_response(prompt)
        
        # Parse and sequence actions
        actions = sequencer.parse_actions_from_response(chatgpt_response.content)
        action_sequence = sequencer.sequence_actions(actions, contextualized_intent)
        
        # Validate actions
        validation_result = validator.validate_actions(action_sequence)
        
        if not validation_result.is_valid:
            logger.warning("Action validation failed", intent_id=intent_obj.id, errors=validation_result.errors)
            return IntentResponse(
                intent_id=intent_obj.id,
                status="validation_failed",
                message="Generated actions failed validation",
                confidence=intent_obj.confidence,
                clarification_needed=False
            )
        
        # Output actions for future execution
        output_result = output_service.save_actions(action_sequence)
        
        # Notify WebSocket clients
        await ws_manager.broadcast({
            "type": "intent_processed",
            "intent_id": intent_obj.id,
            "status": "completed",
            "actions_count": len(action_sequence.actions)
        })
        
        logger.info("Intent processed successfully", intent_id=intent_obj.id, actions_count=len(action_sequence.actions))
        
        return IntentResponse(
            intent_id=intent_obj.id,
            status="completed",
            message="Intent processed successfully",
            confidence=intent_obj.confidence,
            clarification_needed=False
        )
        
    except Exception as e:
        logger.error("Error processing intent", error=str(e), user_id=request.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing intent: {str(e)}"
        )


# Get intent status
@intent_router.get("/intents/{intent_id}/status", response_model=ActionStatusResponse)
async def get_intent_status(
    intent_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    output_service: ActionOutputService = Depends(get_action_output)
):
    """Get the status of a submitted intent."""
    try:
        # Verify authentication
        await verify_token(credentials.credentials)
        
        # Get action status
        status_info = output_service.get_action_status(intent_id)
        
        if not status_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Intent {intent_id} not found"
            )
        
        return ActionStatusResponse(**status_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting intent status", error=str(e), intent_id=intent_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting intent status: {str(e)}"
        )


# WebSocket endpoint for real-time updates
@intent_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.
    
    Clients can connect to receive real-time notifications about:
    - Intent processing status
    - Action execution updates
    - Network anomalies
    - System alerts
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            # Receive messages from client (e.g., authentication, subscriptions)
            data = await websocket.receive_json()
            
            # Handle authentication
            if data.get("type") == "auth":
                token = data.get("token")
                try:
                    user_info = await verify_token(token)
                    await websocket.send_json({
                        "type": "auth_success",
                        "message": "Authentication successful"
                    })
                    logger.info("WebSocket authenticated", user_id=user_info.get("user_id"))
                except Exception as e:
                    await websocket.send_json({
                        "type": "auth_failed",
                        "message": "Authentication failed"
                    })
                    await ws_manager.disconnect(websocket)
                    break
            
            # Handle subscription requests
            elif data.get("type") == "subscribe":
                topics = data.get("topics", [])
                await websocket.send_json({
                    "type": "subscribed",
                    "topics": topics
                })
                logger.info("WebSocket subscribed", topics=topics)
            
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error("WebSocket error", error=str(e))
        ws_manager.disconnect(websocket)


# Health check endpoints
@health_router.get("/health", response_model=HealthResponse)
async def health_check():
    """Basic health check endpoint."""
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        components={
            "api": "healthy"
        }
    )


@health_router.get("/health/ready", response_model=HealthResponse)
async def readiness_check(
    chatgpt: ChatGPTClient = Depends(get_chatgpt_client),
    state_reader: StateFileReader = Depends(lambda: StateFileReader())
):
    """
    Readiness check endpoint.
    
    Checks if all required components are ready:
    - ChatGPT API availability
    - Network state file accessibility
    """
    components = {}
    
    # Check ChatGPT API
    try:
        is_available = await chatgpt.is_available()
        components["chatgpt_api"] = "healthy" if is_available else "unhealthy"
    except Exception as e:
        components["chatgpt_api"] = f"unhealthy: {str(e)}"
    
    # Check state file
    try:
        state = state_reader.get_current_state()
        components["network_state"] = "healthy" if state else "unhealthy"
    except Exception as e:
        components["network_state"] = f"unhealthy: {str(e)}"
    
    # Determine overall status
    overall_status = "healthy" if all("healthy" in v for v in components.values()) else "unhealthy"
    
    return HealthResponse(
        status=overall_status,
        version=settings.app_version,
        components=components
    )


@health_router.get("/health/live")
async def liveness_check():
    """Liveness check endpoint (simple ping)."""
    return {"status": "alive"}
