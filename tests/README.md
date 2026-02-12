# Test Suite - LLM Integration Module

Questa cartella contiene la suite completa di test per il modulo di integrazione LLM.

## 📁 Struttura Test

```
tests/
├── unit/           # Test unitari per componenti individuali
├── property/       # Test property-based con Hypothesis
├── integration/    # Test end-to-end e integrazione
├── mocks/          # Mock e fixture condivisi
└── examples/       # Esempi di test e dati di test
```

## 🧪 Tipi di Test

### Unit Tests (`unit/`)
Test unitari per componenti specifici:
- `test_chatgpt_client.py` - Client ChatGPT API
- `test_context_analyzer.py` - Analizzatore contesto
- `test_validator.py` - Validatore azioni
- `test_models.py` - Modelli dati Pydantic
- `test_logging.py` - Sistema logging
- `test_notifications.py` - Sistema notifiche
- E altri...

**Esecuzione**:
```bash
pytest tests/unit/
```

### Property-Based Tests (`property/`)
Test basati su proprietà usando Hypothesis (100+ iterazioni per test):
- 25 test property-based che validano le proprietà di correttezza
- Ogni test copre una proprietà specifica dal design document
- Generatori intelligenti per dati di test realistici

**Esecuzione**:
```bash
pytest tests/property/ -m property
```

**Nota**: I test property-based possono richiedere più tempo (1-5 minuti per test).

### Integration Tests (`integration/`)
Test end-to-end che verificano l'intero flusso:
- `test_end_to_end_integration.py` - Test E2E completo
- `test_integration_suite.py` - Suite integrazione
- `test_integration.py` - Test integrazione componenti
- `test_api_local.py` - Test API locale

**Esecuzione**:
```bash
pytest tests/integration/
```

### Mocks (`mocks/`)
Mock e fixture condivisi:
- `test_chatgpt_mock.py` - Mock ChatGPT API per test offline
- Fixture comuni per tutti i test

## 🚀 Esecuzione Test

### Tutti i Test
```bash
pytest
```

### Solo Test Unitari
```bash
pytest tests/unit/ -v
```

### Solo Test Property-Based
```bash
pytest tests/property/ -m property
```

### Solo Test Integrazione
```bash
pytest tests/integration/ -v
```

### Test Specifico
```bash
pytest tests/unit/test_chatgpt_client.py -v
```

### Con Coverage
```bash
pytest --cov=src --cov-report=html
```

## 📊 Marker Test

I test sono organizzati con marker pytest:

- `@pytest.mark.unit` - Test unitari
- `@pytest.mark.property` - Test property-based
- `@pytest.mark.integration` - Test integrazione
- `@pytest.mark.slow` - Test lenti (>1 secondo)

**Esecuzione per marker**:
```bash
pytest -m unit          # Solo unitari
pytest -m property      # Solo property-based
pytest -m integration   # Solo integrazione
pytest -m "not slow"    # Escludi test lenti
```

## ⚙️ Configurazione

La configurazione dei test è in `pytest.ini` nella root del progetto:

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

I test property-based usano Hypothesis con:
- **Min examples**: 100 iterazioni per test
- **Max examples**: 1000 iterazioni (se necessario)
- **Database**: `.hypothesis/` (gitignored)
- **Shrinking**: Abilitato per trovare esempi minimi

## 📝 Scrivere Nuovi Test

### Test Unitario
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

### Test Property-Based
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

### Test Integrazione
```python
# tests/integration/test_my_integration.py
import pytest
from src.main import app

@pytest.mark.integration
async def test_full_workflow():
    # Test completo del flusso
    pass
```

## 🐛 Debugging Test

### Verbose Output
```bash
pytest -v -s
```

### Stop al Primo Fallimento
```bash
pytest -x
```

### Esegui Solo Test Falliti
```bash
pytest --lf
```

### Debug con PDB
```bash
pytest --pdb
```

## 📈 Coverage Report

Dopo aver eseguito i test con coverage:

```bash
pytest --cov=src --cov-report=html
```

Apri `htmlcov/index.html` nel browser per vedere il report dettagliato.

## 🔍 Test Property-Based - Proprietà Coperte

| # | Proprietà | File | Status |
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

## 📚 Risorse

- [Pytest Documentation](https://docs.pytest.org/)
- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [Design Document](../.kiro/specs/llm-integration-module/design.md)
- [Testing Guide](../docs/development/TESTING.md)

---

**Nota**: Esegui sempre i test prima di committare modifiche!
