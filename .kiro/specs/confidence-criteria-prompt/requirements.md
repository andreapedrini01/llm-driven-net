# Requirements Document

## Introduction

When the IntentParser calculates a confidence score below the `RULE_BASED_CONFIDENCE_THRESHOLD` (0.8), the system falls back to ChatGPT for action generation. Currently, the ChatGPT prompt includes the intent text, network state, entities, and context, but does not include any information about the confidence scoring criteria. As a result, ChatGPT's response is not targeted enough to help the downstream algorithm extract the precise parameters needed to increase confidence.

This feature enriches the ChatGPT prompt with the confidence criteria used by `IntentParser._calculate_confidence_enhanced`, so that ChatGPT can return structured, criteria-aligned information that the system can use to extract and refine parameters, ultimately improving confidence on subsequent processing.

## Glossary

- **IntentParser**: The service (`llm_integration_module/services/intent_parser.py`) responsible for parsing natural language intents, extracting entities, classifying intent type, and calculating a confidence score.
- **Confidence_Score**: A float value between 0.0 and 1.0 representing how well the system understood the user's intent, computed by `IntentParser._calculate_confidence_enhanced`.
- **Confidence_Criteria**: The set of factors and their weights used to compute the Confidence_Score: base text structure score, entity confidence contribution, intent type confidence contribution, token quality boost, text quality bonuses, and penalties.
- **ChatGPT_Client**: The service (`llm_integration_module/services/chatgpt_client.py`) that sends prompts to the OpenAI API and returns responses.
- **Prompt_Engineering_System**: The service (`llm_integration_module/services/prompt_engineering.py`) that manages prompt templates, context injection, and response parsing for ChatGPT interactions.
- **Action_Sequencer**: The service (`llm_integration_module/services/action_sequencer.py`) that parses ChatGPT responses into `NetworkAction` objects and sequences them for execution.
- **Confidence_Criteria_Extractor**: A new component responsible for extracting parameter suggestions from ChatGPT's criteria-aware response and mapping them to confidence factors.
- **Criteria_Enriched_Prompt**: A ChatGPT prompt that includes the Confidence_Criteria breakdown alongside the intent and network context.
- **Parameter_Suggestion**: A structured object returned by ChatGPT describing a specific parameter or entity that, if clarified or added, would increase the Confidence_Score.

## Requirements

### Requirement 1: Extract Confidence Criteria from IntentParser

**User Story:** As a system developer, I want the confidence criteria and their current values to be extractable from the IntentParser, so that they can be included in the ChatGPT prompt.

#### Acceptance Criteria

1. THE IntentParser SHALL expose a method that returns the Confidence_Criteria breakdown as a structured dictionary containing: base_confidence, entity_boost, type_boost, token_boost, quality_boost, penalties, and the final Confidence_Score.
2. WHEN the IntentParser parses an intent, THE IntentParser SHALL compute and store the individual Confidence_Criteria factor values alongside the final Confidence_Score in the returned IntentObject.
3. THE IntentParser SHALL include in the Confidence_Criteria breakdown the list of detected entities with their individual confidence scores.
4. THE IntentParser SHALL include in the Confidence_Criteria breakdown the classified intent type and its classification confidence.

### Requirement 2: Build Criteria-Enriched Prompt

**User Story:** As a system developer, I want the ChatGPT prompt to include the confidence criteria and their current values, so that ChatGPT can provide targeted suggestions aligned with the scoring algorithm.

#### Acceptance Criteria

1. WHEN the Confidence_Score is below the RULE_BASED_CONFIDENCE_THRESHOLD, THE Prompt_Engineering_System SHALL build a Criteria_Enriched_Prompt that includes the Confidence_Criteria breakdown.
2. THE Criteria_Enriched_Prompt SHALL describe each confidence factor (base text structure, entity extraction, intent classification, token quality, text quality bonuses, penalties) with its current value and maximum possible contribution.
3. THE Criteria_Enriched_Prompt SHALL instruct ChatGPT to return, in addition to the actions array, a `parameter_suggestions` array where each entry contains: the target confidence factor, the suggested parameter or entity, and the estimated confidence improvement.
4. THE Criteria_Enriched_Prompt SHALL include the expected JSON response schema for the `parameter_suggestions` array so ChatGPT returns parseable output.

### Requirement 3: Parse Parameter Suggestions from ChatGPT Response

**User Story:** As a system developer, I want the system to parse parameter suggestions from ChatGPT's response, so that the algorithm can identify which parameters to modify to increase confidence.

#### Acceptance Criteria

