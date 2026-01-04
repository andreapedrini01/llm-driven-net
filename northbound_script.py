"""
Northbound Script for LLM-driven Network
Receives LLM output and applies changes to ComnetsEMU network
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass
import time
import traceback
from enum import Enum

# Assumo che i modelli siano importabili dal file che mi hai fornito
from action_models import (
    NetworkAction, ActionSequence, ActionType,
    ValidationResult, SafetyReport, SimulationResult
)


class ExecutionStatus(str, Enum):
    """Status of action execution."""
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
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


class NetworkLogger:
    """Handles all logging operations with multiple output formats."""
    
    def __init__(self, log_dir: str = "./logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup file logging
        self.setup_file_logger()
        
        # Setup database logging
        self.db_path = self.log_dir / "network_changes.db"
        self.setup_database()
        
        # JSON log file for structured data
        self.json_log_path = self.log_dir / "actions.jsonl"
    
    def setup_file_logger(self):
        """Setup standard file logger."""
        log_file = self.log_dir / f"northbound_{datetime.now().strftime('%Y%m%d')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger("NorthboundScript")
    
    def setup_database(self):
        """Setup SQLite database for queryable logs."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS action_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_id TEXT NOT NULL,
                sequence_id TEXT,
                action_type TEXT NOT NULL,
                target TEXT NOT NULL,
                status TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                duration REAL,
                parameters TEXT,
                error_message TEXT,
                state_before TEXT,
                state_after TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sequence_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sequence_id TEXT NOT NULL,
                intent_id TEXT NOT NULL,
                status TEXT NOT NULL,
                start_time DATETIME NOT NULL,
                end_time DATETIME,
                total_actions INTEGER,
                successful_actions INTEGER,
                failed_actions INTEGER,
                error_summary TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS network_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL,
                target TEXT,
                action_id TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def log_action_execution(self, result: ExecutionResult, sequence_id: Optional[str] = None):
        """Log action execution to all outputs."""
        # File log
        self.logger.info(
            f"Action {result.action_id}: {result.status.value} - {result.message} "
            f"(Duration: {result.duration:.2f}s)"
        )
        
        if result.error:
            self.logger.error(f"Error in {result.action_id}: {result.error}")
        
        # Database log
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO action_executions 
            (action_id, sequence_id, action_type, target, status, timestamp, 
             duration, error_message, state_before, state_after)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            result.action_id,
            sequence_id,
            "unknown",  # Would be filled from action object
            "unknown",
            result.status.value,
            result.timestamp.isoformat(),
            result.duration,
            result.error,
            json.dumps(result.network_state_before) if result.network_state_before else None,
            json.dumps(result.network_state_after) if result.network_state_after else None
        ))
        
        conn.commit()
        conn.close()
        
        # JSON log
        log_entry = {
            "action_id": result.action_id,
            "sequence_id": sequence_id,
            "status": result.status.value,
            "timestamp": result.timestamp.isoformat(),
            "duration": result.duration,
            "message": result.message,
            "error": result.error
        }
        
        with open(self.json_log_path, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def log_sequence_execution(self, sequence_id: str, intent_id: str, 
                              status: ExecutionStatus, results: List[ExecutionResult]):
        """Log sequence execution summary."""
        successful = sum(1 for r in results if r.status == ExecutionStatus.SUCCESS)
        failed = sum(1 for r in results if r.status == ExecutionStatus.FAILED)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO sequence_executions 
            (sequence_id, intent_id, status, start_time, end_time, 
             total_actions, successful_actions, failed_actions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            sequence_id,
            intent_id,
            status.value,
            results[0].timestamp.isoformat() if results else datetime.now().isoformat(),
            results[-1].timestamp.isoformat() if results else datetime.now().isoformat(),
            len(results),
            successful,
            failed
        ))
        
        conn.commit()
        conn.close()
        
        self.logger.info(
            f"Sequence {sequence_id} completed: {successful}/{len(results)} actions successful"
        )
    
    def log_metric(self, metric_name: str, value: float, target: str, action_id: str):
        """Log network metric."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO network_metrics (timestamp, metric_name, metric_value, target, action_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), metric_name, value, target, action_id))
        
        conn.commit()
        conn.close()


class ComnetsEMUInterface:
    """Interface to ComnetsEMU network."""
    
    def __init__(self, controller_url: str = "http://localhost:8080"):
        self.controller_url = controller_url
        self.logger = logging.getLogger("ComnetsEMUInterface")
    
    def get_network_state(self, target: str) -> Dict[str, Any]:
        """Get current state of network resource."""
        # Placeholder - implementa con API reali di ComnetsEMU
        self.logger.info(f"Getting state for {target}")
        return {
            "target": target,
            "status": "active",
            "timestamp": datetime.now().isoformat()
        }
    
    def execute_flow_mod(self, action: NetworkAction) -> Dict[str, Any]:
        """Execute flow modification."""
        self.logger.info(f"Executing flow_mod on {action.target}")
        
        # Simulazione - sostituisci con chiamate reali
        # Esempio: curl -X POST http://controller/flows -d {...}
        
        return {
            "success": True,
            "flow_id": f"flow_{action.id}",
            "message": "Flow rule installed"
        }
    
    def execute_slice_create(self, action: NetworkAction) -> Dict[str, Any]:
        """Execute slice creation."""
        self.logger.info(f"Creating slice: {action.parameters.get('slice_name')}")
        
        # Implementa creazione slice
        return {
            "success": True,
            "slice_id": f"slice_{action.id}",
            "message": "Slice created"
        }
    
    def execute_config_change(self, action: NetworkAction) -> Dict[str, Any]:
        """Execute configuration change."""
        self.logger.info(f"Changing config on {action.target}")
        
        # Implementa cambio configurazione
        return {
            "success": True,
            "message": "Configuration updated"
        }
    
    def verify_action_applied(self, action: NetworkAction) -> bool:
        """Verify that action was successfully applied."""
        # Implementa verifica stato rete
        return True


class NorthboundScript:
    """Main Northbound Script orchestrator."""
    
    def __init__(self, log_dir: str = "./logs"):
        self.logger_handler = NetworkLogger(log_dir)
        self.network_interface = ComnetsEMUInterface()
        self.logger = logging.getLogger("NorthboundScript")
        
        # Configuration
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        self.enable_rollback = True
    
    def parse_llm_output(self, llm_output: str) -> ActionSequence:
        """Parse LLM output into ActionSequence."""
        try:
            # Assume LLM output is JSON formatted
            data = json.loads(llm_output)
            
            # Convert to ActionSequence object
            sequence = ActionSequence(**data)
            
            self.logger.info(f"Parsed sequence {sequence.id} with {len(sequence.actions)} actions")
            return sequence
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON: {e}")
            raise ValueError(f"Invalid JSON in LLM output: {e}")
        except Exception as e:
            self.logger.error(f"Failed to parse LLM output: {e}")
            raise
    
    def validate_sequence(self, sequence: ActionSequence) -> ValidationResult:
        """Validate action sequence before execution."""
        errors = []
        warnings = []
        
        # Validate sequence integrity
        integrity = sequence.validate_sequence_integrity()
        if not integrity["is_valid"]:
            errors.extend(integrity["issues"])
        warnings.extend(integrity["warnings"])
        
        # Validate individual actions
        for action in sequence.actions:
            validation = action.validate_action_parameters()
            if not validation["is_valid"]:
                errors.extend([f"Action {action.id}: {issue}" for issue in validation["issues"]])
            warnings.extend([f"Action {action.id}: {warn}" for warn in validation["warnings"]])
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def execute_action(self, action: NetworkAction) -> ExecutionResult:
        """Execute single network action with retry logic."""
        start_time = time.time()
        state_before = self.network_interface.get_network_state(action.target)
        
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"Executing action {action.id} (attempt {attempt + 1}/{self.max_retries})")
                
                # Execute based on action type
                if action.type == ActionType.FLOW_MOD:
                    result = self.network_interface.execute_flow_mod(action)
                elif action.type == ActionType.SLICE_CREATE:
                    result = self.network_interface.execute_slice_create(action)
                elif action.type == ActionType.CONFIG_CHANGE:
                    result = self.network_interface.execute_config_change(action)
                else:
                    raise ValueError(f"Unknown action type: {action.type}")
                
                # Verify execution
                if not self.network_interface.verify_action_applied(action):
                    raise RuntimeError("Action applied but verification failed")
                
                state_after = self.network_interface.get_network_state(action.target)
                duration = time.time() - start_time
                
                return ExecutionResult(
                    action_id=action.id,
                    status=ExecutionStatus.SUCCESS,
                    timestamp=datetime.now(),
                    duration=duration,
                    message=f"Action executed successfully: {result.get('message', '')}",
                    network_state_before=state_before,
                    network_state_after=state_after
                )
                
            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    # Final attempt failed
                    duration = time.time() - start_time
                    return ExecutionResult(
                        action_id=action.id,
                        status=ExecutionStatus.FAILED,
                        timestamp=datetime.now(),
                        duration=duration,
                        message="Action failed after all retries",
                        error=f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}",
                        network_state_before=state_before
                    )
        
        # Should not reach here, but just in case
        return ExecutionResult(
            action_id=action.id,
            status=ExecutionStatus.FAILED,
            timestamp=datetime.now(),
            duration=time.time() - start_time,
            message="Unknown failure",
            error="Exhausted retries without clear result"
        )
    
    def rollback_action(self, action: NetworkAction) -> ExecutionResult:
        """Rollback a previously executed action."""
        self.logger.warning(f"Rolling back action {action.id}")
        
        # Execute rollback action
        result = self.execute_action(action)
        result.status = ExecutionStatus.ROLLED_BACK
        
        return result
    
    def execute_sequence(self, sequence: ActionSequence) -> List[ExecutionResult]:
        """Execute action sequence with rollback on failure."""
        results = []
        executed_actions = []
        
        # Get execution order
        ordered_actions = sequence.get_execution_order()
        
        self.logger.info(f"Starting execution of sequence {sequence.id}")
        
        for action in ordered_actions:
            result = self.execute_action(action)
            results.append(result)
            
            # Log immediately
            self.logger_handler.log_action_execution(result, sequence.id)
            
            if result.status == ExecutionStatus.SUCCESS:
                executed_actions.append(action)
            else:
                # Action failed - trigger rollback if enabled
                self.logger.error(f"Action {action.id} failed, initiating rollback")
                
                if self.enable_rollback and sequence.rollback_plan:
                    self.logger.info("Executing rollback plan")
                    for rollback_action in reversed(sequence.rollback_plan):
                        rollback_result = self.rollback_action(rollback_action)
                        results.append(rollback_result)
                        self.logger_handler.log_action_execution(rollback_result, sequence.id)
                
                break  # Stop execution on first failure
        
        # Log sequence summary
        final_status = ExecutionStatus.SUCCESS if all(
            r.status == ExecutionStatus.SUCCESS for r in results
        ) else ExecutionStatus.FAILED
        
        self.logger_handler.log_sequence_execution(
            sequence.id, sequence.intent_id, final_status, results
        )
        
        return results
    
    def process_llm_output(self, llm_output: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Main entry point: process LLM output and apply to network.
        
        Args:
            llm_output: JSON string from LLM
            dry_run: If True, validate but don't execute
        
        Returns:
            Dictionary with execution results
        """
        try:
            # Parse LLM output
            sequence = self.parse_llm_output(llm_output)
            
            # Validate
            validation = self.validate_sequence(sequence)
            
            if not validation.is_valid:
                self.logger.error(f"Validation failed: {validation.errors}")
                return {
                    "success": False,
                    "sequence_id": sequence.id,
                    "validation": validation.dict(),
                    "message": "Sequence validation failed"
                }
            
            if validation.warnings:
                self.logger.warning(f"Validation warnings: {validation.warnings}")
            
            if dry_run:
                self.logger.info("Dry run mode - skipping execution")
                return {
                    "success": True,
                    "sequence_id": sequence.id,
                    "validation": validation.dict(),
                    "message": "Dry run completed - sequence is valid"
                }
            
            # Execute sequence
            results = self.execute_sequence(sequence)
            
            # Prepare response
            success = all(r.status == ExecutionStatus.SUCCESS for r in results)
            
            return {
                "success": success,
                "sequence_id": sequence.id,
                "intent_id": sequence.intent_id,
                "total_actions": len(results),
                "successful_actions": sum(1 for r in results if r.status == ExecutionStatus.SUCCESS),
                "failed_actions": sum(1 for r in results if r.status == ExecutionStatus.FAILED),
                "results": [
                    {
                        "action_id": r.action_id,
                        "status": r.status.value,
                        "duration": r.duration,
                        "message": r.message,
                        "error": r.error
                    }
                    for r in results
                ],
                "message": "Sequence execution completed"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to process LLM output: {e}")
            self.logger.error(traceback.format_exc())
            
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "message": "Failed to process LLM output"
            }


