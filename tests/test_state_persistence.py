"""Unit tests for state persistence and recovery."""

import json
import os
import shutil
import time
import tempfile
from datetime import datetime
from pathlib import Path
import pytest

from src.services.state_persistence import (
    StatePersistenceManager,
    PersistenceMetadata,
    RecoveryResult
)


@pytest.fixture
def temp_persistence_dir():
    """Create temporary persistence directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def persistence_manager(temp_persistence_dir):
    """Create persistence manager with temporary directory."""
    persistence_folder = os.path.join(temp_persistence_dir, "persistence")
    backup_folder = os.path.join(temp_persistence_dir, "backups")
    
    manager = StatePersistenceManager(
        persistence_folder=persistence_folder,
        backup_folder=backup_folder,
        max_backups=3,
        auto_backup=False,  # Disable for tests
        enable_checksums=True
    )
    
    yield manager
    
    # Cleanup
    if manager.auto_backup:
        manager.stop_auto_backup()


@pytest.fixture
def sample_state_data():
    """Sample state data for testing."""
    return {
        "active_intents": [
            {"id": "intent_1", "text": "Configure VLAN 100", "status": "processing"},
            {"id": "intent_2", "text": "Add QoS policy", "status": "pending"}
        ],
        "cached_network_state": {
            "switches": ["s1", "s2", "s3"],
            "links": ["l1", "l2"],
            "timestamp": datetime.now().isoformat()
        },
        "processing_queue": ["intent_1", "intent_2"],
        "statistics": {
            "total_intents": 42,
            "successful": 38,
            "failed": 4
        }
    }


class TestPersistenceMetadata:
    """Test PersistenceMetadata class."""
    
    def test_metadata_to_dict(self):
        """Test metadata serialization to dictionary."""
        timestamp = datetime.now()
        metadata = PersistenceMetadata(
            version="1.0.0",
            timestamp=timestamp,
            component="test_component",
            checksum="abc123"
        )
        
        result = metadata.to_dict()
        
        assert result["version"] == "1.0.0"
        assert result["timestamp"] == timestamp.isoformat()
        assert result["component"] == "test_component"
        assert result["checksum"] == "abc123"
    
    def test_metadata_from_dict(self):
        """Test metadata deserialization from dictionary."""
        timestamp = datetime.now()
        data = {
            "version": "1.0.0",
            "timestamp": timestamp.isoformat(),
            "component": "test_component",
            "checksum": "abc123"
        }
        
        metadata = PersistenceMetadata.from_dict(data)
        
        assert metadata.version == "1.0.0"
        assert metadata.component == "test_component"
        assert metadata.checksum == "abc123"
        assert isinstance(metadata.timestamp, datetime)


class TestStatePersistence:
    """Test state persistence operations."""
    
    def test_persist_state_success(self, persistence_manager, sample_state_data):
        """Test successful state persistence."""
        result = persistence_manager.persist_state(
            component="intent_parser",
            state_data=sample_state_data,
            create_backup=False
        )
        
        assert result is True
        
        # Verify file was created
        state_file = persistence_manager._get_state_file_path("intent_parser")
        assert os.path.exists(state_file)
        
        # Verify content
        with open(state_file, 'r') as f:
            content = json.load(f)
        
        assert "metadata" in content
        assert "data" in content
        assert content["data"] == sample_state_data
    
    def test_persist_state_with_backup(self, persistence_manager, sample_state_data):
        """Test state persistence with backup creation."""
        # First persist
        persistence_manager.persist_state(
            component="context_analyzer",
            state_data={"initial": "data"},
            create_backup=False
        )
        
        # Second persist with backup
        result = persistence_manager.persist_state(
            component="context_analyzer",
            state_data=sample_state_data,
            create_backup=True
        )
        
        assert result is True
        
        # Verify backup was created
        backups = persistence_manager.list_backups("context_analyzer")
        assert len(backups) == 1
    
    def test_persist_state_with_checksum(self, persistence_manager, sample_state_data):
        """Test state persistence includes checksum."""
        persistence_manager.persist_state(
            component="validator",
            state_data=sample_state_data
        )
        
        state_file = persistence_manager._get_state_file_path("validator")
        with open(state_file, 'r') as f:
            content = json.load(f)
        
        assert "metadata" in content
        assert "checksum" in content["metadata"]
        assert content["metadata"]["checksum"] is not None
    
    def test_persist_multiple_components(self, persistence_manager, sample_state_data):
        """Test persisting state for multiple components."""
        components = ["intent_parser", "context_analyzer", "action_generator"]
        
        for component in components:
            result = persistence_manager.persist_state(
                component=component,
                state_data={**sample_state_data, "component": component}
            )
            assert result is True
        
        # Verify all files exist
        for component in components:
            state_file = persistence_manager._get_state_file_path(component)
            assert os.path.exists(state_file)


class TestStateRecovery:
    """Test state recovery operations."""
    
    def test_recover_state_success(self, persistence_manager, sample_state_data):
        """Test successful state recovery."""
        # Persist state
        persistence_manager.persist_state(
            component="intent_parser",
            state_data=sample_state_data
        )
        
        # Recover state
        result = persistence_manager.recover_state("intent_parser")
        
        assert result.success is True
        assert result.component == "intent_parser"
        assert result.data == sample_state_data
        assert result.metadata is not None
        assert result.recovered_at is not None
    
    def test_recover_state_not_found(self, persistence_manager):
        """Test recovery when state file doesn't exist."""
        result = persistence_manager.recover_state("nonexistent_component")
        
        assert result.success is False
        assert result.component == "nonexistent_component"
        assert result.error == "State file not found"
        assert result.data is None
    
    def test_recover_state_with_checksum_validation(self, persistence_manager, sample_state_data):
        """Test recovery validates checksum."""
        # Persist state
        persistence_manager.persist_state(
            component="validator",
            state_data=sample_state_data
        )
        
        # Recover and verify checksum was validated
        result = persistence_manager.recover_state("validator")
        
        assert result.success is True
        assert result.metadata.checksum is not None
    
    def test_recover_state_corrupted_checksum(self, persistence_manager, sample_state_data):
        """Test recovery handles corrupted data with invalid checksum."""
        # Persist state with backup
        persistence_manager.persist_state(
            component="context_analyzer",
            state_data=sample_state_data,
            create_backup=False
        )
        
        # Create a backup manually
        state_file = persistence_manager._get_state_file_path("context_analyzer")
        persistence_manager._create_backup("context_analyzer", state_file)
        
        # Corrupt the state file
        with open(state_file, 'r') as f:
            content = json.load(f)
        
        content["data"]["corrupted"] = "data"
        # Keep old checksum (now invalid)
        
        with open(state_file, 'w') as f:
            json.dump(content, f)
        
        # Recovery should fall back to backup
        result = persistence_manager.recover_state("context_analyzer")
        
        # Should recover from backup
        assert result.success is True
        assert "corrupted" not in result.data


