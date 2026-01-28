# Struttura del Progetto Northbound Script Generator

## Panoramica
Il progetto è stato riorganizzato in una struttura modulare e pulita per facilitare lo sviluppo e la manutenzione.

## Struttura delle Cartelle

```
northbound-script-generator/
├── src/                          # Codice sorgente principale
│   ├── __init__.py
│   ├── connectors/               # Connettori di rete
│   │   ├── __init__.py
│   │   ├── ryu_connector.py      # Connettore RYU Controller
│   │   └── comnetsemu_connector.py # Connettore ComnetsEMU
│   ├── models/                   # Modelli di dati
│   │   ├── __init__.py
│   │   └── action_models.py      # Modelli per azioni di rete
│   └── core/                     # Moduli core
│       ├── __init__.py
│       └── northbound_script.py  # Script Northbound principale
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── integration/              # Test di integrazione
│   │   ├── __init__.py
│   │   ├── test_ryu_integration.py
│   │   └── test_comnetsemu_integration.py
│   ├── unit/                     # Test unitari
│   │   └── __init__.py
│   ├── test_basic.py            # Test di base esistenti
│   ├── test_with_mock.py        # Test con mock
│   └── mock_controller.py       # Controller mock
├── demos/                        # Script dimostrativi
│   ├── __init__.py
│   ├── demo_ryu_connector.py     # Demo connettore RYU
│   └── demo_comnetsemu_integration.py # Demo integrazione ComnetsEMU
├── docs/                         # Documentazione
│   ├── __init__.py
│   └── task_1_3_implementation_summary.md
├── logs/                         # File di log
├── network_configs/              # Configurazioni di rete
├── tools/                        # Strumenti di utilità
├── .kiro/specs/                  # Specifiche del progetto
│   └── northbound-script-generator/
│       ├── requirements.md
│       ├── design.md
│       └── tasks.md
├── northbound_script.py          # Script principale (legacy)
├── requirements.txt              # Dipendenze Python
└── README.md                     # Documentazione principale
```

## Moduli Principali

### 1. Connectors (`src/connectors/`)
- **ryu_connector.py**: Integrazione reale con RYU Controller
  - Connection pooling HTTP
  - Gestione retry con exponential backoff
  - Operazioni flow table (add/modify/delete)
  - Statistiche e monitoraggio

- **comnetsemu_connector.py**: Integrazione reale con ComnetsEMU
  - Scoperta topologia di rete
  - Gestione modifiche topologia
  - Configurazione policy QoS
  - Verifica stato di rete

### 2. Models (`src/models/`)
- **action_models.py**: Modelli di dati per azioni di rete
  - NetworkAction, ActionSequence
  - Validazione parametri
  - Serializzazione/deserializzazione

### 3. Core (`src/core/`)
- **northbound_script.py**: Orchestratore principale
  - Integrazione RYU + ComnetsEMU
  - Logging avanzato
  - Gestione retry e rollback

## Test

### Integration Tests (`tests/integration/`)
- Test di integrazione con RYU e ComnetsEMU reali
- Scenari end-to-end
- Gestione errori di connessione

### Unit Tests (`tests/unit/`)
- Test unitari per singoli componenti
- Mock e simulazioni
- Validazione logica di business

## Demo Scripts (`demos/`)
- Script dimostrativi per ogni componente
- Esempi di utilizzo
- Test manuali delle funzionalità

## Come Utilizzare

### Eseguire Demo
```bash
# Demo connettore RYU
python demos/demo_ryu_connector.py

# Demo integrazione ComnetsEMU
python demos/demo_comnetsemu_integration.py
```

### Eseguire Test
```bash
# Test di integrazione
python -m pytest tests/integration/ -v

# Test unitari
python -m pytest tests/unit/ -v

# Tutti i test
python -m pytest tests/ -v
```

### Utilizzare i Moduli
```python
# Import dei connettori
from src.connectors.ryu_connector import create_ryu_connector
from src.connectors.comnetsemu_connector import create_comnetsemu_connector

# Import dei modelli
from src.models.action_models import NetworkAction, ActionType

# Import del core
from src.core.northbound_script import NorthboundScript
```

## Vantaggi della Nuova Struttura

1. **Modularità**: Ogni componente ha una responsabilità specifica
2. **Testabilità**: Test organizzati per tipo e scopo
3. **Manutenibilità**: Codice più facile da navigare e modificare
4. **Scalabilità**: Struttura pronta per nuovi componenti
5. **Documentazione**: Ogni modulo ha la sua documentazione
6. **Riusabilità**: Componenti facilmente riutilizzabili

## Prossimi Passi

1. Completare la migrazione del codice legacy
2. Aggiungere più test unitari
3. Implementare API REST Gateway (Task 3.1)
4. Aggiungere sistema di monitoraggio (Task 4.1)
5. Implementare interfaccia web (Task 5.1)