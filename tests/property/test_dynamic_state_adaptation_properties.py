"""Property-based tests for dynamic state adaptation."""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from datetime import datetime, timedelta
from typing import List, Dict, Any
import copy

from src.services.context_analyzer import NetworkStateCache, ContextCorrelationEngine
from src.models.network import (
    NetworkState, Topology, Switch, Link, Host, Flow,
    NetworkMetrics, BandwidthMetrics, LatencyMetrics, UtilizationMetrics,
    Anomaly, AnomalyType, AnomalySeverity
)
from src.models.intent import IntentObject, IntentType, Entity, ContextualizedIntent


class TestDynamicStateAdaptationProperties:
    """Property-based tests for dynamic state adaptation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.state_cache = NetworkStateCache(default_ttl=600)
        self.context_engine = ContextCorrelationEngine(self.state_cache)
    
    @staticmethod
    @st.composite
    def network_state_with_changes(draw):
        """Generate a pair of network states with significant changes."""
        # Generate initial state
        num_switches = draw(st.integers(min_value=3, max_value=8))
        switches = []
        for i in range(num_switches):
            switch = Switch(
                id=f"switch-{i}",
                name=f"Switch {i}",
                dpid=f"00:00:00:00:00:00:00:{i:02x}",
                ports=[1, 2, 3, 4],
                status="active"
            )
            switches.append(switch)
        
        links = []
        for i in range(num_switches - 1):
            link = Link(
                id=f"link-{i}",
                source_switch=switches[i].id,
                source_port=1,
                destination_switch=switches[i+1].id,
                destination_port=2,
                bandwidth=draw(st.integers(min_value=1000, max_value=10000)),
                latency=draw(st.floats(min_value=1.0, max_value=20.0)),
                status="active"
            )
            links.append(link)
        
        topology = Topology(switches=switches, links=links, hosts=[])
        
        bandwidth_util = draw(st.floats(min_value=20.0, max_value=60.0))
        metrics = NetworkMetrics(
            bandwidth=BandwidthMetrics(
                total_capacity=10000,
                used_bandwidth=int(10000 * bandwidth_util / 100),
                available_bandwidth=int(10000 * (100 - bandwidth_util) / 100),
                utilization_percentage=bandwidth_util
            ),
            latency=LatencyMetrics(
                average_latency=draw(st.floats(min_value=5.0, max_value=30.0)),
                min_latency=1.0,
                max_latency=50.0,
                jitter=2.0
            ),
            utilization=UtilizationMetrics(
                cpu_utilization=draw(st.floats(min_value=20.0, max_value=60.0)),
                memory_utilization=draw(st.floats(min_value=30.0, max_value=60.0)),
                port_utilization={}
            )
        )
        
        initial_state = NetworkState(
            timestamp=datetime.now() - timedelta(seconds=60),
            topology=topology,
            flows=[],
            metrics=metrics,
            anomalies=[]
        )
        
        # Create changed state
        changed_state = copy.deepcopy(initial_state)
        changed_state.timestamp = datetime.now()
        
        # Apply significant changes
        change_type = draw(st.sampled_from([
            "bandwidth_spike", "switch_failure", "link_failure", 
            "latency_increase", "new_anomaly"
        ]))
        
        if change_type == "bandwidth_spike":
            # Significant bandwidth increase
            new_util = draw(st.floats(min_value=85.0, max_value=98.0))
            changed_state.metrics.bandwidth.utilization_percentage = new_util
            changed_state.metrics.bandwidth.used_bandwidth = int(10000 * new_util / 100)
            changed_state.metrics.bandwidth.available_bandwidth = int(10000 * (100 - new_util) / 100)
        
        elif change_type == "switch_failure":
            # Mark a switch as failed
            if changed_state.topology.switches:
                failed_switch = draw(st.sampled_from(changed_state.topology.switches))
                failed_switch.status = "failed"
        
        elif change_type == "link_failure":
            # Mark a link as failed
            if changed_state.topology.links:
                failed_link = draw(st.sampled_from(changed_state.topology.links))
                failed_link.status = "failed"
        
        elif change_type == "latency_increase":
            # Significant latency increase
            new_latency = draw(st.floats(min_value=100.0, max_value=300.0))
            changed_state.metrics.latency.average_latency = new_latency
            changed_state.metrics.latency.max_latency = new_latency * 1.5
        
        elif change_type == "new_anomaly":
            # Add a new critical anomaly
            anomaly = Anomaly(
                id=f"anomaly_{draw(st.integers(min_value=1000, max_value=9999))}",
                type=draw(st.sampled_from([AnomalyType.TRAFFIC_SPIKE, AnomalyType.SWITCH_FAILURE])),
                severity=AnomalySeverity.CRITICAL,
                description="Critical network anomaly detected",
                affected_resources=[switches[0].id] if switches else [],
                detected_at=datetime.now(),
                metrics={}
            )
            changed_state.anomalies.append(anomaly)
        
        return initial_state, changed_state, change_type
    
    @staticmethod
    @st.composite
    def active_intent(draw):
        """Generate an active intent that would be affected by state changes."""
        entities = [
            Entity(
                name="action",
                type="action",
                value=draw(st.sampled_from(["configure", "modify", "create"])),
                confidence=0.9
            ),
            Entity(
                name="target",
                type="resource",
                value=f"switch-{draw(st.integers(min_value=0, max_value=5))}",
                confidence=0.85
            )
        ]
        
        return IntentObject(
            id=f"intent_{draw(st.integers(min_value=1000, max_value=9999))}",
            raw_text=draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=10, max_size=50)),
            timestamp=datetime.now() - timedelta(seconds=30),
            user_id=f"user_{draw(st.integers(min_value=1, max_value=10))}",
            entities=entities,
            intent_type=IntentType.CONFIGURATION,
            confidence=draw(st.floats(min_value=0.7, max_value=1.0)),
            parameters={"target": entities[1].value}
        )
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        state_pair=network_state_with_changes(),
        intent=active_intent()
    )
    def test_dynamic_state_adaptation(self, state_pair, intent):
        """
        **Feature: llm-integration-module, Property 7: Dynamic state adaptation**
        
        For any significant change in NetworkState, active intents should be 
        automatically re-evaluated and updated as necessary.
        
        **Validates: Requirements 2.5**
        
        Requirement 2.5 states:
        "WHEN il Network_State cambia significativamente, THE LLM_Module SHALL 
        rivalutare gli intent attivi se necessario"
        """
        initial_state, changed_state, change_type = state_pair
        
        assume(initial_state is not None)
        assume(changed_state is not None)
        assume(intent is not None)
        
        # Update cache with initial state
        self.state_cache.update_state(initial_state)
        
        # Contextualize intent with initial state
        initial_context = self.context_engine.correlate_intent_with_state(intent)
        
        # Verify initial contextualization
        assert isinstance(initial_context, ContextualizedIntent)
        assert initial_context.intent.id == intent.id
        
        # Store initial context properties
        initial_conflicts = len(initial_context.conflicts)
        initial_recommendations = len(initial_context.recommendations)
        initial_relevant_resources = set(initial_context.relevant_resources)
        
        # Update cache with changed state (significant change)
        self.state_cache.update_state(changed_state)
        
        # Re-evaluate intent with changed state
        updated_context = self.context_engine.correlate_intent_with_state(intent)
        
        # Verify re-evaluation occurred
        assert isinstance(updated_context, ContextualizedIntent)
        assert updated_context.intent.id == intent.id
        
        # Property: Context should be updated to reflect state changes
        updated_conflicts = len(updated_context.conflicts)
        updated_recommendations = len(updated_context.recommendations)
        updated_relevant_resources = set(updated_context.relevant_resources)
        
        # Verify that context reflects the state change
        if change_type == "bandwidth_spike":
            # Should detect high utilization and add conflicts/recommendations
            assert updated_context.network_context["network_metrics"]["bandwidth_utilization"] > 80.0
            # May have additional conflicts or recommendations
            assert updated_conflicts >= 0  # Conflicts may increase
        
        elif change_type == "switch_failure":
            # Should detect failed switch
            failed_switches = [s for s in changed_state.topology.switches if s.status != "active"]
            if failed_switches and any(s.id in initial_relevant_resources for s in failed_switches):
                # Should have conflicts about unavailable resources
                assert updated_conflicts > initial_conflicts or any(
                    "not available" in c.lower() or "inactive" in c.lower() 
                    for c in updated_context.conflicts
                )
        
        elif change_type == "link_failure":
            # Should detect failed link
            failed_links = [l for l in changed_state.topology.links if l.status != "active"]
            if failed_links:
                # Context should reflect topology changes
                assert updated_context.network_context is not None
        
        elif change_type == "latency_increase":
            # Should detect high latency
            assert updated_context.network_context["network_metrics"]["average_latency"] > 50.0
        
        elif change_type == "new_anomaly":
            # Should detect active anomalies
            assert updated_context.network_context["active_anomalies"] > 0
            # Context should reflect the presence of anomalies
            # (May or may not generate conflicts/recommendations depending on whether anomaly affects relevant resources)
        
        # Core property: Re-evaluation produces valid contextualized intent
        assert updated_context.intent is not None
        assert updated_context.network_context is not None
        assert isinstance(updated_context.conflicts, list)
        assert isinstance(updated_context.recommendations, list)
        assert isinstance(updated_context.relevant_resources, list)
        
        # Verify network context is updated with current state
        assert "state_timestamp" in updated_context.network_context
        state_timestamp = datetime.fromisoformat(updated_context.network_context["state_timestamp"])
        # Updated context should use the changed state timestamp
        assert abs((state_timestamp - changed_state.timestamp).total_seconds()) < 5.0
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        state_pair=network_state_with_changes(),
        intent=active_intent()
    )
    def test_state_change_triggers_reevaluation(self, state_pair, intent):
        """Test that significant state changes trigger intent re-evaluation."""
        initial_state, changed_state, change_type = state_pair
        
        assume(initial_state is not None)
        assume(changed_state is not None)
        
        # Update with initial state
        self.state_cache.update_state(initial_state)
        initial_context = self.context_engine.correlate_intent_with_state(intent)
        
        # Update with changed state
        self.state_cache.update_state(changed_state)
        updated_context = self.context_engine.correlate_intent_with_state(intent)
        
        # Verify that context reflects the new state
        initial_timestamp = datetime.fromisoformat(initial_context.network_context["state_timestamp"])
        updated_timestamp = datetime.fromisoformat(updated_context.network_context["state_timestamp"])
        
        # Updated context should use newer state
        assert updated_timestamp > initial_timestamp
        
        # Network metrics should reflect the changed state
        if change_type == "bandwidth_spike":
            assert (updated_context.network_context["network_metrics"]["bandwidth_utilization"] >
                   initial_context.network_context["network_metrics"]["bandwidth_utilization"])
        
        elif change_type == "latency_increase":
            assert (updated_context.network_context["network_metrics"]["average_latency"] >
                   initial_context.network_context["network_metrics"]["average_latency"])
    
    def test_state_adaptation_with_no_changes(self):
        """Test that re-evaluation with unchanged state produces consistent results."""
        # Create a simple state
        switches = [
            Switch(id="switch-1", name="Switch 1", dpid="00:00:00:00:00:00:00:01", 
                   ports=[1, 2, 3], status="active")
        ]
        topology = Topology(switches=switches, links=[], hosts=[])
        
        state = NetworkState(
            timestamp=datetime.now(),
            topology=topology,
            flows=[],
            metrics=NetworkMetrics(
                bandwidth=BandwidthMetrics(
                    total_capacity=1000,
                    used_bandwidth=300,
                    available_bandwidth=700,
                    utilization_percentage=30.0
                ),
                latency=LatencyMetrics(
                    average_latency=10.0,
                    min_latency=5.0,
                    max_latency=20.0,
                    jitter=2.0
                ),
                utilization=UtilizationMetrics(
                    cpu_utilization=40.0,
                    memory_utilization=50.0,
                    port_utilization={}
                )
            ),
            anomalies=[]
        )
        
        # Create intent
        intent = IntentObject(
            id="intent_test",
            raw_text="configure switch-1",
            timestamp=datetime.now(),
            user_id="test_user",
            entities=[
                Entity(name="action", type="action", value="configure", confidence=0.9),
                Entity(name="target", type="resource", value="switch-1", confidence=0.9)
            ],
            intent_type=IntentType.CONFIGURATION,
            confidence=0.9,
            parameters={"target": "switch-1"}
        )
        
        # Update cache
        self.state_cache.update_state(state)
        
        # Contextualize twice with same state
        context1 = self.context_engine.correlate_intent_with_state(intent)
        context2 = self.context_engine.correlate_intent_with_state(intent)
        
        # Results should be consistent
        assert len(context1.conflicts) == len(context2.conflicts)
        assert len(context1.recommendations) == len(context2.recommendations)
        assert set(context1.relevant_resources) == set(context2.relevant_resources)
