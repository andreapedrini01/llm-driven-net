"""Demo script for StateFileReader usage."""

import json
import time
import os
from datetime import datetime
from pathlib import Path

from src.services.state_file_reader import StateFileReader
from src.models.network import NetworkState


def create_sample_state_file(cache_folder: str, file_name: str):
    """Create a sample network state JSON file for testing."""
    sample_data = {
        "timestamp": datetime.now().isoformat(),
        "topology": {
            "switches": [
                {
                    "id": "switch_1",
                    "name": "Core Switch 1",
                    "dpid": "0000000000000001",
                    "ports": [1, 2, 3, 4],
                    "status": "active"
                },
                {
                    "id": "switch_2",
                    "name": "Edge Switch 1",
                    "dpid": "0000000000000002",
                    "ports": [1, 2, 3, 4],
                    "status": "active"
                }
            ],
            "links": [
                {
                    "id": "link_1",
                    "source_switch": "switch_1",
                    "source_port": 1,
                    "destination_switch": "switch_2",
                    "destination_port": 1,
                    "bandwidth": 1000,
                    "latency": 5.0,
                    "status": "active"
                }
            ],
            "hosts": [
                {
                    "id": "host_1",
                    "mac_address": "00:00:00:00:00:01",
                    "ip_address": "10.0.0.1",
                    "connected_switch": "switch_2",
                    "connected_port": 2,
                    "status": "active"
                },
                {
                    "id": "host_2",
                    "mac_address": "00:00:00:00:00:02",
                    "ip_address": "10.0.0.2",
                    "connected_switch": "switch_2",
                    "connected_port": 3,
                    "status": "active"
                }
            ]
        },
        "flows": [],
        "slices": [],
        "metrics": {
            "bandwidth": {
                "total_capacity": 10000,
                "used_bandwidth": 2500,
                "available_bandwidth": 7500,
                "utilization_percentage": 25.0
            },
            "latency": {
                "average_latency": 10.5,
                "min_latency": 5.0,
                "max_latency": 20.0,
                "jitter": 2.5
            },
            "utilization": {
                "cpu_utilization": 45.0,
                "memory_utilization": 60.0,
                "disk_utilization": 30.0
            }
        },
        "anomalies": []
    }
    
    # Ensure cache folder exists
    Path(cache_folder).mkdir(parents=True, exist_ok=True)
    
    # Write sample file
    file_path = os.path.join(cache_folder, file_name)
    with open(file_path, 'w') as f:
        json.dump(sample_data, f, indent=2)
    
    print(f"✓ Created sample state file: {file_path}")
    return file_path


def demo_basic_reading():
    """Demo: Basic file reading."""
    print("\n" + "="*60)
    print("DEMO 1: Basic File Reading")
    print("="*60)
    
    cache_folder = "./demo_cache"
    file_name = "network_state.json"
    
    # Create sample file
    create_sample_state_file(cache_folder, file_name)
    
    # Create reader
    reader = StateFileReader(
        cache_folder=cache_folder,
        state_file_name=file_name
    )
    
    # Load network state
    print("\nLoading network state...")
    state = reader.load_network_state()
    
    if state:
        print(f"✓ Successfully loaded network state")
        print(f"  - Switches: {len(state.topology.switches)}")
        print(f"  - Links: {len(state.topology.links)}")
        print(f"  - Hosts: {len(state.topology.hosts)}")
        print(f"  - Bandwidth utilization: {state.metrics.bandwidth.utilization_percentage}%")
    else:
        print("✗ Failed to load network state")


def demo_error_handling():
    """Demo: Error handling and retry logic."""
    print("\n" + "="*60)
    print("DEMO 2: Error Handling and Retry Logic")
    print("="*60)
    
    cache_folder = "./demo_cache"
    
    # Create reader
    reader = StateFileReader(
        cache_folder=cache_folder,
        state_file_name="nonexistent_file.json",
        max_retries=3,
        initial_backoff=0.5
    )
    
    # Try to read non-existent file
    print("\nAttempting to read non-existent file...")
    result = reader.read_json_file()
    
    print(f"  - Success: {result.success}")
    print(f"  - Error type: {result.error_type}")
    print(f"  - Attempts: {result.attempts}")
    print(f"  - Error message: {result.error}")


def demo_file_info():
    """Demo: Getting file information."""
    print("\n" + "="*60)
    print("DEMO 3: File Information")
    print("="*60)
    
    cache_folder = "./demo_cache"
    file_name = "network_state.json"
    
    # Ensure file exists
    create_sample_state_file(cache_folder, file_name)
    
    # Create reader
    reader = StateFileReader(
        cache_folder=cache_folder,
        state_file_name=file_name
    )
    
    # Get file info
    print("\nGetting file information...")
    info = reader.get_file_info()
    
    print(f"  - Path: {info['path']}")
    print(f"  - Exists: {info['exists']}")
    print(f"  - Readable: {info['readable']}")
    print(f"  - Size: {info['size_bytes']} bytes")
    print(f"  - Modified: {info['modified_time']}")
    print(f"  - Age: {info['age_seconds']:.2f} seconds")


