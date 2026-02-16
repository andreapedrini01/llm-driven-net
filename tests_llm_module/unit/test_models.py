"""Basic tests for data models."""

import pytest
from datetime import datetime
from src.models import (
    IntentObject, IntentType, Entity,
    NetworkState, Topology, NetworkMetrics,
    BandwidthMetrics, LatencyMetrics, UtilizationMetrics,
    NetworkAction, ActionType, ActionSequence
)


class TestIntentModels:
    """Test intent-related models."""
    
    def test_intent_object_creation(self):
        """Test creating an IntentObject."""
        intent = IntentObject(
            id="test-intent-1",
            raw_text="Create a new network slice for tenant A",
            timestamp=datetime.now(),
            user_id="user123",
            intent_type=IntentType.CONFIGURATION,
            confidence=0.85
        )
        
        assert intent.id == "test-intent-1"
        assert intent.intent_type == IntentType.CONFIGURATION
        assert intent.confidence == 0.85
        assert len(intent.entities) == 0
        assert len(intent.parameters) == 0
    
    def test_entity_creation(self):
        """Test creating an Entity."""
        entity = Entity(
            name="tenant",
            type="identifier",
            value="tenant_a",
            confidence=0.9
        )
        
        assert entity.name == "tenant"
        assert entity.type == "identifier"
        assert entity.value == "tenant_a"
        assert entity.confidence == 0.9


class TestNetworkModels:
    """Test network-related models."""
    
    def test_network_metrics_creation(self):
        """Test creating NetworkMetrics."""
        bandwidth = BandwidthMetrics(
            total_capacity=1000,
            used_bandwidth=300,
            available_bandwidth=700,
            utilization_percentage=30.0
        )
        
        latency = LatencyMetrics(
            average_latency=5.2,
            min_latency=1.0,
            max_latency=15.0,
            jitter=2.1
        )
        
        utilization = UtilizationMetrics(
            cpu_utilization=45.0,
            memory_utilization=60.0
        )
        
        metrics = NetworkMetrics(
            bandwidth=bandwidth,
            latency=latency,
            utilization=utilization
        )
        
        assert metrics.bandwidth.utilization_percentage == 30.0
        assert metrics.latency.average_latency == 5.2
        assert metrics.utilization.cpu_utilization == 45.0
    
    def test_network_state_creation(self):
        """Test creating a NetworkState."""
        topology = Topology()
        
        bandwidth = BandwidthMetrics(
            total_capacity=1000,
            used_bandwidth=300,
            available_bandwidth=700,
            utilization_percentage=30.0
        )
        
        latency = LatencyMetrics(
            average_latency=5.2,
            min_latency=1.0,
            max_latency=15.0,
            jitter=2.1
        )
        
        utilization = UtilizationMetrics(
            cpu_utilization=45.0,
            memory_utilization=60.0
        )
        
        metrics = NetworkMetrics(
            bandwidth=bandwidth,
            latency=latency,
            utilization=utilization
        )
        
        state = NetworkState(
            timestamp=datetime.now(),
            topology=topology,
            metrics=metrics
        )
        
        assert len(state.flows) == 0
        assert len(state.anomalies) == 0
        assert state.metrics.bandwidth.utilization_percentage == 30.0


class TestActionModels:
    """Test action-related models."""
    
    def test_network_action_creation(self):
        """Test creating a NetworkAction."""
        action = NetworkAction(
            id="action-1",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={"match": {"in_port": 1}, "actions": [{"output": 2}]},
            priority=1000,
            timeout=30
        )
        
        assert action.id == "action-1"
        assert action.type == ActionType.FLOW_MOD
        assert action.target == "switch-1"
        assert action.priority == 1000
        assert "match" in action.parameters
    
    def test_action_sequence_creation(self):
        """Test creating an ActionSequence."""
        action1 = NetworkAction(
            id="action-1",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={}
        )
        
        action2 = NetworkAction(
            id="action-2",
            type=ActionType.CONFIG_CHANGE,
            target="switch-2",
            parameters={}
        )
        
        sequence = ActionSequence(
            id="sequence-1",
            intent_id="intent-1",
            actions=[action1, action2],
            estimated_duration=60
        )
        
        assert sequence.id == "sequence-1"
        assert sequence.intent_id == "intent-1"
        assert len(sequence.actions) == 2
        assert sequence.estimated_duration == 60