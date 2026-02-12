# Test del Modulo LLM con File JSON Personalizzato

Questa guida spiega come testare il modulo LLM usando il tuo file `network_context_latest.json` senza utilizzare l'API di ChatGPT.

## File Creati

1. **convert_json_format.py** - Converte il formato JSON nel formato compatibile con il modulo
2. **test_with_your_json.py** - Script di test completo che esegue vari test sul modulo
3. **network_context_converted.json** - File JSON convertito (generato automaticamente)

## Come Usare

### Passo 1: Converti il File JSON

Il tuo file `network_context_latest.json` ha un formato leggermente diverso da quello atteso dal modulo. Esegui lo script di conversione:

```bash
python convert_json_format.py
```

Questo creerà il file `network_context_converted.json` con il formato corretto.

### Passo 2: Esegui i Test

Esegui lo script di test completo:

```bash
python test_with_your_json.py
```

## Test Eseguiti

Lo script esegue 5 test principali:

### Test 1: Caricamento Network State
- Carica il file JSON convertito
- Valida la struttura dei dati
- Mostra informazioni su switches, hosts, links e anomalie

### Test 2: Intent Parsing
- Testa il parsing di intent in linguaggio naturale (italiano)
- Estrae entità e parametri dagli intent
- Calcola confidence scores

Intent di esempio testati:
- "Crea un flusso da host_1 a host_2 con priorità alta"
- "Mostra lo stato di switch_0000000000000001"
- "Risolvi l'anomalia sulla porta 3 dello switch 1"
- "Aumenta la bandwidth del link tra switch 1 e switch 2"

### Test 3: Context Analysis
- Analizza il contesto degli intent rispetto allo stato della rete
- Identifica risorse rilevanti
- Rileva potenziali conflitti

### Test 4: Anomaly Analysis
- Analizza le anomalie presenti nel network state
- Classifica tipo e severità
- Suggerisce azioni correttive

Anomalie rilevate nel tuo file:
1. **High Utilization** sulla porta 3 (100% utilizzo) → Severità CRITICAL
2. **High Error Rate** sulla porta 2 (2% errori) → Severità CRITICAL
3. **Isolated Switch** (Switch 4 isolato) → Severità HIGH

### Test 5: Metrics Analysis
- Analizza le metriche di rete (bandwidth, latenza, utilizzo porte)
- Identifica problemi potenziali
- Fornisce raccomandazioni

## Risultati dei Test

Tutti i test sono stati eseguiti con successo! ✓

### Dati Caricati dal Tuo File:
- **Switches**: 4 (tutti attivi)
- **Links**: 2
- **Hosts**: 4
- **Anomalie**: 3
- **Bandwidth Utilizzo**: 9.4% (normale)
- **Latenza Media**: 6.4 ms (nella norma)

### Anomalie Critiche Identificate:
1. Porta 3 dello Switch 1: utilizzo al 100% (CRITICAL)
2. Porta 2 dello Switch 2: alto tasso di errori (CRITICAL)
3. Switch 4: appare isolato dalla rete (HIGH)

## Note Importanti

### Senza ChatGPT API
Questi test utilizzano **solo la logica locale** del modulo:
- Intent parsing con NLP locale
- Context analysis con algoritmi deterministici
- Anomaly detection con pattern matching

### Con ChatGPT API
Per utilizzare ChatGPT API per generazione azioni più intelligenti:
1. Configura la chiave API in `.env`
2. Usa gli endpoint REST API del modulo
3. Vedi `docs/API_USAGE.md` per dettagli

## Formato JSON Richiesto

Il modulo richiede che le anomalie abbiano questo formato:

```json
{
  "anomalies": [
    {
      "id": "anomaly_1",
      "type": "traffic_spike",  // Enum: traffic_spike, latency_increase, link_failure, switch_failure, security_threat
      "severity": "critical",    // Enum: low, medium, high, critical
      "description": "Descrizione dell'anomalia",
      "affected_resources": ["resource_id"],
      "detected_at": "2026-02-11T17:35:50",
      "resolved_at": null,
      "metrics": {
        "confidence": 0.9
      }
    }
  ]
}
```

Lo script `convert_json_format.py` converte automaticamente il tuo formato in questo.

## Prossimi Passi

### Per Testare con ChatGPT API:
1. Configura `.env` con la tua chiave OpenAI
2. Avvia il server API: `python -m src.main`
3. Usa gli endpoint REST per inviare intent

### Per Integrare con Ryu:
1. Il modulo legge file JSON dalla cartella `cache/`
2. Un modulo esterno dovrebbe salvare lo stato di Ryu in `cache/network_state.json`
3. Il modulo LLM rileverà automaticamente i cambiamenti (se file watching è abilitato)

### Per Eseguire Test Completi:
```bash
# Test unitari
pytest tests/

# Test di integrazione
pytest tests/test_end_to_end_integration.py

# Test property-based (richiede più tempo)
pytest tests/ -m "property"
```

## Troubleshooting

### Errore: "File not found"
Assicurati che `network_context_latest.json` sia nella directory corrente.

### Errore: "Validation error"
Esegui prima `convert_json_format.py` per convertire il formato.

### Errore: "Module not found"
Installa le dipendenze:
```bash
pip install -r requirements.txt
```

## Contatti

Per domande o problemi, consulta la documentazione in `docs/` o apri un issue.
