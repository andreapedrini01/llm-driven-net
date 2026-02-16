# Dependencies Guide

This document describes all dependencies used in the LLM Integration Module and how to manage them.

## Core Dependencies

### Web Framework
- **fastapi** (>=0.104.1) - Modern, fast web framework for building APIs with automatic documentation
- **uvicorn[standard]** (>=0.24.0) - ASGI server for running FastAPI applications with high performance
- **pydantic** (>=2.5.0) - Data validation using Python type annotations

### HTTP Client
- **httpx** (>=0.25.2) - Async HTTP client for external API calls

### LLM Integration
- **openai** (>=1.54.0) - Official OpenAI Python client for ChatGPT API integration

### Testing
- **hypothesis** (>=6.119.4) - Property-based testing framework for comprehensive test coverage
- **pytest** (>=8.3.4) - Testing framework
- **pytest-asyncio** (>=0.24.0) - Async support for pytest

### Logging and Monitoring
- **structlog** (>=24.5.0) - Structured logging with JSON output
- **prometheus-client** (>=0.20.0) - Prometheus metrics exporter

### Configuration
- **python-dotenv** (>=1.0.0) - Environment variable management from .env files

### File System
- **watchdog** (>=3.0.0) - File system event monitoring

### Type Checking
- **typing-extensions** (>=4.5.0) - Backported type hints

### Authentication and Security
- **python-jose[cryptography]** (>=3.3.0) - JWT token creation and verification
- **passlib[bcrypt]** (>=1.7.4) - Password hashing using bcrypt
- **python-multipart** (>=0.0.6) - Multipart form data parsing

## Dependency Files

The project uses different files to manage dependencies:

### 1. `requirements.txt` (Production)

Contains minimum dependencies needed to run the application in production.

```bash
pip install -r requirements.txt
```

### 2. `requirements-dev.txt` (Development)

Includes `requirements.txt` plus additional development tools:
- **black** - Automatic code formatting
- **flake8** - Linting
- **mypy** - Static type checking
- **pytest-cov** - Test coverage
- **mkdocs** - Documentation generation

```bash
pip install -r requirements-dev.txt
```

### 3. `requirements-lock.txt` (Exact Versions)

Contains all dependencies with exact versions (generated with `pip freeze`).

Useful for:
- Guaranteeing exact environment reproducibility
- Production deployment
- Debugging version-specific issues

```bash
pip install -r requirements-lock.txt
```

## Installation

### Upgrade pip (Recommended)

Before installing dependencies, upgrade pip to the latest version:

```bash
python -m pip install --upgrade pip
```

### Option 1: Standard Installation (Recommended)

Install production dependencies:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### Option 2: Development Installation

Install development dependencies including testing and linting tools:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install development dependencies
pip install -r requirements-dev.txt
```

### Option 3: Exact Installation (Guaranteed Reproducibility)

Install exact versions for production deployment:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install exact versions
pip install -r requirements-lock.txt
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

**Required configuration**:
```env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4-turbo
```

**Documentation**: [platform.openai.com/docs](https://platform.openai.com/docs)

### Authentication Stack

The authentication system uses:
- **python-jose**: JWT token creation and verification
- **bcrypt**: Secure password hashing (via passlib)
- **python-multipart**: Form data parsing for login endpoints

### Testing Framework

The testing stack includes:
- **pytest**: Main testing framework
- **pytest-asyncio**: Async test support
- **hypothesis**: Property-based testing for validating system correctness properties

### Monitoring and Logging

- **structlog**: Provides structured logging with JSON output
- **prometheus-client**: Exposes metrics for Prometheus monitoring

## Updating Dependencies

### Update Single Dependency

```bash
# Update specific dependency
pip install --upgrade openai

# Update requirements-lock.txt
pip freeze > requirements-lock.txt
```

### Update All Dependencies

```bash
# Update all dependencies to latest compatible versions
pip install --upgrade -r requirements.txt

# Update requirements-lock.txt
pip freeze > requirements-lock.txt
```

**Warning**: Test thoroughly after updating dependencies, especially for major version changes.

### Check Outdated Dependencies

```bash
# Show dependencies with available updates
pip list --outdated
```

## Dependency Verification

### Verify Installation

```bash
# Verify all dependencies are installed
python scripts/verify_installation.py
```

### Verify Versions

```bash
# Show all installed dependencies
pip list

# Show information about specific dependency
pip show openai
```

### Verify Conflicts

```bash
# Verify no conflicts between dependencies
pip check
```

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

**Option 1: Clear pip cache and reinstall**
```bash
pip cache purge
pip uninstall -r requirements.txt -y
pip install -r requirements.txt
```

**Option 2: Create new clean virtual environment**
```bash
# Deactivate current environment
deactivate

# Remove old virtual environment
rm -rf venv  # Linux/Mac
rmdir /s venv  # Windows

# Create new virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

### Missing Dependencies

If a module is not found:

```bash
# Verify it's in requirements.txt
grep <module-name> requirements.txt

# Install manually
pip install <module-name>

# Update requirements-lock.txt
pip freeze > requirements-lock.txt
```

### Network Issues

If installation fails due to network issues:

```bash
# Increase timeout
pip install -r requirements.txt --timeout=300

# Use alternative mirror
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## Best Practices

1. **Always use virtual environment**: Never install dependencies globally
2. **Update requirements-lock.txt**: After every dependency change
3. **Test after updates**: Run `pytest` after every update
4. **Document custom dependencies**: If you add new dependencies, document them
5. **Verify compatibility**: Before updating in production, test in development
6. **Keep dependencies updated**: Regularly update to get security patches
7. **Pin versions in production**: Use exact versions for reproducibility

## Dependencies by Environment

### Local Development

```bash
pip install -r requirements-dev.txt
```

Includes development, testing and debugging tools.

### Testing/CI

```bash
pip install -r requirements.txt
```

Includes only dependencies needed to run tests.

### Production

```bash
pip install -r requirements-lock.txt
```

Uses exact versions to guarantee stability.

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

## Installation Checklist

Before considering installation complete:

- [ ] Virtual environment created and activated
- [ ] Dependencies installed without errors
- [ ] `pip check` shows no conflicts
- [ ] `python scripts/verify_installation.py` passes all checks
- [ ] Tests executed successfully: `pytest`
- [ ] Application can start: `python -m src.main`

## License Information

All dependencies are open source with permissive licenses:
- FastAPI: MIT License
- OpenAI: MIT License
- Pydantic: MIT License
- Most others: MIT or Apache 2.0

Check individual package licenses for details.

## Related Documentation

- **Installation Guide**: See [INSTALLATION.md](../INSTALLATION.md) for detailed setup instructions
- **Testing Guide**: See [TESTING.md](TESTING.md) for information about test dependencies
- **Troubleshooting**: See [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) for dependency-related issues

## Support

For dependency-related issues:
1. Check this document for common solutions
2. Consult [INSTALLATION.md](../INSTALLATION.md) for detailed instructions
3. Run `python scripts/verify_installation.py` to diagnose issues
4. Check the package documentation for specific dependencies
5. Search for similar issues on GitHub
