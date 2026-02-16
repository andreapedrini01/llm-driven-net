# Prompt Engineering System

The Prompt Engineering System provides optimized, networking-specific prompt templates for ChatGPT API integration. It handles prompt construction, context injection, response parsing, and validation.

## Overview

The system is designed to:
- Generate consistent, high-quality prompts for different network operations
- Inject network context efficiently while managing token budgets
- Parse and validate ChatGPT responses against expected schemas
- Optimize prompts for accuracy and token efficiency

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Prompt Engineering System                   │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Template   │  │   Context    │  │   Response   │      │
│  │  Management  │  │  Injection   │  │   Parsing    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Prompt Templates                         │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │ • Intent Parsing                                      │   │
│  │ • Action Generation                                   │   │
│  │ • Anomaly Analysis                                    │   │
│  │ • Clarification                                       │   │
│  │ • Validation                                          │   │
│  │ • Slice Orchestration                                 │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Components

### PromptEngineeringSystem

Main class that manages prompt templates and response processing.

```python
from src.services.prompt_engineering import PromptEngineeringSystem

# Initialize the system
prompt_system = PromptEngineeringSystem()

# Get a template
template = prompt_system.get_template(PromptType.INTENT_PARSING)
```

### PromptType

Enumeration of available prompt types:

- `INTENT_PARSING`: Parse natural language intents
- `ACTION_GENERATION`: Generate network actions
- `ANOMALY_ANALYSIS`: Analyze network anomalies
- `CLARIFICATION`: Request clarifications for ambiguous intents
- `VALIDATION`: Validate action sequences
- `SLICE_ORCHESTRATION`: Orchestrate network slices

### PromptTemplate

Template structure for generating prompts:

```python
class PromptTemplate:
    type: PromptType
    system_message: str          # System message for ChatGPT
    user_template: str           # User prompt template with placeholders
    response_schema: Dict        # Expected response structure
    max_tokens: int = 2000       # Maximum tokens for response
    temperature: float = 0.1     # Temperature for generation
```

## Usage Examples

### 1. Intent Parsing

```python
from src.services.prompt_engineering import PromptEngineeringSystem, PromptType
from src.services.chatgpt_client import ChatGPTClient

# Initialize
prompt_system = PromptEngineeringSystem()
chatgpt_client = ChatGPTClient()

# Build prompt
intent_text = "Create a flow from switch-1 to switch-2"
system_msg, user_prompt, config = prompt_system.build_intent_parsing_prompt(intent_text)

# Get response from ChatGPT
response = await chatgpt_client.generate_response(
    prompt=user_prompt,
    system_message=system_msg
)

# Parse and validate response
template = prompt_system.get_template(PromptType.INTENT_PARSING)
parsed = prompt_system.parse_response(
    response.content,
    template.response_schema,
    PromptType.INTENT_PARSING
)

if parsed.is_valid:
    print(f"Intent Type: {parsed.parsed_data['intent_type']}")
    print(f"Entities: {parsed.parsed_data['entities']}")
```

### 2. Action Generation

```python
# Create contextualized intent with network state
contextualized_intent = ContextualizedIntent(
    intent=intent_object,
    relevant_resources=["switch-1", "switch-2"],
    network_context={"topology": "simple"},
    conflicts=[],
    recommendations=[]
)

# Build prompt with network context
system_msg, user_prompt, config = prompt_system.build_action_generation_prompt(
    contextualized_intent,
    network_state
)

# Get and parse response
response = await chatgpt_client.generate_response(
    prompt=user_prompt,
    system_message=system_msg
)

parsed = prompt_system.parse_response(
    response.content,
    template.response_schema,
    PromptType.ACTION_GENERATION
)

if parsed.is_valid:
    actions = parsed.parsed_data['actions']
    rollback_plan = parsed.parsed_data['rollback_plan']
    risks = parsed.parsed_data['risks']
```

### 3. Anomaly Analysis

```python
# Analyze a detected anomaly
system_msg, user_prompt, config = prompt_system.build_anomaly_analysis_prompt(
    anomaly,
    network_state
)

response = await chatgpt_client.generate_response(
    prompt=user_prompt,
    system_message=system_msg
)

parsed = prompt_system.parse_response(
    response.content,
    template.response_schema,
    PromptType.ANOMALY_ANALYSIS
)

if parsed.is_valid:
    analysis = parsed.parsed_data['analysis']
    root_causes = parsed.parsed_data['root_cause']
    mitigation_actions = parsed.parsed_data['mitigation_actions']
```

### 4. Clarification Requests

```python
# Request clarification for ambiguous intent
ambiguities = ["Which switch?", "What priority?"]

system_msg, user_prompt, config = prompt_system.build_clarification_prompt(
    intent_text,
    ambiguities,
    network_state
)

response = await chatgpt_client.generate_response(
    prompt=user_prompt,
    system_message=system_msg
)

parsed = prompt_system.parse_response(
    response.content,
    template.response_schema,
    PromptType.CLARIFICATION
)

if parsed.is_valid:
    questions = parsed.parsed_data['questions']
    for q in questions:
        print(f"Q: {q['question']}")
        print(f"Suggestions: {q['suggestions']}")
```

