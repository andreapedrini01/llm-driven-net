# LLM Integration Module

Il modulo di integrazione LLM è il componente centrale del sistema di networking intent-based che utilizza **ChatGPT API (OpenAI)** per interpretare intent di rete in linguaggio naturale e generare azioni di configurazione appropriate. L'utilizzo esclusivo di ChatGPT API garantisce velocità di risposta superiore e maggiore accuratezza nell'interpretazione degli intent.

## 📚 Documentazione

- **[docs/](docs/)** - Indice completo documentazione 📖
- **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)** - Guida per iniziare e avviare il server ⚡
- **[docs/getting-started/](docs/getting-started/)** - Guide installazione e quick start
- **[docs/API_USAGE.md](docs/API_USAGE.md)** - Guida completa all'uso dell'API REST e WebSocket 🌐
- **[docs/development/](docs/development/)** - Guide sviluppo, testing e dipendenze 💻
- **[docs/deployment/](docs/deployment/)** - Guide deployment e architettura 🚀
- **[CHANGELOG.md](CHANGELOG.md)** - Registro delle modifiche e versioni 📝

## Struttura del Progetto

```
├── src/                    # Codice sorgente
│   ├── models/            # Data models (Pydantic)
│   ├── services/          # Business logic services
│   ├── api/               # FastAPI routes and endpoints
│   ├── utils/             # Utilities (logging, monitoring)
│   ├── config.py          # Configuration management
│   └── main.py            # Application entry point
│
├── tests/                  # Test suite
│   ├── unit/              # Test unitari
│   ├── property/          # Test property-based (Hypothesis)
│   ├── integration/       # Test end-to-end
│   └── mocks/             # Mock e fixture
│
├── docs/                   # Documentazione
│   ├── getting-started/   # Guide installazione
│   ├── api/               # Documentazione API
│   ├── deployment/        # Guide deployment
│   ├── development/       # Guide sviluppo
│   └── architecture/      # Design e requisiti
│
├── deployment/             # Deployment e infrastruttura
│   ├── kubernetes/        # Manifests K8s
│   ├── docker/            # Dockerfile e compose
│   ├── monitoring/        # Prometheus e alerting
│   └── scripts/           # Script deployment
│
├── config/                 # Configurazioni ambiente
│   ├── .env.example       # Template configurazione
│   ├── dev.env            # Ambiente sviluppo
│   ├── staging.env        # Ambiente staging
│   └── prod.env           # Ambiente produzione
│
├── examples/               # Esempi e demo
│   ├── data/              # Dati di esempio
│   └── *.py               # Script dimostrativi
│
├── cache/                  # Cache runtime
├── output/                 # Output generati
└── .kiro/                  # Spec e configurazione Kiro
```

## Installazione Rapida

### Requisiti di Sistema

- Python 3.11 o superiore
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
   copy config\.env.example .env
   
   # Linux/Mac
   cp config/.env.example .env
   ```
   
   Modifica `.env` con le tue configurazioni (specialmente `OPENAI_API_KEY`).

4. **Avvia il server**:
   ```bash
   python -m src.main
   ```
   
   Il server sarà disponibile su `http://localhost:8080`

Per istruzioni dettagliate, vedi [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)

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
python tests/integration/test_api_local.py
```

### Test Suite Completa

Esegui tutti i test:
```bash
pytest
```

Esegui solo i test unitari:
```bash
pytest tests/unit/ -m unit
```

Esegui i test property-based:
```bash
pytest tests/property/ -m property
```

Esegui i test di integrazione:
```bash
pytest tests/integration/
```

**Nota**: I test property-based possono richiedere più tempo per l'esecuzione.

Per dettagli completi, vedi [tests/README.md](tests/README.md) e [docs/development/TESTING.md](docs/development/TESTING.md)

## Monitoraggio

Il modulo espone metriche Prometheus su `http://localhost:8000/metrics` (configurabile).

Metriche disponibili:
- `llm_module_intents_total`: Numero totale di intent processati
- `llm_module_actions_total`: Numero totale di azioni generate
- `llm_module_processing_seconds`: Tempo di elaborazione per componente
- `llm_module_anomalies_total`: Numero totale di anomalie rilevate

## Configurazione

Tutte le configurazioni sono gestite tramite variabili d'ambiente. Vedi `config/.env.example` per la lista completa.

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

Vedi `config/.env.example` per tutte le opzioni disponibili.

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
3. Implementa test sia unitari che property-based in `tests/`
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

Per dettagli completi, vedi [docs/development/](docs/development/)

## Versione

Versione corrente: **0.1.0**

Vedi [CHANGELOG.md](CHANGELOG.md) per la storia completa delle modifiche.

## Licenza

Questo progetto è sviluppato per scopi educativi e di ricerca.

## Autori

@andreapedrini01

## Supporto

Per problemi o domande:
- Consulta la documentazione in `docs/`
- Leggi la [Troubleshooting Guide](docs/TROUBLESHOOTING.md) per problemi comuni
- Controlla i log del server per errori dettagliati
- Verifica la configurazione in `.env`
- Rivedi i requisiti in `requirements.txt`
- Leggi le guide in [docs/README.md](docs/README.md)