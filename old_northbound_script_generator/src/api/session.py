"""Session management for the API Gateway."""

import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import logging
from uuid import uuid4

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Session timeout in minutes
SESSION_TIMEOUT_MINUTES = 30


class Session(BaseModel):
    """User session model."""
    session_id: str
    username: str
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_active: bool = True


class SessionManager:
    """Manages user sessions with automatic timeout."""
    
    def __init__(self, timeout_minutes: int = SESSION_TIMEOUT_MINUTES):
        self.sessions: Dict[str, Session] = {}
        self.timeout_minutes = timeout_minutes
        self.cleanup_interval = 300  # Cleanup every 5 minutes
        self.last_cleanup = time.time()
    
    def create_session(self, username: str, ip_address: Optional[str] = None, 
                      user_agent: Optional[str] = None) -> str:
        """Create a new session."""
        session_id = str(uuid4())
        now = datetime.utcnow()
        
        session = Session(
            session_id=session_id,
            username=username,
            created_at=now,
            last_activity=now,
            expires_at=now + timedelta(minutes=self.timeout_minutes),
            ip_address=ip_address,
            user_agent=user_agent,
            is_active=True
        )
        
        self.sessions[session_id] = session
        logger.info(f"Session created for user {username}: {session_id}")
        
        # Cleanup old sessions periodically
        self._cleanup_expired_sessions()
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        session = self.sessions.get(session_id)
        
        if not session:
            return None
        
        # Check if session is expired
        if not session.is_active or session.expires_at < datetime.utcnow():
            self.invalidate_session(session_id)
            return None
        
        return session
    
    def update_session_activity(self, session_id: str) -> bool:
        """Update session last activity and extend expiration."""
        session = self.sessions.get(session_id)
        
        if not session or not session.is_active:
            return False
        
        now = datetime.utcnow()
        
        # Check if session is expired
        if session.expires_at < now:
            self.invalidate_session(session_id)
            return False
        
        # Update activity and extend expiration
        session.last_activity = now
        session.expires_at = now + timedelta(minutes=self.timeout_minutes)
        
        return True
    
    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session."""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.is_active = False
            logger.info(f"Session invalidated: {session_id} for user {session.username}")
            return True
        return False
    
    def invalidate_user_sessions(self, username: str) -> int:
        """Invalidate all sessions for a user."""
        count = 0
        for session in self.sessions.values():
            if session.username == username and session.is_active:
                session.is_active = False
                count += 1
        
        logger.info(f"Invalidated {count} sessions for user {username}")
        return count
    
    def get_user_sessions(self, username: str) -> list[Session]:
        """Get all active sessions for a user."""
        return [
            session for session in self.sessions.values()
            if session.username == username and session.is_active
        ]
    
    def _cleanup_expired_sessions(self):
        """Clean up expired sessions."""
        current_time = time.time()
        
        # Only cleanup periodically to avoid performance impact
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        now = datetime.utcnow()
        expired_sessions = []
        
        for session_id, session in self.sessions.items():
            if not session.is_active or session.expires_at < now:
                expired_sessions.append(session_id)
        
        # Remove expired sessions
        for session_id in expired_sessions:
            del self.sessions[session_id]
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
        
        self.last_cleanup = current_time
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics."""
        active_sessions = sum(1 for s in self.sessions.values() if s.is_active)
        total_sessions = len(self.sessions)
        
        # Count sessions by user
        user_sessions = {}
        for session in self.sessions.values():
            if session.is_active:
                user_sessions[session.username] = user_sessions.get(session.username, 0) + 1
        
        return {
            "active_sessions": active_sessions,
            "total_sessions": total_sessions,
            "sessions_by_user": user_sessions,
            "timeout_minutes": self.timeout_minutes
        }


# Global session manager
session_manager = SessionManager()


def create_session_for_user(username: str, ip_address: Optional[str] = None, 
                           user_agent: Optional[str] = None) -> str:
    """Create session for user."""
    return session_manager.create_session(username, ip_address, user_agent)


def validate_session(session_id: str) -> Optional[Session]:
    """Validate and update session."""
    session = session_manager.get_session(session_id)
    if session:
        session_manager.update_session_activity(session_id)
    return session


def invalidate_session(session_id: str) -> bool:
    """Invalidate session."""
    return session_manager.invalidate_session(session_id)


def invalidate_user_sessions(username: str) -> int:
    """Invalidate all user sessions."""
    return session_manager.invalidate_user_sessions(username)