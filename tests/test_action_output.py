"""Tests for action output interface."""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime

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


@pytest.fixture
def temp_directories():
    """Create temporary directories for testing."""
    with tempfile.TemporaryDirectory() as output_dir:
        with tempfile.TemporaryDirectory() as log_dir:
            yield output_dir, log_dir


@pytest.fixture
def action_output_interface(temp_directories):
    """Create action output interface for testing."""
    output_dir, log_dir = temp_directories
    return ActionOutputInterface(
        output_directory=output_dir,
        log_directory=log_dir,
        enable_file_output=True
    )


@pytest.fixture
def sample_action_sequence():
    """Create a sample action sequence for testing."""
    action1 = NetworkAction(
        id="action_1",
        type=ActionType.FLOW_MOD,
        target="switch-1",
        parameters={
            "match": {"in_port": 1, "eth_type": 0x0800},
            "actions": [{"type": "output", "port": 2}]
        },
        priority=1000,
        timeout=30
    )
    
    action2 = NetworkAction(
        id="action_2",
        type=ActionType.SLICE_CREATE,
        target="slice-controller",
        parameters={
            "slice_name": "test_slice",
            "resources": {
                "bandwidth": 100,
                "switches": ["switch-1", "switch-2"]
            }
        },
        priority=900,
        timeout=60
    )
    
    rollback_action = NetworkAction(
        id="rollback_1",
        type=ActionType.FLOW_MOD,
        target="switch-1",
        parameters={
            "match": {"in_port": 1},
            "actions": [{"type": "drop"}]
        },
        priority=1000,
        timeout=30
    )
    
    sequence = ActionSequence(
        id="seq_test_001",
        intent_id="intent_test_001",
        actions=[action1, action2],
        estimated_duration=90,
        dependencies=["dep_1"],
        rollback_plan=[rollback_action]
    )
    
    return sequence


@pytest.fixture
def sample_validation_result():
    """Create a sample validation result."""
    return ValidationResult(
        is_valid=True,
        errors=[],
        warnings=["Minor warning"],
        suggestions=["Consider adding backup"]
    )


@pytest.fixture
def sample_safety_report():
    """Create a sample safety report."""
    return SafetyReport(
        is_safe=True,
        risk_level="low",
        potential_impacts=["Minimal impact on switch-1"],
        mitigation_strategies=["Monitor switch performance"]
    )


class TestNorthboundActionPackage:
    """Tests for NorthboundActionPackage model."""
    
    def test_package_creation(self, sample_action_sequence):
        """Test creating a Northbound action package."""
        package = NorthboundActionPackage(
            package_id="pkg_001",
            created_at=datetime.now(),
            source_intent_id=sample_action_sequence.intent_id,
            sequence_id=sample_action_sequence.id,
            actions=[],
            execution_order=[],
            estimated_duration_seconds=90,
            total_actions=2,
            dependencies=["dep_1"],
            validation_passed=True,
            safety_approved=True,
            risk_level="low",
            rollback_actions=[],
            has_rollback=True,
            trace_id="trace_001"
        )
        
        assert package.package_id == "pkg_001"
        assert package.sequence_id == sample_action_sequence.id
        assert package.validation_passed is True
        assert package.safety_approved is True
    
    def test_package_to_dict(self, sample_action_sequence):
        """Test converting package to dictionary."""
        package = NorthboundActionPackage(
            package_id="pkg_001",
            created_at=datetime.now(),
            source_intent_id=sample_action_sequence.intent_id,
            sequence_id=sample_action_sequence.id,
            actions=[],
            execution_order=[],
            estimated_duration_seconds=90,
            total_actions=2,
            dependencies=[],
            validation_passed=True,
            safety_approved=True,
            risk_level="low",
            rollback_actions=[],
            has_rollback=False,
            trace_id="trace_001"
        )
        
        package_dict = package.to_dict()
        
        assert "package_id" in package_dict
        assert "actions" in package_dict
        assert "metadata" in package_dict
        assert "validation" in package_dict
        assert "rollback" in package_dict
        assert "traceability" in package_dict


