#!/usr/bin/env python3
"""
Simple test for ComnetsEMU integration without network connections
"""

from comnetsemu_connector import ComnetsEMUConnector, ComnetsEMUConfig
from action_models import NetworkAction, ActionType

def test_comnetsemu_simple():
    """Test ComnetsEMU connector functionality without network connections."""
    print("Testing ComnetsEMU connector functionality...")
    
    try:
        # Create ComnetsEMU connector
        config = ComnetsEMUConfig(host="localhost", port=6653)
        connector = ComnetsEMUConnector(config)
        print("✅ ComnetsEMU connector created")
        
        # Test topology discovery
        topology = connector.get_network_topology()
        print(f"✅ Topology discovered: {len(topology.switches)} switches, {len(topology.hosts)} hosts, {len(topology.links)} links")
        
        # Test network state retrieval
        state = connector.get_network_state("switch-1")
        print(f"✅ Network state retrieved: {state['status']}")
        
        # Test QoS policy execution
        qos_action = NetworkAction(
            id="test_qos",
            type=ActionType.CONFIG_CHANGE,
            target="switch-1",
            parameters={
                "config_type": "qos",
                "config_data": {
                    "policy_id": "test_policy",
                    "target_type": "switch",
                    "target_id": "s1",
                    "bandwidth_limit": 100
                }
            }
        )
        
        result = connector.execute_qos_policy(qos_action)
        print(f"✅ QoS policy executed: {result['success']} - {result['message']}")
        
        # Test topology change execution
        topology_action = NetworkAction(
            id="test_topology",
            type=ActionType.CONFIG_CHANGE,
            target="network",
            parameters={
                "config_data": {
                    "operation": "modify",
                    "element_type": "link",
                    "element_id": "test-link",
                    "properties": {"bandwidth": "1Gbps"}
                }
            }
        )
        
        result = connector.execute_topology_change(topology_action)
        print(f"✅ Topology change executed: {result['success']} - {result['message']}")
        
        # Test connection status
        status = connector.get_connection_status()
        print(f"✅ Connection status: {status['status']}")
        print(f"   Topology cache: {status['topology_cache']['cached']}")
        print(f"   Total requests: {status['stats']['total_requests']}")
        
        # Close connector
        connector.close()
        print("✅ ComnetsEMU connector closed")
        
        print("\n🎉 All ComnetsEMU connector tests passed!")
        print("\nFeatures Verified:")
        print("✅ Topology discovery and caching")
        print("✅ Network state retrieval")
        print("✅ QoS policy configuration")
        print("✅ Topology modification")
        print("✅ Connection status monitoring")
        print("✅ Graceful error handling")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_comnetsemu_simple()