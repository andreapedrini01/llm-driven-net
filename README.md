# LLM Integration Module

Il modulo di integrazione LLM è il componente centrale del sistema di networking intent-based che utilizza **ChatGPT API (OpenAI)** per interpretare intent di rete in linguaggio naturale e generare azioni di configurazione appropriate. L'utilizzo esclusivo di ChatGPT API garantisce velocità di risposta superiore e maggiore accuratezza nell'interpretazione degli intent.

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

4. **Configura ChatGPT API**:
   
   Ottieni una API key da [OpenAI Platform](https://platform.openai.com/api-keys) e configurala nel file `.env`:
   
   ```env
   OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
   OPENAI_MODEL=gpt-4-turbo
   ```
   
   Vedi [docs/CHATGPT_SETUP.md](docs/CHATGPT_SETUP.md) per istruzioni dettagliate.

5. Modifica il file `.env` con le altre configurazioni necessarie

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

### Test della Connessione ChatGPT

Prima di eseguire i test completi, verifica che la connessione a ChatGPT funzioni:

```bash
python scripts/test_chatgpt_connection.py
```

### Test Suite Completa

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

### Configurazioni ChatGPT API

- `OPENAI_API_KEY`: La tua chiave API OpenAI (obbligatoria)
- `OPENAI_MODEL`: Modello da utilizzare (raccomandato: `gpt-4-turbo`)
- `OPENAI_MAX_TOKENS`: Token massimi per risposta (default: 2000)
- `OPENAI_TEMPERATURE`: Creatività delle risposte (0.0-1.0, raccomandato: 0.1)
- `OPENAI_RATE_LIMIT_RPM`: Richieste massime al minuto (default: 60)
- `OPENAI_TIMEOUT`: Timeout richieste in secondi (default: 30)
- `OPENAI_MAX_RETRIES`: Tentativi massimi in caso di errore (default: 3)

### Altre Configurazioni

- `RYU_HOST`: Host del controller RYU
- `NORTHBOUND_HOST`: Host dello script Northbound
- `STATE_CACHE_TTL`: TTL della cache dello stato di rete (secondi)
- `ANOMALY_DETECTION_ENABLED`: Abilita rilevamento anomalie

Vedi [docs/CHATGPT_SETUP.md](docs/CHATGPT_SETUP.md) per dettagli completi sulla configurazione ChatGPT.

## Architettura

Il modulo segue un'architettura a microservizi con i seguenti componenti principali:

1. **Intent Parser**: Analizza intent in linguaggio naturale
2. **Context Analyzer**: Correla intent con stato della rete
3. **Action Generator**: Genera azioni concrete tramite ChatGPT API
4. **Validator**: Valida e verifica sicurezza delle azioni
5. **ChatGPT Client**: Gestisce comunicazione con OpenAI API con retry logic e rate limiting

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