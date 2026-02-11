"""WebSocket connection manager for real-time updates."""

from typing import List, Dict, Any
from fastapi import WebSocket
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""
    
    def __init__(self):
        """Initialize the connection manager."""
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[WebSocket, List[str]] = {}
    
    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriptions[websocket] = []
        logger.info("WebSocket connection established", total_connections=len(self.active_connections))
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]
        logger.info("WebSocket connection closed", total_connections=len(self.active_connections))
    
    async def send_personal_message(self, message: Dict[Any, Any], websocket: WebSocket):
        """Send a message to a specific WebSocket connection."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error("Error sending personal message", error=str(e))
            self.disconnect(websocket)
    
    async def broadcast(self, message: Dict[Any, Any], topic: str = None):
        """
        Broadcast a message to all connected clients.
        
        Args:
            message: The message to broadcast
            topic: Optional topic filter (only send to clients subscribed to this topic)
        """
        disconnected = []
        
        for connection in self.active_connections:
            # Check if topic filtering is needed
            if topic and topic not in self.subscriptions.get(connection, []):
                continue
            
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error("Error broadcasting message", error=str(e))
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)
    
    def subscribe(self, websocket: WebSocket, topics: List[str]):
        """Subscribe a WebSocket connection to specific topics."""
        if websocket in self.subscriptions:
            self.subscriptions[websocket].extend(topics)
            self.subscriptions[websocket] = list(set(self.subscriptions[websocket]))  # Remove duplicates
            logger.info("WebSocket subscribed to topics", topics=topics)
    
    def unsubscribe(self, websocket: WebSocket, topics: List[str]):
        """Unsubscribe a WebSocket connection from specific topics."""
        if websocket in self.subscriptions:
            for topic in topics:
                if topic in self.subscriptions[websocket]:
                    self.subscriptions[websocket].remove(topic)
            logger.info("WebSocket unsubscribed from topics", topics=topics)
    
    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self.active_connections)
