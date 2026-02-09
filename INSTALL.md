# Guida Completa all'Installazione

Questa guida fornisce istruzioni dettagliate per installare e configurare il modulo LLM Integration su un nuovo dispositivo.

## Indice

1. [Requisiti di Sistema](#requisiti-di-sistema)
2. [Installazione Passo-Passo](#installazione-passo-passo)
3. [Configurazione](#configurazione)
4. [Verifica dell'Installazione](#verifica-dellinstallazione)
5. [Risoluzione Problemi](#risoluzione-problemi)

## Requisiti di Sistema

### Software Richiesto

- **Python**: Versione 3.10 o superiore
  - Verifica: `python --version` o `python3 --version`
  - Download: [python.org](https://www.python.org/downloads/)

- **pip**: Package manager Python (solitamente incluso con Python)
  - Verifica: `pip --version`

- **Git**: Per clonare il repository
  - Verifica: `git --version`
  - Download: [git-scm.com](https://git-scm.com/downloads)

### Account e Credenziali

- **OpenAI Account**: Necessario per ottenere la API key
  - Registrati su: [platform.openai.com](https://platform.openai.com/signup)
  - Ottieni API key da: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

### Connessione Internet

- Richiesta per:
  - Scaricare le dipendenze Python
  - Comunicare con ChatGPT API
  - Clonare il repository

## Installazione Passo-Passo

### 1. Clona il Repository

```bash
# Clona il repository
git clone <repository-url>

# Entra nella directory del progetto
cd llm-driven-net
```

### 2. Crea l'Ambiente Virtuale

Un ambiente virtuale isola le dipendenze del progetto dal sistema.

#### Linux/macOS

```bash
# Crea l'ambiente virtuale
python3 -m venv venv

# Attiva l'ambiente virtuale
source venv/bin/activate

# Dovresti vedere (venv) nel prompt
```

#### Windows (PowerShell)

```powershell
# Crea l'ambiente virtuale
python -m venv venv

# Attiva l'ambiente virtuale
venv\Scripts\Activate.ps1

# Se ricevi errore di execution policy:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Dovresti vedere (venv) nel prompt
```

#### Windows (CMD)

```cmd
# Crea l'ambiente virtuale
python -m venv venv

# Attiva l'ambiente virtuale
venv\Scripts\activate.bat

# Dovresti vedere (venv) nel prompt
```

### 3. Aggiorna pip

```bash
# Aggiorna pip all'ultima versione
python -m pip install --upgrade pip
```

### 4. Installa le Dipendenze

#### Per Uso in Produzione

```bash
pip install -r requirements.txt
```

#### Per Sviluppo (Include Tool di Testing)

```bash
pip install -r requirements-dev.txt
```

**Tempo stimato**: 2-5 minuti (dipende dalla connessione internet)

### 5. Verifica le Dipendenze Installate

```bash
# Elenca tutte le dipendenze installate
pip list

# Verifica dipendenze specifiche
pip show fastapi openai hypothesis pytest
```

Dovresti vedere:
- `fastapi` >= 0.104.1
- `openai` >= 1.54.0
- `hypothesis` >= 6.119.4
- `pytest` >= 8.3.4
- E altre dipendenze...

## Configurazione

### 1. Crea il File di Configurazione

```bash
# Linux/macOS
cp .env.example .env

# Windows
copy .env.example .env
```

### 2. Configura ChatGPT API (OBBLIGATORIO)

Apri il file `.env` con un editor di testo e configura:

```env
# === ChatGPT API Configuration (OBBLIGATORIO) ===
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4-turbo
OPENAI_MAX_TOKENS=2000
OPENAI_TEMPERATURE=0.1
OPENAI_RATE_LIMIT_RPM=60
OPENAI_TIMEOUT=30
OPENAI_MAX_RETRIES=3
```

**Come ottenere la API key**:
1. Vai su [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Clicca "Create new secret key"
3. Copia la chiave (inizia con `sk-proj-` o `sk-`)
4. Incollala nel file `.env`

**⚠️ IMPORTANTE**: Non condividere mai la tua API key!

### 3. Configura Altri Parametri (Opzionale)

```env
# === RYU Controller ===
RYU_HOST=localhost
RYU_PORT=8080
RYU_API_BASE=/api/v1

# === Northbound Script ===
NORTHBOUND_HOST=localhost
NORTHBOUND_PORT=9090

# === Cache Configuration ===
STATE_CACHE_TTL=300
STATE_CACHE_MAX_SIZE=1000

# === Anomaly Detection ===
ANOMALY_DETECTION_ENABLED=true
ANOMALY_THRESHOLD=0.8

# === Logging ===
LOG_LEVEL=INFO
LOG_FORMAT=json
```

## Verifica dell'Installazione

### 1. Verifica Connessione ChatGPT

```bash
python scripts/test_chatgpt_connection.py
```

**Output atteso**:
```
✓ ChatGPT API connection successful
✓ Model: gpt-4-turbo
✓ Response time: ~2-5 seconds
```

### 2. Esegui i Test

```bash
# Esegui tutti i test
pytest

# Esegui test con output dettagliato
pytest -v

# Esegui solo test unitari (veloci)
pytest tests/test_*.py -v

# Esegui test property-based (più lenti)
pytest tests/test_*_properties.py -v
```

**Output atteso**:
```
==================== test session starts ====================
collected XX items

tests/test_action_sequencer.py .................. [100%]
tests/test_chatgpt_client.py .................... [100%]
...

==================== XX passed in X.XXs ====================
```

### 3. Avvia l'Applicazione (Test Manuale)

```bash
# Avvia il server
python -m src.main

# Oppure con uvicorn
uvicorn src.main:app --reload
```

**Output atteso**:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Apri il browser su `http://localhost:8000/docs` per vedere la documentazione API interattiva.

## Risoluzione Problemi

### Problema: Python non trovato

**Sintomo**:
```
'python' is not recognized as an internal or external command
```

**Soluzione**:
1. Verifica che Python sia installato: scarica da [python.org](https://www.python.org/downloads/)
2. Durante l'installazione, seleziona "Add Python to PATH"
3. Riavvia il terminale
4. Prova con `python3` invece di `python`

### Problema: pip non trovato

**Sintomo**:
```
'pip' is not recognized as an internal or external command
```

**Soluzione**:
```bash
# Usa python -m pip invece di pip
python -m pip install -r requirements.txt
```

### Problema: Errore durante creazione venv

**Sintomo**:
```
Error: [Errno 13] Permission denied
```

**Soluzione**:
```bash
# Linux/macOS: usa sudo
sudo python3 -m venv venv

# Windows: esegui PowerShell come amministratore
```

### Problema: Errore di Execution Policy (Windows)

**Sintomo**:
```
cannot be loaded because running scripts is disabled on this system
```

**Soluzione**:
```powershell
# Esegui in PowerShell come amministratore
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Problema: OpenAI API key non valida

**Sintomo**:
```
Error: Invalid API key provided
```

**Soluzione**:
1. Verifica che la chiave nel file `.env` sia corretta
2. Controlla che la chiave sia attiva su [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
3. Verifica di avere credito disponibile sul tuo account OpenAI
4. Assicurati che non ci siano spazi prima/dopo la chiave nel file `.env`

### Problema: Test falliscono

**Sintomo**:
```
ImportError: No module named 'src'
```

**Soluzione**:
1. Verifica di essere nella directory root del progetto: `pwd` (Linux/Mac) o `cd` (Windows)
2. Verifica che l'ambiente virtuale sia attivato (dovresti vedere `(venv)` nel prompt)
3. Reinstalla le dipendenze: `pip install -r requirements.txt`

### Problema: Timeout durante installazione dipendenze

**Sintomo**:
```
ReadTimeoutError: HTTPSConnectionPool
```

**Soluzione**:
```bash
# Aumenta il timeout
pip install -r requirements.txt --timeout=300

# Oppure usa un mirror più veloce
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Problema: Conflitti di versione

**Sintomo**:
```
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed
```

**Soluzione**:
```bash
# Crea un nuovo ambiente virtuale pulito
deactivate
rm -rf venv  # Linux/Mac
# oppure
rmdir /s venv  # Windows

# Ricrea l'ambiente
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate  # Windows

# Reinstalla
pip install -r requirements.txt
```

## Supporto Aggiuntivo

Se riscontri altri problemi:

1. Controlla i log in `logs/` (se esistono)
2. Verifica la documentazione completa in `docs/`
3. Consulta il file `README.md` per informazioni generali
4. Controlla le issue su GitHub (se disponibile)

## Checklist Finale

Prima di considerare l'installazione completa, verifica:

- [ ] Python 3.10+ installato e funzionante
- [ ] Ambiente virtuale creato e attivato
- [ ] Tutte le dipendenze installate senza errori
- [ ] File `.env` creato e configurato
- [ ] OpenAI API key configurata e valida
- [ ] Test di connessione ChatGPT superato
- [ ] Test suite eseguita con successo
- [ ] Applicazione avviata senza errori

**Congratulazioni! L'installazione è completa.** 🎉
