# Quick Start Guide

Get the LLM Integration Module running in under 10 minutes.

## Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- OpenAI API key ([Get one here](https://platform.openai.com/api-keys))

## Installation Steps

### 1. Clone the Repository

```bash
git clone <repository-url>
cd llm-driven-net
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env      # Linux/macOS
copy .env.example .env    # Windows
```

Edit `.env` and set your OpenAI API key:

```env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o-mini
```

### 5. Run the Server

```bash
python -m src.main
```

The server will start on `http://localhost:8080`

## Verification

### 1. Check Server Status

You should see output like:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
```

### 2. Test the Health Endpoint

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

### 3. Access Interactive Documentation

- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

## Next Steps

- **Detailed Setup**: See [Installation Guide](INSTALLATION.md) for comprehensive installation instructions
- **API Documentation**: See [API Usage Guide](API_USAGE.md) to learn how to use the API
- **Troubleshooting**: See [Troubleshooting Guide](TROUBLESHOOTING.md) if you encounter any issues

## Quick Troubleshooting

### Python not found
```bash
# Verify Python installation
python --version
python3 --version
```

If not installed, download from [python.org](https://www.python.org/downloads/)

### Port 8080 already in use

Change the port in `.env`:
```env
API_PORT=8081
```

### API key error

Verify your `.env` file contains a valid OpenAI API key:
```bash
cat .env | grep OPENAI_API_KEY  # Linux/macOS
type .env | findstr OPENAI_API_KEY  # Windows
```

For more help, see the [Troubleshooting Guide](TROUBLESHOOTING.md).

