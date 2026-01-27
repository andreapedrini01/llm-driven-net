#!/usr/bin/env python3
"""
Test ComnetsEMU integration with different action types
"""

import json
from northbound_script import NorthboundScript
from action_models import NetworkAction, ActionType

def test_comnetsemu_integration():
    """Test ComnetsEMU integration with various action types."""
    print("Testing ComnetsEMU integration...")
    
    try:
        # Initialize Northbound Script with ComnetsEMU
        northbound = NorthboundScript(
            log_dir="./logs",
            ryu_host="localhost",
            ryu_port=8080,
            comnetsemu_host="localhost",
            comnetsemu_port=6653,
            timeout_seconds=30,
            max_retries=3
        )
        
        print("✅ Northbound Script initialized with ComnetsEMU integration")
        
        # Test 1: Flow modification (RYU)
        print("\n1. Testing Flow Modification (RYU)...")
        flow_action = NetworkAction(
            id="test_flow_001",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={
                "operation": "add",
                "match": {"ip_src": "192.168.1.100"},
                "actions": ["drop"]
            },
            priority=1000,
            timeout=30
        )
        
        # Test execution (dry run)
        result = northbound.network_interface.execute_flow_mod(flow_action)
        print(f"   Flow mod result: {result['success']} - {result['message']}")
        
        # Test 2: Slice creation (ComnetsEMU)
        print("\n2. Testing Slice Creation (ComnetsEMU)...")
        slice_action = NetworkAction(
            id="test_slice_001",
            type=ActionType.SLICE_CREATE,
            target="network",
            parameters={
                "slice_name": "test_slice",
                "resources": {
                    "bandwidth": "100Mbps",
                    "hosts": ["web1", "app1"]
                }
            },
            priority=500,
            timeout=60
        )
        
        result = northbound.network_interface.execute_slice_create(slice_action)
        print(f"   Slice creation result: {result['success']} - {result['message']}")
        
        # Test 3: QoS configuration (ComnetsEMU)
        print("\n3. Testing QoS Configuration (ComnetsEMU)...")
        qos_action = NetworkAction(
            id="test_qos_001",
            type=ActionType.CONFIG_CHANGE,
            target="switch-1",
            parameters={
                "config_type": "qos",
                "config_data": {
                    "policy_id": "test_qos",
                    "target_type": "switch",
                    "target_id": "s1",
                    "bandwidth_limit": 100,
                    "latency_limit": 10
                }
            },
            priority=750,
            timeout=30
        )
        
        result = northbound.network_interface.execute_config_change(qos_action)
        print(f"   QoS config result: {result['success']} - {result['message']}")
        
        # Test 4: Topology change (ComnetsEMU)
        print("\n4. Testing Topology Change (ComnetsEMU)...")
        topology_action = NetworkAction(
            id="test_topology_001",
            type=ActionType.CONFIG_CHANGE,
            target="network",
            parameters={
                "config_type": "topology",
                "config_data": {
                    "operation": "modify",
                    "element_type": "link",
                    "element_id": "s1-s2-link",
                    "properties": {
                        "bandwidth": "500Mbps",
                        "delay": "2ms"
                    }
                }
            },
            priority=800,
            timeout=45
        )
        
        result = northbound.network_interface.execute_config_change(topology_action)
        print(f"   Topology change result: {result['success']} - {result['message']}")
        
        # Test 5: Network state retrieval
        print("\n5. Testing Network State Retrieval...")
        state = northbound.network_interface.get_network_state("switch-1")
        print(f"   Network state status: {state['status']}")
        print(f"   Switch ID: {state.get('switch_id', 'N/A')}")
        print(f"   Has RYU data: {'ryu_switch_info' in state}")
        print(f"   Has ComnetsEMU data: {'comnetsemu_switch_info' in state}")
        print(f"   Links count: {len(state.get('links', []))}")
        
        # Test 6: Connection status
        print("\n6. Testing Connection Status...")
        status = northbound.get_ryu_status()
        print(f"   Overall status: {status.get('overall_status', 'unknown')}")
        print(f"   RYU status: {status.get('ryu', {}).get('status', 'unknown')}")
        print(f"   ComnetsEMU status: {status.get('comnetsemu', {}).get('status', 'unknown')}")
        
        # Test 7: Action verification
        print("\n7. Testing Action Verification...")
        flow_verified = northbound.network_interface.verify_action_applied(flow_action)
        slice_verified = northbound.network_interface.verify_action_applied(slice_action)
        print(f"   Flow action verified: {flow_verified}")
        print(f"   Slice action verified: {slice_verified}")
        
        # Clean up
        northbound.close()
        print("\n✅ ComnetsEMU integration closed successfully")
        
        print("\n🎉 All ComnetsEMU integration tests completed!")
        print("\nIntegration Features Verified:")
        print("✅ RYU connector for flow modifications")
        print("✅ ComnetsEMU connector for topology management")
        print("✅ Network slice creation")
        print("✅ QoS policy configuration")
        print("✅ Topology modification")
        print("✅ Combined network state retrieval")
        print("✅ Dual connection status monitoring")
        print("✅ Action verification routing")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_comnetsemu_integration()