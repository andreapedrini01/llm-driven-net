#!/usr/bin/env python3
"""
Complete mock implementation of ComnetsEMU for testing
Simulates network behavior without requiring actual ComnetsEMU installation
"""

import time
import random
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import threading


@dataclass
class MockSwitch:
    """Mock network switch."""
    dpid: str
    ports: int
    role: str = "edge"
    status: str = "active"
    flows: List[Dict[str, Any]] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        self.statistics = {
            "packets_in": 0,
            "packets_out": 0,
            "bytes_in": 0,
            "bytes_out": 0,
            "flows_active": 0
        }


@dataclass
class MockHost:
    """Mock network host."""
    name: str
    ip: str
    mac: str
    status: str = "active"
    connected_to: Optional[str] = None
    traffic_stats: Dict[str, int] = field(default_factory=dict)
    
    def __post_init__(self):
        self.traffic_stats = {
            "packets_sent": 0,
            "packets_received": 0,
            "bytes_sent": 0,
            "bytes_received": 0
        }


@dataclass
class MockLink:
    """Mock network link."""
    src: str
    dst: str
    bandwidth: int = 1000  # Mbps
    latency: int = 1  # ms
    packet_loss: float = 0.0
    status: str = "active"


class MockComnetsEMU:
    """
    Complete mock implementation of ComnetsEMU.
    Simulates network topology, traffic, and failures.
    """
    
    def __init__(self):
        self.switches: Dict[str, MockSwitch] = {}
        self.hosts: Dict[str, MockHost] = {}
        self.links: List[MockLink] = []
        self.qos_policies: Dict[str, Dict[str, Any]] = {}
        self.failure_scenarios: List[Dict[str, Any]] = []
        self.simulation_running = False
        self.simulation_thread = None
        
        # Initialize with default topology
        self._initialize_default_topology()
    
    def _initialize_default_topology(self):
        """Initialize a default network topology."""
        # Add default switches
        self.switches["s1"] = MockSwitch(dpid="1", ports=8, role="core")
        self.switches["s2"] = MockSwitch(dpid="2", ports=4, role="edge")
        
        # Add default hosts
        self.hosts["h1"] = MockHost(
            name="h1",
            ip="10.0.1.1",
            mac="00:00:00:00:01:01",
            connected_to="s1"
        )
        self.hosts["h2"] = MockHost(
            name="h2",
            ip="10.0.1.2",
            mac="00:00:00:00:01:02",
            connected_to="s2"
        )
        
        # Add default links
        self.links.append(MockLink(src="s1", dst="s2", bandwidth=1000, latency=1))
        self.links.append(MockLink(src="h1", dst="s1", bandwidth=100, latency=1))
        self.links.append(MockLink(src="h2", dst="s2", bandwidth=100, latency=1))
    
    def add_switch(self, dpid: str, ports: int = 4, role: str = "edge") -> bool:
        """Add a switch to the topology."""
        if dpid in self.switches:
            return False
        
        self.switches[dpid] = MockSwitch(dpid=dpid, ports=ports, role=role)
        return True
    
    def remove_switch(self, dpid: str) -> bool:
        """Remove a switch from the topology."""
        if dpid not in self.switches:
            return False
        
        # Remove associated links
        self.links = [link for link in self.links 
                     if link.src != dpid and link.dst != dpid]
        
        del self.switches[dpid]
        return True
    
    def add_host(self, name: str, ip: str, mac: str, connected_to: str = None) -> bool:
        """Add a host to the topology."""
        if name in self.hosts:
            return False
        
        self.hosts[name] = MockHost(
            name=name,
            ip=ip,
            mac=mac,
            connected_to=connected_to
        )
        
        # Add link if connected_to is specified
        if connected_to and connected_to in self.switches:
            self.links.append(MockLink(src=name, dst=connected_to, bandwidth=100))
        
        return True
    
    def remove_host(self, name: str) -> bool:
        """Remove a host from the topology."""
        if name not in self.hosts:
            return False
        
        # Remove associated links
        self.links = [link for link in self.links 
                     if link.src != name and link.dst != name]
        
        del self.hosts[name]
        return True
    
    def add_link(self, src: str, dst: str, bandwidth: int = 1000, 
                 latency: int = 1, packet_loss: float = 0.0) -> bool:
        """Add a link between two network elements."""
        # Check if link already exists
        for link in self.links:
            if (link.src == src and link.dst == dst) or \
               (link.src == dst and link.dst == src):
                return False
        
        self.links.append(MockLink(
            src=src,
            dst=dst,
            bandwidth=bandwidth,
            latency=latency,
            packet_loss=packet_loss
        ))
        return True
    
    def remove_link(self, src: str, dst: str) -> bool:
        """Remove a link between two network elements."""
        initial_count = len(self.links)
        self.links = [link for link in self.links 
                     if not ((link.src == src and link.dst == dst) or 
                            (link.src == dst and link.dst == src))]
        return len(self.links) < initial_count
    
    def add_flow(self, switch_dpid: str, flow: Dict[str, Any]) -> bool:
        """Add a flow rule to a switch."""
        if switch_dpid not in self.switches:
            return False
        
        switch = self.switches[switch_dpid]
        
        # Check for duplicate flows
        for existing_flow in switch.flows:
            if existing_flow.get("match") == flow.get("match") and \
               existing_flow.get("priority") == flow.get("priority"):
                return False
        
        switch.flows.append(flow)
        switch.statistics["flows_active"] = len(switch.flows)
        return True
    
    def remove_flow(self, switch_dpid: str, flow_id: str) -> bool:
        """Remove a flow rule from a switch."""
        if switch_dpid not in self.switches:
            return False
        
        switch = self.switches[switch_dpid]
        initial_count = len(switch.flows)
        switch.flows = [f for f in switch.flows if f.get("id") != flow_id]
        switch.statistics["flows_active"] = len(switch.flows)
        
        return len(switch.flows) < initial_count
    
    def set_qos_policy(self, policy_id: str, target_id: str, 
                       bandwidth_limit: int, latency_limit: int,
                       packet_loss_limit: float) -> bool:
        """Set QoS policy for a network element."""
        self.qos_policies[policy_id] = {
            "target_id": target_id,
            "bandwidth_limit": bandwidth_limit,
            "latency_limit": latency_limit,
            "packet_loss_limit": packet_loss_limit,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Apply to relevant links
        for link in self.links:
            if link.src == target_id or link.dst == target_id:
                link.bandwidth = min(link.bandwidth, bandwidth_limit)
                link.latency = max(link.latency, latency_limit)
                link.packet_loss = max(link.packet_loss, packet_loss_limit)
        
        return True
    
    def get_topology(self) -> Dict[str, Any]:
        """Get current network topology."""
        return {
            "switches": [
                {
                    "dpid": s.dpid,
                    "ports": s.ports,
                    "role": s.role,
                    "status": s.status,
                    "flows": len(s.flows)
                }
                for s in self.switches.values()
            ],
            "hosts": [
                {
                    "name": h.name,
                    "ip": h.ip,
                    "mac": h.mac,
                    "status": h.status,
                    "connected_to": h.connected_to
                }
                for h in self.hosts.values()
            ],
            "links": [
                {
                    "src": l.src,
                    "dst": l.dst,
                    "bandwidth": l.bandwidth,
                    "latency": l.latency,
                    "packet_loss": l.packet_loss,
                    "status": l.status
                }
                for l in self.links
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get network statistics."""
        total_flows = sum(len(s.flows) for s in self.switches.values())
        total_packets = sum(h.traffic_stats["packets_sent"] for h in self.hosts.values())
        
        return {
            "topology_summary": {
                "switches": len(self.switches),
                "hosts": len(self.hosts),
                "links": len(self.links),
                "total_flows": total_flows
            },
            "traffic_summary": {
                "total_packets": total_packets,
                "total_bytes": sum(h.traffic_stats["bytes_sent"] for h in self.hosts.values())
            },
            "qos_policies": len(self.qos_policies),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def inject_failure(self, failure_type: str, target: str, 
                       duration: int = 10) -> bool:
        """Inject a failure scenario for testing."""
        failure = {
            "type": failure_type,
            "target": target,
            "duration": duration,
            "start_time": time.time(),
            "active": True
        }
        
        self.failure_scenarios.append(failure)
        
        # Apply failure immediately
        if failure_type == "switch_down":
            if target in self.switches:
                self.switches[target].status = "down"
        elif failure_type == "link_down":
            for link in self.links:
                if link.src == target or link.dst == target:
                    link.status = "down"
        elif failure_type == "high_latency":
            for link in self.links:
                if link.src == target or link.dst == target:
                    link.latency *= 10
        elif failure_type == "packet_loss":
            for link in self.links:
                if link.src == target or link.dst == target:
                    link.packet_loss = 0.5
        
        return True
    
    def clear_failures(self):
        """Clear all active failures."""
        for failure in self.failure_scenarios:
            target = failure["target"]
            failure_type = failure["type"]
            
            if failure_type == "switch_down":
                if target in self.switches:
                    self.switches[target].status = "active"
            elif failure_type == "link_down":
                for link in self.links:
                    if link.src == target or link.dst == target:
                        link.status = "active"
            elif failure_type == "high_latency":
                for link in self.links:
                    if link.src == target or link.dst == target:
                        link.latency = 1
            elif failure_type == "packet_loss":
                for link in self.links:
                    if link.src == target or link.dst == target:
                        link.packet_loss = 0.0
        
        self.failure_scenarios = []
    
    def simulate_traffic(self, duration: int = 10):
        """Simulate network traffic for testing."""
        def traffic_generator():
            end_time = time.time() + duration
            
            while time.time() < end_time and self.simulation_running:
                # Randomly generate traffic between hosts
                if len(self.hosts) >= 2:
                    src_host = random.choice(list(self.hosts.values()))
                    dst_host = random.choice([h for h in self.hosts.values() 
                                            if h.name != src_host.name])
                    
                    # Simulate packet transmission
                    packet_size = random.randint(64, 1500)
                    src_host.traffic_stats["packets_sent"] += 1
                    src_host.traffic_stats["bytes_sent"] += packet_size
                    dst_host.traffic_stats["packets_received"] += 1
                    dst_host.traffic_stats["bytes_received"] += packet_size
                    
                    # Update switch statistics
                    for switch in self.switches.values():
                        switch.statistics["packets_in"] += 1
                        switch.statistics["packets_out"] += 1
                        switch.statistics["bytes_in"] += packet_size
                        switch.statistics["bytes_out"] += packet_size
                
                time.sleep(0.1)
        
        self.simulation_running = True
        self.simulation_thread = threading.Thread(target=traffic_generator)
        self.simulation_thread.start()
    
    def stop_simulation(self):
        """Stop traffic simulation."""
        self.simulation_running = False
        if self.simulation_thread:
            self.simulation_thread.join(timeout=5)
    
    def reset(self):
        """Reset the mock to initial state."""
        self.switches.clear()
        self.hosts.clear()
        self.links.clear()
        self.qos_policies.clear()
        self.failure_scenarios.clear()
        self.stop_simulation()
        self._initialize_default_topology()


# Singleton instance for testing
_mock_instance = None


def get_mock_comnetsemu() -> MockComnetsEMU:
    """Get singleton mock instance."""
    global _mock_instance
    if _mock_instance is None:
        _mock_instance = MockComnetsEMU()
    return _mock_instance


def reset_mock_comnetsemu():
    """Reset the mock instance."""
    global _mock_instance
    if _mock_instance:
        _mock_instance.reset()
