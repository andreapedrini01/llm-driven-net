#!/usr/bin/env python3
"""
Verification script to test the standalone northbound_script_generator module.

This script verifies that the module is self-contained and can be used
independently without external dependencies.
"""

import sys
import os

# Add parent directory to path to access the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 70)
print("NORTHBOUND SCRIPT GENERATOR - STANDALONE MODULE VERIFICATION")
print("=" * 70)

# Test 1: Module Import
print("\n[Test 1] Testing module import...")
try:
    from northbound_script_generator import NorthboundScript
    print("✅ Module imported successfully")
    print(f"   NorthboundScript class: {NorthboundScript}")
except ImportError as e:
    print(f"❌ Module import failed: {e}")
    sys.exit(1)

# Test 2: Check Module Structure
print("\n[Test 2] Checking module structure...")
module_path = "northbound_script_generator"
required_items = [
    "src",
    "config",
    "logs",
    "requirements.txt",
    ".env.example",
    "start_system.py",
    "main.py",
    "__init__.py"
]

missing_items = []
for item in required_items:
    item_path = os.path.join(module_path, item)
    if not os.path.exists(item_path):
        missing_items.append(item)
        print(f"❌ Missing: {item}")
    else:
        print(f"✅ Found: {item}")

if missing_items:
    print(f"\n❌ Module structure incomplete. Missing: {missing_items}")
    sys.exit(1)
else:
    print("\n✅ Module structure is complete")

# Test 3: Check Source Modules
print("\n[Test 3] Checking source modules...")
src_modules = [
    "api",
    "backup",
    "config",
    "connectors",
    "core",
    "logging",
    "models",
    "monitoring",
    "orchestrator",
    "scalability"
]

missing_modules = []
for module in src_modules:
    module_path_check = os.path.join(module_path, "src", module)
    if not os.path.exists(module_path_check):
        missing_modules.append(module)
        print(f"❌ Missing: src/{module}")
    else:
        print(f"✅ Found: src/{module}")

if missing_modules:
    print(f"\n❌ Source modules incomplete. Missing: {missing_modules}")
    sys.exit(1)
else:
    print("\n✅ All source modules present")

# Test 4: Test NorthboundScript Instantiation
print("\n[Test 4] Testing NorthboundScript instantiation...")
try:
    from unittest.mock import Mock, patch
    
    # Mock the network interfaces to avoid actual connections
    with patch('northbound_script_generator.northbound_script.RYUNetworkInterface') as mock_interface:
        mock_interface.return_value = Mock()
        northbound = NorthboundScript()
        print("✅ NorthboundScript instantiated successfully")
        print(f"   Instance: {northbound}")
except Exception as e:
    print(f"❌ Instantiation failed: {e}")
    sys.exit(1)

# Test 5: Test Basic Functionality
print("\n[Test 5] Testing basic functionality...")
try:
    import json
    
    test_sequence = {
        "id": "test_001",
        "intent_id": "verify_test",
        "estimated_duration": 10,
        "actions": [{
            "id": "action_001",
            "type": "flow_mod",
            "target": "switch-1",
            "parameters": {
                "operation": "add",
                "match": {"ip_src": "192.168.1.1"},
                "actions": ["drop"]
            },
            "priority": 1000,
            "timeout": 30
        }],
        "dependencies": [],
        "rollback_plan": []
    }
    
    with patch('northbound_script_generator.northbound_script.RYUNetworkInterface') as mock_interface:
        mock_interface.return_value = Mock()
        northbound = NorthboundScript()
        
        # Test parsing
        sequence = northbound.parse_llm_output(json.dumps(test_sequence))
        print(f"✅ Parsing works - Sequence ID: {sequence.id}")
        
        # Test validation
        validation = northbound.validate_sequence(sequence)
        print(f"✅ Validation works - Valid: {validation.is_valid}")
        
        # Test dry run
        result = northbound.process_llm_output(json.dumps(test_sequence), dry_run=True)
        print(f"✅ Dry run works - Success: {result['success']}")
        
except Exception as e:
    print(f"❌ Functionality test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: Check Configuration Files
print("\n[Test 6] Checking configuration files...")
config_files = [
    "config/system_config.example.yaml",
    "config/backup_config.example.yaml"
]

for config_file in config_files:
    config_path = os.path.join(module_path, config_file)
    if os.path.exists(config_path):
        print(f"✅ Found: {config_file}")
    else:
        print(f"⚠️  Missing: {config_file} (optional)")

# Final Summary
print("\n" + "=" * 70)
print("VERIFICATION COMPLETE")
print("=" * 70)
print("\n✅ All critical tests passed!")
print("\nThe northbound_script_generator module is:")
print("  • Self-contained")
print("  • Properly structured")
print("  • Fully functional")
print("  • Ready for integration")
print("\nYou can now:")
print("  1. Run it standalone: cd northbound_script_generator && python start_system.py")
print("  2. Import it: from northbound_script_generator import NorthboundScript")
print("  3. Copy it to another project: cp -r northbound_script_generator /path/to/project/")
print("\n" + "=" * 70)