# Example usage
if __name__ == "__main__":
    # Initialize Northbound Script
    northbound = NorthboundScript(log_dir="./logs")
    
    # Example LLM output
    llm_output = json.dumps({
        "id": "seq_001",
        "intent_id": "intent_block_traffic",
        "estimated_duration": 10,
        "actions": [
            {
                "id": "action_001",
                "type": "flow_mod",
                "target": "switch-1",
                "parameters": {
                    "match": {
                        "ip_src": "192.168.1.100"
                    },
                    "actions": ["drop"]
                },
                "priority": 1000,
                "timeout": 30,
                "description": "Block traffic from suspicious IP"
            }
        ],
        "dependencies": [],
        "rollback_plan": [
            {
                "id": "rollback_001",
                "type": "flow_mod",
                "target": "switch-1",
                "parameters": {
                    "match": {
                        "ip_src": "192.168.1.100"
                    },
                    "actions": ["normal"]
                },
                "priority": 1000,
                "timeout": 30
            }
        ]
    })
    
    # Process (dry run first)
    print("=== DRY RUN ===")
    result = northbound.process_llm_output(llm_output, dry_run=True)
    print(json.dumps(result, indent=2))
    
    # Execute for real
    print("\n=== ACTUAL EXECUTION ===")
    result = northbound.process_llm_output(llm_output, dry_run=False)
    print(json.dumps(result, indent=2))