"""Confidence Criteria Extractor service.

Maps ChatGPT parameter suggestions to actionable confidence modifications
that can be applied to the IntentObject to improve confidence scores.
"""

import logging
from typing import List

from llm_integration_module.models.confidence import (
    ConfidenceCriteriaBreakdown,
    ConfidenceModification,
    ParameterSuggestion,
)


logger = logging.getLogger(__name__)

# Mapping from target_factor to the IntentObject field it modifies
FACTOR_TO_FIELD = {
    "entity_boost": "entities",
    "type_boost": "parameters",
    "base_confidence": "raw_text",
    "token_boost": "raw_text",
    "quality_boost": "raw_text",
}


class ConfidenceCriteriaExtractor:
    """Maps ChatGPT parameter suggestions to actionable confidence modifications."""

    VALID_FACTORS = {
        "base_confidence",
        "entity_boost",
        "type_boost",
        "token_boost",
        "quality_boost",
    }

    def extract_modifications(
        self,
        breakdown: ConfidenceCriteriaBreakdown,
        suggestions: List[ParameterSuggestion],
    ) -> List[ConfidenceModification]:
        """Produce a list of recommended modifications from parameter suggestions.

        For each suggestion whose target_factor is in VALID_FACTORS, creates a
        ConfidenceModification with the appropriate target_field mapping.
        Suggestions targeting unknown factors are discarded with a warning.

        Args:
            breakdown: The current confidence criteria breakdown.
            suggestions: Parameter suggestions from ChatGPT.

        Returns:
            List of ConfidenceModification objects for valid suggestions.
        """
        modifications: List[ConfidenceModification] = []

        for suggestion in suggestions:
            if suggestion.target_factor not in self.VALID_FACTORS:
                logger.warning(
                    "Discarding suggestion with unknown target_factor '%s'",
                    suggestion.target_factor,
                )
                continue

            target_field = FACTOR_TO_FIELD[suggestion.target_factor]
            current_value = getattr(breakdown, suggestion.target_factor, 0.0)
            estimated_new_score = min(
                1.0,
                max(0.1, breakdown.final_score + suggestion.estimated_improvement),
            )

            modifications.append(
                ConfidenceModification(
                    target_field=target_field,
                    current_value=current_value,
                    suggested_value=suggestion.suggested_value,
                    estimated_new_score=estimated_new_score,
                    source_suggestion=suggestion,
                )
            )

        return modifications
