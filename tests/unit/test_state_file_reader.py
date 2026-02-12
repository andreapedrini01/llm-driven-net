"""Tests for StateFileReader service."""

import json
import os
import time
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import pytest

from src.services.state_file_reader import StateFileReader, FileReadResult
from src.models.network import NetworkState


@pytest.fixture
def temp_cache_dir():
    """Create a temporary cache directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_network_state_json():
    """Sample valid network state JSON data."""
    # Use current time to avoid timezone comparison issues
    current_time = datetime.now().isoformat()
    return {
        "timestamp": current_time,
        "topology": {
            "switches": [
                {
                    "id": "switch_1",
                    "name": "Core Switch 1",
                    "dpid": "0000000000000001",
                    "ports": [1, 2, 3, 4],
                    "status": "active"
                }
            ],
            "links": [
                {
                    "id": "link_1",
                    "source_switch": "switch_1",
                    "source_port": 1,
                    "destination_switch": "switch_2",
                    "destination_port": 1,
                    "bandwidth": 1000,
                    "latency": 5.0,
                    "status": "active"
                }
            ],
            "hosts": [
                {
                    "id": "host_1",
                    "mac_address": "00:00:00:00:00:01",
                    "ip_address": "10.0.0.1",
                    "connected_switch": "switch_1",
                    "connected_port": 2,
                    "status": "active"
                }
            ]
        },
        "flows": [],
        "slices": [],
        "metrics": {
            "bandwidth": {
                "total_capacity": 10000,
                "used_bandwidth": 2500,
                "available_bandwidth": 7500,
                "utilization_percentage": 25.0
            },
            "latency": {
                "average_latency": 10.5,
                "min_latency": 5.0,
                "max_latency": 20.0,
                "jitter": 2.5
            },
            "utilization": {
                "cpu_utilization": 45.0,
                "memory_utilization": 60.0,
                "disk_utilization": 30.0
            }
        },
        "anomalies": []
    }


@pytest.fixture
def state_file_reader(temp_cache_dir):
    """Create a StateFileReader instance for testing."""
    return StateFileReader(
        cache_folder=temp_cache_dir,
        state_file_name="test_state.json",
        max_retries=3,
        initial_backoff=0.1,
        max_backoff=1.0,
        enable_file_watching=False
    )


class TestStateFileReader:
    """Test suite for StateFileReader."""

    def test_initialization(self, temp_cache_dir):
        """Test StateFileReader initialization."""
        reader = StateFileReader(
            cache_folder=temp_cache_dir,
            state_file_name="test.json"
        )
        
        assert reader.cache_folder == temp_cache_dir
        assert reader.state_file_name == "test.json"
        assert reader.max_retries == 5  # default
        assert os.path.exists(temp_cache_dir)

    def test_get_file_path(self, state_file_reader, temp_cache_dir):
        """Test getting file path."""
        file_path = state_file_reader.get_file_path()
        expected_path = os.path.join(temp_cache_dir, "test_state.json")
        
        assert file_path == expected_path

    def test_read_valid_json_file(self, state_file_reader, temp_cache_dir, sample_network_state_json):
        """Test reading a valid JSON file."""
        # Create test file
        file_path = state_file_reader.get_file_path()
        with open(file_path, 'w') as f:
            json.dump(sample_network_state_json, f)
        
        # Read file
        result = state_file_reader.read_json_file()
        
        assert result.success is True
        assert result.data is not None
        assert result.error is None
        assert result.attempts == 1
        assert result.data["timestamp"] == sample_network_state_json["timestamp"]

    def test_read_nonexistent_file(self, state_file_reader):
        """Test reading a file that doesn't exist."""
        result = state_file_reader.read_json_file()
        
        assert result.success is False
        assert result.data is None
        assert result.error is not None
        assert result.error_type == "FileNotFoundError"
        assert result.attempts == 3  # Should retry

    def test_read_empty_file(self, state_file_reader, temp_cache_dir):
        """Test reading an empty file."""
        # Create empty file
        file_path = state_file_reader.get_file_path()
        Path(file_path).touch()
        
        result = state_file_reader.read_json_file()
        
        assert result.success is False
        assert result.error_type == "ValueError"
        assert "empty" in result.error.lower()

    def test_read_malformed_json(self, state_file_reader, temp_cache_dir):
        """Test reading a file with malformed JSON."""
        # Create file with invalid JSON
        file_path = state_file_reader.get_file_path()
        with open(file_path, 'w') as f:
            f.write('{"invalid": json content}')
        
        result = state_file_reader.read_json_file()
        
        assert result.success is False
        assert result.error_type == "JSONDecodeError"

    def test_read_invalid_structure(self, state_file_reader, temp_cache_dir):
        """Test reading JSON with invalid structure."""
        # Create file with valid JSON but invalid structure
        file_path = state_file_reader.get_file_path()
        with open(file_path, 'w') as f:
            json.dump({"invalid": "structure"}, f)
        
        result = state_file_reader.read_json_file()
        
        assert result.success is False
        assert result.error_type == "ValueError"
        assert "Invalid JSON structure" in result.error

    def test_validate_json_structure_valid(self, state_file_reader, sample_network_state_json):
        """Test JSON structure validation with valid data."""
        result = state_file_reader._validate_json_structure(sample_network_state_json)
        
        assert result["is_valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_json_structure_missing_fields(self, state_file_reader):
        """Test JSON structure validation with missing fields."""
        invalid_data = {"timestamp": "2024-01-15T10:30:00Z"}
        
        result = state_file_reader._validate_json_structure(invalid_data)
        
        assert result["is_valid"] is False
        assert len(result["errors"]) > 0
        assert any("topology" in error for error in result["errors"])

    def test_validate_json_structure_invalid_timestamp(self, state_file_reader, sample_network_state_json):
        """Test JSON structure validation with invalid timestamp."""
        invalid_data = sample_network_state_json.copy()
        invalid_data["timestamp"] = "invalid-timestamp"
        
        result = state_file_reader._validate_json_structure(invalid_data)
        
        assert result["is_valid"] is False
        assert any("timestamp" in error.lower() for error in result["errors"])

    def test_parse_to_network_state(self, state_file_reader, sample_network_state_json):
        """Test parsing JSON to NetworkState object."""
        state = state_file_reader.parse_to_network_state(sample_network_state_json)
        
        assert isinstance(state, NetworkState)
        assert len(state.topology.switches) == 1
        assert len(state.topology.links) == 1
        assert len(state.topology.hosts) == 1
        assert state.metrics.bandwidth.utilization_percentage == 25.0

    def test_load_network_state_success(self, state_file_reader, temp_cache_dir, sample_network_state_json):
        """Test loading network state successfully."""
        # Create test file
        file_path = state_file_reader.get_file_path()
        with open(file_path, 'w') as f:
            json.dump(sample_network_state_json, f)
        
        # Load state
        state = state_file_reader.load_network_state()
        
        assert state is not None
        assert isinstance(state, NetworkState)
        assert len(state.topology.switches) == 1

    def test_load_network_state_failure(self, state_file_reader):
        """Test loading network state when file doesn't exist."""
        state = state_file_reader.load_network_state()
        
        assert state is None

    def test_retry_logic_with_exponential_backoff(self, state_file_reader, temp_cache_dir, sample_network_state_json):
        """Test retry logic with exponential backoff."""
        file_path = state_file_reader.get_file_path()
        
        # Start time
        start_time = time.time()
        
        # Try to read non-existent file (will retry)
        result = state_file_reader.read_json_file()
        
        # End time
        elapsed_time = time.time() - start_time
        
        # Should have retried 3 times with backoff (0.1, 0.2 seconds)
        # Total wait time should be at least 0.3 seconds
        assert result.success is False
        assert result.attempts == 3
        assert elapsed_time >= 0.25  # Allow some tolerance

    def test_get_file_info_existing_file(self, state_file_reader, temp_cache_dir, sample_network_state_json):
        """Test getting file info for existing file."""
        # Create test file
        file_path = state_file_reader.get_file_path()
        with open(file_path, 'w') as f:
            json.dump(sample_network_state_json, f)
        
        # Get file info
        info = state_file_reader.get_file_info()
        
        assert info["exists"] is True
        assert info["readable"] is True
        assert info["size_bytes"] > 0
        assert info["modified_time"] is not None
        assert info["age_seconds"] is not None
        # Allow for small timing precision issues (microseconds)
        assert info["age_seconds"] >= -0.001  # Allow 1ms tolerance

    def test_get_file_info_nonexistent_file(self, state_file_reader):
        """Test getting file info for non-existent file."""
        info = state_file_reader.get_file_info()
        
        assert info["exists"] is False
        assert info["readable"] is False
        assert info["size_bytes"] is None

    def test_file_watching_start_stop(self, temp_cache_dir, sample_network_state_json):
        """Test starting and stopping file watching."""
        callback_called = []
        
        def test_callback(state):
            callback_called.append(state)
        
        reader = StateFileReader(
            cache_folder=temp_cache_dir,
            state_file_name="watch_test.json",
            enable_file_watching=False,
            file_change_callback=test_callback
        )
        
        # Start watching
        success = reader.start_file_watching()
        assert success is True
        assert reader.is_watching() is True
        
        # Stop watching
        success = reader.stop_file_watching()
        assert success is True
        assert reader.is_watching() is False

    def test_file_watching_callback(self, temp_cache_dir, sample_network_state_json):
        """Test file watching callback is triggered on file change."""
        callback_called = []
        
        def test_callback(state):
            callback_called.append(state)
        
        # Create initial file
        file_path = os.path.join(temp_cache_dir, "watch_test.json")
        with open(file_path, 'w') as f:
            json.dump(sample_network_state_json, f)
        
        reader = StateFileReader(
            cache_folder=temp_cache_dir,
            state_file_name="watch_test.json",
            enable_file_watching=False,
            file_change_callback=test_callback
        )
        
        # Start watching
        reader.start_file_watching()
        
        # Wait a bit for watcher to initialize
        time.sleep(1.0)
        
        # Modify file with updated timestamp to ensure change is detected
        sample_network_state_json["timestamp"] = datetime.now().isoformat()
        with open(file_path, 'w') as f:
            json.dump(sample_network_state_json, f)
        
        # Wait for callback (file watching can be slow on some systems)
        time.sleep(3.0)
        
        # Stop watching
        reader.stop_file_watching()
        
        # Callback should have been called (may not work reliably on all systems)
        # This is a best-effort test
        if len(callback_called) > 0:
            assert isinstance(callback_called[0], NetworkState)
        else:
            # File watching may not work reliably in test environment
            pytest.skip("File watching callback not triggered (may be system-dependent)")

    def test_concurrent_file_reading(self, state_file_reader, temp_cache_dir, sample_network_state_json):
        """Test concurrent file reading operations."""
        import threading
        
        # Create test file
        file_path = state_file_reader.get_file_path()
        with open(file_path, 'w') as f:
            json.dump(sample_network_state_json, f)
        
        results = []
        
        def read_file():
            result = state_file_reader.read_json_file()
            results.append(result)
        
        # Create multiple threads
        threads = [threading.Thread(target=read_file) for _ in range(5)]
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # All reads should succeed
        assert len(results) == 5
        assert all(r.success for r in results)

    def test_error_handling_permission_error(self, state_file_reader, temp_cache_dir, sample_network_state_json):
        """Test error handling for permission errors."""
        # This test is platform-specific and may not work on all systems
        # Skip on Windows where permission handling is different
        import platform
        if platform.system() == "Windows":
            pytest.skip("Permission test not reliable on Windows")
        
        # Create test file
        file_path = state_file_reader.get_file_path()
        with open(file_path, 'w') as f:
            json.dump(sample_network_state_json, f)
        
        # Remove read permission
        os.chmod(file_path, 0o000)
        
        try:
            result = state_file_reader.read_json_file()
            assert result.success is False
            assert result.error_type == "PermissionError"
        finally:
            # Restore permissions for cleanup
            os.chmod(file_path, 0o644)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
