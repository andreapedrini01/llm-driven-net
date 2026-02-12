# Dependencies Guide

This document describes all dependencies used in the LLM Integration Module.

## Core Dependencies

### Web Framework
- **fastapi** (>=0.104.1) - Modern, fast web framework for building APIs
- **uvicorn[standard]** (>=0.24.0) - ASGI server for running FastAPI applications
- **pydantic** (>=2.5.0) - Data validation using Python type annotations

### HTTP Client
- **httpx** (>=0.25.2) - Async HTTP client for external API calls

### LLM Integration
- **openai** (>=1.54.0) - Official OpenAI Python client for ChatGPT API

### Testing
- **hypothesis** (>=6.119.4) - Property-based testing framework
- **pytest** (>=8.3.4) - Testing framework
- **pytest-asyncio** (>=0.24.0) - Async support for pytest

### Logging and Monitoring
- **structlog** (>=24.5.0) - Structured logging
- **prometheus-client** (>=0.20.0) - Prometheus metrics exporter

### Configuration
- **python-dotenv** (>=1.0.0) - Environment variable management from .env files

### File System
- **watchdog** (>=3.0.0) - File system event monitoring

### Type Checking
- **typing-extensions** (>=4.5.0) - Backported type hints

### Authentication and Security
- **python-jose[cryptography]** (>=3.3.0) - JWT token creation and verification
- **passlib[bcrypt]** (>=1.7.4) - Password hashing (uses bcrypt)
- **python-multipart** (>=0.0.6) - Multipart form data parsing

## Installation

### Standard Installation

Install all dependencies:

```bash
pip install -r requirements.txt
```

### Upgrade pip (Recommended)

Before installing dependencies, upgrade pip to the latest version:

```bash
python -m pip install --upgrade pip
```

### Virtual Environment (Recommended)

It's recommended to use a virtual environment:

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Dependency Details

### FastAPI Ecosystem

FastAPI is the core web framework that provides:
- Automatic API documentation (Swagger UI, ReDoc)
- Data validation with Pydantic
- Async support
- WebSocket support
- Dependency injection

Uvicorn is the ASGI server that runs FastAPI applications with high performance.

### OpenAI Client

The `openai` package provides:
- ChatGPT API integration
- Automatic retry logic
- Rate limiting support
- Streaming responses
- Error handling

### Authentication Stack

The authentication system uses:
- **python-jose**: JWT token creation and verification
- **bcrypt**: Secure password hashing (via passlib)
- **python-multipart**: Form data parsing for login endpoints

### Testing Framework

The testing stack includes:
- **pytest**: Main testing framework
- **pytest-asyncio**: Async test support
- **hypothesis**: Property-based testing for comprehensive test coverage

### Monitoring and Logging

- **structlog**: Provides structured logging with JSON output
- **prometheus-client**: Exposes metrics for Prometheus monitoring

## Troubleshooting

### Installation Issues

**Problem**: `pip install` fails with permission errors

**Solution**: Use `--user` flag or virtual environment:
```bash
pip install --user -r requirements.txt
```

**Problem**: `bcrypt` installation fails on Windows

**Solution**: Install Visual C++ Build Tools or use pre-built wheels:
```bash
pip install --only-binary :all: bcrypt
```

**Problem**: `cryptography` installation fails

**Solution**: Install build dependencies:
- Windows: Install Visual C++ Build Tools
- Linux: `sudo apt-get install build-essential libssl-dev libffi-dev python3-dev`
- Mac: `xcode-select --install`

### Version Conflicts

If you encounter version conflicts:

1. **Clear pip cache**:
   ```bash
   pip cache purge
   ```

2. **Reinstall dependencies**:
   ```bash
   pip uninstall -r requirements.txt -y
   pip install -r requirements.txt
   ```

3. **Use specific versions**:
   The `requirements.txt` file specifies minimum versions. If needed, you can pin exact versions.

### Dependency Updates

To update all dependencies to their latest compatible versions:

```bash
pip install --upgrade -r requirements.txt
```

**Warning**: Test thoroughly after updating dependencies, especially for major version changes.

## Production Considerations

### Security

1. **Keep dependencies updated**: Regularly update to get security patches
2. **Use virtual environments**: Isolate dependencies per project
3. **Pin versions in production**: Use exact versions for reproducibility

### Performance

1. **Use uvicorn with workers**: For production, run multiple workers:
   ```bash
   uvicorn src.main:app --workers 4
   ```

2. **Enable uvloop**: Uvicorn[standard] includes uvloop for better performance

3. **Configure connection pools**: Adjust httpx and database connection pools for your load

## Dependency Tree

Main dependency relationships:

```
fastapi
├── pydantic (data validation)
├── starlette (ASGI framework)
└── typing-extensions (type hints)

uvicorn[standard]
├── uvloop (event loop)
├── httptools (HTTP parsing)
└── websockets (WebSocket support)

openai
├── httpx (HTTP client)
├── pydantic (data models)
└── typing-extensions (type hints)

python-jose[cryptography]
├── cryptography (encryption)
├── ecdsa (signatures)
└── rsa (RSA encryption)

passlib[bcrypt]
└── bcrypt (password hashing)

structlog
└── (no major dependencies)

prometheus-client
└── (no major dependencies)

hypothesis
└── (no major dependencies)

pytest
└── pluggy (plugin system)

pytest-asyncio
├── pytest
└── (async support)
```

## License Information

All dependencies are open source with permissive licenses:
- FastAPI: MIT License
- OpenAI: MIT License
- Pydantic: MIT License
- Most others: MIT or Apache 2.0

Check individual package licenses for details.

## Support

For dependency-related issues:
1. Check the package documentation
2. Search for similar issues on GitHub
3. Consult the project's issue tracker

For project-specific issues, see the main README.md.
