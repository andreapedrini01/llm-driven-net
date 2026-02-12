"""Property-based tests for action traceability functionality."""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck, Phase
from datetime import datetime
from pathlib import Path
import json
import tempfile
from typing import Dict, Any, List

from src.services.action_output import (
    ActionOutputInterface,
    NorthboundActionPackage,
    ActionOutputRecord,
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


class TestActionTraceabilityProperties:
    """Property-based tests for action traceability."""
    
    # Generator strategies for test data
    @staticmethod
    @st.composite
    def valid_action_id(draw):
        """Generate valid action IDs."""
        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-'
        length = draw(st.integers(min_value=1, max_value=50))
        return ''.join(draw(st.lists(st.sampled_from(chars), min_size=length, max_size=length)))
    
    @staticmethod
    @st.composite
    def valid_target(draw):
        """Generate valid target identifiers."""
        target_types = [
            lambda: f"switch-{draw(st.integers(min_value=1, max_value=100))}",
            lambda: f"192.168.{draw(st.integers(min_value=1, max_value=255))}.{draw(st.integers(min_value=1, max_value=255))}",
            lambda: f"host_{draw(st.integers(min_value=1, max_value=100))}"
        ]
        target_generator = draw(st.sampled_from(target_types))
        return target_generator()
    
    @staticmethod
    @st.composite
    def network_action(draw):
        """Generate a valid NetworkAction."""
        action_type = draw(st.sampled_from(list(ActionType)))
        
        # Generate basic parameters
        parameters = {}
        if action_type == ActionType.FLOW_MOD:
            parameters = {
                'match': {'in_port': draw(st.integers(min_value=1, max_value=48))},
                'actions': [{'type': 'output', 'port': draw(st.integers(min_value=1, max_value=48))}]
            }
        elif action_type == ActionType.SLICE_CREATE:
            parameters = {
                'slice_name': f"slice_{draw(st.integers(min_value=1, max_value=1000))}",
                'resources': {
                    'bandwidth': draw(st.integers(min_value=10, max_value=10000)),
                    'switches': [f"sw{i}" for i in range(1, draw(st.integers(min_value=2, max_value=5)))]
                }
            }
        elif action_type == ActionType.CONFIG_CHANGE:
            parameters = {
                'config_type': draw(st.sampled_from(['qos', 'routing', 'security'])),
                'config_data': {'setting': draw(st.integers(min_value=1, max_value=100))}
            }
        
        return NetworkAction(
            id=draw(TestActionTraceabilityProperties.valid_action_id()),
            type=action_type,
            target=draw(TestActionTraceabilityProperties.valid_target()),
            parameters=parameters,
            priority=draw(st.integers(min_value=1, max_value=65535)),
            timeout=draw(st.integers(min_value=1, max_value=3600))
        )
    
    @staticmethod
    @st.composite
    def action_sequence(draw):
        """Generate a valid ActionSequence."""
        actions = draw(st.lists(
            TestActionTraceabilityProperties.network_action(),
            min_size=1,
            max_size=10
        ))
        
        # Ensure unique action IDs
        used_ids = set()
        unique_actions = []
        for action in actions:
            if action.id not in used_ids:
                unique_actions.append(action)
                used_ids.add(action.id)
        
        if not unique_actions:
            unique_actions = [draw(TestActionTraceabilityProperties.network_action())]
        
        estimated_duration = sum(action.estimate_execution_time() for action in unique_actions)
        
        # Generate rollback plan
        rollback_actions = []
        if draw(st.booleans()):
            for action in unique_actions[:draw(st.integers(min_value=1, max_value=len(unique_actions)))]:
                rollback_action = NetworkAction(
                    id=f"rollback_{action.id}",
                    type=action.type,
                    target=action.target,
                    parameters={'rollback': True},
                    priority=action.priority,
                    timeout=action.timeout
                )
                rollback_actions.append(rollback_action)
        
        return ActionSequence(
            id=draw(TestActionTraceabilityProperties.valid_action_id()),
            intent_id=draw(TestActionTraceabilityProperties.valid_action_id()),
            actions=unique_actions,
            estimated_duration=estimated_duration,
            dependencies=draw(st.lists(
                TestActionTraceabilityProperties.valid_action_id(),
                min_size=0,
                max_size=3
            )),
            rollback_plan=rollback_actions
        )
    
    @staticmethod
    @st.composite
    def validation_result(draw):
        """Generate a ValidationResult."""
        is_valid = draw(st.booleans())
        errors = [] if is_valid else draw(st.lists(st.text(min_size=5, max_size=100), min_size=1, max_size=3))
        warnings = draw(st.lists(st.text(min_size=5, max_size=100), min_size=0, max_size=3))
        suggestions = draw(st.lists(st.text(min_size=5, max_size=100), min_size=0, max_size=3))
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )
    
    @staticmethod
    @st.composite
    def safety_report(draw):
        """Generate a SafetyReport."""
        is_safe = draw(st.booleans())
        risk_level = draw(st.sampled_from(['low', 'medium', 'high', 'critical']))
        potential_impacts = draw(st.lists(st.text(min_size=5, max_size=100), min_size=0, max_size=5))
        mitigation_strategies = draw(st.lists(st.text(min_size=5, max_size=100), min_size=0, max_size=5))
        
        return SafetyReport(
            is_safe=is_safe,
            risk_level=risk_level,
            potential_impacts=potential_impacts,
            mitigation_strategies=mitigation_strategies
        )
    
    @settings(
        max_examples=20, 
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
        phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target]
    )
    @given(
        sequence=action_sequence(),
        validation=validation_result(),
        safety=safety_report(),
        user_id=st.one_of(st.none(), st.text(min_size=1, max_size=50))
    )
    def test_action_traceability(self, sequence, validation, safety, user_id):
        """
        **Feature: llm-integration-module, Property 11: Action traceability**
        
        For any NetworkAction sent to the external execution module, a complete log entry 
        should be created and maintained for audit and debugging purposes.
        
        **Validates: Requirements 3.5**
        """
        assume(sequence is not None)
        assume(len(sequence.actions) > 0)
        assume(validation is not None)
        assume(safety is not None)
        
        # Create temporary output interface for this test
        with tempfile.TemporaryDirectory() as output_dir:
            with tempfile.TemporaryDirectory() as log_dir:
                temp_output_interface = ActionOutputInterface(
                    output_directory=output_dir,
                    log_directory=log_dir,
                    enable_file_output=True
                )
                
                # Execute the complete action output workflow
                result = temp_output_interface.output_actions(
                    sequence=sequence,
                    validation_result=validation,
                    safety_report=safety,
                    user_id=user_id,
                    save_to_file=True
                )
                
                # Property 1: Output workflow must succeed and return complete results
                assert result["success"] is True, "Action output workflow must succeed"
                assert "package" in result, "Result must contain package"
                assert "json_output" in result, "Result must contain JSON output"
                assert "file_path" in result, "Result must contain file path"
                assert "record" in result, "Result must contain traceability record"
                assert "trace_id" in result, "Result must contain trace ID"
                
                package = result["package"]
                record = result["record"]
                trace_id = result["trace_id"]
                
                # Property 2: Complete log entry must be created for traceability
                assert record is not None, "Traceability record must be created"
                assert isinstance(record, ActionOutputRecord), "Record must be ActionOutputRecord type"
                
                # Property 3: Log entry must contain all essential traceability information
                assert record.record_id is not None and len(record.record_id) > 0, "Record must have valid ID"
                assert record.sequence_id == sequence.id, "Record must reference correct sequence ID"
                assert record.intent_id == sequence.intent_id, "Record must reference correct intent ID"
                assert record.timestamp is not None, "Record must have timestamp"
                assert isinstance(record.timestamp, datetime), "Timestamp must be datetime object"
                assert record.status is not None, "Record must have status"
                assert isinstance(record.status, ActionStatus), "Status must be ActionStatus enum"
                
                # Property 4: Log entry must include validation and safety information
                assert record.validation_result is not None, "Record must include validation result"
                assert record.validation_result == validation, "Record must preserve validation result"
                assert record.safety_report is not None, "Record must include safety report"
                assert record.safety_report == safety, "Record must preserve safety report"
                
                # Property 5: Log entry must include comprehensive metadata for audit
                assert record.metadata is not None, "Record must have metadata"
                assert isinstance(record.metadata, dict), "Metadata must be dictionary"
                assert "package_id" in record.metadata, "Metadata must include package ID"
                assert "trace_id" in record.metadata, "Metadata must include trace ID"
                assert "total_actions" in record.metadata, "Metadata must include action count"
                assert "estimated_duration" in record.metadata, "Metadata must include duration"
                assert "risk_level" in record.metadata, "Metadata must include risk level"
                assert "has_rollback" in record.metadata, "Metadata must include rollback status"
                
                # Verify metadata values
                assert record.metadata["package_id"] == package.package_id
                assert record.metadata["trace_id"] == trace_id
                assert record.metadata["total_actions"] == len(sequence.actions)
                assert record.metadata["estimated_duration"] == sequence.estimated_duration
                assert record.metadata["risk_level"] == safety.risk_level
                assert record.metadata["has_rollback"] == (len(sequence.rollback_plan) > 0)
                
                # Property 6: User ID must be tracked when provided
                if user_id:
                    assert record.metadata.get("user_id") == user_id, "User ID must be tracked in metadata"
                
                # Property 7: Record must be retrievable by record ID
                retrieved_record = temp_output_interface.get_output_record(record.record_id)
                assert retrieved_record is not None, "Record must be retrievable by ID"
                assert retrieved_record.record_id == record.record_id, "Retrieved record must match"
                assert retrieved_record.sequence_id == sequence.id, "Retrieved record must have correct sequence ID"
                
                # Property 8: Record must be retrievable by intent ID
                intent_records = temp_output_interface.get_records_by_intent(sequence.intent_id)
                assert len(intent_records) > 0, "Records must be retrievable by intent ID"
                assert any(r.record_id == record.record_id for r in intent_records), "Record must be in intent records"
                
                # Property 9: Record must be retrievable by sequence ID
                sequence_records = temp_output_interface.get_records_by_sequence(sequence.id)
                assert len(sequence_records) > 0, "Records must be retrievable by sequence ID"
                assert any(r.record_id == record.record_id for r in sequence_records), "Record must be in sequence records"
                
                # Property 10: Package must contain complete traceability information
                assert package.trace_id is not None and len(package.trace_id) > 0, "Package must have trace ID"
                assert package.trace_id == trace_id, "Package trace ID must match result trace ID"
                assert package.package_id is not None, "Package must have unique ID"
                assert package.sequence_id == sequence.id, "Package must reference sequence"
                assert package.source_intent_id == sequence.intent_id, "Package must reference intent"
                
                # Property 11: Package must include all actions with traceability
                assert len(package.actions) == len(sequence.actions), "Package must include all actions"
                for i, action_data in enumerate(package.actions):
                    assert "action_id" in action_data, "Action must have ID for traceability"
                    assert action_data["action_id"] == sequence.actions[i].id, "Action ID must match"
                
                # Property 12: Execution order must be tracked for traceability
                assert package.execution_order is not None, "Package must have execution order"
                assert isinstance(package.execution_order, list), "Execution order must be list"
                assert len(package.execution_order) == len(sequence.actions), "Execution order must include all actions"
                for action_id in package.execution_order:
                    assert any(a.id == action_id for a in sequence.actions), "Execution order must reference valid actions"
                
                # Property 13: File output must be created and contain traceability data
                if result["file_path"]:
                    file_path = Path(result["file_path"])
                    assert file_path.exists(), "Output file must exist"
                    
                    # Verify file content
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_content = json.load(f)
                        assert "package_id" in file_content, "File must contain package ID"
                        assert "sequence_id" in file_content, "File must contain sequence ID"
                        assert "source_intent_id" in file_content, "File must contain intent ID"
                        assert "traceability" in file_content, "File must contain traceability section"
                        assert file_content["traceability"]["trace_id"] == trace_id, "File must contain trace ID"
                
                # Property 14: Log file must be created with traceability entry
                log_file = temp_output_interface.log_directory / "action_output.log"
                assert log_file.exists(), "Log file must be created"
                
                # Verify log file content
                with open(log_file, 'r') as f:
                    log_content = f.read()
                    assert len(log_content) > 0, "Log file must not be empty"
                    
                    # Parse log entries
                    log_lines = [line for line in log_content.split('\n') if line.strip()]
                    assert len(log_lines) > 0, "Log file must contain entries"
                    
                    # Find our log entry
                    found_entry = False
                    for line in log_lines:
                        try:
                            log_entry = json.loads(line)
                            if log_entry.get("record_id") == record.record_id:
                                found_entry = True
                                # Verify log entry completeness
                                assert "timestamp" in log_entry, "Log entry must have timestamp"
                                assert "sequence_id" in log_entry, "Log entry must have sequence ID"
                                assert "intent_id" in log_entry, "Log entry must have intent ID"
                                assert "status" in log_entry, "Log entry must have status"
                                assert "metadata" in log_entry, "Log entry must have metadata"
                                assert log_entry["sequence_id"] == sequence.id
                                assert log_entry["intent_id"] == sequence.intent_id
                                break
                        except json.JSONDecodeError:
                            continue
                    
                    assert found_entry, "Log file must contain entry for this action"
                
                # Property 15: Record status must be updatable for lifecycle tracking
                new_status = ActionStatus.SENT
                update_success = temp_output_interface.update_record_status(
                    record_id=record.record_id,
                    status=new_status
                )
                assert update_success is True, "Record status must be updatable"
                
                # Verify status update
                updated_record = temp_output_interface.get_output_record(record.record_id)
                assert updated_record.status == new_status, "Updated status must be persisted"
                
                # Property 16: Error messages must be trackable in record
                error_message = "Test error for traceability"
                error_update_success = temp_output_interface.update_record_status(
                    record_id=record.record_id,
                    status=ActionStatus.FAILED,
                    error_message=error_message
                )
                assert error_update_success is True, "Error status must be updatable"
                
                # Verify error tracking
                error_record = temp_output_interface.get_output_record(record.record_id)
                assert error_record.status == ActionStatus.FAILED, "Failed status must be persisted"
                assert error_record.error_message == error_message, "Error message must be tracked"
    
    @settings(
        max_examples=10, 
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
        phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target]
    )
    @given(
        sequences=st.lists(action_sequence(), min_size=2, max_size=5),
        validation=validation_result(),
        safety=safety_report()
    )
    def test_multiple_actions_traceability(self, sequences, validation, safety):
        """Test traceability for multiple action sequences."""
        assume(len(sequences) >= 2)
        
        # Create temporary output interface for this test
        with tempfile.TemporaryDirectory() as output_dir:
            with tempfile.TemporaryDirectory() as log_dir:
                temp_output_interface = ActionOutputInterface(
                    output_directory=output_dir,
                    log_directory=log_dir,
                    enable_file_output=True
                )
                
                # Output multiple action sequences
                records = []
                for sequence in sequences:
                    result = temp_output_interface.output_actions(
                        sequence=sequence,
                        validation_result=validation,
                        safety_report=safety,
                        save_to_file=True
                    )
                    records.append(result["record"])
                
                # Property: All records must be independently traceable
                assert len(records) == len(sequences), "Each sequence must have a record"
                
                # Property: Each record must have unique ID
                record_ids = [r.record_id for r in records]
                assert len(record_ids) == len(set(record_ids)), "All record IDs must be unique"
                
                # Property: Each record must be retrievable independently
                for record in records:
                    retrieved = temp_output_interface.get_output_record(record.record_id)
                    assert retrieved is not None, "Each record must be retrievable"
                    assert retrieved.record_id == record.record_id
                
                # Property: Records can be filtered by intent
                for i, sequence in enumerate(sequences):
                    intent_records = temp_output_interface.get_records_by_intent(sequence.intent_id)
                    assert len(intent_records) > 0, "Records must be filterable by intent"
                    assert any(r.record_id == records[i].record_id for r in intent_records)
                
                # Property: Records can be filtered by sequence
                for i, sequence in enumerate(sequences):
                    seq_records = temp_output_interface.get_records_by_sequence(sequence.id)
                    assert len(seq_records) > 0, "Records must be filterable by sequence"
                    assert any(r.record_id == records[i].record_id for r in seq_records)