class TestActionOutputInterface:
    """Tests for ActionOutputInterface."""
    
    def test_initialization(self, temp_directories):
        """Test interface initialization."""
        output_dir, log_dir = temp_directories
        interface = ActionOutputInterface(
            output_directory=output_dir,
            log_directory=log_dir,
            enable_file_output=True
        )
        
        assert interface.output_directory == Path(output_dir)
        assert interface.log_directory == Path(log_dir)
        assert interface.enable_file_output is True
        assert interface.output_directory.exists()
        assert interface.log_directory.exists()
    
    def test_create_northbound_package(
        self,
        action_output_interface,
        sample_action_sequence,
        sample_validation_result,
        sample_safety_report
    ):
        """Test creating a Northbound package."""
        package = action_output_interface.create_northbound_package(
            sequence=sample_action_sequence,
            validation_result=sample_validation_result,
            safety_report=sample_safety_report,
            user_id="test_user"
        )
        
        assert package.sequence_id == sample_action_sequence.id
        assert package.source_intent_id == sample_action_sequence.intent_id
        assert package.total_actions == len(sample_action_sequence.actions)
        assert package.validation_passed is True
        assert package.safety_approved is True
        assert package.risk_level == "low"
        assert package.user_id == "test_user"
        assert len(package.actions) == 2
        assert len(package.execution_order) == 2
        assert package.has_rollback is True
    
    def test_serialize_to_json(
        self,
        action_output_interface,
        sample_action_sequence,
        sample_validation_result,
        sample_safety_report
    ):
        """Test JSON serialization."""
        package = action_output_interface.create_northbound_package(
            sequence=sample_action_sequence,
            validation_result=sample_validation_result,
            safety_report=sample_safety_report
        )
        
        json_str = action_output_interface.serialize_to_json(package, pretty=True)
        
        assert isinstance(json_str, str)
        assert len(json_str) > 0
        
        # Verify it's valid JSON
        parsed = json.loads(json_str)
        assert "package_id" in parsed
        assert "actions" in parsed
        assert "metadata" in parsed
    
    def test_save_to_file(
        self,
        action_output_interface,
        sample_action_sequence,
        sample_validation_result,
        sample_safety_report
    ):
        """Test saving package to file."""
        package = action_output_interface.create_northbound_package(
            sequence=sample_action_sequence,
            validation_result=sample_validation_result,
            safety_report=sample_safety_report
        )
        
        file_path = action_output_interface.save_to_file(
            package=package,
            filename="test_package.json"
        )
        
        assert file_path != ""
        assert Path(file_path).exists()
        
        # Verify file content
        with open(file_path, 'r') as f:
            content = json.load(f)
            assert content["package_id"] == package.package_id
            assert content["sequence_id"] == package.sequence_id
    
    def test_log_action_output(
        self,
        action_output_interface,
        sample_action_sequence,
        sample_validation_result,
        sample_safety_report
    ):
        """Test logging action output."""
        package = action_output_interface.create_northbound_package(
            sequence=sample_action_sequence,
            validation_result=sample_validation_result,
            safety_report=sample_safety_report
        )
        
        record = action_output_interface.log_action_output(
            package=package,
            validation_result=sample_validation_result,
            safety_report=sample_safety_report,
            output_path="/test/path.json",
            status=ActionStatus.READY
        )
        
        assert record.sequence_id == package.sequence_id
        assert record.intent_id == package.source_intent_id
        assert record.status == ActionStatus.READY
        assert record.output_path == "/test/path.json"
        assert record.validation_result == sample_validation_result
        assert record.safety_report == sample_safety_report
    
    def test_output_actions_complete_workflow(
        self,
        action_output_interface,
        sample_action_sequence,
        sample_validation_result,
        sample_safety_report
    ):
        """Test complete action output workflow."""
        result = action_output_interface.output_actions(
            sequence=sample_action_sequence,
            validation_result=sample_validation_result,
            safety_report=sample_safety_report,
            user_id="test_user",
            save_to_file=True
        )
        
        assert result["success"] is True
        assert "package" in result
        assert "json_output" in result
        assert "file_path" in result
        assert "record" in result
        assert "trace_id" in result
        
        # Verify package
        package = result["package"]
        assert package.user_id == "test_user"
        assert package.validation_passed is True
        
        # Verify file was created
        assert result["file_path"] is not None
        assert Path(result["file_path"]).exists()
        
        # Verify record
        record = result["record"]
        assert record.status == ActionStatus.READY
    
    def test_get_output_record(
        self,
        action_output_interface,
        sample_action_sequence,
        sample_validation_result,
        sample_safety_report
    ):
        """Test retrieving output record."""
        result = action_output_interface.output_actions(
            sequence=sample_action_sequence,
            validation_result=sample_validation_result,
            safety_report=sample_safety_report
        )
        
        record_id = result["record"].record_id
        retrieved_record = action_output_interface.get_output_record(record_id)
        
        assert retrieved_record is not None
        assert retrieved_record.record_id == record_id
    
    def test_get_records_by_intent(
        self,
        action_output_interface,
        sample_action_sequence,
        sample_validation_result,
        sample_safety_report
    ):
        """Test retrieving records by intent ID."""
        action_output_interface.output_actions(
            sequence=sample_action_sequence,
            validation_result=sample_validation_result,
            safety_report=sample_safety_report
        )
        
        records = action_output_interface.get_records_by_intent(
            sample_action_sequence.intent_id
        )
        
        assert len(records) == 1
        assert records[0].intent_id == sample_action_sequence.intent_id
    
    def test_get_records_by_sequence(
        self,
        action_output_interface,
        sample_action_sequence,
        sample_validation_result,
        sample_safety_report
    ):
        """Test retrieving records by sequence ID."""
        action_output_interface.output_actions(
            sequence=sample_action_sequence,
            validation_result=sample_validation_result,
            safety_report=sample_safety_report
        )
        
        records = action_output_interface.get_records_by_sequence(
            sample_action_sequence.id
        )
        
        assert len(records) == 1
        assert records[0].sequence_id == sample_action_sequence.id
    
    def test_update_record_status(
        self,
        action_output_interface,
        sample_action_sequence,
        sample_validation_result,
        sample_safety_report
    ):
        """Test updating record status."""
        result = action_output_interface.output_actions(
            sequence=sample_action_sequence,
            validation_result=sample_validation_result,
            safety_report=sample_safety_report
        )
        
        record_id = result["record"].record_id
        
        # Update status
        success = action_output_interface.update_record_status(
            record_id=record_id,
            status=ActionStatus.SENT
        )
        
        assert success is True
        
        # Verify update
        record = action_output_interface.get_output_record(record_id)
        assert record.status == ActionStatus.SENT
    
    def test_update_record_status_with_error(
        self,
        action_output_interface,
        sample_action_sequence,
        sample_validation_result,
        sample_safety_report
    ):
        """Test updating record status with error message."""
        result = action_output_interface.output_actions(
            sequence=sample_action_sequence,
            validation_result=sample_validation_result,
            safety_report=sample_safety_report
        )
        
        record_id = result["record"].record_id
        
        # Update status with error
        success = action_output_interface.update_record_status(
            record_id=record_id,
            status=ActionStatus.FAILED,
            error_message="Test error"
        )
        
        assert success is True
        
        # Verify update
        record = action_output_interface.get_output_record(record_id)
        assert record.status == ActionStatus.FAILED
        assert record.error_message == "Test error"
    
    def test_get_interface_contract(self, action_output_interface):
        """Test getting interface contract specification."""
        contract = action_output_interface.get_interface_contract()
        
        assert "contract_version" in contract
        assert "description" in contract
        assert "package_format" in contract
        assert "action_format" in contract
        assert "integration_points" in contract
        assert "expected_workflow" in contract
        
        # Verify package format specification
        package_format = contract["package_format"]
        assert "package_id" in package_format
        assert "actions" in package_format
        assert "metadata" in package_format
        
        # Verify action format specification
        action_format = contract["action_format"]
        assert "action_id" in action_format
        assert "action_type" in action_format
        assert "target_resource" in action_format
    
    def test_disabled_file_output(self, temp_directories):
        """Test interface with file output disabled."""
        output_dir, log_dir = temp_directories
        interface = ActionOutputInterface(
            output_directory=output_dir,
            log_directory=log_dir,
            enable_file_output=False
        )
        
        # Create a simple sequence
        action = NetworkAction(
            id="action_1",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={"match": {}, "actions": []},
            priority=1000,
            timeout=30
        )
        
        sequence = ActionSequence(
            id="seq_001",
            intent_id="intent_001",
            actions=[action],
            estimated_duration=30,
            dependencies=[],
            rollback_plan=[]
        )
        
        validation_result = ValidationResult(is_valid=True, errors=[], warnings=[], suggestions=[])
        safety_report = SafetyReport(is_safe=True, risk_level="low", potential_impacts=[], mitigation_strategies=[])
        
        # Output actions with file output disabled
        result = interface.output_actions(
            sequence=sequence,
            validation_result=validation_result,
            safety_report=safety_report,
            save_to_file=True
        )
        
        # File path should be None when file output is disabled
        assert result["file_path"] is None
        assert result["success"] is True


