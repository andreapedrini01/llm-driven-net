# Prompt Engineering System

The prompt engineering system manages how the app communicates with ChatGPT. It builds structured prompts, injects network context, and parses responses back into actionable data.

## How It Works

When the rule-based engine can't handle an intent (confidence < 0.8), the system:

1. Picks the right prompt template for the task
2. Injects the current network state and intent details
3. Sends it to ChatGPT via `ChatGPTClient`
4. Parses and validates the JSON response

## Prompt Types

The system has templates for different operations:

| Type | Purpose | Temperature |
|------|---------|-------------|
| `INTENT_PARSING` | Parse natural language intents | 0.1 |
| `ACTION_GENERATION` | Generate network actions from intents | 0.1 |
| `ANOMALY_ANALYSIS` | Analyze detected anomalies | 0.2 |
| `CLARIFICATION` | Ask follow-up questions for ambiguous intents | 0.3 |
| `VALIDATION` | Validate action sequences for safety | 0.1 |
| `SLICE_ORCHESTRATION` | Design network slices | 0.1 |
| `CONFIDENCE_ENRICHED` | Generate actions with confidence-aware suggestions | 0.1 |

Each template includes a system message (sets ChatGPT's role), a user template with placeholders, and an expected response schema.

## Usage

```python
from llm_integration_module.services.prompt_engineering import PromptEngineeringSystem, PromptType
from llm_integration_module.services.chatgpt_client import ChatGPTClient

prompt_system = PromptEngineeringSystem()
client = ChatGPTClient()

# Build a prompt
system_msg, user_prompt, config = prompt_system.build_intent_parsing_prompt(
    "create slice between h1 h2 with bandwidth at 10 mbps"
)

# Send to ChatGPT
response = await client.generate_response(
    prompt=user_prompt,
    system_message=system_msg
)

# Parse the response
template = prompt_system.get_template(PromptType.INTENT_PARSING)
parsed = prompt_system.parse_response(
    response.content,
    template.response_schema,
    PromptType.INTENT_PARSING
)

if parsed.is_valid:
    print(parsed.parsed_data)
```

## Available Build Methods

Each prompt type has a dedicated builder:

- `build_intent_parsing_prompt(intent_text)` — for parsing raw text
- `build_action_generation_prompt(contextualized_intent, network_state)` — for generating actions
- `build_anomaly_analysis_prompt(anomaly, network_state)` — for anomaly analysis
- `build_clarification_prompt(intent_text, ambiguities, network_state)` — for follow-up questions
- `build_validation_prompt(action_sequence, network_state)` — for safety checks
- `build_slice_orchestration_prompt(intent_text, requirements, network_state)` — for slice design
- `build_confidence_enriched_prompt(intent_obj, breakdown, network_state)` — for confidence-aware generation

All return a tuple of `(system_message, user_prompt, config)`.

## Response Parsing

The parser handles multiple response formats automatically:
- Plain JSON
- JSON wrapped in markdown code blocks
- JSON embedded in surrounding text

Validation checks JSON structure, required fields, and field types. The result includes a confidence score based on completeness.

## Context Injection

Network state is formatted into a compact summary before injection:

```
Topology:
  - Switch switch-1: 4 ports, active
  - Switch switch-2: 4 ports, active
Links: 2 total
Metrics:
  - Bandwidth utilization: 30.5%
  - Average latency: 2.5ms
```

This keeps token usage low while giving ChatGPT enough context to make good decisions.

## Integration with main.py

In `main.py`, the confidence-enriched prompt is the primary path when ChatGPT is needed:

```python
system_msg, user_prompt, prompt_config = prompt_system.build_confidence_enriched_prompt(
    intent_obj, breakdown, network_state
)
llm_response = asyncio.run(generate_actions_llm())
actions, suggestions = action_sequencer.parse_actions_and_suggestions(llm_response.content)
```

The confidence breakdown is included in the prompt so ChatGPT can suggest parameter improvements alongside the actions.
