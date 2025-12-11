# LLM-Driven Network

Intent-based networking using Large Language Models (LLMs)

## Roadmap

### Fase 1: Analisi e Definizione dei Requisiti

**Obiettivo:** Comprendere esattamente cosa si vuole ottenere e definire scenari d'uso concreti (ad esempio, orchestrazione di slice e rilevamento anomalie).

**Task principali:**
- Studio di RYU e raccolta dati di stato di rete
- Identificazione delle possibili "intent" da gestire con LLM (es. routing, anomaly detection, configurazione slice)

**Divisione ruoli:**
- **Filippo:** Responsabile SDN/RYU
- **Andrea:** Studio LLM e integrazione
- **Pietro:** Architettura applicativa e script Northbound

### Fase 2: Progettazione Architettura

**Obiettivo:** Definire come dialogano i vari componenti (RYU, servizio LLM, script Northbound).

**Task principali:**
- Schema di flusso dati tra RYU, modulo LLM e script Northbound
- Specifica dati di input/output per LLM
- Scelta framework per orchestrare lo scambio (REST API, Python, etc.)

### Fase 3: Sviluppo Singoli Moduli

**Divisione:**

**Filippo:**
- Sviluppo script per raccogliere stato rete da RYU
- Gestione intent: parsing e invio intent al modulo LLM

**Andrea:**
- Prototipazione e test modello LLM (Chat GPT o clone)
- Script di interfaccia per ricevere stato/intents e restituire azioni
- Validazione risposte modello

**Pietro:**
- Sviluppo Northbound script: riceve output LLM e applica modifiche alla rete
- Logging/monitoraggio cambiamenti e gestione errori

### Fase 4: Integrazione e Test

**Obiettivo:** Collegare tutti i moduli, testare funzionalità end-to-end ed eseguire casi di test.

**Task principali:**
- Test scenario "quale slice usare" e "anomaly detection"
- Simulazione flussi di rete ed errori, raccolta log
- Miglioramenti iterativi e debugging in gruppo

### Fase 5: Documentazione e Presentazione

**Obiettivo:** Produrre materiale per documentare implementazione, test e risultati.

**Task principali:**
- Scrivere report tecnico e slide di presentazione
- Preparare demo funzionale per valutatori/professori
- Eventuali video o script per simulazione

## Suggerimenti per la Divisione del Lavoro

- Ruotare i ruoli di test/debugging e documentazione in modo che tutti acquisiscano familiarità con l'intero progetto
- Utilizzare repository condiviso (es. GitHub) e tool di project management (Trello/Notion)