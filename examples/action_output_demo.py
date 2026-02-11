"""
Demo script for Action Output Interface.

This demonstrates how to use the ActionOutputInterface to:
1. Create structured output packages for validated actions
2. Serialize actions to JSON format
3. Save actions to files for future Northbound integration
4. Log actions for traceability
5. Retrieve and update action records
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
from src.services.action_output import (
    ActionOutputInterface,
    OutputFormat,
    ActionStatus
)
from src.models.actions import (
    NetworkAction,
    ActionSequence,
    ActionType,
    ValidationResult,
    SafetyReport
)


def create_sample_actions():
    """Create sample network actions for demonstration."""
    print("\n=== Creating Sample Network Actions ===")
    
    # Action 1: Flow modification
    action1 = NetworkAction(
        id="flow_mod_001",
        type=ActionType.FLOW_MOD,
        target="switch-1",
        parameters={
            "match": {
                "in_port": 1,
                "eth_type": 0x0800,
                "ip_dst": "10.0.0.5"
            },
            "actions": [
                {"type": "output", "port": 2}
            ],
            "priority": 100
        },
        priority=1000,
        timeout=30,
        description="Route traffic to host 10.0.0.5 through port 2"
    )
    print(f"  ✓ Created action: {action1.id} - {action1.description}")
    
    # Action 2: Network slice creation
    action2 = NetworkAction(
        id="slice_create_001",
        type=ActionType.SLICE_CREATE,
        target="slice-controller",
        parameters={
            "slice_name": "iot_slice",
            "resources": {
                "bandwidth": 500,  # Mbps
                "switches": ["switch-1", "switch-2", "switch-3"],
                "paths": [
                    {
                        "switches": ["switch-1", "switch-2"],
                        "bandwidth": 200
                    },
                    {
                        "switches": ["switch-2", "switch-3"],
                        "bandwidth": 300
                    }
                ]
            },
            "policies": [
                {
                    "type": "qos",
                    "priority": "high",
                    "max_latency": 50
                }
            ],
            "sla": {
                "min_bandwidth": 400,
                "max_latency": 100,
                "availability": 99.9
            }
        },
        priority=900,
        timeout=120,
        description="Create IoT network slice with QoS guarantees"
    )
    print(f"  ✓ Created action: {action2.id} - {action2.description}")
    
    # Action 3: Configuration change
    action3 = NetworkAction(
        id="config_change_001",
        type=ActionType.CONFIG_CHANGE,
        target="switch-2",
        parameters={
            "config_type": "qos_config",
            "config_data": {
                "queue_config": {
                    "queue_1": {"min_rate": 100, "max_rate": 500},
                    "queue_2": {"min_rate": 50, "max_rate": 200}
                }
            },
            "backup": True,
            "validate_before_apply": True
        },
        priority=800,
        timeout=60,
        description="Configure QoS queues on switch-2"
    )
    print(f"  ✓ Created action: {action3.id} - {action3.description}")
    
    # Rollback action
    rollback_action = NetworkAction(
        id="rollback_flow_001",
        type=ActionType.FLOW_MOD,
        target="switch-1",
        parameters={
            "match": {"in_port": 1},
            "actions": [{"type": "drop"}]
        },
        priority=1000,
        timeout=30,
        description="Rollback: Drop traffic on port 1"
    )
    print(f"  ✓ Created rollback action: {rollback_action.id}")
    
    return [action1, action2, action3], [rollback_action]


def create_action_sequence(actions, rollback_actions):
    """Create an action sequence from actions."""
    print("\n=== Creating Action Sequence ===")
    
    sequence = ActionSequence(
        id="seq_demo_001",
        intent_id="intent_demo_001",
        actions=actions,
        estimated_duration=210,  # 3.5 minutes
        dependencies=["network_state_update"],
        rollback_plan=rollback_actions
    )
    
    print(f"  ✓ Sequence ID: {sequence.id}")
    print(f"  ✓ Intent ID: {sequence.intent_id}")
    print(f"  ✓ Total actions: {len(sequence.actions)}")
    print(f"  ✓ Estimated duration: {sequence.estimated_duration}s")
    print(f"  ✓ Has rollback plan: {len(sequence.rollback_plan) > 0}")
    
    return sequence


def create_validation_and_safety_reports():
    """Create sample validation and safety reports."""
    print("\n=== Creating Validation and Safety Reports ===")
    
    validation_result = ValidationResult(
        is_valid=True,
        errors=[],
        warnings=[
            "Slice creation affects multiple switches",
            "High bandwidth allocation requested"
        ],
        suggestions=[
            "Monitor switch performance after deployment",
            "Consider implementing gradual rollout"
        ]
    )
    print(f"  ✓ Validation: {'PASSED' if validation_result.is_valid else 'FAILED'}")
    print(f"  ✓ Warnings: {len(validation_result.warnings)}")
    print(f"  ✓ Suggestions: {len(validation_result.suggestions)}")
    
    safety_report = SafetyReport(
        is_safe=True,
        risk_level="medium",
        potential_impacts=[
            "Affects 3 switches in the network",
            "Allocates 500 Mbps bandwidth",
            "May impact existing traffic flows"
        ],
        mitigation_strategies=[
            "Implement changes during maintenance window",
            "Monitor network performance metrics",
            "Have rollback plan ready for immediate execution"
        ]
    )
    print(f"  ✓ Safety: {'APPROVED' if safety_report.is_safe else 'REJECTED'}")
    print(f"  ✓ Risk level: {safety_report.risk_level.upper()}")
    print(f"  ✓ Potential impacts: {len(safety_report.potential_impacts)}")
    
    return validation_result, safety_report


def demonstrate_action_output():
    """Main demonstration function."""
    print("\n" + "="*70)
    print("ACTION OUTPUT INTERFACE DEMONSTRATION")
    print("="*70)
    
    # Create sample data
    actions, rollback_actions = create_sample_actions()
    sequence = create_action_sequence(actions, rollback_actions)
    validation_result, safety_report = create_validation_and_safety_reports()
    
    # Initialize action output interface
    print("\n=== Initializing Action Output Interface ===")
    output_interface = ActionOutputInterface(
        output_directory="./output/actions",
        log_directory="./output/logs",
        enable_file_output=True
    )
    print(f"  ✓ Output directory: {output_interface.output_directory}")
    print(f"  ✓ Log directory: {output_interface.log_directory}")
    
    # Create Northbound package
    print("\n=== Creating Northbound Action Package ===")
    package = output_interface.create_northbound_package(
        sequence=sequence,
        validation_result=validation_result,
        safety_report=safety_report,
        user_id="admin_user"
    )
    print(f"  ✓ Package ID: {package.package_id}")
    print(f"  ✓ Package version: {package.package_version}")
    print(f"  ✓ Created at: {package.created_at.isoformat()}")
    print(f"  ✓ Trace ID: {package.trace_id}")
    print(f"  ✓ Validation passed: {package.validation_passed}")
    print(f"  ✓ Safety approved: {package.safety_approved}")
    print(f"  ✓ Risk level: {package.risk_level}")
    
    # Serialize to JSON
    print("\n=== Serializing to JSON ===")
    json_output = output_interface.serialize_to_json(package, pretty=True)
    print(f"  ✓ JSON size: {len(json_output)} bytes")
    print(f"  ✓ Preview (first 200 chars):")
    print(f"    {json_output[:200]}...")
    
    # Save to file
    print("\n=== Saving to File ===")
    file_path = output_interface.save_to_file(
        package=package,
        output_format=OutputFormat.JSON
    )
    print(f"  ✓ File saved: {file_path}")
    print(f"  ✓ File exists: {Path(file_path).exists()}")
    print(f"  ✓ File size: {Path(file_path).stat().st_size} bytes")
    
    # Log action output
    print("\n=== Logging Action Output ===")
    record = output_interface.log_action_output(
        package=package,
        validation_result=validation_result,
        safety_report=safety_report,
        output_path=file_path,
        status=ActionStatus.READY
    )
    print(f"  ✓ Record ID: {record.record_id}")
    print(f"  ✓ Status: {record.status.value}")
    print(f"  ✓ Timestamp: {record.timestamp.isoformat()}")
    
    # Complete workflow
    print("\n=== Complete Output Workflow ===")
    result = output_interface.output_actions(
        sequence=sequence,
        validation_result=validation_result,
        safety_report=safety_report,
        user_id="admin_user",
        save_to_file=True
    )
    print(f"  ✓ Workflow success: {result['success']}")
    print(f"  ✓ Package created: {result['package'].package_id}")
    print(f"  ✓ File saved: {result['file_path']}")
    print(f"  ✓ Record created: {result['record'].record_id}")
    print(f"  ✓ Trace ID: {result['trace_id']}")
    
    # Retrieve records
    print("\n=== Retrieving Records ===")
    
    # By record ID
    retrieved_record = output_interface.get_output_record(record.record_id)
    print(f"  ✓ Retrieved by record ID: {retrieved_record.record_id if retrieved_record else 'Not found'}")
    
    # By intent ID
    intent_records = output_interface.get_records_by_intent(sequence.intent_id)
    print(f"  ✓ Records for intent {sequence.intent_id}: {len(intent_records)}")
    
    # By sequence ID
    sequence_records = output_interface.get_records_by_sequence(sequence.id)
    print(f"  ✓ Records for sequence {sequence.id}: {len(sequence_records)}")
    
    # Update record status
    print("\n=== Updating Record Status ===")
    print(f"  ✓ Current status: {record.status.value}")
    
    output_interface.update_record_status(
        record_id=record.record_id,
        status=ActionStatus.SENT
    )
    updated_record = output_interface.get_output_record(record.record_id)
    print(f"  ✓ Updated status: {updated_record.status.value}")
    
    output_interface.update_record_status(
        record_id=record.record_id,
        status=ActionStatus.ACKNOWLEDGED
    )
    updated_record = output_interface.get_output_record(record.record_id)
    print(f"  ✓ Final status: {updated_record.status.value}")
    
    # Get interface contract
    print("\n=== Interface Contract for Northbound Integration ===")
    contract = output_interface.get_interface_contract()
    print(f"  ✓ Contract version: {contract['contract_version']}")
    print(f"  ✓ Description: {contract['description']}")
    print(f"  ✓ File location: {contract['integration_points']['file_location']}")
    print(f"  ✓ File format: {contract['integration_points']['file_format']}")
    print(f"  ✓ Expected workflow steps: {len(contract['expected_workflow'])}")
    
    print("\n" + "="*70)
    print("DEMONSTRATION COMPLETE")
    print("="*70)
    print(f"\nOutput files created:")
    print(f"  - Action package: {file_path}")
    print(f"  - Log file: {output_interface.log_directory / 'action_output.log'}")
    print(f"\nThe action package is ready for future Northbound module integration!")
    print("="*70 + "\n")


if __name__ == "__main__":
    demonstrate_action_output()
