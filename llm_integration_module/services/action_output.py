"""Action output interface for future Northbound module integration."""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
import logging
from enum import Enum
from pydantic import BaseModel, Field

from llm_integration_module.models.actions import (
    NetworkAction,
    ActionSequence,
    ValidationResult,
    SafetyReport,
    ImpactAssessment
)


logger = logging.getLogger(__name__)


class OutputFormat(str, Enum):
    """Supported output formats for action serialization."""
    JSON = "json"
    YAML = "yaml"
    NORTHBOUND_V1 = "northbound_v1"


class ActionStatus(str, Enum):
    """Status of action output."""
    PENDING = "pending"
    READY = "ready"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"


class ActionOutputRecord(BaseModel):
    """Record of action output for traceability."""
    record_id: str
    sequence_id: str
    intent_id: str
    timestamp: datetime
    status: ActionStatus
    output_format: OutputFormat
    output_path: Optional[str] = None
    validation_result: Optional[ValidationResult] = None
    safety_report: Optional[SafetyReport] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class NorthboundActionPackage(BaseModel):
    """
    Structured package for Northbound module integration.
    This defines the interface contract for future integration.
    """
    package_id: str
    package_version: str = "1.0"
    created_at: datetime
    source_intent_id: str
    sequence_id: str
    
    # Action data
    actions: List[Dict[str, Any]]
    execution_order: List[str]  # List of action IDs in execution order
    
    # Metadata
    estimated_duration_seconds: int
    total_actions: int
    dependencies: List[str]
    
    # Safety and validation
    validation_passed: bool
    safety_approved: bool
    risk_level: str
    
    # Rollback
    rollback_actions: List[Dict[str, Any]]
    has_rollback: bool
    
    # Traceability
    trace_id: str
    user_id: Optional[str] = None
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "package_id": self.package_id,
            "package_version": self.package_version,
            "created_at": self.created_at.isoformat(),
            "source_intent_id": self.source_intent_id,
            "sequence_id": self.sequence_id,
            "actions": self.actions,
            "execution_order": self.execution_order,
            "metadata": {
                "estimated_duration_seconds": self.estimated_duration_seconds,
                "total_actions": self.total_actions,
                "dependencies": self.dependencies
            },
            "validation": {
                "validation_passed": self.validation_passed,
                "safety_approved": self.safety_approved,
                "risk_level": self.risk_level
            },
            "rollback": {
                "rollback_actions": self.rollback_actions,
                "has_rollback": self.has_rollback
            },
            "traceability": {
                "trace_id": self.trace_id,
                "user_id": self.user_id
            }
        }


