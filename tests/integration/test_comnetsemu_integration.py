#!/usr/bin/env python3
"""
Integration tests for ComnetsEMU Connector
Tests the real ComnetsEMU integration with various scenarios
"""

import pytest
import json
import time
from datetime import datetime
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from connectors.comnetsemu_connector import create_comnetsemu_connector, ComnetsEMUConfig
from models.action_models import NetworkAction, ActionType


class TestComnetsEMUIntegration:
    """Integration tests for ComnetsEMU connector."""
    
    @pytest.fixture
    def comnetsemu_connector(self):
        """Create ComnetsEMU connector for testing."""
        config = ComnetsEMUConfig(
            host="localhost",
            port=6653,
            api_port=8181,
            timeout_seconds=10,
            max_retries=2
        )
        connector = create_comnetsemu_connector(config=config)
        yield connector
        connector.close()
    
    def test_connection_initialization(self, comnetsemu_connector):
        """Test ComnetsEMU connector initialization."""
        status = comnetsemu_connector.get_connection_status()
        
        assert status is not None
        assert "status" in status
        assert "config" in status
        assert status["config"]["host"] == "localhost"
        assert status["config"]["port"] == 6653
    
    def test_topology_discovery(self, comnetsemu_connector):
        """Test network topology discovery."""
        topology = comnetsemu_connector.get_network_topology()
        
        assert topology is not None
        assert hasattr(topology, 'switches')
        assert hasattr(topology, 'hosts')
        assert hasattr(topology, 'links')
        assert isinstance(topology.switches, list)
        assert isinstance(topology.hosts, list)
        assert isinstance(topology.links, list)
    
    def test_network_state_retrieval(self, comnetsemu_connector):
        """Test network state retrieval for different targets."""
        # Test switch state
        switch_state = comnetsemu_connector.get_network_state("switch-1")
        assert isinstance(switch_state, dict)
        assert "target" in switch_state
        assert "status" in switch_state
        assert "timestamp" in switch_state
        
        # Test host state
        host_state = comnetsemu_connector.get_network_state("10.0.1.10")
        assert isinstance(host_state, dict)
        assert "target" in host_state
        assert "status" in host_state
    
    def test_topology_change_operations(self, comnetsemu_connector):
        """Test topology change operations."""
        # Test adding a switch
        action = NetworkAction(
            id="test_topo_001",
            type=ActionType.CONFIG_CHANGE,
            target="network",
            parameters={
                "config_type": "topology",
                "config_data": {
                    "operation": "add",
                    "element_type": "switch",
                    "element_id": "test_switch",
                    "properties": {
                        "dpid": "999",
                        "ports": 4
                    }
                }
            },
            priority=1000,
            timeout=30
        )
        
        result = comnetsemu_connector.execute_topology_change(action)
        assert isinstance(result, dict)
        assert "success" in result
        assert "message" in result
        
        # For simulation mode, this should succeed
        if result["success"]:
            assert result["operation"] == "add"
            assert result["element_type"] == "switch"
            assert result["element_id"] == "test_switch"
    
    def test_qos_policy_operations(self, comnetsemu_connector):
        """Test QoS policy configuration."""
        action = NetworkAction(
            id="test_qos_001",
            type=ActionType.CONFIG_CHANGE,
            target="switch-1",
            parameters={
                "config_type": "qos",
                "config_data": {
                    "policy_id": "test_policy",
                    "target_type": "switch",
                    "target_id": "s1",
                    "bandwidth_limit": 100,
                    "latency_limit": 10,
                    "packet_loss_limit": 0.01
                }
            },
            priority=1000,
            timeout=30
        )
        
        result = comnetsemu_connector.execute_qos_policy(action)
        assert isinstance(result, dict)
        assert "success" in result
        assert "message" in result
        
        if result["success"]:
            assert result["policy_id"] == "test_policy"
            assert result["target_type"] == "switch"
            assert result["target_id"] == "s1"
    
    def test_network_verification(self, comnetsemu_connector):
        """Test network state verification."""
        action = NetworkAction(
            id="test_verify_001",
            type=ActionType.SLICE_CREATE,
            target="network",
            parameters={
                "slice_name": "test_slice",
                "resources": {
                    "hosts": ["web1", "db1"],
                    "switches": ["s1", "s2"],
                    "bandwidth": "100Mbps"
                }
            },
            priority=1000
        )
        
        expected_state = {"status": "active"}
        result = comnetsemu_connector.verify_network_state(action, expected_state)
        assert isinstance(result, bool)
    
    def test_network_statistics(self, comnetsemu_connector):
        """Test network statistics collection."""
        stats = comnetsemu_connector.get_network_statistics()
        
        assert isinstance(stats, dict)
        assert "timestamp" in stats
        assert "topology_summary" in stats
        
        summary = stats["topology_summary"]
        assert "switches" in summary
        assert "hosts" in summary
        assert "links" in summary
        assert "controllers" in summary
    
    def test_health_check(self, comnetsemu_connector):
        """Test health check functionality."""
        health = comnetsemu_connector.health_check()
        
        assert isinstance(health, dict)
        assert "timestamp" in health
        assert "overall_status" in health
        assert "checks" in health
        
        # Check that we have expected health checks
        checks = health["checks"]
        assert "connectivity" in checks
        assert "topology_cache" in checks
        assert "success_rate" in checks
    
    def test_error_handling(self):
        """Test error handling with invalid operations."""
        config = ComnetsEMUConfig(
            host="localhost",
            port=6653,
            timeout_seconds=5,
            max_retries=1
        )
        connector = create_comnetsemu_connector(config=config)
        
        try:
            # Test invalid topology operation
            action = NetworkAction(
                id="test_invalid_001",
                type=ActionType.CONFIG_CHANGE,
                target="network",
                parameters={
                    "config_type": "topology",
                    "config_data": {
                        "operation": "invalid_operation",
                        "element_type": "switch",
                        "element_id": "test"
                    }
                }
            )
            
            result = connector.execute_topology_change(action)
            assert isinstance(result, dict)
            assert "success" in result
            # Should fail due to invalid operation
            assert not result["success"]
            assert "error" in result
            
        finally:
            connector.close()
    
    def test_flow_validation(self, comnetsemu_connector):
        """Test flow parameter validation."""
        # Test with valid flow parameters
        valid_result = comnetsemu_connector._validate_flow_parameters(
            operation="add",
            match_fields={"ip_src": "10.0.0.1", "tcp_dst": 80},
            actions=["output:2"],
            priority=1000
        )
        
        assert valid_result["valid"] is True
        assert len(valid_result["errors"]) == 0
        
        # Test with invalid flow parameters
        invalid_result = comnetsemu_connector._validate_flow_parameters(
            operation="invalid_op",
            match_fields={"invalid_field": "value"},
            actions=["invalid_action"],
            priority=-1
        )
        
        assert invalid_result["valid"] is False
        assert len(invalid_result["errors"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])