# Implementation Plan: Confidence Criteria Prompt

## Overview

Enrich the ChatGPT fallback prompt with confidence criteria breakdown from IntentParser, enabling ChatGPT to return targeted parameter suggestions that map back to actionable intent modifications. Implementation proceeds bottom-up: data models → IntentParser → PromptEngineeringSystem → ActionSequencer → ConfidenceCriteriaExtractor → main pipeline integration.

## Tasks

- [x] 1. Create confidence data models
  - [x] 1.1 Create `src/models/confidence.py` with `ConfidenceCriteriaBreakdown`, `ParameterSuggestion`, and `ConfidenceModification` Pydantic models
    - `ConfidenceCriteriaBreakdown`: fields `base_confidence`, `entity_boost`, `type_boost`, `token_boost`, `quality_boost`, `penalties`, `final_score` (all float 0.0–1.0), `entities_detail` (list), `intent_type_detail` (dict)
    - Add `@validator('final_score')` that checks `final_score == max(0.1, min(1.0, sum_of_contributions - penalties))` within tolerance 0.01
    - `ParameterSuggestion`: fields `target_factor` (str), `suggested_parameter` (str), `suggested_value` (str), `estimated_improvement` (float 0.0–1.0), `reasoning` (str)
    - `ConfidenceModification`: fields `target_field` (str), `current_value` (Any), `suggested_value` (Any), `estimated_new_score` (float 0.0–1.0), `source_suggestion` (ParameterSuggestion)
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 1.2 Write property test for ConfidenceCriteriaBreakdown validation constraint
    - **Property 7: ConfidenceCriteriaBreakdown validation constraint**
    - Generate random floats in [0.0, 1.0] for each factor; verify construction succeeds only when `final_score` matches `max(0.1, min(1.0, sum - penalties))` within 0.01 tolerance, and raises `ValidationError` otherwise
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4**

- [x] 2. Add `get_confidence_breakdown` to IntentParser
  - [x] 2.1 Implement `get_confidence_breakdown(self, intent_obj: IntentObject) -> ConfidenceCriteriaBreakdown` in `src/services/intent_parser.py`
    - Re-run the same logic as `_calculate_confidence_enhanced` but capture individual factor values (`base_confidence`, `entity_boost`, `type_boost`, `token_boost`, `quality_boost`, `penalties`)
    - Build `entities_detail` list from `intent_obj.entities` (each entry: `{"name": ..., "type": ..., "confidence": ...}`)
    - Build `intent_type_detail` dict with `type` and `confidence` from `_classify_intent_type_enhanced`
    - Return a `ConfidenceCriteriaBreakdown` instance
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ]* 2.2 Write property test for breakdown completeness
    - **Property 1: Breakdown completeness**
    - For any valid intent text, `get_confidence_breakdown` returns a `ConfidenceCriteriaBreakdown` with all float fields present and in [0.0, 1.0]
    - **Validates: Requirements 1.1, 1.2**

  - [ ]* 2.3 Write property test for breakdown detail consistency
    - **Property 2: Breakdown detail consistency**
    - For any intent producing at least one entity, `entities_detail` length matches `IntentObject.entities` length with correct keys; `intent_type_detail` contains matching `type` and `confidence`
    - **Validates: Requirements 1.3, 1.4**

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Add CONFIDENCE_ENRICHED prompt template
  - [x] 4.1 Add `CONFIDENCE_ENRICHED = "confidence_enriched"` to `PromptType` enum in `src/services/prompt_engineering.py`
    - _Requirements: 7.1_

  - [x] 4.2 Register the `CONFIDENCE_ENRICHED` template in `_initialize_templates()` in `src/services/prompt_engineering.py`
    - System message: instruct ChatGPT to act as an SDN expert that understands confidence scoring and to prioritize returning structured parameter suggestions aligned with the provided criteria
    - User template with placeholders: `{intent_text}`, `{network_state_summary}`, `{confidence_criteria_breakdown}`, `{response_schema}`
    - Template must describe each confidence factor with its current value and maximum possible contribution
    - Response schema must include both `actions` array and `parameter_suggestions` array (each suggestion: `target_factor`, `suggested_parameter`, `suggested_value`, `estimated_improvement`, `reasoning`)
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 4.3 Implement `build_confidence_enriched_prompt(self, intent, breakdown, network_state)` method in `PromptEngineeringSystem`
    - Accept `IntentObject`, `ConfidenceCriteriaBreakdown`, and `NetworkState`
    - Format the breakdown into a human-readable string showing each factor name and numeric value
    - Return `Tuple[str, str, Dict[str, Any]]` (system_message, user_prompt, config)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 4.4 Write property test for enriched prompt containing all criteria factors
    - **Property 3: Enriched prompt contains all criteria factors**
    - For any `ConfidenceCriteriaBreakdown`, the prompt string contains string representations of all six factor names and their numeric values
    - **Validates: Requirements 2.1, 2.2**

