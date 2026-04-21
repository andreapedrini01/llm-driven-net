"""Intent-related data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator
import re


class IntentType(str, Enum):
    """Types of network intents."""
    CONFIGURATION = "configuration"
    QUERY = "query"
    ANOMALY_RESPONSE = "anomaly_response"


class Entity(BaseModel):
    """Extracted entity from natural language intent."""
    name: str
    type: str
    value: str
    confidence: float = Field(ge=0.0, le=1.0)

    @validator('name')
    def validate_name(cls, v):
        """Validate entity name."""
        if not v or not isinstance(v, str):
            raise ValueError("Entity name must be a non-empty string")
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Entity name must contain only alphanumeric characters, underscores, and hyphens")
        return v

    @validator('type')
    def validate_type(cls, v):
        """Validate entity type."""
        valid_types = ['resource', 'action', 'target', 'parameter', 'identifier', 'value', 'condition']
        if v not in valid_types:
            raise ValueError(f"Entity type must be one of: {', '.join(valid_types)}")
        return v

    @validator('value')
    def validate_value(cls, v):
        """Validate entity value."""
        if not isinstance(v, str):
            raise ValueError("Entity value must be a string")
        if len(v.strip()) == 0:
            raise ValueError("Entity value cannot be empty or only whitespace")
        return v.strip()


class IntentObject(BaseModel):
    """Structured representation of a network intent."""
    id: str
    raw_text: str
    timestamp: datetime
    user_id: str
    entities: List[Entity] = Field(default_factory=list)
    intent_type: IntentType
    confidence: float = Field(ge=0.0, le=1.0)
    parameters: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    @validator('id')
    def validate_id(cls, v):
        """Validate intent ID format."""
        if not v or not isinstance(v, str):
            raise ValueError("Intent ID must be a non-empty string")
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Intent ID must contain only alphanumeric characters, underscores, and hyphens")
        return v

    @validator('raw_text')
    def validate_raw_text(cls, v):
        """Validate raw text input."""
        if not v or not isinstance(v, str):
            raise ValueError("Raw text must be a non-empty string")
        if len(v.strip()) == 0:
            raise ValueError("Raw text cannot be empty or only whitespace")
        if len(v) > 10000:  # Reasonable limit for intent text
            raise ValueError("Raw text cannot exceed 10000 characters")
        return v.strip()

    @validator('user_id')
    def validate_user_id(cls, v):
        """Validate user ID format."""
        if not v or not isinstance(v, str):
            raise ValueError("User ID must be a non-empty string")
        if not re.match(r'^[a-zA-Z0-9_@.-]+$', v):
            raise ValueError("User ID contains invalid characters")
        return v

    @validator('entities')
    def validate_entities(cls, v):
        """Validate entities list."""
        if not isinstance(v, list):
            raise ValueError("Entities must be a list")
        # Check for duplicate entity names
        entity_names = [entity.name for entity in v]
        if len(entity_names) != len(set(entity_names)):
            raise ValueError("Duplicate entity names are not allowed")
        return v

    def validate_data_integrity(self) -> Dict[str, Any]:
        """Validate data integrity and return validation report."""
        issues = []
        warnings = []
        
        # Check confidence score consistency with entities
        if self.entities:
            avg_entity_confidence = sum(e.confidence for e in self.entities) / len(self.entities)
            if abs(self.confidence - avg_entity_confidence) > 0.3:
                warnings.append("Intent confidence significantly differs from average entity confidence")
        
        # Check if intent type matches extracted entities
        if self.intent_type == IntentType.CONFIGURATION:
            config_entities = [e for e in self.entities if e.type in ['resource', 'action', 'target']]
            if not config_entities:
                warnings.append("Configuration intent has no configuration-related entities")
        
        # Check parameter consistency
        entity_values = {e.name: e.value for e in self.entities}
        for param_key, param_value in self.parameters.items():
            if param_key in entity_values and str(param_value) != str(entity_values[param_key]):
                issues.append(f"Parameter '{param_key}' value conflicts with entity value")
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "entity_count": len(self.entities),
            "confidence_score": self.confidence
        }


class ContextualizedIntent(BaseModel):
    """Intent enriched with network context information."""
    intent: IntentObject
    relevant_resources: List[str] = Field(default_factory=list)
    network_context: Dict[str, Any] = Field(default_factory=dict)
    conflicts: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)