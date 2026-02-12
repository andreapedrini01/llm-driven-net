# Test Suite - LLM Integration Module

This folder contains the complete test suite for the LLM integration module.

## 📁 Test Structure

```
tests/
├── unit/           # Unit tests for individual components
├── property/       # Property-based tests with Hypothesis
├── integration/    # End-to-end and integration tests
├── mocks/          # Shared mocks and fixtures
└── examples/       # Test examples and test data
```

## 🧪 Test Types

### Unit Tests (`unit/`)
Unit tests for specific components:
- `test_chatgpt_client.py` - ChatGPT API client
- `test_context_analyzer.py` - Context analyzer
- `test_validator.py` - Action validator
- `test_models.py` - Pydantic data models
- `test_logging.py` - Logging system
- `test_notifications.py` - Notification system
- And others...

**Execution**:
```bash
pytest tests/unit/
```

### Property-Based Tests (`property/`)
Property-based tests using Hypothesis (100+ iterations per test):
- 25 property-based tests that validate correctness properties
- Each test covers a specific property from the design document
- Smart generators for realistic test data

**Execution**:
```bash
pytest tests/property/ -m property
```

**Note**: Property-based tests may take longer (1-5 minutes per test).

### Integration Tests (`integration/`)
End-to-end tests that verify the entire flow:
- `test_end_to_end_integration.py` - Complete E2E test
- `test_integration_suite.py` - Integration suite
- `test_integration.py` - Component integration tests
- `test_api_local.py` - Local API tests

**Execution**:
```bash
pytest tests/integration/
```

### Mocks (`mocks/`)
Shared mocks and fixtures:
- `test_chatgpt_mock.py` - ChatGPT API mock for offline testing
- Common fixtures for all tests

## 🚀 Running Tests

### All Tests
```bash
pytest
```

### Unit Tests Only
```bash
pytest tests/unit/ -v
```

### Property-Based Tests Only
```bash
pytest tests/property/ -m property
```

### Integration Tests Only
```bash
pytest tests/integration/ -v
```

### Specific Test
```bash
pytest tests/unit/test_chatgpt_client.py -v
```

### With Coverage
```bash
pytest --cov=src --cov-report=html
```

## 📊 Test Markers

Tests are organized with pytest markers:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.property` - Property-based tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.slow` - Slow tests (>1 second)

**Execution by marker**:
```bash
pytest -m unit          # Unit tests only
pytest -m property      # Property-based only
pytest -m integration   # Integration only
pytest -m "not slow"    # Exclude slow tests
```

## ⚙️ Configuration

Test configuration is in `pytest.ini` in the project root:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    unit: Unit tests
    property: Property-based tests
    integration: Integration tests
    slow: Slow tests
```

## 🔧 Hypothesis Configuration

Property-based tests use Hypothesis with:
- **Min examples**: 100 iterations per test
- **Max examples**: 1000 iterations (if needed)
- **Database**: `.hypothesis/` (gitignored)
- **Shrinking**: Enabled to find minimal examples

## 📝 Writing New Tests

### Unit Test
```python
# tests/unit/test_my_component.py
import pytest
from src.services.my_component import MyComponent

@pytest.mark.unit
def test_my_component_basic():
    component = MyComponent()
    result = component.process("input")
    assert result == "expected"
```

### Property-Based Test
```python
# tests/property/test_my_properties.py
import pytest
from hypothesis import given, strategies as st
from src.services.my_component import MyComponent

@pytest.mark.property
@given(input_data=st.text(min_size=1))
def test_property_always_returns_string(input_data):
    """Property: Output is always a string"""
    component = MyComponent()
    result = component.process(input_data)
    assert isinstance(result, str)
```

### Integration Test
```python
# tests/integration/test_my_integration.py
import pytest
from src.main import app

@pytest.mark.integration
async def test_full_workflow():
    # Complete workflow test
    pass
```

## 🐛 Debugging Tests

### Verbose Output
```bash
pytest -v -s
```

### Stop at First Failure
```bash
pytest -x
```

### Run Only Failed Tests
```bash
pytest --lf
```

### Debug with PDB
```bash
pytest --pdb
```

## 📈 Coverage Report

After running tests with coverage:

```bash
pytest --cov=src --cov-report=html
```

Open `htmlcov/index.html` in browser to see detailed report.

## 🔍 Property-Based Tests - Covered Properties

| # | Property | File | Status |
|---|-----------|------|--------|
| 1 | Intent parsing completeness | `test_intent_parsing_properties.py` | ✅ |
| 2 | Resource validation consistency | `test_resource_validation_properties.py` | ✅ |
| 3 | Clarification request appropriateness | `test_clarification_properties.py` | ✅ |
| 4 | Action generation completeness | `test_action_generation_properties.py` | ✅ |
| 5 | State data freshness | `test_state_freshness_properties.py` | ✅ |
| 6 | State file reading reliability | `test_state_file_reading_properties.py` | ✅ |
| 7 | Dynamic state adaptation | `test_dynamic_state_adaptation_properties.py` | ✅ |
| 8 | Action validation and formatting | `test_action_validation_properties.py` | ✅ |
| 9 | Conflict detection accuracy | `test_conflict_detection_properties.py` | ✅ |
| 10 | Action sequencing logic | `test_action_sequencing_properties.py` | ✅ |
| 11 | Action traceability | `test_action_traceability_properties.py` | ✅ |
| 12 | Anomaly detection comprehensiveness | `test_anomaly_detection_properties.py` | ✅ |
| 13 | Automatic anomaly mitigation | `test_automatic_anomaly_mitigation_properties.py` | ✅ |
| 14 | Anomaly notification completeness | `test_anomaly_notification_properties.py` | ✅ |
| 15 | Learning system improvement | `test_learning_system_properties.py` | ✅ |
| 16 | Slice configuration completeness | `test_slice_configuration_properties.py` | ✅ |
| 17 | Service continuity preservation | `test_service_continuity_properties.py` | ✅ |
| 18 | Resource allocation fairness | `test_resource_allocation_fairness_properties.py` | ✅ |
| 19 | Resource cleanup completeness | `test_resource_cleanup_properties.py` | ✅ |
| 20 | Dependency update consistency | `test_dependency_update_properties.py` | ✅ |
| 21 | File system resilience | `test_file_system_resilience_properties.py` | ✅ |
| 22 | API resilience | `test_api_resilience_properties.py` | ✅ |
| 23 | Input sanitization security | `test_input_sanitization_properties.py` | ✅ |
| 24 | Error handling completeness | `test_error_handling_properties.py` | ✅ |
| 25 | State recovery reliability | `test_state_recovery_properties.py` | ✅ |

## 📚 Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [Design Document](../.kiro/specs/llm-integration-module/design.md)
- [Testing Guide](../docs/development/TESTING.md)

---

**Note**: Always run tests before committing changes!
