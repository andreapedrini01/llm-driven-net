# ChatGPT API Mock System

This directory contains a comprehensive mocking system for the ChatGPT API, enabling cost-free offline testing of the LLM Integration Module.

## Overview

The mock system provides:
- **Zero-cost testing**: No API calls, no charges
- **Offline operation**: No internet connection required
- **Response variation**: Multiple response templates for different scenarios
- **Realistic simulation**: Optional latency and error simulation
- **Full tracking**: Request/response history and statistics

## Components

### 1. MockChatGPTClient

The main mock client that replaces `ChatGPTClient` in tests.

```python
from tests.mocks import MockChatGPTClient

# Basic usage
client = MockChatGPTClient(simulate_latency=False)
response = await client.generate_response("Configure network flow")
```

**Features:**
- Drop-in replacement for `ChatGPTClient`
- Automatic response generation based on prompt content
- Request/response tracking
- Statistics collection
- Custom response handlers

### 2. ChatGPTResponseGenerator

Generates varied mock responses using templates.

```python
from tests.mocks import ChatGPTResponseGenerator, MockResponseVariant

generator = ChatGPTResponseGenerator()

# Generate specific response types
network_response = generator.generate_response(
    variant=MockResponseVariant.NETWORK_CONFIG,
    resource="switch_1",
    target="s1"
)

anomaly_response = generator.generate_anomaly_response(
    anomaly_type="high_latency",
    severity="critical"
)
```

**Response Variants:**
- `SIMPLE`: Basic intent/action responses
- `NETWORK_CONFIG`: Network configuration actions
- `ANOMALY_DETECTION`: Anomaly detection results
- `SLICE_MANAGEMENT`: Network slice operations
- `CLARIFICATION_REQUEST`: Clarification questions
- `ERROR_RESPONSE`: Error messages

### 3. Convenience Functions

Quick setup functions for common scenarios.

```python
from tests.mocks import create_mock_client, create_mock_response

# Create configured client
client = create_mock_client(
    simulate_latency=False,
    model="gpt-4-turbo"
)

# Create standalone response
response = create_mock_response(
    content="Mock response",
    tokens=100
)
```

## Usage Examples

### Basic Test

```python
import pytest
from tests.mocks import MockChatGPTClient

@pytest.mark.asyncio
async def test_intent_parsing():
    client = MockChatGPTClient(simulate_latency=False)
    
    response = await client.generate_response(
        prompt="Configure switch s1 to forward traffic",
        context={"network_state": "active"}
    )
    
    assert response is not None
    assert response.tokens_used > 0
    assert response.finish_reason == "stop"
```

### Custom Response Handler

```python
@pytest.mark.asyncio
async def test_custom_responses():
    client = MockChatGPTClient(simulate_latency=False)
    
    # Register custom handler for specific prompts
    def handle_special_case(prompt: str, context):
        return '{"action": "special_handling", "status": "success"}'
    
    client.register_custom_handler("special case", handle_special_case)
    
    response = await client.generate_response(
        "Handle this special case"
    )
    
    assert "special_handling" in response.content
```

### Simulating Errors

```python
@pytest.mark.asyncio
async def test_error_handling():
    from openai import APITimeoutError
    
    client = MockChatGPTClient(
        simulate_errors=True,
        error_rate=0.5  # 50% error rate
    )
    
    # Some requests will raise errors
    try:
        response = await client.generate_response("Test")
    except APITimeoutError:
        # Handle error as in production code
        pass
```

### Simulating Latency

```python
@pytest.mark.asyncio
async def test_with_latency():
    client = MockChatGPTClient(simulate_latency=True)
    
    start = time.time()
    response = await client.generate_response("Test")
    duration = time.time() - start
    
    # Will have realistic latency (0.5-2.0 seconds)
    assert duration >= 0.5
```

### Rate Limiting

```python
@pytest.mark.asyncio
async def test_rate_limiting():
    from src.services.chatgpt_client import ChatGPTConfig
    
    config = ChatGPTConfig(
        api_key="mock",
        rate_limit_rpm=5  # Low limit for testing
    )
    
    client = MockChatGPTClient(config=config)
    
    # Make requests up to limit
    for i in range(5):
        await client.generate_response(f"Request {i}")
    
    # Check rate limit status
    status = client.get_rate_limit_status()
    assert status.remaining_requests == 0
```

### Tracking and Statistics

```python
@pytest.mark.asyncio
async def test_tracking():
    client = MockChatGPTClient(simulate_latency=False)
    
    # Make several requests
    await client.generate_response("Request 1")
    await client.generate_response("Request 2")
    await client.generate_response("Request 3")
    
    # Get statistics
    stats = client.get_stats()
    assert stats["total_requests"] == 3
    assert stats["total_cost"] == 0.0  # Always free
    
    # Get request history
    history = client.get_request_history()
    assert len(history) == 3
    
    # Get response history
    responses = client.get_response_history()
    assert len(responses) == 3
```

### Response Generation