class TestActionOutputTraceability:
    """Tests for action output traceability features."""
    
    def test_trace_id_generation(
        self,
        action_output_interface,
        sample_action_sequence,
        sample_validation_result,
        sample_safety_report
    ):
        """Test automatic trace ID generation."""
        package = action_output_interface.create_northbound_package(
            sequence=sample_action_sequence,
            validation_result=sample_validation_result,
            safety_report=sample_safety_report
        )
        
        assert package.trace_id is not None
        assert package.trace_id.startswith("trace_")
        assert sample_action_sequence.intent_id in package.trace_id
    
    def test_custom_trace_id(
        self,
        action_output_interface,
        sample_action_sequence,
        sample_validation_result,
        sample_safety_report
    ):
        """Test using custom trace ID."""
        custom_trace_id = "custom_trace_12345"
        
        package = action_output_interface.create_northbound_package(
            sequence=sample_action_sequence,
            validation_result=sample_validation_result,
            safety_report=sample_safety_report,
            trace_id=custom_trace_id
        )
        
        assert package.trace_id == custom_trace_id
    
    def test_action_logging_creates_log_file(
        self,
        action_output_interface,
        sample_action_sequence,
        sample_validation_result,
        sample_safety_report
    ):
        """Test that action logging creates log file."""
        action_output_interface.output_actions(
            sequence=sample_action_sequence,
            validation_result=sample_validation_result,
            safety_report=sample_safety_report
        )
        
        log_file = action_output_interface.log_directory / "action_output.log"
        assert log_file.exists()
        
        # Verify log content
        with open(log_file, 'r') as f:
            log_content = f.read()
            assert len(log_content) > 0
            
            # Parse first log entry
            first_line = log_content.split('\n')[0]
            log_entry = json.loads(first_line)
            
            assert "timestamp" in log_entry
            assert "record_id" in log_entry
            assert "sequence_id" in log_entry
            assert log_entry["sequence_id"] == sample_action_sequence.id


