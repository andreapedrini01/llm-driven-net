"""Confidence criteria data models for criteria-enriched ChatGPT prompts."""

from typing import Any, Dict, List
from pydantic import BaseModel, Field, validator


class ConfidenceCriteriaBreakdown(BaseModel):
    """Breakdown of confidence scoring factors."""
    base_confidence: float = Field(ge=0.0, le=1.0)
    entity_boost: float = Field(ge=0.0, le=1.0)
    type_boost: float = Field(ge=0.0, le=1.0)
    token_boost: float = Field(ge=0.0, le=1.0)
    quality_boost: float = Field(ge=0.0, le=1.0)
    penalties: float = Field(ge=0.0, le=1.0)
    final_score: float = Field(ge=0.0, le=1.0)
    entities_detail: List[Dict[str, Any]] = Field(default_factory=list)
    intent_type_detail: Dict[str, Any] = Field(default_factory=dict)

    @validator('final_score')
    def validate_final_score(cls, v, values):
        """Validate final_score equals sum of contributions minus penalties, clamped."""
        contributions = (
            values.get('base_confidence', 0)
            + values.get('entity_boost', 0)
            + values.get('type_boost', 0)
            + values.get('token_boost', 0)
            + values.get('quality_boost', 0)
        )
        expected = max(0.1, min(1.0, contributions - values.get('penalties', 0)))
        if abs(v - expected) > 0.01:
            raise ValueError(
                f"final_score {v} does not match computed value {expected}"
            )
        return v


class ParameterSuggestion(BaseModel):
    """A suggestion from ChatGPT for improving confidence."""
    target_factor: str
    suggested_parameter: str
    suggested_value: str
    estimated_improvement: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""


class ConfidenceModification(BaseModel):
    """A recommended modification to the IntentObject."""
    target_field: str  # "entities", "parameters", or "raw_text"
    current_value: Any = None
    suggested_value: Any = None
    estimated_new_score: float = Field(ge=0.0, le=1.0)
    source_suggestion: ParameterSuggestion
