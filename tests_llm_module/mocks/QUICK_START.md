# Quick Start Guide - ChatGPT Mock Client

Get started with the mock ChatGPT client in 5 minutes.

## Installation

No installation needed! The mock system is already part of the test suite.

## Basic Usage

### 1. Import the Mock Client

```python
from tests.mocks import MockChatGPTClient, create_mock_client
```

### 2. Create a Client

```python
# Simple creation
client = MockChatGPTClient(simulate_latency=False)

# Or use convenience function
client = create_mock_client(simulate_latency=False)
```

### 3. Make Requests

```python
response = await client.generate_response("Configure network flow")
print(response.content)
print(f"Tokens used: {response.tokens_used}")
print(f"Cost: ${response.latency}")
```

## Common Patterns

### Pattern 1: Basic Test

```python
import pytest
from tests.mocks import create_mock_client

@pytest.mark.asyncio
async def test_my_feature():
    client = create_mock_client(simulate_latency=False)
    response = await client.generate_response("Test prompt")
    assert response is not None
```

### Pattern 2: With Fixture

```python
@pytest.fixture
def mock_client():
    client = create_mock_client(simulate_latency=False)
    yield client
    client.reset()

@pytest.mark.asyncio
async def test_with_fixture(mock_client):
    response = await mock_client.generate_response("Test")
    assert response is not None
```

### Pattern 3: Custom Responses

```python
client = create_mock_client(simulate_latency=False)

def my_handler(prompt, context):
    return '{"custom": "response"}'

client.register_custom_handler("keyword", my_handler)
response = await client.generate_response("prompt with keyword")
```

### Pattern 4: Error Simulation

```python
from openai import APITimeoutError

client = create_mock_client(
    simulate_errors=True,
    error_rate=0.5  # 50% error rate
)

try:
    response = await client.generate_response("Test")
except APITimeoutError:
    # Handle error
    pass
```

## Key Features

✅ **Zero Cost** - No API charges  
✅ **Fast** - No network latency (unless simulated)  
✅ **Offline** - Works without internet  
✅ **Smart** - Generates context-aware responses  
✅ **Trackable** - Full request/response history  

## Response Types

The mock automatically detects intent type and generates appropriate responses:

- **Configuration**: "Configure switch..." → Flow modification actions
- **Anomaly**: "Detect anomaly..." → Anomaly detection results
- **Slice**: "Create slice..." → Slice management actions
- **Query**: "What is..." → Information responses

## Quick Tips

1. **Disable latency in unit tests** for speed:
   ```python
   client = create_mock_client(simulate_latency=False)
   ```

2. **Enable latency in integration tests** for realism:
   ```python
   client = create_mock_client(simulate_latency=True)
   ```

3. **Check statistics** to verify behavior:
   ```python
   stats = client.get_stats()
   print(f"Requests: {stats['total_requests']}")
   print(f"Cost: ${stats['total_cost']}")  # Always 0.0
   ```

4. **Reset between tests** to clear history:
   ```python
   client.reset()
   ```

## Examples

See `tests/examples/test_using_mock_client.py` for comprehensive examples.

## Need Help?

- Read the full documentation: `tests/mocks/README.md`
- Check test examples: `tests/test_chatgpt_mock.py`
- Review integration examples: `tests/examples/test_using_mock_client.py`
