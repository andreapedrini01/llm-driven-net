# LLM Integration Module

Il modulo di integrazione LLM è il componente centrale del sistema di networking intent-based che utilizza Large Language Models per interpretare intent di rete in linguaggio naturale e generare azioni di configurazione appropriate.

## Struttura del Progetto

```
├── src/
│   ├── models/          # Data models (Pydantic)
│   │   ├── intent.py    # Intent-related models
│   │   ├── network.py   # Network state models
│   │   ├── actions.py   # Action models
│   │   └── slices.py    # Network slice models
│   ├── services/        # Business logic services
│   ├── api/            # FastAPI routes and endpoints
│   ├── utils/          # Utilities
│   │   ├── logging.py  # Structured logging
│   │   └── monitoring.py # Metrics and monitoring
│   ├── config.py       # Configuration management
│   └── main.py         # Application entry point
├── tests/              # Test files
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Installazione

1. Clona il repository
2. Crea un ambiente virtuale Python:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # oppure
   venv\Scripts\activate     # Windows
   ```

3. Installa le dipendenze:
   ```bash
   pip install -r requirements.txt
   ```

4. Copia il file di configurazione:
   ```bash
   cp .env.example .env
   ```

5. Modifica il file `.env` con le tue configurazioni

## Esecuzione

### Sviluppo
```bash
python -m src.main
```

### Produzione
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8080
```

## Test

Esegui tutti i test:
```bash
pytest
```

Esegui solo i test unitari:
```bash
pytest -m unit
```

Esegui i test property-based:
```bash
pytest -m property
```

## Monitoraggio

Il modulo espone metriche Prometheus su `http://localhost:8000/metrics` (configurabile).

Metriche disponibili:
- `llm_module_intents_total`: Numero totale di intent processati
- `llm_module_actions_total`: Numero totale di azioni generate
- `llm_module_processing_seconds`: Tempo di elaborazione per componente
- `llm_module_anomalies_total`: Numero totale di anomalie rilevate

## Configurazione

Tutte le configurazioni sono gestite tramite variabili d'ambiente. Vedi `.env.example` per la lista completa.

Configurazioni principali:
- `LLM_PROVIDER`: Provider LLM ("openai" o "local")
- `OPENAI_API_KEY`: Chiave API OpenAI (se usando OpenAI)
- `RYU_HOST`: Host del controller RYU
- `NORTHBOUND_HOST`: Host dello script Northbound

## Architettura

Il modulo segue un'architettura a microservizi con i seguenti componenti principali:

1. **Intent Parser**: Analizza intent in linguaggio naturale
2. **Context Analyzer**: Correla intent con stato della rete
3. **Action Generator**: Genera azioni concrete tramite LLM
4. **Validator**: Valida e verifica sicurezza delle azioni

## API

L'API REST sarà disponibile su `/api/v1/` (da implementare nei prossimi task).

## Logging

Il sistema utilizza logging strutturato con supporto per:
- Output JSON per produzione
- Correlation ID per tracciamento
- Audit logging per eventi critici
- Diversi livelli di log configurabili

## Sviluppo

Per contribuire al progetto:

1. Segui la struttura dei task definita in `.kiro/specs/llm-integration-module/tasks.md`
2. Usa i modelli Pydantic definiti in `src/models/`
3. Implementa test sia unitari che property-based
4. Mantieni la copertura dei test alta
5. Segui le convenzioni di logging e monitoraggio