# LLM Integration Module

Il modulo di integrazione LLM è il componente centrale del sistema di networking intent-based che utilizza **ChatGPT API (OpenAI)** per interpretare intent di rete in linguaggio naturale e generare azioni di configurazione appropriate. L'utilizzo esclusivo di ChatGPT API garantisce velocità di risposta superiore e maggiore accuratezza nell'interpretazione degli intent.

## 📚 Documentazione

- **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)** - Guida per iniziare e avviare il server ⚡
- **[docs/API_USAGE.md](docs/API_USAGE.md)** - Guida completa all'uso dell'API REST e WebSocket 🌐
- **[docs/DEPENDENCIES.md](docs/DEPENDENCIES.md)** - Informazioni dettagliate sulle dipendenze 📦
- **[CHANGELOG.md](CHANGELOG.md)** - Registro delle modifiche e versioni 📝
- **[README.md](README.md)** - Questo documento (panoramica generale) 📖

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

## Installazione Rapida

### Requisiti di Sistema

- Python 3.8 o superiore
- pip (package manager Python)
- Connessione internet per accedere a ChatGPT API

### Installazione

1. **Clona il repository**:
   ```bash
   git clone <repository-url>
   cd llm-driven-net
   ```

2. **Installa le dipendenze**:
   
   Per uso normale:
   ```bash
   pip install -r requirements.txt
   ```
   
   Per sviluppo (include tool di testing, linting, ecc.):
   ```bash
   pip install -r requirements-dev.txt
   ```

3. **Configura le variabili d'ambiente**:
   
   Copia il file di esempio e modificalo:
   ```bash
   # Windows
   copy .env.example .env
   
   # Linux/Mac
   cp .env.example .env
   ```
   
   Modifica `.env` con le tue configurazioni (specialmente `OPENAI_API_KEY`).

4. **Avvia il server**:
   ```bash
   python -m src.main
   ```
   
   Il server sarà disponibile su `http://localhost:8080`

Per istruzioni dettagliate, vedi [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)

## Esecuzione

### Avvio del Server

```bash
python -m src.main
```

Il server sarà disponibile su:
- API: http://localhost:8080
- Metrics: http://localhost:8000
- Docs: http://localhost:8080/docs

### Test Rapido

```bash
# Test health check
curl http://localhost:8080/health

# Login
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

### Produzione

Per produzione, usa uvicorn direttamente:
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8080 --workers 4
```

## Test

### Test Rapido dell'API

```bash
python test_api_local.py
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

**Nota**: I test property-based possono richiedere più tempo per l'esecuzione.

## Monitoraggio

Il modulo espone metriche Prometheus su `http://localhost:8000/metrics` (configurabile).

Metriche disponibili:
- `llm_module_intents_total`: Numero totale di intent processati
- `llm_module_actions_total`: Numero totale di azioni generate
- `llm_module_processing_seconds`: Tempo di elaborazione per componente
- `llm_module_anomalies_total`: Numero totale di anomalie rilevate

## Configurazione

Tutte le configurazioni sono gestite tramite variabili d'ambiente. Vedi `.env.example` per la lista completa.

### Configurazioni Essenziali

#### ChatGPT API (Obbligatorio)
- `OPENAI_API_KEY`: La tua chiave API OpenAI
- `OPENAI_MODEL`: Modello da utilizzare (default: `gpt-4o-mini`)

#### Autenticazione (Raccomandato cambiare in produzione)
- `JWT_SECRET_KEY`: Chiave segreta per JWT
- `ADMIN_PASSWORD`: Password utente admin
- `OPERATOR_PASSWORD`: Password utente operator
- `VIEWER_PASSWORD`: Password utente viewer

#### Server
- `API_HOST`: Host del server (default: `0.0.0.0`)
- `API_PORT`: Porta del server (default: `8080`)

### Configurazioni Avanzate

