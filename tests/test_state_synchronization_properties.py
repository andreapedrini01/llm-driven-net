"""Property-based tests for state synchronization reliability."""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from unittest.mock import Mock, patch
import copy

from src.services.context_analyzer import NetworkStateCache, CacheEntry, ContextCorrelationEngine
from src.services.intent_parser import IntentParser
from src.models.network import NetworkState, Topology, Switch, Link, Host, NetworkMetrics, BandwidthMetrics, LatencyMetrics, UtilizationMetrics, Flow
from src.models.intent import IntentObject, IntentType, Entity


# Test data generators
@st.composite
def generate_switch(draw):
    """Generate a valid Switch object."""
    switch_id = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'))))
    name = draw(st.text(min_size=1, max_size=30))
    dpid = draw(st.text(min_size=1, max_size=20))  # dpid is string in the model
    ports = draw(st.lists(st.integers(min_value=1, max_value=48), min_size=1, max_size=48))
    status = draw(st.sampled_from(["active", "inactive", "maintenance"]))
    
    return Switch(
        id=switch_id,
        name=name,
        dpid=dpid,
        ports=ports,
        status=status
    )


@st.composite
def generate_link(draw, switches):
    """Generate a valid Link object."""
    if len(switches) < 2:
        # Create minimal switches if not enough provided
        switches = [
            Switch(id="sw1", name="Switch1", dpid="1", ports=[1, 2], status="active"),
            Switch(id="sw2", name="Switch2", dpid="2", ports=[1, 2], status="active")
        ]
    
    source_switch = draw(st.sampled_from(switches)).id
    other_switches = [s for s in switches if s.id != source_switch]
    if not other_switches:
        # Fallback if somehow we still have no other switches
        other_switches = switches
    dest_switch = draw(st.sampled_from(other_switches)).id
    
    link_id = f"link_{source_switch}_{dest_switch}"
    source_port = draw(st.integers(min_value=1, max_value=48))
    dest_port = draw(st.integers(min_value=1, max_value=48))
    bandwidth = draw(st.integers(min_value=1, max_value=10000))
    latency = draw(st.floats(min_value=0.1, max_value=100.0))
    status = draw(st.sampled_from(["active", "inactive", "maintenance"]))
    
    return Link(
        id=link_id,
        source_switch=source_switch,
        source_port=source_port,
        destination_switch=dest_switch,
        destination_port=dest_port,
        bandwidth=bandwidth,
        latency=latency,
        status=status
    )


@st.composite
def generate_host(draw, switches):
    """Generate a valid Host object."""
    if not switches:
        switches = [Switch(id="sw1", name="Switch1", dpid="1", ports=[1, 2], status="active")]
    
    host_id = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'))))
    # Generate a proper MAC address format
    mac_parts = [f"{draw(st.integers(0, 255)):02x}" for _ in range(6)]
    mac_address = ":".join(mac_parts)
    ip_address = f"{draw(st.integers(1, 255))}.{draw(st.integers(0, 255))}.{draw(st.integers(0, 255))}.{draw(st.integers(1, 254))}"
    connected_switch = draw(st.sampled_from(switches)).id
    connected_port = draw(st.integers(min_value=1, max_value=48))
    status = draw(st.sampled_from(["active", "inactive"]))
    
    return Host(
        id=host_id,
        mac_address=mac_address,
        ip_address=ip_address,
        connected_switch=connected_switch,
        connected_port=connected_port,
        status=status
    )


@st.composite
def generate_network_metrics(draw):
    """Generate valid NetworkMetrics."""
    total_capacity = draw(st.integers(min_value=100, max_value=100000))
    used_bandwidth = draw(st.integers(min_value=0, max_value=total_capacity))
    
    bandwidth = BandwidthMetrics(
        total_capacity=total_capacity,
        used_bandwidth=used_bandwidth,
        available_bandwidth=total_capacity - used_bandwidth,
        utilization_percentage=draw(st.floats(min_value=0.0, max_value=100.0))
    )
    
    min_lat = draw(st.floats(min_value=0.1, max_value=10.0))
    max_lat = draw(st.floats(min_value=min_lat, max_value=2000.0))
    avg_lat = draw(st.floats(min_value=min_lat, max_value=max_lat))
    
    latency = LatencyMetrics(
        average_latency=avg_lat,
        min_latency=min_lat,
        max_latency=max_lat,
        jitter=draw(st.floats(min_value=0.0, max_value=50.0))
    )
    
    utilization = UtilizationMetrics(
        cpu_utilization=draw(st.floats(min_value=0.0, max_value=100.0)),
        memory_utilization=draw(st.floats(min_value=0.0, max_value=100.0))
    )
    
    return NetworkMetrics(
        bandwidth=bandwidth,
        latency=latency,
        utilization=utilization
    )