- [x] 5. Add `parse_actions_and_suggestions` to ActionSequencer
  - [x] 5.1 Implement `parse_actions_and_suggestions(self, response_content: str) -> Tuple[List[NetworkAction], List[ParameterSuggestion]]` in `src/services/action_sequencer.py`
    - Reuse existing JSON extraction logic from `parse_actions_from_response`
    - Parse `actions` array into `NetworkAction` objects
    - Parse `parameter_suggestions` array into `ParameterSuggestion` objects, validating `target_factor` against known factors
    - If `parameter_suggestions` is missing or malformed, log a warning and return `(actions, [])`
    - If entire response is invalid JSON, return `([], [])`
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ]* 5.2 Write property test for actions and suggestions parsing round-trip
    - **Property 4: Actions and suggestions parsing round-trip**
    - For any valid JSON with `actions` and `parameter_suggestions` arrays, parsed output list lengths match input array lengths
    - **Validates: Requirements 3.1, 3.4**

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Create ConfidenceCriteriaExtractor service
  - [x] 7.1 Create `src/services/confidence_criteria_extractor.py` with `ConfidenceCriteriaExtractor` class
    - Define `VALID_FACTORS = {"base_confidence", "entity_boost", "type_boost", "token_boost", "quality_boost"}`
    - Implement `extract_modifications(self, breakdown: ConfidenceCriteriaBreakdown, suggestions: List[ParameterSuggestion]) -> List[ConfidenceModification]`
    - For each suggestion: if `target_factor` is in `VALID_FACTORS`, produce a `ConfidenceModification`; otherwise discard and log warning
    - Map `entity_boost` → `target_field="entities"`, `type_boost` → `target_field="parameters"`, others → `target_field="raw_text"`
    - Estimate `estimated_new_score` from breakdown values and suggestion's `estimated_improvement`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 7.2 Write property test for suggestion factor validation and filtering
    - **Property 5: Suggestion factor validation and filtering**
    - Valid `target_factor` values produce a `ConfidenceModification`; unknown factors produce no modification
    - **Validates: Requirements 3.2, 4.5**

  - [ ]* 7.3 Write property test for factor-to-field mapping
    - **Property 6: Factor-to-field mapping**
    - `target_factor="entity_boost"` → `target_field="entities"`; `target_factor="type_boost"` → `target_field="parameters"`
    - **Validates: Requirements 4.3, 4.4**

- [x] 8. Integrate criteria-enriched flow into main pipeline
  - [x] 8.1 Modify the `not use_rule_based` branch in `main.py` to use the criteria-enriched prompt
    - Import `ConfidenceCriteriaBreakdown`, `ParameterSuggestion`, `ConfidenceModification` from `src.models.confidence`
    - Import `ConfidenceCriteriaExtractor` from `src.services.confidence_criteria_extractor`
    - Instantiate `ConfidenceCriteriaExtractor` alongside other services in `main()`
    - In the ChatGPT fallback branch: call `intent_parser.get_confidence_breakdown(intent_obj)` to get breakdown
    - Call `prompt_system.build_confidence_enriched_prompt(intent_obj, breakdown, network_state)` to build the enriched prompt
    - After receiving ChatGPT response, call `action_sequencer.parse_actions_and_suggestions(response.content)` instead of `parse_actions_from_response`
    - If suggestions are present, call `extractor.extract_modifications(breakdown, suggestions)` and log the modifications
    - Log the breakdown sent and suggestions received for observability
    - Continue executing actions from the `actions` array as before (backward compatible)
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties using Hypothesis
- Unit tests validate specific examples and edge cases
- The design uses Python throughout — all code examples and implementations use Python
