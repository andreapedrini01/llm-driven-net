"""Network slice-related data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator
import re


class SliceStatus(str, Enum):
    """Network slice status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    CONFIGURING = "configuring"
    ERROR = "error"


class Path(BaseModel):
    """Network path representation."""
    id: str
    switches: List[str] = Field(default_factory=list)
    links: List[str] = Field(default_factory=list)
    bandwidth: Optional[int] = None
    latency: Optional[float] = None

    @validator('id')
    def validate_id(cls, v):
        """Validate path ID format."""
        if not v or not isinstance(v, str):
            raise ValueError("Path ID must be a non-empty string")
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Path ID must contain only alphanumeric characters, underscores, and hyphens")
        return v

    @validator('switches')
    def validate_switches(cls, v):
        """Validate switches list."""
        if len(v) < 2:
            raise ValueError("Path must include at least 2 switches")
        # Check for duplicates
        if len(v) != len(set(v)):
            raise ValueError("Path cannot contain duplicate switches")
        return v

    @validator('bandwidth')
    def validate_bandwidth(cls, v):
        """Validate path bandwidth."""
        if v is not None:
            if not isinstance(v, int) or v <= 0:
                raise ValueError("Path bandwidth must be a positive integer")
        return v

    @validator('latency')
    def validate_latency(cls, v):
        """Validate path latency."""
        if v is not None:
            if not isinstance(v, (int, float)) or v < 0:
                raise ValueError("Path latency must be a non-negative number")
        return v


class SliceResources(BaseModel):
    """Resources allocated to a network slice."""
    bandwidth: int  # in Mbps
    switches: List[str] = Field(default_factory=list)
    paths: List[Path] = Field(default_factory=list)
    cpu_allocation: Optional[float] = None  # percentage
    memory_allocation: Optional[int] = None  # in MB

    @validator('bandwidth')
    def validate_bandwidth(cls, v):
        """Validate bandwidth allocation."""
        if not isinstance(v, int) or v <= 0:
            raise ValueError("Bandwidth must be a positive integer")
        if v > 100000:  # 100 Gbps max
            raise ValueError("Bandwidth allocation cannot exceed 100000 Mbps")
        return v

    @validator('cpu_allocation')
    def validate_cpu_allocation(cls, v):
        """Validate CPU allocation percentage."""
        if v is not None:
            if not isinstance(v, (int, float)) or v < 0 or v > 100:
                raise ValueError("CPU allocation must be between 0 and 100 percent")
        return v

    @validator('memory_allocation')
    def validate_memory_allocation(cls, v):
        """Validate memory allocation."""
        if v is not None:
            if not isinstance(v, int) or v <= 0:
                raise ValueError("Memory allocation must be a positive integer")
            if v > 1024000:  # 1TB max
                raise ValueError("Memory allocation cannot exceed 1024000 MB")
        return v

    def get_total_allocated_resources(self) -> Dict[str, Any]:
        """Get summary of all allocated resources."""
        return {
            "bandwidth_mbps": self.bandwidth,
            "switch_count": len(self.switches),
            "path_count": len(self.paths),
            "cpu_percentage": self.cpu_allocation,
            "memory_mb": self.memory_allocation,
            "total_path_bandwidth": sum(path.bandwidth or 0 for path in self.paths)
        }

    def check_resource_conflicts(self, other_resources: 'SliceResources') -> List[str]:
        """Check for resource conflicts with another slice."""
        conflicts = []
        
        # Check switch conflicts
        common_switches = set(self.switches) & set(other_resources.switches)
        if common_switches:
            conflicts.append(f"Shared switches: {common_switches}")
        
        # Check path conflicts (simplified - checking if paths share switches)
        self_path_switches = set()
        for path in self.paths:
            self_path_switches.update(path.switches)
        
        other_path_switches = set()
        for path in other_resources.paths:
            other_path_switches.update(path.switches)
        
        common_path_switches = self_path_switches & other_path_switches
        if common_path_switches:
            conflicts.append(f"Paths share switches: {common_path_switches}")
        
        return conflicts


