"""Redis-based session and cache management for scalability."""

import json
import logging
import pickle
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
import redis
from redis.exceptions import RedisError


class RedisSessionManager:
    """
    Redis-based session manager for distributed deployments.
    
    Features:
    - Session storage and retrieval
    - Automatic expiration
    - Distributed caching
    - Connection pooling
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/1",
        session_ttl: int = 1800,  # 30 minutes
        cache_ttl: int = 300,  # 5 minutes
        max_connections: int = 50
    ):
        self.logger = logging.getLogger("RedisSessionManager")
        self.session_ttl = session_ttl
        self.cache_ttl = cache_ttl
        
        # Create connection pool
        try:
            self.pool = redis.ConnectionPool.from_url(
                redis_url,
                max_connections=max_connections,
                decode_responses=False  # We'll handle encoding ourselves
            )
            self.client = redis.Redis(connection_pool=self.pool)
            
            # Test connection
            self.client.ping()
            
            self.logger.info(f"Connected to Redis at {redis_url}")
        
        except RedisError as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            raise
        
        # Statistics
        self.stats = {
            "sessions_created": 0,
            "sessions_retrieved": 0,
            "sessions_deleted": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "cache_sets": 0,
            "errors": 0
        }
    
    def create_session(
        self,
        session_id: str,
        user_id: str,
        data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Create a new session.
        
        Args:
            session_id: Unique session identifier
            user_id: User identifier
            data: Session data
            ttl: Time to live in seconds (default: session_ttl)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            ttl = ttl or self.session_ttl
            
            session_data = {
                "session_id": session_id,
                "user_id": user_id,
                "created_at": datetime.now().isoformat(),
                "last_accessed": datetime.now().isoformat(),
                "data": data
            }
            
            key = f"session:{session_id}"
            
            # Store session
            self.client.setex(
                key,
                ttl,
                json.dumps(session_data)
            )
            
            # Create user session index
            user_key = f"user_sessions:{user_id}"
            self.client.sadd(user_key, session_id)
            self.client.expire(user_key, ttl)
            
            self.stats["sessions_created"] += 1
            
            self.logger.debug(f"Created session {session_id} for user {user_id}")
            return True
        
        except RedisError as e:
            self.logger.error(f"Failed to create session {session_id}: {e}")
            self.stats["errors"] += 1
            return False
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a session.
        
        Args:
            session_id: Session identifier
        
        Returns:
            Session data if found, None otherwise
        """
        try:
            key = f"session:{session_id}"
            
            data = self.client.get(key)
            
            if data is None:
                self.logger.debug(f"Session {session_id} not found")
                return None
            
            session_data = json.loads(data)
            
            # Update last accessed time
            session_data["last_accessed"] = datetime.now().isoformat()
            
            # Refresh TTL
            self.client.setex(
                key,
                self.session_ttl,
                json.dumps(session_data)
            )
            
            self.stats["sessions_retrieved"] += 1
            
            return session_data
        
        except RedisError as e:
            self.logger.error(f"Failed to get session {session_id}: {e}")
            self.stats["errors"] += 1
            return None
    
    def update_session(
        self,
        session_id: str,
        data: Dict[str, Any]
    ) -> bool:
        """
        Update session data.
        
        Args:
            session_id: Session identifier
            data: New session data
        
        Returns:
            True if successful, False otherwise
        """
        try:
            session = self.get_session(session_id)
            
            if session is None:
                self.logger.warning(f"Cannot update non-existent session {session_id}")
                return False
            
            # Update data
            session["data"].update(data)
            session["last_accessed"] = datetime.now().isoformat()
            
            key = f"session:{session_id}"
            
            self.client.setex(
                key,
                self.session_ttl,
                json.dumps(session)
            )
            
            self.logger.debug(f"Updated session {session_id}")
            return True
        
        except RedisError as e:
            self.logger.error(f"Failed to update session {session_id}: {e}")
            self.stats["errors"] += 1
            return False
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: Session identifier
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get session to find user_id
            session = self.get_session(session_id)
            
            if session:
                user_id = session["user_id"]
                
                # Remove from user session index
                user_key = f"user_sessions:{user_id}"
                self.client.srem(user_key, session_id)
            
            # Delete session
            key = f"session:{session_id}"
            self.client.delete(key)
            
            self.stats["sessions_deleted"] += 1
            
            self.logger.debug(f"Deleted session {session_id}")
            return True
        
        except RedisError as e:
            self.logger.error(f"Failed to delete session {session_id}: {e}")
            self.stats["errors"] += 1
            return False
    
    def get_user_sessions(self, user_id: str) -> list:
        """
        Get all sessions for a user.
        
        Args:
            user_id: User identifier
        
        Returns:
            List of session IDs
        """
        try:
            user_key = f"user_sessions:{user_id}"
            session_ids = self.client.smembers(user_key)
            
            return [sid.decode() if isinstance(sid, bytes) else sid for sid in session_ids]
        
        except RedisError as e:
            self.logger.error(f"Failed to get user sessions for {user_id}: {e}")
            self.stats["errors"] += 1
            return []
    
    def delete_user_sessions(self, user_id: str) -> int:
        """
        Delete all sessions for a user.
        
        Args:
            user_id: User identifier
        
        Returns:
            Number of sessions deleted
        """
        try:
            session_ids = self.get_user_sessions(user_id)
            
            count = 0
            for session_id in session_ids:
                if self.delete_session(session_id):
                    count += 1
            
            # Clean up user session index
            user_key = f"user_sessions:{user_id}"
            self.client.delete(user_key)
            
            self.logger.info(f"Deleted {count} sessions for user {user_id}")
            return count
        
        except RedisError as e:
            self.logger.error(f"Failed to delete user sessions for {user_id}: {e}")
            self.stats["errors"] += 1
            return 0
    
    def cache_set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        serialize: bool = True
    ) -> bool:
        """
        Set a cache value.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default: cache_ttl)
            serialize: Whether to serialize value with pickle
        
        Returns:
            True if successful, False otherwise
        """
        try:
            ttl = ttl or self.cache_ttl
            cache_key = f"cache:{key}"
            
            if serialize:
                data = pickle.dumps(value)
            else:
                data = value
            
            self.client.setex(cache_key, ttl, data)
            
            self.stats["cache_sets"] += 1
            
            self.logger.debug(f"Cached value for key {key}")
            return True
        
        except (RedisError, pickle.PickleError) as e:
            self.logger.error(f"Failed to cache value for key {key}: {e}")
            self.stats["errors"] += 1
            return False
    
    def cache_get(
        self,
        key: str,
        deserialize: bool = True
    ) -> Optional[Any]:
        """
        Get a cached value.
        
        Args:
            key: Cache key
            deserialize: Whether to deserialize value with pickle
        
        Returns:
            Cached value if found, None otherwise
        """
        try:
            cache_key = f"cache:{key}"
            
            data = self.client.get(cache_key)
            
            if data is None:
                self.stats["cache_misses"] += 1
                return None
            
            self.stats["cache_hits"] += 1
            
            if deserialize:
                return pickle.loads(data)
            else:
                return data
        
        except (RedisError, pickle.PickleError) as e:
            self.logger.error(f"Failed to get cached value for key {key}: {e}")
            self.stats["errors"] += 1
            return None
    
    def cache_delete(self, key: str) -> bool:
        """
        Delete a cached value.
        
        Args:
            key: Cache key
        
        Returns:
            True if successful, False otherwise
        """
        try:
            cache_key = f"cache:{key}"
            self.client.delete(cache_key)
            
            self.logger.debug(f"Deleted cache for key {key}")
            return True
        
        except RedisError as e:
            self.logger.error(f"Failed to delete cache for key {key}: {e}")
            self.stats["errors"] += 1
            return False
    
    def cache_exists(self, key: str) -> bool:
        """
        Check if a cache key exists.
        
        Args:
            key: Cache key
        
        Returns:
            True if exists, False otherwise
        """
        try:
            cache_key = f"cache:{key}"
            return self.client.exists(cache_key) > 0
        
        except RedisError as e:
            self.logger.error(f"Failed to check cache existence for key {key}: {e}")
            self.stats["errors"] += 1
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get session manager statistics."""
        try:
            # Get Redis info
            info = self.client.info()
            
            cache_hit_rate = 0.0
            total_cache_ops = self.stats["cache_hits"] + self.stats["cache_misses"]
            if total_cache_ops > 0:
                cache_hit_rate = (self.stats["cache_hits"] / total_cache_ops) * 100
            
            return {
                **self.stats,
                "cache_hit_rate": cache_hit_rate,
                "redis_connected_clients": info.get("connected_clients", 0),
                "redis_used_memory": info.get("used_memory_human", "unknown"),
                "redis_total_commands": info.get("total_commands_processed", 0)
            }
        
        except RedisError as e:
            self.logger.error(f"Failed to get stats: {e}")
            return self.stats
    
    def cleanup_expired(self) -> int:
        """
        Clean up expired sessions (Redis handles this automatically).
        This is a no-op but provided for API compatibility.
        
        Returns:
            0 (Redis handles expiration automatically)
        """
        self.logger.debug("Redis handles expiration automatically")
        return 0
    
    def close(self):
        """Close Redis connection."""
        try:
            self.client.close()
            self.logger.info("Closed Redis connection")
        except Exception as e:
            self.logger.error(f"Error closing Redis connection: {e}")


# Global session manager instance
_session_manager: Optional[RedisSessionManager] = None


def get_session_manager(
    redis_url: str = "redis://localhost:6379/1",
    **kwargs
) -> RedisSessionManager:
    """Get or create global session manager instance."""
    global _session_manager
    
    if _session_manager is None:
        _session_manager = RedisSessionManager(redis_url, **kwargs)
    
    return _session_manager
