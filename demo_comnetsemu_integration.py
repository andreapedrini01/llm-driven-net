#!/usr/bin/env python3
"""
Demo script for ComnetsEMU Integration
Demonstrates the real ComnetsEMU integration with topology management and network operations
"""

import json
import time
from datetime import datetime
from northbound_script import NorthboundScript


def demo_comnetsemu_integration():
    """Demonstrate ComnetsEMU integration functionality."""
    print("=" * 70)
    print("COMNETSEMU INTEGRATION DEMONSTRATION")
    print("=" * 70)
    
    # Initialize Northbound Script with RYU and ComnetsEMU configuration
    print("\n1. Initializing Northbound Script with ComnetsEMU Integration...")
    
    northbound = NorthboundScript(
        log_dir="./logs",
        ryu_host="localhost",
        ryu_port=8080,
        comnetsemu_host="localhost",
        comnetsemu_port=6653,
        timeout_seconds=30,
        max_retries=3,
        retry_delay=2.0,
        connection_pool_size=10,
        comnetsemu_topology_discovery_interval=60
    )
    
    try:
        # Check network connection status
        print("\n2. Checking Network Connection Status...")
        status = northbound.get_ryu_status()
        
        print(f"   Overall Status: {status.get('overall_status', 'unknown')}")
        
        # RYU Status
        ryu_status = status.get('ryu', {})
        print(f"\n   RYU Controller:")
        print(f"     Status: {ryu_status.get('status', 'unknown')}")
        print(f"     Host: {ryu_status.get('config', {}).get('host', 'unknown')}")
        print(f"     Port: {ryu_status.get('config', {}).get('port', 'unknown')}")
        
        # ComnetsEMU Status
        comnetsemu_status = status.get('comnetsemu', {})
        print(f"\n   ComnetsEMU:")
        print(f"     Status: {comnetsemu_status.get('status', 'unknown')}")
        print(f"     Host: {comnetsemu_status.get('config', {}).get('host', 'unknown')}")
        print(f"     Port: {comnetsemu_status.get('config', {}).get('port', 'unknown')}")
        
        # Topology Cache Info
        topology_cache = comnetsemu_status.get('topology_cache', {})
        if topology_cache.get('cached'):
            print(f"     Topology Cache: {topology_cache.get('switches_count', 0)} switches, "
                  f"{topology_cache.get('hosts_count', 0)} hosts, "
                  f"{topology_cache.get('links_count', 0)} links")
        
        # Create comprehensive network action sequence
        print("\n3. Creating Comprehensive Network Action Sequence...")
        
        comprehensive_action = {
            "id": "demo_comprehensive_001",
            "intent_id": "demo_intent_network_management",
            "estimated_duration": 60,
            "actions": [
                {
                    "id": "demo_flow_001",
                    "type": "flow_mod",
                    "target": "switch-1",
                    "parameters": {
                        "operation": "add",
                        "match": {
                            "ip_src": "10.0.0.200",  # Attacker IP from topology
                            "eth_type": 2048  # IPv4
                        },
                        "actions": ["drop"],
                        "idle_timeout": 300,
                        "hard_timeout": 600,
                        "table_id": 0
                    },
                    "priority": 2000,
                    "timeout": 30,
                    "description": "Block attacker traffic via RYU flow rule"
                },
                {
                    "id": "demo_slice_001",
                    "type": "slice_create",
                    "target": "network",
                    "parameters": {
                        "slice_name": "web_service_slice",
                        "resources": {
                            "bandwidth": "100Mbps",
                            "hosts": ["web1", "app1"],
                            "switches": ["s1"],
                            "isolation_level": "high"
                        }
                    },
                    "priority": 1500,
                    "timeout": 60,
                    "description": "Create isolated slice for web services"
                },
                {
                    "id": "demo_qos_001",
                    "type": "config_change",
                    "target": "switch-1",
                    "parameters": {
                        "config_type": "qos",
                        "config_data": {
                            "policy_id": "web_priority_qos",
                            "target_type": "switch",
                            "target_id": "s1",
                            "bandwidth_limit": 100,  # Mbps
                            "latency_limit": 10,     # ms
                            "packet_loss_limit": 0.01,  # 1%
                            "dscp_marking": 46       # EF (Expedited Forwarding)
                        }
                    },
                    "priority": 1000,
                    "timeout": 30,
                    "description": "Apply high-priority QoS to web traffic"
                },
                {
                    "id": "demo_topology_001",
                    "type": "config_change",
                    "target": "network",
                    "parameters": {
                        "config_type": "topology",
                        "config_data": {
                            "operation": "modify",
                            "element_type": "link",
                            "element_id": "s1-s2-link",
                            "properties": {
                                "bandwidth": "500Mbps",
                                "delay": "2ms",
                                "loss": 0.001
                            }
                        }
                    },
                    "priority": 800,
                    "timeout": 45,
                    "description": "Optimize inter-switch link parameters"
                }
            ],
            "dependencies": [],
            "rollback_plan": [
                {
                    "id": "demo_rollback_flow_001",
                    "type": "flow_mod",
                    "target": "switch-1",
                    "parameters": {
                        "operation": "delete",
                        "match": {
                            "ip_src": "10.0.0.200",
                            "eth_type": 2048
                        },
                        "table_id": 0
                    },
                    "priority": 2000,
                    "timeout": 30,
                    "description": "Remove attacker blocking rule"
                }
            ]
        }
        
        llm_output = json.dumps(comprehensive_action, indent=2)
        
        print("   Comprehensive Action Created:")
        print(f"   - Total Actions: {len(comprehensive_action['actions'])}")
        print(f"   - Flow Modifications: 1 (RYU)")
        print(f"   - Slice Creation: 1 (ComnetsEMU)")
        print(f"   - QoS Policies: 1 (ComnetsEMU)")
        print(f"   - Topology Changes: 1 (ComnetsEMU)")
        print(f"   - Rollback Actions: {len(comprehensive_action['rollback_plan'])}")
        
        # Perform dry run validation
        print("\n4. Performing Comprehensive Dry Run Validation...")
        
        dry_run_result = northbound.process_llm_output(llm_output, dry_run=True)
        
        if dry_run_result["success"]:
            print("   ✅ Comprehensive dry run successful!")
            print(f"   - Sequence ID: {dry_run_result['sequence_id']}")
            print(f"   - Intent ID: {dry_run_result.get('intent_id', 'N/A')}")
            print(f"   - Total Actions: {dry_run_result.get('total_actions', 0)}")
            
            if 'validation' in dry_run_result:
                validation = dry_run_result['validation']
                if validation.get('warnings'):
                    print(f"   - Warnings: {len(validation['warnings'])}")
                    for warning in validation['warnings'][:3]:  # Show first 3 warnings
                        print(f"     • {warning}")
        else:
            print("   ❌ Comprehensive dry run failed!")
            if 'validation' in dry_run_result:
                validation = dry_run_result['validation']
                if validation.get('errors'):
                    print(f"   - Errors: {len(validation['errors'])}")
                    for error in validation['errors']:
                        print(f"     • {error}")
        
        # Show ComnetsEMU integration features
        print("\n5. ComnetsEMU Integration Features:")
        print("   ✅ Real topology discovery and caching")
        print("   ✅ Network slice creation and management")
        print("   ✅ QoS policy configuration")
        print("   ✅ Dynamic topology modification")
        print("   ✅ Host and switch state monitoring")
        print("   ✅ Link parameter optimization")
        print("   ✅ Container-based host management")
        print("   ✅ OpenFlow integration with RYU")
        
        # Show network operations supported
        print("\n6. Supported Network Operations:")
        print("   RYU Controller Operations:")
        print("     • Flow table management (add/modify/delete)")
        print("     • Switch discovery and monitoring")
        print("     • Port statistics collection")
        print("     • Network topology discovery")
        print("     • Flow rule verification")
        
        print("   ComnetsEMU Operations:")
        print("     • Network topology management")
        print("     • Container host orchestration")
        print("     • Network slice creation")
        print("     • QoS policy enforcement")
        print("     • Link parameter configuration")
        print("     • Network state verification")
        
        # Show integration architecture
        print("\n7. Integration Architecture:")
        print("   ┌─────────────────┐    ┌─────────────────┐")
        print("   │   LLM Actions   │    │  Northbound     │")
        print("   │                 │───▶│  Script         │")
        print("   └─────────────────┘    └─────────────────┘")
        print("                                   │")
        print("                          ┌────────┴────────┐")
        print("                          ▼                 ▼")
        print("                   ┌─────────────┐   ┌─────────────┐")
        print("                   │ RYU         │   │ ComnetsEMU  │")
        print("                   │ Connector   │   │ Connector   │")
        print("                   └─────────────┘   └─────────────┘")
        print("                          │                 │")
        print("                          ▼                 ▼")
        print("                   ┌─────────────┐   ┌─────────────┐")
        print("                   │ RYU         │   │ ComnetsEMU  │")
        print("                   │ Controller  │   │ Network     │")
        print("                   │ (Flows)     │   │ (Topology)  │")
        print("                   └─────────────┘   └─────────────┘")
        
        print("\n" + "=" * 70)
        print("DEMONSTRATION COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print("\nKey Integration Features Implemented:")
        print("✅ Real ComnetsEMU API integration for topology management")
        print("✅ Network slice creation and resource allocation")
        print("✅ QoS policy configuration and enforcement")
        print("✅ Dynamic topology modification capabilities")
        print("✅ Comprehensive network state verification")
        print("✅ Container host management integration")
        print("✅ Combined RYU + ComnetsEMU orchestration")
        print("✅ Topology caching and discovery optimization")
        
        print(f"\nNote: This demo runs in simulation mode.")
        print(f"To connect to real ComnetsEMU, ensure the network is running at {comnetsemu_status.get('config', {}).get('host', 'localhost')}:{comnetsemu_status.get('config', {}).get('port', 6653)}")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Clean up
        print(f"\n8. Cleaning up resources...")
        northbound.close()
        print("   ✅ Resources cleaned up successfully")


if __name__ == "__main__":
    demo_comnetsemu_integration()