class Policy(BaseModel):
    """Network policy definition."""
    id: str
    name: str
    type: str  # "qos", "security", "routing", etc.
    rules: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 1000

    @validator('id')
    def validate_id(cls, v):
        """Validate policy ID format."""
        if not v or not isinstance(v, str):
            raise ValueError("Policy ID must be a non-empty string")
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Policy ID must contain only alphanumeric characters, underscores, and hyphens")
        return v

    @validator('name')
    def validate_name(cls, v):
        """Validate policy name."""
        if not v or not isinstance(v, str):
            raise ValueError("Policy name must be a non-empty string")
        if len(v.strip()) == 0:
            raise ValueError("Policy name cannot be empty or only whitespace")
        return v.strip()

    @validator('type')
    def validate_type(cls, v):
        """Validate policy type."""
        valid_types = ['qos', 'security', 'routing', 'access_control', 'traffic_shaping', 'monitoring']
        if v not in valid_types:
            raise ValueError(f"Policy type must be one of: {', '.join(valid_types)}")
        return v

    @validator('priority')
    def validate_priority(cls, v):
        """Validate policy priority."""
        if not isinstance(v, int) or v < 0 or v > 65535:
            raise ValueError("Policy priority must be an integer between 0 and 65535")
        return v


class ServiceLevelAgreement(BaseModel):
    """SLA definition for network slice."""
    id: str
    min_bandwidth: int  # in Mbps
    max_latency: float  # in ms
    availability: float = Field(ge=0.0, le=100.0)  # percentage
    packet_loss_threshold: float = Field(ge=0.0, le=100.0)  # percentage

    @validator('id')
    def validate_id(cls, v):
        """Validate SLA ID format."""
        if not v or not isinstance(v, str):
            raise ValueError("SLA ID must be a non-empty string")
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("SLA ID must contain only alphanumeric characters, underscores, and hyphens")
        return v

    @validator('min_bandwidth')
    def validate_min_bandwidth(cls, v):
        """Validate minimum bandwidth requirement."""
        if not isinstance(v, int) or v <= 0:
            raise ValueError("Minimum bandwidth must be a positive integer")
        return v

    @validator('max_latency')
    def validate_max_latency(cls, v):
        """Validate maximum latency requirement."""
        if not isinstance(v, (int, float)) or v <= 0:
            raise ValueError("Maximum latency must be a positive number")
        if v > 10000:  # 10 seconds max
            raise ValueError("Maximum latency cannot exceed 10000 ms")
        return v

    def check_compliance(self, current_metrics: Dict[str, float]) -> Dict[str, Any]:
        """Check if current metrics comply with SLA."""
        violations = []
        warnings = []
        
        # Check bandwidth
        if 'bandwidth' in current_metrics:
            if current_metrics['bandwidth'] < self.min_bandwidth:
                violations.append(f"Bandwidth {current_metrics['bandwidth']} Mbps below minimum {self.min_bandwidth} Mbps")
        
        # Check latency
        if 'latency' in current_metrics:
            if current_metrics['latency'] > self.max_latency:
                violations.append(f"Latency {current_metrics['latency']} ms exceeds maximum {self.max_latency} ms")
        
        # Check availability
        if 'availability' in current_metrics:
            if current_metrics['availability'] < self.availability:
                violations.append(f"Availability {current_metrics['availability']}% below required {self.availability}%")
        
        # Check packet loss
        if 'packet_loss' in current_metrics:
            if current_metrics['packet_loss'] > self.packet_loss_threshold:
                violations.append(f"Packet loss {current_metrics['packet_loss']}% exceeds threshold {self.packet_loss_threshold}%")
        
        return {
            "is_compliant": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "sla_id": self.id
        }


