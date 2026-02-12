# Getting Started with LLM Integration Module

This guide will help you set up and run the LLM Integration Module locally.

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- OpenAI API key (for ChatGPT integration)

## Installation

1. **Clone the repository** (if not already done)

2. **Install dependencies:**

```bash
pip install -r requirements.txt
```

This will install all required packages:
- **fastapi** - Web framework
- **uvicorn** - ASGI server
- **pydantic** - Data validation
- **openai** - ChatGPT API client
- **python-jose** - JWT authentication
- **bcrypt** - Password hashing
- **prometheus-client** - Metrics
- **structlog** - Structured logging
- **hypothesis** - Property-based testing
- And more (see requirements.txt for full list)

3. **Configure environment variables:**

Copy the example environment file and edit it:

```bash
copy .env.example .env
```

Edit `.env` and set your configuration:

```env
# Required: Set your OpenAI API key
OPENAI_API_KEY=your-actual-api-key-here

# Optional: Change default passwords (recommended for production)
ADMIN_PASSWORD=your-secure-admin-password
OPERATOR_PASSWORD=your-secure-operator-password
VIEWER_PASSWORD=your-secure-viewer-password

# Optional: Generate a secure JWT secret key
JWT_SECRET_KEY=your-secure-random-key-here
```

**Important**: Never commit your `.env` file with real credentials!

## Running the Server

### Start the API server:

```bash
python -m src.main
```

The server will start on `http://localhost:8080`

You should see output like:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
```

### Access the interactive API documentation:

- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

## Quick Test

### 1. Test the health endpoint:

```bash
curl http://localhost:8080/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "components": {
    "api": "healthy"
  }
}
```

### 2. Login to get an access token:

```bash
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"admin\", \"password\": \"admin123\"}"
```

Expected response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

Save the `access_token` for subsequent requests.

### 3. Test authenticated endpoint:

```bash
curl -X GET http://localhost:8080/api/v1/auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Expected response:
```json
{
  "username": "admin",
  "role": "admin",
  "permissions": ["read", "write", "admin"]
}
```

## Using the Python Test Script

A simple test script is provided to verify the API:

```bash
python test_api_local.py
```

This will test:
- Health endpoint
- Login endpoint
- Basic authentication

## Network State Setup

The module reads network state from a JSON file in the cache folder. To set this up:

1. **Create the cache directory:**

```bash
mkdir cache
```

2. **Create a sample network state file:**

Create `cache/network_state.json` with sample data:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "topology": {
    "switches": [
      {
        "id": "s1",
        "name": "Core Switch 1",
        "status": "active",
        "ports": []
      }
    ],
    "links": [],
    "hosts": []
  },
  "flows": [],
  "slices": [],
  "metrics": {
    "bandwidth": {},
    "latency": {},
    "utilization": {}
  },
  "anomalies": []
}
```

## Submitting an Intent

Once the server is running and you have a token:

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

**Note**: This requires:
- Valid OpenAI API key in `.env`
- Network state file in `cache/network_state.json`

## WebSocket Connection

To test real-time updates via WebSocket, you can use a WebSocket client or the browser console:

```javascript
const ws = new WebSocket('ws://localhost:8080/api/v1/ws');

ws.onopen = () => {
  // Authenticate
  ws.send(JSON.stringify({
    type: 'auth',
    token: 'YOUR_ACCESS_TOKEN'
  }));
};

ws.onmessage = (event) => {
  console.log('Received:', JSON.parse(event.data));
};
```

## Troubleshooting

### Server won't start

- Check if port 8080 is already in use
- Verify all dependencies are installed: `pip list`
- Check for syntax errors in configuration files
- Ensure Python version is 3.8 or higher: `python --version`

### Missing dependencies

If you get "ModuleNotFoundError", install missing packages:

```bash
# Reinstall all dependencies
pip install -r requirements.txt

# Or install specific package
pip install <package-name>
```

### Authentication fails

- Verify you're using the correct username/password from `.env`
- Check that JWT_SECRET_KEY is set in `.env`
- Ensure the token hasn't expired (60 minutes default)

### Intent submission fails

- Verify OPENAI_API_KEY is set correctly in `.env`
- Check that `cache/network_state.json` exists and is valid JSON
- Review server logs for detailed error messages

### ChatGPT API errors

- Verify your API key is valid and has credits
- Check rate limits (default: 60 requests per minute)
- Review OpenAI API status: https://status.openai.com/

### bcrypt/cryptography installation issues

On Windows, if bcrypt or cryptography fail to install:

1. Install Visual C++ Build Tools from Microsoft
2. Or use pre-built wheels:
   ```bash
   pip install --only-binary :all: bcrypt cryptography
   ```

On Linux:
```bash
sudo apt-get install build-essential libssl-dev libffi-dev python3-dev
pip install -r requirements.txt
```

## Development Mode

To run the server in development mode with auto-reload:

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8080
```

## Production Deployment

For production deployment:

1. **Change all default passwords** in `.env`
2. **Generate a secure JWT secret key**
3. **Use HTTPS** (configure reverse proxy like nginx)
4. **Set up proper logging** and monitoring
5. **Configure rate limiting** appropriately
6. **Use a production WSGI server** (already using uvicorn)
7. **Set DEBUG=false** in `.env`

## Next Steps

- Read the [API Usage Guide](API_USAGE.md) for detailed API documentation
- Review the [Design Document](.kiro/specs/llm-integration-module/design.md)
- Check the [Requirements](.kiro/specs/llm-integration-module/requirements.md)

## Support

For issues or questions:
- Check the logs in the console output
- Review the API documentation at http://localhost:8080/docs
- Consult the design and requirements documents
