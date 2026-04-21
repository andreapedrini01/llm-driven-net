"""Property-based tests for state data freshness."""

import pytest
import json
import os
import time
import tempfile
from pathlib import Path
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from datetime import datetime, timedelta
from llm_integration_module.services.context_analyzer import NetworkStateCache
from llm_integration_module.models.network import (
    NetworkState, Topology, Switch, Link, Host, Flow,
    NetworkMetrics, BandwidthMetrics, LatencyMetrics, UtilizationMetrics,
    Anomaly, AnomalyType, AnomalySeverity
)


class TestStateFreshnessProperties:
    """Property-based tests for state data freshness."""
    
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
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        state_data=valid_network_state_json(),
        max_age_threshold=st.integers(min_value=10, max_value=600)
    )
    def test_state_freshness_loading(self, state_data, max_age_threshold):
        """
        **Feature: llm-integration-module, Property 5: State data freshness**
        
        For any intent processing operation, the LLM_Module should load the most 
        recent NetworkState data from the JSON file in cache.
        
        **Validates: Requirements 1.5, 2.1**
        """
        # Create temporary file with valid JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(state_data, f)
            temp_file = f.name
        
        try:
            # Create cache and load state
            cache = NetworkStateCache(default_ttl=max_age_threshold)
            state = cache.load_state_from_file(temp_file)
            
            # Verify state was loaded successfully
            assert state is not None
            assert isinstance(state, NetworkState)
            
            # Verify the loaded state is the most recent
            cached_state = cache.get_current_state()
            assert cached_state is not None
            assert cached_state.timestamp == state.timestamp
            
            # Verify state age is tracked correctly
            state_age = cache.get_state_age()
            assert state_age is not None
            assert state_age >= 0.0
            assert state_age < 5.0  # Should be very recent (loaded just now)
            
            # Verify state is considered fresh immediately after loading
            assert cache.is_state_fresh(max_age_seconds=max_age_threshold)
            assert not cache.is_state_stale(max_age=max_age_threshold)
            
        finally:
            # Clean up
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        state_data=valid_network_state_json(),
        max_age_threshold=st.integers(min_value=10, max_value=600)
    )
    def test_state_staleness_detection(self, state_data, max_age_threshold):
        """
        **Feature: llm-integration-module, Property 5: State data freshness**
        
        The LLM_Module should correctly detect when NetworkState data exceeds 
        the configured age threshold and mark it as stale.
        
        **Validates: Requirements 2.3, 2.4**
        """
        # Create temporary file with valid JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(state_data, f)
            temp_file = f.name
        
        try:
            # Create cache with specific TTL
            cache = NetworkStateCache(default_ttl=max_age_threshold)
            state = cache.load_state_from_file(temp_file)
            
            # Verify state is fresh initially
            assert cache.is_state_fresh(max_age_seconds=max_age_threshold)
            assert not cache.is_state_stale(max_age=max_age_threshold)
            
            # Test with a very small threshold to verify staleness detection works
            very_small_threshold = 0.001  # 1 millisecond
            time.sleep(0.01)  # Wait 10 milliseconds
            
            # Check state age increased
            state_age = cache.get_state_age()
            assert state_age is not None
            assert state_age > 0
            
            # With very small threshold, state should be stale
            assert cache.is_state_stale(max_age=very_small_threshold)
            assert not cache.is_state_fresh(max_age_seconds=very_small_threshold)
            
            # But with large threshold, state should still be fresh
            assert cache.is_state_fresh(max_age_seconds=max_age_threshold)
            assert not cache.is_state_stale(max_age=max_age_threshold)
            
        finally:
            # Clean up
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        initial_state=valid_network_state_json(),
        updated_state=valid_network_state_json()
    )
    def test_state_refresh_updates_freshness(self, initial_state, updated_state):
        """
        **Feature: llm-integration-module, Property 5: State data freshness**
        
        When state is refreshed, the LLM_Module should load the new data and 
        reset the freshness timer.
        
        **Validates: Requirements 2.3, 2.4**
        """
        # Create temporary file with initial state
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(initial_state, f)
            temp_file = f.name
        
        try:
            # Create cache and load initial state
            cache = NetworkStateCache(default_ttl=300)
            initial_loaded = cache.load_state_from_file(temp_file)
            
            # Get initial age
            initial_age = cache.get_state_age()
            assert initial_age is not None
            assert initial_age < 1.0
            
            # Wait a bit
            time.sleep(0.1)
            
            # Verify age increased
            age_after_wait = cache.get_state_age()
            assert age_after_wait > initial_age
            
            # Update the file with new state
            with open(temp_file, 'w') as f:
                json.dump(updated_state, f)
            
            # Refresh state
            refreshed_state = cache.refresh_state(temp_file)
            
            # Verify refresh was successful
            assert refreshed_state is not None
            assert isinstance(refreshed_state, NetworkState)
            
            # Verify age was reset (should be very recent)
            age_after_refresh = cache.get_state_age()
            assert age_after_refresh is not None
            assert age_after_refresh < 1.0  # Should be fresh again
            assert age_after_refresh < age_after_wait  # Should be younger than before refresh
            
            # Verify state is fresh after refresh
            assert cache.is_state_fresh(max_age_seconds=300)
            assert not cache.is_state_stale(max_age=300)
            
        finally:
            # Clean up
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        state_data=valid_network_state_json(),
        max_age_threshold=st.integers(min_value=10, max_value=100)
    )
    def test_multiple_freshness_checks_consistency(self, state_data, max_age_threshold):
        """
        **Feature: llm-integration-module, Property 5: State data freshness**
        
        Multiple freshness checks should be consistent and accurately reflect 
        the state age over time.
        
        **Validates: Requirements 2.3, 2.4**
        """
        # Create temporary file with valid JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(state_data, f)
            temp_file = f.name
        
        try:
            # Create cache and load state
            cache = NetworkStateCache(default_ttl=max_age_threshold)
            state = cache.load_state_from_file(temp_file)
            
            # Perform multiple freshness checks
            ages = []
            freshness_results = []
            staleness_results = []
            
            for i in range(3):
                age = cache.get_state_age()
                is_fresh = cache.is_state_fresh(max_age_seconds=max_age_threshold)
                is_stale = cache.is_state_stale(max_age=max_age_threshold)
                
                ages.append(age)
                freshness_results.append(is_fresh)
                staleness_results.append(is_stale)
                
                # Wait between checks
                if i < 2:
                    time.sleep(0.05)
            
            # Verify ages are monotonically increasing
            assert ages[0] < ages[1] < ages[2]
            
            # Verify freshness and staleness are opposites
            for fresh, stale in zip(freshness_results, staleness_results):
                assert fresh != stale
            
            # Verify all ages are reasonable
            for age in ages:
                assert age >= 0.0
                assert age < 10.0  # Should not be too old in this test
            
        finally:
            # Clean up
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(state_data=valid_network_state_json())
    def test_state_freshness_with_no_state_loaded(self, state_data):
        """
        **Feature: llm-integration-module, Property 5: State data freshness**
        
        When no state is loaded, freshness checks should indicate unavailable/stale state.
        
        **Validates: Requirements 2.3, 2.4**
        """
        # Create cache without loading any state
        cache = NetworkStateCache(default_ttl=300)
        
        # Verify no state is available
        assert cache.get_current_state() is None
        
        # Verify age is None when no state loaded
        assert cache.get_state_age() is None
        
        # Verify state is considered stale when not loaded
        assert cache.is_state_stale(max_age=300)
        
        # Verify state is not fresh when not loaded
        assert not cache.is_state_fresh(max_age_seconds=300)
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        state_data=valid_network_state_json(),
        custom_max_age=st.integers(min_value=1, max_value=100)
    )
    def test_state_freshness_with_custom_thresholds(self, state_data, custom_max_age):
        """
        **Feature: llm-integration-module, Property 5: State data freshness**
        
        Freshness checks should respect custom age thresholds provided by the caller.
        
        **Validates: Requirements 2.3, 2.4**
        """
        # Create temporary file with valid JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(state_data, f)
            temp_file = f.name
        
        try:
            # Create cache with default TTL
            cache = NetworkStateCache(default_ttl=300)
            state = cache.load_state_from_file(temp_file)
            
            # Check freshness with custom threshold
            is_fresh_custom = cache.is_state_fresh(max_age_seconds=custom_max_age)
            is_stale_custom = cache.is_state_stale(max_age=custom_max_age)
            
            # Verify freshness and staleness are opposites
            assert is_fresh_custom != is_stale_custom
            
            # Verify state age is within reasonable bounds
            state_age = cache.get_state_age()
            assert state_age is not None
            
            # If age is less than threshold, should be fresh
            if state_age < custom_max_age:
                assert is_fresh_custom
                assert not is_stale_custom
            # If age is greater than threshold, should be stale
            elif state_age > custom_max_age:
                assert not is_fresh_custom
                assert is_stale_custom
            
        finally:
            # Clean up
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    @given(
        state_data=valid_network_state_json(),
        ttl_seconds=st.integers(min_value=5, max_value=20)
    )
    def test_state_freshness_respects_ttl(self, state_data, ttl_seconds):
        """
        **Feature: llm-integration-module, Property 5: State data freshness**
        
        State freshness should respect the TTL (time-to-live) configured for the cache.
        
        **Validates: Requirements 2.3, 2.4**
        """
        # Create temporary file with valid JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(state_data, f)
            temp_file = f.name
        
        try:
            # Create cache with specific TTL
            cache = NetworkStateCache(default_ttl=ttl_seconds)
            state = cache.load_state_from_file(temp_file)
            
            # Verify state is fresh initially
            assert cache.is_state_fresh(max_age_seconds=ttl_seconds)
            
            # Get cache stats
            stats = cache.get_cache_stats()
            assert stats["current_state_available"]
            assert stats["current_state_fresh"]
            
            # Verify state age is tracked
            age = cache.get_state_age()
            assert age is not None
            assert age < ttl_seconds
            
        finally:
            # Clean up
            if os.path.exists(temp_file):
                os.unlink(temp_file)
