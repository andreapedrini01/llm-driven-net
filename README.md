# Northbound Script Generator - Documentation

## Overview

Il Northbound Script Generator è un modulo semplificato per l'elaborazione di azioni di rete che si integra con ComnetsEMU per fornire capacità di gestione della rete. Questo modulo è progettato per essere autonomo e leggero, senza dipendenze da database complessi o sistemi API.
**Il seguente documento rispecchia un piano di sviluppo precedente rispetto a quello finale, per questo fare riferimento unicamente al README del branch main**

**Status:** ✅ Operativo | **Version:** 2.0.0 (Simplified) | **Last Updated:** Aprile 2026

## Quick Start

```bash
# 1. Naviga nella cartella del modulo
cd northbound_script_generator

# 2. Configura il sistema (opzionale - usa valori di default se non presente)
cp config.example.yaml config.yaml
# Modifica config.yaml secondo necessità

# 3. Prepara il file delle azioni
# Crea un file JSON o JSONL con le azioni da eseguire
# Esempio: logs/actions.jsonl

# 4. Avvia il sistema
python main.py
```

**Nota:** Il modulo è completamente autonomo e non richiede servizi esterni come API Gateway, database PostgreSQL o Redis. Tutte le operazioni sono basate su file locali.

## Documentation Structure

### 🚀 Getting Started
- **[Quick Start](#quick-start)** - Get up and running in 5 minutes
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete deployment guide (Docker, Kubernetes, manual)

### 📚 Core Documentation
- **[NORTHBOUND_MODULE.md](NORTHBOUND_MODULE.md)** - Complete module documentation (Italian)
- **[NORTHBOUND_MODULE_EN.md](NORTHBOUND_MODULE_EN.md)** - Complete module documentation (English)
- **[API_REFERENCE.md](API_REFERENCE.md)** - Complete API documentation and examples (legacy)
- **[ACTION_PACKAGE_GUIDE.md](ACTION_PACKAGE_GUIDE.md)** - Input data format specification
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture and design

### 🔧 Operations
- **[OPERATIONS.md](OPERATIONS.md)** - Operations guide, troubleshooting, and runbook

## Key Features

### Network Management
- Real-time network topology management
- Flow rule configuration (OpenFlow)
- QoS policy enforcement
- Network slicing support
- Traffic engineering

### Security
- JWT authentication with MFA
- Role-Based Access Control (RBAC)
- API key authentication for LLM integration
- Rate limiting and backpressure
- Session management

### Monitoring
- Prometheus metrics integration
- InfluxDB time-series storage
- Real-time alerting
- Grafana dashboards
- Health monitoring

### Scalability
- Horizontal scaling support
- Load balancing
- Connection pooling
- Parallel processing
- Redis caching

### Operations
- Automated backups (hourly)
- Point-in-time recovery
- Configuration hot-reload
- Graceful shutdown
- Comprehensive logging

## System Requirements

### Minimum Requirements
- Python 3.8+
- 4GB RAM
- 2 CPU cores
- 10GB disk space

### Recommended for Production
- Python 3.10+
- 8GB RAM
- 4 CPU cores
- 50GB disk space
- PostgreSQL 12+
- Redis 6+

### External Dependencies
- RYU Controller (running on localhost:8080)
- ComnetsEMU (running on localhost:6653)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                  External Interfaces                         │
│  LLM → API Gateway ← Web Dashboard                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   API & Security Layer                       │
│  Authentication | Authorization | Rate Limiting              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Core Services Layer                       │
│  Northbound Module | Monitoring | Backup | Config           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  Network Integration Layer                   │
│  RYU Connector | ComnetsEMU Connector | Retry System        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                     Data & Cache Layer                       │
│  PostgreSQL | Redis | InfluxDB                              │
└─────────────────────────────────────────────────────────────┘
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed information.

## Common Tasks

### Submit a Network Action

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'

# Submit action
curl -X POST http://localhost:8000/api/v1/actions \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "flow_mod",
    "target": "switch-1",
    "parameters": {
      "match": {"in_port": 1},
      "actions": [{"type": "output", "port": 2}]
    }
  }'
```

### Check System Health

```bash
curl http://localhost:8000/health
```

### View Logs

```bash
tail -f logs/system.log
```

### Run Tests

```bash
python scripts/run_tests.py
```

## Technology Stack

**Backend:**
- Python 3.8+, FastAPI, Pydantic, SQLAlchemy
- PostgreSQL, Redis, InfluxDB

**Frontend:**
- React 18, TypeScript, Material-UI, Vite

**Infrastructure:**
- Docker, Kubernetes, Nginx
- Prometheus, Grafana

**Testing:**
- Pytest, Hypothesis, GitHub Actions

## Project Structure

```
northbound-script-generator/
├── src/                    # Source code
│   ├── api/               # API Gateway and routes
│   ├── core/              # Core business logic
│   ├── connectors/        # RYU and ComnetsEMU connectors
│   ├── monitoring/        # Monitoring and metrics
│   ├── backup/            # Backup and recovery
│   ├── config/            # Configuration management
│   ├── scalability/       # Scalability features
│   └── orchestrator/      # System orchestration
├── frontend/              # React web dashboard
├── tests/                 # Test suite
├── docs/                  # Documentation
├── deployment/            # Deployment configurations
├── config/                # Configuration files
├── scripts/               # Utility scripts
└── demos/                 # Demo scripts
```

## Support and Troubleshooting

### Common Issues

**Service won't start:**
- Check logs: `tail -f logs/system.log`
- Verify RYU/ComnetsEMU are running
- Check port availability

**Authentication fails:**
- Verify credentials
- Check JWT secret key configuration
- Review auth logs

**Performance issues:**
- Check metrics: `curl http://localhost:8000/metrics`
- Review resource usage
- Check for bottlenecks

See [OPERATIONS.md](OPERATIONS.md) for detailed troubleshooting.

### Getting Help

- **Documentation:** Browse docs/ directory
- **API Docs:** http://localhost:8000/docs
- **Logs:** Check logs/ directory
- **Diagnostics:** Run `python scripts/diagnose.py`

## Development

### Running Tests

```bash
# All tests
python scripts/run_tests.py

# Specific test suite
pytest tests/test_api_gateway.py -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

### Code Quality

```bash
# Linting
flake8 src/ tests/

# Type checking
mypy src/

# Formatting
black src/ tests/
```

### Contributing

1. Follow existing code style
2. Add tests for new features
3. Update documentation
4. Run validation: `python scripts/validate_docs.py`

## License

MIT License - See LICENSE file for details

## Version History

- **1.0.0** (January 2025) - Production release
  - Complete system implementation
  - All 13 tasks completed
  - Full documentation
  - Production-ready deployment
---

**Production Ready** ✅ | **Fully Documented** ✅ | **Enterprise Grade** ✅