@st.composite
def generate_network_state(draw):
    """Generate a valid NetworkState object."""
    # Generate switches first
    switches = draw(st.lists(generate_switch(), min_size=1, max_size=10))
    
    # Generate links between switches
    links = draw(st.lists(generate_link(switches), min_size=0, max_size=min(20, len(switches) * 2)))
    
    # Generate hosts connected to switches
    hosts = draw(st.lists(generate_host(switches), min_size=0, max_size=20))
    
    topology = Topology(
        switches=switches,
        links=links,
        hosts=hosts
    )
    
    # Generate flows using the Flow model
    flows = []
    if switches:  # Only generate flows if we have switches
        flows = draw(st.lists(
            st.builds(Flow,
                id=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'))),
                switch_id=st.sampled_from([s.id for s in switches]),
                priority=st.integers(min_value=1, max_value=65535)
            ), 
            min_size=0, max_size=min(50, len(switches) * 5)
        ))
    
    metrics = draw(generate_network_metrics())
    
    # Generate timestamp (must not be in the future due to model validation)
    # Use a fixed base time to avoid flaky strategy issues
    base_time = datetime(2024, 1, 1, 12, 0, 0)
    timestamp = draw(st.datetimes(
        min_value=base_time - timedelta(hours=1),
        max_value=base_time - timedelta(seconds=1)  # Always in the past
    ))
    
    return NetworkState(
        timestamp=timestamp,
        topology=topology,
        flows=flows,
        metrics=metrics,
        anomalies=[]  # Simplified for testing
    )


@st.composite
def generate_corrupted_network_state(draw):
    """Generate a NetworkState with potential corruption issues."""
    base_state = draw(generate_network_state())
    
    corruption_type = draw(st.sampled_from([
        "missing_switches",
        "invalid_links", 
        "negative_metrics",
        "future_timestamp",
        "empty_topology"
    ]))
    
    if corruption_type == "missing_switches":
        # Remove all switches but keep links referencing them
        base_state.topology.switches = []
    elif corruption_type == "invalid_links":
        # Create links referencing non-existent switches
        base_state.topology.links = [
            Link(id="invalid_link", source_switch="nonexistent1", source_port=1,
                 destination_switch="nonexistent2", destination_port=1, bandwidth=1000, 
                 latency=1.0, status="active")
        ]
    elif corruption_type == "negative_metrics":
        # Set negative values in metrics
        base_state.metrics.bandwidth.utilization_percentage = -10.0
        base_state.metrics.latency.average_latency = -5.0
    elif corruption_type == "future_timestamp":
        # Set timestamp far in the future
        base_state.timestamp = datetime.now() + timedelta(days=365)
    elif corruption_type == "empty_topology":
        # Completely empty topology
        base_state.topology = Topology(switches=[], links=[], hosts=[])
    
    return base_state, corruption_type


