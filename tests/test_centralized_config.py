"""Tests for centralized configuration management."""

import pytest
import tempfile
import os
from pathlib import Path
from datetime import datetime

from src.config.centralized_config import (
    CentralizedConfigManager,
    ConfigVersion,
    ConfigOperation
)


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def config_manager(temp_db):
    """Create config manager instance."""
    return CentralizedConfigManager(db_path=temp_db)


def test_create_initial_version(config_manager):
    """Test creating initial configuration version."""
    config_data = {
        "api": {"host": "localhost", "port": 8000},
        "logging": {"level": "INFO"}
    }
    
    version = config_manager.create_version(
        config_data=config_data,
        user="admin",
        comment="Initial configuration"
    )
    
    assert version.version_number == 1
    assert version.operation == ConfigOperation.CREATE
    assert version.created_by == "admin"
    assert version.config_data == config_data
    assert version.checksum is not None


def test_create_multiple_versions(config_manager):
    """Test creating multiple configuration versions."""
    # Create first version
    config_v1 = {"api": {"port": 8000}}
    version1 = config_manager.create_version(
        config_data=config_v1,
        user="admin",
        comment="Version 1"
    )
    
    # Create second version
    config_v2 = {"api": {"port": 8080}}
    version2 = config_manager.create_version(
        config_data=config_v2,
        user="admin",
        comment="Version 2"
    )
    
    assert version1.version_number == 1
    assert version2.version_number == 2
    assert version2.parent_version == version1.version_id
    assert version2.operation == ConfigOperation.UPDATE


def test_get_version(config_manager):
    """Test retrieving specific version."""
    config_data = {"test": "data"}
    created_version = config_manager.create_version(
        config_data=config_data,
        user="admin",
        comment="Test version"
    )
    
    retrieved_version = config_manager.get_version(created_version.version_number)
    
    assert retrieved_version is not None
    assert retrieved_version.version_id == created_version.version_id
    assert retrieved_version.config_data == config_data


def test_get_nonexistent_version(config_manager):
    """Test retrieving non-existent version."""
    version = config_manager.get_version(999)
    assert version is None


def test_rollback_to_version(config_manager):
    """Test rolling back to previous version."""
    # Create versions
    config_v1 = {"setting": "value1"}
    version1 = config_manager.create_version(
        config_data=config_v1,
        user="admin",
        comment="Version 1"
    )
    
    config_v2 = {"setting": "value2"}
    version2 = config_manager.create_version(
        config_data=config_v2,
        user="admin",
        comment="Version 2"
    )
    
    # Rollback to version 1
    rollback_version = config_manager.rollback_to_version(
        version_number=1,
        user="admin",
        comment="Rollback test"
    )
    
    assert rollback_version.version_number == 3
    assert rollback_version.operation == ConfigOperation.ROLLBACK
    assert rollback_version.config_data == config_v1
    assert rollback_version.parent_version == version2.version_id


def test_rollback_to_nonexistent_version(config_manager):
    """Test rollback to non-existent version fails."""
    with pytest.raises(ValueError, match="Version 999 not found"):
        config_manager.rollback_to_version(
            version_number=999,
            user="admin",
            comment="Should fail"
        )


def test_get_current_config(config_manager):
    """Test getting current active configuration."""
    config_data = {"current": "config"}
    config_manager.create_version(
        config_data=config_data,
        user="admin",
        comment="Current config"
    )
    
    current = config_manager.get_current_config()
    assert current == config_data


def test_get_version_history(config_manager):
    """Test retrieving version history."""
    # Create multiple versions
    for i in range(5):
        config_manager.create_version(
            config_data={"version": i},
            user="admin",
            comment=f"Version {i}"
        )
    
    history = config_manager.get_version_history(limit=3)
    
    assert len(history) == 3
    # Should be in descending order
    assert history[0]["version_number"] == 5
    assert history[1]["version_number"] == 4
    assert history[2]["version_number"] == 3


