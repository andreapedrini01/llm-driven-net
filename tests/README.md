# Test Suite

All project tests live under this directory, organized by test type.

## Structure

```
tests/
├── conftest.py          # Shared fixtures and Hypothesis configuration
├── unit/                # Unit tests for all modules
├── property/            # Property-based tests (Hypothesis)
├── integration/         # End-to-end and integration tests
├── mocks/               # ChatGPT mock client for offline testing
└── examples/            # Example tests and usage patterns
```

## Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# Property-based tests only
pytest tests/property/

# Integration tests only
pytest tests/integration/

# Specific file
pytest tests/unit/test_validator.py -v
```

## Markers

```bash
pytest -m unit          # Unit tests
pytest -m property      # Property-based tests
pytest -m integration   # Integration tests
pytest -m "not slow"    # Exclude slow tests
```
