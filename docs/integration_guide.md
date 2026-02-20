# Northbound Script Generator - Integration Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [Environment Setup](#environment-setup)
3. [Authentication Setup](#authentication-setup)
4. [Basic Integration](#basic-integration)
5. [Advanced Integration](#advanced-integration)
6. [LLM Integration](#llm-integration)
7. [Troubleshooting](#troubleshooting)

## Getting Started

This guide will walk you through integrating your application with the Northbound Script Generator API.

### Prerequisites

- Python 3.8+ or Node.js 14+ (depending on your integration language)
- Network access to the API server
- Valid credentials or API key

### Quick Start (5 minutes)

1. **Get API credentials**
2. **Install client library**
3. **Submit your first action**
4. **Monitor action status**

Let's begin!

## Environment Setup

### Step 1: Install Dependencies

**Python:**
```bash
pip install requests python-dotenv
```

**Node.js:**
```bash
npm install axios dotenv
```

### Step 2: Configure Environment Variables

Create a `.env` file in your project root:

```bash
# API Configuration
NORTHBOUND_API_URL=http://localhost:8000
NORTHBOUND_API_KEY=your-api-key-here

# Optional: JWT Token (if using token auth instead of API key)
NORTHBOUND_JWT_TOKEN=your-jwt-token-here

# Optional: Logging
LOG_LEVEL=INFO
```

**Security Note:** Never commit `.env` files to version control. Add `.env` to your `.gitignore`.

### Step 3: Verify API Connectivity

Test that you can reach the API:

**Python:**
```python
import requests
import os
from dotenv import load_dotenv

load_dotenv()

api_url = os.getenv('NORTHBOUND_API_URL')
response = requests.get(f"{api_url}/health")

if response.status_code == 200:
    print("✓ API is reachable")
    print(f"Status: {response.json()['status']}")
else:
    print("✗ API is not reachable")
```

**Node.js:**
```javascript
const axios = require('axios');
require('dotenv').config();

const apiUrl = process.env.NORTHBOUND_API_URL;

axios.get(`${apiUrl}/health`)
  .then(response => {
    console.log('✓ API is reachable');
    console.log(`Status: ${response.data.status}`);
  })
  .catch(error => {
    console.log('✗ API is not reachable');
    console.error(error.message);
  });
```

## Authentication Setup

### Option 1: API Key Authentication (Recommended for Automation)

API keys are ideal for automated systems, LLM integrations, and service-to-service communication.

#### Step 1: Obtain an API Key

**Via Web Dashboard:**
1. Login to http://localhost:8000/dashboard
2. Navigate to Settings > API Keys
3. Click "Generate New API Key"
4. Copy the key (it won't be shown again!)
5. Store it securely in your `.env` file

**Via API (if you have admin credentials):**
```bash
curl -X POST http://localhost:8000/api/v1/auth/api-keys \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Integration",
    "expires_in_days": 365
  }'
```

#### Step 2: Test API Key

**Python:**
```python
import requests
import os
from dotenv import load_dotenv

load_dotenv()

api_url = os.getenv('NORTHBOUND_API_URL')
api_key = os.getenv('NORTHBOUND_API_KEY')

headers = {
    'X-API-Key': api_key,
    'Content-Type': 'application/json'
}

response = requests.get(f"{api_url}/api/v1/actions", headers=headers)

if response.status_code == 200:
    print("✓ API key is valid")
else:
    print(f"✗ API key validation failed: {response.status_code}")
```

### Option 2: JWT Token Authentication (For User-Based Access)

JWT tokens are ideal for user-facing applications where you need user-specific permissions.

#### Step 1: Login and Obtain Token

**Python:**
```python
import requests

def login(api_url, username, password):
    response = requests.post(
        f"{api_url}/api/v1/auth/login",
        json={
            "username": username,
            "password": password
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        return data['access_token'], data['refresh_token']
    else:
        raise Exception(f"Login failed: {response.text}")

# Usage
api_url = "http://localhost:8000"
access_token, refresh_token = login(api_url, "admin", "your-password")
print(f"✓ Logged in successfully")
```

#### Step 2: Use Token in Requests

```python
headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json'
}

response = requests.get(f"{api_url}/api/v1/actions", headers=headers)
```

#### Step 3: Refresh Token When Expired

```python
def refresh_access_token(api_url, refresh_token):
    response = requests.post(
        f"{api_url}/api/v1/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    
    if response.status_code == 200:
        return response.json()['access_token']
    else:
        raise Exception("Token refresh failed")

# Usage
try:
    response = requests.get(f"{api_url}/api/v1/actions", headers=headers)
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 401:
        # Token expired, refresh it
        access_token = refresh_access_token(api_url, refresh_token)
        headers['Authorization'] = f'Bearer {access_token}'
        response = requests.get(f"{api_url}/api/v1/actions", headers=headers)
```

## Basic Integration

### Step 1: Create a Client Class

**Python:**
```python
import requests
import time
from typing import Dict, Any, List, Optional

class NorthboundClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        }
    
    def submit_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a network action."""
        response = requests.post(
            f"{self.base_url}/api/v1/actions",
            json=action,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def get_action_status(self, action_id: str) -> Dict[str, Any]:
        """Get action status."""
        response = requests.get(
            f"{self.base_url}/api/v1/actions/{action_id}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def list_actions(self, status_filter: Optional[str] = None, 
                     limit: int = 100) -> List[Dict[str, Any]]:
        """List actions with optional filtering."""
        params = {'limit': limit}
        if status_filter:
            params['status_filter'] = status_filter
        
        response = requests.get(
            f"{self.base_url}/api/v1/actions",
            headers=self.headers,
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def cancel_action(self, action_id: str) -> Dict[str, Any]:
        """Cancel an action."""
        response = requests.delete(
            f"{self.base_url}/api/v1/actions/{action_id}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def wait_for_completion(self, action_id: str, 
                           timeout: int = 300,
                           poll_interval: int = 2) -> Dict[str, Any]:
        """Wait for action to complete."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_action_status(action_id)
            
            if status['status'] in ['completed', 'failed', 'cancelled']:
                return status
            
            time.sleep(poll_interval)
        
        raise TimeoutError(
            f"Action {action_id} did not complete within {timeout}s"
        )
```

### Step 2: Submit Your First Action

```python
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize client
client = NorthboundClient(
    base_url=os.getenv('NORTHBOUND_API_URL'),
    api_key=os.getenv('NORTHBOUND_API_KEY')
)

# Define a simple flow rule action
action = {
    "type": "flow_rule",
    "target": "switch-1",
    "parameters": {
        "operation": "add",
        "match": {
            "in_port": 1,
            "eth_type": 2048  # IPv4
        },
        "actions": ["output:2"],
        "priority": 100
    },
    "priority": 5,
    "timeout": 60,
    "description": "Forward IPv4 traffic from port 1 to port 2"
}

# Submit action
print("Submitting action...")
result = client.submit_action(action)
print(f"✓ Action submitted: {result['action_id']}")
print(f"  Status: {result['status']}")
print(f"  Estimated completion: {result['estimated_completion']}")

# Wait for completion
print("\nWaiting for action to complete...")
final_status = client.wait_for_completion(result['action_id'])

if final_status['status'] == 'completed':
    print("✓ Action completed successfully!")
    print(f"  Result: {final_status.get('result')}")
elif final_status['status'] == 'failed':
    print("✗ Action failed!")
    print(f"  Error: {final_status.get('error')}")
```

### Step 3: Handle Errors Gracefully

```python
from requests.exceptions import HTTPError, RequestException

def submit_action_safely(client, action):
    try:
        result = client.submit_action(action)
        print(f"✓ Action submitted: {result['action_id']}")
        return result
    
    except HTTPError as e:
        if e.response.status_code == 400:
            print("✗ Invalid action parameters:")
            print(f"  {e.response.json()}")
        elif e.response.status_code == 401:
            print("✗ Authentication failed. Check your API key.")
        elif e.response.status_code == 429:
            print("✗ Rate limit exceeded. Please wait and retry.")
            retry_after = e.response.headers.get('Retry-After', 60)
            print(f"  Retry after: {retry_after} seconds")
        else:
            print(f"✗ HTTP error: {e.response.status_code}")
            print(f"  {e.response.text}")
        return None
    
    except RequestException as e:
        print(f"✗ Network error: {e}")
        return None
    
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return None

# Usage
result = submit_action_safely(client, action)
if result:
    # Proceed with monitoring
    pass
```

## Advanced Integration

### Batch Operations

Submit multiple actions efficiently:

```python
def submit_batch_actions(client, actions):
    """Submit multiple actions as a batch."""
    batch_request = {"actions": actions}
    
    response = requests.post(
        f"{client.base_url}/api/v1/actions/batch",
        json=batch_request,
        headers=client.headers
    )
    response.raise_for_status()
    return response.json()

# Example: Configure multiple switches
actions = [
    {
        "type": "flow_rule",
        "target": "switch-1",
        "parameters": {
            "operation": "add",
            "match": {"in_port": 1},
            "actions": ["output:2"]
        }
    },
    {
        "type": "flow_rule",
        "target": "switch-2",
        "parameters": {
            "operation": "add",
            "match": {"in_port": 1},
            "actions": ["output:3"]
        }
    },
    {
        "type": "qos_policy",
        "target": "switch-1:port-2",
        "parameters": {
            "bandwidth_limit_mbps": 100,
            "latency_limit_ms": 50
        }
    }
]

batch_result = submit_batch_actions(client, actions)
print(f"✓ Batch submitted: {batch_result['batch_id']}")
print(f"  Total actions: {batch_result['total_actions']}")
print(f"  Action IDs: {batch_result['action_ids']}")

# Monitor all actions
for action_id in batch_result['action_ids']:
    status = client.wait_for_completion(action_id)
    print(f"  {action_id}: {status['status']}")
```

### Retry Logic with Exponential Backoff

```python
import time
from typing import Callable, Any

def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0
) -> Any:
    """Retry a function with exponential backoff."""
    delay = initial_delay
    
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            
            print(f"Attempt {attempt + 1} failed: {e}")
            print(f"Retrying in {delay:.1f} seconds...")
            time.sleep(delay)
            
            delay = min(delay * backoff_factor, max_delay)

# Usage
result = retry_with_backoff(
    lambda: client.submit_action(action),
    max_retries=3
)
```

### Async/Concurrent Operations

For high-throughput scenarios:

```python
import asyncio
import aiohttp
from typing import List, Dict, Any

class AsyncNorthboundClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        }
    
    async def submit_action(self, session: aiohttp.ClientSession, 
                           action: Dict[str, Any]) -> Dict[str, Any]:
        """Submit action asynchronously."""
        async with session.post(
            f"{self.base_url}/api/v1/actions",
            json=action,
            headers=self.headers
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    async def submit_multiple_actions(self, 
                                     actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Submit multiple actions concurrently."""
        async with aiohttp.ClientSession() as session:
            tasks = [
                self.submit_action(session, action)
                for action in actions
            ]
            return await asyncio.gather(*tasks)

# Usage
async def main():
    client = AsyncNorthboundClient(
        base_url=os.getenv('NORTHBOUND_API_URL'),
        api_key=os.getenv('NORTHBOUND_API_KEY')
    )
    
    actions = [...]  # Your actions
    results = await client.submit_multiple_actions(actions)
    
    for result in results:
        print(f"Submitted: {result['action_id']}")

# Run
asyncio.run(main())
```

## LLM Integration

### OpenAI Integration Example

```python
import openai
import json
from typing import Dict, Any

class LLMNetworkController:
    def __init__(self, northbound_client: NorthboundClient, openai_api_key: str):
        self.client = northbound_client
        openai.api_key = openai_api_key
    
    def natural_language_to_action(self, command: str) -> Dict[str, Any]:
        """Convert natural language command to network action using LLM."""
        
        system_prompt = """You are a network configuration assistant. 
        Convert natural language commands into JSON network actions.
        
        Available action types:
        - flow_rule: Configure OpenFlow rules
        - topology_change: Modify network topology
        - qos_policy: Configure QoS policies
        
        Return only valid JSON matching the API schema."""
        
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": command}
            ],
            temperature=0.1
        )
        
        action_json = response.choices[0].message.content
        return json.loads(action_json)
    
    def execute_natural_language_command(self, command: str) -> Dict[str, Any]:
        """Execute a natural language network command."""
        print(f"Processing command: {command}")
        
        # Convert to action
        action = self.natural_language_to_action(command)
        print(f"Generated action: {action['type']} on {action['target']}")
        
        # Submit action
        result = self.client.submit_action(action)
        print(f"Action submitted: {result['action_id']}")
        
        # Wait for completion
        final_status = self.client.wait_for_completion(result['action_id'])
        
        return final_status

# Usage
llm_controller = LLMNetworkController(client, openai_api_key)

commands = [
    "Forward all HTTP traffic from port 1 to port 2 on switch-1",
    "Apply QoS policy with 100Mbps bandwidth limit to switch-1 port 3",
    "Add a new switch with ID switch-5 to the topology"
]

for command in commands:
    result = llm_controller.execute_natural_language_command(command)
    print(f"Result: {result['status']}\n")
```

### LangChain Integration

```python
from langchain.tools import Tool
from langchain.agents import initialize_agent, AgentType
from langchain.llms import OpenAI

def create_network_tools(client: NorthboundClient):
    """Create LangChain tools for network operations."""
    
    def submit_flow_rule(params: str) -> str:
        """Submit a flow rule. Params: JSON string with action details."""
        action = json.loads(params)
        result = client.submit_action(action)
        return f"Action submitted: {result['action_id']}"
    
    def check_action_status(action_id: str) -> str:
        """Check status of an action."""
        status = client.get_action_status(action_id)
        return f"Status: {status['status']}"
    
    def list_recent_actions(params: str) -> str:
        """List recent actions."""
        actions = client.list_actions(limit=10)
        return json.dumps(actions, indent=2)
    
    return [
        Tool(
            name="SubmitFlowRule",
            func=submit_flow_rule,
            description="Submit a network flow rule action"
        ),
        Tool(
            name="CheckActionStatus",
            func=check_action_status,
            description="Check the status of a submitted action"
        ),
        Tool(
            name="ListRecentActions",
            func=list_recent_actions,
            description="List recent network actions"
        )
    ]

# Create agent
llm = OpenAI(temperature=0)
tools = create_network_tools(client)
agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)

# Use agent
result = agent.run(
    "Configure switch-1 to forward traffic from port 1 to port 2, "
    "then check if the action completed successfully"
)
print(result)
```

## Troubleshooting

### Common Issues and Solutions

#### Issue 1: Authentication Failures

**Symptom:** 401 Unauthorized errors

**Solutions:**
1. Verify API key is correct and not expired
2. Check that API key is properly set in headers
3. Ensure no extra whitespace in API key
4. Try regenerating the API key

```python
# Debug authentication
import requests

response = requests.get(
    f"{api_url}/api/v1/actions",
    headers={'X-API-Key': api_key}
)

print(f"Status: {response.status_code}")
print(f"Headers sent: {response.request.headers}")
print(f"Response: {response.text}")
```

#### Issue 2: Action Validation Failures

**Symptom:** 400 Bad Request with validation errors

**Solutions:**
1. Check action parameters match the schema
2. Verify all required fields are present
3. Ensure data types are correct
4. Review API documentation for parameter requirements

```python
# Validate action locally before submission
def validate_flow_rule_action(action):
    required_params = ['operation', 'match', 'actions']
    
    if action['type'] != 'flow_rule':
        raise ValueError("Not a flow_rule action")
    
    for param in required_params:
        if param not in action['parameters']:
            raise ValueError(f"Missing required parameter: {param}")
    
    valid_operations = ['add', 'modify', 'delete']
    if action['parameters']['operation'] not in valid_operations:
        raise ValueError(f"Invalid operation: {action['parameters']['operation']}")
    
    return True

# Use before submission
try:
    validate_flow_rule_action(action)
    result = client.submit_action(action)
except ValueError as e:
    print(f"Validation error: {e}")
```

#### Issue 3: Timeout Errors

**Symptom:** Actions timeout or take too long

**Solutions:**
1. Increase timeout parameter in action
2. Check network connectivity to RYU/ComnetsEMU
3. Verify target switches are reachable
4. Review system logs for bottlenecks

```python
# Increase timeout and add better error handling
action['timeout'] = 300  # 5 minutes

try:
    result = client.submit_action(action)
    final_status = client.wait_for_completion(
        result['action_id'],
        timeout=600  # 10 minutes
    )
except TimeoutError:
    # Check action status manually
    status = client.get_action_status(result['action_id'])
    print(f"Action still running: {status}")
    # Decide whether to wait more or cancel
```

#### Issue 4: Rate Limiting

**Symptom:** 429 Too Many Requests errors

**Solutions:**
1. Implement rate limiting in your client
2. Use batch operations for multiple actions
3. Add delays between requests
4. Request higher rate limits if needed

```python
import time
from collections import deque

class RateLimitedClient:
    def __init__(self, client, max_requests=100, time_window=60):
        self.client = client
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
    
    def _wait_if_needed(self):
        now = time.time()
        
        # Remove old requests outside time window
        while self.requests and self.requests[0] < now - self.time_window:
            self.requests.popleft()
        
        # Wait if at limit
        if len(self.requests) >= self.max_requests:
            sleep_time = self.requests[0] + self.time_window - now
            if sleep_time > 0:
                time.sleep(sleep_time)
                self._wait_if_needed()
    
    def submit_action(self, action):
        self._wait_if_needed()
        self.requests.append(time.time())
        return self.client.submit_action(action)

# Usage
rate_limited_client = RateLimitedClient(client, max_requests=90, time_window=60)
```

### Debugging Tips

#### Enable Verbose Logging

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Now all HTTP requests will be logged
```

#### Inspect API Responses

```python
def debug_request(client, action):
    """Submit action with detailed debugging."""
    import json
    
    print("=== Request ===")
    print(f"URL: {client.base_url}/api/v1/actions")
    print(f"Headers: {json.dumps(client.headers, indent=2)}")
    print(f"Body: {json.dumps(action, indent=2)}")
    
    try:
        result = client.submit_action(action)
        print("\n=== Response ===")
        print(f"Status: Success")
        print(f"Body: {json.dumps(result, indent=2)}")
        return result
    except Exception as e:
        print("\n=== Error ===")
        print(f"Type: {type(e).__name__}")
        print(f"Message: {str(e)}")
        if hasattr(e, 'response'):
            print(f"Status Code: {e.response.status_code}")
            print(f"Response: {e.response.text}")
        raise
```

#### Check System Health

```python
def check_system_health(client):
    """Comprehensive health check."""
    try:
        response = requests.get(f"{client.base_url}/health")
        health = response.json()
        
        print("=== System Health ===")
        print(f"Overall Status: {health['status']}")
        print(f"Version: {health['version']}")
        print("\nServices:")
        for service, status in health['services'].items():
            icon = "✓" if status == "healthy" else "✗"
            print(f"  {icon} {service}: {status}")
        
        if health['status'] != 'healthy':
            print(f"\nError: {health.get('error', 'Unknown')}")
            return False
        
        return True
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return False

# Run before submitting actions
if check_system_health(client):
    result = client.submit_action(action)
```

### Getting Help

If you continue to experience issues:

1. Check the API documentation: http://localhost:8000/docs
2. Review system logs in the `logs/` directory
3. Check the dashboard for system status: http://localhost:8000/dashboard
4. Contact the network operations team with:
   - Error messages and stack traces
   - Action payloads that failed
   - Timestamps of failures
   - Your API client version

## Next Steps

- Explore the [API Documentation](api_documentation.md) for detailed endpoint reference
- Review [Deployment Guide](deployment_guide.md) for production setup
- Check [Troubleshooting Guide](troubleshooting_guide.md) for common issues
- Visit the interactive API docs at http://localhost:8000/docs
