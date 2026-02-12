"""Property-based tests for state file reading reliability."""

import pytest
import json
import os
import tempfile
from pathlib import Path
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from datetime import datetime, timedelta
from src.services.context_analyzer import NetworkStateCache
from src.models.network import (
    NetworkState, Topology, Switch, Link, Host, Flow,
    NetworkMetrics, BandwidthMetrics, LatencyMetrics, UtilizationMetrics,
    Anomaly, AnomalyType, AnomalySeverity
)


class TestStateFileReadingProperties:
    """Property-based tests for state file reading reliability."""
    
    # Generator strategies for test data
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
    def corrupted_json_data(draw):
        """Generate corrupted JSON data for testing error handling."""
        corruption_type = draw(st.sampled_from([
            "missing_timestamp",
            "invalid_timestamp",
            "missing_topology",
            "invalid_topology_type",
            "invalid_flows_type",
            "invalid_metrics_type"
        ]))
        
        # Start with a minimal valid structure
        data = {
            "timestamp": datetime.now().isoformat(),
            "topology": {
                "switches": [],
                "links": [],
                "hosts": []
            },
            "flows": [],
            "metrics": {
                "bandwidth": {
                    "total_capacity": 1000,
                    "used_bandwidth": 100,
                    "available_bandwidth": 900,
                    "utilization_percentage": 10.0
                },
                "latency": {
                    "average_latency": 5.0,
                    "min_latency": 1.0,
                    "max_latency": 10.0,
                    "jitter": 2.0
                },
                "utilization": {
                    "cpu_utilization": 50.0,
                    "memory_utilization": 60.0,
                    "port_utilization": {}
                }
            },
            "anomalies": []
        }
        
        # Apply corruption
        if corruption_type == "missing_timestamp":
            del data["timestamp"]
        elif corruption_type == "invalid_timestamp":
            data["timestamp"] = "not-a-valid-timestamp"
        elif corruption_type == "missing_topology":
            del data["topology"]
        elif corruption_type == "invalid_topology_type":
            data["topology"] = "not-a-dict"
        elif corruption_type == "invalid_flows_type":
            data["flows"] = "not-a-list"
        elif corruption_type == "invalid_metrics_type":
            data["metrics"] = "not-a-dict"
        
        return data
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(state_data=valid_network_state_json())
    def test_valid_json_file_reading(self, state_data):
        """
        **Feature: llm-integration-module, Property 6: State file reading reliability**
        
        For any valid JSON file, the LLM_Module should correctly parse the data
        and create a valid NetworkState object.
        
        **Validates: Requirements 2.1**
        """
        # Create temporary file with valid JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(state_data, f)
            temp_file = f.name
        
        try:
            # Create cache and load state
            cache = NetworkStateCache()
            state = cache.load_state_from_file(temp_file)
            
            # Verify state was loaded successfully
            assert state is not None
            assert isinstance(state, NetworkState)
            
            # Verify timestamp
            assert isinstance(state.timestamp, datetime)
            
            # Verify topology
            assert isinstance(state.topology, Topology)
            assert len(state.topology.switches) == len(state_data["topology"]["switches"])
            assert len(state.topology.links) == len(state_data["topology"]["links"])
            assert len(state.topology.hosts) == len(state_data["topology"]["hosts"])
            
            # Verify flows
            assert len(state.flows) == len(state_data["flows"])
            
            # Verify metrics
            assert isinstance(state.metrics, NetworkMetrics)
            assert isinstance(state.metrics.bandwidth, BandwidthMetrics)
            assert isinstance(state.metrics.latency, LatencyMetrics)
            assert isinstance(state.metrics.utilization, UtilizationMetrics)
            
            # Verify anomalies
            assert len(state.anomalies) == len(state_data["anomalies"])
            
            # Verify state is cached
            cached_state = cache.get_current_state()
            assert cached_state is not None
            assert cached_state.timestamp == state.timestamp
            
        finally:
            # Clean up
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(state_data=corrupted_json_data())
    def test_corrupted_json_handling(self, state_data):
        """
        **Feature: llm-integration-module, Property 6: State file reading reliability**
        
        For any corrupted or malformed JSON file, the LLM_Module should properly
        handle the error with appropriate error signaling.
        
        **Validates: Requirements 2.2**
        """
        # Create temporary file with corrupted JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(state_data, f)
            temp_file = f.name
        
        try:
            # Create cache and attempt to load state
            cache = NetworkStateCache()
            
            # Should raise an exception for corrupted data
            with pytest.raises((ValueError, Exception)):
                cache.load_state_from_file(temp_file, max_retries=1)
            
        finally:
            # Clean up
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def test_missing_file_handling(self):
        """
        **Feature: llm-integration-module, Property 6: State file reading reliability**
        
        For any missing file, the LLM_Module should properly handle the error
        with appropriate error signaling after retry attempts.
        
        **Validates: Requirements 2.2**
        """
        # Use a non-existent file path
        non_existent_file = "/tmp/non_existent_state_file_12345.json"
        
        # Ensure file doesn't exist
        if os.path.exists(non_existent_file):
            os.unlink(non_existent_file)
        
        # Create cache and attempt to load state
        cache = NetworkStateCache()
        
        # Should raise FileNotFoundError after retries
        with pytest.raises(FileNotFoundError):
            cache.load_state_from_file(non_existent_file, max_retries=2)
    
    def test_malformed_json_syntax(self):
        """
        **Feature: llm-integration-module, Property 6: State file reading reliability**
        
        For any file with invalid JSON syntax, the LLM_Module should properly
        handle the error with appropriate error signaling.
        
        **Validates: Requirements 2.2**
        """
        # Create temporary file with invalid JSON syntax
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"timestamp": "2024-01-01T00:00:00", "topology": {invalid json}')
            temp_file = f.name
        
        try:
            # Create cache and attempt to load state
            cache = NetworkStateCache()
            
            # Should raise JSONDecodeError after retries
            with pytest.raises(json.JSONDecodeError):
                cache.load_state_from_file(temp_file, max_retries=1)
            
        finally:
            # Clean up
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(state_data=valid_network_state_json())
    def test_state_refresh_functionality(self, state_data):
        """
        **Feature: llm-integration-module, Property 6: State file reading reliability**
        
        The refresh_state method should successfully reload state from file
        and update the cache.
        
        **Validates: Requirements 2.1**
        """
        # Create temporary file with valid JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(state_data, f)
            temp_file = f.name
        
        try:
            # Create cache and load initial state
            cache = NetworkStateCache()
            initial_state = cache.load_state_from_file(temp_file)
            assert initial_state is not None
            
            # Refresh state
            refreshed_state = cache.refresh_state(temp_file)
            
            # Verify refresh was successful
            assert refreshed_state is not None
            assert isinstance(refreshed_state, NetworkState)
            assert refreshed_state.timestamp == initial_state.timestamp
            
        finally:
            # Clean up
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(state_data=valid_network_state_json())
    def test_state_age_tracking(self, state_data):
        """
        **Feature: llm-integration-module, Property 6: State file reading reliability**
        
        The cache should correctly track the age of loaded state data.
        
        **Validates: Requirements 2.1**
        """
        # Create temporary file with valid JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(state_data, f)
            temp_file = f.name
        
        try:
            # Create cache and load state
            cache = NetworkStateCache()
            state = cache.load_state_from_file(temp_file)
            assert state is not None
            
            # Check state age
            age = cache.get_state_age()
            assert age is not None
            assert age >= 0.0
            assert age < 5.0  # Should be very recent
            
            # Check staleness
            assert not cache.is_state_stale(max_age=300)  # Not stale within 5 minutes
            
        finally:
            # Clean up
            if os.path.exists(temp_file):
                os.unlink(temp_file)
