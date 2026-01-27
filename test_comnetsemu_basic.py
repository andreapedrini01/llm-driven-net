#!/usr/bin/env python3
"""
Basic test for ComnetsEMU connector
"""

from comnetsemu_connector import create_comnetsemu_connector
import json

def test_comnetsemu_basic():
    """Test basic ComnetsEMU connector functionality."""
    print("Testing ComnetsEMU connector...")
    
    try:
        # Create connector
        connector = create_comnetsemu_connector()
        print("✅ ComnetsEMU connector created successfully")
        
        # Get status
        status = connector.get_connection_status()
        print(f"✅ Status: {status['status']}")
        
        # Get topology
        topology = connector.get_network_topology()
        print(f"✅ Topology discovered: {len(topology.switches)} switches, {len(topology.hosts)} hosts, {len(topology.links)} links")
        
        # Get network state
        state = connector.get_network_state("switch-1")
        print(f"✅ Network state retrieved for switch-1: {state['status']}")
        
        # Close connector
        connector.close()
        print("✅ ComnetsEMU connector closed successfully")
        
        print("\n🎉 All ComnetsEMU connector tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_comnetsemu_basic()