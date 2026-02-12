# Gestione delle Dipendenze

Questo documento spiega come gestire le dipendenze del progetto.

## File di Dipendenze

Il progetto utilizza diversi file per gestire le dipendenze:

### 1. `requirements.txt` (Produzione)

Contiene le dipendenze minime necessarie per eseguire l'applicazione in produzione.

```bash
pip install -r requirements.txt
```

**Dipendenze principali**:
- `fastapi` - Framework web per API REST
- `pydantic` - Validazione dati e serializzazione
- `openai` - Client ufficiale per ChatGPT API
- `httpx` - Client HTTP asincrono
- `hypothesis` - Property-based testing
- `pytest` - Framework di testing
- `structlog` - Logging strutturato
- `python-dotenv` - Gestione variabili d'ambiente

### 2. `requirements-dev.txt` (Sviluppo)

Include `requirements.txt` più tool di sviluppo aggiuntivi.

```bash
pip install -r requirements-dev.txt
```

**Dipendenze aggiuntive**:
- `black` - Formattazione automatica del codice
- `flake8` - Linting
- `mypy` - Type checking statico
- `pytest-cov` - Coverage dei test
- `mkdocs` - Generazione documentazione

### 3. `requirements-lock.txt` (Versioni Esatte)

Contiene tutte le dipendenze con versioni esatte (generate con `pip freeze`).

Utile per:
- Garantire riproducibilità esatta dell'ambiente
- Deploy in produzione
- Debug di problemi specifici di versione

```bash
pip install -r requirements-lock.txt
```

## Installazione su Nuovo Dispositivo

### Opzione 1: Installazione Standard (Raccomandato)

```bash
# Crea ambiente virtuale
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Installa dipendenze
pip install -r requirements.txt
```

### Opzione 2: Installazione Esatta (Riproducibilità Garantita)

```bash
# Crea ambiente virtuale
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Installa versioni esatte
pip install -r requirements-lock.txt
```

### Opzione 3: Installazione per Sviluppo

```bash
# Crea ambiente virtuale
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Installa dipendenze di sviluppo
pip install -r requirements-dev.txt
```

## Aggiornamento Dipendenze

### Aggiornare una Singola Dipendenza

```bash
# Aggiorna una specifica dipendenza
pip install --upgrade openai

# Aggiorna pip freeze
pip freeze > requirements-lock.txt
```

### Aggiornare Tutte le Dipendenze

```bash
# Aggiorna tutte le dipendenze
pip install --upgrade -r requirements.txt

# Aggiorna pip freeze
pip freeze > requirements-lock.txt
```

### Verificare Dipendenze Obsolete

```bash
# Mostra dipendenze con aggiornamenti disponibili
pip list --outdated
```

## Verifica Dipendenze

### Verifica Installazione

```bash
# Verifica che tutte le dipendenze siano installate
python scripts/verify_installation.py
```

### Verifica Versioni

```bash
# Mostra tutte le dipendenze installate
pip list

# Mostra informazioni su una specifica dipendenza
pip show openai
```

### Verifica Conflitti

```bash
# Verifica conflitti tra dipendenze
pip check
```

## Dipendenze Critiche

### ChatGPT API (OpenAI)

**Pacchetto**: `openai >= 1.54.0`

**Configurazione richiesta**:
```env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4-turbo
```

**Documentazione**: [platform.openai.com/docs](https://platform.openai.com/docs)

### FastAPI

**Pacchetto**: `fastapi >= 0.104.1`

Framework web per costruire API REST ad alte prestazioni.

### Hypothesis

**Pacchetto**: `hypothesis >= 6.119.4`

Framework per property-based testing, utilizzato per validare le proprietà di correttezza del sistema.

## Risoluzione Problemi

### Conflitti di Versione

Se riscontri conflitti di versione:

```bash
# Crea un nuovo ambiente virtuale pulito
deactivate
rm -rf venv  # Linux/Mac
rmdir /s venv  # Windows

python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Reinstalla
pip install -r requirements.txt
```

### Dipendenze Mancanti

Se un modulo non viene trovato:

```bash
# Verifica che sia in requirements.txt
grep <nome-modulo> requirements.txt

# Installalo manualmente
pip install <nome-modulo>

# Aggiorna requirements-lock.txt
pip freeze > requirements-lock.txt
```

### Problemi di Rete

Se l'installazione fallisce per problemi di rete:

```bash
# Aumenta il timeout
pip install -r requirements.txt --timeout=300

# Usa un mirror alternativo
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## Best Practices

1. **Usa sempre un ambiente virtuale**: Non installare mai dipendenze globalmente
2. **Aggiorna requirements-lock.txt**: Dopo ogni modifica alle dipendenze
3. **Testa dopo aggiornamenti**: Esegui `pytest` dopo ogni aggiornamento
4. **Documenta dipendenze custom**: Se aggiungi nuove dipendenze, documentale
5. **Verifica compatibilità**: Prima di aggiornare in produzione, testa in sviluppo

## Dipendenze per Ambiente

### Sviluppo Locale

```bash
pip install -r requirements-dev.txt
```

Include tool di sviluppo, testing e debugging.

### Testing/CI

```bash
pip install -r requirements.txt
```

Include solo dipendenze necessarie per eseguire test.

### Produzione

```bash
pip install -r requirements-lock.txt
```

Usa versioni esatte per garantire stabilità.

## Checklist Installazione

Prima di considerare l'installazione completa:

- [ ] Ambiente virtuale creato e attivato
- [ ] Dipendenze installate senza errori
- [ ] `pip check` non mostra conflitti
- [ ] `python scripts/verify_installation.py` passa tutti i controlli
- [ ] Test eseguiti con successo: `pytest`
- [ ] Applicazione avviabile: `python -m src.main`

## Supporto

Per problemi con le dipendenze:

1. Consulta questo documento
2. Verifica `INSTALL.md` per istruzioni dettagliate
3. Esegui `python scripts/verify_installation.py`
4. Controlla i log di errore
