"""
Real RYU Controller Connector
Replaces the simulated interface with actual HTTP calls to RYU REST API
"""

import json
import logging
import time
import requests
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urljoin
import threading
from queue import Queue, Empty
from contextlib import contextmanager

from ..models.action_models import NetworkAction, ActionType


class ConnectionStatus(str, Enum):
    """Status of RYU controller connection."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class RYUConfig:
    """Configuration for RYU Controller connection."""
    host: str = "localhost"
    port: int = 8080
    api_version: str = "v1.0"
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay: float = 2.0
    ssl_enabled: bool = False
    ssl_verify: bool = True
    connection_pool_size: int = 10
    max_connections_per_host: int = 5
    
    @property
    def base_url(self) -> str:
        """Get base URL for RYU REST API."""
        protocol = "https" if self.ssl_enabled else "http"
        return f"{protocol}://{self.host}:{self.port}"


@dataclass
class ConnectionPoolStats:
    """Statistics for connection pool."""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    failed_connections: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)


class RYUConnectionPool:
    """Connection pool for RYU Controller HTTP connections."""
    
    def __init__(self, config: RYUConfig):
        self.config = config
        self.logger = logging.getLogger("RYUConnectionPool")
        
        # Create session with connection pooling
        self.session = requests.Session()
        
        # Configure session
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=config.connection_pool_size,
            pool_maxsize=config.max_connections_per_host,
            max_retries=0  # We handle retries manually
        )
        
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default timeout and SSL settings
        self.session.timeout = config.timeout_seconds
        self.session.verify = config.ssl_verify if config.ssl_enabled else True
        
        # Statistics tracking
        self.stats = ConnectionPoolStats()
        self.stats_lock = threading.Lock()
        
        # Health check
        self.last_health_check = None
        self.health_check_interval = timedelta(minutes=5)
        
    def _update_stats(self, success: bool, response_time: float):
        """Update connection pool statistics."""
        with self.stats_lock:
            self.stats.total_requests += 1
            if success:
                self.stats.successful_requests += 1
            else:
                self.stats.failed_requests += 1
            
            # Update average response time (exponential moving average)
            alpha = 0.1
            self.stats.average_response_time = (
                alpha * response_time + 
                (1 - alpha) * self.stats.average_response_time
            )
            self.stats.last_updated = datetime.now()
    
    def get_stats(self) -> ConnectionPoolStats:
        """Get current connection pool statistics."""
        with self.stats_lock:
            return ConnectionPoolStats(
                total_connections=self.stats.total_connections,
                active_connections=self.stats.active_connections,
                idle_connections=self.stats.idle_connections,
                failed_connections=self.stats.failed_connections,
                total_requests=self.stats.total_requests,
                successful_requests=self.stats.successful_requests,
                failed_requests=self.stats.failed_requests,
                average_response_time=self.stats.average_response_time,
                last_updated=self.stats.last_updated
            )
    
    def health_check(self) -> bool:
        """Perform health check on RYU controller."""
        try:
            start_time = time.time()
            response = self.session.get(
                urljoin(self.config.base_url, f"/{self.config.api_version}/stats/switches"),
                timeout=5  # Short timeout for health check
            )
            response_time = time.time() - start_time
            
            success = response.status_code == 200
            self._update_stats(success, response_time)
            
            if success:
                self.last_health_check = datetime.now()
                self.logger.debug(f"Health check passed in {response_time:.2f}s")
            else:
                self.logger.warning(f"Health check failed: HTTP {response.status_code}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            self._update_stats(False, 0.0)
            return False
    
    def should_perform_health_check(self) -> bool:
        """Check if health check should be performed."""
        if self.last_health_check is None:
            return True
        return datetime.now() - self.last_health_check > self.health_check_interval
    
    @contextmanager
    def request(self, method: str, url: str, **kwargs):
        """Context manager for making HTTP requests with error handling."""
        start_time = time.time()
        response = None
        
        try:
            # Perform health check if needed
            if self.should_perform_health_check():
                self.health_check()
            
            # Make the request
            response = self.session.request(method, url, **kwargs)
            response_time = time.time() - start_time
            
            # Update statistics
            success = 200 <= response.status_code < 300
            self._update_stats(success, response_time)
            
            if not success:
                self.logger.warning(
                    f"HTTP {response.status_code} for {method} {url}: {response.text[:200]}"
                )
            
            yield response
            
        except requests.exceptions.Timeout as e:
            response_time = time.time() - start_time
            self._update_stats(False, response_time)
            self.logger.error(f"Request timeout for {method} {url}: {e}")
            raise
            
        except requests.exceptions.ConnectionError as e:
            response_time = time.time() - start_time
            self._update_stats(False, response_time)
            self.logger.error(f"Connection error for {method} {url}: {e}")
            raise
            
        except Exception as e:
            response_time = time.time() - start_time
            self._update_stats(False, response_time)
            self.logger.error(f"Unexpected error for {method} {url}: {e}")
            raise
    
    def close(self):
        """Close the connection pool."""
        self.session.close()


class RYUConnector:
    """Real RYU Controller connector with connection pooling and error handling."""
    
    def __init__(self, config: RYUConfig = None):
        self.config = config or RYUConfig()
        self.logger = logging.getLogger("RYUConnector")
        
        # Initialize connection pool
        self.connection_pool = RYUConnectionPool(self.config)
        
        # Track connection status
        self.status = ConnectionStatus.DISCONNECTED
        self.last_error = None
        self.last_successful_request = None
        
        # Initialize connection
        self._initialize_connection()
    
    def _initialize_connection(self):
        """Initialize connection to RYU controller."""
        try:
            self.logger.info(f"Initializing connection to RYU at {self.config.base_url}")
            
            if self.connection_pool.health_check():
                self.status = ConnectionStatus.CONNECTED
                self.last_successful_request = datetime.now()
                self.logger.info("Successfully connected to RYU controller")
            else:
                self.status = ConnectionStatus.ERROR
                self.logger.error("Failed to connect to RYU controller")
                
        except Exception as e:
            self.status = ConnectionStatus.ERROR
            self.last_error = str(e)
            self.logger.error(f"Failed to initialize RYU connection: {e}")
    
    def _make_request_with_retry(self, method: str, endpoint: str, 
                                data: Optional[Dict] = None, 
                                params: Optional[Dict] = None) -> requests.Response:
        """Make HTTP request with retry logic and exponential backoff."""
        url = urljoin(self.config.base_url, f"/{self.config.api_version}{endpoint}")
        
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                self.logger.debug(f"Attempt {attempt + 1}/{self.config.max_retries + 1}: {method} {url}")
                
                with self.connection_pool.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    timeout=self.config.timeout_seconds
                ) as response:
                    
                    if response.status_code == 200:
                        self.status = ConnectionStatus.CONNECTED
                        self.last_successful_request = datetime.now()
                        self.last_error = None
                        return response
                    
                    elif response.status_code in [400, 404, 422]:
                        # Client errors - don't retry
                        self.logger.error(f"Client error {response.status_code}: {response.text}")
                        response.raise_for_status()
                    
                    elif response.status_code >= 500:
                        # Server errors - retry
                        self.logger.warning(f"Server error {response.status_code}, will retry")
                        if attempt < self.config.max_retries:
                            time.sleep(self.config.retry_delay * (2 ** attempt))
                            continue
                        else:
                            response.raise_for_status()
                    
                    else:
                        # Other status codes
                        response.raise_for_status()
            
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_exception = e
                self.status = ConnectionStatus.TIMEOUT if isinstance(e, requests.exceptions.Timeout) else ConnectionStatus.ERROR
                self.last_error = str(e)
                
                if attempt < self.config.max_retries:
                    delay = self.config.retry_delay * (2 ** attempt)
                    self.logger.warning(f"Request failed ({e}), retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    self.logger.error(f"Request failed after {self.config.max_retries + 1} attempts: {e}")
                    raise
            
            except Exception as e:
                self.status = ConnectionStatus.ERROR
                self.last_error = str(e)
                self.logger.error(f"Unexpected error in request: {e}")
                raise
        
        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("Request failed for unknown reason")
    
    def get_switches(self) -> List[Dict[str, Any]]:
        """Get list of connected switches."""
        try:
            response = self._make_request_with_retry("GET", "/stats/switches")
            switches = response.json()
            self.logger.debug(f"Retrieved {len(switches)} switches")
            return switches
            
        except Exception as e:
            self.logger.error(f"Failed to get switches: {e}")
            raise
    
    def get_flows(self, switch_id: str) -> List[Dict[str, Any]]:
        """Get flow entries for a specific switch."""
        try:
            response = self._make_request_with_retry("GET", f"/stats/flow/{switch_id}")
            flows_data = response.json()
            
            # RYU returns flows in format: {switch_id: [flows]}
            flows = flows_data.get(switch_id, [])
            self.logger.debug(f"Retrieved {len(flows)} flows for switch {switch_id}")
            return flows
            
        except Exception as e:
            self.logger.error(f"Failed to get flows for switch {switch_id}: {e}")
            raise
    
    def add_flow(self, switch_id: str, flow_rule: Dict[str, Any]) -> bool:
        """Add a flow rule to a switch."""
        try:
            # Prepare flow mod data for RYU
            flow_mod_data = {
                "dpid": int(switch_id) if switch_id.isdigit() else switch_id,
                "table_id": flow_rule.get("table_id", 0),
                "priority": flow_rule.get("priority", 1000),
                "match": flow_rule.get("match", {}),
                "actions": flow_rule.get("actions", []),
                "idle_timeout": flow_rule.get("idle_timeout", 0),
                "hard_timeout": flow_rule.get("hard_timeout", 0)
            }
            
            self.logger.info(f"Adding flow rule to switch {switch_id}: {flow_mod_data}")
            
            response = self._make_request_with_retry("POST", "/stats/flowentry/add", data=flow_mod_data)
            
            if response.status_code == 200:
                self.logger.info(f"Successfully added flow rule to switch {switch_id}")
                return True
            else:
                self.logger.error(f"Failed to add flow rule: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to add flow rule to switch {switch_id}: {e}")
            raise
    
    def delete_flow(self, switch_id: str, flow_rule: Dict[str, Any]) -> bool:
        """Delete a flow rule from a switch."""
        try:
            # Prepare flow mod data for deletion
            flow_mod_data = {
                "dpid": int(switch_id) if switch_id.isdigit() else switch_id,
                "table_id": flow_rule.get("table_id", 0),
                "priority": flow_rule.get("priority", 1000),
                "match": flow_rule.get("match", {})
            }
            
            self.logger.info(f"Deleting flow rule from switch {switch_id}: {flow_mod_data}")
            
            response = self._make_request_with_retry("POST", "/stats/flowentry/delete", data=flow_mod_data)
            
            if response.status_code == 200:
                self.logger.info(f"Successfully deleted flow rule from switch {switch_id}")
                return True
            else:
                self.logger.error(f"Failed to delete flow rule: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to delete flow rule from switch {switch_id}: {e}")
            raise
    
    def modify_flow(self, switch_id: str, flow_rule: Dict[str, Any]) -> bool:
        """Modify an existing flow rule."""
        try:
            # Prepare flow mod data for modification
            flow_mod_data = {
                "dpid": int(switch_id) if switch_id.isdigit() else switch_id,
                "table_id": flow_rule.get("table_id", 0),
                "priority": flow_rule.get("priority", 1000),
                "match": flow_rule.get("match", {}),
                "actions": flow_rule.get("actions", []),
                "idle_timeout": flow_rule.get("idle_timeout", 0),
                "hard_timeout": flow_rule.get("hard_timeout", 0)
            }
            
            self.logger.info(f"Modifying flow rule on switch {switch_id}: {flow_mod_data}")
            
            response = self._make_request_with_retry("POST", "/stats/flowentry/modify", data=flow_mod_data)
            
            if response.status_code == 200:
                self.logger.info(f"Successfully modified flow rule on switch {switch_id}")
                return True
            else:
                self.logger.error(f"Failed to modify flow rule: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to modify flow rule on switch {switch_id}: {e}")
            raise
    
    def get_port_stats(self, switch_id: str) -> List[Dict[str, Any]]:
        """Get port statistics for a switch."""
        try:
            response = self._make_request_with_retry("GET", f"/stats/port/{switch_id}")
            port_stats_data = response.json()
            
            # RYU returns port stats in format: {switch_id: [port_stats]}
            port_stats = port_stats_data.get(switch_id, [])
            self.logger.debug(f"Retrieved port stats for {len(port_stats)} ports on switch {switch_id}")
            return port_stats
            
        except Exception as e:
            self.logger.error(f"Failed to get port stats for switch {switch_id}: {e}")
            raise
    
    def get_network_topology(self) -> Dict[str, Any]:
        """Get current network topology."""
        try:
            # Get switches
            switches = self.get_switches()
            
            # Get links between switches
            response = self._make_request_with_retry("GET", "/v1.0/topology/links")
            links = response.json()
            
            topology = {
                "switches": switches,
                "links": links,
                "timestamp": datetime.now().isoformat()
            }
            
            self.logger.debug(f"Retrieved topology: {len(switches)} switches, {len(links)} links")
            return topology
            
        except Exception as e:
            self.logger.error(f"Failed to get network topology: {e}")
            raise
    
    def execute_flow_mod(self, action: NetworkAction) -> Dict[str, Any]:
        """Execute flow modification action."""
        try:
            switch_id = action.target
            parameters = action.parameters
            
            # Extract flow rule parameters
            flow_rule = {
                "priority": action.priority,
                "match": parameters.get("match", {}),
                "actions": parameters.get("actions", []),
                "idle_timeout": parameters.get("idle_timeout", 0),
                "hard_timeout": parameters.get("hard_timeout", 0),
                "table_id": parameters.get("table_id", 0)
            }
            
            # Determine operation type
            operation = parameters.get("operation", "add")
            
            if operation == "add":
                success = self.add_flow(switch_id, flow_rule)
            elif operation == "delete":
                success = self.delete_flow(switch_id, flow_rule)
            elif operation == "modify":
                success = self.modify_flow(switch_id, flow_rule)
            else:
                raise ValueError(f"Unknown flow operation: {operation}")
            
            return {
                "success": success,
                "operation": operation,
                "switch_id": switch_id,
                "flow_rule": flow_rule,
                "message": f"Flow {operation} {'successful' if success else 'failed'}"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to execute flow_mod action {action.id}: {e}")
            raise
    
    def verify_action_applied(self, action: NetworkAction) -> bool:
        """Verify that a network action was successfully applied."""
        try:
            if action.type == ActionType.FLOW_MOD:
                return self._verify_flow_mod(action)
            else:
                self.logger.warning(f"Verification not implemented for action type: {action.type}")
                return True  # Assume success for unsupported types
                
        except Exception as e:
            self.logger.error(f"Failed to verify action {action.id}: {e}")
            return False
    
    def _verify_flow_mod(self, action: NetworkAction) -> bool:
        """Verify that a flow modification was applied."""
        try:
            switch_id = action.target
            expected_match = action.parameters.get("match", {})
            expected_priority = action.priority
            
            # Get current flows
            flows = self.get_flows(switch_id)
            
            # Look for matching flow
            for flow in flows:
                flow_match = flow.get("match", {})
                flow_priority = flow.get("priority", 0)
                
                # Check if this flow matches our expectations
                if (flow_priority == expected_priority and 
                    self._matches_flow_criteria(flow_match, expected_match)):
                    self.logger.debug(f"Verified flow rule exists on switch {switch_id}")
                    return True
            
            self.logger.warning(f"Flow rule not found on switch {switch_id}")
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to verify flow_mod for action {action.id}: {e}")
            return False
    
    def _matches_flow_criteria(self, actual_match: Dict, expected_match: Dict) -> bool:
        """Check if actual flow match criteria matches expected criteria."""
        for key, expected_value in expected_match.items():
            if key not in actual_match or actual_match[key] != expected_value:
                return False
        return True
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get current connection status and statistics."""
        stats = self.connection_pool.get_stats()
        
        return {
            "status": self.status.value,
            "last_error": self.last_error,
            "last_successful_request": self.last_successful_request.isoformat() if self.last_successful_request else None,
            "config": {
                "host": self.config.host,
                "port": self.config.port,
                "base_url": self.config.base_url,
                "timeout": self.config.timeout_seconds,
                "max_retries": self.config.max_retries
            },
            "pool_stats": {
                "total_requests": stats.total_requests,
                "successful_requests": stats.successful_requests,
                "failed_requests": stats.failed_requests,
                "success_rate": (stats.successful_requests / max(stats.total_requests, 1)) * 100,
                "average_response_time": stats.average_response_time,
                "last_updated": stats.last_updated.isoformat()
            }
        }
    
    def close(self):
        """Close the RYU connector and clean up resources."""
        self.logger.info("Closing RYU connector")
        self.connection_pool.close()
        self.status = ConnectionStatus.DISCONNECTED


# Factory function for easy instantiation
def create_ryu_connector(host: str = "localhost", port: int = 8080, **kwargs) -> RYUConnector:
    """Create a RYU connector with specified configuration."""
    config = RYUConfig(host=host, port=port, **kwargs)
    return RYUConnector(config)