def demo_file_watching():
    """Demo: File watching with automatic updates."""
    print("\n" + "="*60)
    print("DEMO 4: File Watching")
    print("="*60)
    
    cache_folder = "./demo_cache"
    file_name = "watched_state.json"
    
    # Create initial file
    file_path = create_sample_state_file(cache_folder, file_name)
    
    # Track callback invocations
    callback_count = [0]
    
    def on_file_change(state: NetworkState):
        """Callback when file changes."""
        callback_count[0] += 1
        print(f"\n  ✓ File change detected! (callback #{callback_count[0]})")
        print(f"    - Switches: {len(state.topology.switches)}")
        print(f"    - Timestamp: {state.timestamp}")
    
    # Create reader with file watching
    reader = StateFileReader(
        cache_folder=cache_folder,
        state_file_name=file_name,
        enable_file_watching=False,  # Start manually
        file_change_callback=on_file_change
    )
    
    # Start watching
    print("\nStarting file watching...")
    reader.start_file_watching()
    print(f"  - Watching: {reader.is_watching()}")
    
    # Wait a bit for watcher to initialize
    time.sleep(1.0)
    
    # Modify file
    print("\nModifying file...")
    sample_data = {
        "timestamp": datetime.now().isoformat(),
        "topology": {
            "switches": [
                {
                    "id": "switch_1",
                    "name": "Modified Switch",
                    "dpid": "0000000000000001",
                    "ports": [1, 2, 3, 4, 5],  # Added port
                    "status": "active"
                }
            ],
            "links": [],
            "hosts": []
        },
        "flows": [],
        "slices": [],
        "metrics": {
            "bandwidth": {
                "total_capacity": 10000,
                "used_bandwidth": 3500,  # Changed
                "available_bandwidth": 6500,
                "utilization_percentage": 35.0
            },
            "latency": {
                "average_latency": 12.0,
                "min_latency": 6.0,
                "max_latency": 25.0,
                "jitter": 3.0
            },
            "utilization": {
                "cpu_utilization": 55.0,
                "memory_utilization": 70.0,
                "disk_utilization": 40.0
            }
        },
        "anomalies": []
    }
    
    with open(file_path, 'w') as f:
        json.dump(sample_data, f, indent=2)
    
    # Wait for callback
    print("  Waiting for file change detection...")
    time.sleep(3.0)
    
    # Stop watching
    print("\nStopping file watching...")
    reader.stop_file_watching()
    print(f"  - Watching: {reader.is_watching()}")
    
    if callback_count[0] > 0:
        print(f"\n✓ File watching worked! Callback invoked {callback_count[0]} time(s)")
    else:
        print("\n⚠ File watching callback not triggered (may be system-dependent)")


def demo_validation():
    """Demo: JSON validation."""
    print("\n" + "="*60)
    print("DEMO 5: JSON Validation")
    print("="*60)
    
    cache_folder = "./demo_cache"
    
    # Create reader
    reader = StateFileReader(cache_folder=cache_folder)
    
    # Test valid structure
    print("\nValidating valid JSON structure...")
    valid_data = {
        "timestamp": datetime.now().isoformat(),
        "topology": {
            "switches": [],
            "links": [],
            "hosts": []
        },
        "flows": [],
        "metrics": {
            "bandwidth": {},
            "latency": {},
            "utilization": {}
        }
    }
    
    result = reader._validate_json_structure(valid_data)
    print(f"  - Valid: {result['is_valid']}")
    print(f"  - Errors: {result['errors']}")
    
    # Test invalid structure
    print("\nValidating invalid JSON structure...")
    invalid_data = {
        "timestamp": "invalid-timestamp",
        "topology": "not-a-dict"
    }
    
    result = reader._validate_json_structure(invalid_data)
    print(f"  - Valid: {result['is_valid']}")
    print(f"  - Errors: {len(result['errors'])} error(s)")
    for error in result['errors'][:3]:  # Show first 3 errors
        print(f"    • {error}")


def cleanup_demo_files():
    """Clean up demo files."""
    import shutil
    cache_folder = "./demo_cache"
    if os.path.exists(cache_folder):
        shutil.rmtree(cache_folder)
        print(f"\n✓ Cleaned up demo cache folder: {cache_folder}")


def main():
    """Run all demos."""
    print("\n" + "="*60)
    print("StateFileReader Demo")
    print("="*60)
    
    try:
        demo_basic_reading()
        demo_error_handling()
        demo_file_info()
        demo_file_watching()
        demo_validation()
        
        print("\n" + "="*60)
        print("All demos completed!")
        print("="*60)
        
    finally:
        # Cleanup
        cleanup_demo_files()


if __name__ == "__main__":
    main()