class TestBackupOperations:
    """Test backup and restoration operations."""
    
    def test_create_manual_backup(self, persistence_manager, sample_state_data):
        """Test manual backup creation."""
        # Persist state
        persistence_manager.persist_state(
            component="intent_parser",
            state_data=sample_state_data,
            create_backup=False
        )
        
        # Create manual backup
        result = persistence_manager.create_manual_backup("intent_parser")
        
        assert result is True
        
        # Verify backup exists
        backups = persistence_manager.list_backups("intent_parser")
        assert len(backups) == 1
    
    def test_backup_cleanup(self, persistence_manager, sample_state_data):
        """Test old backups are cleaned up."""
        # Persist state multiple times to create backups
        persistence_manager.persist_state(
            component="validator",
            state_data=sample_state_data,
            create_backup=False
        )
        
        # Create more backups than max_backups
        for i in range(5):
            time.sleep(0.1)  # Ensure different timestamps
            persistence_manager.create_manual_backup("validator")
        
        # Should only keep max_backups (3)
        backups = persistence_manager.list_backups("validator")
        assert len(backups) <= persistence_manager.max_backups
    
    def test_restore_from_backup(self, persistence_manager, sample_state_data):
        """Test restoring state from backup."""
        # Persist initial state
        initial_data = {"version": 1, "data": "initial"}
        persistence_manager.persist_state(
            component="action_generator",
            state_data=initial_data,
            create_backup=False
        )
        
        # Create backup
        persistence_manager.create_manual_backup("action_generator")
        
        # Update state
        updated_data = {"version": 2, "data": "updated"}
        persistence_manager.persist_state(
            component="action_generator",
            state_data=updated_data,
            create_backup=False
        )
        
        # Restore from backup
        result = persistence_manager.restore_from_backup("action_generator")
        
        assert result is True
        
        # Verify restored data
        recovery = persistence_manager.recover_state("action_generator")
        assert recovery.success is True
        assert recovery.data == initial_data
    
    def test_list_backups(self, persistence_manager, sample_state_data):
        """Test listing available backups."""
        # Create multiple backups
        persistence_manager.persist_state(
            component="context_analyzer",
            state_data=sample_state_data,
            create_backup=False
        )
        
        for i in range(3):
            time.sleep(0.1)
            persistence_manager.create_manual_backup("context_analyzer")
        
        # List backups
        backups = persistence_manager.list_backups("context_analyzer")
        
        assert len(backups) == 3
        
        # Verify backup info structure
        for backup in backups:
            assert "file" in backup
            assert "path" in backup
            assert "size_bytes" in backup
            assert "created_at" in backup
            assert "age_seconds" in backup
        
        # Verify sorted by newest first
        timestamps = [backup["created_at"] for backup in backups]
        assert timestamps == sorted(timestamps, reverse=True)