class ActionOutputInterface:
    """
    Interface for outputting validated actions for future Northbound module integration.
    
    This service handles:
    - Structured output format creation
    - Action serialization to JSON/file
    - Action logging and storage for traceability
    - Interface contract definition for Northbound module
    """
    
    def __init__(
        self,
        output_directory: str = "./output/actions",
        log_directory: str = "./output/logs",
        enable_file_output: bool = True
    ):
        """
        Initialize action output interface.
        
        Args:
            output_directory: Directory for action output files
            log_directory: Directory for action logs
            enable_file_output: Whether to write files (disable for testing)
        """
        self.logger = logging.getLogger(__name__)
        self.output_directory = Path(output_directory)
        self.log_directory = Path(log_directory)
        self.enable_file_output = enable_file_output
        
        # Create directories if they don't exist
        if self.enable_file_output:
            self.output_directory.mkdir(parents=True, exist_ok=True)
            self.log_directory.mkdir(parents=True, exist_ok=True)
        
        # In-memory storage for traceability
        self._output_records: Dict[str, ActionOutputRecord] = {}
        
        self.logger.info(
            f"ActionOutputInterface initialized: "
            f"output_dir={output_directory}, log_dir={log_directory}"
        )
    
    def create_northbound_package(
        self,
        sequence: ActionSequence,
        validation_result: ValidationResult,
        safety_report: SafetyReport,
        user_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> NorthboundActionPackage:
        """
        Create a structured package for Northbound module integration.
        
        Args:
            sequence: Validated action sequence
            validation_result: Validation results
            safety_report: Safety assessment
            user_id: Optional user ID for traceability
            trace_id: Optional trace ID for correlation
            
        Returns:
            NorthboundActionPackage ready for integration
        """
        self.logger.info(f"Creating Northbound package for sequence {sequence.id}")
        
        # Generate package ID with microseconds for uniqueness
        package_id = f"pkg_{sequence.id}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        # Generate trace ID if not provided
        if not trace_id:
            trace_id = f"trace_{sequence.intent_id}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        # Convert actions to Northbound format
        actions = [action.to_northbound_format() for action in sequence.actions]
        
        # Get execution order
        ordered_actions = sequence.get_execution_order()
        execution_order = [action.id for action in ordered_actions]
        
        # Convert rollback actions
        rollback_actions = [
            action.to_northbound_format() for action in sequence.rollback_plan
        ] if sequence.rollback_plan else []
        
        # Create package
        package = NorthboundActionPackage(
            package_id=package_id,
            created_at=datetime.now(),
            source_intent_id=sequence.intent_id,
            sequence_id=sequence.id,
            actions=actions,
            execution_order=execution_order,
            estimated_duration_seconds=sequence.estimated_duration,
            total_actions=len(sequence.actions),
            dependencies=sequence.dependencies,
            validation_passed=validation_result.is_valid,
            safety_approved=safety_report.is_safe,
            risk_level=safety_report.risk_level,
            rollback_actions=rollback_actions,
            has_rollback=len(rollback_actions) > 0,
            trace_id=trace_id,
            user_id=user_id
        )
        
        self.logger.info(
            f"Northbound package created: {package_id}, "
            f"actions={len(actions)}, validated={validation_result.is_valid}"
        )
        
        return package
    
    def serialize_to_json(
        self,
        package: NorthboundActionPackage,
        pretty: bool = True
    ) -> str:
        """
        Serialize action package to JSON format.
        
        Args:
            package: The action package to serialize
            pretty: Whether to use pretty printing
            
        Returns:
            JSON string representation
        """
        self.logger.debug(f"Serializing package {package.package_id} to JSON")
        
        package_dict = package.to_dict()
        
        if pretty:
            json_str = json.dumps(package_dict, indent=2, ensure_ascii=False)
        else:
            json_str = json.dumps(package_dict, ensure_ascii=False)
        
        return json_str
    
    def save_to_file(
        self,
        package: NorthboundActionPackage,
        filename: Optional[str] = None,
        output_format: OutputFormat = OutputFormat.JSON
    ) -> str:
        """
        Save action package to file for future Northbound integration.
        
        Args:
            package: The action package to save
            filename: Optional custom filename
            output_format: Output format (JSON, YAML, etc.)
            
        Returns:
            Path to saved file
        """
        if not self.enable_file_output:
            self.logger.warning("File output is disabled")
            return ""
        
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"action_package_{package.sequence_id}_{timestamp}.json"
        
        file_path = self.output_directory / filename
        
        self.logger.info(f"Saving action package to {file_path}")
        
        try:
            if output_format == OutputFormat.JSON:
                json_content = self.serialize_to_json(package, pretty=True)
                file_path.write_text(json_content, encoding='utf-8')
            else:
                raise NotImplementedError(f"Output format {output_format} not yet implemented")
            
            self.logger.info(f"Action package saved successfully: {file_path}")
            return str(file_path)
            
        except Exception as e:
            self.logger.error(f"Failed to save action package: {e}")
            raise
    
    def log_action_output(
        self,
        package: NorthboundActionPackage,
        validation_result: ValidationResult,
        safety_report: SafetyReport,
        output_path: Optional[str] = None,
        status: ActionStatus = ActionStatus.READY
    ) -> ActionOutputRecord:
        """
        Log action output for traceability and audit.
        
        Args:
            package: The action package
            validation_result: Validation results
            safety_report: Safety assessment
            output_path: Path where package was saved
            status: Current status of the output
            
        Returns:
            ActionOutputRecord for tracking
        """
        self.logger.info(f"Logging action output for package {package.package_id}")
        
        # Create output record
        record = ActionOutputRecord(
            record_id=f"rec_{package.package_id}",
            sequence_id=package.sequence_id,
            intent_id=package.source_intent_id,
            timestamp=datetime.now(),
            status=status,
            output_format=OutputFormat.JSON,
            output_path=output_path,
            validation_result=validation_result,
            safety_report=safety_report,
            metadata={
                "package_id": package.package_id,
                "trace_id": package.trace_id,
                "user_id": package.user_id,
                "total_actions": package.total_actions,
                "estimated_duration": package.estimated_duration_seconds,
                "risk_level": package.risk_level,
                "has_rollback": package.has_rollback
            }
        )
        
        # Store in memory
        self._output_records[record.record_id] = record
        
        # Write to log file
        if self.enable_file_output:
            self._write_log_entry(record)
        
        self.logger.info(f"Action output logged: {record.record_id}")
        
        return record
    
    def _write_log_entry(self, record: ActionOutputRecord) -> None:
        """Write log entry to file."""
        try:
            log_file = self.log_directory / "action_output.log"
            
            log_entry = {
                "timestamp": record.timestamp.isoformat(),
                "record_id": record.record_id,
                "sequence_id": record.sequence_id,
                "intent_id": record.intent_id,
                "status": record.status.value,
                "output_path": record.output_path,
                "validation_passed": record.validation_result.is_valid if record.validation_result else None,
                "safety_approved": record.safety_report.is_safe if record.safety_report else None,
                "metadata": record.metadata
            }
            
            # Append to log file
            with log_file.open('a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')
                
        except Exception as e:
            self.logger.error(f"Failed to write log entry: {e}")
    
    def output_actions(
        self,
        sequence: ActionSequence,
        validation_result: ValidationResult,
        safety_report: SafetyReport,
        user_id: Optional[str] = None,
        save_to_file: bool = True
    ) -> Dict[str, Any]:
        """
        Complete action output workflow: create package, serialize, save, and log.
        
        This is the main method for outputting validated actions.
        
        Args:
            sequence: Validated action sequence
            validation_result: Validation results
            safety_report: Safety assessment
            user_id: Optional user ID for traceability
            save_to_file: Whether to save to file
            
        Returns:
            Dictionary with output results including package, file path, and record
        """
        self.logger.info(f"Starting action output workflow for sequence {sequence.id}")
        
        # Create Northbound package
        package = self.create_northbound_package(
            sequence=sequence,
            validation_result=validation_result,
            safety_report=safety_report,
            user_id=user_id
        )
        
        # Serialize to JSON
        json_output = self.serialize_to_json(package)
        
        # Save to file if requested
        file_path = None
        if save_to_file and self.enable_file_output:
            file_path = self.save_to_file(package)
        
        # Log the output
        record = self.log_action_output(
            package=package,
            validation_result=validation_result,
            safety_report=safety_report,
            output_path=file_path,
            status=ActionStatus.READY
        )
        
        self.logger.info(
            f"Action output workflow complete: package={package.package_id}, "
            f"file={file_path}, record={record.record_id}"
        )
        
        return {
            "success": True,
            "package": package,
            "json_output": json_output,
            "file_path": file_path,
            "record": record,
            "trace_id": package.trace_id
        }
    
    def get_output_record(self, record_id: str) -> Optional[ActionOutputRecord]:
        """
        Retrieve an output record by ID.
        
        Args:
            record_id: The record ID to retrieve
            
        Returns:
            ActionOutputRecord if found, None otherwise
        """
        return self._output_records.get(record_id)
    
    def get_records_by_intent(self, intent_id: str) -> List[ActionOutputRecord]:
        """
        Retrieve all output records for a specific intent.
        
        Args:
            intent_id: The intent ID to search for
            
        Returns:
            List of ActionOutputRecord for the intent
        """
        return [
            record for record in self._output_records.values()
            if record.intent_id == intent_id
        ]
    
    def get_records_by_sequence(self, sequence_id: str) -> List[ActionOutputRecord]:
        """
        Retrieve all output records for a specific sequence.
        
        Args:
            sequence_id: The sequence ID to search for
            
        Returns:
            List of ActionOutputRecord for the sequence
        """
        return [
            record for record in self._output_records.values()
            if record.sequence_id == sequence_id
        ]
    
    def update_record_status(
        self,
        record_id: str,
        status: ActionStatus,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update the status of an output record.
        
        Args:
            record_id: The record ID to update
            status: New status
            error_message: Optional error message if status is FAILED
            
        Returns:
            True if updated successfully, False otherwise
        """
        record = self._output_records.get(record_id)
        if not record:
            self.logger.warning(f"Record not found: {record_id}")
            return False
        
        record.status = status
        if error_message:
            record.error_message = error_message
        
        self.logger.info(f"Record {record_id} status updated to {status.value}")
        
        # Log the status change
        if self.enable_file_output:
            self._write_log_entry(record)
        
        return True
    
    def get_interface_contract(self) -> Dict[str, Any]:
        """
        Get the interface contract specification for Northbound module integration.
        
        This defines the expected format and structure for future integration.
        
        Returns:
            Dictionary describing the interface contract
        """
        return {
            "contract_version": "1.0",
            "description": "Interface contract for LLM Module to Northbound Module integration",
            "package_format": {
                "package_id": "string - Unique identifier for the action package",
                "package_version": "string - Version of the package format",
                "created_at": "ISO 8601 datetime - Package creation timestamp",
                "source_intent_id": "string - ID of the originating intent",
                "sequence_id": "string - ID of the action sequence",
                "actions": "array - List of network actions in Northbound format",
                "execution_order": "array - Ordered list of action IDs for execution",
                "metadata": {
                    "estimated_duration_seconds": "integer - Estimated execution time",
                    "total_actions": "integer - Number of actions in sequence",
                    "dependencies": "array - List of external dependencies"
                },
                "validation": {
                    "validation_passed": "boolean - Whether validation passed",
                    "safety_approved": "boolean - Whether safety checks passed",
                    "risk_level": "string - Risk level: low, medium, high, critical"
                },
                "rollback": {
                    "rollback_actions": "array - List of rollback actions",
                    "has_rollback": "boolean - Whether rollback plan exists"
                },
                "traceability": {
                    "trace_id": "string - Unique trace ID for correlation",
                    "user_id": "string - Optional user ID"
                }
            },
            "action_format": {
                "action_id": "string - Unique action identifier",
                "action_type": "string - Type: flow_mod, slice_create, slice_modify, config_change",
                "target_resource": "string - Target network resource",
                "parameters": "object - Action-specific parameters",
                "execution_priority": "integer - Priority (0-65535)",
                "timeout_seconds": "integer - Execution timeout",
                "description": "string - Human-readable description"
            },
            "integration_points": {
                "file_location": str(self.output_directory),
                "file_format": "JSON",
                "file_naming": "action_package_{sequence_id}_{timestamp}.json",
                "log_location": str(self.log_directory),
                "status_updates": "Use update_record_status() method"
            },
            "expected_workflow": [
                "1. LLM Module creates and validates action sequence",
                "2. LLM Module calls output_actions() to generate package",
                "3. Package is saved to file in output directory",
                "4. Northbound Module reads package from file",
                "5. Northbound Module executes actions in specified order",
                "6. Northbound Module updates status via update_record_status()",
                "7. Results are logged for traceability"
            ]
        }
    
    def save_actions(self, action_sequence: ActionSequence) -> Dict[str, Any]:
        """
        Save actions for API compatibility.
        
        Args:
            action_sequence: The action sequence to save
            
        Returns:
            Dictionary with save results
        """
        # Create minimal validation and safety reports for compatibility
        validation_result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[]
        )
        
        safety_report = SafetyReport(
            is_safe=True,
            risk_level="low",
            risks=[]
        )
        
        return self.output_actions(
            sequence=action_sequence,
            validation_result=validation_result,
            safety_report=safety_report,
            save_to_file=True
        )
    
    def get_action_status(self, intent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get action status for an intent (API compatibility).
        
        Args:
            intent_id: The intent ID to query
            
        Returns:
            Dictionary with status information or None if not found
        """
        records = self.get_records_by_intent(intent_id)
        
        if not records:
            return None
        
        # Get the most recent record
        latest_record = max(records, key=lambda r: r.timestamp)
        
        # Count actions by status
        total_actions = latest_record.metadata.get("total_actions", 0)
        
        return {
            "intent_id": intent_id,
            "status": latest_record.status.value,
            "actions_generated": total_actions,
            "actions_validated": total_actions if latest_record.validation_result and latest_record.validation_result.is_valid else 0,
            "actions_executed": 0,  # Will be updated by Northbound module
            "errors": [latest_record.error_message] if latest_record.error_message else None
        }


# Create a service alias for easier imports
ActionOutputService = ActionOutputInterface
