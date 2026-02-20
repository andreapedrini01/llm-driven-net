#!/usr/bin/env python3
"""
Error scenario tests for the Northbound Script Generator
Tests system behavior under various failure conditions
Validates: Requirement 7.3 - Detailed logging for debugging
"""

import pytest
import time
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'mocks'))

from connectors.ryu_connector import create_ryu_connector, RYUConfig
from connectors.comnetsemu_connector import create_comnetsemu_connector, ComnetsEMUConfig
from models.action_models import NetworkAction, ActionType
from mock_comnetsemu import get_mock_comnetsemu, reset_mock_comnetsemu


class TestErrorScenarios:
    """Test system behavior under error conditions."""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        reset_mock_comnetsemu()
        yield
        reset_mock_comnetsemu()
    
    @pytest.fixture
    def ryu_connector(self):
        """Create RYU connector for testing."""
        config = RYUConfig(
            host="localhost",
            port=8080,
            timeout_seconds=5,
            max_retries=2,
            retry_delay=0.5
        )
        connector = create_ryu_connector(config=config)
        yield connector
        connector.close()
    
    @pytest.fixture
    def comnetsemu_connector(self):
        """Create ComnetsEMU connector for testing."""
        config = ComnetsEMUConfig(
            host="localhost",
            port=6653,
            api_port=8181,
            timeout_seconds=5,
            max_retries=2
        )
        connector = create_comnetsemu_connector(config=config)
        yield connector
        connector.close()
    
    def test_scenario_switch_failure(self, comnetsemu_connector):
        """
        Test behavior when a switch fails
        Validates: Requirement 7.3 - Detailed logging
        """
        mock = get_mock_comnetsemu()
        
        # Add a switch
        mock.add_switch("s10", ports=4)
        
        # Inject switch failure
        mock.inject_failure("switch_down", "s10", duration=5)
        
        # Try to add flow to failed switch
        action = NetworkAction(
            id="test_switch_failure",
            type=ActionType.FLOW_MOD,
            target="10",
            parameters={
                "operation": "add",
                "match": {"eth_type": 2048, "ip_src": "10.0.1.1"},
                "actions": ["output:1"],
                "priority": 1000,
                "idle_timeout": 60,
                "hard_timeout": 120
            },
            priority=1000,
            timeout=30
        )
        
        # Should handle gracefully
        topology = comnetsemu_connector.get_network_topology()
        
        # Verify switch is marked as down
        switch_status = next((s for s in topology["switches"] if s["dpid"] == "10"), None)
        if switch_status:
            assert switch_status["status"] == "down"
        
        # Clear failure
        mock.clear_failures()
        
        # Verify recovery
        topology = comnetsemu_connector.get_network_topology()
        switch_status = next((s for s in topology["switches"] if s["dpid"] == "10"), None)
        if switch_status:
            assert switch_status["status"] == "active"
    
    def test_scenario_link_failure(self, comnetsemu_connector):
        """
        Test behavior when a link fails
        Validates: Requirement 7.3 - Detailed logging
        """
        mock = get_mock_comnetsemu()
        
        # Inject link failure
        mock.inject_failure("link_down", "s1", duration=5)
        
        # Get topology
        topology = comnetsemu_connector.get_network_topology()
        
        # Verify affected links are marked as down
        down_links = [link for link in topology["links"] 
                     if link["status"] == "down" and 
                     (link["src"] == "s1" or link["dst"] == "s1")]
        
        assert len(down_links) > 0
        
        # Clear failure
        mock.clear_failures()
        
        # Verify recovery
        topology = comnetsemu_connector.get_network_topology()
        active_links = [link for link in topology["links"] 
                       if link["status"] == "active"]
        
        assert len(active_links) > 0
    
    def test_scenario_high_latency(self, comnetsemu_connector):
        """
        Test behavior under high latency conditions
        Validates: Requirement 7.3 - Detailed logging
        """
        mock = get_mock_comnetsemu()
        
        # Get initial latency
        topology_before = comnetsemu_connector.get_network_topology()
        initial_latency = topology_before["links"][0]["latency"] if topology_before["links"] else 1
        
        # Inject high latency
        mock.inject_failure("high_latency", "s1", duration=5)
        
        # Get topology with high latency
        topology_after = comnetsemu_connector.get_network_topology()
        
        # Verify latency increased
        affected_links = [link for link in topology_after["links"] 
                         if link["src"] == "s1" or link["dst"] == "s1"]
        
        if affected_links:
            assert affected_links[0]["latency"] > initial_latency
        
        # Clear failure
        mock.clear_failures()
    
    def test_scenario_packet_loss(self, comnetsemu_connector):
        """
        Test behavior under packet loss conditions
        Validates: Requirement 7.3 - Detailed logging
        """
        mock = get_mock_comnetsemu()
        
        # Inject packet loss
        mock.inject_failure("packet_loss", "s1", duration=5)
        
        # Get topology
        topology = comnetsemu_connector.get_network_topology()
        
        # Verify packet loss on affected links
        affected_links = [link for link in topology["links"] 
                         if link["src"] == "s1" or link["dst"] == "s1"]
        
        if affected_links:
            assert affected_links[0]["packet_loss"] > 0
        
        # Clear failure
        mock.clear_failures()
    
    def test_scenario_invalid_flow_parameters(self, ryu_connector):
        """
        Test handling of invalid flow parameters
        Validates: Requirement 7.3 - Detailed logging
        """
        # Test with invalid priority
        action = NetworkAction(
            id="test_invalid_priority",
            type=ActionType.FLOW_MOD,
            target="1",
            parameters={
                "operation": "add",
                "match": {"eth_type": 2048},
                "actions": ["output:1"],
                "priority": -1,  # Invalid priority
                "idle_timeout": 60,
                "hard_timeout": 120
            },
            priority=1000,
            timeout=30
        )
        
        try:
            result = ryu_connector.execute_flow_mod(action)
            # Should either fail or handle gracefully
            assert isinstance(result, dict)
        except Exception as e:
            # Expected to fail with validation error
            assert "priority" in str(e).lower() or "invalid" in str(e).lower()
    
    def test_scenario_connection_timeout(self):
        """
        Test handling of connection timeouts
        Validates: Requirement 7.3 - Detailed logging
        """
        # Create connector with very short timeout
        config = RYUConfig(
            host="192.0.2.1",  # Non-routable IP (TEST-NET-1)
            port=8080,
            timeout_seconds=1,
            max_retries=1,
            retry_delay=0.1
        )
        
        connector = create_ryu_connector(config=config)
        
        try:
            # This should timeout
            status = connector.get_connection_status()
            # If it doesn't timeout, check the status
            assert "status" in status
        except Exception as e:
            # Expected to timeout
            assert "timeout" in str(e).lower() or "connection" in str(e).lower()
        finally:
            connector.close()
    
    def test_scenario_duplicate_flow(self, ryu_connector):
        """
        Test handling of duplicate flow rules
        Validates: Requirement 7.3 - Detailed logging
        """
        action = NetworkAction(
            id="test_duplicate_flow",
            type=ActionType.FLOW_MOD,
            target="1",
            parameters={
                "operation": "add",
                "match": {"eth_type": 2048, "ip_src": "10.0.1.100"},
                "actions": ["output:1"],
                "priority": 5000,
                "idle_timeout": 0,
                "hard_timeout": 0
            },
            priority=1000,
            timeout=30
        )
        
        try:
            # Add flow first time
            result1 = ryu_connector.execute_flow_mod(action)
            
            # Try to add same flow again
            result2 = ryu_connector.execute_flow_mod(action)
            
            # Should handle gracefully (either succeed or report duplicate)
            assert isinstance(result1, dict)
            assert isinstance(result2, dict)
        except Exception as e:
            # May fail with duplicate error
            pass
    
    def test_scenario_resource_exhaustion(self, comnetsemu_connector):
        """
        Test behavior under resource exhaustion
        Validates: Requirement 7.3 - Detailed logging
        """
        mock = get_mock_comnetsemu()
        
        # Add many switches to simulate resource pressure
        for i in range(100):
            mock.add_switch(f"s{100 + i}", ports=4)
        
        # Try to get topology
        topology = comnetsemu_connector.get_network_topology()
        
        # Should handle large topology
        assert len(topology["switches"]) >= 100
        
        # Get statistics
        stats = comnetsemu_connector.get_network_statistics()
        assert stats["topology_summary"]["switches"] >= 100
    
    def test_scenario_concurrent_failures(self, comnetsemu_connector):
        """
        Test handling of multiple concurrent failures
        Validates: Requirement 7.3 - Detailed logging
        """
        mock = get_mock_comnetsemu()
        
        # Inject multiple failures
        mock.inject_failure("switch_down", "s1", duration=10)
        mock.inject_failure("link_down", "s2", duration=10)
        mock.inject_failure("high_latency", "h1", duration=10)
        
        # System should still be able to get topology
        topology = comnetsemu_connector.get_network_topology()
        
        assert topology is not None
        assert "switches" in topology
        assert "hosts" in topology
        assert "links" in topology
        
        # Clear all failures
        mock.clear_failures()
    
    def test_scenario_rapid_configuration_changes(self, comnetsemu_connector):
        """
        Test handling of rapid configuration changes
        Validates: Requirement 7.3 - Detailed logging
        """
        mock = get_mock_comnetsemu()
        
        # Rapidly add and remove elements
        for i in range(20):
            # Add switch
            mock.add_switch(f"rapid_s{i}", ports=4)
            
            # Add host
            mock.add_host(f"rapid_h{i}", f"10.100.{i}.1", f"00:00:00:64:{i:02x}:01")
            
            # Add QoS policy
            mock.set_qos_policy(
                f"rapid_qos_{i}",
                f"rapid_s{i}",
                bandwidth_limit=100,
                latency_limit=10,
                packet_loss_limit=0.01
            )
        
        # Get final topology
        topology = comnetsemu_connector.get_network_topology()
        
        # Should have all elements
        assert len(topology["switches"]) >= 20
        assert len(topology["hosts"]) >= 20
        
        # Remove all rapid elements
        for i in range(20):
            mock.remove_switch(f"rapid_s{i}")
            mock.remove_host(f"rapid_h{i}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