class TestAutoBackup:
    """Test automatic backup functionality."""
    
    def test_start_auto_backup(self, persistence_manager):
        """Test starting automatic backup thread."""
        result = persistence_manager.start_auto_backup()
        
        assert result is True
        assert persistence_manager._backup_thread is not None
        assert persistence_manager._backup_thread.is_alive()
        
        # Cleanup
        persistence_manager.stop_auto_backup()
    
    def test_stop_auto_backup(self, persistence_manager):
        """Test stopping automatic backup thread."""
        persistence_manager.start_auto_backup()
        
        result = persistence_manager.stop_auto_backup()
        
        assert result is True
        
        # Give thread time to stop
        time.sleep(0.5)
        
        if persistence_manager._backup_thread:
            assert not persistence_manager._backup_thread.is_alive()
    
    def test_auto_backup_creates_backups(self, persistence_manager, sample_state_data):
        """Test auto-backup creates periodic backups."""
        # Set short interval for testing
        persistence_manager.backup_interval = 1
        
        # Persist state
        persistence_manager.persist_state(
            component="intent_parser",
            state_data=sample_state_data,
            create_backup=False
        )
        
        # Start auto-backup
        persistence_manager.start_auto_backup()
        
        # Wait for backup to be created
        time.sleep(2)
        
        # Stop auto-backup
        persistence_manager.stop_auto_backup()
        
        # Verify backup was created
        backups = persistence_manager.list_backups("intent_parser")
        assert len(backups) >= 1


class TestPersistenceInfo:
    """Test persistence information and utilities."""
    
    def test_get_persistence_info(self, persistence_manager, sample_state_data):
        """Test getting persistence system information."""
        # Persist some states
        components = ["intent_parser", "context_analyzer"]
        for component in components:
            persistence_manager.persist_state(
                component=component,
                state_data=sample_state_data
            )
        
        # Get info
        info = persistence_manager.get_persistence_info()
        
        assert "persistence_folder" in info
        assert "backup_folder" in info
        assert "max_backups" in info
        assert "auto_backup_enabled" in info
        assert "components" in info
        
        # Verify components info
        assert len(info["components"]) == 2
        
        for comp_info in info["components"]:
            assert "name" in comp_info
            assert "file" in comp_info
            assert "size_bytes" in comp_info
            assert "last_modified" in comp_info
            assert "backup_count" in comp_info
    
    def test_delete_state(self, persistence_manager, sample_state_data):
        """Test deleting persisted state."""
        # Persist state with backup
        persistence_manager.persist_state(
            component="validator",
            state_data=sample_state_data,
            create_backup=False
        )
        persistence_manager.create_manual_backup("validator")
        
        # Delete state only
        result = persistence_manager.delete_state("validator", delete_backups=False)
        
        assert result is True
        
        # Verify state file deleted
        state_file = persistence_manager._get_state_file_path("validator")
        assert not os.path.exists(state_file)
        
        # Verify backup still exists
        backups = persistence_manager.list_backups("validator")
        assert len(backups) == 1
    
    def test_delete_state_with_backups(self, persistence_manager, sample_state_data):
        """Test deleting state and backups."""
        # Persist state with backup
        persistence_manager.persist_state(
            component="action_generator",
            state_data=sample_state_data,
            create_backup=False
        )
        persistence_manager.create_manual_backup("action_generator")
        
        # Delete state and backups
        result = persistence_manager.delete_state("action_generator", delete_backups=True)
        
        assert result is True
        
        # Verify everything deleted
        state_file = persistence_manager._get_state_file_path("action_generator")
        assert not os.path.exists(state_file)
        
        backups = persistence_manager.list_backups("action_generator")
        assert len(backups) == 0


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_persist_empty_state(self, persistence_manager):
        """Test persisting empty state data."""
        result = persistence_manager.persist_state(
            component="empty_component",
            state_data={}
        )
        
        assert result is True
        
        # Verify can recover empty state
        recovery = persistence_manager.recover_state("empty_component")
        assert recovery.success is True
        assert recovery.data == {}
    
    def test_persist_large_state(self, persistence_manager):
        """Test persisting large state data."""
        large_data = {
            "items": [{"id": i, "data": "x" * 1000} for i in range(1000)]
        }
        
        result = persistence_manager.persist_state(
            component="large_component",
            state_data=large_data
        )
        
        assert result is True
        
        # Verify can recover large state
        recovery = persistence_manager.recover_state("large_component")
        assert recovery.success is True
        assert len(recovery.data["items"]) == 1000
    
    def test_concurrent_persistence(self, persistence_manager, sample_state_data):
        """Test concurrent persistence operations."""
        import threading
        
        results = []
        
        def persist_state(component_id):
            result = persistence_manager.persist_state(
                component=f"component_{component_id}",
                state_data={**sample_state_data, "id": component_id}
            )
            results.append(result)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=persist_state, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Verify all succeeded
        assert all(results)
        assert len(results) == 5