1. WHEN ChatGPT returns a response to a Criteria_Enriched_Prompt, THE Action_Sequencer SHALL parse both the `actions` array and the `parameter_suggestions` array from the response.
2. THE Action_Sequencer SHALL validate each Parameter_Suggestion against the known Confidence_Criteria factors (base_confidence, entity_boost, type_boost, token_boost, quality_boost).
3. IF the `parameter_suggestions` array is missing or malformed, THEN THE Action_Sequencer SHALL log a warning and continue processing the `actions` array without parameter suggestions.
4. THE Action_Sequencer SHALL return the parsed Parameter_Suggestion list alongside the parsed NetworkAction list.

### Requirement 4: Confidence Criteria Extractor

**User Story:** As a system developer, I want a component that maps ChatGPT's parameter suggestions to actionable confidence improvements, so that the system can refine the intent and increase confidence.

#### Acceptance Criteria

1. THE Confidence_Criteria_Extractor SHALL accept the current Confidence_Criteria breakdown and a list of Parameter_Suggestion objects as input.
2. THE Confidence_Criteria_Extractor SHALL produce a list of recommended modifications, where each modification specifies: the target field in the IntentObject (entities, parameters, or raw_text), the suggested value, and the estimated Confidence_Score after applying the modification.
3. WHEN a Parameter_Suggestion targets the entity_boost factor, THE Confidence_Criteria_Extractor SHALL generate a modification that adds or updates an entity in the IntentObject.
4. WHEN a Parameter_Suggestion targets the type_boost factor, THE Confidence_Criteria_Extractor SHALL generate a modification that refines the intent type classification.
5. IF a Parameter_Suggestion references an unknown confidence factor, THEN THE Confidence_Criteria_Extractor SHALL discard the suggestion and log a warning.

### Requirement 5: Integrate Criteria-Enriched Flow into Main Pipeline

**User Story:** As a system developer, I want the main pipeline to use the criteria-enriched prompt when falling back to ChatGPT, so that the end-to-end flow benefits from targeted confidence improvement.

#### Acceptance Criteria

1. WHEN the Confidence_Score is below RULE_BASED_CONFIDENCE_THRESHOLD and the system falls back to ChatGPT, THE main pipeline SHALL use the Criteria_Enriched_Prompt instead of the current generic prompt.
2. WHEN ChatGPT returns parameter suggestions, THE main pipeline SHALL pass them to the Confidence_Criteria_Extractor and log the recommended modifications.
3. THE main pipeline SHALL preserve backward compatibility by continuing to generate and execute network actions from the `actions` array regardless of whether parameter suggestions are present.
4. THE main pipeline SHALL log the Confidence_Criteria breakdown sent to ChatGPT and the parameter suggestions received, for observability.

### Requirement 6: Confidence Criteria Data Model

**User Story:** As a system developer, I want structured data models for confidence criteria and parameter suggestions, so that the data flows cleanly between components.

#### Acceptance Criteria

1. THE system SHALL define a `ConfidenceCriteriaBreakdown` model containing fields: base_confidence (float), entity_boost (float), type_boost (float), token_boost (float), quality_boost (float), penalties (float), final_score (float), entities_detail (list), and intent_type_detail (dict).
2. THE system SHALL define a `ParameterSuggestion` model containing fields: target_factor (string), suggested_parameter (string), suggested_value (string), estimated_improvement (float), and reasoning (string).
3. THE system SHALL define a `ConfidenceModification` model containing fields: target_field (string), current_value (any), suggested_value (any), estimated_new_score (float), and source_suggestion (ParameterSuggestion).
4. THE ConfidenceCriteriaBreakdown model SHALL validate that all float fields are between 0.0 and 1.0 and that final_score equals the sum of contributions minus penalties, clamped to the range 0.1 to 1.0.

### Requirement 7: Prompt Template for Confidence Criteria

**User Story:** As a system developer, I want a dedicated prompt template for confidence-criteria-enriched requests, so that the prompt structure is maintainable and consistent.

#### Acceptance Criteria

1. THE Prompt_Engineering_System SHALL register a new `PromptType.CONFIDENCE_ENRICHED` template alongside the existing templates (INTENT_PARSING, ACTION_GENERATION, etc.).
2. THE CONFIDENCE_ENRICHED template SHALL include placeholders for: intent_text, network_state_summary, confidence_criteria_breakdown, and response_schema.
3. THE CONFIDENCE_ENRICHED template system_message SHALL instruct ChatGPT to act as an SDN expert that understands confidence scoring and to prioritize returning structured parameter suggestions that align with the provided criteria.
4. THE CONFIDENCE_ENRICHED template SHALL specify a response schema that includes both an `actions` array and a `parameter_suggestions` array.
