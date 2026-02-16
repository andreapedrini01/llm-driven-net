# Scripts Utility

Questa directory contiene script utility per setup, testing e verifica del sistema.

## Script Disponibili

### 🔧 Setup e Installazione

#### `verify_installation.py`
Verifica che l'installazione sia completa e corretta.

```bash
python scripts/verify_installation.py
```

**Controlla**:
- Versione Python (>= 3.10)
- Dipendenze installate
- File di configurazione (.env)
- Struttura del progetto
- Test disponibili

**Output**: Report dettagliato con ✓ (successo), ✗ (errore), ⚠ (warning)

---

### 🌐 Test ChatGPT API

#### `test_chatgpt_connection.py`
Testa la connessione a ChatGPT API.

```bash
python scripts/test_chatgpt_connection.py
```

**Verifica**:
- API key valida
- Connessione funzionante
- Latenza della risposta
- Modello configurato

**Nota**: Questo script effettua una chiamata reale all'API (costo minimo ~$0.001)

#### `verify_chatgpt_client.py`
Verifica il client ChatGPT con test più approfonditi.

```bash
python scripts/verify_chatgpt_client.py
```

**Testa**:
- Configurazione client
- Rate limiting
- Retry logic
- Error handling

---

### 🛠️ Altri Script

#### `setup.py`
Script di setup per configurazioni avanzate (se necessario).

```bash
python scripts/setup.py
```

---

## Script di Setup Automatico (Root Directory)

### Linux/macOS: `setup.sh`

```bash
chmod +x setup.sh
./setup.sh
```

**Esegue automaticamente**:
1. Verifica Python
2. Crea ambiente virtuale
3. Installa dipendenze
4. Configura .env
5. Verifica installazione

### Windows: `setup.bat`

```cmd
setup.bat
```

**Esegue automaticamente**:
1. Verifica Python
2. Crea ambiente virtuale
3. Installa dipendenze
4. Configura .env
5. Verifica installazione

---

## Workflow Consigliato

### Prima Installazione

```bash
# 1. Setup automatico
./setup.sh  # Linux/Mac
setup.bat   # Windows

# 2. Verifica installazione
python scripts/verify_installation.py

# 3. Configura API key nel file .env

# 4. Test connessione ChatGPT
python scripts/test_chatgpt_connection.py

# 5. Esegui test completi
pytest
```

### Verifica Periodica

```bash
# Verifica installazione
python scripts/verify_installation.py

# Test connessione API
python scripts/test_chatgpt_connection.py

# Verifica client
python scripts/verify_chatgpt_client.py
```

### Debug Problemi

```bash
# 1. Verifica installazione
python scripts/verify_installation.py

# 2. Se problemi con ChatGPT API
python scripts/test_chatgpt_connection.py

# 3. Se problemi con dipendenze
pip check
pip list --outdated

# 4. Se problemi con test
pytest -v --tb=short
```

---

## Creazione di Nuovi Script

Se vuoi aggiungere nuovi script utility:

1. Crea il file in `scripts/`
2. Aggiungi shebang: `#!/usr/bin/env python3`
3. Rendi eseguibile (Linux/Mac): `chmod +x scripts/nome_script.py`
4. Documenta in questo README
5. Aggiungi test se appropriato

### Template Script

```python
#!/usr/bin/env python3
"""Descrizione breve dello script."""

import sys
from pathlib import Path

# Aggiungi src al path per import
sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    """Funzione principale."""
    print("Script in esecuzione...")
    # Il tuo codice qui
    return 0

if __name__ == '__main__':
    sys.exit(main())
```

---

## Note

- **Ambiente virtuale**: Assicurati che l'ambiente virtuale sia attivato prima di eseguire gli script
- **Permessi**: Su Linux/Mac, alcuni script potrebbero richiedere `chmod +x`
- **API Costs**: Gli script che testano ChatGPT API hanno costi minimi (~$0.001 per test)
- **Configurazione**: Tutti gli script leggono configurazione da `.env`

---

## Troubleshooting

### Script non trovato

```bash
# Verifica di essere nella directory root del progetto
pwd  # Linux/Mac
cd   # Windows

# Verifica che lo script esista
ls scripts/  # Linux/Mac
dir scripts\  # Windows
```

### Errore di import

```bash
# Verifica che l'ambiente virtuale sia attivato
which python  # Linux/Mac (dovrebbe mostrare venv/bin/python)
where python  # Windows (dovrebbe mostrare venv\Scripts\python.exe)

# Verifica che le dipendenze siano installate
pip list
```

### Permission denied (Linux/Mac)

```bash
# Rendi lo script eseguibile
chmod +x scripts/nome_script.py

# Oppure esegui con python
python scripts/nome_script.py
```

---

## Supporto

Per problemi con gli script:

1. Verifica che l'ambiente virtuale sia attivato
2. Esegui `python scripts/verify_installation.py`
3. Controlla i log di errore
4. Consulta `INSTALL.md` per istruzioni dettagliate
