# Quick Start Guide

Guida rapida per iniziare con il modulo LLM Integration in 5 minuti.

## Prerequisiti

- Python 3.10 o superiore
- Account OpenAI con API key

## Installazione Rapida

### Linux/macOS

```bash
# 1. Clona e entra nella directory
git clone <repository-url>
cd llm-driven-net

# 2. Esegui lo script di setup automatico
chmod +x setup.sh
./setup.sh

# 3. Configura la tua API key nel file .env
nano .env  # o usa il tuo editor preferito
```

### Windows

```cmd
REM 1. Clona e entra nella directory
git clone <repository-url>
cd llm-driven-net

REM 2. Esegui lo script di setup automatico
setup.bat

REM 3. Configura la tua API key nel file .env
notepad .env
```

### Installazione Manuale

Se preferisci installare manualmente:

```bash
# 1. Crea ambiente virtuale
python -m venv venv

# 2. Attiva ambiente virtuale
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 3. Installa dipendenze
pip install -r requirements.txt

# 4. Configura .env
cp .env.example .env  # Linux/Mac
copy .env.example .env  # Windows

# 5. Modifica .env con la tua API key
```

## Configurazione API Key

1. Ottieni una API key da [OpenAI Platform](https://platform.openai.com/api-keys)
2. Apri il file `.env`
3. Sostituisci `your-api-key-here` con la tua chiave:

```env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4-turbo
```

## Verifica Installazione

```bash
# Verifica che tutto sia configurato correttamente
python scripts/verify_installation.py
```

Output atteso:
```
✓ Python 3.12.4 (>= 3.10 richiesto)
✓ fastapi installato
✓ openai installato
...
✓ Installazione completa e corretta!
```

## Esegui i Test

```bash
# Esegui tutti i test
pytest

# Esegui test con output dettagliato
pytest -v

# Esegui solo test unitari (veloci)
pytest tests/test_*.py -k "not properties"
```

## Avvia l'Applicazione

```bash
# Metodo 1: Direttamente con Python
python -m src.main

# Metodo 2: Con uvicorn (raccomandato per sviluppo)
uvicorn src.main:app --reload

# Metodo 3: Con uvicorn (produzione)
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

L'applicazione sarà disponibile su:
- API: http://localhost:8000
- Documentazione interattiva: http://localhost:8000/docs
- Documentazione alternativa: http://localhost:8000/redoc

## Test Rapido

### Test Connessione ChatGPT

```bash
python scripts/test_chatgpt_connection.py
```

### Test API (con curl)

```bash
# Health check
curl http://localhost:8000/health

# Esempio richiesta (da implementare)
curl -X POST http://localhost:8000/api/v1/intents \
  -H "Content-Type: application/json" \
  -d '{"text": "Create a flow from switch-1 to switch-2"}'
```

## Struttura del Progetto

```
llm-driven-net/
├── src/                    # Codice sorgente
│   ├── models/            # Data models
│   ├── services/          # Business logic
│   ├── api/              # API endpoints
│   └── main.py           # Entry point
├── tests/                 # Test suite
├── scripts/              # Utility scripts
├── .env                  # Configurazione (da creare)
├── requirements.txt      # Dipendenze produzione
└── README.md            # Documentazione completa
```

## Comandi Utili

```bash
# Attiva ambiente virtuale
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Disattiva ambiente virtuale
deactivate

# Aggiorna dipendenze
pip install --upgrade -r requirements.txt

# Verifica dipendenze obsolete
pip list --outdated

# Esegui linting (se hai installato requirements-dev.txt)
flake8 src/
black src/ --check

# Formatta codice
black src/

# Type checking
mypy src/

# Coverage test
pytest --cov=src tests/
```

## Prossimi Passi

1. **Leggi la documentazione completa**: `README.md`
2. **Consulta la guida di installazione dettagliata**: `INSTALL.md`
3. **Esplora le specifiche del progetto**: `.kiro/specs/llm-integration-module/`
4. **Contribuisci**: Segui i task in `tasks.md`

## Risoluzione Problemi Rapida

### Python non trovato
```bash
# Verifica installazione
python --version
python3 --version

# Se non installato, scarica da python.org
```

### pip non trovato
```bash
# Usa python -m pip invece di pip
python -m pip install -r requirements.txt
```

### Errore API key
```bash
# Verifica che .env esista e contenga la chiave
cat .env | grep OPENAI_API_KEY  # Linux/Mac
type .env | findstr OPENAI_API_KEY  # Windows

# Verifica che la chiave sia valida su platform.openai.com
```

### Test falliscono
```bash
# Reinstalla dipendenze
pip install -r requirements.txt --force-reinstall

# Verifica installazione
python scripts/verify_installation.py
```

## Supporto

Per problemi o domande:

1. Consulta `INSTALL.md` per istruzioni dettagliate
2. Consulta `DEPENDENCIES.md` per problemi con le dipendenze
3. Esegui `python scripts/verify_installation.py` per diagnostica
4. Controlla i log in `logs/` (se esistono)

## Risorse

- **Documentazione OpenAI**: [platform.openai.com/docs](https://platform.openai.com/docs)
- **FastAPI Docs**: [fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- **Hypothesis Docs**: [hypothesis.readthedocs.io](https://hypothesis.readthedocs.io)

---

**Buon lavoro! 🚀**
