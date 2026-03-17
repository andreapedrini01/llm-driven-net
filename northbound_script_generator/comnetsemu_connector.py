"""
Simplified ComnetsEMU Connector
Essential network connectivity without complex topology management
"""

import logging
import socket
import time
from datetime import datetime
from typing import Dict, Any
from dataclasses import dataclass
from enum import Enum

from .models import NetworkAction, ActionType
from .retry_system import SimpleRetrySystem, RetryConfig


class ConnectionStatus(str, Enum):
    """Status of ComnetsEMU connection."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class ComnetsEMUConfig:
    """Configuration for ComnetsEMU connection."""
    host: str = "localhost"
    port: int = 6653
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay: float = 2.0


class ComnetsEMUConnector:
    """Simplified ComnetsEMU connector for network operations."""
    
    def __init__(self, config: ComnetsEMUConfig = None):
        self.config = config or ComnetsEMUConfig()
        self.logger = logging.getLogger("ComnetsEMUConnector")
        
        # Initialize retry system
        retry_config = RetryConfig(
            max_attempts=self.config.max_retries + 1,
            base_delay=self.config.retry_delay,
            max_delay=60.0
        )
        self.retry_system = SimpleRetrySystem(retry_config)
        
        # Connection state
        self.status = ConnectionStatus.DISCONNECTED
        self.last_error = None
        self.last_successful_request = None
        
        # Statistics
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0
        }
        
        # Initialize connection
        self._initialize_connection()
    
    def _initialize_connection(self):
        """Initialize connection to ComnetsEMU."""
        try:
            self.logger.info(f"Initializing connection to ComnetsEMU at {self.config.host}:{self.config.port}")
            
            if self._test_connectivity():
                self.status = ConnectionStatus.CONNECTED
                self.last_successful_request = datetime.now()
                self.logger.info("Successfully connected to ComnetsEMU")
            else:
                self.status = ConnectionStatus.ERROR
                self.logger.error("Failed to connect to ComnetsEMU")
                
        except Exception as e:
            self.status = ConnectionStatus.ERROR
            self.last_error = str(e)
            self.logger.error(f"Failed to initialize ComnetsEMU connection: {e}")
    
    def _test_connectivity(self) -> bool:
        """Test basic connectivity to ComnetsEMU."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.config.timeout_seconds)
            result = sock.connect_ex((self.config.host, self.config.port))
            sock.close()
            
            if result == 0:
                self.logger.debug(f"OpenFlow port {self.config.port} is accessible")
                return True
            else:
                self.logger.warning(f"OpenFlow port {self.config.port} is not accessible")
                return False
                
        except Exception as e:
            self.logger.error(f"Connectivity test failed: {e}")
            return False
    
    def execute_topology_change(self, action: NetworkAction) -> Dict[str, Any]:
        """Execute topology change with retry system."""
        try:
            def _execute_change():
                """Internal function to execute topology change."""
                operation = action.parameters.get("operation", "add")
                element_type = action.parameters.get("element_type", "unknown")
                element_id = action.parameters.get("element_id", action.target)
                
                self.logger.info(f"Executing topology change: {operation} {element_type} {element_id}")
                
                # Validate operation
                valid_operations = ["add", "remove", "modify"]
                if operation not in valid_operations:
                    raise ValueError(f"Invalid operation '{operation}'")
                
                # Simulate topology change execution
                # In real implementation, this would interact with ComnetsEMU APIs
                success = True
                
                if success:
                    self.stats["successful_requests"] += 1
                    self.stats["total_requests"] += 1
                    self.last_successful_request = datetime.now()
                    return {
                        "operation": operation,
                        "element_type": element_type,
                        "element_id": element_id
                    }
                else:
                    self.stats["failed_requests"] += 1
                    self.stats["total_requests"] += 1
                    raise Exception("Topology change failed")
            
            # Use retry system
            result = self.retry_system.execute_with_retry(_execute_change)
            
            if result.success:
                return {
                    "success": True,
                    "message": "Topology change completed successfully",
                    **result.result,
                    "retry_stats": {
                        "attempts": len(result.attempts),
                        "total_time": result.total_time
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "Topology change failed after retries",
                    "error": result.error,
                    "retry_stats": {
                        "attempts": len(result.attempts),
                        "total_time": result.total_time
                    }
                }
                
        except Exception as e:
            self.logger.error(f"Failed to execute topology change {action.id}: {e}")
            raise
    
    def execute_qos_policy(self, action: NetworkAction) -> Dict[str, Any]:
        """Execute QoS policy with retry system."""
        try:
            def _execute_qos():
                """Internal function to execute QoS policy."""
                self.logger.info(f"Executing QoS policy on {action.target}")
                
                # Simulate QoS policy execution
                success = True
                
                if success:
                    self.stats["successful_requests"] += 1
                    self.stats["total_requests"] += 1
                    self.last_successful_request = datetime.now()
                    return True
                else:
                    self.stats["failed_requests"] += 1
                    self.stats["total_requests"] += 1
                    raise Exception("QoS policy execution failed")
            
            result = self.retry_system.execute_with_retry(_execute_qos)
            
            if result.success:
                return {
                    "success": True,
                    "message": "QoS policy applied successfully",
                    "retry_stats": {
                        "attempts": len(result.attempts),
                        "total_time": result.total_time
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "QoS policy failed after retries",
                    "error": result.error,
                    "retry_stats": {
                        "attempts": len(result.attempts),
                        "total_time": result.total_time
                    }
                }
                
        except Exception as e:
            self.logger.error(f"Failed to execute QoS policy {action.id}: {e}")
            raise
    
    def get_network_state(self, target: str) -> Dict[str, Any]:
        """Get network state with retry system."""
        def _get_state():
            """Internal function to get network state."""
            self.logger.info(f"Getting network state for {target}")
            
            # Simulate network state retrieval
            state = {
                "target": target,
                "status": "active",
                "timestamp": datetime.now().isoformat()
            }
            
            self.stats["successful_requests"] += 1
            self.stats["total_requests"] += 1
            self.last_successful_request = datetime.now()
            return state
        
        try:
            result = self.retry_system.execute_with_retry(_get_state)
            
            if result.success:
                return result.result
            else:
                return {
                    "target": target,
                    "status": "error",
                    "error": result.error,
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get network state for {target}: {e}")
            return {
                "target": target,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get current connection status and statistics."""
        return {
            "status": self.status.value,
            "last_error": self.last_error,
            "last_successful_request": self.last_successful_request.isoformat() if self.last_successful_request else None,
            "config": {
                "host": self.config.host,
                "port": self.config.port,
                "timeout": self.config.timeout_seconds,
                "max_retries": self.config.max_retries
            },
            "stats": {
                "total_requests": self.stats["total_requests"],
                "successful_requests": self.stats["successful_requests"],
                "failed_requests": self.stats["failed_requests"],
                "success_rate": (self.stats["successful_requests"] / max(self.stats["total_requests"], 1)) * 100
            }
        }
    
    def close(self):
        """Close the ComnetsEMU connector."""
        self.logger.info("Closing ComnetsEMU connector")
        self.status = ConnectionStatus.DISCONNECTED
