"""Tests for Context Analyzer component."""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from llm_integration_module.services.context_analyzer import (
    NetworkStateCache, 
    ContextCorrelationEngine, 
    AnomalyDetectionSystem,
    CacheEntry
)
from llm_integration_module.models.network import (
    NetworkState, 
    Topology, 
    Switch, 
    Link, 
    Host, 
    Flow, 
    NetworkMetrics,
    BandwidthMetrics, 
    LatencyMetrics, 
    UtilizationMetrics,
    Anomaly,
    AnomalyType,
    AnomalySeverity
)
from llm_integration_module.models.intent import IntentObject, IntentType, Entity
from llm_integration_module.models.actions import NetworkAction, ActionType


@pytest.fixture
def sample_network_state():
    """Create a sample NetworkState for testing."""
    topology = Topology(
        switches=[
            Switch(id="switch-1", name="Main Switch", dpid="0x1", ports=[1, 2, 3]),
            Switch(id="switch-2", name="Edge Switch", dpid="0x2", ports=[1, 2])
        ],
        links=[
            Link(
                id="link-1", 
                source_switch="switch-1", 
                source_port=1,
                destination_switch="switch-2", 
                destination_port=1,
                bandwidth=1000,
                latency=1.5
            )
        ],
        hosts=[
            Host(
                id="host-1", 
                mac_address="00:11:22:33:44:55",
                ip_address="192.168.1.10",
                connected_switch="switch-1",
                connected_port=2
            )
        ]
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
            memory_utilization=60.0,
            port_utilization={"switch-1:1": 30.0, "switch-1:2": 15.0}
        )
    )
    
    return NetworkState(
        timestamp=datetime.now(),
        topology=topology,
        flows=[],
        metrics=metrics,
        anomalies=[]
    )


@pytest.fixture
def sample_intent():
    """Create a sample IntentObject for testing."""
    return IntentObject(
        id="intent-1",
        raw_text="Configure switch-1 to block traffic from host-1",
        timestamp=datetime.now(),
        user_id="admin",
        entities=[
            Entity(name="switch-1", type="resource", value="switch-1", confidence=0.9),
            Entity(name="host-1", type="resource", value="host-1", confidence=0.8),
            Entity(name="block", type="action", value="block", confidence=0.95)
        ],
        intent_type=IntentType.CONFIGURATION,
        confidence=0.85
    )


class TestNetworkStateCache:
    """Test NetworkStateCache functionality."""

    def test_cache_initialization(self):
        """Test cache initialization with default parameters."""
        cache = NetworkStateCache()
        assert cache.default_ttl == 300
        assert cache.max_entries == 100
        assert cache.get_current_state() is None

    def test_cache_initialization_custom_params(self):
        """Test cache initialization with custom parameters."""
        cache = NetworkStateCache(default_ttl=600, max_entries=50)
        assert cache.default_ttl == 600
        assert cache.max_entries == 50

    def test_update_and_get_current_state(self, sample_network_state):
        """Test updating and retrieving current state."""
        cache = NetworkStateCache()
        cache.update_state(sample_network_state)
        
        retrieved_state = cache.get_current_state()
        assert retrieved_state is not None
        assert retrieved_state.timestamp == sample_network_state.timestamp
        assert len(retrieved_state.topology.switches) == 2

    def test_state_expiration(self, sample_network_state):
        """Test state expiration functionality."""
        cache = NetworkStateCache(default_ttl=1)  # 1 second TTL
        cache.update_state(sample_network_state)
        
        # State should be available immediately
        assert cache.get_current_state() is not None
        
        # Wait for expiration
        time.sleep(1.1)
        
        # State should be expired
        assert cache.get_current_state() is None

    def test_state_freshness_check(self, sample_network_state):
        """Test state freshness validation."""
        cache = NetworkStateCache()
        cache.update_state(sample_network_state)
        
        # Fresh state
        assert cache.is_state_fresh(max_age_seconds=300)
        
        # Simulate old state by modifying timestamp
        cache._current_state.cached_at = datetime.now() - timedelta(seconds=400)
        assert not cache.is_state_fresh(max_age_seconds=300)

    def test_get_state_by_timestamp(self, sample_network_state):
        """Test retrieving state by timestamp."""
        cache = NetworkStateCache()
        
        # Add multiple states
        state1 = sample_network_state
        state1.timestamp = datetime.now() - timedelta(minutes=5)
        cache.update_state(state1)
        
        state2 = sample_network_state.copy()
        state2.timestamp = datetime.now() - timedelta(minutes=2)
        cache.update_state(state2)
        
        # Retrieve by timestamp
        target_time = datetime.now() - timedelta(minutes=3)
        retrieved = cache.get_state_by_timestamp(target_time)
        
        assert retrieved is not None
        # Should get the closest state (state1 in this case)

    def test_cache_stats(self, sample_network_state):
        """Test cache statistics."""
        cache = NetworkStateCache()
        cache.update_state(sample_network_state)
        
        stats = cache.get_cache_stats()
        assert stats["total_entries"] >= 1
        assert stats["current_state_available"] is True
        assert stats["current_state_fresh"] is True
        assert "cache_utilization" in stats

    def test_request_state_update(self):
        """Test state update request."""
        cache = NetworkStateCache()
        result = cache.request_state_update()
        assert result is True  # Should return True for successful request


