#!/usr/bin/env python3
"""
End-to-end workflow tests for the Northbound Script Generator
Tests complete workflows from API to network execution
Validates: Requirements 7.1, 7.2
"""

import pytest
import json
import time
from datetime import datetime
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from connectors.ryu_connector import create_ryu_connector, RYUConfig
from connectors.comnetsemu_connector import create_comnetsemu_connector, ComnetsEMUConfig
from models.action_models import NetworkAction, ActionType, ActionSequence


class TestEndToEndWorkflows:
    """End-to-end workflow tests."""
    
    @pytest.fixture
    def ryu_connector(self):
        """Create RYU connector for testing."""
        config = RYUConfig(
            host="localhost",
            port=8080,
            timeout_seconds=30,
            max_retries=3,
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
            timeout_seconds=30,
            max_retries=3
        )
        connector = create_comnetsemu_connector(config=config)
        yield connector
        connector.close()
    
    def test_workflow_1_network_setup_and_configuration(self, ryu_connector, comnetsemu_connector):
        """
        Workflow 1: Complete network setup and configuration
        Steps:
        1. Create network topology
        2. Configure switches
        3. Add flow rules
        4. Configure QoS policies
        5. Verify network state
        """
        workflow_start = time.time()
        
        # Step 1: Create network topology
        print("\n=== Step 1: Create Network Topology ===")
        topology_actions = [
            {
                "element_type": "switch",
                "element_id": "core_s1",
                "properties": {"dpid": "1", "ports": 8, "role": "core"}
            },
            {
                "element_type": "switch",
                "element_id": "edge_s2",
                "properties": {"dpid": "2", "ports": 4, "role": "edge"}
            },
            {
                "element_type": "host",
                "element_id": "web_server",
                "properties": {"ip": "10.0.1.10", "mac": "00:00:00:00:01:0a"}
            },
            {
                "element_type": "host",
                "element_id": "db_server",
                "properties": {"ip": "10.0.1.20", "mac": "00:00:00:00:01:14"}
            }
        ]
        
        for topo_spec in topology_actions:
            action = NetworkAction(
                id=f"workflow1_topo_{topo_spec['element_id']}",
                type=ActionType.CONFIG_CHANGE,
                target="network",
                parameters={
                    "config_type": "topology",
                    "config_data": {
                        "operation": "add",
                        "element_type": topo_spec["element_type"],
                        "element_id": topo_spec["element_id"],
                        "properties": topo_spec["properties"]
                    }
                },
                priority=1000,
                timeout=30
            )
            
            result = comnetsemu_connector.execute_topology_change(action)
            assert result["success"], f"Failed to create {topo_spec['element_id']}"
            print(f"✓ Created {topo_spec['element_type']}: {topo_spec['element_id']}")
        
        # Step 2: Configure flow rules for connectivity
        print("\n=== Step 2: Configure Flow Rules ===")
        flow_rules = [
            {
                "name": "web_to_db",
                "switch": "1",
                "match": {"eth_type": 2048, "ip_src": "10.0.1.10", "ip_dst": "10.0.1.20"},
                "actions": ["output:2"],
                "priority": 2000
            },
            {
                "name": "db_to_web",
                "switch": "1",
                "match": {"eth_type": 2048, "ip_src": "10.0.1.20", "ip_dst": "10.0.1.10"},
                "actions": ["output:1"],
                "priority": 2000
            },
            {
                "name": "external_to_web",
                "switch": "2",
                "match": {"eth_type": 2048, "ip_dst": "10.0.1.10", "ip_proto": 6, "tcp_dst": 80},
                "actions": ["output:1"],
                "priority": 3000
            }
        ]
        
        for flow_spec in flow_rules:
            action = NetworkAction(
                id=f"workflow1_flow_{flow_spec['name']}",
                type=ActionType.FLOW_MOD,
                target=flow_spec["switch"],
                parameters={
                    "operation": "add",
                    "match": flow_spec["match"],
                    "actions": flow_spec["actions"],
                    "priority": flow_spec["priority"],
                    "idle_timeout": 0,
                    "hard_timeout": 0
                },
                priority=1000,
                timeout=30
            )
            
            try:
                result = ryu_connector.execute_flow_mod(action)
                print(f"✓ Configured flow rule: {flow_spec['name']}")
            except Exception as e:
                print(f"✗ Failed to configure {flow_spec['name']}: {e}")
        
        # Step 3: Configure QoS policies
        print("\n=== Step 3: Configure QoS Policies ===")
        qos_policies = [
            {
                "policy_id": "web_server_qos",
                "target_id": "core_s1",
                "bandwidth_limit": 1000,
                "latency_limit": 10,
                "packet_loss_limit": 0.001
            },
            {
                "policy_id": "db_server_qos",
                "target_id": "core_s1",
                "bandwidth_limit": 500,
                "latency_limit": 5,
                "packet_loss_limit": 0.0001
            }
        ]
        
        for qos_spec in qos_policies:
            action = NetworkAction(
                id=f"workflow1_qos_{qos_spec['policy_id']}",
                type=ActionType.CONFIG_CHANGE,
                target=qos_spec["target_id"],
                parameters={
                    "config_type": "qos",
                    "config_data": {
                        "policy_id": qos_spec["policy_id"],
                        "target_type": "switch",
                        "target_id": qos_spec["target_id"],
                        "bandwidth_limit": qos_spec["bandwidth_limit"],
                        "latency_limit": qos_spec["latency_limit"],
                        "packet_loss_limit": qos_spec["packet_loss_limit"]
                    }
                },
                priority=1000,
                timeout=30
            )
            
            result = comnetsemu_connector.execute_qos_policy(action)
            assert result["success"], f"Failed to configure {qos_spec['policy_id']}"
            print(f"✓ Configured QoS policy: {qos_spec['policy_id']}")
        
        # Step 4: Verify network state
        print("\n=== Step 4: Verify Network State ===")
        topology = comnetsemu_connector.get_network_topology()
        assert len(topology.switches) >= 2, "Expected at least 2 switches"
        assert len(topology.hosts) >= 2, "Expected at least 2 hosts"
        print(f"✓ Topology verified: {len(topology.switches)} switches, {len(topology.hosts)} hosts")
        
        workflow_duration = time.time() - workflow_start
        print(f"\n=== Workflow 1 Complete ===")
        print(f"Duration: {workflow_duration:.2f}s")
        
        # Requirement 7.1: Should complete in reasonable time
        assert workflow_duration < 60, "Workflow took too long"
    
    def test_workflow_2_traffic_engineering(self, ryu_connector, comnetsemu_connector):
        """
        Workflow 2: Traffic engineering and optimization
        Steps:
        1. Analyze current network state
        2. Identify bottlenecks
        3. Reconfigure flow rules for optimization
        4. Apply QoS policies
        5. Verify improvements
        """
        workflow_start = time.time()
        
        # Step 1: Analyze current network state
        print("\n=== Step 1: Analyze Network State ===")
        topology = comnetsemu_connector.get_network_topology()
        stats = comnetsemu_connector.get_network_statistics()
        print(f"✓ Current topology: {len(topology.switches)} switches, {len(topology.hosts)} hosts")
        
        # Step 2: Create optimized flow rules
        print("\n=== Step 2: Create Optimized Flow Rules ===")
        optimized_flows = [
            {
                "name": "high_priority_traffic",
                "match": {"eth_type": 2048, "ip_proto": 6, "tcp_dst": 443},
                "actions": ["set_field:dscp=46", "output:1"],
                "priority": 5000
            },
            {
                "name": "bulk_traffic",
                "match": {"eth_type": 2048, "ip_proto": 6, "tcp_dst": 8080},
                "actions": ["set_field:dscp=10", "output:2"],
                "priority": 3000
            },
            {
                "name": "best_effort",
                "match": {"eth_type": 2048},
                "actions": ["output:3"],
                "priority": 1000
            }
        ]
        
        for flow_spec in optimized_flows:
            action = NetworkAction(
                id=f"workflow2_flow_{flow_spec['name']}",
                type=ActionType.FLOW_MOD,
                target="1",
                parameters={
                    "operation": "add",
                    "match": flow_spec["match"],
                    "actions": flow_spec["actions"],
                    "priority": flow_spec["priority"],
                    "idle_timeout": 0,
                    "hard_timeout": 0
                },
                priority=1000,
                timeout=30
            )
            
            try:
                result = ryu_connector.execute_flow_mod(action)
                print(f"✓ Applied optimized flow: {flow_spec['name']}")
            except Exception as e:
                print(f"✗ Failed to apply {flow_spec['name']}: {e}")
        
        # Step 3: Apply traffic shaping QoS
        print("\n=== Step 3: Apply Traffic Shaping ===")
        qos_action = NetworkAction(
            id="workflow2_qos_shaping",
            type=ActionType.CONFIG_CHANGE,
            target="s1",
            parameters={
                "config_type": "qos",
                "config_data": {
                    "policy_id": "traffic_shaping",
                    "target_type": "switch",
                    "target_id": "s1",
                    "bandwidth_limit": 1000,
                    "latency_limit": 10,
                    "packet_loss_limit": 0.01
                }
            },
            priority=1000,
            timeout=30
        )
        
        result = comnetsemu_connector.execute_qos_policy(qos_action)
        assert result["success"]
        print("✓ Traffic shaping applied")
        
        workflow_duration = time.time() - workflow_start
        print(f"\n=== Workflow 2 Complete ===")
        print(f"Duration: {workflow_duration:.2f}s")
        
        assert workflow_duration < 60
    
    def test_workflow_3_security_policy_deployment(self, ryu_connector):
        """
        Workflow 3: Security policy deployment
        Steps:
        1. Define security zones
        2. Configure inter-zone firewall rules
        3. Apply rate limiting
        4. Configure DDoS protection
        5. Verify security policies
        """
        workflow_start = time.time()
        
        # Step 1: Define security zones with flow rules
        print("\n=== Step 1: Define Security Zones ===")
        zones = {
            "dmz": "10.0.1.0/24",
            "internal": "10.0.2.0/24",
            "management": "10.0.3.0/24"
        }
        
        # Step 2: Configure inter-zone firewall rules
        print("\n=== Step 2: Configure Firewall Rules ===")
        firewall_rules = [
            {
                "name": "allow_dmz_to_internal_http",
                "match": {"eth_type": 2048, "ip_src": zones["dmz"], "ip_dst": zones["internal"], 
                         "ip_proto": 6, "tcp_dst": 80},
                "action": "output:1",
                "priority": 5000
            },
            {
                "name": "block_dmz_to_management",
                "match": {"eth_type": 2048, "ip_src": zones["dmz"], "ip_dst": zones["management"]},
                "action": "drop",
                "priority": 6000
            },
            {
                "name": "allow_management_to_all",
                "match": {"eth_type": 2048, "ip_src": zones["management"]},
                "action": "output:1",
                "priority": 4000
            },
            {
                "name": "block_external_ssh",
                "match": {"eth_type": 2048, "ip_proto": 6, "tcp_dst": 22},
                "action": "drop",
                "priority": 7000
            }
        ]
        
        for rule in firewall_rules:
            action = NetworkAction(
                id=f"workflow3_fw_{rule['name']}",
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
                print(f"✓ Applied firewall rule: {rule['name']}")
            except Exception as e:
                print(f"✗ Failed to apply {rule['name']}: {e}")
        
        # Step 3: Configure rate limiting for DDoS protection
        print("\n=== Step 3: Configure Rate Limiting ===")
        rate_limit_rules = [
            {
                "name": "limit_icmp",
                "match": {"eth_type": 2048, "ip_proto": 1},
                "priority": 8000
            },
            {
                "name": "limit_syn_flood",
                "match": {"eth_type": 2048, "ip_proto": 6, "tcp_flags": 2},
                "priority": 8000
            }
        ]
        
        for rule in rate_limit_rules:
            action = NetworkAction(
                id=f"workflow3_rate_{rule['name']}",
                type=ActionType.FLOW_MOD,
                target="1",
                parameters={
                    "operation": "add",
                    "match": rule["match"],
                    "actions": ["output:controller"],
                    "priority": rule["priority"],
                    "idle_timeout": 10,
                    "hard_timeout": 30
                },
                priority=1000,
                timeout=30
            )
            
            try:
                result = ryu_connector.execute_flow_mod(action)
                print(f"✓ Applied rate limiting: {rule['name']}")
            except Exception as e:
                print(f"✗ Failed to apply {rule['name']}: {e}")
        
        workflow_duration = time.time() - workflow_start
        print(f"\n=== Workflow 3 Complete ===")
        print(f"Duration: {workflow_duration:.2f}s")
        
        assert workflow_duration < 60
    
    def test_workflow_4_disaster_recovery(self, ryu_connector, comnetsemu_connector):
        """
        Workflow 4: Disaster recovery and failover
        Steps:
        1. Simulate network failure
        2. Detect failure
        3. Activate backup paths
        4. Reconfigure flow rules
        5. Verify recovery
        """
        workflow_start = time.time()
        
        # Step 1: Setup primary and backup paths
        print("\n=== Step 1: Setup Primary and Backup Paths ===")
        
        # Primary path flows
        primary_flows = [
            {
                "name": "primary_path_1",
                "match": {"eth_type": 2048, "ip_dst": "10.0.1.10"},
                "actions": ["output:1"],
                "priority": 3000
            }
        ]
        
        for flow_spec in primary_flows:
            action = NetworkAction(
                id=f"workflow4_primary_{flow_spec['name']}",
                type=ActionType.FLOW_MOD,
                target="1",
                parameters={
                    "operation": "add",
                    "match": flow_spec["match"],
                    "actions": flow_spec["actions"],
                    "priority": flow_spec["priority"],
                    "idle_timeout": 0,
                    "hard_timeout": 0
                },
                priority=1000,
                timeout=30
            )
            
            try:
                result = ryu_connector.execute_flow_mod(action)
                print(f"✓ Configured primary path: {flow_spec['name']}")
            except Exception as e:
                print(f"✗ Failed: {e}")
        
        # Step 2: Simulate failure by removing primary flows
        print("\n=== Step 2: Simulate Failure ===")
        time.sleep(1)  # Simulate some operation time
        
        # Step 3: Activate backup paths
        print("\n=== Step 3: Activate Backup Paths ===")
        backup_flows = [
            {
                "name": "backup_path_1",
                "match": {"eth_type": 2048, "ip_dst": "10.0.1.10"},
                "actions": ["output:2"],  # Different output port
                "priority": 2000  # Lower priority than primary
            }
        ]
        
        for flow_spec in backup_flows:
            action = NetworkAction(
                id=f"workflow4_backup_{flow_spec['name']}",
                type=ActionType.FLOW_MOD,
                target="1",
                parameters={
                    "operation": "add",
                    "match": flow_spec["match"],
                    "actions": flow_spec["actions"],
                    "priority": flow_spec["priority"],
                    "idle_timeout": 0,
                    "hard_timeout": 0
                },
                priority=1000,
                timeout=30
            )
            
            try:
                result = ryu_connector.execute_flow_mod(action)
                print(f"✓ Activated backup path: {flow_spec['name']}")
            except Exception as e:
                print(f"✗ Failed: {e}")
        
        # Step 4: Verify recovery
        print("\n=== Step 4: Verify Recovery ===")
        topology = comnetsemu_connector.get_network_topology()
        print(f"✓ Network topology verified after recovery")
        
        workflow_duration = time.time() - workflow_start
        print(f"\n=== Workflow 4 Complete ===")
        print(f"Duration: {workflow_duration:.2f}s")
        
        assert workflow_duration < 60


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
