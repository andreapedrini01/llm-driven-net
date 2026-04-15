"""
Minimal Action Models - Essential data structures for network actions
"""

from enum import Enum
from typing import Any, Dict, Optional
from dataclasses import dataclass
import re


class ActionType(str, Enum):
    """Types of network actions."""
    FLOW_MOD = "flow_mod"
    SLICE_CREATE = "slice_create"
    SLICE_MODIFY = "slice_modify"
    SLICE_DELETE = "slice_delete"
    LOAD_BALANCE = "load_balance"
    CONFIG_CHANGE = "config_change"


@dataclass
class NetworkAction:
    """Network action data structure."""
    id: str
    type: ActionType
    target: str
    parameters: Dict[str, Any]
    priority: int = 1000
    timeout: int = 30
    description: Optional[str] = None
    
    def __post_init__(self):
        """Validate fields after initialization."""
        if not self.id or not isinstance(self.id, str):
            raise ValueError("Action ID must be a non-empty string")
        if not re.match(r'^[a-zA-Z0-9_-]+$', self.id):
            raise ValueError("Action ID must contain only alphanumeric characters, underscores, and hyphens")
        
        if not self.target or not isinstance(self.target, str):
            raise ValueError("Target must be a non-empty string")
        
        if not isinstance(self.priority, int) or self.priority < 0 or self.priority > 65535:
            raise ValueError("Priority must be an integer between 0 and 65535")
        
        if not isinstance(self.timeout, int) or self.timeout < 1:
            raise ValueError("Timeout must be a positive integer")
        
        # Convert string to ActionType if needed
        if isinstance(self.type, str):
            self.type = ActionType(self.type)
    
    def validate_action_parameters(self) -> Dict[str, Any]:
        """Validate action parameters based on action type."""
        issues = []
        warnings = []
        
        if self.type == ActionType.FLOW_MOD:
            if 'match' not in self.parameters:
                issues.append("Flow modification requires 'match' parameters")
            if 'actions' not in self.parameters:
                issues.append("Flow modification requires 'actions' parameters")
        
        elif self.type == ActionType.SLICE_CREATE:
            required_fields = ['slice_name', 'resources']
            for field in required_fields:
                if field not in self.parameters:
                    issues.append(f"Slice creation requires '{field}' parameter")
        
        elif self.type in (ActionType.SLICE_MODIFY, ActionType.SLICE_DELETE, ActionType.LOAD_BALANCE):
            pass  # Flexible parameters, validated at execution time
        
        elif self.type == ActionType.CONFIG_CHANGE:
            if 'config_type' not in self.parameters:
                issues.append("Configuration change requires 'config_type' parameter")
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings
        }