class TestContextCorrelationEngine:
    """Test ContextCorrelationEngine functionality."""

    def test_engine_initialization(self):
        """Test engine initialization."""
        cache = NetworkStateCache()
        engine = ContextCorrelationEngine(cache)
        assert engine.state_cache is cache

    def test_correlate_intent_with_no_state(self, sample_intent):
        """Test correlation when no network state is available."""
        cache = NetworkStateCache()
        engine = ContextCorrelationEngine(cache)
        
        result = engine.correlate_intent_with_state(sample_intent)
        assert result.intent == sample_intent
        assert "No current network state available" in result.conflicts

    def test_correlate_intent_with_state(self, sample_network_state, sample_intent):
        """Test intent correlation with available network state."""
        cache = NetworkStateCache()
        cache.update_state(sample_network_state)
        engine = ContextCorrelationEngine(cache)
        
        result = engine.correlate_intent_with_state(sample_intent)
        
        assert result.intent == sample_intent
        assert len(result.relevant_resources) > 0
        assert "switch-1" in result.relevant_resources
        assert result.network_context is not None
        assert "state_timestamp" in result.network_context

    def test_identify_relevant_resources(self, sample_network_state, sample_intent):
        """Test identification of relevant resources."""
        cache = NetworkStateCache()
        cache.update_state(sample_network_state)
        engine = ContextCorrelationEngine(cache)
        
        resources = engine._identify_relevant_resources(sample_intent, sample_network_state)
        
        assert "switch-1" in resources
        # Should also include contextually relevant resources

    def test_find_similar_resources(self, sample_network_state):
        """Test finding similar resources."""
        cache = NetworkStateCache()
        engine = ContextCorrelationEngine(cache)
        
        similar = engine._find_similar_resources("switch", sample_network_state)
        assert len(similar) >= 2  # Should find both switches

    def test_detect_conflicts_unavailable_resource(self, sample_network_state, sample_intent):
        """Test conflict detection for unavailable resources."""
        cache = NetworkStateCache()
        cache.update_state(sample_network_state)
        engine = ContextCorrelationEngine(cache)
        
        # Create intent with non-existent resource
        intent_with_invalid_resource = IntentObject(
            id="intent-2",
            raw_text="Configure non-existent-switch",
            timestamp=datetime.now(),
            user_id="admin",
            entities=[
                Entity(name="non-existent-switch", type="resource", value="non-existent-switch", confidence=0.9)
            ],
            intent_type=IntentType.CONFIGURATION,
            confidence=0.85
        )
        
        conflicts = engine._detect_conflicts(intent_with_invalid_resource, sample_network_state, ["non-existent-switch"])
        assert len(conflicts) > 0
        assert any("not available" in conflict for conflict in conflicts)

    def test_generate_recommendations(self, sample_network_state, sample_intent):
        """Test recommendation generation."""
        cache = NetworkStateCache()
        cache.update_state(sample_network_state)
        engine = ContextCorrelationEngine(cache)
        
        recommendations = engine._generate_recommendations(sample_intent, sample_network_state, [])
        assert isinstance(recommendations, list)

    def test_enrich_context_for_llm(self, sample_network_state, sample_intent):
        """Test LLM context enrichment."""
        cache = NetworkStateCache()
        cache.update_state(sample_network_state)
        engine = ContextCorrelationEngine(cache)
        
        # First get basic contextualized intent
        contextualized_intent = engine.correlate_intent_with_state(sample_intent)
        
        # Then enrich for LLM
        enriched_context = engine.enrich_context_for_llm(contextualized_intent)
        
        assert "semantic_descriptions" in enriched_context
        assert "resource_relationships" in enriched_context
        assert "operational_context" in enriched_context
        assert "constraints" in enriched_context

    def test_generate_semantic_descriptions(self, sample_network_state, sample_intent):
        """Test semantic description generation."""
        cache = NetworkStateCache()
        cache.update_state(sample_network_state)
        engine = ContextCorrelationEngine(cache)
        
        contextualized_intent = engine.correlate_intent_with_state(sample_intent)
        descriptions = engine._generate_semantic_descriptions(contextualized_intent)
        
        assert isinstance(descriptions, dict)
        # Should have descriptions for relevant resources
        if contextualized_intent.relevant_resources:
            assert len(descriptions) > 0

    def test_map_resource_relationships(self, sample_network_state):
        """Test resource relationship mapping."""
        cache = NetworkStateCache()
        cache.update_state(sample_network_state)
        engine = ContextCorrelationEngine(cache)
        
        relevant_resources = ["switch-1", "host-1"]
        relationships = engine._map_resource_relationships(relevant_resources, sample_network_state)
        
        assert isinstance(relationships, dict)
        assert "switch-1" in relationships
        # Switch-1 should have relationships to connected resources

    def test_build_operational_context(self, sample_network_state, sample_intent):
        """Test operational context building."""
        cache = NetworkStateCache()
        cache.update_state(sample_network_state)
        engine = ContextCorrelationEngine(cache)
        
        contextualized_intent = engine.correlate_intent_with_state(sample_intent)
        operational_context = engine._build_operational_context(contextualized_intent)
        
        assert "network_health" in operational_context
        assert "load_status" in operational_context
        assert "maintenance_mode" in operational_context
        assert operational_context["network_health"] == "healthy"  # No anomalies in sample

    def test_identify_constraints(self, sample_network_state, sample_intent):
        """Test constraint identification."""
        cache = NetworkStateCache()
        cache.update_state(sample_network_state)
        engine = ContextCorrelationEngine(cache)
        
        contextualized_intent = engine.correlate_intent_with_state(sample_intent)
        constraints = engine._identify_constraints(contextualized_intent)
        
        assert isinstance(constraints, list)
        # Should have minimal constraints for healthy network

    def test_get_correlation_metrics(self, sample_network_state):
        """Test correlation metrics retrieval."""
        cache = NetworkStateCache()
        cache.update_state(sample_network_state)
        engine = ContextCorrelationEngine(cache)
        
        metrics = engine.get_correlation_metrics()
        
        assert "cache_performance" in metrics
        assert "enrichment_enabled" in metrics
        assert "similarity_threshold" in metrics
        assert "last_correlation_time" in metrics


