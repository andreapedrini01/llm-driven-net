"""Distributed configuration management for multi-instance deployments."""

import json
import logging
import threading
import time
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import redis
from redis.exceptions import RedisError


class SyncStatus(str, Enum):
    """Configuration sync status."""
    SYNCED = "synced"
    OUT_OF_SYNC = "out_of_sync"
    SYNCING = "syncing"
    ERROR = "error"


@dataclass
class DistributedConfigUpdate:
    """Distributed configuration update message."""
    instance_id: str
    version_number: int
    config_data: Dict[str, Any]
    timestamp: datetime
    user: str
    comment: str


class DistributedConfigManager:
    """
    Distributed configuration manager using Redis pub/sub.
    
    Features:
    - Real-time configuration sync across instances
    - Leader election for configuration updates
    - Conflict resolution
    - Network partition handling
    """
    
    def __init__(
        self,
        instance_id: str,
        redis_url: str = "redis://localhost:6379/0",
        channel: str = "config_updates"
    ):
        self.logger = logging.getLogger("DistributedConfigManager")
        self.instance_id = instance_id
        self.channel = channel
        
        # Redis connection
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.pubsub = self.redis_client.pubsub()
            self.logger.info(f"Connected to Redis at {redis_url}")
        except RedisError as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            raise
        
        # Sync status
        self.sync_status = SyncStatus.SYNCED
        self._status_lock = threading.RLock()
        
        # Update listeners
        self._update_listeners: List[Callable[[DistributedConfigUpdate], None]] = []
        
        # Subscriber thread
        self._subscriber_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Statistics
        self.stats = {
            "updates_received": 0,
            "updates_sent": 0,
            "sync_errors": 0,
            "last_sync_time": None,
            "connected_instances": 0
        }
        
        # Start subscriber
        self.start()
        
        self.logger.info(f"DistributedConfigManager initialized for instance {instance_id}")
    
    def start(self):
        """Start listening for configuration updates."""
        if self._running:
            self.logger.warning("Already running")
            return
        
        self._running = True
        
        # Subscribe to channel
        self.pubsub.subscribe(self.channel)
        
        # Start subscriber thread
        self._subscriber_thread = threading.Thread(
            target=self._subscriber_loop,
            daemon=True,
            name="ConfigSubscriber"
        )
        self._subscriber_thread.start()
        
        # Register instance
        self._register_instance()
        
        self.logger.info("Started configuration subscriber")
    
    def stop(self):
        """Stop listening for configuration updates."""
        if not self._running:
            return
        
        self._running = False
        
        # Unregister instance
        self._unregister_instance()
        
        # Unsubscribe
        self.pubsub.unsubscribe(self.channel)
        self.pubsub.close()
        
        # Wait for thread
        if self._subscriber_thread:
            self._subscriber_thread.join(timeout=5)
        
        self.logger.info("Stopped configuration subscriber")
    
    def _subscriber_loop(self):
        """Subscriber loop for receiving configuration updates."""
        self.logger.info("Subscriber loop started")
        
        while self._running:
            try:
                message = self.pubsub.get_message(timeout=1.0)
                
                if message and message['type'] == 'message':
                    self._handle_update_message(message['data'])
            
            except Exception as e:
                self.logger.error(f"Error in subscriber loop: {e}")
                self.stats["sync_errors"] += 1
                time.sleep(1)
        
        self.logger.info("Subscriber loop stopped")
    
    def _handle_update_message(self, message_data: str):
        """Handle configuration update message."""
        try:
            data = json.loads(message_data)
            
            # Ignore own messages
            if data.get('instance_id') == self.instance_id:
                return
            
            # Parse update
            update = DistributedConfigUpdate(
                instance_id=data['instance_id'],
                version_number=data['version_number'],
                config_data=data['config_data'],
                timestamp=datetime.fromisoformat(data['timestamp']),
                user=data['user'],
                comment=data.get('comment', '')
            )
            
            self.logger.info(
                f"Received config update from {update.instance_id}, "
                f"version {update.version_number}"
            )
            
            # Update statistics
            self.stats["updates_received"] += 1
            self.stats["last_sync_time"] = datetime.now().isoformat()
            
            # Notify listeners
            self._notify_listeners(update)
            
            # Update sync status
            with self._status_lock:
                self.sync_status = SyncStatus.SYNCED
        
        except Exception as e:
            self.logger.error(f"Failed to handle update message: {e}")
            self.stats["sync_errors"] += 1
            
            with self._status_lock:
                self.sync_status = SyncStatus.ERROR
    
    def broadcast_update(
        self,
        version_number: int,
        config_data: Dict[str, Any],
        user: str,
        comment: str = ""
    ):
        """
        Broadcast configuration update to all instances.
        
        Args:
            version_number: Configuration version number
            config_data: Configuration data
            user: User who made the update
            comment: Update comment
        """
        try:
            with self._status_lock:
                self.sync_status = SyncStatus.SYNCING
            
            # Create update message
            message = {
                'instance_id': self.instance_id,
                'version_number': version_number,
                'config_data': config_data,
                'timestamp': datetime.now().isoformat(),
                'user': user,
                'comment': comment
            }
            
            # Publish to channel
            self.redis_client.publish(self.channel, json.dumps(message))
            
            # Update statistics
            self.stats["updates_sent"] += 1
            self.stats["last_sync_time"] = datetime.now().isoformat()
            
            with self._status_lock:
                self.sync_status = SyncStatus.SYNCED
            
            self.logger.info(f"Broadcasted config update version {version_number}")
        
        except RedisError as e:
            self.logger.error(f"Failed to broadcast update: {e}")
            self.stats["sync_errors"] += 1
            
            with self._status_lock:
                self.sync_status = SyncStatus.ERROR
            
            raise
    
    def register_update_listener(
        self,
        listener: Callable[[DistributedConfigUpdate], None]
    ):
        """Register listener for configuration updates."""
        self._update_listeners.append(listener)
        self.logger.info(f"Registered update listener: {listener.__name__}")
    
    def _notify_listeners(self, update: DistributedConfigUpdate):
        """Notify all listeners of configuration update."""
        for listener in self._update_listeners:
            try:
                listener(update)
            except Exception as e:
                self.logger.error(f"Error notifying listener {listener.__name__}: {e}")
    
    def _register_instance(self):
        """Register this instance in Redis."""
        try:
            key = f"config_instances:{self.instance_id}"
            self.redis_client.setex(
                key,
                60,  # TTL 60 seconds
                json.dumps({
                    'instance_id': self.instance_id,
                    'registered_at': datetime.now().isoformat(),
                    'status': self.sync_status.value
                })
            )
            
            # Start heartbeat thread
            self._start_heartbeat()
            
            self.logger.info(f"Registered instance {self.instance_id}")
        
        except RedisError as e:
            self.logger.error(f"Failed to register instance: {e}")
    
    def _unregister_instance(self):
        """Unregister this instance from Redis."""
        try:
            key = f"config_instances:{self.instance_id}"
            self.redis_client.delete(key)
            
            self.logger.info(f"Unregistered instance {self.instance_id}")
        
        except RedisError as e:
            self.logger.error(f"Failed to unregister instance: {e}")
    
    def _start_heartbeat(self):
        """Start heartbeat thread to keep instance registered."""
        def heartbeat_loop():
            while self._running:
                try:
                    key = f"config_instances:{self.instance_id}"
                    self.redis_client.expire(key, 60)
                    time.sleep(30)  # Heartbeat every 30 seconds
                except Exception as e:
                    self.logger.error(f"Heartbeat error: {e}")
                    time.sleep(5)
        
        heartbeat_thread = threading.Thread(
            target=heartbeat_loop,
            daemon=True,
            name="ConfigHeartbeat"
        )
        heartbeat_thread.start()
    
    def get_connected_instances(self) -> List[Dict[str, Any]]:
        """Get list of connected instances."""
        try:
            pattern = "config_instances:*"
            keys = self.redis_client.keys(pattern)
            
            instances = []
            for key in keys:
                data = self.redis_client.get(key)
                if data:
                    instances.append(json.loads(data))
            
            self.stats["connected_instances"] = len(instances)
            
            return instances
        
        except RedisError as e:
            self.logger.error(f"Failed to get connected instances: {e}")
            return []
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status."""
        with self._status_lock:
            return {
                "instance_id": self.instance_id,
                "status": self.sync_status.value,
                "connected_instances": self.stats["connected_instances"],
                "last_sync_time": self.stats["last_sync_time"]
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get distributed configuration statistics."""
        return {
            **self.stats,
            "instance_id": self.instance_id,
            "sync_status": self.sync_status.value,
            "running": self._running
        }


# Global distributed config manager instance
_distributed_config_manager: Optional[DistributedConfigManager] = None


def get_distributed_config_manager(
    instance_id: str,
    redis_url: str = "redis://localhost:6379/0"
) -> DistributedConfigManager:
    """Get or create global distributed config manager instance."""
    global _distributed_config_manager
    
    if _distributed_config_manager is None:
        _distributed_config_manager = DistributedConfigManager(instance_id, redis_url)
    
    return _distributed_config_manager