class TestNorthboundIntegration:
    """Tests for Northbound module integration features."""
    
    def test_action_northbound_format(
        self,
        action_output_interface,
        sample_action_sequence,
        sample_validation_result,
        sample_safety_report
    ):
        """Test that actions are in correct Northbound format."""
        package = action_output_interface.create_northbound_package(
            sequence=sample_action_sequence,
            validation_result=sample_validation_result,
            safety_report=sample_safety_report
        )
        
        # Check action format
        for action in package.actions:
            assert "action_id" in action
            assert "action_type" in action
            assert "target_resource" in action
            assert "parameters" in action
            assert "execution_priority" in action
            assert "timeout_seconds" in action
            assert "description" in action
    
    def test_execution_order_preserved(
        self,
        action_output_interface,
        sample_action_sequence,
        sample_validation_result,
        sample_safety_report
    ):
        """Test that execution order is preserved."""
        package = action_output_interface.create_northbound_package(
            sequence=sample_action_sequence,
            validation_result=sample_validation_result,
            safety_report=sample_safety_report
        )
        
        # Execution order should match the optimized order from sequence
        ordered_actions = sample_action_sequence.get_execution_order()
        expected_order = [action.id for action in ordered_actions]
        
        assert package.execution_order == expected_order
    
    def test_rollback_plan_included(
        self,
        action_output_interface,
        sample_action_sequence,
        sample_validation_result,
        sample_safety_report
    ):
        """Test that rollback plan is included in package."""
        package = action_output_interface.create_northbound_package(
            sequence=sample_action_sequence,
            validation_result=sample_validation_result,
            safety_report=sample_safety_report
        )
        
        assert package.has_rollback is True
        assert len(package.rollback_actions) > 0
        
        # Check rollback action format
        for rollback_action in package.rollback_actions:
            assert "action_id" in rollback_action
            assert "action_type" in rollback_action