#### ChatGPT API
- `OPENAI_MAX_TOKENS`: Token massimi per risposta (default: 2000)
- `OPENAI_TEMPERATURE`: Creatività delle risposte (0.0-1.0, default: 0.1)
- `OPENAI_RATE_LIMIT_RPM`: Richieste massime al minuto (default: 60)
- `OPENAI_TIMEOUT`: Timeout richieste in secondi (default: 30)
- `OPENAI_MAX_RETRIES`: Tentativi massimi in caso di errore (default: 3)

#### Network State
- `STATE_CACHE_TTL`: TTL della cache dello stato di rete (default: 300 secondi)
- `STATE_REFRESH_INTERVAL`: Intervallo refresh automatico (default: 60 secondi)

#### Monitoring
- `METRICS_PORT`: Porta per metriche Prometheus (default: 8000)
- `ENABLE_METRICS`: Abilita server metriche (default: true)

Vedi `.env.example` per tutte le opzioni disponibili.

## Architettura

Il modulo segue un'architettura modulare con i seguenti componenti principali:

### Core Components

1. **Intent Parser**: Analizza intent in linguaggio naturale
2. **Context Analyzer**: Correla intent con stato della rete
3. **Action Generator**: Genera azioni concrete tramite ChatGPT API
4. **Validator**: Valida e verifica sicurezza delle azioni
5. **ChatGPT Client**: Gestisce comunicazione con OpenAI API con retry logic e rate limiting

### API Layer

6. **REST API**: Endpoints per sottomissione intent e gestione
7. **WebSocket**: Aggiornamenti real-time per client connessi
8. **Authentication**: Sistema JWT con ruoli e permessi

### Infrastructure

9. **State Cache**: Cache thread-safe per stato della rete
10. **Monitoring**: Metriche Prometheus e health checks
11. **Logging**: Logging strutturato con correlation IDs

Vedi [.kiro/specs/llm-integration-module/design.md](.kiro/specs/llm-integration-module/design.md) per dettagli completi.

## API REST

Il modulo espone un'API REST completa per la gestione degli intent di rete.

### Endpoints Principali

- `POST /api/v1/auth/login` - Autenticazione e ottenimento token JWT
- `GET /api/v1/auth/me` - Informazioni utente corrente
- `POST /api/v1/intents` - Sottomissione intent in linguaggio naturale
- `GET /api/v1/intents/{id}/status` - Status di un intent
- `WS /api/v1/ws` - WebSocket per aggiornamenti real-time
- `GET /health` - Health check
- `GET /health/ready` - Readiness check
- `GET /health/live` - Liveness check

### Documentazione Interattiva

Una volta avviato il server, la documentazione interattiva è disponibile su:
- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

### Autenticazione

L'API utilizza JWT (JSON Web Tokens) per l'autenticazione. Utenti predefiniti:
- `admin` / `admin123` - Accesso completo
- `operator` / `operator123` - Lettura e scrittura
- `viewer` / `viewer123` - Solo lettura

**Importante**: Cambia le password predefinite in produzione tramite variabili d'ambiente!

Per dettagli completi, vedi [docs/API_USAGE.md](docs/API_USAGE.md)

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

### Dipendenze di Sviluppo

Per installare le dipendenze di sviluppo (linting, formatting, ecc.):

```bash
pip install -r requirements-dev.txt
```

Questo include:
- black (code formatter)
- flake8 (linter)
- mypy (type checker)
- pytest-cov (test coverage)
- E altro (vedi requirements-dev.txt)

## Versione

Versione corrente: **0.1.0**

Vedi [CHANGELOG.md](CHANGELOG.md) per la storia completa delle modifiche.

## Licenza

Questo progetto è sviluppato per scopi educativi e di ricerca.

## Autori

Sviluppato come parte del progetto LLM-Driven Network Management.

## Supporto

Per problemi o domande:
- Consulta la documentazione in `docs/`
- Controlla i log del server per errori dettagliati
- Verifica la configurazione in `.env`
- Rivedi i requisiti in `requirements.txt`