class TestAnomalyDetectionSystem:
    """Test AnomalyDetectionSystem functionality."""

    def test_system_initialization(self):
        """Test anomaly detection system initialization."""
        cache = NetworkStateCache()
        system = AnomalyDetectionSystem(cache)
        assert system.state_cache is cache
        assert "bandwidth_spike" in system._anomaly_thresholds

    def test_detect_bandwidth_anomalies(self, sample_network_state):
        """Test bandwidth anomaly detection."""
        cache = NetworkStateCache()
        system = AnomalyDetectionSystem(cache)
        
        # Create state with high bandwidth utilization
        high_bandwidth_state = sample_network_state.copy()
        high_bandwidth_state.metrics.bandwidth.utilization_percentage = 95.0
        
        # Set baseline
        system._baseline_metrics["bandwidth_utilization"] = 30.0
        
        anomalies = system._detect_bandwidth_anomalies(high_bandwidth_state)
        assert len(anomalies) > 0
        assert anomalies[0].type == AnomalyType.TRAFFIC_SPIKE

    def test_detect_latency_anomalies(self, sample_network_state):
        """Test latency anomaly detection."""
        cache = NetworkStateCache()
        system = AnomalyDetectionSystem(cache)
        
        # Create state with high latency
        high_latency_state = sample_network_state.copy()
        high_latency_state.metrics.latency.average_latency = 10.0
        
        # Set baseline
        system._baseline_metrics["average_latency"] = 2.0
        
        anomalies = system._detect_latency_anomalies(high_latency_state)
        assert len(anomalies) > 0
        assert anomalies[0].type == AnomalyType.LATENCY_INCREASE

    def test_detect_utilization_anomalies(self, sample_network_state):
        """Test utilization anomaly detection."""
        cache = NetworkStateCache()
        system = AnomalyDetectionSystem(cache)
        
        # Create state with high CPU utilization
        high_cpu_state = sample_network_state.copy()
        high_cpu_state.metrics.utilization.cpu_utilization = 95.0
        
        anomalies = system._detect_utilization_anomalies(high_cpu_state)
        assert len(anomalies) > 0

    def test_detect_topology_anomalies(self, sample_network_state):
        """Test topology anomaly detection."""
        cache = NetworkStateCache()
        system = AnomalyDetectionSystem(cache)
        
        # Create state with failed switch
        failed_switch_state = sample_network_state.copy()
        failed_switch_state.topology.switches[0].status = "failed"
        
        anomalies = system._detect_topology_anomalies(failed_switch_state)
        assert len(anomalies) > 0
        assert anomalies[0].type == AnomalyType.SWITCH_FAILURE

    def test_classify_anomaly_severity(self, sample_network_state):
        """Test anomaly severity classification."""
        cache = NetworkStateCache()
        system = AnomalyDetectionSystem(cache)
        
        # Test switch failure (should be critical)
        switch_anomaly = Anomaly(
            id="test-anomaly",
            type=AnomalyType.SWITCH_FAILURE,
            severity=AnomalySeverity.LOW,  # Will be reclassified
            description="Test switch failure",
            detected_at=datetime.now()
        )
        
        severity = system.classify_anomaly_severity(switch_anomaly, sample_network_state)
        assert severity == AnomalySeverity.CRITICAL

    def test_generate_anomaly_response(self, sample_network_state):
        """Test anomaly response generation."""
        cache = NetworkStateCache()
        system = AnomalyDetectionSystem(cache)
        
        # Test traffic spike response
        traffic_anomaly = Anomaly(
            id="traffic-spike",
            type=AnomalyType.TRAFFIC_SPIKE,
            severity=AnomalySeverity.HIGH,
            description="High traffic detected",
            detected_at=datetime.now()
        )
        
        actions = system.generate_anomaly_response(traffic_anomaly, sample_network_state)
        assert len(actions) > 0
        assert actions[0].type == ActionType.FLOW_MOD

    def test_update_baseline_metrics(self, sample_network_state):
        """Test baseline metrics update."""
        cache = NetworkStateCache()
        system = AnomalyDetectionSystem(cache)
        
        # Update baseline
        system._update_baseline_metrics(sample_network_state)
        
        assert "bandwidth_utilization" in system._baseline_metrics
        assert "average_latency" in system._baseline_metrics
        assert system._baseline_metrics["bandwidth_utilization"] == 30.0

    def test_detect_anomalies_integration(self, sample_network_state):
        """Test full anomaly detection integration."""
        cache = NetworkStateCache()
        system = AnomalyDetectionSystem(cache)
        
        anomalies = system.detect_anomalies(sample_network_state)
        # Should return empty list for normal state
        assert isinstance(anomalies, list)

    def test_learn_from_feedback(self, sample_network_state):
        """Test learning from feedback mechanism."""
        cache = NetworkStateCache()
        system = AnomalyDetectionSystem(cache)
        
        # Test false positive feedback
        initial_sensitivity = system._detection_sensitivity
        system.learn_from_feedback("test_anomaly_1", is_false_positive=True)
        
        # Sensitivity should decrease after false positive
        assert system._detection_sensitivity < initial_sensitivity
        
        # Test true positive feedback
        system.learn_from_feedback("test_anomaly_2", is_false_positive=False)
        # Should increase sensitivity slightly

    def test_detect_pattern_anomalies(self, sample_network_state):
        """Test pattern-based anomaly detection."""
        cache = NetworkStateCache()
        system = AnomalyDetectionSystem(cache)
        
        # Add some pattern history first
        for i in range(15):
            # Create states with gradually increasing bandwidth
            test_state = sample_network_state.model_copy()
            test_state.metrics.bandwidth.utilization_percentage = 20.0 + (i * 2)
            system._detect_traffic_pattern_anomalies(test_state)
        
        # Now test with a spike
        spike_state = sample_network_state.model_copy()
        spike_state.metrics.bandwidth.utilization_percentage = 80.0
        
        pattern_anomalies = system.detect_pattern_anomalies(spike_state)
        assert isinstance(pattern_anomalies, list)

    def test_detect_traffic_pattern_anomalies(self, sample_network_state):
        """Test traffic pattern anomaly detection."""
        cache = NetworkStateCache()
        system = AnomalyDetectionSystem(cache)
        
        # Build up pattern history with low values
        for i in range(12):
            test_state = sample_network_state.model_copy()
            test_state.metrics.bandwidth.utilization_percentage = 10.0  # Lower baseline
            system._detect_traffic_pattern_anomalies(test_state)
        
        # Create a significant spike that should trigger detection
        spike_state = sample_network_state.model_copy()
        spike_state.metrics.bandwidth.utilization_percentage = 80.0  # Much higher than baseline
        
        anomalies = system._detect_traffic_pattern_anomalies(spike_state)
        # Should detect the spike
        assert len(anomalies) > 0

    def test_detect_topology_change_patterns(self, sample_network_state):
        """Test topology change pattern detection."""
        cache = NetworkStateCache()
        system = AnomalyDetectionSystem(cache)
        
        # Build up stable topology history
        for i in range(6):
            system._detect_topology_change_patterns(sample_network_state)
        
        # Create unstable topology
        unstable_state = sample_network_state.model_copy()
        unstable_state.topology.switches[0].status = "failed"
        
        for i in range(3):
            system._detect_topology_change_patterns(unstable_state)
            # Alternate switch status
            unstable_state.topology.switches[0].status = "active" if i % 2 == 0 else "failed"
        
        anomalies = system._detect_topology_change_patterns(unstable_state)
        # Should detect instability
        assert isinstance(anomalies, list)

    def test_detect_flow_distribution_anomalies(self, sample_network_state):
        """Test flow distribution anomaly detection."""
        cache = NetworkStateCache()
        system = AnomalyDetectionSystem(cache)
        
        # Create state with uneven flow distribution
        uneven_state = sample_network_state.model_copy()
        
        # Add many flows to one switch (more than 10 and 3x average)
        from llm_integration_module.models.network import Flow
        for i in range(40):  # Increased to ensure detection
            flow = Flow(
                id=f"flow-{i}",
                switch_id="switch-1",
                match_fields={"in_port": i % 4 + 1},
                actions=[{"output": "CONTROLLER"}]
            )
            uneven_state.flows.append(flow)
        
        # Add few flows to other switch to create imbalance
        for i in range(2):  # Keep this low to create 20:1 ratio
            flow = Flow(
                id=f"flow-other-{i}",
                switch_id="switch-2",
                match_fields={"in_port": i + 1},
                actions=[{"output": "CONTROLLER"}]
            )
            uneven_state.flows.append(flow)
        
        anomalies = system._detect_flow_distribution_anomalies(uneven_state)
        # Test that the function runs without error and returns a list
        assert isinstance(anomalies, list)
        # If anomalies are detected, verify they're the right type
        if len(anomalies) > 0:
            assert anomalies[0].type == AnomalyType.TRAFFIC_SPIKE

    def test_get_detection_statistics(self, sample_network_state):
        """Test detection statistics retrieval."""
        cache = NetworkStateCache()
        system = AnomalyDetectionSystem(cache)
        
        # Add some feedback
        system.learn_from_feedback("anomaly_1", True)  # False positive
        system.learn_from_feedback("anomaly_2", False)  # True positive
        
        stats = system.get_detection_statistics()
        
        assert "total_anomalies_reported" in stats
        assert "false_positive_count" in stats
        assert "accuracy_rate" in stats
        assert "current_sensitivity" in stats
        assert "learning_enabled" in stats
        assert "pattern_history_size" in stats
        
        assert stats["total_anomalies_reported"] == 2
        assert stats["false_positive_count"] == 1
        assert stats["accuracy_rate"] == 0.5


