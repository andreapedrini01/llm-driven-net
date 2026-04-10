"""Action-related data models."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator
import json
import re


class ActionType(str, Enum):
    """Types of network actions."""
    FLOW_MOD = "flow_mod"
    SLICE_CREATE = "slice_create"
    SLICE_MODIFY = "slice_modify"
    CONFIG_CHANGE = "config_change"


class NetworkAction(BaseModel):
    """Individual network action."""
    id: str
    type: ActionType
    target: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 1000
    timeout: int = 30
    description: Optional[str] = None

    @validator('id')
    def validate_id(cls, v):
        """Validate action ID format."""
        if not v or not isinstance(v, str):
            raise ValueError("Action ID must be a non-empty string")
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Action ID must contain only alphanumeric characters, underscores, and hyphens")
        return v

    @validator('target')
    def validate_target(cls, v):
        """Validate target format."""
        if not v or not isinstance(v, str):
            raise ValueError("Target must be a non-empty string")
        # Allow various target formats: switch-1, 192.168.1.1, switch:port, etc.
        if not re.match(r'^[a-zA-Z0-9._:-]+$', v):
            raise ValueError("Target contains invalid characters")
        return v

    @validator('priority')
    def validate_priority(cls, v):
        """Validate priority range."""
        if not isinstance(v, int) or v < 0 or v > 65535:
            raise ValueError("Priority must be an integer between 0 and 65535")
        return v

    @validator('timeout', pre=True)
    def validate_timeout(cls, v):
        """Validate timeout value. Coerces 0 or missing to default (30s)."""
        if v is None or v == 0:
            return 30  # default timeout
        if not isinstance(v, int):
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise ValueError("Timeout must be an integer between 1 and 3600 seconds")
        if v < 0 or v > 3600:
            raise ValueError("Timeout must be an integer between 1 and 3600 seconds")
        return v

    def validate_action_parameters(self) -> Dict[str, Any]:
        """Validate action parameters based on action type."""
        issues = []
        warnings = []
        
        if self.type == ActionType.FLOW_MOD:
            # Validate flow modification parameters
            if 'match' not in self.parameters:
                issues.append("Flow modification requires 'match' parameters")
            if 'actions' not in self.parameters:
                issues.append("Flow modification requires 'actions' parameters")
            
            # Check for valid match fields
            if 'match' in self.parameters:
                valid_match_fields = ['in_port', 'eth_src', 'eth_dst', 'eth_type', 'ip_src', 'ip_dst', 'tcp_src', 'tcp_dst']
                for field in self.parameters['match']:
                    if field not in valid_match_fields:
                        warnings.append(f"Unknown match field: {field}")
        
        elif self.type == ActionType.SLICE_CREATE:
            # Validate slice creation parameters
            required_fields = ['slice_name', 'resources']
            for field in required_fields:
                if field not in self.parameters:
                    issues.append(f"Slice creation requires '{field}' parameter")
        
        elif self.type == ActionType.CONFIG_CHANGE:
            # Validate configuration change parameters
            if 'config_type' not in self.parameters:
                issues.append("Configuration change requires 'config_type' parameter")
            if 'config_data' not in self.parameters:
                issues.append("Configuration change requires 'config_data' parameter")
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings
        }

    def to_northbound_format(self) -> Dict[str, Any]:
        """Convert action to Northbound Script compatible format."""
        return {
            "action_id": self.id,
            "action_type": self.type.value,
            "target_resource": self.target,
            "parameters": self.parameters,
            "execution_priority": self.priority,
            "timeout_seconds": self.timeout,
            "description": self.description or f"{self.type.value} on {self.target}"
        }

    def estimate_execution_time(self) -> int:
        """Estimate execution time in seconds based on action type."""
        base_times = {
            ActionType.FLOW_MOD: 2,
            ActionType.SLICE_CREATE: 30,
            ActionType.SLICE_MODIFY: 15,
            ActionType.CONFIG_CHANGE: 10
        }
        
        base_time = base_times.get(self.type, 5)
        
        # Adjust based on complexity
        if self.type == ActionType.FLOW_MOD and 'actions' in self.parameters:
            base_time += len(self.parameters['actions']) * 1
        
        return min(base_time, self.timeout)


class ActionSequence(BaseModel):
    """Sequence of network actions to be executed."""
    id: str
    intent_id: str
    actions: List[NetworkAction] = Field(default_factory=list)
    estimated_duration: int  # in seconds
    dependencies: List[str] = Field(default_factory=list)
    rollback_plan: List[NetworkAction] = Field(default_factory=list)

    @validator('id')
    def validate_id(cls, v):
        """Validate sequence ID format."""
        if not v or not isinstance(v, str):
            raise ValueError("Sequence ID must be a non-empty string")
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Sequence ID must contain only alphanumeric characters, underscores, and hyphens")
        return v

    @validator('intent_id')
    def validate_intent_id(cls, v):
        """Validate intent ID format."""
        if not v or not isinstance(v, str):
            raise ValueError("Intent ID must be a non-empty string")
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Intent ID must contain only alphanumeric characters, underscores, and hyphens")
        return v

    @validator('estimated_duration')
    def validate_estimated_duration(cls, v):
        """Validate estimated duration."""
        if not isinstance(v, int) or v < 0:
            raise ValueError("Estimated duration must be a non-negative integer")
        if v > 7200:  # 2 hours max
            raise ValueError("Estimated duration cannot exceed 7200 seconds (2 hours)")
        return v

    @validator('actions')
    def validate_actions(cls, v):
        """Validate actions list."""
        if not isinstance(v, list):
            raise ValueError("Actions must be a list")
        
        # Check for duplicate action IDs
        action_ids = [action.id for action in v]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("Duplicate action IDs are not allowed")
        
        return v

    @validator('dependencies')
    def validate_dependencies(cls, v):
        """Validate dependencies list."""
        if not isinstance(v, list):
            raise ValueError("Dependencies must be a list")
        
        # Check for valid dependency format
        for dep in v:
            if not isinstance(dep, str) or not re.match(r'^[a-zA-Z0-9_-]+$', dep):
                raise ValueError(f"Invalid dependency format: {dep}")
        
        return v

    def validate_sequence_integrity(self) -> Dict[str, Any]:
        """Validate action sequence integrity and dependencies."""
        issues = []
        warnings = []
        
        # Check action dependencies within sequence
        action_ids = {action.id for action in self.actions}
        for dep in self.dependencies:
            if dep in action_ids:
                warnings.append(f"Dependency '{dep}' is also an action in this sequence")
        
        # Check for conflicting actions
        targets = {}
        for action in self.actions:
            if action.target in targets:
                if targets[action.target].type != action.type:
                    warnings.append(f"Multiple different action types on target {action.target}")
            targets[action.target] = action
        
        # Validate rollback plan
        if self.rollback_plan:
            rollback_targets = {action.target for action in self.rollback_plan}
            action_targets = {action.target for action in self.actions}
            
            # Rollback should cover all modified targets
            uncovered_targets = action_targets - rollback_targets
            if uncovered_targets:
                warnings.append(f"Rollback plan doesn't cover targets: {uncovered_targets}")
        
        # Check estimated duration vs actual action times
        actual_duration = sum(action.estimate_execution_time() for action in self.actions)
        if abs(self.estimated_duration - actual_duration) > actual_duration * 0.5:
            warnings.append("Estimated duration significantly differs from sum of action times")
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "action_count": len(self.actions),
            "unique_targets": len(targets),
            "has_rollback": len(self.rollback_plan) > 0
        }

    def to_northbound_format(self) -> Dict[str, Any]:
        """Convert sequence to Northbound Script compatible format."""
        return {
            "sequence_id": self.id,
            "source_intent": self.intent_id,
            "actions": [action.to_northbound_format() for action in self.actions],
            "execution_metadata": {
                "estimated_duration_seconds": self.estimated_duration,
                "dependencies": self.dependencies,
                "total_actions": len(self.actions)
            },
            "rollback_actions": [action.to_northbound_format() for action in self.rollback_plan] if self.rollback_plan else []
        }

    def get_execution_order(self) -> List[NetworkAction]:
        """Get actions in optimal execution order based on dependencies and priorities."""
        # Sort by priority (higher priority first), then by estimated execution time
        return sorted(self.actions, key=lambda x: (-x.priority, x.estimate_execution_time()))

    def add_dependency_tracking(self, dependency_map: Dict[str, List[str]]) -> None:
        """Add dependency tracking between actions in the sequence."""
        for action in self.actions:
            if action.id in dependency_map:
                # Add dependencies that are not already in the sequence dependencies
                for dep in dependency_map[action.id]:
                    if dep not in self.dependencies:
                        self.dependencies.append(dep)


class ValidationResult(BaseModel):
    """Result of action validation."""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


class SafetyReport(BaseModel):
    """Safety assessment of actions."""
    is_safe: bool
    risk_level: str  # "low", "medium", "high", "critical"
    potential_impacts: List[str] = Field(default_factory=list)
    mitigation_strategies: List[str] = Field(default_factory=list)


class SimulationResult(BaseModel):
    """Result of action simulation."""
    success: bool
    predicted_outcomes: Dict[str, Any] = Field(default_factory=dict)
    performance_impact: Dict[str, float] = Field(default_factory=dict)
    resource_changes: Dict[str, Any] = Field(default_factory=dict)


class ImpactAssessment(BaseModel):
    """Assessment of action impact on network."""
    affected_resources: List[str] = Field(default_factory=list)
    performance_impact: Dict[str, float] = Field(default_factory=dict)
    service_disruption_risk: str  # "none", "minimal", "moderate", "high"
    estimated_recovery_time: int  # in seconds