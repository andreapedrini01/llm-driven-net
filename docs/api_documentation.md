# Northbound Script Generator - API Documentation

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [API Endpoints](#api-endpoints)
4. [Action Types](#action-types)
5. [Error Handling](#error-handling)
6. [Rate Limiting](#rate-limiting)
7. [Integration Examples](#integration-examples)
8. [Best Practices](#best-practices)

## Overview

The Northbound Script Generator API provides a REST interface for submitting and managing network actions that are applied to ComnetsEMU/RYU controlled networks. The API is designed for integration with Large Language Models (LLMs) and other automation systems.

**Base URL:** `http://localhost:8000` (development) or `https://api.example.com` (production)

**API Version:** v1

**Interactive Documentation:**
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Authentication

### JWT Token Authentication

Most API endpoints require JWT token authentication. Obtain a token by logging in:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "your-password"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

Use the access token in subsequent requests:

```bash
curl -X GET http://localhost:8000/api/v1/actions \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### API Key Authentication

For LLM integrations and automated systems, use API keys:

```bash
curl -X GET http://localhost:8000/api/v1/actions \
  -H "X-API-Key: your-api-key-here"
```

**Obtaining an API Key:**

1. Login to the web dashboard
2. Navigate to Settings > API Keys
3. Click "Generate New API Key"
4. Copy and securely store the key (it won't be shown again)

### Multi-Factor Authentication (MFA)

Admin users can enable MFA for enhanced security:

1. Enable MFA: `POST /api/v1/auth/mfa/enable`
2. Scan QR code with authenticator app
3. Verify with TOTP code: `POST /api/v1/auth/mfa/verify`

When MFA is enabled, include the TOTP code in login requests:

```json
{
  "username": "admin",
  "password": "your-password",
  "totp_code": "123456"
}
```

## API Endpoints

### Health Check

**Endpoint:** `GET /health`

**Authentication:** Not required

**Description:** Check API and service health status

**Example:**
```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0",
  "services": {
    "northbound": "healthy",
    "api_gateway": "healthy",
    "ryu_controller": "healthy",
    "database": "healthy"
  }
}
```

### Submit Action

**Endpoint:** `POST /api/v1/actions`

**Authentication:** Required

**Description:** Submit a network action for processing

**Request Body:**
```json
{
  "type": "flow_rule",
  "target": "switch-1",
  "parameters": {
    "operation": "add",
    "match": {
      "in_port": 1,
      "eth_type": 2048,
      "ipv4_dst": "10.0.0.1/32"
    },
    "actions": ["output:2"],
    "priority": 100
  },
  "priority": 5,
  "timeout": 60,
  "description": "Route traffic to host 10.0.0.1"
}
```

**Response:**
```json
{
  "action_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Action submitted successfully",
  "estimated_completion": "2024-01-15T10:31:00Z"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/actions \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "flow_rule",
    "target": "switch-1",
    "parameters": {
      "operation": "add",
      "match": {"in_port": 1},
      "actions": ["output:2"]
    }
  }'
```

### Get Action Status

**Endpoint:** `GET /api/v1/actions/{action_id}`

**Authentication:** Required

**Description:** Retrieve the status of a specific action

**Example:**
```bash
curl http://localhost:8000/api/v1/actions/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{
  "action_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:45Z",
  "created_by": "admin",
  "result": {
    "success": true,
    "flow_id": "flow-12345",
    "applied_at": "2024-01-15T10:30:45Z"
  }
}
```

### List Actions

**Endpoint:** `GET /api/v1/actions`

**Authentication:** Required

**Description:** List all actions with optional filtering

**Query Parameters:**
- `status_filter`: Filter by status (pending/executing/completed/failed)
- `limit`: Maximum number of results (default: 100)
- `offset`: Pagination offset (default: 0)

**Example:**
```bash
curl "http://localhost:8000/api/v1/actions?status_filter=completed&limit=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
[
  {
    "action_id": "550e8400-e29b-41d4-a716-446655440000",
    "type": "flow_rule",
    "target": "switch-1",
    "status": "completed",
    "created_at": "2024-01-15T10:30:00Z",
    "created_by": "admin"
  }
]
```

### Cancel Action

**Endpoint:** `DELETE /api/v1/actions/{action_id}`

**Authentication:** Required

**Description:** Cancel a pending or executing action

**Example:**
```bash
curl -X DELETE http://localhost:8000/api/v1/actions/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{
  "message": "Action cancelled successfully"
}
```

### Submit Batch Actions

**Endpoint:** `POST /api/v1/actions/batch`

**Authentication:** Required

**Description:** Submit multiple actions in a single request

**Request Body:**
```json
{
  "actions": [
    {
      "type": "flow_rule",
      "target": "switch-1",
      "parameters": {"operation": "add", "match": {"in_port": 1}, "actions": ["output:2"]}
    },
    {
      "type": "flow_rule",
      "target": "switch-2",
      "parameters": {"operation": "add", "match": {"in_port": 1}, "actions": ["output:3"]}
    }
  ]
}
```

**Response:**
```json
{
  "batch_id": "batch-550e8400-e29b-41d4-a716-446655440000",
  "action_ids": [
    "550e8400-e29b-41d4-a716-446655440001",
    "550e8400-e29b-41d4-a716-446655440002"
  ],
  "total_actions": 2,
  "message": "Batch actions submitted successfully"
}
```

### Get Metrics

**Endpoint:** `GET /metrics`

**Authentication:** Not required

**Description:** Get Prometheus-style metrics

**Example:**
```bash
curl http://localhost:8000/metrics
```

**Response:**
```
# HELP northbound_actions_total Total number of actions processed
# TYPE northbound_actions_total counter
northbound_actions_total 1523
# HELP northbound_actions_by_status Actions by status
# TYPE northbound_actions_by_status gauge
northbound_actions_by_status{status="completed"} 1450
northbound_actions_by_status{status="failed"} 73
```

## Action Types

### Flow Rule Actions

Configure OpenFlow rules on switches.

**Type:** `flow_rule`

**Parameters:**
- `operation`: "add", "modify", or "delete"
- `match`: Match criteria (in_port, eth_type, ipv4_src, ipv4_dst, etc.)
- `actions`: List of actions (output:port, drop, set_field, etc.)
- `priority`: Rule priority (0-65535)
- `idle_timeout`: Idle timeout in seconds (0 = no timeout)
- `hard_timeout`: Hard timeout in seconds (0 = no timeout)

**Example:**
```json
{
  "type": "flow_rule",
  "target": "switch-1",
  "parameters": {
    "operation": "add",
    "match": {
      "in_port": 1,
      "eth_type": 2048,
      "ipv4_dst": "10.0.0.1/32"
    },
    "actions": ["output:2"],
    "priority": 100,
    "idle_timeout": 0,
    "hard_timeout": 300
  }
}
```

### Topology Change Actions

Modify network topology (add/remove switches, links, hosts).

**Type:** `topology_change`

**Parameters:**
- `operation`: "add", "remove", or "modify"
- `element_type`: "switch", "link", or "host"
- `element_id`: Identifier of the element
- `properties`: Element-specific properties

**Example - Add Switch:**
```json
{
  "type": "topology_change",
  "target": "topology",
  "parameters": {
    "operation": "add",
    "element_type": "switch",
    "element_id": "switch-3",
    "properties": {
      "dpid": "0000000000000003",
      "protocols": ["OpenFlow13"]
    }
  }
}
```

**Example - Add Link:**
```json
{
  "type": "topology_change",
  "target": "topology",
  "parameters": {
    "operation": "add",
    "element_type": "link",
    "element_id": "link-1-2",
    "properties": {
      "src_switch": "switch-1",
      "src_port": 3,
      "dst_switch": "switch-2",
      "dst_port": 1,
      "bandwidth_mbps": 1000
    }
  }
}
```

### QoS Policy Actions

Configure Quality of Service policies.

**Type:** `qos_policy`

**Parameters:**
- `bandwidth_limit_mbps`: Bandwidth limit in Mbps
- `latency_limit_ms`: Maximum latency in milliseconds
- `packet_loss_limit`: Maximum packet loss ratio (0-1)
- `dscp_marking`: DSCP marking value (0-63)

**Example:**
```json
{
  "type": "qos_policy",
  "target": "switch-1:port-2",
  "parameters": {
    "bandwidth_limit_mbps": 100,
    "latency_limit_ms": 50,
    "packet_loss_limit": 0.01,
    "dscp_marking": 46
  },
  "description": "VoIP QoS policy"
}
```

### Network Configuration Actions

General network configuration changes.

**Type:** `network_config`

**Parameters:** Varies based on configuration type

**Example - Update Controller:**
```json
{
  "type": "network_config",
  "target": "controller",
  "parameters": {
    "config_type": "controller_settings",
    "settings": {
      "max_flows_per_switch": 10000,
      "flow_timeout_default": 300,
      "enable_packet_in_filtering": true
    }
  }
}
```

## Error Handling

### Error Response Format

All errors follow a consistent format:

```json
{
  "error": "Detailed error message",
  "status_code": 400,
  "timestamp": "2024-01-15T10:30:00Z",
  "details": {
    "field": "parameters.match",
    "issue": "Missing required field 'in_port'"
  }
}
```

### HTTP Status Codes

- `200 OK`: Request successful
- `202 Accepted`: Action submitted successfully
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error
- `503 Service Unavailable`: Service temporarily unavailable

### Common Error Scenarios

**Invalid Action Parameters:**
```json
{
  "error": "Action validation failed",
  "status_code": 400,
  "details": {
    "issues": [
      "Missing required parameter: match",
      "Invalid action type: invalid_action"
    ]
  }
}
```

**Authentication Failed:**
```json
{
  "error": "Invalid credentials",
  "status_code": 401
}
```

**Rate Limit Exceeded:**
```json
{
  "error": "Rate limit exceeded",
  "status_code": 429,
  "details": {
    "limit": 100,
    "window": "1 minute",
    "retry_after": 45
  }
}
```

## Rate Limiting

Rate limits are applied per user/API key:

- **Standard Users:** 100 requests/minute
- **Admin Users:** 1000 requests/minute
- **Batch Operations:** Count as 1 request regardless of action count

**Rate Limit Headers:**

Responses include rate limit information:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642248600
```

**Handling Rate Limits:**

When rate limited, wait for the time specified in `Retry-After` header or `X-RateLimit-Reset`.

## Integration Examples

### Python Integration

```python
import requests
from typing import Dict, Any

class NorthboundClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
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
    
    def wait_for_completion(self, action_id: str, timeout: int = 300) -> Dict[str, Any]:
        """Wait for action to complete."""
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_action_status(action_id)
            if status["status"] in ["completed", "failed", "cancelled"]:
                return status
            time.sleep(2)
        
        raise TimeoutError(f"Action {action_id} did not complete within {timeout}s")

# Usage
client = NorthboundClient("http://localhost:8000", "your-api-key")

# Submit flow rule
action = {
    "type": "flow_rule",
    "target": "switch-1",
    "parameters": {
        "operation": "add",
        "match": {"in_port": 1},
        "actions": ["output:2"]
    }
}

result = client.submit_action(action)
print(f"Action submitted: {result['action_id']}")

# Wait for completion
final_status = client.wait_for_completion(result['action_id'])
print(f"Action completed: {final_status}")
```

### JavaScript/Node.js Integration

```javascript
const axios = require('axios');

class NorthboundClient {
  constructor(baseUrl, apiKey) {
    this.baseUrl = baseUrl;
    this.client = axios.create({
      baseURL: baseUrl,
      headers: {
        'X-API-Key': apiKey,
        'Content-Type': 'application/json'
      }
    });
  }

  async submitAction(action) {
    const response = await this.client.post('/api/v1/actions', action);
    return response.data;
  }

  async getActionStatus(actionId) {
    const response = await this.client.get(`/api/v1/actions/${actionId}`);
    return response.data;
  }

  async waitForCompletion(actionId, timeout = 300000) {
    const startTime = Date.now();
    
    while (Date.now() - startTime < timeout) {
      const status = await this.getActionStatus(actionId);
      if (['completed', 'failed', 'cancelled'].includes(status.status)) {
        return status;
      }
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
    
    throw new Error(`Action ${actionId} did not complete within ${timeout}ms`);
  }
}

// Usage
const client = new NorthboundClient('http://localhost:8000', 'your-api-key');

const action = {
  type: 'flow_rule',
  target: 'switch-1',
  parameters: {
    operation: 'add',
    match: { in_port: 1 },
    actions: ['output:2']
  }
};

client.submitAction(action)
  .then(result => {
    console.log(`Action submitted: ${result.action_id}`);
    return client.waitForCompletion(result.action_id);
  })
  .then(finalStatus => {
    console.log('Action completed:', finalStatus);
  })
  .catch(error => {
    console.error('Error:', error.message);
  });
```

### cURL Examples

**Submit Flow Rule:**
```bash
curl -X POST http://localhost:8000/api/v1/actions \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "flow_rule",
    "target": "switch-1",
    "parameters": {
      "operation": "add",
      "match": {"in_port": 1, "eth_type": 2048},
      "actions": ["output:2"],
      "priority": 100
    },
    "description": "Forward IPv4 traffic from port 1 to port 2"
  }'
```

**Check Action Status:**
```bash
ACTION_ID="550e8400-e29b-41d4-a716-446655440000"
curl http://localhost:8000/api/v1/actions/$ACTION_ID \
  -H "X-API-Key: your-api-key"
```

**Submit Batch Actions:**
```bash
curl -X POST http://localhost:8000/api/v1/actions/batch \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "actions": [
      {
        "type": "flow_rule",
        "target": "switch-1",
        "parameters": {"operation": "add", "match": {"in_port": 1}, "actions": ["output:2"]}
      },
      {
        "type": "flow_rule",
        "target": "switch-2",
        "parameters": {"operation": "add", "match": {"in_port": 1}, "actions": ["output:3"]}
      }
    ]
  }'
```

## Best Practices

### 1. Use Batch Operations for Multiple Actions

When submitting multiple related actions, use the batch endpoint to reduce overhead:

```python
# Good - Single batch request
client.submit_batch([action1, action2, action3])

# Avoid - Multiple individual requests
client.submit_action(action1)
client.submit_action(action2)
client.submit_action(action3)
```

### 2. Implement Exponential Backoff for Retries

When retrying failed requests, use exponential backoff:

```python
import time

def submit_with_retry(client, action, max_retries=3):
    for attempt in range(max_retries):
        try:
            return client.submit_action(action)
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt
            time.sleep(wait_time)
```

### 3. Validate Actions Before Submission

Validate action parameters locally before submitting to reduce errors:

```python
def validate_flow_rule(action):
    required_fields = ['operation', 'match', 'actions']
    for field in required_fields:
        if field not in action['parameters']:
            raise ValueError(f"Missing required field: {field}")
    
    if action['parameters']['operation'] not in ['add', 'modify', 'delete']:
        raise ValueError(f"Invalid operation: {action['parameters']['operation']}")
```

### 4. Monitor Action Status

Always check action status after submission:

```python
result = client.submit_action(action)
final_status = client.wait_for_completion(result['action_id'])

if final_status['status'] == 'failed':
    print(f"Action failed: {final_status.get('error')}")
    # Handle failure
elif final_status['status'] == 'completed':
    print(f"Action completed successfully")
    # Process result
```

### 5. Use Descriptive Action Descriptions

Include meaningful descriptions for better tracking and debugging:

```python
action = {
    "type": "flow_rule",
    "target": "switch-1",
    "parameters": {...},
    "description": "Route VoIP traffic from subnet 10.0.1.0/24 to QoS-enabled port"
}
```

### 6. Handle Rate Limits Gracefully

Respect rate limits and implement proper handling:

```python
try:
    result = client.submit_action(action)
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 429:
        retry_after = int(e.response.headers.get('Retry-After', 60))
        print(f"Rate limited. Retrying after {retry_after} seconds")
        time.sleep(retry_after)
        result = client.submit_action(action)
    else:
        raise
```

### 7. Secure API Keys

- Never commit API keys to version control
- Use environment variables or secure vaults
- Rotate keys regularly
- Use different keys for different environments

```python
import os

api_key = os.environ.get('NORTHBOUND_API_KEY')
if not api_key:
    raise ValueError("NORTHBOUND_API_KEY environment variable not set")

client = NorthboundClient(base_url, api_key)
```

### 8. Log All API Interactions

Maintain logs of API interactions for debugging and auditing:

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def submit_action_with_logging(client, action):
    logger.info(f"Submitting action: {action['type']} to {action['target']}")
    try:
        result = client.submit_action(action)
        logger.info(f"Action submitted successfully: {result['action_id']}")
        return result
    except Exception as e:
        logger.error(f"Failed to submit action: {e}")
        raise
```

## Support and Resources

- **Interactive API Documentation:** http://localhost:8000/docs
- **API Reference:** http://localhost:8000/redoc
- **Web Dashboard:** http://localhost:8000/dashboard
- **Health Check:** http://localhost:8000/health
- **Metrics:** http://localhost:8000/metrics

For additional support, contact the network operations team.
