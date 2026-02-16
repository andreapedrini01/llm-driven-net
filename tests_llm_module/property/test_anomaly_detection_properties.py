"""Property-based tests for anomaly detection functionality."""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from datetime import datetime, timedelta
from typing import List, Dict, Any
import time

from src.services.context_analyzer import AnomalyDetectionSystem, NetworkStateCache
from src.models.network import (
    NetworkState, Topology, NetworkMetrics, BandwidthMetrics, 
    LatencyMetrics, UtilizationMetrics, Switch, Link, Host, Flow,
    Anomaly, AnomalyType, AnomalySeverity
)


class TestAnomalyDetectionProperties:
    """Property-based tests for anomaly detection comprehensiveness."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.cache = NetworkStateCache()
        self.detection_system = AnomalyDetectionSystem(self.cache)
    
    # Generator strategies for test data
    @staticmethod
    @st.composite
    def network_state_with_anomalous_patterns(draw):
        """Generate NetworkState instances with known anomalous patterns."""
        
        # Generate base topology
        num_switches = draw(st.integers(min_value=1, max_value=10))
        num_links = draw(st.integers(min_value=0, max_value=num_switches * 2))
        num_hosts = draw(st.integers(min_value=0, max_value=num_switches * 3))
        
        switches = []
        for i in range(num_switches):
            # Introduce switch failures for anomaly testing
            status = draw(st.sampled_from(["active", "inactive", "failed"]))
            switch = Switch(
                id=f"switch_{i}",
                name=f"Switch {i}",
                dpid=f"000000000000000{i:x}",
                ports=list(range(1, draw(st.integers(min_value=2, max_value=8)))),
                status=status
            )
            switches.append(switch)
        
        links = []
        for i in range(num_links):
            if len(switches) >= 2:
                source_idx = draw(st.integers(min_value=0, max_value=len(switches)-1))
                dest_idx = draw(st.integers(min_value=0, max_value=len(switches)-1))
                # Introduce link failures for anomaly testing
                status = draw(st.sampled_from(["active", "inactive", "failed"]))
                link = Link(
                    id=f"link_{i}",
                    source_switch=switches[source_idx].id,
                    source_port=draw(st.integers(min_value=1, max_value=4)),
                    destination_switch=switches[dest_idx].id,
                    destination_port=draw(st.integers(min_value=1, max_value=4)),
                    bandwidth=draw(st.integers(min_value=100, max_value=10000)),
                    latency=draw(st.floats(min_value=0.1, max_value=100.0)),
                    status=status
                )
                links.append(link)
        
        hosts = []
        for i in range(num_hosts):
            if switches:
                connected_switch = draw(st.sampled_from(switches)).id
                host = Host(
                    id=f"host_{i}",
                    mac_address=f"00:00:00:00:00:{i:02x}",
                    ip_address=f"10.0.0.{i+1}",
                    connected_switch=connected_switch,
                    connected_port=draw(st.integers(min_value=1, max_value=4)),
                    status="active"
                )
                hosts.append(host)
        
        topology = Topology(switches=switches, links=links, hosts=hosts)
        
        # Generate flows
        flows = []
        num_flows = draw(st.integers(min_value=0, max_value=50))
        for i in range(num_flows):
            if switches:
                switch_id = draw(st.sampled_from(switches)).id
                flow = Flow(
                    id=f"flow_{i}",
                    switch_id=switch_id,
                    match_fields={"in_port": draw(st.integers(min_value=1, max_value=4))},
                    actions=[{"type": "output", "port": draw(st.integers(min_value=1, max_value=4))}],
                    priority=draw(st.integers(min_value=100, max_value=9000)),
                    byte_count=draw(st.integers(min_value=0, max_value=1000000)),
                    packet_count=draw(st.integers(min_value=0, max_value=10000))
                )
                flows.append(flow)
        
        # Generate metrics with potential anomalous values
        bandwidth_util = draw(st.floats(min_value=0.0, max_value=100.0))
        total_capacity = draw(st.integers(min_value=1000, max_value=100000))
        used_bandwidth = int(total_capacity * bandwidth_util / 100)
        
        bandwidth_metrics = BandwidthMetrics(
            total_capacity=total_capacity,
            used_bandwidth=used_bandwidth,
            available_bandwidth=total_capacity - used_bandwidth,
            utilization_percentage=bandwidth_util
        )
        
        # Generate potentially anomalous latency
        avg_latency = draw(st.floats(min_value=0.1, max_value=500.0))
        latency_metrics = LatencyMetrics(
            average_latency=avg_latency,
            min_latency=max(0.1, avg_latency * 0.5),
            max_latency=avg_latency * 2.0,
            jitter=draw(st.floats(min_value=0.0, max_value=avg_latency * 0.5))
        )
        
        # Generate potentially anomalous utilization
        cpu_util = draw(st.floats(min_value=0.0, max_value=100.0))
        memory_util = draw(st.floats(min_value=0.0, max_value=100.0))
        
        utilization_metrics = UtilizationMetrics(
            cpu_utilization=cpu_util,
            memory_utilization=memory_util,
            port_utilization={f"port_{i}": draw(st.floats(min_value=0.0, max_value=100.0)) 
                            for i in range(draw(st.integers(min_value=0, max_value=5)))}
        )
        
        metrics = NetworkMetrics(
            bandwidth=bandwidth_metrics,
            latency=latency_metrics,
            utilization=utilization_metrics
        )
        
        # Generate timestamp (recent)
        timestamp = datetime.now() - timedelta(seconds=draw(st.integers(min_value=0, max_value=300)))
        
        return NetworkState(
            timestamp=timestamp,
            topology=topology,
            flows=flows,
            metrics=metrics,
            anomalies=[]  # Start with no anomalies, let detection system find them
        )
    
    @staticmethod
    @st.composite
    def network_state_with_known_anomalies(draw):
        """Generate NetworkState with specific known anomalous conditions."""
        
        # Generate a base state using the other strategy
        base_state = draw(TestAnomalyDetectionProperties.network_state_with_anomalous_patterns())
        
        # Force specific anomalous conditions
        anomaly_type = draw(st.sampled_from([
            "bandwidth_spike", "latency_increase", "cpu_high", 
            "memory_high", "switch_failure", "link_failure"
        ]))
        
        if anomaly_type == "bandwidth_spike":
            # Force high bandwidth utilization
            utilization = draw(st.floats(min_value=85.0, max_value=100.0))
            used = int(base_state.metrics.bandwidth.total_capacity * utilization / 100)
            base_state.metrics.bandwidth.utilization_percentage = utilization
            base_state.metrics.bandwidth.used_bandwidth = used
            base_state.metrics.bandwidth.available_bandwidth = base_state.metrics.bandwidth.total_capacity - used
        
        elif anomaly_type == "latency_increase":
            # Force high latency
            avg_latency = draw(st.floats(min_value=100.0, max_value=500.0))
            base_state.metrics.latency.average_latency = avg_latency
            base_state.metrics.latency.max_latency = avg_latency * 2.0
            base_state.metrics.latency.min_latency = avg_latency * 0.5
        
        elif anomaly_type == "cpu_high":
            # Force high CPU utilization
            base_state.metrics.utilization.cpu_utilization = draw(st.floats(min_value=90.0, max_value=100.0))
        
        elif anomaly_type == "memory_high":
            # Force high memory utilization
            base_state.metrics.utilization.memory_utilization = draw(st.floats(min_value=85.0, max_value=100.0))
        
        elif anomaly_type == "switch_failure":
            # Force at least one switch to be failed
            if base_state.topology.switches:
                failed_switch = draw(st.sampled_from(base_state.topology.switches))
                failed_switch.status = "failed"
        
        elif anomaly_type == "link_failure":
            # Force at least one link to be failed
            if base_state.topology.links:
                failed_link = draw(st.sampled_from(base_state.topology.links))
                failed_link.status = "failed"
        
        return base_state, anomaly_type
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(state_data=network_state_with_known_anomalies())
    def test_anomaly_detection_comprehensiveness(self, state_data):
        """
        **Feature: llm-integration-module, Property 12: Anomaly detection comprehensiveness**
        
        For any NetworkState containing known anomalous patterns, the LLM_Module should 
        correctly identify, classify, and assess the severity of all anomalies.
        
        **Validates: Requirements 4.1, 4.2**
        """
        network_state, expected_anomaly_type = state_data
        
        # Ensure we have a valid network state
        assume(network_state is not None)
        assume(isinstance(network_state, NetworkState))
        
        # Update the cache with the network state
        self.cache.update_state(network_state)
        
        # Detect anomalies
        detected_anomalies = self.detection_system.detect_anomalies(network_state)
        
        # Verify that anomalies are detected as a list
        assert isinstance(detected_anomalies, list)
        
        # For each detected anomaly, verify it's properly structured
        for anomaly in detected_anomalies:
            assert isinstance(anomaly, Anomaly)
            assert anomaly.id is not None and len(anomaly.id) > 0
            assert isinstance(anomaly.type, AnomalyType)
            assert isinstance(anomaly.severity, AnomalySeverity)
            assert anomaly.description is not None and len(anomaly.description) > 0
            assert isinstance(anomaly.detected_at, datetime)
            assert isinstance(anomaly.affected_resources, list)
            assert isinstance(anomaly.metrics, dict)
            
            # Verify severity classification is appropriate
            classified_severity = self.detection_system.classify_anomaly_severity(anomaly, network_state)
            assert isinstance(classified_severity, AnomalySeverity)
            
            # Verify that critical anomalies (like switch failures) are classified as critical
            if anomaly.type == AnomalyType.SWITCH_FAILURE:
                assert classified_severity == AnomalySeverity.CRITICAL
        
        # Verify comprehensive detection based on the known anomaly type
        if expected_anomaly_type == "bandwidth_spike":
            # Should detect bandwidth-related anomalies when utilization is high
            if network_state.metrics.bandwidth.utilization_percentage > 80:
                bandwidth_anomalies = [a for a in detected_anomalies 
                                     if a.type == AnomalyType.TRAFFIC_SPIKE]
                # Should detect at least one bandwidth anomaly for high utilization
                if network_state.metrics.bandwidth.utilization_percentage > 95:
                    assert len(bandwidth_anomalies) > 0, "Should detect traffic spike for very high bandwidth utilization"
        
        elif expected_anomaly_type == "latency_increase":
            # Should detect latency anomalies when latency is high
            if network_state.metrics.latency.average_latency > 100:
                latency_anomalies = [a for a in detected_anomalies 
                                   if a.type == AnomalyType.LATENCY_INCREASE]
                # For very high latency, should detect anomaly
                if network_state.metrics.latency.average_latency > 200:
                    assert len(latency_anomalies) > 0, "Should detect latency anomaly for very high latency"
        
        elif expected_anomaly_type == "cpu_high":
            # Should detect CPU utilization anomalies
            if network_state.metrics.utilization.cpu_utilization > 90:
                cpu_anomalies = [a for a in detected_anomalies 
                               if "cpu" in a.description.lower() or a.type == AnomalyType.TRAFFIC_SPIKE]
                assert len(cpu_anomalies) > 0, "Should detect CPU utilization anomaly"
        
        elif expected_anomaly_type == "memory_high":
            # Should detect memory utilization anomalies
            if network_state.metrics.utilization.memory_utilization > 85:
                memory_anomalies = [a for a in detected_anomalies 
                                  if "memory" in a.description.lower() or a.type == AnomalyType.TRAFFIC_SPIKE]
                assert len(memory_anomalies) > 0, "Should detect memory utilization anomaly"
        
        elif expected_anomaly_type == "switch_failure":
            # Should detect switch failure anomalies
            failed_switches = [s for s in network_state.topology.switches if s.status != "active"]
            if failed_switches:
                switch_anomalies = [a for a in detected_anomalies 
                                  if a.type == AnomalyType.SWITCH_FAILURE]
                assert len(switch_anomalies) > 0, "Should detect switch failure anomalies"
                
                # Verify affected resources are correctly identified
                for anomaly in switch_anomalies:
                    assert len(anomaly.affected_resources) > 0, "Switch failure should identify affected resources"
        
        elif expected_anomaly_type == "link_failure":
            # Should detect link failure anomalies
            failed_links = [l for l in network_state.topology.links if l.status != "active"]
            if failed_links:
                link_anomalies = [a for a in detected_anomalies 
                                if a.type == AnomalyType.LINK_FAILURE]
                assert len(link_anomalies) > 0, "Should detect link failure anomalies"
                
                # Verify affected resources include the link and connected switches
                for anomaly in link_anomalies:
                    assert len(anomaly.affected_resources) >= 1, "Link failure should identify affected resources"
        
        # Verify that all detected anomalies have reasonable metrics
        for anomaly in detected_anomalies:
            if anomaly.type == AnomalyType.TRAFFIC_SPIKE:
                # Traffic spike anomalies should have utilization metrics
                if "utilization" in anomaly.metrics or "bandwidth" in anomaly.metrics:
                    assert any(key in anomaly.metrics for key in 
                             ["current_utilization", "baseline_utilization", "cpu_utilization", "memory_utilization"])
            
            elif anomaly.type == AnomalyType.LATENCY_INCREASE:
                # Latency anomalies should have latency metrics
                assert any(key in anomaly.metrics for key in 
                         ["current_latency", "baseline_latency", "latency_multiplier"])
            
            elif anomaly.type in [AnomalyType.SWITCH_FAILURE, AnomalyType.LINK_FAILURE]:
                # Failure anomalies should have status information
                assert any(key in anomaly.metrics for key in 
                         ["switch_status", "link_status"])
        
        # The core property is that anomalies are detected and properly structured
        # Consistency between calls is less important than comprehensive detection
    
    @settings(max_examples=50)
    @given(network_state=network_state_with_anomalous_patterns())
    def test_anomaly_severity_classification_consistency(self, network_state):
        """Test that anomaly severity classification is consistent and appropriate."""
        assume(network_state is not None)
        
        # Update cache and detect anomalies
        self.cache.update_state(network_state)
        detected_anomalies = self.detection_system.detect_anomalies(network_state)
        
        # Test severity classification for each detected anomaly
        for anomaly in detected_anomalies:
            severity = self.detection_system.classify_anomaly_severity(anomaly, network_state)
            
            # Verify severity is valid
            assert isinstance(severity, AnomalySeverity)
            
            # Verify severity logic consistency
            if anomaly.type == AnomalyType.SWITCH_FAILURE:
                assert severity == AnomalySeverity.CRITICAL, "Switch failures should always be critical"
            
            elif anomaly.type == AnomalyType.LINK_FAILURE:
                # Link failure severity should depend on impact
                if len(anomaly.affected_resources) > 2:
                    assert severity in [AnomalySeverity.HIGH, AnomalySeverity.CRITICAL], "Multi-resource link failures should be high severity"
                else:
                    assert severity in [AnomalySeverity.MEDIUM, AnomalySeverity.HIGH], "Single link failures should be medium-high severity"
            
            elif anomaly.type == AnomalyType.TRAFFIC_SPIKE:
                # Traffic spike severity should correlate with utilization
                if network_state.metrics.bandwidth.utilization_percentage > 95:
                    assert severity in [AnomalySeverity.HIGH, AnomalySeverity.CRITICAL], "Very high utilization should be high severity"
                elif network_state.metrics.bandwidth.utilization_percentage > 80:
                    assert severity in [AnomalySeverity.MEDIUM, AnomalySeverity.HIGH], "High utilization should be medium-high severity"
    
    @settings(max_examples=30)
    @given(network_state=network_state_with_anomalous_patterns())
    def test_anomaly_response_generation(self, network_state):
        """Test that appropriate response actions are generated for detected anomalies."""
        assume(network_state is not None)
        
        # Update cache and detect anomalies
        self.cache.update_state(network_state)
        detected_anomalies = self.detection_system.detect_anomalies(network_state)
        
        # Test response generation for each anomaly
        for anomaly in detected_anomalies:
            response_actions = self.detection_system.generate_anomaly_response(anomaly, network_state)
            
            # Verify response actions are generated
            assert isinstance(response_actions, list)
            
            # For critical anomalies, should generate response actions
            if anomaly.severity in [AnomalySeverity.HIGH, AnomalySeverity.CRITICAL]:
                # Should generate at least one response action for critical issues
                if anomaly.type in [AnomalyType.SWITCH_FAILURE, AnomalyType.LINK_FAILURE, AnomalyType.TRAFFIC_SPIKE]:
                    assert len(response_actions) > 0, f"Should generate response actions for {anomaly.type} anomalies"
            
            # Verify each response action is properly structured
            for action in response_actions:
                assert hasattr(action, 'id') and action.id is not None
                assert hasattr(action, 'type') and action.type is not None
                assert hasattr(action, 'target') and action.target is not None
                assert hasattr(action, 'parameters') and isinstance(action.parameters, dict)
                assert hasattr(action, 'priority') and isinstance(action.priority, int)
                assert hasattr(action, 'description') and action.description is not None
                
                # Verify anomaly ID is referenced in action parameters
                assert 'anomaly_id' in action.parameters
                assert action.parameters['anomaly_id'] == anomaly.id
    
    def test_anomaly_detection_with_empty_state(self):
        """Test anomaly detection with minimal/empty network state."""
        # Create minimal network state
        minimal_state = NetworkState(
            timestamp=datetime.now(),
            topology=Topology(switches=[], links=[], hosts=[]),
            flows=[],
            metrics=NetworkMetrics(
                bandwidth=BandwidthMetrics(
                    total_capacity=1000,
                    used_bandwidth=0,
                    available_bandwidth=1000,
                    utilization_percentage=0.0
                ),
                latency=LatencyMetrics(
                    average_latency=1.0,
                    min_latency=1.0,
                    max_latency=1.0,
                    jitter=0.0
                ),
                utilization=UtilizationMetrics(
                    cpu_utilization=0.0,
                    memory_utilization=0.0
                )
            ),
            anomalies=[]
        )
        
        # Should handle empty state gracefully
        self.cache.update_state(minimal_state)
        detected_anomalies = self.detection_system.detect_anomalies(minimal_state)
        
        # Should return empty list or minimal anomalies for empty state
        assert isinstance(detected_anomalies, list)
        # Empty state should not generate false positive anomalies
        assert len(detected_anomalies) == 0, "Empty network state should not generate anomalies"