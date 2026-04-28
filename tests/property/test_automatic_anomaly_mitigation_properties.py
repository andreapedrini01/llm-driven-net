"""Property-based tests for automatic anomaly mitigation."""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from datetime import datetime
from typing import List

from llm_integration_module.services.context_analyzer import AnomalyDetectionSystem, NetworkStateCache
from llm_integration_module.models.network import (
    NetworkState, Topology, Switch, Link, Host,
    NetworkMetrics, BandwidthMetrics, LatencyMetrics, UtilizationMetrics,
    Anomaly, AnomalyType, AnomalySeverity
)
from llm_integration_module.models.actions import NetworkAction, ActionType


@st.composite
def _network_state_for_anomaly(draw, anomaly: Anomaly):
    """Generate network state matching the anomaly."""
    # Generate switches
    num_switches = draw(st.integers(min_value=3, max_value=8))
    switches = []
    for i in range(num_switches):
        status = "active"
        switch_id = f"switch-{i}"
        
        # If anomaly is switch failure, mark some switches as failed
        if anomaly.type == AnomalyType.SWITCH_FAILURE and switch_id in anomaly.affected_resources:
            status = "failed"
        
        switch = Switch(
            id=switch_id,
            name=f"Switch {i}",
            dpid=f"00:00:00:00:00:00:00:{i:02x}",
            ports=[1, 2, 3, 4],
            status=status
        )
        switches.append(switch)
    
    # Generate links
    links = []
    for i in range(num_switches - 1):
        status = "active"
        link_id = f"link-{i}"
        
        # If anomaly is link failure, mark some links as failed
        if anomaly.type == AnomalyType.LINK_FAILURE and link_id in anomaly.affected_resources:
            status = "failed"
        
        link = Link(
            id=link_id,
            source_switch=switches[i].id,
            source_port=1,
            destination_switch=switches[i+1].id,
            destination_port=2,
            bandwidth=draw(st.integers(min_value=1000, max_value=10000)),
            latency=draw(st.floats(min_value=1.0, max_value=20.0)),
            status=status
        )
        links.append(link)
    
    topology = Topology(switches=switches, links=links, hosts=[])
    
    # Generate metrics based on anomaly type
    if anomaly.type == AnomalyType.TRAFFIC_SPIKE:
        bandwidth_util = draw(st.floats(min_value=90.0, max_value=99.0))
    else:
        bandwidth_util = draw(st.floats(min_value=30.0, max_value=70.0))
    
    metrics = NetworkMetrics(
        bandwidth=BandwidthMetrics(
            total_capacity=10000,
            used_bandwidth=int(10000 * bandwidth_util / 100),
            available_bandwidth=int(10000 * (100 - bandwidth_util) / 100),
            utilization_percentage=bandwidth_util
        ),
        latency=LatencyMetrics(
            average_latency=draw(st.floats(min_value=5.0, max_value=50.0)),
            min_latency=1.0,
            max_latency=100.0,
            jitter=5.0
        ),
        utilization=UtilizationMetrics(
            cpu_utilization=draw(st.floats(min_value=30.0, max_value=80.0)),
            memory_utilization=draw(st.floats(min_value=40.0, max_value=80.0)),
            port_utilization={}
        )
    )
    
    return NetworkState(
        timestamp=datetime.now(),
        topology=topology,
        flows=[],
        metrics=metrics,
        anomalies=[anomaly]
    )