class TestStateSync:
    """Test class for state synchronization properties."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cache = NetworkStateCache(default_ttl=300, max_entries=10)

    @given(generate_network_state())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_property_6_valid_state_storage_and_retrieval(self, valid_state):
        """
        **Feature: llm-integration-module, Property 6: State synchronization reliability**
        **Validates: Requirements 2.1, 2.2**
        
        For any valid NetworkState data received from RYU_Controller, 
        the LLM_Module should correctly store the data and make it available for retrieval.
        """
        # Store the valid state
        self.cache.update_state(valid_state)
        
        # Retrieve the state
        retrieved_state = self.cache.get_current_state()
        
        # Verify the state was stored and retrieved correctly
        assert retrieved_state is not None
        assert retrieved_state.timestamp == valid_state.timestamp
        assert len(retrieved_state.topology.switches) == len(valid_state.topology.switches)
        assert len(retrieved_state.topology.links) == len(valid_state.topology.links)
        assert len(retrieved_state.topology.hosts) == len(valid_state.topology.hosts)
        assert retrieved_state.metrics.bandwidth.utilization_percentage == valid_state.metrics.bandwidth.utilization_percentage

    @given(generate_corrupted_network_state())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_property_6_corrupted_state_handling(self, corrupted_data):
        """
        **Feature: llm-integration-module, Property 6: State synchronization reliability**
        **Validates: Requirements 2.1, 2.2**
        
        For any corrupted or incomplete NetworkState data received from RYU_Controller,
        the LLM_Module should properly handle the corruption with appropriate error signaling.
        """
        corrupted_state, corruption_type = corrupted_data
        
        # Attempt to store the corrupted state
        # The cache should still store it but log warnings about integrity issues
        self.cache.update_state(corrupted_state)
        
        # Verify the state is stored (cache is resilient)
        retrieved_state = self.cache.get_current_state()
        assert retrieved_state is not None
        
        # Verify data integrity validation detects issues
        validation_result = retrieved_state.validate_data_integrity()
        
        # For corrupted states, validation should report issues
        if corruption_type == "missing_switches":
            # Only invalid if there are flows referencing non-existent switches
            if len(corrupted_state.flows) > 0:
                assert not validation_result["is_valid"]
                assert len(validation_result["issues"]) > 0
        elif corruption_type in ["invalid_links", "negative_metrics"]:
            assert not validation_result["is_valid"]
            assert len(validation_result["issues"]) > 0
        elif corruption_type == "empty_topology":
            # Empty topology is valid if there are no flows
            if len(corrupted_state.flows) == 0:
                assert validation_result["is_valid"]
            else:
                assert not validation_result["is_valid"]
        
        # Future timestamps should be handled gracefully
        if corruption_type == "future_timestamp":
            # State should still be stored but marked as potentially problematic
            assert retrieved_state.timestamp == corrupted_state.timestamp

    @given(st.lists(generate_network_state(), min_size=2, max_size=5))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_property_6_state_update_sequence(self, state_sequence):
        """
        **Feature: llm-integration-module, Property 6: State synchronization reliability**
        **Validates: Requirements 2.1, 2.2**
        
        For any sequence of NetworkState updates from RYU_Controller,
        the LLM_Module should maintain the most recent valid state.
        """
        # Sort states by timestamp to ensure proper ordering
        sorted_states = sorted(state_sequence, key=lambda s: s.timestamp)
        
        # Update states in sequence
        for state in sorted_states:
            self.cache.update_state(state)
        
        # Verify the most recent state is current
        current_state = self.cache.get_current_state()
        assert current_state is not None
        
        # Should be the latest timestamp
        latest_state = sorted_states[-1]
        assert current_state.timestamp == latest_state.timestamp

    @given(generate_network_state(), st.integers(min_value=1, max_value=3600))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_property_6_ttl_expiration_handling(self, state, ttl_seconds):
        """
        **Feature: llm-integration-module, Property 6: State synchronization reliability**
        **Validates: Requirements 2.1, 2.2**
        
        For any NetworkState with TTL expiration, the LLM_Module should properly
        handle expired states and request updates when needed.
        """
        # Store state with specific TTL
        self.cache.update_state(state, ttl=ttl_seconds)
        
        # Verify state is initially available
        current_state = self.cache.get_current_state()
        assert current_state is not None
        
        # Check TTL behavior
        cache_entry = self.cache._current_state
        assert cache_entry is not None
        assert cache_entry.ttl_seconds == ttl_seconds
        
        # Verify expiration logic works
        if ttl_seconds < 60:  # For short TTLs, we can test expiration logic
            # Manually set cached_at to past time to simulate expiration
            cache_entry.cached_at = datetime.now() - timedelta(seconds=ttl_seconds + 1)
            
            # Now getting current state should return None due to expiration
            expired_state = self.cache.get_current_state()
            assert expired_state is None

    @given(generate_network_state())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_property_6_concurrent_access_safety(self, state):
        """
        **Feature: llm-integration-module, Property 6: State synchronization reliability**
        **Validates: Requirements 2.1, 2.2**
        
        For any NetworkState accessed concurrently, the LLM_Module should maintain
        thread safety and data consistency.
        """
        import threading
        import time
        
        # Store initial state
        self.cache.update_state(state)
        
        results = []
        errors = []
        
        def concurrent_access():
            try:
                # Multiple operations that should be thread-safe
                for _ in range(10):
                    retrieved_state = self.cache.get_current_state()
                    if retrieved_state:
                        results.append(retrieved_state.timestamp)
                    
                    # Small delay to increase chance of race conditions
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=concurrent_access)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred
        assert len(errors) == 0, f"Concurrent access errors: {errors}"
        
        # Verify all results are consistent (same timestamp)
        assert len(results) > 0
        assert all(ts == state.timestamp for ts in results)

    @given(st.lists(generate_network_state(), min_size=1, max_size=15))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_property_6_cache_capacity_management(self, state_list):
        """
        **Feature: llm-integration-module, Property 6: State synchronization reliability**
        **Validates: Requirements 2.1, 2.2**
        
        For any number of NetworkState updates exceeding cache capacity,
        the LLM_Module should properly manage cache size and maintain most recent states.
        """
        # Use a small cache for testing
        small_cache = NetworkStateCache(default_ttl=300, max_entries=5)
        
        # Add states beyond capacity
        for i, state in enumerate(state_list):
            # Modify timestamp to ensure uniqueness
            state.timestamp = datetime.now() + timedelta(seconds=i)
            small_cache.update_state(state)
        
        # Verify cache doesn't exceed capacity
        cache_stats = small_cache.get_cache_stats()
        assert cache_stats["total_entries"] <= 5
        
        # Verify current state is still available
        current_state = small_cache.get_current_state()
        assert current_state is not None
        
        # Should be the most recently added state
        if state_list:
            latest_state = state_list[-1]
            # Allow for small timestamp differences due to processing time
            time_diff = abs((current_state.timestamp - latest_state.timestamp).total_seconds())
            assert time_diff < 2  # Within 2 seconds

    @given(generate_network_state())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_property_6_state_freshness_validation(self, state):
        """
        **Feature: llm-integration-module, Property 6: State synchronization reliability**
        **Validates: Requirements 2.1, 2.2**
        
        For any NetworkState, the LLM_Module should correctly assess data freshness
        and request updates when data becomes stale.
        """
        # Test with fresh state (just cached)
        fresh_state = copy.deepcopy(state)
        fresh_state.timestamp = datetime.now() - timedelta(seconds=30)  # 30 seconds old
        
        self.cache.update_state(fresh_state)
        
        # Should be considered fresh (just cached)
        assert self.cache.is_state_fresh(max_age_seconds=60)
        assert self.cache.is_state_fresh(max_age_seconds=10)  # Cache entry is fresh even if NetworkState timestamp is old
        
        # Test with stale state by creating a cache entry with old cached_at time
        # We need to test actual cache staleness, not NetworkState timestamp
        import time
        
        # Cache a state, then simulate time passing
        old_state = copy.deepcopy(state)
        self.cache.update_state(old_state)
        
        # Manually modify the cache entry's cached_at time to simulate staleness
        if self.cache._current_state:
            # Make the cache entry appear old
            self.cache._current_state.cached_at = datetime.now() - timedelta(seconds=400)
        
        # Should not be considered fresh
        assert not self.cache.is_state_fresh(max_age_seconds=300)
        
        # Should trigger update request
        update_requested = self.cache.request_state_update()
        assert update_requested  # Should return True indicating request was made

    @given(generate_network_state())
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_property_6_state_integrity_preservation(self, original_state):
        """
        **Feature: llm-integration-module, Property 6: State synchronization reliability**
        **Validates: Requirements 2.1, 2.2**
        
        For any NetworkState stored and retrieved, the LLM_Module should preserve
        all data integrity without modification or corruption.
        """
        # Store the original state
        self.cache.update_state(original_state)
        
        # Retrieve the state
        retrieved_state = self.cache.get_current_state()
        
        assert retrieved_state is not None
        
        # Verify complete data integrity
        assert retrieved_state.timestamp == original_state.timestamp
        
        # Verify topology integrity
        assert len(retrieved_state.topology.switches) == len(original_state.topology.switches)
        assert len(retrieved_state.topology.links) == len(original_state.topology.links)
        assert len(retrieved_state.topology.hosts) == len(original_state.topology.hosts)
        
        # Verify switch details
        for orig_switch, retr_switch in zip(original_state.topology.switches, retrieved_state.topology.switches):
            assert orig_switch.id == retr_switch.id
            assert orig_switch.name == retr_switch.name
            assert orig_switch.dpid == retr_switch.dpid
            assert orig_switch.status == retr_switch.status
        
        # Verify metrics integrity
        assert retrieved_state.metrics.bandwidth.utilization_percentage == original_state.metrics.bandwidth.utilization_percentage
        assert retrieved_state.metrics.latency.average_latency == original_state.metrics.latency.average_latency
        assert retrieved_state.metrics.utilization.cpu_utilization == original_state.metrics.utilization.cpu_utilization
        
        # Verify flows integrity
        assert len(retrieved_state.flows) == len(original_state.flows)
        
        # The retrieved state should be a different object (not the same reference)
        # to prevent external modifications
        assert retrieved_state is not original_state

    def test_property_5_state_data_freshness_simple(self):
        """
        **Feature: llm-integration-module, Property 5: State data freshness**
        **Validates: Requirements 1.5, 2.3, 2.4**
        
        For any intent processing operation, the LLM_Module should use the most recent 
        NetworkState data available and request updates when data exceeds the configured age threshold.
        """
        # Create a simple network state for testing
        from src.models.network import NetworkState, Topology, Switch, NetworkMetrics, BandwidthMetrics, LatencyMetrics, UtilizationMetrics
        
        topology = Topology(
            switches=[Switch(id="sw1", name="Switch1", dpid="1", ports=[1, 2], status="active")],
            links=[],
            hosts=[]
        )
        
        metrics = NetworkMetrics(
            bandwidth=BandwidthMetrics(
                total_capacity=1000,
                used_bandwidth=300,
                available_bandwidth=700,
                utilization_percentage=30.0
            ),
            latency=LatencyMetrics(
                average_latency=2.5,
                min_latency=1.0,
                max_latency=5.0,
                jitter=0.5
            ),
            utilization=UtilizationMetrics(
                cpu_utilization=45.0,
                memory_utilization=60.0
            )
        )
        
        # Test with fresh state
        fresh_state = NetworkState(
            timestamp=datetime.now() - timedelta(seconds=60),  # 1 minute old
            topology=topology,
            flows=[],
            metrics=metrics,
            anomalies=[]
        )
        
        self.cache.update_state(fresh_state)
        
        # Verify state is considered fresh (within 5 minute threshold)
        assert self.cache.is_state_fresh(max_age_seconds=300)
        
        # Test with stale state by manipulating the cache entry directly
        stale_state = NetworkState(
            timestamp=datetime.now() - timedelta(seconds=600),  # 10 minutes old
            topology=topology,
            flows=[],
            metrics=metrics,
            anomalies=[]
        )
        
        self.cache.update_state(stale_state)
        
        # Manually set the cached_at time to simulate stale cache
        self.cache._current_state.cached_at = datetime.now() - timedelta(seconds=400)
        
        # Verify state is considered stale (exceeds 5 minute threshold)
        assert not self.cache.is_state_fresh(max_age_seconds=300)
        
        # Test that most recent state is used
        older_state = NetworkState(
            timestamp=datetime.now() - timedelta(seconds=600),
            topology=topology,
            flows=[],
            metrics=metrics,
            anomalies=[]
        )
        
        newer_state = NetworkState(
            timestamp=datetime.now() - timedelta(seconds=60),
            topology=topology,
            flows=[],
            metrics=metrics,
            anomalies=[]
        )
        
        # Add states in non-chronological order
        self.cache.update_state(older_state)
        self.cache.update_state(newer_state)
        
        # Should always get the most recent state
        current_state = self.cache.get_current_state()
        assert current_state is not None
        assert current_state.timestamp == newer_state.timestamp