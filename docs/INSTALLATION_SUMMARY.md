# Installation Summary

Quick reference for installing and running the LLM Integration Module.

## Prerequisites

- Python 3.8+
- pip (latest version recommended)
- OpenAI API key

## Quick Install

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
copy .env.example .env
# Edit .env and set OPENAI_API_KEY

# 3. Run server
python -m src.main
```

Server will be available at http://localhost:8080

## Dependencies Installed

The `requirements.txt` file installs:

### Core (Required)
- **fastapi** - Web framework
- **uvicorn** - ASGI server
- **pydantic** - Data validation
- **openai** - ChatGPT API client

### Authentication
- **python-jose** - JWT tokens
- **bcrypt** - Password hashing (via passlib)
- **python-multipart** - Form data

### Monitoring
- **prometheus-client** - Metrics
- **structlog** - Structured logging

### Testing
- **hypothesis** - Property-based testing
- **pytest** - Test framework
- **pytest-asyncio** - Async tests

### Utilities
- **httpx** - HTTP client
- **python-dotenv** - Environment variables
- **watchdog** - File monitoring
- **typing-extensions** - Type hints

## Development Dependencies

For development work, install additional tools:

```bash
pip install -r requirements-dev.txt
```

This adds:
- **black** - Code formatter
- **flake8** - Linter
- **mypy** - Type checker
- **pytest-cov** - Test coverage
- **ipython** - Enhanced shell
- And more...

## Verification

After installation, verify everything works:

```bash
# Check Python version
python --version  # Should be 3.8+

# Check pip version
pip --version

# List installed packages
pip list

# Run test script
python test_api_local.py
```

## Common Issues

### bcrypt installation fails (Windows)
```bash
pip install --only-binary :all: bcrypt
```

### Permission errors
```bash
pip install --user -r requirements.txt
```

### Old pip version
```bash
python -m pip install --upgrade pip
```

## File Structure

```
requirements.txt          # Production dependencies
requirements-dev.txt      # Development dependencies
.env.example             # Environment template
.env                     # Your configuration (create this)
```

## Environment Variables

Required in `.env`:
```env
OPENAI_API_KEY=your-key-here
```

Optional (with defaults):
```env
API_HOST=0.0.0.0
API_PORT=8080
OPENAI_MODEL=gpt-4o-mini
JWT_SECRET_KEY=auto-generated
ADMIN_PASSWORD=admin123
```

## Next Steps

1. Read [GETTING_STARTED.md](GETTING_STARTED.md) for detailed setup
2. Review [API_USAGE.md](API_USAGE.md) for API documentation
3. Check [DEPENDENCIES.md](DEPENDENCIES.md) for dependency details

## Support

For issues:
- Check server logs
- Verify `.env` configuration
- Review [GETTING_STARTED.md](GETTING_STARTED.md) troubleshooting section
