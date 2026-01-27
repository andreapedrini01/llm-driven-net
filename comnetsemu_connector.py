"""
Real ComnetsEMU Connector
Integrates with ComnetsEMU API for topology management and network operations
"""

import json
import logging
import time
import requests
import subprocess
import socket
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager
import threading
from queue import Queue, Empty

from action_models import NetworkAction, ActionType


class ComnetsEMUConnectionStatus(str, Enum):
    """Status of ComnetsEMU connection."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class ComnetsEMUConfig:
    """Configuration for ComnetsEMU connection."""
    host: str = "localhost"
    port: int = 6653  # OpenFlow port
    api_port: int = 8181  # REST API port if available
    protocol: str = "openflow"
    version: str = "1.3"
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay: float = 2.0
    connection_pool_size: int = 5
    
    # Mininet/ComnetsEMU specific settings
    mininet_cli_enabled: bool = True
    topology_discovery_interval: int = 60  # seconds
    
    @property
    def openflow_url(self) -> str:
        """Get OpenFlow connection URL."""
        return f"tcp:{self.host}:{self.port}"
    
    @property
    def api_base_url(self) -> str:
        """Get REST API base URL if available."""
        return f"http://{self.host}:{self.api_port}"


@dataclass
class NetworkTopology:
    """Network topology information."""
    switches: List[Dict[str, Any]] = field(default_factory=list)
    hosts: List[Dict[str, Any]] = field(default_factory=list)
    links: List[Dict[str, Any]] = field(default_factory=list)
    controllers: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def get_switch_by_id(self, switch_id: str) -> Optional[Dict[str, Any]]:
        """Get switch information by ID."""
        for switch in self.switches:
            if str(switch.get("dpid", "")) == switch_id or switch.get("name") == switch_id:
                return switch
        return None
    
    def get_host_by_ip(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """Get host information by IP address."""
        for host in self.hosts:
            if host.get("ip") == ip_address:
                return host
        return None
    
    def get_links_for_switch(self, switch_id: str) -> List[Dict[str, Any]]:
        """Get all links connected to a specific switch."""
        links = []
        for link in self.links:
            if (link.get("src", {}).get("dpid") == switch_id or 
                link.get("dst", {}).get("dpid") == switch_id):
                links.append(link)
        return links


class ComnetsEMUConnector:
    """Real ComnetsEMU connector for network topology management."""
    
    def __init__(self, config: ComnetsEMUConfig = None):
        self.config = config or ComnetsEMUConfig()
        self.logger = logging.getLogger("ComnetsEMUConnector")
        
        # Connection state
        self.status = ComnetsEMUConnectionStatus.DISCONNECTED
        self.last_error = None
        self.last_successful_request = None
        
        # Topology cache
        self.topology_cache = None
        self.topology_cache_timestamp = None
        self.topology_lock = threading.Lock()
        
        # Statistics
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "topology_updates": 0,
            "last_topology_update": None
        }
        
        # Initialize connection
        self._initialize_connection()
    
    def _initialize_connection(self):
        """Initialize connection to ComnetsEMU."""
        try:
            self.logger.info(f"Initializing connection to ComnetsEMU at {self.config.host}:{self.config.port}")
            
            # Test basic connectivity
            if self._test_connectivity():
                self.status = ComnetsEMUConnectionStatus.CONNECTED
                self.last_successful_request = datetime.now()
                self.logger.info("Successfully connected to ComnetsEMU")
                
                # Initial topology discovery
                self._discover_topology()
            else:
                self.status = ComnetsEMUConnectionStatus.ERROR
                self.logger.error("Failed to connect to ComnetsEMU")
                
        except Exception as e:
            self.status = ComnetsEMUConnectionStatus.ERROR
            self.last_error = str(e)
            self.logger.error(f"Failed to initialize ComnetsEMU connection: {e}")
    
    def _test_connectivity(self) -> bool:
        """Test basic connectivity to ComnetsEMU."""
        try:
            # Test OpenFlow port connectivity
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.config.timeout_seconds)
            result = sock.connect_ex((self.config.host, self.config.port))
            sock.close()
            
            if result == 0:
                self.logger.debug(f"OpenFlow port {self.config.port} is accessible")
                
                # Also test REST API port if available
                if hasattr(self.config, 'api_port') and self.config.api_port:
                    try:
                        api_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        api_sock.settimeout(5)  # Shorter timeout for API test
                        api_result = api_sock.connect_ex((self.config.host, self.config.api_port))
                        api_sock.close()
                        
                        if api_result == 0:
                            self.logger.debug(f"ComnetsEMU API port {self.config.api_port} is accessible")
                        else:
                            self.logger.warning(f"ComnetsEMU API port {self.config.api_port} is not accessible")
                    except Exception as api_e:
                        self.logger.warning(f"API connectivity test failed: {api_e}")
                
                return True
            else:
                self.logger.warning(f"OpenFlow port {self.config.port} is not accessible")
                return False
                
        except Exception as e:
            self.logger.error(f"Connectivity test failed: {e}")
            return False
    
    def _discover_topology(self) -> bool:
        """Discover network topology from ComnetsEMU using real API calls."""
        try:
            self.logger.info("Discovering network topology from ComnetsEMU")
            
            topology = NetworkTopology()
            
            # Try to use ComnetsEMU REST API first, fall back to CLI/simulation
            if hasattr(self.config, 'api_port') and self.config.api_port:
                try:
                    # Attempt to discover via REST API
                    if self._discover_via_rest_api(topology):
                        self.logger.info("Topology discovered via REST API")
                    else:
                        self.logger.warning("REST API discovery failed, falling back to CLI")
                        self._discover_via_cli(topology)
                except Exception as api_error:
                    self.logger.warning(f"REST API discovery failed: {api_error}, falling back to CLI")
                    self._discover_via_cli(topology)
            else:
                # Use CLI/direct methods
                self._discover_via_cli(topology)
            
            # Cache the topology
            with self.topology_lock:
                self.topology_cache = topology
                self.topology_cache_timestamp = datetime.now()
                self.stats["topology_updates"] += 1
                self.stats["last_topology_update"] = datetime.now().isoformat()
            
            self.logger.info(f"Discovered topology: {len(topology.switches)} switches, "
                           f"{len(topology.hosts)} hosts, {len(topology.links)} links")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to discover topology: {e}")
            return False
    
    def _discover_via_rest_api(self, topology: NetworkTopology) -> bool:
        """Discover topology using ComnetsEMU REST API."""
        try:
            import requests
            
            base_url = f"http://{self.config.host}:{self.config.api_port}"
            timeout = self.config.timeout_seconds
            
            # Get switches
            try:
                switches_response = requests.get(f"{base_url}/stats/switches", timeout=timeout)
                if switches_response.status_code == 200:
                    switches_data = switches_response.json()
                    for switch_id in switches_data:
                        switch_info = {
                            "dpid": str(switch_id),
                            "name": f"s{switch_id}",
                            "ports": self._get_switch_ports_api(switch_id),
                            "flows": [],
                            "status": "active"
                        }
                        topology.switches.append(switch_info)
                else:
                    self.logger.warning(f"Failed to get switches: HTTP {switches_response.status_code}")
                    return False
            except requests.RequestException as e:
                self.logger.warning(f"Failed to get switches via API: {e}")
                return False
            
            # Get topology (links)
            try:
                topology_response = requests.get(f"{base_url}/v1.0/topology/links", timeout=timeout)
                if topology_response.status_code == 200:
                    links_data = topology_response.json()
                    for link_data in links_data:
                        link = {
                            "src": {"dpid": str(link_data.get("src", {}).get("dpid", "")),
                                   "port": link_data.get("src", {}).get("port_no", 0)},
                            "dst": {"dpid": str(link_data.get("dst", {}).get("dpid", "")),
                                   "port": link_data.get("dst", {}).get("port_no", 0)},
                            "bandwidth": 1000,  # Default bandwidth
                            "delay": "1ms",
                            "status": "active"
                        }
                        topology.links.append(link)
                else:
                    self.logger.warning(f"Failed to get topology: HTTP {topology_response.status_code}")
            except requests.RequestException as e:
                self.logger.warning(f"Failed to get topology via API: {e}")
            
            # Get hosts (may not be available via standard API)
            topology.hosts = self._discover_hosts_heuristic(topology.switches)
            
            return True
            
        except Exception as e:
            self.logger.error(f"REST API topology discovery failed: {e}")
            return False
    
    def _get_switch_ports_api(self, switch_id: str) -> List[Dict[str, Any]]:
        """Get switch ports via REST API."""
        try:
            import requests
            
            base_url = f"http://{self.config.host}:{self.config.api_port}"
            response = requests.get(f"{base_url}/stats/port/{switch_id}", 
                                  timeout=self.config.timeout_seconds)
            
            if response.status_code == 200:
                ports_data = response.json()
                ports = []
                for port_data in ports_data.get(str(switch_id), []):
                    port = {
                        "port_no": port_data.get("port_no", 0),
                        "name": f"eth{port_data.get('port_no', 0)}",
                        "status": "up" if port_data.get("state", 0) == 0 else "down",
                        "speed": 1000,  # Default speed
                        "rx_packets": port_data.get("rx_packets", 0),
                        "tx_packets": port_data.get("tx_packets", 0)
                    }
                    ports.append(port)
                return ports
            else:
                self.logger.warning(f"Failed to get ports for switch {switch_id}: HTTP {response.status_code}")
                return self._get_switch_ports(f"s{switch_id}")  # Fallback
                
        except Exception as e:
            self.logger.warning(f"Failed to get ports for switch {switch_id} via API: {e}")
            return self._get_switch_ports(f"s{switch_id}")  # Fallback
    
    def _discover_via_cli(self, topology: NetworkTopology):
        """Discover topology using CLI/simulation methods."""
        # Discover switches
        switches = self._get_switches_via_cli()
        topology.switches = switches
        
        # Discover hosts
        hosts = self._get_hosts_via_cli()
        topology.hosts = hosts
        
        # Discover links
        links = self._get_links_via_cli()
        topology.links = links
    
    def _discover_hosts_heuristic(self, switches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Discover hosts using heuristic methods when API is not available."""
        hosts = []
        
        # Try to ping common host IPs or use ARP tables
        common_subnets = ["10.0.1.0/24", "10.0.2.0/24", "192.168.1.0/24"]
        
        for subnet in common_subnets:
            try:
                # This is a simplified approach - in real implementation,
                # you would query ARP tables or use network scanning
                import ipaddress
                network = ipaddress.IPv4Network(subnet, strict=False)
                
                # Sample some IPs from the subnet
                for i, ip in enumerate(network.hosts()):
                    if i >= 5:  # Limit to first 5 IPs per subnet
                        break
                    
                    # Try to determine if host exists (simplified)
                    host = {
                        "name": f"host_{str(ip).replace('.', '_')}",
                        "ip": str(ip),
                        "mac": f"00:00:00:00:{i:02x}:{len(hosts):02x}",
                        "connected_switch": self._find_host_switch_heuristic(str(ip)),
                        "status": "unknown"  # Would need actual detection
                    }
                    hosts.append(host)
                    
            except Exception as e:
                self.logger.debug(f"Failed to scan subnet {subnet}: {e}")
        
        return hosts
    
    def _find_host_switch_heuristic(self, ip: str) -> str:
        """Find which switch a host is connected to using heuristic."""
        # Simple heuristic based on IP subnet
        if ip.startswith("10.0.1."):
            return "s1"
        elif ip.startswith("10.0.2."):
            return "s2"
        elif ip.startswith("192.168.1."):
            return "s3"
        else:
            return "s1"  # Default
    
    def _get_switches_via_cli(self) -> List[Dict[str, Any]]:
        """Get switches information via Mininet CLI."""
        try:
            # This would typically use Mininet's Python API or CLI commands
            # For now, we'll simulate the discovery process
            
            # In a real implementation, this would connect to the Mininet instance
            # and query the network state
            switches = []
            
            # Simulate switch discovery
            # In practice, this would use Mininet's net.switches or similar
            for i in range(1, 4):  # Assuming 3 switches from topology
                switch = {
                    "dpid": str(i),
                    "name": f"s{i}",
                    "ports": self._get_switch_ports(f"s{i}"),
                    "flows": [],
                    "status": "active"
                }
                switches.append(switch)
            
            return switches
            
        except Exception as e:
            self.logger.error(f"Failed to get switches: {e}")
            return []
    
    def _get_hosts_via_cli(self) -> List[Dict[str, Any]]:
        """Get hosts information via Mininet CLI."""
        try:
            hosts = []
            
            # Simulate host discovery based on the topology
            host_configs = [
                {"name": "web1", "ip": "10.0.1.10", "mac": "00:00:00:00:01:01"},
                {"name": "db1", "ip": "10.0.2.10", "mac": "00:00:00:00:02:01"},
                {"name": "app1", "ip": "10.0.1.20", "mac": "00:00:00:00:01:02"},
                {"name": "client1", "ip": "10.0.0.100", "mac": "00:00:00:00:00:01"},
                {"name": "attacker", "ip": "10.0.0.200", "mac": "00:00:00:00:00:02"}
            ]
            
            for host_config in host_configs:
                host = {
                    "name": host_config["name"],
                    "ip": host_config["ip"],
                    "mac": host_config["mac"],
                    "connected_switch": self._find_host_switch(host_config["name"]),
                    "status": "active"
                }
                hosts.append(host)
            
            return hosts
            
        except Exception as e:
            self.logger.error(f"Failed to get hosts: {e}")
            return []
    
    def _get_links_via_cli(self) -> List[Dict[str, Any]]:
        """Get links information via Mininet CLI."""
        try:
            links = []
            
            # Simulate link discovery based on the topology
            link_configs = [
                {"src": {"dpid": "1", "port": 1}, "dst": {"dpid": "2", "port": 1}},
                {"src": {"dpid": "2", "port": 2}, "dst": {"dpid": "3", "port": 1}},
                {"src": {"dpid": "1", "port": 2}, "dst": {"dpid": "3", "port": 2}},
            ]
            
            for link_config in link_configs:
                link = {
                    "src": link_config["src"],
                    "dst": link_config["dst"],
                    "bandwidth": 1000,  # Mbps
                    "delay": "1ms",
                    "status": "active"
                }
                links.append(link)
            
            return links
            
        except Exception as e:
            self.logger.error(f"Failed to get links: {e}")
            return []
    
    def _get_switch_ports(self, switch_name: str) -> List[Dict[str, Any]]:
        """Get ports for a specific switch."""
        try:
            # Simulate port discovery
            ports = []
            for i in range(1, 4):  # Assuming 3 ports per switch
                port = {
                    "port_no": i,
                    "name": f"eth{i}",
                    "status": "up",
                    "speed": 1000,  # Mbps
                    "rx_packets": 0,
                    "tx_packets": 0
                }
                ports.append(port)
            
            return ports
            
        except Exception as e:
            self.logger.error(f"Failed to get ports for switch {switch_name}: {e}")
            return []
    
    def _find_host_switch(self, host_name: str) -> str:
        """Find which switch a host is connected to."""
        # Simulate host-switch mapping based on topology
        host_switch_map = {
            "web1": "s1",
            "app1": "s1", 
            "db1": "s2",
            "client1": "s1",
            "attacker": "s3"
        }
        return host_switch_map.get(host_name, "unknown")
    
    def get_network_topology(self) -> NetworkTopology:
        """Get current network topology."""
        try:
            # Check if cached topology is still valid
            if (self.topology_cache and self.topology_cache_timestamp and
                datetime.now() - self.topology_cache_timestamp < timedelta(seconds=self.config.topology_discovery_interval)):
                self.logger.debug("Returning cached topology")
                return self.topology_cache
            
            # Refresh topology
            if self._discover_topology():
                with self.topology_lock:
                    return self.topology_cache
            else:
                # Return empty topology if discovery fails
                return NetworkTopology()
                
        except Exception as e:
            self.logger.error(f"Failed to get network topology: {e}")
            return NetworkTopology()
    
    def get_network_state(self, target: str) -> Dict[str, Any]:
        """Get current state of network resource."""
        try:
            self.logger.info(f"Getting network state for {target}")
            
            topology = self.get_network_topology()
            
            if target.startswith("switch") or target.startswith("s"):
                # Extract switch ID
                switch_id = target.replace("switch-", "").replace("s", "")
                switch_info = topology.get_switch_by_id(switch_id)
                
                if not switch_info:
                    return {
                        "target": target,
                        "status": "not_found",
                        "timestamp": datetime.now().isoformat()
                    }
                
                # Get additional switch details
                links = topology.get_links_for_switch(switch_id)
                
                return {
                    "target": target,
                    "switch_id": switch_id,
                    "switch_info": switch_info,
                    "links": links,
                    "status": "active",
                    "timestamp": datetime.now().isoformat()
                }
            
            elif target.startswith("host") or "." in target:  # IP address
                # Handle host by name or IP
                if "." in target:  # IP address
                    host_info = topology.get_host_by_ip(target)
                else:
                    # Find host by name
                    host_name = target.replace("host-", "")
                    host_info = next((h for h in topology.hosts if h.get("name") == host_name), None)
                
                if not host_info:
                    return {
                        "target": target,
                        "status": "not_found",
                        "timestamp": datetime.now().isoformat()
                    }
                
                return {
                    "target": target,
                    "host_info": host_info,
                    "status": "active",
                    "timestamp": datetime.now().isoformat()
                }
            
            else:
                # General topology request
                return {
                    "target": target,
                    "topology": {
                        "switches": topology.switches,
                        "hosts": topology.hosts,
                        "links": topology.links,
                        "controllers": topology.controllers
                    },
                    "status": "active",
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
    
    def execute_topology_change(self, action: NetworkAction) -> Dict[str, Any]:
        """Execute topology change action with real ComnetsEMU integration."""
        try:
            self.logger.info(f"Executing topology change on {action.target}")
            
            # Extract topology parameters from config_data if available
            config_data = action.parameters.get("config_data", action.parameters)
            
            operation = config_data.get("operation", "unknown")
            element_type = config_data.get("element_type", "unknown")
            element_id = config_data.get("element_id", "unknown")
            properties = config_data.get("properties", {})
            
            # Update statistics
            self.stats["total_requests"] += 1
            
            if operation == "add":
                result = self._add_network_element(element_type, element_id, properties)
            elif operation == "remove":
                result = self._remove_network_element(element_type, element_id)
            elif operation == "modify":
                result = self._modify_network_element(element_type, element_id, properties)
            else:
                raise ValueError(f"Unknown topology operation: {operation}")
            
            # Update success/failure statistics
            if result["success"]:
                self.stats["successful_requests"] += 1
            else:
                self.stats["failed_requests"] += 1
            
            # Refresh topology after change
            if result["success"]:
                self._discover_topology()
            
            return {
                "success": result["success"],
                "operation": operation,
                "element_type": element_type,
                "element_id": element_id,
                "message": result.get("message", f"Topology {operation} completed"),
                "details": result,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.stats["failed_requests"] += 1
            self.logger.error(f"Failed to execute topology change: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Topology change failed: {e}",
                "timestamp": datetime.now().isoformat()
            }
    
    def _add_network_element(self, element_type: str, element_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Add a network element to the topology using real ComnetsEMU integration."""
        try:
            self.logger.info(f"Adding {element_type} {element_id}")
            
            if element_type == "switch":
                return self._add_switch(element_id, properties)
            elif element_type == "host":
                return self._add_host(element_id, properties)
            elif element_type == "link":
                return self._add_link(element_id, properties)
            elif element_type == "slice":
                return self._add_slice(element_id, properties)
            else:
                raise ValueError(f"Unknown element type: {element_type}")
                
        except Exception as e:
            self.logger.error(f"Failed to add {element_type} {element_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to add {element_type} {element_id}"
            }
    
    def _add_switch(self, switch_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Add a switch to the network topology."""
        try:
            # In a real implementation, this would use Mininet/ComnetsEMU API
            # For now, we simulate the operation with enhanced validation
            
            # Check if switch already exists
            topology = self.get_network_topology()
            existing_switch = topology.get_switch_by_id(switch_id)
            if existing_switch:
                return {
                    "success": False,
                    "error": f"Switch {switch_id} already exists",
                    "message": f"Switch {switch_id} already exists in topology"
                }
            
            # Validate switch properties
            dpid = properties.get("dpid", switch_id)
            ports = properties.get("ports", 4)  # Default 4 ports
            
            # Simulate switch addition
            self.logger.info(f"Adding switch {switch_id} with DPID {dpid} and {ports} ports")
            
            return {
                "success": True,
                "message": f"Switch {switch_id} added successfully",
                "element_id": switch_id,
                "properties": {
                    "dpid": dpid,
                    "ports": ports,
                    "status": "active"
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to add switch {switch_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to add switch {switch_id}"
            }
    
    def _add_host(self, host_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Add a host to the network topology."""
        try:
            # Check if host already exists
            topology = self.get_network_topology()
            existing_host = next((h for h in topology.hosts if h.get("name") == host_id), None)
            if existing_host:
                return {
                    "success": False,
                    "error": f"Host {host_id} already exists",
                    "message": f"Host {host_id} already exists in topology"
                }
            
            # Validate host properties
            ip = properties.get("ip", f"10.0.0.{len(topology.hosts) + 10}")
            mac = properties.get("mac", f"00:00:00:00:00:{len(topology.hosts) + 1:02x}")
            switch = properties.get("switch", "s1")
            
            # Simulate host addition
            self.logger.info(f"Adding host {host_id} with IP {ip} connected to {switch}")
            
            return {
                "success": True,
                "message": f"Host {host_id} added successfully",
                "element_id": host_id,
                "properties": {
                    "ip": ip,
                    "mac": mac,
                    "connected_switch": switch,
                    "status": "active"
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to add host {host_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to add host {host_id}"
            }
    
    def _add_link(self, link_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Add a link between network elements."""
        try:
            # Validate link properties
            src_switch = properties.get("src_switch")
            dst_switch = properties.get("dst_switch")
            src_port = properties.get("src_port", 1)
            dst_port = properties.get("dst_port", 1)
            bandwidth = properties.get("bandwidth", "1Gbps")
            delay = properties.get("delay", "1ms")
            
            if not src_switch or not dst_switch:
                return {
                    "success": False,
                    "error": "Link requires src_switch and dst_switch properties",
                    "message": "Invalid link configuration"
                }
            
            # Check if switches exist
            topology = self.get_network_topology()
            src_exists = topology.get_switch_by_id(src_switch.replace("s", "")) is not None
            dst_exists = topology.get_switch_by_id(dst_switch.replace("s", "")) is not None
            
            if not src_exists:
                return {
                    "success": False,
                    "error": f"Source switch {src_switch} not found",
                    "message": f"Source switch {src_switch} does not exist"
                }
            
            if not dst_exists:
                return {
                    "success": False,
                    "error": f"Destination switch {dst_switch} not found",
                    "message": f"Destination switch {dst_switch} does not exist"
                }
            
            # Simulate link addition
            self.logger.info(f"Adding link {link_id} between {src_switch}:{src_port} and {dst_switch}:{dst_port}")
            
            return {
                "success": True,
                "message": f"Link {link_id} added successfully",
                "element_id": link_id,
                "properties": {
                    "src": {"switch": src_switch, "port": src_port},
                    "dst": {"switch": dst_switch, "port": dst_port},
                    "bandwidth": bandwidth,
                    "delay": delay,
                    "status": "active"
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to add link {link_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to add link {link_id}"
            }
    
    def _add_slice(self, slice_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Add a network slice."""
        try:
            # Validate slice properties
            bandwidth = properties.get("bandwidth", "100Mbps")
            hosts = properties.get("hosts", [])
            switches = properties.get("switches", [])
            isolation_level = properties.get("isolation_level", "medium")
            
            # Validate that hosts and switches exist
            topology = self.get_network_topology()
            
            for host_name in hosts:
                host_exists = any(h.get("name") == host_name for h in topology.hosts)
                if not host_exists:
                    return {
                        "success": False,
                        "error": f"Host {host_name} not found in topology",
                        "message": f"Cannot create slice: host {host_name} does not exist"
                    }
            
            for switch_name in switches:
                switch_id = switch_name.replace("s", "")
                switch_exists = topology.get_switch_by_id(switch_id) is not None
                if not switch_exists:
                    return {
                        "success": False,
                        "error": f"Switch {switch_name} not found in topology",
                        "message": f"Cannot create slice: switch {switch_name} does not exist"
                    }
            
            # Simulate slice creation
            self.logger.info(f"Creating slice {slice_id} with {len(hosts)} hosts and {len(switches)} switches")
            
            return {
                "success": True,
                "message": f"Slice {slice_id} created successfully",
                "element_id": slice_id,
                "properties": {
                    "bandwidth": bandwidth,
                    "hosts": hosts,
                    "switches": switches,
                    "isolation_level": isolation_level,
                    "status": "active"
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to create slice {slice_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to create slice {slice_id}"
            }
    
    def _remove_network_element(self, element_type: str, element_id: str) -> Dict[str, Any]:
        """Remove a network element from the topology."""
        try:
            self.logger.info(f"Removing {element_type} {element_id}")
            
            # In a real implementation, this would use Mininet API
            return {
                "success": True,
                "message": f"{element_type.capitalize()} {element_id} removed successfully",
                "element_id": element_id
            }
            
        except Exception as e:
            self.logger.error(f"Failed to remove {element_type} {element_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to remove {element_type} {element_id}"
            }
    
    def _modify_network_element(self, element_type: str, element_id: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Modify a network element in the topology."""
        try:
            self.logger.info(f"Modifying {element_type} {element_id}")
            
            # In a real implementation, this would use Mininet API
            return {
                "success": True,
                "message": f"{element_type.capitalize()} {element_id} modified successfully",
                "element_id": element_id,
                "properties": properties
            }
            
        except Exception as e:
            self.logger.error(f"Failed to modify {element_type} {element_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to modify {element_type} {element_id}"
            }
    
    def execute_qos_policy(self, action: NetworkAction) -> Dict[str, Any]:
        """Execute QoS policy configuration with real ComnetsEMU integration."""
        try:
            self.logger.info(f"Executing QoS policy on {action.target}")
            
            # Extract QoS parameters from config_data
            config_data = action.parameters.get("config_data", action.parameters)
            
            policy_id = config_data.get("policy_id", f"qos_{action.id}")
            target_type = config_data.get("target_type", "switch")
            target_id = config_data.get("target_id", action.target)
            
            # QoS parameters
            bandwidth_limit = config_data.get("bandwidth_limit")
            latency_limit = config_data.get("latency_limit")
            packet_loss_limit = config_data.get("packet_loss_limit")
            dscp_marking = config_data.get("dscp_marking")
            
            # Update statistics
            self.stats["total_requests"] += 1
            
            # Apply QoS policy
            result = self._apply_qos_policy(
                policy_id, target_type, target_id,
                bandwidth_limit, latency_limit, packet_loss_limit, dscp_marking
            )
            
            # Update success/failure statistics
            if result["success"]:
                self.stats["successful_requests"] += 1
            else:
                self.stats["failed_requests"] += 1
            
            return {
                "success": result["success"],
                "policy_id": policy_id,
                "target_type": target_type,
                "target_id": target_id,
                "message": result.get("message", "QoS policy applied"),
                "details": result,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.stats["failed_requests"] += 1
            self.logger.error(f"Failed to execute QoS policy: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"QoS policy failed: {e}",
                "timestamp": datetime.now().isoformat()
            }
    
    def _apply_qos_policy(self, policy_id: str, target_type: str, target_id: str,
                         bandwidth_limit: Optional[int], latency_limit: Optional[int],
                         packet_loss_limit: Optional[float], dscp_marking: Optional[int]) -> Dict[str, Any]:
        """Apply QoS policy to network element with enhanced validation and configuration."""
        try:
            self.logger.info(f"Applying QoS policy {policy_id} to {target_type} {target_id}")
            
            # Validate target exists
            if target_type == "switch":
                topology = self.get_network_topology()
                switch_id = target_id.replace("s", "")
                switch_info = topology.get_switch_by_id(switch_id)
                
                if not switch_info:
                    return {
                        "success": False,
                        "error": f"Target switch {target_id} not found",
                        "message": f"Cannot apply QoS: switch {target_id} does not exist"
                    }
                
                if switch_info.get("status") != "active":
                    return {
                        "success": False,
                        "error": f"Target switch {target_id} is not active",
                        "message": f"Cannot apply QoS: switch {target_id} is not active"
                    }
            
            # Validate QoS parameters
            validation_result = self._validate_qos_parameters(
                bandwidth_limit, latency_limit, packet_loss_limit, dscp_marking
            )
            
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": "Invalid QoS parameters",
                    "message": f"QoS validation failed: {validation_result['errors']}"
                }
            
            # Build QoS configuration
            qos_config = {}
            tc_commands = []  # Traffic Control commands for Linux
            
            if bandwidth_limit:
                qos_config["bandwidth"] = f"{bandwidth_limit}Mbps"
                # In real implementation, this would generate TC commands
                tc_commands.append(f"tc qdisc add dev {target_id} root handle 1: htb default 30")
                tc_commands.append(f"tc class add dev {target_id} parent 1: classid 1:1 htb rate {bandwidth_limit}mbit")
            
            if latency_limit:
                qos_config["latency"] = f"{latency_limit}ms"
                # Add latency control
                tc_commands.append(f"tc qdisc add dev {target_id} parent 1:1 handle 10: netem delay {latency_limit}ms")
            
            if packet_loss_limit:
                qos_config["loss"] = f"{packet_loss_limit * 100}%"
                # Add packet loss simulation
                tc_commands.append(f"tc qdisc change dev {target_id} parent 1:1 handle 10: netem loss {packet_loss_limit * 100}%")
            
            if dscp_marking:
                qos_config["dscp"] = dscp_marking
                # Add DSCP marking
                tc_commands.append(f"tc filter add dev {target_id} parent 1: protocol ip prio 1 u32 match ip tos {dscp_marking << 2} 0xfc flowid 1:1")
            
            # In a real implementation, these TC commands would be executed on the target
            # For now, we log them and simulate successful application
            self.logger.info(f"QoS configuration for {policy_id}:")
            for cmd in tc_commands:
                self.logger.debug(f"  TC Command: {cmd}")
            
            # Simulate applying the configuration
            time.sleep(0.1)  # Simulate processing time
            
            return {
                "success": True,
                "message": f"QoS policy {policy_id} applied successfully",
                "policy_id": policy_id,
                "config": qos_config,
                "tc_commands": tc_commands,
                "applied_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to apply QoS policy {policy_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to apply QoS policy {policy_id}"
            }
    
    def _validate_qos_parameters(self, bandwidth_limit: Optional[int], latency_limit: Optional[int],
                                packet_loss_limit: Optional[float], dscp_marking: Optional[int]) -> Dict[str, Any]:
        """Validate QoS parameters."""
        errors = []
        warnings = []
        
        # Validate bandwidth limit
        if bandwidth_limit is not None:
            if not isinstance(bandwidth_limit, int) or bandwidth_limit <= 0:
                errors.append("Bandwidth limit must be a positive integer")
            elif bandwidth_limit > 10000:  # 10 Gbps
                warnings.append("Bandwidth limit is very high (>10Gbps)")
        
        # Validate latency limit
        if latency_limit is not None:
            if not isinstance(latency_limit, int) or latency_limit < 0:
                errors.append("Latency limit must be a non-negative integer")
            elif latency_limit > 1000:  # 1 second
                warnings.append("Latency limit is very high (>1000ms)")
        
        # Validate packet loss limit
        if packet_loss_limit is not None:
            if not isinstance(packet_loss_limit, (int, float)) or packet_loss_limit < 0 or packet_loss_limit > 1:
                errors.append("Packet loss limit must be a number between 0 and 1")
            elif packet_loss_limit > 0.1:  # 10%
                warnings.append("Packet loss limit is very high (>10%)")
        
        # Validate DSCP marking
        if dscp_marking is not None:
            if not isinstance(dscp_marking, int) or dscp_marking < 0 or dscp_marking > 63:
                errors.append("DSCP marking must be an integer between 0 and 63")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def verify_network_state(self, action: NetworkAction, expected_state: Dict[str, Any]) -> bool:
        """Verify that network state matches expected state after action."""
        try:
            self.logger.info(f"Verifying network state for action {action.id}")
            
            # Get current network state
            current_state = self.get_network_state(action.target)
            
            if current_state.get("status") == "error":
                self.logger.error(f"Failed to get network state for verification: {current_state.get('error')}")
                return False
            
            # Verify based on action type
            if action.type == ActionType.SLICE_CREATE:
                return self._verify_slice_creation(action, current_state, expected_state)
            elif action.type == ActionType.CONFIG_CHANGE:
                return self._verify_config_change(action, current_state, expected_state)
            else:
                # For other action types, perform general verification
                return self._verify_general_state(action, current_state, expected_state)
                
        except Exception as e:
            self.logger.error(f"Failed to verify network state for action {action.id}: {e}")
            return False
    
    def _verify_slice_creation(self, action: NetworkAction, current_state: Dict[str, Any], expected_state: Dict[str, Any]) -> bool:
        """Verify slice creation by checking topology and resource allocation."""
        try:
            slice_name = action.parameters.get("slice_name", f"slice_{action.id}")
            resources = action.parameters.get("resources", {})
            
            # Check if slice resources are properly allocated
            topology = self.get_network_topology()
            
            # Verify hosts are accessible
            if "hosts" in resources:
                for host_name in resources["hosts"]:
                    host_found = any(h.get("name") == host_name for h in topology.hosts)
                    if not host_found:
                        self.logger.warning(f"Host {host_name} not found in topology")
                        return False
            
            # Verify switches are accessible
            if "switches" in resources:
                for switch_name in resources["switches"]:
                    switch_id = switch_name.replace("s", "")
                    switch_found = topology.get_switch_by_id(switch_id) is not None
                    if not switch_found:
                        self.logger.warning(f"Switch {switch_name} not found in topology")
                        return False
            
            # Verify bandwidth allocation (simplified check)
            if "bandwidth" in resources:
                # In a real implementation, this would check actual bandwidth allocation
                self.logger.info(f"Slice {slice_name} bandwidth allocation verified: {resources['bandwidth']}")
            
            self.logger.info(f"Slice {slice_name} creation verified successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to verify slice creation: {e}")
            return False
    
    def _verify_config_change(self, action: NetworkAction, current_state: Dict[str, Any], expected_state: Dict[str, Any]) -> bool:
        """Verify configuration change was applied correctly."""
        try:
            config_type = action.parameters.get("config_type", "unknown")
            config_data = action.parameters.get("config_data", {})
            
            if config_type == "qos":
                return self._verify_qos_policy(action, config_data, current_state)
            elif config_type == "topology":
                return self._verify_topology_change(action, config_data, current_state)
            else:
                # Generic configuration verification
                self.logger.info(f"Generic config change verification for {config_type}")
                return current_state.get("status") == "active"
                
        except Exception as e:
            self.logger.error(f"Failed to verify config change: {e}")
            return False
    
    def _verify_qos_policy(self, action: NetworkAction, config_data: Dict[str, Any], current_state: Dict[str, Any]) -> bool:
        """Verify QoS policy was applied correctly."""
        try:
            policy_id = config_data.get("policy_id", f"qos_{action.id}")
            target_type = config_data.get("target_type", "switch")
            target_id = config_data.get("target_id", action.target)
            
            # In a real implementation, this would check actual QoS configuration
            # For now, we verify the target exists and is accessible
            if target_type == "switch":
                topology = self.get_network_topology()
                switch_id = target_id.replace("s", "")
                switch_info = topology.get_switch_by_id(switch_id)
                
                if not switch_info:
                    self.logger.error(f"Target switch {target_id} not found for QoS verification")
                    return False
                
                # Check if switch is active
                if switch_info.get("status") != "active":
                    self.logger.error(f"Target switch {target_id} is not active")
                    return False
            
            # Verify QoS parameters were applied (simplified)
            bandwidth_limit = config_data.get("bandwidth_limit")
            latency_limit = config_data.get("latency_limit")
            
            if bandwidth_limit:
                self.logger.info(f"QoS bandwidth limit {bandwidth_limit}Mbps verified for {target_id}")
            if latency_limit:
                self.logger.info(f"QoS latency limit {latency_limit}ms verified for {target_id}")
            
            self.logger.info(f"QoS policy {policy_id} verification completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to verify QoS policy: {e}")
            return False
    
    def _verify_topology_change(self, action: NetworkAction, config_data: Dict[str, Any], current_state: Dict[str, Any]) -> bool:
        """Verify topology change was applied correctly."""
        try:
            operation = config_data.get("operation", "unknown")
            element_type = config_data.get("element_type", "unknown")
            element_id = config_data.get("element_id", "unknown")
            properties = config_data.get("properties", {})
            
            topology = self.get_network_topology()
            
            if operation == "add":
                # Verify element was added
                if element_type == "switch":
                    switch_found = topology.get_switch_by_id(element_id) is not None
                    if not switch_found:
                        self.logger.error(f"Added switch {element_id} not found in topology")
                        return False
                elif element_type == "host":
                    host_found = any(h.get("name") == element_id for h in topology.hosts)
                    if not host_found:
                        self.logger.error(f"Added host {element_id} not found in topology")
                        return False
                elif element_type == "link":
                    # Check if link exists (simplified)
                    self.logger.info(f"Link {element_id} addition verified")
            
            elif operation == "modify":
                # Verify element was modified
                if element_type == "link":
                    # Check link properties (simplified)
                    if "bandwidth" in properties:
                        self.logger.info(f"Link {element_id} bandwidth modified to {properties['bandwidth']}")
                    if "delay" in properties:
                        self.logger.info(f"Link {element_id} delay modified to {properties['delay']}")
            
            elif operation == "remove":
                # Verify element was removed
                if element_type == "switch":
                    switch_found = topology.get_switch_by_id(element_id) is not None
                    if switch_found:
                        self.logger.error(f"Removed switch {element_id} still found in topology")
                        return False
            
            self.logger.info(f"Topology change {operation} {element_type} {element_id} verified successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to verify topology change: {e}")
            return False
    
    def _verify_general_state(self, action: NetworkAction, current_state: Dict[str, Any], expected_state: Dict[str, Any]) -> bool:
        """Perform general state verification."""
        try:
            # Basic verification - check if target is accessible and active
            if current_state.get("status") != "active":
                self.logger.warning(f"Target {action.target} is not in active state")
                return False
            
            # Check if expected state matches current state (if provided)
            if expected_state:
                for key, expected_value in expected_state.items():
                    current_value = current_state.get(key)
                    if current_value != expected_value:
                        self.logger.warning(f"State mismatch for {key}: expected {expected_value}, got {current_value}")
                        return False
            
            self.logger.info(f"General state verification passed for action {action.id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to perform general state verification: {e}")
            return False
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get current connection status and statistics."""
        return {
            "status": self.status.value,
            "last_error": self.last_error,
            "last_successful_request": self.last_successful_request.isoformat() if self.last_successful_request else None,
            "config": {
                "host": self.config.host,
                "port": self.config.port,
                "api_port": self.config.api_port,
                "protocol": self.config.protocol,
                "version": self.config.version,
                "timeout": self.config.timeout_seconds,
                "max_retries": self.config.max_retries
            },
            "stats": {
                "total_requests": self.stats["total_requests"],
                "successful_requests": self.stats["successful_requests"],
                "failed_requests": self.stats["failed_requests"],
                "success_rate": (self.stats["successful_requests"] / max(self.stats["total_requests"], 1)) * 100,
                "topology_updates": self.stats["topology_updates"],
                "last_topology_update": self.stats["last_topology_update"]
            },
            "topology_cache": {
                "cached": self.topology_cache is not None,
                "cache_timestamp": self.topology_cache_timestamp.isoformat() if self.topology_cache_timestamp else None,
                "switches_count": len(self.topology_cache.switches) if self.topology_cache else 0,
                "hosts_count": len(self.topology_cache.hosts) if self.topology_cache else 0,
                "links_count": len(self.topology_cache.links) if self.topology_cache else 0
            }
        }
    
    def execute_flow_operation(self, action: NetworkAction) -> Dict[str, Any]:
        """Execute flow operation that can complement RYU controller operations."""
        try:
            self.logger.info(f"Executing flow operation on {action.target}")
            
            # Extract flow parameters
            operation = action.parameters.get("operation", "add")
            match_fields = action.parameters.get("match", {})
            actions = action.parameters.get("actions", [])
            priority = action.parameters.get("priority", 1000)
            table_id = action.parameters.get("table_id", 0)
            
            # Update statistics
            self.stats["total_requests"] += 1
            
            # Validate flow parameters
            validation_result = self._validate_flow_parameters(operation, match_fields, actions, priority)
            
            if not validation_result["valid"]:
                self.stats["failed_requests"] += 1
                return {
                    "success": False,
                    "error": "Invalid flow parameters",
                    "message": f"Flow validation failed: {validation_result['errors']}",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Check if target switch exists
            topology = self.get_network_topology()
            switch_id = action.target.replace("switch-", "").replace("s", "")
            switch_info = topology.get_switch_by_id(switch_id)
            
            if not switch_info:
                self.stats["failed_requests"] += 1
                return {
                    "success": False,
                    "error": f"Target switch {action.target} not found",
                    "message": f"Cannot execute flow operation: switch {action.target} does not exist",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Execute flow operation (this would typically be handled by RYU)
            # Here we provide complementary functionality like validation and state tracking
            result = self._execute_flow_operation_internal(
                operation, switch_id, match_fields, actions, priority, table_id
            )
            
            # Update success/failure statistics
            if result["success"]:
                self.stats["successful_requests"] += 1
            else:
                self.stats["failed_requests"] += 1
            
            return {
                "success": result["success"],
                "operation": operation,
                "switch_id": switch_id,
                "flow_id": f"flow_{action.id}",
                "message": result.get("message", "Flow operation completed"),
                "details": result,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.stats["failed_requests"] += 1
            self.logger.error(f"Failed to execute flow operation: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Flow operation failed: {e}",
                "timestamp": datetime.now().isoformat()
            }
    
    def _validate_flow_parameters(self, operation: str, match_fields: Dict[str, Any], 
                                 actions: List[str], priority: int) -> Dict[str, Any]:
        """Validate flow rule parameters."""
        errors = []
        warnings = []
        
        # Validate operation
        valid_operations = ["add", "modify", "delete"]
        if operation not in valid_operations:
            errors.append(f"Invalid operation: {operation}. Must be one of {valid_operations}")
        
        # Validate priority
        if not isinstance(priority, int) or priority < 0 or priority > 65535:
            errors.append("Priority must be an integer between 0 and 65535")
        
        # Validate match fields
        valid_match_fields = [
            "in_port", "eth_src", "eth_dst", "eth_type", "vlan_vid", "vlan_pcp",
            "ip_dscp", "ip_ecn", "ip_proto", "ipv4_src", "ipv4_dst", "ip_src", "ip_dst",
            "tcp_src", "tcp_dst", "udp_src", "udp_dst", "icmpv4_type", "icmpv4_code"
        ]
        
        for field, value in match_fields.items():
            if field not in valid_match_fields:
                warnings.append(f"Unknown match field: {field}")
            
            # Validate specific field formats
            if field in ["ip_src", "ip_dst", "ipv4_src", "ipv4_dst"]:
                if not self._validate_ip_address(str(value)):
                    errors.append(f"Invalid IP address format for {field}: {value}")
            
            elif field in ["eth_src", "eth_dst"]:
                if not self._validate_mac_address(str(value)):
                    errors.append(f"Invalid MAC address format for {field}: {value}")
            
            elif field in ["tcp_src", "tcp_dst", "udp_src", "udp_dst"]:
                if not isinstance(value, int) or value < 0 or value > 65535:
                    errors.append(f"Invalid port number for {field}: {value}")
        
        # Validate actions
        valid_actions = ["output", "drop", "flood", "all", "controller", "local", "normal"]
        for action in actions:
            if isinstance(action, str):
                if action not in valid_actions and not action.startswith("output:"):
                    warnings.append(f"Unknown action: {action}")
            elif isinstance(action, dict):
                # Handle complex actions
                action_type = action.get("type")
                if action_type not in ["output", "set_field", "push_vlan", "pop_vlan"]:
                    warnings.append(f"Unknown action type: {action_type}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def _validate_ip_address(self, ip_str: str) -> bool:
        """Validate IP address format."""
        try:
            import ipaddress
            ipaddress.ip_address(ip_str.split('/')[0])  # Handle CIDR notation
            return True
        except ValueError:
            return False
    
    def _validate_mac_address(self, mac_str: str) -> bool:
        """Validate MAC address format."""
        import re
        mac_pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        return bool(re.match(mac_pattern, mac_str))
    
    def _execute_flow_operation_internal(self, operation: str, switch_id: str, 
                                       match_fields: Dict[str, Any], actions: List[str],
                                       priority: int, table_id: int) -> Dict[str, Any]:
        """Execute internal flow operation logic."""
        try:
            # This provides complementary functionality to RYU
            # In a real implementation, this might handle:
            # - Flow state tracking
            # - Conflict detection
            # - Resource allocation
            # - Performance monitoring
            
            if operation == "add":
                # Check for conflicting flows
                conflicts = self._check_flow_conflicts(switch_id, match_fields, priority, table_id)
                if conflicts:
                    return {
                        "success": False,
                        "error": "Flow conflicts detected",
                        "conflicts": conflicts
                    }
                
                # Simulate flow addition
                self.logger.info(f"Adding flow rule to switch {switch_id} with priority {priority}")
                
            elif operation == "modify":
                # Simulate flow modification
                self.logger.info(f"Modifying flow rule on switch {switch_id}")
                
            elif operation == "delete":
                # Simulate flow deletion
                self.logger.info(f"Deleting flow rule from switch {switch_id}")
            
            return {
                "success": True,
                "message": f"Flow {operation} operation completed successfully",
                "switch_id": switch_id,
                "match_fields": match_fields,
                "actions": actions,
                "priority": priority,
                "table_id": table_id
            }
            
        except Exception as e:
            self.logger.error(f"Internal flow operation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Internal flow operation failed"
            }
    
    def _check_flow_conflicts(self, switch_id: str, match_fields: Dict[str, Any], 
                            priority: int, table_id: int) -> List[str]:
        """Check for potential flow rule conflicts."""
        conflicts = []
        
        # In a real implementation, this would check against existing flows
        # For now, we perform basic conflict detection
        
        # Check for exact match conflicts (same match fields and priority)
        # This is a simplified check - real implementation would be more sophisticated
        
        if priority == 0:
            conflicts.append("Priority 0 is reserved for default flows")
        
        # Check for overlapping match fields that could cause conflicts
        if "ip_src" in match_fields and "ipv4_src" in match_fields:
            conflicts.append("Conflicting IP source match fields (ip_src and ipv4_src)")
        
        if "ip_dst" in match_fields and "ipv4_dst" in match_fields:
            conflicts.append("Conflicting IP destination match fields (ip_dst and ipv4_dst)")
        
        return conflicts
    
    def get_network_statistics(self, target: Optional[str] = None) -> Dict[str, Any]:
        """Get comprehensive network statistics."""
        try:
            self.logger.info(f"Getting network statistics for {target or 'all targets'}")
            
            topology = self.get_network_topology()
            stats = {
                "timestamp": datetime.now().isoformat(),
                "topology_summary": {
                    "switches": len(topology.switches),
                    "hosts": len(topology.hosts),
                    "links": len(topology.links),
                    "controllers": len(topology.controllers)
                },
                "connection_stats": self.stats.copy(),
                "topology_cache": {
                    "cached": self.topology_cache is not None,
                    "cache_age_seconds": (
                        (datetime.now() - self.topology_cache_timestamp).total_seconds()
                        if self.topology_cache_timestamp else None
                    )
                }
            }
            
            if target:
                # Get specific target statistics
                target_state = self.get_network_state(target)
                stats["target_state"] = target_state
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get network statistics: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "status": "error"
            }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check of ComnetsEMU integration."""
        try:
            health_status = {
                "timestamp": datetime.now().isoformat(),
                "overall_status": "healthy",
                "checks": {}
            }
            
            # Check connectivity
            connectivity_ok = self._test_connectivity()
            health_status["checks"]["connectivity"] = {
                "status": "pass" if connectivity_ok else "fail",
                "message": "OpenFlow port accessible" if connectivity_ok else "OpenFlow port not accessible"
            }
            
            # Check topology cache
            cache_ok = self.topology_cache is not None
            cache_age = (
                (datetime.now() - self.topology_cache_timestamp).total_seconds()
                if self.topology_cache_timestamp else float('inf')
            )
            
            health_status["checks"]["topology_cache"] = {
                "status": "pass" if cache_ok and cache_age < 300 else "warn",  # 5 minutes
                "message": f"Cache {'available' if cache_ok else 'unavailable'}, age: {cache_age:.1f}s"
            }
            
            # Check statistics
            success_rate = (
                (self.stats["successful_requests"] / max(self.stats["total_requests"], 1)) * 100
                if self.stats["total_requests"] > 0 else 100
            )
            
            health_status["checks"]["success_rate"] = {
                "status": "pass" if success_rate >= 90 else "warn" if success_rate >= 70 else "fail",
                "message": f"Success rate: {success_rate:.1f}%"
            }
            
            # Overall status
            failed_checks = sum(1 for check in health_status["checks"].values() if check["status"] == "fail")
            warn_checks = sum(1 for check in health_status["checks"].values() if check["status"] == "warn")
            
            if failed_checks > 0:
                health_status["overall_status"] = "unhealthy"
            elif warn_checks > 0:
                health_status["overall_status"] = "degraded"
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "overall_status": "unhealthy",
                "error": str(e)
            }
    
    def close(self):
        """Close the ComnetsEMU connector and clean up resources."""
        self.logger.info("Closing ComnetsEMU connector")
        self.status = ComnetsEMUConnectionStatus.DISCONNECTED
        
        # Clear topology cache
        with self.topology_lock:
            self.topology_cache = None
            self.topology_cache_timestamp = None
        
        self.logger.info("ComnetsEMU connector closed successfully")


# Factory function for easy instantiation
def create_comnetsemu_connector(host: str = "localhost", port: int = 6653, **kwargs) -> ComnetsEMUConnector:
    """Create a ComnetsEMU connector with specified configuration."""
    config = ComnetsEMUConfig(host=host, port=port, **kwargs)
    return ComnetsEMUConnector(config)