class NetworkSlice(BaseModel):
    """Network slice representation."""
    id: str
    name: str
    resources: SliceResources
    policies: List[Policy] = Field(default_factory=list)
    sla: Optional[ServiceLevelAgreement] = None
    status: SliceStatus = SliceStatus.CONFIGURING
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    tenant_id: Optional[str] = None

    @validator('id')
    def validate_id(cls, v):
        """Validate slice ID format."""
        if not v or not isinstance(v, str):
            raise ValueError("Slice ID must be a non-empty string")
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Slice ID must contain only alphanumeric characters, underscores, and hyphens")
        return v

    @validator('name')
    def validate_name(cls, v):
        """Validate slice name."""
        if not v or not isinstance(v, str):
            raise ValueError("Slice name must be a non-empty string")
        if len(v.strip()) == 0:
            raise ValueError("Slice name cannot be empty or only whitespace")
        if len(v) > 100:
            raise ValueError("Slice name cannot exceed 100 characters")
        return v.strip()

    @validator('tenant_id')
    def validate_tenant_id(cls, v):
        """Validate tenant ID format."""
        if v is not None:
            if not isinstance(v, str) or len(v.strip()) == 0:
                raise ValueError("Tenant ID must be a non-empty string")
            if not re.match(r'^[a-zA-Z0-9_@.-]+$', v):
                raise ValueError("Tenant ID contains invalid characters")
        return v

    def validate_slice_integrity(self) -> Dict[str, Any]:
        """Validate network slice integrity and configuration."""
        issues = []
        warnings = []
        
        # Check resource allocation consistency
        if self.sla:
            if self.resources.bandwidth < self.sla.min_bandwidth:
                issues.append(f"Allocated bandwidth {self.resources.bandwidth} Mbps is less than SLA minimum {self.sla.min_bandwidth} Mbps")
        
        # Check policy consistency
        policy_types = [policy.type for policy in self.policies]
        if len(policy_types) != len(set(policy_types)):
            warnings.append("Multiple policies of the same type detected")
        
        # Check status consistency
        if self.status == SliceStatus.ACTIVE:
            if not self.resources.switches:
                issues.append("Active slice must have allocated switches")
            if not self.resources.paths:
                warnings.append("Active slice has no defined paths")
        
        # Check timestamp consistency
        if self.created_at and self.updated_at:
            try:
                created = datetime.fromisoformat(self.created_at.replace('Z', '+00:00'))
                updated = datetime.fromisoformat(self.updated_at.replace('Z', '+00:00'))
                if updated < created:
                    issues.append("Updated timestamp is before created timestamp")
            except ValueError:
                warnings.append("Invalid timestamp format")
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "resource_summary": self.resources.get_total_allocated_resources(),
            "policy_count": len(self.policies),
            "has_sla": self.sla is not None
        }

    def update_status(self, new_status: SliceStatus, timestamp: Optional[str] = None) -> None:
        """Update slice status with timestamp."""
        self.status = new_status
        self.updated_at = timestamp or datetime.now().isoformat()

    def add_policy(self, policy: Policy) -> bool:
        """Add a policy to the slice, checking for conflicts."""
        # Check for existing policy of same type
        existing_types = [p.type for p in self.policies]
        if policy.type in existing_types:
            return False  # Policy type already exists
        
        self.policies.append(policy)
        self.updated_at = datetime.now().isoformat()
        return True

    def remove_policy(self, policy_id: str) -> bool:
        """Remove a policy from the slice."""
        original_count = len(self.policies)
        self.policies = [p for p in self.policies if p.id != policy_id]
        
        if len(self.policies) < original_count:
            self.updated_at = datetime.now().isoformat()
            return True
        return False

    def get_resource_utilization_summary(self) -> Dict[str, Any]:
        """Get summary of resource utilization for monitoring."""
        return {
            "slice_id": self.id,
            "slice_name": self.name,
            "status": self.status.value,
            "resources": self.resources.get_total_allocated_resources(),
            "sla_requirements": {
                "min_bandwidth": self.sla.min_bandwidth if self.sla else None,
                "max_latency": self.sla.max_latency if self.sla else None,
                "availability": self.sla.availability if self.sla else None
            } if self.sla else None,
            "policy_count": len(self.policies),
            "tenant": self.tenant_id
        }

    def can_accommodate_request(self, bandwidth_required: int, latency_required: float) -> bool:
        """Check if slice can accommodate a new service request."""
        if self.status != SliceStatus.ACTIVE:
            return False
        
        # Check bandwidth availability (simplified - assumes some headroom)
        available_bandwidth = self.resources.bandwidth * 0.8  # 80% utilization max
        if bandwidth_required > available_bandwidth:
            return False
        
        # Check latency requirements against SLA
        if self.sla and latency_required > self.sla.max_latency:
            return False
        
        return True