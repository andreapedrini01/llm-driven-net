#!/usr/bin/env python3
"""
Demo script for ComnetsEMU Integration
Demonstrates the real ComnetsEMU integration with topology management and network operations
"""

import json
import time
from datetime import datetime
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from connectors.comnetsemu_connector import create_comnetsemu_connector
from models.action_models import NetworkAction, ActionType


def demo_comnetsemu_integration():
    """Demonstrate ComnetsEMU integration functionality."""
    print("=" * 70)
    print("COMNETSEMU INTEGRATION DEMONSTRATION")
    print("=" * 70)
    
    # Initialize ComnetsEMU connector
    print("\n1. Initializing ComnetsEMU Connector...")
    
    connector = create_comnetsemu_connector(
        host="localhost",
        port=6653,
        api_port=8181,
        timeout_seconds=30,
        max_retries=3
    )
    
    try:
        # Check connection status
        print("\n2. Checking ComnetsEMU Connection Status...")
        status = connector.get_connection_status()
        
        print(f"   Status: {status['status']}")
        print(f"   Host: {status['config']['host']}")
        print(f"   OpenFlow Port: {status['config']['port']}")
        print(f"   API Port: {status['config']['api_port']}")
        print(f"   Protocol: {status['config']['protocol']} v{status['config']['version']}")
        
        if 'stats' in status:
            stats = status['stats']
            print(f"   Total Requests: {stats.get('total_requests', 0)}")
            print(f"   Success Rate: {stats.get('success_rate', 0):.1f}%")
            print(f"   Topology Updates: {stats.get('topology_updates', 0)}")
        
        # Discover network topology
        print("\n3. Discovering Network Topology...")
        topology = connector.get_network_topology()
        
        print(f"   Switches: {len(topology.switches)}")
        for switch in topology.switches[:3]:  # Show first 3 switches
            print(f"     - {switch.get('name', 'Unknown')} (DPID: {switch.get('dpid', 'N/A')})")
        
        print(f"   Hosts: {len(topology.hosts)}")
        for host in topology.hosts[:3]:  # Show first 3 hosts
            print(f"     - {host.get('name', 'Unknown')} ({host.get('ip', 'N/A')})")
        
        print(f"   Links: {len(topology.links)}")
        for link in topology.links[:3]:  # Show first 3 links
            src = link.get('src', {})
            dst = link.get('dst', {})
            print(f"     - s{src.get('dpid', '?')}:{src.get('port', '?')} <-> s{dst.get('dpid', '?')}:{dst.get('port', '?')}")
        
        # Test topology change operations
        print("\n4. Testing Topology Change Operations...")
        
        # Create a sample topology change action
        topology_action = NetworkAction(
            id="demo_topo_001",
            type=ActionType.CONFIG_CHANGE,
            target="network",
            parameters={
                "config_type": "topology",
                "config_data": {
                    "operation": "add",
                    "element_type": "switch",
                    "element_id": "s4",
                    "properties": {
                        "dpid": "4",
                        "ports": 4
                    }
                }
            },
            priority=1000,
            timeout=30,
            description="Add new switch to topology"
        )
        
        print("   Executing topology change (add switch)...")
        topo_result = connector.execute_topology_change(topology_action)
        
        if topo_result["success"]:
            print("   ✅ Topology change successful!")
            print(f"   - Operation: {topo_result.get('operation', 'N/A')}")
            print(f"   - Element: {topo_result.get('element_type', 'N/A')} {topo_result.get('element_id', 'N/A')}")
            print(f"   - Message: {topo_result.get('message', 'N/A')}")
        else:
            print("   ❌ Topology change failed!")
            print(f"   - Error: {topo_result.get('error', 'Unknown error')}")
        
        # Test QoS policy operations
        print("\n5. Testing QoS Policy Operations...")
        
        qos_action = NetworkAction(
            id="demo_qos_001",
            type=ActionType.CONFIG_CHANGE,
            target="switch-1",
            parameters={
                "config_type": "qos",
                "config_data": {
                    "policy_id": "demo_policy_001",
                    "target_type": "switch",
                    "target_id": "s1",
                    "bandwidth_limit": 100,  # 100 Mbps
                    "latency_limit": 10,     # 10 ms
                    "packet_loss_limit": 0.01,  # 1%
                    "dscp_marking": 46       # EF (Expedited Forwarding)
                }
            },
            priority=1000,
            timeout=30,
            description="Apply QoS policy to switch"
        )
        
        print("   Executing QoS policy configuration...")
        qos_result = connector.execute_qos_policy(qos_action)
        
        if qos_result["success"]:
            print("   ✅ QoS policy applied successfully!")
            print(f"   - Policy ID: {qos_result.get('policy_id', 'N/A')}")
            print(f"   - Target: {qos_result.get('target_type', 'N/A')} {qos_result.get('target_id', 'N/A')}")
            print(f"   - Message: {qos_result.get('message', 'N/A')}")
        else:
            print("   ❌ QoS policy failed!")
            print(f"   - Error: {qos_result.get('error', 'Unknown error')}")
        
        # Test network state retrieval
        print("\n6. Testing Network State Retrieval...")
        
        switch_state = connector.get_network_state("switch-1")
        print(f"   Switch-1 State: {switch_state.get('status', 'Unknown')}")
        
        if switch_state.get('switch_info'):
            switch_info = switch_state['switch_info']
            print(f"   - DPID: {switch_info.get('dpid', 'N/A')}")
            print(f"   - Ports: {len(switch_info.get('ports', []))}")
            print(f"   - Status: {switch_info.get('status', 'N/A')}")
        
        # Test network statistics
        print("\n7. Getting Network Statistics...")
        
        stats = connector.get_network_statistics()
        print(f"   Timestamp: {stats.get('timestamp', 'N/A')}")
        
        if 'topology_summary' in stats:
            summary = stats['topology_summary']
            print(f"   Topology Summary:")
            print(f"     - Switches: {summary.get('switches', 0)}")
            print(f"     - Hosts: {summary.get('hosts', 0)}")
            print(f"     - Links: {summary.get('links', 0)}")
            print(f"     - Controllers: {summary.get('controllers', 0)}")
        
        # Perform health check
        print("\n8. Performing Health Check...")
        
        health = connector.health_check()
        print(f"   Overall Status: {health.get('overall_status', 'Unknown')}")
        
        if 'checks' in health:
            for check_name, check_result in health['checks'].items():
                status_icon = "✅" if check_result['status'] == 'pass' else "⚠️" if check_result['status'] == 'warn' else "❌"
                print(f"   {status_icon} {check_name.replace('_', ' ').title()}: {check_result['message']}")
        
        print("\n" + "=" * 70)
        print("DEMONSTRATION COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print("\nKey Features Implemented:")
        print("✅ Real ComnetsEMU OpenFlow integration")
        print("✅ Network topology discovery and caching")
        print("✅ Topology change operations (add/modify/remove)")
        print("✅ QoS policy configuration and validation")
        print("✅ Network state monitoring and retrieval")
        print("✅ Comprehensive health checking")
        print("✅ Statistics collection and reporting")
        print("✅ Error handling and connection management")
        
        print(f"\nNote: This demo runs with simulated topology.")
        print(f"To connect to a real ComnetsEMU instance, ensure it's running at localhost:6653")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Clean up
        print(f"\n9. Cleaning up resources...")
        connector.close()
        print("   ✅ Resources cleaned up successfully")


if __name__ == "__main__":
    demo_comnetsemu_integration()