## Prompt Optimization

The system includes token optimization to manage costs:

```python
# Optimize a long prompt
long_prompt = "..." # Very long network state description

optimized = prompt_system.optimize_prompt_for_tokens(
    long_prompt,
    max_tokens=4000
)

# The optimized prompt will be truncated intelligently
# to fit within the token budget
```

## Response Parsing

The system handles various response formats:

### Plain JSON
```json
{"intent_type": "configuration", "confidence": 0.9}
```

### Markdown-wrapped JSON
```markdown
```json
{"intent_type": "configuration", "confidence": 0.9}
```
```

### JSON with surrounding text
```
Here is the analysis: {"intent_type": "configuration", "confidence": 0.9} as requested.
```

All formats are automatically detected and parsed.

## Context Injection

The system efficiently injects network context into prompts:

### Network State Formatting
- Topology summary (switches, links, hosts)
- Metrics (bandwidth, latency, utilization)
- Active anomalies
- Flow information

### Token-Efficient Context
- Limits detailed information to most relevant resources
- Summarizes large topologies
- Prioritizes critical metrics

Example formatted context:
```
Topology:
  - Switch switch-1: 4 ports, active
  - Switch switch-2: 4 ports, active

Links: 2 total
  - switch-1:1 <-> switch-2:1 (1000Mbps)

Metrics:
  - Bandwidth utilization: 30.5%
  - Average latency: 2.5ms
  - CPU utilization: 45.0%
```

## Validation

Response validation includes:

1. **JSON Structure**: Validates JSON syntax
2. **Schema Compliance**: Checks required fields
3. **Type Checking**: Validates field types
4. **Completeness**: Estimates confidence based on completeness

```python
parsed = prompt_system.parse_response(raw_response, schema, prompt_type)

print(f"Valid: {parsed.is_valid}")
print(f"Confidence: {parsed.confidence}")
print(f"Errors: {parsed.validation_errors}")
```

## Best Practices

### 1. Choose Appropriate Temperature
- **Low (0.0-0.2)**: For deterministic tasks (parsing, validation)
- **Medium (0.3-0.5)**: For creative tasks (clarification, suggestions)
- **High (0.6-1.0)**: Not recommended for network operations

### 2. Manage Token Budgets
- Use `optimize_prompt_for_tokens()` for large contexts
- Limit network state details to relevant resources
- Monitor token usage and costs

### 3. Validate Responses
- Always validate parsed responses
- Check confidence scores
- Handle validation errors gracefully

### 4. Context Relevance
- Include only relevant network resources
- Prioritize recent metrics
- Filter out unnecessary details

### 5. Error Handling
```python
try:
    response = await chatgpt_client.generate_response(...)
    parsed = prompt_system.parse_response(...)
    
    if not parsed.is_valid:
        logger.warning(f"Invalid response: {parsed.validation_errors}")
        # Handle invalid response
    
except Exception as e:
    logger.error(f"Error: {str(e)}")
    # Fallback to rule-based processing
```

## Performance Considerations

### Token Usage
- Intent Parsing: ~500-1500 tokens
- Action Generation: ~1000-2500 tokens
- Anomaly Analysis: ~800-2000 tokens
- Clarification: ~400-1000 tokens
- Validation: ~600-1500 tokens

### Latency
- Typical response time: 2-5 seconds (GPT-4-turbo)
- Varies with prompt complexity and token count

### Cost Estimation
- GPT-4-turbo: ~$0.01-0.03 per request
- GPT-4: ~$0.03-0.06 per request
- GPT-3.5-turbo: ~$0.001-0.003 per request

## Testing

Run the test suite:
```bash
pytest tests/test_prompt_engineering.py -v
```

Run examples:
```bash
python examples/prompt_engineering_example.py
```

## Integration with ChatGPT Client

The prompt engineering system is designed to work seamlessly with the ChatGPT client:

```python
# Complete workflow
prompt_system = PromptEngineeringSystem()
chatgpt_client = ChatGPTClient()

# 1. Build prompt
system_msg, user_prompt, config = prompt_system.build_intent_parsing_prompt(intent_text)

# 2. Get response
response = await chatgpt_client.generate_response(
    prompt=user_prompt,
    system_message=system_msg
)

# 3. Parse and validate
template = prompt_system.get_template(PromptType.INTENT_PARSING)
parsed = prompt_system.parse_response(
    response.content,
    template.response_schema,
    PromptType.INTENT_PARSING
)

# 4. Use parsed data
if parsed.is_valid:
    # Process the structured data
    process_intent(parsed.parsed_data)
```

## Future Enhancements

- [ ] Dynamic prompt optimization based on feedback
- [ ] A/B testing for prompt variations
- [ ] Caching for similar prompts
- [ ] Multi-language support
- [ ] Custom template creation API
- [ ] Prompt performance analytics

## References

- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Prompt Engineering Guide](https://www.promptingguide.ai/)
- [ChatGPT Best Practices](https://platform.openai.com/docs/guides/prompt-engineering)