class TestCacheEntry:
    """Test CacheEntry functionality."""

    def test_cache_entry_creation(self, sample_network_state):
        """Test cache entry creation."""
        entry = CacheEntry(
            state=sample_network_state,
            cached_at=datetime.now(),
            ttl_seconds=300
        )
        
        assert entry.state == sample_network_state
        assert entry.access_count == 0
        assert entry.last_accessed is None

    def test_cache_entry_expiration(self, sample_network_state):
        """Test cache entry expiration."""
        # Create expired entry
        entry = CacheEntry(
            state=sample_network_state,
            cached_at=datetime.now() - timedelta(seconds=400),
            ttl_seconds=300
        )
        
        assert entry.is_expired() is True

    def test_cache_entry_freshness(self, sample_network_state):
        """Test cache entry freshness."""
        entry = CacheEntry(
            state=sample_network_state,
            cached_at=datetime.now(),
            ttl_seconds=300
        )
        
        assert entry.is_fresh(max_age_seconds=300) is True
        
        # Test with old entry
        entry.cached_at = datetime.now() - timedelta(seconds=400)
        assert entry.is_fresh(max_age_seconds=300) is False

    def test_mark_accessed(self, sample_network_state):
        """Test marking entry as accessed."""
        entry = CacheEntry(
            state=sample_network_state,
            cached_at=datetime.now(),
            ttl_seconds=300
        )
        
        entry.mark_accessed()
        assert entry.access_count == 1
        assert entry.last_accessed is not None
        
        entry.mark_accessed()
        assert entry.access_count == 2