def test_get_audit_trail(config_manager):
    """Test retrieving audit trail."""
    # Create versions
    config_manager.create_version(
        config_data={"test": "data1"},
        user="user1",
        comment="First",
        ip_address="192.168.1.1"
    )
    
    config_manager.create_version(
        config_data={"test": "data2"},
        user="user2",
        comment="Second",
        ip_address="192.168.1.2"
    )
    
    # Get all audit entries
    audit = config_manager.get_audit_trail(limit=10)
    assert len(audit) == 2
    
    # Filter by user
    audit_user1 = config_manager.get_audit_trail(user="user1", limit=10)
    assert len(audit_user1) == 1
    assert audit_user1[0]["user"] == "user1"


def test_audit_trail_with_time_filter(config_manager):
    """Test audit trail with time filtering."""
    start_time = datetime.now()
    
    config_manager.create_version(
        config_data={"test": "data"},
        user="admin",
        comment="Test"
    )
    
    end_time = datetime.now()
    
    audit = config_manager.get_audit_trail(
        start_time=start_time,
        end_time=end_time,
        limit=10
    )
    
    assert len(audit) >= 1


def test_checksum_calculation(config_manager):
    """Test that identical configs have same checksum."""
    config1 = {"a": 1, "b": 2}
    config2 = {"b": 2, "a": 1}  # Same data, different order
    
    version1 = config_manager.create_version(
        config_data=config1,
        user="admin",
        comment="Config 1"
    )
    
    version2 = config_manager.create_version(
        config_data=config2,
        user="admin",
        comment="Config 2"
    )
    
    # Checksums should be identical (order-independent)
    assert version1.checksum == version2.checksum


def test_change_detection(config_manager):
    """Test change detection between versions."""
    config_v1 = {
        "api": {"port": 8000, "host": "localhost"},
        "logging": {"level": "INFO"}
    }
    
    config_v2 = {
        "api": {"port": 8080, "host": "localhost"},  # Modified
        "logging": {"level": "DEBUG"},  # Modified
        "monitoring": {"enabled": True}  # Added
    }
    
    config_manager.create_version(
        config_data=config_v1,
        user="admin",
        comment="V1"
    )
    
    version2 = config_manager.create_version(
        config_data=config_v2,
        user="admin",
        comment="V2"
    )
    
    # Get audit entry to check changes
    audit = config_manager.get_audit_trail(limit=1)
    changes = audit[0]["changes"]
    
    assert "modified" in changes
    assert "added" in changes


def test_statistics(config_manager):
    """Test statistics tracking."""
    # Create some versions
    config_manager.create_version(
        config_data={"v": 1},
        user="admin",
        comment="V1"
    )
    
    config_manager.create_version(
        config_data={"v": 2},
        user="admin",
        comment="V2"
    )
    
    config_manager.rollback_to_version(
        version_number=1,
        user="admin",
        comment="Rollback"
    )
    
    stats = config_manager.get_stats()
    
    assert stats["total_versions"] == 3
    assert stats["total_updates"] == 1
    assert stats["total_rollbacks"] == 1
    assert stats["current_version_number"] == 3


def test_concurrent_version_creation(config_manager):
    """Test that version numbers are sequential even with concurrent access."""
    import threading
    
    versions = []
    
    def create_version(i):
        v = config_manager.create_version(
            config_data={"thread": i},
            user=f"user{i}",
            comment=f"Thread {i}"
        )
        versions.append(v)
    
    threads = []
    for i in range(10):
        t = threading.Thread(target=create_version, args=(i,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    # Check that all version numbers are unique and sequential
    version_numbers = [v.version_number for v in versions]
    assert len(set(version_numbers)) == 10
    assert min(version_numbers) == 1
    assert max(version_numbers) == 10


def test_empty_config(config_manager):
    """Test handling of empty configuration."""
    version = config_manager.create_version(
        config_data={},
        user="admin",
        comment="Empty config"
    )
    
    assert version.config_data == {}
    assert version.checksum is not None


def test_large_config(config_manager):
    """Test handling of large configuration."""
    # Create a large config
    large_config = {
        f"section_{i}": {
            f"key_{j}": f"value_{j}"
            for j in range(100)
        }
        for i in range(10)
    }
    
    version = config_manager.create_version(
        config_data=large_config,
        user="admin",
        comment="Large config"
    )
    
    retrieved = config_manager.get_version(version.version_number)
    assert retrieved.config_data == large_config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
