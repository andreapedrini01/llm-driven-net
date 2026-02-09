# 🧪 Guida al Testing del Network State Collector

Questa guida ti mostra come testare il Network State Collector e visualizzare i JSON generati.

## 📋 Prerequisiti

Assicurati di avere installato tutte le dipendenze:

```bash
pip install -r requirements.txt
```

## 🚀 Quick Start - Test Singolo Snapshot

### 1. Avvia il Mock Server Ryu

In un terminale, avvia il server mock che simula un controller Ryu:

```bash
python mock_ryu_server.py
```

Dovresti vedere:
```
🚀 Avvio Mock Ryu Controller Server...
📡 Server disponibile su: http://localhost:8080
```

### 2. Esegui il Test

In un **altro terminale**, esegui lo script di test:

```bash
python test_collector_live.py
```

Lo script:
- ✅ Verifica la connessione al mock server
- 📸 Raccoglie un singolo snapshot della rete
- 💾 Salva i dati in formato JSON
- 📊 Mostra statistiche e informazioni

### 3. Visualizza i JSON Generati

I file vengono salvati in due directory:

#### **File LLM (ottimizzati per modelli AI)**
```bash
# Visualizza il file più recente
cat data/llm_output/network_context_latest.json

# Formattato con colori
cat data/llm_output/network_context_latest.json | python -m json.tool

# Lista tutti i file
ls -lh data/llm_output/
```

#### **File Snapshot Completi (dati grezzi)**
```bash
# Lista snapshot storici
ls -lh data/history/

# Visualizza uno snapshot
cat data/history/network_snapshot_YYYYMMDD_HHMMSS.json | python -m json.tool
```

## 🔄 Test Raccolta Continua

Per testare la raccolta continua (snapshot periodici):

### 1. Avvia il Mock Server
```bash
python mock_ryu_server.py
```

### 2. Avvia la Raccolta Continua
```bash
python test_continuous_collection.py
```

Lo script raccoglierà snapshot ogni 5 secondi. Premi `Ctrl+C` per fermare.

### 3. Monitora i File in Tempo Reale

In un terzo terminale, puoi monitorare i file che vengono creati:

```bash
# Monitora la directory
watch -n 2 'ls -lh data/llm_output/'

# Oppure conta i file
watch -n 2 'echo "File LLM: $(ls data/llm_output/*.json 2>/dev/null | wc -l)"'
```

## 📊 Struttura del JSON LLM

Il file `network_context_latest.json` contiene:

```json
{
  "network_summary": {
    "total_switches": 3,
    "total_links": 2,
    "total_ports": 9,
    "active_switches": 3,
    "active_links": 2
  },
  "topology_embedding": {
    "switches": [...],
    "links": [...],
    "adjacency_matrix": {...}
  },
  "performance_vectors": {
    "switch_metrics": {...},
    "port_metrics": {...},
    "aggregated_stats": {...}
  },
  "temporal_features": {
    "timestamp": 1234567890.123,
    "collection_time_ms": 45.67,
    "time_of_day": "14:30:00"
  },
  "anomalies_detected": [],
  "metadata": {
    "version": "1.0.0",
    "environment": "development"
  }
}
```

## 🔍 Comandi Utili

### Visualizzare JSON Formattato
```bash
# Con Python
python -m json.tool data/llm_output/network_context_latest.json

# Con jq (se installato)
jq '.' data/llm_output/network_context_latest.json

# Colorato con jq
jq -C '.' data/llm_output/network_context_latest.json | less -R
```

### Estrarre Informazioni Specifiche
```bash
# Numero di switch
jq '.network_summary.total_switches' data/llm_output/network_context_latest.json

# Lista DPID degli switch
jq '.topology_embedding.switches[].dpid' data/llm_output/network_context_latest.json

# Timestamp
jq '.temporal_features.timestamp' data/llm_output/network_context_latest.json
```

### Confrontare Due Snapshot
```bash
# Differenza tra due file
diff <(jq -S '.' file1.json) <(jq -S '.' file2.json)
```

## 🧹 Pulizia File di Test

Per pulire i file generati durante i test:

```bash
# Rimuovi tutti i file LLM
rm -rf data/llm_output/*.json

# Rimuovi tutti gli snapshot storici
rm -rf data/history/*.json

# Rimuovi tutto
rm -rf data/
```

## 🐛 Troubleshooting

### Mock Server Non Raggiungibile

**Problema:** `Mock server non raggiungibile`

**Soluzione:**
1. Verifica che il mock server sia avviato: `python mock_ryu_server.py`
2. Controlla che la porta 8080 sia libera: `lsof -i :8080`
3. Prova a connetterti manualmente: `curl http://localhost:8080/stats/switches`

### Nessun File Generato

**Problema:** La directory `data/llm_output/` è vuota

**Soluzione:**
1. Verifica i permessi della directory
2. Controlla i log per errori
3. Verifica che lo snapshot sia stato raccolto con successo

### Errori di Importazione

**Problema:** `ModuleNotFoundError: No module named 'network_state_collector'`

**Soluzione:**
```bash
# Installa il package in modalità development
pip install -e .
```

## 📝 Personalizzazione

### Modificare l'Intervallo di Raccolta

Modifica `test_continuous_collection.py`:

```python
config.collection.interval = 10.0  # Raccolta ogni 10 secondi
```

### Cambiare la Directory di Output

Modifica gli script di test:

```python
config.output.directory = "my_custom_output"
```

### Disabilitare Pretty Print

Per JSON più compatti:

```python
config.output.pretty_print = False
```

## 🎯 Prossimi Passi

Dopo aver testato con il mock server, puoi:

1. **Connettere a un Ryu Controller Reale**
   - Modifica `config.ryu.base_url` con l'URL del tuo controller
   - Esempio: `http://192.168.1.100:8080`

2. **Integrare con Mininet**
   - Avvia una topologia Mininet
   - Avvia il controller Ryu
   - Esegui il collector

3. **Usare i JSON con un LLM**
   - Carica `network_context_latest.json` nel tuo modello
   - Usa per analisi, troubleshooting, o ottimizzazione

## 📚 Risorse Aggiuntive

- **Documentazione Ryu:** https://ryu.readthedocs.io/
- **Mininet:** http://mininet.org/
- **OpenFlow:** https://www.opennetworking.org/

## 💡 Suggerimenti

- Usa `watch` per monitorare i file in tempo reale
- Usa `jq` per query JSON complesse
- Salva snapshot interessanti per analisi future
- Confronta snapshot prima/dopo modifiche alla rete

---

**Buon testing! 🚀**