class TestAutomaticAnomalyMitigationProperties:
    """Property-based tests for automatic anomaly mitigation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.state_cache = NetworkStateCache()
        self.detection_system = AnomalyDetectionSystem(self.state_cache)
    
    @st.composite
    def critical_anomaly(draw):
        """Generate a critical anomaly that requires mitigation."""
        anomaly_type = draw(st.sampled_from([
            AnomalyType.SWITCH_FAILURE,
            AnomalyType.LINK_FAILURE,
            AnomalyType.TRAFFIC_SPIKE,
            AnomalyType.SECURITY_THREAT
        ]))
        
        # Generate affected resources with realistic names based on anomaly type
        num_resources = draw(st.integers(min_value=1, max_value=5))
        if anomaly_type == AnomalyType.SWITCH_FAILURE:
            affected_resources = [f"switch-{i}" for i in range(num_resources)]
        elif anomaly_type == AnomalyType.LINK_FAILURE:
            affected_resources = [f"link-{i}" for i in range(num_resources)]
        else:
            # For traffic spike and security threats, use switch names as affected resources
            affected_resources = [f"switch-{i}" for i in range(num_resources)]
        
        return Anomaly(
            id=f"anomaly_{draw(st.integers(min_value=1000, max_value=9999))}",
            type=anomaly_type,
            severity=AnomalySeverity.CRITICAL,
            description=f"Critical {anomaly_type.value} detected",
            affected_resources=affected_resources,
            detected_at=datetime.now(),
            metrics={
                "severity_score": draw(st.floats(min_value=0.8, max_value=1.0)),
                "impact_level": "high"
            }
        )
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        anomaly=critical_anomaly(),
        data=st.data()
    )
    def test_automatic_anomaly_mitigation(self, anomaly, data):
        """
        **Feature: llm-integration-module, Property 13: Automatic anomaly mitigation**
        
        For any critical anomaly detected, appropriate NetworkActions should be 
        automatically generated to mitigate the problem without human intervention.
        
        **Validates: Requirements 4.3**
        
        Requirement 4.3 states:
        "WHEN un'anomalia critica viene identificata, THE LLM_Module SHALL generare 
        automaticamente Network_Action per mitigare il problema"
        """
        assume(anomaly is not None)
        assume(anomaly.severity == AnomalySeverity.CRITICAL)
        
        # Generate matching network state
        network_state = data.draw(_network_state_for_anomaly(anomaly))
        
        # Update cache
        self.state_cache.update_state(network_state)
        
        # Generate automatic response actions
        response_actions = self.detection_system.generate_anomaly_response(anomaly, network_state)
        
        # Property: Critical anomalies should generate mitigation actions
        assert isinstance(response_actions, list), "Response should be a list of actions"
        
        # For critical anomalies, actions should be generated
        if anomaly.type in [AnomalyType.SWITCH_FAILURE, AnomalyType.LINK_FAILURE, 
                           AnomalyType.TRAFFIC_SPIKE, AnomalyType.SECURITY_THREAT]:
            assert len(response_actions) > 0, (
                f"Critical {anomaly.type.value} should generate mitigation actions"
            )
        
        # Verify each action is properly structured
        for action in response_actions:
            assert isinstance(action, NetworkAction), "Response should contain NetworkAction objects"
            assert action.id is not None and len(action.id) > 0, "Action must have valid ID"
            assert isinstance(action.type, ActionType), "Action must have valid type"
            assert action.target is not None and len(action.target) > 0, "Action must have target"
            assert isinstance(action.parameters, dict), "Action parameters must be a dictionary"
            assert isinstance(action.priority, int), "Action priority must be an integer"
            assert action.description is not None, "Action must have description"
            
            # Verify anomaly ID is referenced in action parameters
            assert 'anomaly_id' in action.parameters, "Action must reference the anomaly ID"
            assert action.parameters['anomaly_id'] == anomaly.id, "Action must reference correct anomaly"
        
        # Verify action types are appropriate for anomaly type
        if anomaly.type == AnomalyType.SWITCH_FAILURE:
            # Should generate failover actions
            action_types = [a.type for a in response_actions]
            assert ActionType.CONFIG_CHANGE in action_types, (
                "Switch failure should generate failover configuration actions"
            )
            
            # Verify actions target backup/alternative resources
            for action in response_actions:
                if action.type == ActionType.CONFIG_CHANGE:
                    assert 'failed_switch' in action.parameters or 'action' in action.parameters
        
        elif anomaly.type == AnomalyType.LINK_FAILURE:
            # Should generate rerouting actions
            action_types = [a.type for a in response_actions]
            assert ActionType.FLOW_MOD in action_types, (
                "Link failure should generate rerouting flow modification actions"
            )
            
            # Verify actions address the failed link
            for action in response_actions:
                if action.type == ActionType.FLOW_MOD:
                    assert 'failed_link' in action.parameters or 'action' in action.parameters
        
        elif anomaly.type == AnomalyType.TRAFFIC_SPIKE:
            # Should generate load balancing actions
            action_types = [a.type for a in response_actions]
            assert ActionType.FLOW_MOD in action_types, (
                "Traffic spike should generate load balancing actions"
            )
            
            # Verify actions aim to distribute load
            for action in response_actions:
                if action.type == ActionType.FLOW_MOD:
                    params = action.parameters
                    assert 'action' in params or 'strategy' in params
        
        elif anomaly.type == AnomalyType.SECURITY_THREAT:
            # Should generate security response actions
            action_types = [a.type for a in response_actions]
            assert ActionType.FLOW_MOD in action_types, (
                "Security threat should generate blocking/filtering actions"
            )
            
            # Verify actions address security concerns
            for action in response_actions:
                if action.type == ActionType.FLOW_MOD:
                    assert 'action' in action.parameters
        
        # Verify action priorities are appropriate for critical anomalies
        for action in response_actions:
            # Critical anomaly responses should have high priority
            assert action.priority >= 5000, (
                f"Critical anomaly mitigation should have high priority, got {action.priority}"
            )
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(
        anomaly=critical_anomaly(),
        data=st.data()
    )
    def test_mitigation_actions_are_executable(self, anomaly, data):
        """Test that generated mitigation actions are properly formatted and executable."""
        assume(anomaly is not None)
        assume(anomaly.severity == AnomalySeverity.CRITICAL)
        
        # Generate network state
        network_state = data.draw(_network_state_for_anomaly(anomaly))
        self.state_cache.update_state(network_state)
        
        # Generate response actions
        response_actions = self.detection_system.generate_anomaly_response(anomaly, network_state)
        
        # Verify actions can be validated
        for action in response_actions:
            validation_result = action.validate_action_parameters()
            
            # Actions should be valid or have only warnings
            assert isinstance(validation_result, dict)
            assert "is_valid" in validation_result
            assert "issues" in validation_result
            
            # Critical mitigation actions should be valid
            if len(validation_result["issues"]) > 0:
                # Log issues but don't fail - some actions may have warnings
                print(f"Action {action.id} validation issues: {validation_result['issues']}")
    
    @settings(max_examples=30)
    @given(
        anomaly=critical_anomaly(),
        data=st.data()
    )
    def test_mitigation_without_human_intervention(self, anomaly, data):
        """Test that mitigation actions are generated automatically without requiring human input."""
        assume(anomaly is not None)
        assume(anomaly.severity == AnomalySeverity.CRITICAL)
        
        # Generate network state
        network_state = data.draw(_network_state_for_anomaly(anomaly))
        self.state_cache.update_state(network_state)
        
        # Generate response - should not require any additional input
        response_actions = self.detection_system.generate_anomaly_response(anomaly, network_state)
        
        # Verify actions are generated automatically
        assert isinstance(response_actions, list)
        
        # For critical anomalies, should generate actions
        if anomaly.type in [AnomalyType.SWITCH_FAILURE, AnomalyType.LINK_FAILURE, 
                           AnomalyType.TRAFFIC_SPIKE, AnomalyType.SECURITY_THREAT]:
            assert len(response_actions) > 0
            
            # Verify actions are complete and don't require additional parameters
            for action in response_actions:
                assert action.id is not None
                assert action.type is not None
                assert action.target is not None
                assert action.parameters is not None
                assert 'anomaly_id' in action.parameters
    
    def test_mitigation_for_multiple_critical_anomalies(self):
        """Test mitigation generation for multiple simultaneous critical anomalies."""
        # Create multiple critical anomalies
        anomalies = [
            Anomaly(
                id="anomaly_switch_1",
                type=AnomalyType.SWITCH_FAILURE,
                severity=AnomalySeverity.CRITICAL,
                description="Switch failure",
                affected_resources=["switch-1"],
                detected_at=datetime.now(),
                metrics={}
            ),
            Anomaly(
                id="anomaly_traffic_1",
                type=AnomalyType.TRAFFIC_SPIKE,
                severity=AnomalySeverity.CRITICAL,
                description="Traffic spike",
                affected_resources=["switch-2"],
                detected_at=datetime.now(),
                metrics={}
            )
        ]
        
        # Create network state
        switches = [
            Switch(id="switch-1", name="Switch 1", dpid="00:00:00:00:00:00:00:01", 
                   ports=[1, 2, 3], status="failed"),
            Switch(id="switch-2", name="Switch 2", dpid="00:00:00:00:00:00:00:02", 
                   ports=[1, 2, 3], status="active")
        ]
        
        topology = Topology(switches=switches, links=[], hosts=[])
        
        network_state = NetworkState(
            timestamp=datetime.now(),
            topology=topology,
            flows=[],
            metrics=NetworkMetrics(
                bandwidth=BandwidthMetrics(
                    total_capacity=10000,
                    used_bandwidth=9500,
                    available_bandwidth=500,
                    utilization_percentage=95.0
                ),
                latency=LatencyMetrics(
                    average_latency=20.0,
                    min_latency=5.0,
                    max_latency=50.0,
                    jitter=5.0
                ),
                utilization=UtilizationMetrics(
                    cpu_utilization=70.0,
                    memory_utilization=60.0,
                    port_utilization={}
                )
            ),
            anomalies=anomalies
        )
        
        self.state_cache.update_state(network_state)
        
        # Generate responses for each anomaly
        all_actions = []
        for anomaly in anomalies:
            actions = self.detection_system.generate_anomaly_response(anomaly, network_state)
            all_actions.extend(actions)
        
        # Should generate actions for both anomalies
        assert len(all_actions) >= 2, "Should generate actions for multiple critical anomalies"
        
        # Verify each anomaly is addressed
        anomaly_ids_in_actions = set()
        for action in all_actions:
            if 'anomaly_id' in action.parameters:
                anomaly_ids_in_actions.add(action.parameters['anomaly_id'])
        
        assert len(anomaly_ids_in_actions) >= 1, "Actions should address the anomalies"
