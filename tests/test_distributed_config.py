"""Tests for distributed configuration management."""

import pytest
import time
import threading
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from src.config.distributed_config import (
    DistributedConfigManager,
    DistributedConfigUpdate,
    SyncStatus
)


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    with patch('src.config.distributed_config.redis') as mock:
        redis_client = MagicMock()
        pubsub = MagicMock()
        
        redis_client.pubsub.return_value = pubsub
        mock.from_url.return_value = redis_client
        
        yield redis_client, pubsub


def test_initialization(mock_redis):
    """Test distributed config manager initialization."""
    redis_client, pubsub = mock_redis
    
    manager = DistributedConfigManager(
        instance_id="test-instance",
        redis_url="redis://localhost:6379/0"
    )
    
    assert manager.instance_id == "test-instance"
    assert manager.sync_status == SyncStatus.SYNCED
    assert manager._running is True
    
    # Verify Redis connection
    redis_client.pubsub.assert_called_once()
    pubsub.subscribe.assert_called_once_with("config_updates")


def test_broadcast_update(mock_redis):
    """Test broadcasting configuration update."""
    redis_client, pubsub = mock_redis
    
    manager = DistributedConfigManager(
        instance_id="test-instance",
        redis_url="redis://localhost:6379/0"
    )
    
    config_data = {"api": {"port": 8080}}
    
    manager.broadcast_update(
        version_number=1,
        config_data=config_data,
        user="admin",
        comment="Test update"
    )
    
    # Verify publish was called
    assert redis_client.publish.called
    call_args = redis_client.publish.call_args
    
    assert call_args[0][0] == "config_updates"
    
    # Verify statistics
    assert manager.stats["updates_sent"] == 1
    assert manager.stats["last_sync_time"] is not None


def test_receive_update(mock_redis):
    """Test receiving configuration update from another instance."""
    redis_client, pubsub = mock_redis
    
    manager = DistributedConfigManager(
        instance_id="instance-1",
        redis_url="redis://localhost:6379/0"
    )
    
    # Register listener
    received_updates = []
    
    def listener(update: DistributedConfigUpdate):
        received_updates.append(update)
    
    manager.register_update_listener(listener)
    
    # Simulate receiving message
    import json
    message_data = json.dumps({
        "instance_id": "instance-2",
        "version_number": 5,
        "config_data": {"test": "data"},
        "timestamp": datetime.now().isoformat(),
        "user": "admin",
        "comment": "Test"
    })
    
    manager._handle_update_message(message_data)
    
    # Verify update was received
    assert len(received_updates) == 1
    assert received_updates[0].instance_id == "instance-2"
    assert received_updates[0].version_number == 5
    
    # Verify statistics
    assert manager.stats["updates_received"] == 1


def test_ignore_own_messages(mock_redis):
    """Test that manager ignores its own broadcast messages."""
    redis_client, pubsub = mock_redis
    
    manager = DistributedConfigManager(
        instance_id="test-instance",
        redis_url="redis://localhost:6379/0"
    )
    
    # Register listener
    received_updates = []
    manager.register_update_listener(lambda u: received_updates.append(u))
    
    # Simulate receiving own message
    import json
    message_data = json.dumps({
        "instance_id": "test-instance",  # Same as manager
        "version_number": 1,
        "config_data": {},
        "timestamp": datetime.now().isoformat(),
        "user": "admin",
        "comment": ""
    })
    
    manager._handle_update_message(message_data)
    
    # Should not receive own message
    assert len(received_updates) == 0


def test_multiple_listeners(mock_redis):
    """Test multiple update listeners."""
    redis_client, pubsub = mock_redis
    
    manager = DistributedConfigManager(
        instance_id="test-instance",
        redis_url="redis://localhost:6379/0"
    )
    
    # Register multiple listeners
    listener1_calls = []
    listener2_calls = []
    
    manager.register_update_listener(lambda u: listener1_calls.append(u))
    manager.register_update_listener(lambda u: listener2_calls.append(u))
    
    # Simulate update
    import json
    message_data = json.dumps({
        "instance_id": "other-instance",
        "version_number": 1,
        "config_data": {},
        "timestamp": datetime.now().isoformat(),
        "user": "admin",
        "comment": ""
    })
    
    manager._handle_update_message(message_data)
    
    # Both listeners should be called
    assert len(listener1_calls) == 1
    assert len(listener2_calls) == 1


def test_sync_status_transitions(mock_redis):
    """Test sync status transitions."""
    redis_client, pubsub = mock_redis
    
    manager = DistributedConfigManager(
        instance_id="test-instance",
        redis_url="redis://localhost:6379/0"
    )
    
    # Initial status
    assert manager.sync_status == SyncStatus.SYNCED
    
    # Broadcast should transition to SYNCING then SYNCED
    manager.broadcast_update(
        version_number=1,
        config_data={},
        user="admin",
        comment=""
    )
    
    assert manager.sync_status == SyncStatus.SYNCED


