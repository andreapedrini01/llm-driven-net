# Dependency Management

This document explains how to manage project dependencies.

## Dependency Files

The project uses different files to manage dependencies:

### 1. `requirements.txt` (Production)

Contains minimum dependencies needed to run the application in production.

```bash
pip install -r requirements.txt
```

**Main dependencies**:
- `fastapi` - Web framework for REST API
- `pydantic` - Data validation and serialization
- `openai` - Official client for ChatGPT API
- `httpx` - Asynchronous HTTP client
- `hypothesis` - Property-based testing
- `pytest` - Testing framework
- `structlog` - Structured logging
- `python-dotenv` - Environment variable management

### 2. `requirements-dev.txt` (Development)

Includes `requirements.txt` plus additional development tools.

```bash
pip install -r requirements-dev.txt
```

**Additional dependencies**:
- `black` - Automatic code formatting
- `flake8` - Linting
- `mypy` - Static type checking
- `pytest-cov` - Test coverage
- `mkdocs` - Documentation generation

### 3. `requirements-lock.txt` (Exact Versions)

Contains all dependencies with exact versions (generated with `pip freeze`).

Useful for:
- Guaranteeing exact environment reproducibility
- Production deployment
- Debugging version-specific issues

```bash
pip install -r requirements-lock.txt
```

## Installation on New Device

### Option 1: Standard Installation (Recommended)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### Option 2: Exact Installation (Guaranteed Reproducibility)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install exact versions
pip install -r requirements-lock.txt
```

### Option 3: Development Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install development dependencies
pip install -r requirements-dev.txt
```

## Updating Dependencies

### Update Single Dependency

```bash
# Update specific dependency
pip install --upgrade openai

# Update pip freeze
pip freeze > requirements-lock.txt
```

### Update All Dependencies

```bash
# Update all dependencies
pip install --upgrade -r requirements.txt

# Update pip freeze
pip freeze > requirements-lock.txt
```

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
# Verify conflicts between dependencies
pip check
```

## Critical Dependencies

### ChatGPT API (OpenAI)

**Package**: `openai >= 1.54.0`

**Required configuration**:
```env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4-turbo
```

**Documentation**: [platform.openai.com/docs](https://platform.openai.com/docs)

### FastAPI

**Package**: `fastapi >= 0.104.1`

Web framework for building high-performance REST APIs.

### Hypothesis

**Package**: `hypothesis >= 6.119.4`

Framework for property-based testing, used to validate system correctness properties.

## Troubleshooting

### Version Conflicts

If you encounter version conflicts:

```bash
# Create new clean virtual environment
deactivate
rm -rf venv  # Linux/Mac
rmdir /s venv  # Windows

python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Reinstall
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

## Installation Checklist

Before considering installation complete:

- [ ] Virtual environment created and activated
- [ ] Dependencies installed without errors
- [ ] `pip check` shows no conflicts
- [ ] `python scripts/verify_installation.py` passes all checks
- [ ] Tests executed successfully: `pytest`
- [ ] Application can start: `python -m src.main`

## Support

For dependency issues:

1. Consult this document
2. Verify `INSTALL.md` for detailed instructions
3. Run `python scripts/verify_installation.py`
4. Check error logs
