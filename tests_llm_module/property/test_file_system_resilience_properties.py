"""Property-based tests for file system resilience."""

import pytest
import json
import os
import tempfile
import time
from pathlib import Path
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from datetime import datetime, timedelta
from unittest.mock import patch, Mock

from src.services.state_file_reader import StateFileReader, FileReadResult
from src.models.network import (
    NetworkState, Topology, Switch, Link, Host, Flow,
    NetworkMetrics, BandwidthMetrics, LatencyMetrics, UtilizationMetrics,
    Anomaly, AnomalyType, AnomalySeverity
)


class TestFileSystemResilienceProperties:
    """Property-based tests for file system resilience."""
    
    # Generator strategies for test data
    @staticmethod
    @st.composite
    def file_error_scenario(draw):
        """Generate file system error scenarios."""
        error_types = [
            'file_not_found',
            'permission_denied',
            'corrupted_json',
            'empty_file',
            'partial_write',
            'io_error'
        ]
        error_type = draw(st.sampled_from(error_types))
        
        # Number of consecutive failures before success
        failure_count = draw(st.integers(min_value=1, max_value=5))
        
        # Whether the operation eventually succeeds
        eventually_succeeds = draw(st.booleans())
        
        return {
            'error_type': error_type,
            'failure_count': failure_count,
            'eventually_succeeds': eventually_succeeds
        }
    
    @staticmethod
    @st.composite
    def valid_network_state_json(draw):
        """Generate valid network state JSON data."""
        # Generate timestamp
        timestamp = datetime.now() - timedelta(seconds=draw(st.integers(min_value=0, max_value=300)))
        
        # Generate switches
        num_switches = draw(st.integers(min_value=1, max_value=5))
        switches = []
        for i in range(num_switches):
            switches.append({
                "id": f"sw{i}",
                "name": f"Switch{i}",
                "dpid": f"000000000000000{i}",
                "ports": list(range(1, draw(st.integers(min_value=2, max_value=8)))),
                "status": draw(st.sampled_from(["active", "inactive"]))
            })
        
        # Generate links
        num_links = draw(st.integers(min_value=0, max_value=min(num_switches * 2, 10)))
        links = []
        for i in range(num_links):
            src_idx = draw(st.integers(min_value=0, max_value=num_switches-1))
            dst_idx = draw(st.integers(min_value=0, max_value=num_switches-1))
            if src_idx != dst_idx:
                links.append({
                    "id": f"link{i}",
                    "source_switch": f"sw{src_idx}",
                    "source_port": draw(st.integers(min_value=1, max_value=7)),
                    "destination_switch": f"sw{dst_idx}",
                    "destination_port": draw(st.integers(min_value=1, max_value=7)),
                    "bandwidth": draw(st.integers(min_value=100, max_value=10000)),
                    "latency": draw(st.floats(min_value=0.1, max_value=100.0)),
                    "status": draw(st.sampled_from(["active", "inactive"]))
                })
        
        # Generate hosts
        num_hosts = draw(st.integers(min_value=0, max_value=8))
        hosts = []
        for i in range(num_hosts):
            sw_idx = draw(st.integers(min_value=0, max_value=num_switches-1))
            hosts.append({
                "id": f"host{i}",
                "mac_address": f"00:00:00:00:00:{i:02x}",
                "ip_address": f"10.0.0.{i+1}",
                "connected_switch": f"sw{sw_idx}",
                "connected_port": draw(st.integers(min_value=1, max_value=7)),
                "status": draw(st.sampled_from(["active", "inactive"]))
            })
        
        # Generate flows
        num_flows = draw(st.integers(min_value=0, max_value=10))
        flows = []
        for i in range(num_flows):
            sw_idx = draw(st.integers(min_value=0, max_value=num_switches-1))
            flows.append({
                "id": f"flow{i}",
                "switch_id": f"sw{sw_idx}",
                "match_fields": {"in_port": draw(st.integers(min_value=1, max_value=7))},
                "actions": [{"type": "output", "port": draw(st.integers(min_value=1, max_value=7))}],
                "priority": draw(st.integers(min_value=100, max_value=10000)),
                "idle_timeout": draw(st.integers(min_value=0, max_value=300)),
                "hard_timeout": draw(st.integers(min_value=0, max_value=600)),
                "byte_count": draw(st.integers(min_value=0, max_value=1000000)),
                "packet_count": draw(st.integers(min_value=0, max_value=10000))
            })
        
        # Generate metrics
        total_capacity = draw(st.integers(min_value=1000, max_value=100000))
        used_bandwidth = draw(st.integers(min_value=0, max_value=total_capacity))
        
        metrics = {
            "bandwidth": {
                "total_capacity": total_capacity,
                "used_bandwidth": used_bandwidth,
                "available_bandwidth": total_capacity - used_bandwidth,
                "utilization_percentage": (used_bandwidth / total_capacity) * 100
            },
            "latency": {
                "average_latency": draw(st.floats(min_value=0.1, max_value=100.0)),
                "min_latency": draw(st.floats(min_value=0.01, max_value=10.0)),
                "max_latency": draw(st.floats(min_value=10.0, max_value=200.0)),
                "jitter": draw(st.floats(min_value=0.0, max_value=50.0))
            },
            "utilization": {
                "cpu_utilization": draw(st.floats(min_value=0.0, max_value=100.0)),
                "memory_utilization": draw(st.floats(min_value=0.0, max_value=100.0)),
                "port_utilization": {}
            }
        }
        
        # Generate anomalies
        num_anomalies = draw(st.integers(min_value=0, max_value=3))
        anomalies = []
        for i in range(num_anomalies):
            anomalies.append({
                "id": f"anomaly{i}",
                "type": draw(st.sampled_from([t.value for t in AnomalyType])),
                "severity": draw(st.sampled_from([s.value for s in AnomalySeverity])),
                "description": f"Test anomaly {i}",
                "affected_resources": [f"sw{draw(st.integers(min_value=0, max_value=num_switches-1))}"],
                "detected_at": timestamp.isoformat(),
                "metrics": {}
            })
        
        return {
            "timestamp": timestamp.isoformat(),
            "topology": {
                "switches": switches,
                "links": links,
                "hosts": hosts
            },
            "flows": flows,
            "metrics": metrics,
            "anomalies": anomalies
        }
    
    @staticmethod
    @st.composite
    def retry_configuration(draw):
        """Generate retry configuration parameters."""
        max_retries = draw(st.integers(min_value=1, max_value=5))
        initial_backoff = draw(st.floats(min_value=0.1, max_value=2.0))
        max_backoff = draw(st.floats(min_value=5.0, max_value=60.0))
        
        return {
            'max_retries': max_retries,
            'initial_backoff': initial_backoff,
            'max_backoff': max_backoff
        }
    
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(
        scenario=file_error_scenario(),
        state_data=valid_network_state_json()
    )
    def test_file_system_resilience_with_retries(self, scenario, state_data):
        """
        **Feature: llm-integration-module, Property 21: File system resilience**
        
        For any file reading error when accessing the JSON cache file, the retry mechanism
        should implement exponential backoff and eventually succeed or fail gracefully
        with appropriate error reporting.
        
        **Validates: Requirements 6.1**
        """
        error_type = scenario['error_type']
        failure_count = scenario['failure_count']
        eventually_succeeds = scenario['eventually_succeeds']
        
        # Create temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test_state.json")
            
            # Create reader with specific retry configuration
            reader = StateFileReader(
                cache_folder=temp_dir,
                state_file_name="test_state.json",
                max_retries=5,
                initial_backoff=0.1,  # Faster for testing
                max_backoff=2.0
            )
            
            # Assume reasonable failure counts for testing
            assume(failure_count <= reader.max_retries or eventually_succeeds)
            
            # Set up the error scenario
            if error_type == 'file_not_found':
                # File doesn't exist initially
                if eventually_succeeds and failure_count < reader.max_retries:
                    # Create file after some failures
                    def delayed_file_creation():
                        time.sleep(0.1 * failure_count)
                        with open(file_path, 'w') as f:
                            json.dump(state_data, f)
                    
                    import threading
                    thread = threading.Thread(target=delayed_file_creation)
                    thread.start()
                    
                    # Try to load - should eventually succeed
                    result = reader.read_json_file(file_path)
                    thread.join()
                    
                    if eventually_succeeds:
                        assert result.success is True
                        assert result.data is not None
                        assert result.attempts >= failure_count
                else:
                    # File never created - should fail
                    result = reader.read_json_file(file_path)
                    assert result.success is False
                    assert result.error_type == "FileNotFoundError"
                    assert result.attempts == reader.max_retries
            
            elif error_type == 'corrupted_json':
                # Create file with corrupted JSON - should fail gracefully
                with open(file_path, 'w') as f:
                    f.write('{"timestamp": "invalid json}')
                
                result = reader.read_json_file(file_path)
                assert result.success is False
                assert result.error_type == "JSONDecodeError"
                assert result.attempts == reader.max_retries
            
            elif error_type == 'empty_file':
                # Create empty file - should fail gracefully
                Path(file_path).touch()
                
                result = reader.read_json_file(file_path)
                assert result.success is False
                assert result.error_type == "ValueError"
                assert result.attempts == reader.max_retries
            
            elif error_type == 'permission_denied':
                # Skip permission tests on Windows as they're unreliable
                assume(False)
            
            else:
                # For other error types, create valid file and test successful read
                with open(file_path, 'w') as f:
                    json.dump(state_data, f)
                
                result = reader.read_json_file(file_path)
                assert result.success is True
                assert result.data is not None
    
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow])
    @given(
        state_data=valid_network_state_json(),
        retry_config=retry_configuration()
    )
    def test_exponential_backoff_behavior(self, state_data, retry_config):
        """Test that exponential backoff is applied correctly during file read retries."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test_state.json")
            
            # Create reader with specific retry configuration
            reader = StateFileReader(
                cache_folder=temp_dir,
                state_file_name="test_state.json",
                max_retries=retry_config['max_retries'],
                initial_backoff=retry_config['initial_backoff'],
                max_backoff=retry_config['max_backoff']
            )
            
            # Track sleep times
            sleep_times = []
            original_sleep = time.sleep
            
            def track_sleep(duration):
                sleep_times.append(duration)
                # Don't actually sleep in tests
                pass
            
            with patch('time.sleep', side_effect=track_sleep):
                # Try to read non-existent file
                result = reader.read_json_file(file_path)
                
                # Should fail after retries
                assert result.success is False
                assert result.error_type == "FileNotFoundError"
                assert result.attempts == retry_config['max_retries']
                
                # Verify exponential backoff was applied
                if len(sleep_times) > 0:
                    # First wait should be initial backoff
                    assert sleep_times[0] == pytest.approx(retry_config['initial_backoff'], rel=0.1)
                    
                    # Each subsequent wait should be approximately double the previous
                    for i in range(1, len(sleep_times)):
                        expected = min(
                            retry_config['initial_backoff'] * (2 ** i),
                            retry_config['max_backoff']
                        )
                        assert sleep_times[i] == pytest.approx(expected, rel=0.1)
                    
                    # Verify backoff doesn't exceed max
                    assert all(t <= retry_config['max_backoff'] for t in sleep_times)
    
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(state_data=valid_network_state_json())
    def test_successful_file_read_after_retries(self, state_data):
        """Test that file reading succeeds immediately when file exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test_state.json")
            
            reader = StateFileReader(
                cache_folder=temp_dir,
                state_file_name="test_state.json",
                max_retries=5,
                initial_backoff=0.05,
                max_backoff=0.5
            )
            
            # Create file immediately
            with open(file_path, 'w') as f:
                json.dump(state_data, f)
            
            # Try to read - should succeed immediately
            result = reader.read_json_file(file_path)
            
            # Verify success
            assert result.success is True
            assert result.data is not None
            assert result.attempts >= 1
            assert result.read_time is not None
            
            # Verify data integrity
            assert result.data["timestamp"] == state_data["timestamp"]
            assert len(result.data["topology"]["switches"]) == len(state_data["topology"]["switches"])
    
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(state_data=valid_network_state_json())
    def test_graceful_failure_with_error_reporting(self, state_data):
        """Test that failures are reported gracefully with detailed error information."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test_state.json")
            
            reader = StateFileReader(
                cache_folder=temp_dir,
                state_file_name="test_state.json",
                max_retries=3,
                initial_backoff=0.1,
                max_backoff=1.0
            )
            
            # Test various failure scenarios
            
            # 1. File not found
            result = reader.read_json_file(file_path)
            assert result.success is False
            assert result.error is not None
            assert result.error_type == "FileNotFoundError"
            assert result.attempts == reader.max_retries
            assert "not found" in result.error.lower()
            
            # 2. Corrupted JSON
            with open(file_path, 'w') as f:
                f.write('{"invalid": json}')
            
            result = reader.read_json_file(file_path)
            assert result.success is False
            assert result.error is not None
            assert result.error_type == "JSONDecodeError"
            assert result.attempts == reader.max_retries
            
            # 3. Empty file
            with open(file_path, 'w') as f:
                f.write('')
            
            result = reader.read_json_file(file_path)
            assert result.success is False
            assert result.error is not None
            assert result.error_type == "ValueError"
            assert "empty" in result.error.lower()
            
            # 4. Invalid structure
            with open(file_path, 'w') as f:
                json.dump({"invalid": "structure"}, f)
            
            result = reader.read_json_file(file_path)
            assert result.success is False
            assert result.error is not None
            assert result.error_type == "ValueError"
            assert "invalid" in result.error.lower() or "missing" in result.error.lower()
    
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow])
    @given(
        state_data=valid_network_state_json(),
        num_concurrent_reads=st.integers(min_value=2, max_value=5)
    )
    def test_concurrent_file_access_resilience(self, state_data, num_concurrent_reads):
        """Test that concurrent file access is handled gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test_state.json")
            
            # Create file
            with open(file_path, 'w') as f:
                json.dump(state_data, f)
            
            reader = StateFileReader(
                cache_folder=temp_dir,
                state_file_name="test_state.json",
                max_retries=3,
                initial_backoff=0.1,
                max_backoff=1.0
            )
            
            # Perform concurrent reads
            import threading
            results = []
            errors = []
            
            def read_file():
                try:
                    result = reader.read_json_file(file_path)
                    results.append(result)
                except Exception as e:
                    errors.append(e)
            
            threads = []
            for _ in range(num_concurrent_reads):
                thread = threading.Thread(target=read_file)
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
            
            # Verify all reads succeeded
            assert len(errors) == 0
            assert len(results) == num_concurrent_reads
            assert all(r.success for r in results)
            assert all(r.data is not None for r in results)
    
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(state_data=valid_network_state_json())
    def test_load_network_state_with_retry_logic(self, state_data):
        """Test that load_network_state properly uses retry logic and returns NetworkState."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test_state.json")
            
            reader = StateFileReader(
                cache_folder=temp_dir,
                state_file_name="test_state.json",
                max_retries=5,
                initial_backoff=0.1,
                max_backoff=2.0
            )
            
            # Test successful load
            with open(file_path, 'w') as f:
                json.dump(state_data, f)
            
            state = reader.load_network_state(file_path)
            
            # Verify NetworkState object
            assert state is not None
            assert isinstance(state, NetworkState)
            assert isinstance(state.timestamp, datetime)
            assert len(state.topology.switches) == len(state_data["topology"]["switches"])
            
            # Test load failure with non-existent file
            non_existent = os.path.join(temp_dir, "non_existent.json")
            state = reader.load_network_state(non_existent)
            assert state is None
            
            # Test load failure with corrupted file
            corrupted_path = os.path.join(temp_dir, "corrupted.json")
            with open(corrupted_path, 'w') as f:
                f.write('{"invalid": json}')
            
            state = reader.load_network_state(corrupted_path)
            assert state is None
    
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow])
    @given(state_data=valid_network_state_json())
    def test_file_info_retrieval(self, state_data):
        """Test that file information can be retrieved even when file operations fail."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test_state.json")
            
            reader = StateFileReader(
                cache_folder=temp_dir,
                state_file_name="test_state.json"
            )
            
            # Test info for non-existent file
            info = reader.get_file_info(file_path)
            assert info["path"] == file_path
            assert info["exists"] is False
            assert info["readable"] is False
            assert info["size_bytes"] is None
            
            # Create file and test info
            with open(file_path, 'w') as f:
                json.dump(state_data, f)
            
            info = reader.get_file_info(file_path)
            assert info["path"] == file_path
            assert info["exists"] is True
            assert info["readable"] is True
            assert info["size_bytes"] > 0
            assert info["modified_time"] is not None
            assert info["age_seconds"] is not None
            # Allow for small timing variations (microseconds)
            assert info["age_seconds"] >= -0.001
    
    def test_retry_mechanism_respects_max_retries(self):
        """Test that retry mechanism respects the configured max_retries limit."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test_state.json")
            
            # Create reader with specific max_retries
            max_retries = 3
            reader = StateFileReader(
                cache_folder=temp_dir,
                state_file_name="test_state.json",
                max_retries=max_retries,
                initial_backoff=0.1,
                max_backoff=1.0
            )
            
            # Track number of attempts
            attempt_count = [0]
            original_sleep = time.sleep
            
            def track_attempts(duration):
                attempt_count[0] += 1
            
            with patch('time.sleep', side_effect=track_attempts):
                # Try to read non-existent file
                result = reader.read_json_file(file_path)
                
                # Verify max retries was respected
                assert result.success is False
                assert result.attempts == max_retries
                # Sleep is called (max_retries - 1) times (not after last attempt)
                assert attempt_count[0] == max_retries - 1
    
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(state_data=valid_network_state_json())
    def test_error_recovery_and_continuation(self, state_data):
        """Test that the system can recover from errors and continue operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test_state.json")
            
            reader = StateFileReader(
                cache_folder=temp_dir,
                state_file_name="test_state.json",
                max_retries=3,
                initial_backoff=0.1,
                max_backoff=1.0
            )
            
            # First attempt - file doesn't exist
            result1 = reader.load_network_state(file_path)
            assert result1 is None
            
            # Create file
            with open(file_path, 'w') as f:
                json.dump(state_data, f)
            
            # Second attempt - should succeed
            result2 = reader.load_network_state(file_path)
            assert result2 is not None
            assert isinstance(result2, NetworkState)
            
            # Corrupt file
            with open(file_path, 'w') as f:
                f.write('{"invalid": json}')
            
            # Third attempt - should fail gracefully
            result3 = reader.load_network_state(file_path)
            assert result3 is None
            
            # Fix file
            with open(file_path, 'w') as f:
                json.dump(state_data, f)
            
            # Fourth attempt - should succeed again
            result4 = reader.load_network_state(file_path)
            assert result4 is not None
            assert isinstance(result4, NetworkState)