def test_error_handling(mock_redis):
    """Test error handling in message processing."""
    redis_client, pubsub = mock_redis
    
    manager = DistributedConfigManager(
        instance_id="test-instance",
        redis_url="redis://localhost:6379/0"
    )
    
    # Send malformed message
    manager._handle_update_message("invalid json")
    
    # Should handle error gracefully
    assert manager.stats["sync_errors"] == 1
    assert manager.sync_status == SyncStatus.ERROR


def test_listener_error_handling(mock_redis):
    """Test that listener errors don't crash the manager."""
    redis_client, pubsub = mock_redis
    
    manager = DistributedConfigManager(
        instance_id="test-instance",
        redis_url="redis://localhost:6379/0"
    )
    
    # Register failing listener
    def failing_listener(update):
        raise Exception("Listener error")
    
    manager.register_update_listener(failing_listener)
    
    # Simulate update
    import json
    message_data = json.dumps({
        "instance_id": "other-instance",
        "version_number": 1,
        "config_data": {},
        "timestamp": datetime.now().isoformat(),
        "user": "admin",
        "comment": ""
    })
    
    # Should not raise exception
    manager._handle_update_message(message_data)


def test_get_sync_status(mock_redis):
    """Test getting sync status."""
    redis_client, pubsub = mock_redis
    
    manager = DistributedConfigManager(
        instance_id="test-instance",
        redis_url="redis://localhost:6379/0"
    )
    
    status = manager.get_sync_status()
    
    assert status["instance_id"] == "test-instance"
    assert status["status"] == SyncStatus.SYNCED.value
    assert "connected_instances" in status
    assert "last_sync_time" in status


def test_get_connected_instances(mock_redis):
    """Test getting list of connected instances."""
    redis_client, pubsub = mock_redis
    
    # Mock keys and get methods
    import json
    redis_client.keys.return_value = [
        "config_instances:instance-1",
        "config_instances:instance-2"
    ]
    
    redis_client.get.side_effect = [
        json.dumps({"instance_id": "instance-1", "status": "synced"}),
        json.dumps({"instance_id": "instance-2", "status": "synced"})
    ]
    
    manager = DistributedConfigManager(
        instance_id="test-instance",
        redis_url="redis://localhost:6379/0"
    )
    
    instances = manager.get_connected_instances()
    
    assert len(instances) == 2
    assert instances[0]["instance_id"] == "instance-1"
    assert instances[1]["instance_id"] == "instance-2"


def test_stop_manager(mock_redis):
    """Test stopping the distributed config manager."""
    redis_client, pubsub = mock_redis
    
    manager = DistributedConfigManager(
        instance_id="test-instance",
        redis_url="redis://localhost:6379/0"
    )
    
    assert manager._running is True
    
    manager.stop()
    
    assert manager._running is False
    pubsub.unsubscribe.assert_called_once_with("config_updates")
    pubsub.close.assert_called_once()


def test_statistics(mock_redis):
    """Test statistics tracking."""
    redis_client, pubsub = mock_redis
    
    manager = DistributedConfigManager(
        instance_id="test-instance",
        redis_url="redis://localhost:6379/0"
    )
    
    # Broadcast update
    manager.broadcast_update(
        version_number=1,
        config_data={},
        user="admin",
        comment=""
    )
    
    # Receive update
    import json
    message_data = json.dumps({
        "instance_id": "other-instance",
        "version_number": 2,
        "config_data": {},
        "timestamp": datetime.now().isoformat(),
        "user": "admin",
        "comment": ""
    })
    manager._handle_update_message(message_data)
    
    stats = manager.get_stats()
    
    assert stats["updates_sent"] == 1
    assert stats["updates_received"] == 1
    assert stats["sync_errors"] == 0
    assert stats["instance_id"] == "test-instance"
    assert stats["running"] is True


def test_redis_connection_failure():
    """Test handling of Redis connection failure."""
    with patch('src.config.distributed_config.redis') as mock_redis:
        from redis.exceptions import RedisError
        mock_redis.from_url.side_effect = RedisError("Connection failed")
        
        with pytest.raises(RedisError):
            DistributedConfigManager(
                instance_id="test-instance",
                redis_url="redis://localhost:6379/0"
            )


def test_broadcast_failure(mock_redis):
    """Test handling of broadcast failure."""
    redis_client, pubsub = mock_redis
    
    from redis.exceptions import RedisError
    redis_client.publish.side_effect = RedisError("Publish failed")
    
    manager = DistributedConfigManager(
        instance_id="test-instance",
        redis_url="redis://localhost:6379/0"
    )
    
    with pytest.raises(RedisError):
        manager.broadcast_update(
            version_number=1,
            config_data={},
            user="admin",
            comment=""
        )
    
    # Should update error statistics
    assert manager.stats["sync_errors"] == 1
    assert manager.sync_status == SyncStatus.ERROR


def test_custom_channel(mock_redis):
    """Test using custom Redis channel."""
    redis_client, pubsub = mock_redis
    
    manager = DistributedConfigManager(
        instance_id="test-instance",
        redis_url="redis://localhost:6379/0",
        channel="custom_channel"
    )
    
    assert manager.channel == "custom_channel"
    pubsub.subscribe.assert_called_once_with("custom_channel")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
