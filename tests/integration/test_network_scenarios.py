#!/usr/bin/env python3
"""
Integration tests for realistic network scenarios
Tests complete workflows with RYU and ComnetsEMU integration
"""

import pytest
import json
import time
from datetime import datetime
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from connectors.ryu_connector import create_ryu_connector, RYUConfig
from connectors.comnetsemu_connector import create_comnetsemu_connector, ComnetsEMUConfig
from models.action_models import NetworkAction, ActionType


class TestRealisticNetworkScenarios:
    """Integration tests for realistic network scenarios."""
    
    @pytest.fixture
    def ryu_connector(self):
        """Create RYU connector for testing."""
        config = RYUConfig(
            host="localhost",
            port=8080,
            timeout_seconds=10,
            max_retries=2,
            retry_delay=1.0
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
            timeout_seconds=10,
            max_retries=2
        )
        connector = create_comnetsemu_connector(config=config)
        yield connector
        connector.close()
    
    def test_scenario_1_traffic_isolation(self, ryu_connector, comnetsemu_connector):
        """
        Scenario 1: Traffic Isolation
        Create isolated network slices for different tenants
        """
        # Step 1: Create network topology
        topology_action = NetworkAction(
            id="scenario1_topo",
            type=ActionType.CONFIG_CHANGE,
            target="network",
            parameters={
                "config_type": "topology",
                "config_data": {
                    "operation": "add",
                    "element_type": "switch",
                    "element_id": "s1",
                    "properties": {"dpid": "1", "ports": 8}
                }
            },
            priority=1000,
            timeout=30
        )
        
        topo_result = comnetsemu_connector.execute_topology_change(topology_action)
        assert topo_result["success"]
        
        # Step 2: Configure flow rules for tenant isolation
        flow_actions = []
        for tenant_id in range(1, 4):
            action = NetworkAction(
                id=f"scenario1_flow_tenant{tenant_id}",
                type=ActionType.FLOW_MOD,
                target="1",
                parameters={
                    "operation": "add",
                    "match": {
                        "eth_type": 2048,
                        "ip_src": f"10.0.{tenant_id}.0/24"
                    },
                    "actions": [f"output:{tenant_id}"],
                    "priority": 1000 + tenant_id,
                    "idle_timeout": 0,
                    "hard_timeout": 0
                },
                priority=1000,
                timeout=30
            )
            flow_actions.append(action)
        
        # Execute flow rules
        for action in flow_actions:
            try:
                result = ryu_connector.execute_flow_mod(action)
                # In simulation mode, this should succeed
                assert isinstance(result, dict)
            except Exception as e:
                # Expected if RYU is not running
                assert "Connection" in str(e) or "timeout" in str(e).lower()
        
        # Step 3: Verify network state
        topology = comnetsemu_connector.get_network_topology()
        assert topology is not None
        assert len(topology.switches) >= 1
    
    def test_scenario_2_qos_enforcement(self, ryu_connector, comnetsemu_connector):
        """
        Scenario 2: QoS Enforcement
        Configure different QoS policies for different traffic classes
        """
        # Step 1: Create QoS policies for different traffic classes
        qos_policies = [
            {
                "policy_id": "high_priority",
                "target_type": "switch",
                "target_id": "s1",
                "bandwidth_limit": 1000,  # 1 Gbps
                "latency_limit": 5,  # 5ms
                "packet_loss_limit": 0.001
            },
            {
                "policy_id": "medium_priority",
                "target_type": "switch",
                "target_id": "s1",
                "bandwidth_limit": 500,  # 500 Mbps
                "latency_limit": 10,  # 10ms
                "packet_loss_limit": 0.01
            },
            {
                "policy_id": "low_priority",
                "target_type": "switch",
                "target_id": "s1",
                "bandwidth_limit": 100,  # 100 Mbps
                "latency_limit": 50,  # 50ms
                "packet_loss_limit": 0.05
            }
        ]
        
        for policy in qos_policies:
            action = NetworkAction(
                id=f"scenario2_qos_{policy['policy_id']}",
                type=ActionType.CONFIG_CHANGE,
                target="s1",
                parameters={
                    "config_type": "qos",
                    "config_data": policy
                },
                priority=1000,
                timeout=30
            )
            
            result = comnetsemu_connector.execute_qos_policy(action)
            assert result["success"]
            assert result["policy_id"] == policy["policy_id"]
        
        # Step 2: Configure flow rules with QoS marking
        flow_actions = [
            {
                "match": {"eth_type": 2048, "ip_proto": 6, "tcp_dst": 22},  # SSH
                "dscp": 46,  # EF (Expedited Forwarding)
                "priority": 3000
            },
            {
                "match": {"eth_type": 2048, "ip_proto": 6, "tcp_dst": 80},  # HTTP
                "dscp": 26,  # AF31
                "priority": 2000
            },
            {
                "match": {"eth_type": 2048, "ip_proto": 6, "tcp_dst": 443},  # HTTPS
                "dscp": 26,  # AF31
                "priority": 2000
            }
        ]
        
        for idx, flow_spec in enumerate(flow_actions):
            action = NetworkAction(
                id=f"scenario2_flow_{idx}",
                type=ActionType.FLOW_MOD,
                target="1",
                parameters={
                    "operation": "add",
                    "match": flow_spec["match"],
                    "actions": [f"set_field:dscp={flow_spec['dscp']}", "output:1"],
                    "priority": flow_spec["priority"],
                    "idle_timeout": 0,
                    "hard_timeout": 0
                },
                priority=1000,
                timeout=30
            )
            
            try:
                result = ryu_connector.execute_flow_mod(action)
                assert isinstance(result, dict)
            except Exception as e:
                assert "Connection" in str(e) or "timeout" in str(e).lower()
    
    def test_scenario_3_load_balancing(self, ryu_connector, comnetsemu_connector):
        """
        Scenario 3: Load Balancing
        Distribute traffic across multiple servers
        """
        # Step 1: Create topology with multiple servers
        servers = ["server1", "server2", "server3"]
        for idx, server in enumerate(servers):
            action = NetworkAction(
                id=f"scenario3_topo_{server}",
                type=ActionType.CONFIG_CHANGE,
                target="network",
                parameters={
                    "config_type": "topology",
                    "config_data": {
                        "operation": "add",
                        "element_type": "host",
                        "element_id": server,
                        "properties": {
                            "ip": f"10.0.1.{10 + idx}",
                            "mac": f"00:00:00:00:01:{10 + idx:02x}"
                        }
                    }
                },
                priority=1000,
                timeout=30
            )
            
            result = comnetsemu_connector.execute_topology_change(action)
            assert result["success"]
        
        # Step 2: Configure load balancing flow rules
        # Round-robin distribution based on source IP hash
        for idx, server in enumerate(servers):
            action = NetworkAction(
                id=f"scenario3_lb_{server}",
                type=ActionType.FLOW_MOD,
                target="1",
                parameters={
                    "operation": "add",
                    "match": {
                        "eth_type": 2048,
                        "ip_dst": "10.0.1.100",  # Virtual IP
                        "ip_proto": 6,
                        "tcp_dst": 80
                    },
                    "actions": [
                        f"set_field:ip_dst=10.0.1.{10 + idx}",
                        f"set_field:eth_dst=00:00:00:00:01:{10 + idx:02x}",
                        f"output:{idx + 1}"
                    ],
                    "priority": 2000 + idx,
                    "idle_timeout": 0,
                    "hard_timeout": 0
                },
                priority=1000,
                timeout=30
            )
            
            try:
                result = ryu_connector.execute_flow_mod(action)
                assert isinstance(result, dict)
            except Exception as e:
                assert "Connection" in str(e) or "timeout" in str(e).lower()
        
        # Step 3: Verify topology
        topology = comnetsemu_connector.get_network_topology()
        assert len(topology.hosts) >= 3
    
    def test_scenario_4_firewall_rules(self, ryu_connector):
        """
        Scenario 4: Firewall Rules
        Implement security policies with flow rules
        """
        # Define firewall rules
        firewall_rules = [
            {
                "name": "block_ssh_external",
                "match": {"eth_type": 2048, "ip_proto": 6, "tcp_dst": 22, "ip_src": "0.0.0.0/0"},
                "action": "drop",
                "priority": 5000
            },
            {
                "name": "allow_http",
                "match": {"eth_type": 2048, "ip_proto": 6, "tcp_dst": 80},
                "action": "output:1",
                "priority": 4000
            },
            {
                "name": "allow_https",
                "match": {"eth_type": 2048, "ip_proto": 6, "tcp_dst": 443},
                "action": "output:1",
                "priority": 4000
            },
            {
                "name": "block_telnet",
                "match": {"eth_type": 2048, "ip_proto": 6, "tcp_dst": 23},
                "action": "drop",
                "priority": 5000
            },
            {
                "name": "allow_dns",
                "match": {"eth_type": 2048, "ip_proto": 17, "udp_dst": 53},
                "action": "output:1",
                "priority": 4000
            }
        ]
        
        for rule in firewall_rules:
            action = NetworkAction(
                id=f"scenario4_fw_{rule['name']}",
                type=ActionType.FLOW_MOD,
                target="1",
                parameters={
                    "operation": "add",
                    "match": rule["match"],
                    "actions": [rule["action"]],
                    "priority": rule["priority"],
                    "idle_timeout": 0,
                    "hard_timeout": 0
                },
                priority=1000,
                timeout=30
            )
            
            try:
                result = ryu_connector.execute_flow_mod(action)
                assert isinstance(result, dict)
            except Exception as e:
                assert "Connection" in str(e) or "timeout" in str(e).lower()
    
    def test_scenario_5_network_slicing(self, ryu_connector, comnetsemu_connector):
        """
        Scenario 5: Network Slicing
        Create isolated network slices with different characteristics
        """
        # Define network slices
        slices = [
            {
                "name": "eMBB",  # Enhanced Mobile Broadband
                "bandwidth": 1000,
                "latency": 10,
                "reliability": 0.99
            },
            {
                "name": "URLLC",  # Ultra-Reliable Low-Latency Communications
                "bandwidth": 100,
                "latency": 1,
                "reliability": 0.99999
            },
            {
                "name": "mMTC",  # Massive Machine-Type Communications
                "bandwidth": 10,
                "latency": 100,
                "reliability": 0.95
            }
        ]
        
        for idx, slice_spec in enumerate(slices):
            # Step 1: Create slice topology
            topo_action = NetworkAction(
                id=f"scenario5_topo_{slice_spec['name']}",
                type=ActionType.CONFIG_CHANGE,
                target="network",
                parameters={
                    "config_type": "topology",
                    "config_data": {
                        "operation": "add",
                        "element_type": "switch",
                        "element_id": f"s{idx + 10}",
                        "properties": {
                            "dpid": str(idx + 10),
                            "ports": 4,
                            "slice": slice_spec["name"]
                        }
                    }
                },
                priority=1000,
                timeout=30
            )
            
            result = comnetsemu_connector.execute_topology_change(topo_action)
            assert result["success"]
            
            # Step 2: Configure QoS for slice
            qos_action = NetworkAction(
                id=f"scenario5_qos_{slice_spec['name']}",
                type=ActionType.CONFIG_CHANGE,
                target=f"s{idx + 10}",
                parameters={
                    "config_type": "qos",
                    "config_data": {
                        "policy_id": f"slice_{slice_spec['name']}",
                        "target_type": "switch",
                        "target_id": f"s{idx + 10}",
                        "bandwidth_limit": slice_spec["bandwidth"],
                        "latency_limit": slice_spec["latency"],
                        "packet_loss_limit": 1 - slice_spec["reliability"]
                    }
                },
                priority=1000,
                timeout=30
            )
            
            result = comnetsemu_connector.execute_qos_policy(qos_action)
            assert result["success"]
            
            # Step 3: Configure flow rules for slice
            flow_action = NetworkAction(
                id=f"scenario5_flow_{slice_spec['name']}",
                type=ActionType.FLOW_MOD,
                target=str(idx + 10),
                parameters={
                    "operation": "add",
                    "match": {
                        "eth_type": 2048,
                        "ip_src": f"10.{idx}.0.0/16"
                    },
                    "actions": ["output:1"],
                    "priority": 3000 + idx,
                    "idle_timeout": 0,
                    "hard_timeout": 0
                },
                priority=1000,
                timeout=30
            )
            
            try:
                result = ryu_connector.execute_flow_mod(flow_action)
                assert isinstance(result, dict)
            except Exception as e:
                assert "Connection" in str(e) or "timeout" in str(e).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