```python
from tests.mocks import ChatGPTResponseGenerator, MockResponseVariant

def test_response_generation():
    generator = ChatGPTResponseGenerator()
    
    # Network configuration
    config_response = generator.generate_network_action_response(
        intent_text="Add flow rule",
        action_type="flow_mod",
        num_actions=2
    )
    
    # Anomaly detection
    anomaly_response = generator.generate_anomaly_response(
        anomaly_type="packet_loss",
        severity="high",
        auto_mitigate=True
    )
    
    # Clarification request
    clarification = generator.generate_clarification_response(
        ambiguous_elements=["switch ID"],
        questions=["Which switch: s1, s2, or s3?"]
    )
```

## Integration with Existing Tests

### Replacing Real Client

```python
# Before (with real API)
from src.services.chatgpt_client import ChatGPTClient

client = ChatGPTClient()
response = await client.generate_response("Test")

# After (with mock)
from tests.mocks import MockChatGPTClient

client = MockChatGPTClient(simulate_latency=False)
response = await client.generate_response("Test")
```

### Using in Property-Based Tests

```python
from hypothesis import given, strategies as st
from tests.mocks import MockChatGPTClient

class TestWithMock:
    @given(prompt=st.text(min_size=10, max_size=100))
    @pytest.mark.asyncio
    async def test_property(self, prompt):
        client = MockChatGPTClient(simulate_latency=False)
        response = await client.generate_response(prompt)
        
        # Verify properties
        assert response is not None
        assert response.tokens_used > 0
```

### Fixture Setup

```python
import pytest
from tests.mocks import MockChatGPTClient

@pytest.fixture
def mock_chatgpt_client():
    """Provide a mock ChatGPT client for tests."""
    client = MockChatGPTClient(simulate_latency=False)
    yield client
    client.reset()  # Clean up after test

@pytest.mark.asyncio
async def test_with_fixture(mock_chatgpt_client):
    response = await mock_chatgpt_client.generate_response("Test")
    assert response is not None
```

## Configuration Options

### MockChatGPTClient Parameters

- `config`: ChatGPTConfig object (optional, uses defaults if None)
- `response_generator`: Custom ChatGPTResponseGenerator (optional)
- `simulate_latency`: Enable latency simulation (default: True)
- `simulate_errors`: Enable error simulation (default: False)
- `error_rate`: Probability of errors 0.0-1.0 (default: 0.0)

### ChatGPTConfig Parameters

- `api_key`: API key (use "mock" for testing)
- `model`: Model name (e.g., "gpt-4-turbo")
- `max_tokens`: Maximum tokens per request
- `temperature`: Temperature setting
- `rate_limit_rpm`: Requests per minute limit
- `timeout`: Request timeout in seconds
- `max_retries`: Maximum retry attempts

## Best Practices

1. **Disable latency in unit tests**: Use `simulate_latency=False` for faster tests
2. **Enable latency in integration tests**: Use `simulate_latency=True` for realistic scenarios
3. **Use custom handlers for specific cases**: Register handlers for edge cases
4. **Reset between tests**: Call `client.reset()` to clear history
5. **Check statistics**: Use `get_stats()` to verify behavior
6. **Test error handling**: Use `simulate_errors=True` to test resilience

## Benefits

- **Cost Savings**: No API charges during development and testing
- **Speed**: Tests run faster without network calls
- **Reliability**: No dependency on external API availability
- **Reproducibility**: Consistent responses for deterministic testing
- **Flexibility**: Easy to simulate various scenarios and edge cases

## Running Tests

```bash
# Run all mock tests
pytest tests/test_chatgpt_mock.py -v

# Run with coverage
pytest tests/test_chatgpt_mock.py --cov=tests.mocks --cov-report=html

# Run specific test
pytest tests/test_chatgpt_mock.py::TestMockChatGPTClient::test_generate_response_basic -v
```

## Extending the Mock System

### Adding New Response Variants

```python
# In chatgpt_mock.py, add to _initialize_templates():

MockResponseVariant.CUSTOM_TYPE: [
    MockResponseTemplate(
        variant=MockResponseVariant.CUSTOM_TYPE,
        template='{"custom": "{value}"}',
        variables=["value"]
    ),
]
```

### Adding New Generator Methods

```python
# In ChatGPTResponseGenerator class:

def generate_custom_response(self, param1: str, param2: int) -> str:
    """Generate custom response type."""
    response = {
        "type": "custom",
        "param1": param1,
        "param2": param2
    }
    return json.dumps(response, indent=2)
```

## Troubleshooting

**Issue**: Mock responses don't match expected format
- **Solution**: Use custom handlers or add new templates

**Issue**: Tests are too slow
- **Solution**: Disable latency simulation with `simulate_latency=False`

**Issue**: Need specific response for edge case
- **Solution**: Register a custom handler with `register_custom_handler()`

**Issue**: Want to test error scenarios
- **Solution**: Enable error simulation with `simulate_errors=True` and set `error_rate`

## Support

For issues or questions about the mock system, refer to:
- Test examples in `tests/test_chatgpt_mock.py`
- Source code in `tests/mocks/chatgpt_mock.py`
- Integration tests in `tests/test_integration_suite.py`
