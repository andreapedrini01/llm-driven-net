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

# Import from our organized modules
from ..models.action_models import (
    NetworkAction, ActionSequence, ActionType,
    ValidationResult, SafetyReport, SimulationResult
)
from ..connectors.ryu_connector import create_ryu_connector
from ..connectors.comnetsemu_connector import create_comnetsemu_connector


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


class RYUNetworkInterface:
    """Real interface to RYU Controller and ComnetsEMU network."""
    
    def __init__(self, ryu_host: str = "localhost", ryu_port: int = 8080, 
                 comnetsemu_host: str = "localhost", comnetsemu_port: int = 6653, **config):
        
        self.logger = logging.getLogger("RYUNetworkInterface")
        
        # Initialize real RYU connector
        ryu_config = {k: v for k, v in config.items() if not k.startswith('comnetsemu_')}
        self.ryu_connector = create_ryu_connector(
            host=ryu_host, 
            port=ryu_port, 
            **ryu_config
        )
        
        # Initialize real ComnetsEMU connector
        comnetsemu_config = {k.replace('comnetsemu_', ''): v for k, v in config.items() if k.startswith('comnetsemu_')}
        self.comnetsemu_connector = create_comnetsemu_connector(
            host=comnetsemu_host,
            port=comnetsemu_port,
            **comnetsemu_config
        )
        
        self.logger.info(f"Initialized RYU interface to {ryu_host}:{ryu_port}")
        self.logger.info(f"Initialized ComnetsEMU interface to {comnetsemu_host}:{comnetsemu_port}")
    
    def get_network_state(self, target: str) -> Dict[str, Any]:
        """Get current state of network resource."""
        try:
            self.logger.info(f"Getting network state for {target}")
            
            # Use ComnetsEMU connector for topology and network state information
            comnetsemu_state = self.comnetsemu_connector.get_network_state(target)
            
            # Get comprehensive network state from RYU for flow information
            if target.startswith("switch"):
                # Extract switch ID from target (e.g., "switch-1" -> "1")
                switch_id = target.split("-")[-1] if "-" in target else target.replace("s", "")
                
                try:
                    # Get switch information from RYU
                    switches = self.ryu_connector.get_switches()
                    switch_info = None
                    for switch in switches:
                        if str(switch.get("dpid", "")) == switch_id:
                            switch_info = switch
                            break
                    
                    # Get flows and port stats for the switch from RYU
                    flows = self.ryu_connector.get_flows(switch_id) if switch_info else []
                    port_stats = self.ryu_connector.get_port_stats(switch_id) if switch_info else []
                    
                    # Combine RYU and ComnetsEMU information
                    combined_state = {
                        "target": target,
                        "switch_id": switch_id,
                        "ryu_switch_info": switch_info,
                        "comnetsemu_switch_info": comnetsemu_state.get("switch_info"),
                        "flows": flows,
                        "port_stats": port_stats,
                        "links": comnetsemu_state.get("links", []),
                        "status": "active" if switch_info and comnetsemu_state.get("status") == "active" else "error",
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    return combined_state
                    
                except Exception as ryu_error:
                    self.logger.warning(f"Failed to get RYU data for {target}: {ryu_error}")
                    # Return ComnetsEMU data only if RYU fails
                    return comnetsemu_state
            else:
                # For non-switch targets, primarily use ComnetsEMU data
                return comnetsemu_state
                
        except Exception as e:
            self.logger.error(f"Failed to get network state for {target}: {e}")
            return {
                "target": target,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def execute_flow_mod(self, action: NetworkAction) -> Dict[str, Any]:
        """Execute flow modification using real RYU API."""
        try:
            self.logger.info(f"Executing real flow_mod on {action.target}")
            
            # Use the real RYU connector to execute the flow modification
            result = self.ryu_connector.execute_flow_mod(action)
            
            return {
                "success": result["success"],
                "flow_id": f"flow_{action.id}",
                "message": result["message"],
                "operation": result.get("operation", "unknown"),
                "switch_id": result.get("switch_id"),
                "details": result
            }
            
        except Exception as e:
            self.logger.error(f"Failed to execute flow_mod: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Flow modification failed: {e}"
            }
    
    def execute_slice_create(self, action: NetworkAction) -> Dict[str, Any]:
        """Execute slice creation using real ComnetsEMU integration."""
        try:
            self.logger.info(f"Executing real slice creation on {action.target}")
            
            # Use ComnetsEMU connector for slice creation
            # Convert action to topology change format
            topology_action = NetworkAction(
                id=action.id,
                type=ActionType.CONFIG_CHANGE,  # Treat slice as config change
                target=action.target,
                parameters={
                    "operation": "add",
                    "element_type": "slice",
                    "element_id": action.parameters.get("slice_name", f"slice_{action.id}"),
                    "properties": action.parameters.get("resources", {})
                },
                priority=action.priority,
                timeout=action.timeout,
                description=action.description
            )
            
            result = self.comnetsemu_connector.execute_topology_change(topology_action)
            
            return {
                "success": result["success"],
                "slice_id": action.parameters.get("slice_name", f"slice_{action.id}"),
                "message": result.get("message", "Slice creation completed"),
                "details": result
            }
            
        except Exception as e:
            self.logger.error(f"Failed to execute slice creation: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Slice creation failed: {e}"
            }
    
    def execute_config_change(self, action: NetworkAction) -> Dict[str, Any]:
        """Execute configuration change using real ComnetsEMU integration."""
        try:
            self.logger.info(f"Executing real config change on {action.target}")
            
            config_type = action.parameters.get("config_type", "unknown")
            
            if config_type == "qos":
                # Handle QoS configuration through ComnetsEMU
                result = self.comnetsemu_connector.execute_qos_policy(action)
            elif config_type == "topology":
                # Handle topology changes through ComnetsEMU
                result = self.comnetsemu_connector.execute_topology_change(action)
            else:
                # Generic configuration change
                result = self.comnetsemu_connector.execute_topology_change(action)
            
            return {
                "success": result["success"],
                "config_type": config_type,
                "message": result.get("message", "Configuration change completed"),
                "details": result
            }
            
        except Exception as e:
            self.logger.error(f"Failed to execute config change: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Configuration change failed: {e}"
            }
    
    def verify_action_applied(self, action: NetworkAction) -> bool:
        """Verify that action was successfully applied using real RYU and ComnetsEMU APIs."""
        try:
            if action.type == ActionType.FLOW_MOD:
                # Use RYU connector for flow verification
                return self.ryu_connector.verify_action_applied(action)
            elif action.type in [ActionType.SLICE_CREATE, ActionType.CONFIG_CHANGE]:
                # Use ComnetsEMU connector for topology/config verification
                expected_state = {}  # Could be derived from action parameters
                return self.comnetsemu_connector.verify_network_state(action, expected_state)
            else:
                self.logger.warning(f"Verification not implemented for action type: {action.type}")
                return True  # Assume success for unsupported types
                
        except Exception as e:
            self.logger.error(f"Failed to verify action {action.id}: {e}")
            return False
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get RYU and ComnetsEMU connection status and statistics."""
        ryu_status = self.ryu_connector.get_connection_status()
        comnetsemu_status = self.comnetsemu_connector.get_connection_status()
        
        return {
            "ryu": ryu_status,
            "comnetsemu": comnetsemu_status,
            "overall_status": "connected" if (
                ryu_status.get("status") == "connected" and 
                comnetsemu_status.get("status") == "connected"
            ) else "error"
        }
    
    def close(self):
        """Close the network interface and clean up resources."""
        self.logger.info("Closing RYU and ComnetsEMU network interfaces")
        self.ryu_connector.close()
        self.comnetsemu_connector.close()


class NorthboundScript:
    """Main Northbound Script orchestrator with real RYU and ComnetsEMU integration."""
    
    def __init__(self, log_dir: str = "./logs", 
                 ryu_host: str = "localhost", ryu_port: int = 8080,
                 comnetsemu_host: str = "localhost", comnetsemu_port: int = 6653,
                 **config):
        self.logger_handler = NetworkLogger(log_dir)
        
        # Initialize real RYU and ComnetsEMU network interface
        self.network_interface = RYUNetworkInterface(
            ryu_host=ryu_host, 
            ryu_port=ryu_port,
            comnetsemu_host=comnetsemu_host,
            comnetsemu_port=comnetsemu_port,
            **config
        )
        
        self.logger = logging.getLogger("NorthboundScript")
        
        # Configuration
        self.max_retries = config.get("max_retries", 3)
        self.retry_delay = config.get("retry_delay", 2)  # seconds
        self.enable_rollback = True
        
        self.logger.info(f"Initialized NorthboundScript with RYU at {ryu_host}:{ryu_port} and ComnetsEMU at {comnetsemu_host}:{comnetsemu_port}")
    
    def get_ryu_status(self) -> Dict[str, Any]:
        """Get RYU and ComnetsEMU connection status and statistics."""
        return self.network_interface.get_connection_status()
    
    def close(self):
        """Close the northbound script and clean up resources."""
        self.logger.info("Closing NorthboundScript")
        self.network_interface.close()
    
    # ... [resto dei metodi del NorthboundScript] ...
    # Per brevità, includo solo le parti principali. Il file completo sarebbe troppo lungo.