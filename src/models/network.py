"""Network-related data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator
import re


class Switch(BaseModel):
    """Network switch representation."""
    id: str
    name: str
    dpid: str
    ports: List[int] = Field(default_factory=list)
    status: str = "active"


class Link(BaseModel):
    """Network link representation."""
    id: str
    source_switch: str
    source_port: int
    destination_switch: str
    destination_port: int
    bandwidth: Optional[int] = None
    latency: Optional[float] = None
    status: str = "active"


class Host(BaseModel):
    """Network host representation."""
    id: str
    mac_address: str
    ip_address: Optional[str] = None
    connected_switch: str
    connected_port: int
    status: str = "active"


class Flow(BaseModel):
    """Network flow representation."""
    id: str
    switch_id: str
    match_fields: Dict[str, Any] = Field(default_factory=dict)
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    priority: int = 1000
    idle_timeout: int = 0
    hard_timeout: int = 0
    byte_count: int = 0
    packet_count: int = 0


class BandwidthMetrics(BaseModel):
    """Bandwidth utilization metrics."""
    total_capacity: int
    used_bandwidth: int
    available_bandwidth: int
    utilization_percentage: float = Field(ge=0.0, le=100.0)


class LatencyMetrics(BaseModel):
    """Network latency metrics."""
    average_latency: float
    min_latency: float
    max_latency: float
    jitter: float


class UtilizationMetrics(BaseModel):
    """Resource utilization metrics."""
    cpu_utilization: float = Field(ge=0.0, le=100.0)
    memory_utilization: float = Field(ge=0.0, le=100.0)
    port_utilization: Dict[str, float] = Field(default_factory=dict)


class NetworkMetrics(BaseModel):
    """Comprehensive network metrics."""
    bandwidth: BandwidthMetrics
    latency: LatencyMetrics
    utilization: UtilizationMetrics


class Topology(BaseModel):
    """Network topology representation."""
    switches: List[Switch] = Field(default_factory=list)
    links: List[Link] = Field(default_factory=list)
    hosts: List[Host] = Field(default_factory=list)


class AnomalyType(str, Enum):
    """Types of network anomalies."""
    TRAFFIC_SPIKE = "traffic_spike"
    LATENCY_INCREASE = "latency_increase"
    LINK_FAILURE = "link_failure"
    SWITCH_FAILURE = "switch_failure"
    SECURITY_THREAT = "security_threat"


class AnomalySeverity(str, Enum):
    """Severity levels for anomalies."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Anomaly(BaseModel):
    """Network anomaly representation."""
    id: str
    type: AnomalyType
    severity: AnomalySeverity
    description: str
    affected_resources: List[str] = Field(default_factory=list)
    detected_at: datetime
    resolved_at: Optional[datetime] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)


class NetworkState(BaseModel):
    """Complete network state representation."""
    timestamp: datetime
    topology: Topology
    flows: List[Flow] = Field(default_factory=list)
    metrics: NetworkMetrics
    anomalies: List[Anomaly] = Field(default_factory=list)

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    @validator('timestamp')
    def validate_timestamp(cls, v):
        """Validate timestamp is not in the future."""
        if v > datetime.now():
            raise ValueError("Network state timestamp cannot be in the future")
        return v

    @validator('flows')
    def validate_flows(cls, v, values):
        """Validate flows against topology."""
        if 'topology' not in values:
            return v
        
        topology = values['topology']
        switch_ids = {switch.id for switch in topology.switches}
        
        for flow in v:
            if flow.switch_id not in switch_ids:
                raise ValueError(f"Flow {flow.id} references non-existent switch {flow.switch_id}")
        
        return v

    def validate_data_integrity(self) -> Dict[str, Any]:
        """Validate network state data integrity."""
        issues = []
        warnings = []
        
        # Check topology consistency
        switch_ids = {switch.id for switch in self.topology.switches}
        host_switches = {host.connected_switch for host in self.topology.hosts}
        
        # Validate host connections
        for host in self.topology.hosts:
            if host.connected_switch not in switch_ids:
                issues.append(f"Host {host.id} connected to non-existent switch {host.connected_switch}")
        
        # Validate link connections
        for link in self.topology.links:
            if link.source_switch not in switch_ids:
                issues.append(f"Link {link.id} source switch {link.source_switch} does not exist")
            if link.destination_switch not in switch_ids:
                issues.append(f"Link {link.id} destination switch {link.destination_switch} does not exist")
        
        # Check flow consistency
        for flow in self.flows:
            if flow.switch_id not in switch_ids:
                issues.append(f"Flow {flow.id} references non-existent switch {flow.switch_id}")
        
        # Check metrics consistency
        total_bandwidth = sum(link.bandwidth or 0 for link in self.topology.links)
        if total_bandwidth > 0 and self.metrics.bandwidth.total_capacity > total_bandwidth * 2:
            warnings.append("Total bandwidth capacity seems unusually high compared to link capacities")
        
        # Check for negative metrics (invalid)
        if self.metrics.bandwidth.utilization_percentage < 0:
            issues.append("Bandwidth utilization percentage cannot be negative")
        if self.metrics.latency.average_latency < 0:
            issues.append("Average latency cannot be negative")
        if self.metrics.utilization.cpu_utilization < 0:
            issues.append("CPU utilization cannot be negative")
        if self.metrics.utilization.memory_utilization < 0:
            issues.append("Memory utilization cannot be negative")
        
        # Check anomaly references
        all_resource_ids = (switch_ids | 
                           {link.id for link in self.topology.links} | 
                           {host.id for host in self.topology.hosts})
        
        for anomaly in self.anomalies:
            for resource in anomaly.affected_resources:
                if resource not in all_resource_ids:
                    warnings.append(f"Anomaly {anomaly.id} references unknown resource {resource}")
        
        # Check data freshness
        age_seconds = (datetime.now() - self.timestamp).total_seconds()
        if age_seconds > 300:  # 5 minutes
            warnings.append(f"Network state data is {age_seconds:.0f} seconds old")
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "topology_summary": {
                "switches": len(self.topology.switches),
                "links": len(self.topology.links),
                "hosts": len(self.topology.hosts)
            },
            "flows_count": len(self.flows),
            "anomalies_count": len(self.anomalies),
            "data_age_seconds": age_seconds
        }

    def is_resource_available(self, resource_id: str) -> bool:
        """Check if a network resource exists and is available."""
        # Check switches
        for switch in self.topology.switches:
            if switch.id == resource_id:
                return switch.status == "active"
        
        # Check links
        for link in self.topology.links:
            if link.id == resource_id:
                return link.status == "active"
        
        # Check hosts
        for host in self.topology.hosts:
            if host.id == resource_id:
                return host.status == "active"
        
        return False

    def get_resource_utilization(self, resource_id: str) -> Optional[float]:
        """Get utilization percentage for a specific resource."""
        # Check if it's a switch port
        if resource_id in self.metrics.utilization.port_utilization:
            return self.metrics.utilization.port_utilization[resource_id]
        
        # For switches, return CPU utilization as proxy
        for switch in self.topology.switches:
            if switch.id == resource_id:
                return self.metrics.utilization.cpu_utilization
        
        return None