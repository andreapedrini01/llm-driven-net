"""
Action Processor - Simplified action processing without API/database dependencies
Extracts core action processing logic for direct file-based operation
"""

import logging
import time
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass

# Import core dependencies (preserved from original architecture)
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from models.action_models import NetworkAction, ActionType
from connectors.comnetsemu_connector import create_comnetsemu_connector
from core.retry_system import AdvancedRetrySystem, RetryConfig


class ExecutionStatus(str, Enum):
    """Status of action execution."""
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class ExecutionResult:
    """Result of action execution."""
    action_id: str
    status: ExecutionStatus
    timestamp: datetime
    duration: float
    message: str
    error: Optional[str] = None
    network_state_before: Optional[Dict] = None
    network_state_after: Optional[Dict] = None


class ActionProcessor:
    """
    Simplified action processor for direct file-based operation.
    
    Responsibilities:
    - Validate network actions (structure and parameters)
    - Execute actions using ComnetsEMU connector
    - Apply retry logic for error handling
    - Return execution results
    
    Does NOT depend on:
    - API Gateway
    - Database Manager
    - Monitoring services
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize action processor with configuration.
        
        Args:
            config: Configuration dictionary with:
                - comnetsemu_host: ComnetsEMU host address
                - comnetsemu_port: ComnetsEMU port
                - max_retries: Maximum retry attempts
                - retry_delay: Base delay between retries
                - timeout_seconds: Timeout for operations
        """
        self.logger = logging.getLogger("ActionProcessor")
        self.config = config
        
        # Initialize ComnetsEMU connector
        comnetsemu_host = config.get("comnetsemu_host", "localhost")
        comnetsemu_port = config.get("comnetsemu_port", 6653)
        timeout_seconds = config.get("timeout_seconds", 30)
        
        self.logger.info(f"Initializing ComnetsEMU connector to {comnetsemu_host}:{comnetsemu_port}")
        self.comnetsemu_connector = create_comnetsemu_connector(
            host=comnetsemu_host,
            port=comnetsemu_port,
            timeout_seconds=timeout_seconds
        )
        
        # Initialize retry system
        max_retries = config.get("max_retries", 3)
        retry_delay = config.get("retry_delay", 2.0)
        
        retry_config = RetryConfig(
            max_attempts=max_retries,
            base_delay=retry_delay,
            max_delay=60.0,
            failure_threshold=3,
            recovery_timeout=45.0,
            enable_persistent_queue=False  # Simplified: no persistent queue
        )
        self.retry_system = AdvancedRetrySystem(retry_config)
        
        self.logger.info("Action processor initialized successfully")
    
    def validate_action(self, action: NetworkAction) -> Dict[str, Any]:
        """
        Validate action structure and parameters.
        
        Args:
            action: NetworkAction to validate
            
        Returns:
            Dictionary with validation results:
                - is_valid: bool
                - errors: List[str]
                - warnings: List[str]
        """
        errors = []
        warnings = []
        
        try:
            # Validate action ID
            if not action.id or not isinstance(action.id, str):
                errors.append("Action ID must be a non-empty string")
            
            # Validate target
            if not action.target or not isinstance(action.target, str):
                errors.append("Target must be a non-empty string")
            
            # Validate priority
            if not isinstance(action.priority, int) or action.priority < 0 or action.priority > 65535:
                errors.append("Priority must be an integer between 0 and 65535")
            
            # Validate timeout
            if not isinstance(action.timeout, int) or action.timeout < 1:
                errors.append("Timeout must be a positive integer")
            
            # Validate parameters based on action type
            param_validation = action.validate_action_parameters()
            if not param_validation["is_valid"]:
                errors.extend(param_validation["issues"])
            warnings.extend(param_validation["warnings"])
            
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
            self.logger.error(f"Error validating action {action.id}: {e}")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def execute_action(self, action: NetworkAction) -> ExecutionResult:
        """
        Execute a single network action with retry logic.
        
        Args:
            action: NetworkAction to execute
            
        Returns:
            ExecutionResult with execution details
        """
        start_time = time.time()
        
        # Validate action first
        validation = self.validate_action(action)
        if not validation["is_valid"]:
            duration = time.time() - start_time
            error_msg = f"Action validation failed: {', '.join(validation['errors'])}"
            self.logger.error(error_msg)
            
            return ExecutionResult(
                action_id=action.id,
                status=ExecutionStatus.FAILED,
                timestamp=datetime.now(),
                duration=duration,
                message="Validation failed",
                error=error_msg
            )
        
        # Log warnings if any
        if validation["warnings"]:
            for warning in validation["warnings"]:
                self.logger.warning(f"Action {action.id}: {warning}")
        
        # Get network state before execution
        try:
            state_before = self.comnetsemu_connector.get_network_state(action.target)
        except Exception as e:
            self.logger.warning(f"Failed to get network state before execution: {e}")
            state_before = None
        
        # Execute action with retry logic
        try:
            self.logger.info(f"Executing action {action.id} (type: {action.type}, target: {action.target})")
            
            def _execute():
                """Internal execution function for retry system."""
                if action.type == ActionType.FLOW_MOD:
                    return self._execute_flow_mod(action)
                elif action.type == ActionType.SLICE_CREATE:
                    return self._execute_slice_create(action)
                elif action.type == ActionType.CONFIG_CHANGE:
                    return self._execute_config_change(action)
                else:
                    raise ValueError(f"Unknown action type: {action.type}")
            
            # Use retry system for execution
            retry_result = self.retry_system.execute_with_retry(
                _execute,
                service_name="comnetsemu"
            )
            
            if retry_result.success:
                # Get network state after execution
                try:
                    state_after = self.comnetsemu_connector.get_network_state(action.target)
                except Exception as e:
                    self.logger.warning(f"Failed to get network state after execution: {e}")
                    state_after = None
                
                duration = time.time() - start_time
                
                return ExecutionResult(
                    action_id=action.id,
                    status=ExecutionStatus.SUCCESS,
                    timestamp=datetime.now(),
                    duration=duration,
                    message=f"Action executed successfully (attempts: {len(retry_result.attempts)})",
                    network_state_before=state_before,
                    network_state_after=state_after
                )
            else:
                # Execution failed after retries
                duration = time.time() - start_time
                error_msg = f"Action failed after {len(retry_result.attempts)} attempts: {retry_result.error}"
                
                return ExecutionResult(
                    action_id=action.id,
                    status=ExecutionStatus.FAILED,
                    timestamp=datetime.now(),
                    duration=duration,
                    message="Action failed after all retries",
                    error=error_msg,
                    network_state_before=state_before
                )
                
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            self.logger.error(f"Failed to execute action {action.id}: {e}")
            
            return ExecutionResult(
                action_id=action.id,
                status=ExecutionStatus.FAILED,
                timestamp=datetime.now(),
                duration=duration,
                message="Action execution error",
                error=error_msg,
                network_state_before=state_before
            )
    
    def _execute_flow_mod(self, action: NetworkAction) -> Dict[str, Any]:
        """Execute flow modification action."""
        self.logger.debug(f"Executing flow_mod for action {action.id}")
        
        # Extract parameters
        operation = action.parameters.get("operation", "add")
        match_fields = action.parameters.get("match", {})
        actions = action.parameters.get("actions", [])
        
        # Use ComnetsEMU connector (which may delegate to RYU for flow operations)
        # For now, we'll use the topology change method as a placeholder
        # In a real implementation, this would call a specific flow_mod method
        result = self.comnetsemu_connector.execute_topology_change(action)
        
        if result.get("success"):
            return {
                "success": True,
                "message": f"Flow modification {operation} completed",
                "operation": operation,
                "match": match_fields,
                "actions": actions
            }
        else:
            raise RuntimeError(f"Flow modification failed: {result.get('error', 'Unknown error')}")
    
    def _execute_slice_create(self, action: NetworkAction) -> Dict[str, Any]:
        """Execute slice creation action."""
        self.logger.debug(f"Executing slice_create for action {action.id}")
        
        # Extract parameters
        slice_name = action.parameters.get("slice_name", f"slice_{action.id}")
        resources = action.parameters.get("resources", {})
        
        # Convert to topology change format
        topology_action = NetworkAction(
            id=action.id,
            type=ActionType.CONFIG_CHANGE,
            target=action.target,
            parameters={
                "operation": "add",
                "element_type": "slice",
                "element_id": slice_name,
                "properties": resources
            },
            priority=action.priority,
            timeout=action.timeout,
            description=action.description
        )
        
        result = self.comnetsemu_connector.execute_topology_change(topology_action)
        
        if result.get("success"):
            return {
                "success": True,
                "message": "Slice creation completed",
                "slice_name": slice_name,
                "resources": resources
            }
        else:
            raise RuntimeError(f"Slice creation failed: {result.get('error', 'Unknown error')}")
    
    def _execute_config_change(self, action: NetworkAction) -> Dict[str, Any]:
        """Execute configuration change action."""
        self.logger.debug(f"Executing config_change for action {action.id}")
        
        config_type = action.parameters.get("config_type", "unknown")
        
        if config_type == "qos":
            # Execute QoS policy
            result = self.comnetsemu_connector.execute_qos_policy(action)
        else:
            # Generic topology change
            result = self.comnetsemu_connector.execute_topology_change(action)
        
        if result.get("success"):
            return {
                "success": True,
                "message": f"Configuration change ({config_type}) completed",
                "config_type": config_type
            }
        else:
            raise RuntimeError(f"Configuration change failed: {result.get('error', 'Unknown error')}")
    
    def execute_actions_sequence(self, actions: List[NetworkAction]) -> List[ExecutionResult]:
        """
        Execute a sequence of actions in order.
        
        Args:
            actions: List of NetworkAction objects to execute
            
        Returns:
            List of ExecutionResult objects
        """
        results = []
        
        self.logger.info(f"Executing sequence of {len(actions)} actions")
        
        for action in actions:
            result = self.execute_action(action)
            results.append(result)
            
            # Stop on first failure (can be made configurable)
            if result.status == ExecutionStatus.FAILED:
                self.logger.error(f"Action {action.id} failed, stopping sequence execution")
                break
        
        successful = sum(1 for r in results if r.status == ExecutionStatus.SUCCESS)
        self.logger.info(f"Sequence execution completed: {successful}/{len(results)} actions successful")
        
        return results
    
    def get_connector_status(self) -> Dict[str, Any]:
        """
        Get status of ComnetsEMU connector.
        
        Returns:
            Dictionary with connector status information
        """
        try:
            return self.comnetsemu_connector.get_connection_status()
        except Exception as e:
            self.logger.error(f"Failed to get connector status: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def close(self):
        """Clean up resources."""
        self.logger.info("Closing action processor")
        try:
            self.comnetsemu_connector.close()
        except Exception as e:
            self.logger.error(f"Error closing connector: {e}")
