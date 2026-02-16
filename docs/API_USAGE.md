# API Usage Guide

This guide explains how to use the LLM Integration Module REST API and WebSocket interface.

**New to the project?** See the [Quick Start Guide](QUICK_START.md) to get the application running first.

## Base URL

```
http://localhost:8080/api/v1
```

## Authentication

All API endpoints (except `/auth/login`) require authentication using JWT Bearer tokens.

### Login

Get an access token by authenticating with username and password:

```bash
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### Default Users

- **admin** / admin123 - Full access (read, write, admin)
- **operator** / operator123 - Read and write access
- **viewer** / viewer123 - Read-only access

**Important**: Change these passwords in production via environment variables!

### Using the Token

Include the token in the `Authorization` header for all subsequent requests:

```bash
curl -X GET http://localhost:8080/api/v1/intents/123/status \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## API Endpoints

### Submit Intent

Submit a natural language intent for processing:

```bash
curl -X POST http://localhost:8080/api/v1/intents \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Create a network slice for IoT devices with 100 Mbps bandwidth",
    "user_id": "admin",
    "priority": 5
  }'
```

Response (success):
```json
{
  "intent_id": "intent-123abc",
  "status": "completed",
  "message": "Intent processed successfully",
  "confidence": 0.95,
  "clarification_needed": false
}
```

Response (clarification needed):
```json
{
  "intent_id": "intent-456def",
  "status": "clarification_needed",
  "message": "Intent requires clarification",
  "confidence": 0.65,
  "clarification_needed": true,
  "clarification_questions": [
    "Which switches should be included in the IoT slice?",
    "What is the maximum latency requirement?"
  ]
}
```

### Get Intent Status

Check the status of a submitted intent:

```bash
curl -X GET http://localhost:8080/api/v1/intents/intent-123abc/status \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Response:
```json
{
  "intent_id": "intent-123abc",
  "status": "completed",
  "actions_generated": 5,
  "actions_validated": 5,
  "actions_executed": 5,
  "errors": null
}
```

### Get Current User Info

Get information about the currently authenticated user:

```bash
curl -X GET http://localhost:8080/api/v1/auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Response:
```json
{
  "username": "admin",
  "role": "admin",
  "permissions": ["read", "write", "admin"]
}
```

### Refresh Token

Refresh your access token before it expires:

```bash
curl -X POST http://localhost:8080/api/v1/auth/refresh \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

## Health Check Endpoints

### Basic Health Check

```bash
curl http://localhost:8080/health
```

Response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "components": {
    "api": "healthy"
  }
}
```

### Readiness Check

Check if all components are ready:

```bash
curl http://localhost:8080/health/ready
```

Response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "components": {
    "api": "healthy",
    "chatgpt_api": "healthy",
    "network_state": "healthy"
  }
}
```

### Liveness Check

Simple ping to check if the service is alive:

```bash
curl http://localhost:8080/health/live
```

Response:
```json
{
  "status": "alive"
}
```

## WebSocket Interface

Connect to the WebSocket endpoint for real-time updates:

```
ws://localhost:8080/api/v1/ws
```

### JavaScript Example

```javascript
const ws = new WebSocket('ws://localhost:8080/api/v1/ws');

// Authenticate after connection
ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'auth',
    token: 'YOUR_ACCESS_TOKEN'
  }));
};

// Handle authentication response
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'auth_success') {
    console.log('WebSocket authenticated');
    
    // Subscribe to topics
    ws.send(JSON.stringify({
      type: 'subscribe',
      topics: ['intents', 'anomalies', 'alerts']
    }));
  }
  
  if (data.type === 'intent_processed') {
    console.log('Intent processed:', data.intent_id);
  }
  
  if (data.type === 'anomaly_detected') {
    console.log('Anomaly detected:', data);
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('WebSocket connection closed');
};
```

### Python Example

```python
import asyncio
import websockets
import json

async def connect_websocket():
    uri = "ws://localhost:8080/api/v1/ws"
    
    async with websockets.connect(uri) as websocket:
        # Authenticate
        await websocket.send(json.dumps({
            "type": "auth",
            "token": "YOUR_ACCESS_TOKEN"
        }))
        
        # Wait for auth response
        response = await websocket.recv()
        data = json.loads(response)
        
        if data["type"] == "auth_success":
            print("WebSocket authenticated")
            
            # Subscribe to topics
            await websocket.send(json.dumps({
                "type": "subscribe",
                "topics": ["intents", "anomalies", "alerts"]
            }))
            
            # Listen for messages
            async for message in websocket:
                data = json.loads(message)
                print(f"Received: {data}")

asyncio.run(connect_websocket())
```

### WebSocket Message Types

**Client to Server:**
- `auth` - Authenticate the connection
- `subscribe` - Subscribe to specific topics
- `unsubscribe` - Unsubscribe from topics

**Server to Client:**
- `auth_success` - Authentication successful
- `auth_failed` - Authentication failed
- `subscribed` - Subscription confirmed
- `intent_processed` - Intent processing completed
- `anomaly_detected` - Network anomaly detected
- `alert` - System alert

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

Common HTTP status codes:
- `400` - Bad Request (invalid input)
- `401` - Unauthorized (missing or invalid token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found (resource doesn't exist)
- `500` - Internal Server Error (server-side error)

## Rate Limiting

The API implements rate limiting to prevent abuse:
- Default: 60 requests per minute per user
- Exceeding the limit returns `429 Too Many Requests`

## Security Best Practices

1. **Change default passwords** - Set custom passwords via environment variables
2. **Use HTTPS in production** - Never send tokens over unencrypted connections
3. **Rotate JWT secret** - Generate a secure random key for `JWT_SECRET_KEY`
4. **Token expiration** - Tokens expire after 60 minutes by default
5. **Secure storage** - Store tokens securely (e.g., httpOnly cookies, secure storage)

## Interactive API Documentation

FastAPI provides interactive API documentation:

- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

These interfaces allow you to test API endpoints directly from your browser.

## Related Documentation

- [Quick Start Guide](QUICK_START.md) - Get the application running in under 10 minutes
- [Installation Guide](INSTALLATION.md) - Comprehensive installation instructions
- [Troubleshooting](TROUBLESHOOTING.md) - Solutions to common issues
- [Deployment Guide](deployment/DEPLOYMENT_GUIDE.md) - Deploy to production environments
- [Architecture](deployment/ARCHITECTURE.md) - System architecture and design details
