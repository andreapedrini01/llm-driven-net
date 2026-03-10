# Simplify Architecture Local Storage - Bugfix Design

## Overview

Il progetto Northbound Script Generator presenta un'architettura sovra-ingegnerizzata con componenti enterprise non necessari per il caso d'uso reale. Il sistema attuale include database PostgreSQL, frontend React, API REST complessa, autenticazione multi-fattore, monitoring distribuito (Prometheus/InfluxDB), sistema di backup, scalabilità orizzontale, e orchestrazione Kubernetes.

Questa complessità rende il sistema difficile da mantenere e utilizzare per il semplice caso d'uso di:
1. Leggere azioni da un file JSON (`logs/actions.jsonl`)
2. Applicarle alla rete ComnetsEMU
3. Salvare i risultati localmente in `history/`
4. Fornire logging base

La strategia di fix consiste nel rimuovere tutti i componenti enterprise non necessari e implementare un'architettura minimale con storage locale, preservando le funzionalità core essenziali (applicazione azioni, retry logic, validazione).

## Glossary

- **Bug_Condition (C)**: La condizione che identifica componenti enterprise non necessari - quando il sistema richiede servizi esterni (database, Redis, InfluxDB) o componenti complessi (API Gateway, Frontend, Monitoring distribuito) per funzionare
- **Property (P)**: Il comportamento desiderato - il sistema deve funzionare con solo Python e dipendenze minime, leggendo da file JSON e salvando risultati localmente
- **Preservation**: Funzionalità core che devono rimanere invariate - applicazione azioni a ComnetsEMU, retry logic con exponential backoff, validazione azioni, logging errori
- **ComnetsEMU Connector**: Il modulo in `src/connectors/comnetsemu_connector.py` che gestisce la comunicazione con il controller di rete ComnetsEMU
- **Retry System**: Il sistema in `src/core/retry_system.py` che implementa retry logic con exponential backoff e circuit breaker
- **Action Processor**: Il componente che processa le azioni di rete, valida i parametri e coordina l'esecuzione
- **History Manager**: Il componente che salva i risultati delle operazioni in file JSON nella cartella `history/`
- **Enterprise Components**: Componenti complessi non necessari come PostgreSQL, Redis, InfluxDB, API Gateway, Frontend React, Kubernetes, Prometheus, Grafana

## Bug Details

### Bug Condition

Il bug si manifesta quando il sistema richiede componenti enterprise complessi per funzionare, rendendo impossibile l'utilizzo semplice del tool. Il sistema attuale ha dipendenze da PostgreSQL per storage, Redis per sessioni, InfluxDB per metriche, API Gateway per accesso, Frontend React per UI, e richiede Docker Compose o Kubernetes per deployment.

**Formal Specification:**
```
FUNCTION isBugCondition(Component)
  INPUT: Component of type SystemComponent
  OUTPUT: boolean
  
  RETURN (
    Component IN [
      "PostgreSQL", "Redis", "InfluxDB", 
      "API_Gateway", "JWT_Auth", "MFA",
      "Prometheus", "Grafana", "AlertManager",
      "Frontend_React", "WebSocket",
      "Backup_System", "Database_Manager",
      "Load_Balancer", "Connection_Pool",
      "Kubernetes", "Docker_Compose",
      "Distributed_Config", "Session_Manager",
      "Scalability_Module", "Monitoring_Service"
    ]
  ) AND (
    Component NOT IN [
      "ComnetsEMU_Connector", 
      "Action_Processor", 
      "Local_File_Storage", 
      "Basic_Python_Logging",
      "Retry_System"
    ]
  )
END FUNCTION
```

### Examples

- **Esempio 1 - Dipendenza Database**: Sistema richiede PostgreSQL per salvare risultati. Bug Condition: `isBugCondition("PostgreSQL") = true`. Expected: Sistema usa solo file JSON in `history/action_results_<timestamp>.json`

- **Esempio 2 - Complessità Deployment**: Deployment richiede `docker-compose up` con 5+ servizi (PostgreSQL, Redis, InfluxDB, API, Frontend). Bug Condition: `isBugCondition("Docker_Compose") = true`. Expected: Deployment con semplice `python main.py`

- **Esempio 3 - API non necessaria**: Azioni processate via REST API POST `/api/actions` con JWT auth. Bug Condition: `isBugCondition("API_Gateway") = true`. Expected: Azioni lette direttamente da `logs/actions.jsonl`

- **Esempio 4 - Monitoring complesso**: Sistema richiede Prometheus + InfluxDB + Grafana per monitoring. Bug Condition: `isBugCondition("Prometheus") = true`. Expected: Logging Python standard con output su `logs/system.log`

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Applicazione corretta delle azioni di rete al controller ComnetsEMU deve continuare a funzionare esattamente come prima
- Retry logic con exponential backoff per errori di connessione deve rimanere invariata
- Validazione della struttura e parametri delle azioni deve continuare a funzionare
- Logging degli errori con stack trace completo deve rimanere invariato
- Processing sequenziale di azioni multiple rispettando l'ordine deve continuare a funzionare
- Salvataggio risultati con timestamp, status (success/failure), e dettagli operazione deve rimanere invariato

**Scope:**
Tutte le funzionalità core che NON dipendono da componenti enterprise devono essere completamente preservate. Questo include:
- Connessione e comunicazione con ComnetsEMU
- Logica di retry e circuit breaker
- Validazione parametri azioni
- Error handling e logging
- Processing sequenziale azioni
- Salvataggio risultati (cambia solo il backend da database a file)

## Hypothesized Root Cause

Basandosi sull'analisi del bug, le cause più probabili sono:

1. **Over-Engineering Iniziale**: Il progetto è stato sviluppato con un'architettura enterprise-grade pensando a scenari di produzione complessi (multi-tenant, alta disponibilità, scalabilità orizzontale) che non sono necessari per il caso d'uso reale di un tool locale

2. **Feature Creep**: Durante lo sviluppo sono stati aggiunti progressivamente componenti (Task 1-13 nel documento ARCHITECTURE.md) senza considerare se fossero realmente necessari per il caso d'uso base

3. **Dipendenze Transitive**: L'aggiunta di un componente (es. API Gateway) ha portato alla necessità di altri componenti (autenticazione, sessioni, database per utenti), creando una catena di dipendenze

4. **Mancanza di Separazione**: Non esiste una chiara separazione tra il modulo core (northbound_script_generator) e i componenti enterprise, rendendo impossibile usare solo la parte essenziale

## Correctness Properties

Property 1: Bug Condition - System Simplification

_For any_ component where the bug condition holds (isBugCondition returns true), the fixed system SHALL NOT include that component in the codebase, dependencies, or runtime requirements, and SHALL function correctly without it.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8**

Property 2: Preservation - Core Functionality

_For any_ network action that is valid and processable, the simplified system SHALL produce the same network effects as the original system, preserving retry logic, validation, error handling, and result storage (with only the storage backend changing from database to local files).

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

## Fix Implementation

### Changes Required

Assumendo che la root cause analysis sia corretta, i cambiamenti necessari sono:

**File**: Struttura progetto `northbound_script_generator/`

**Specific Changes**:

1. **Riorganizzazione Cartella northbound_script_generator/**:
   - Rimuovere cartelle: `src/api/`, `src/backup/`, `src/monitoring/`, `src/scalability/`, `src/orchestrator/`
   - Mantenere solo: `src/connectors/`, `src/core/`, `src/models/`
   - Creare nuovi file minimali: `action_processor.py`, `history_manager.py`, `config_loader.py`
   - Spostare file essenziali nella root: `main.py`, `config.yaml`, `requirements.txt`

2. **Nuovo main.py Semplificato**:
   - Rimuovere SystemOrchestrator e tutti i servizi complessi
   - Implementare loop semplice: leggi da `logs/actions.jsonl` → processa → salva in `history/`
   - Usare solo logging Python standard (no aggregator, no InfluxDB)
   - Configurazione da singolo file `config.yaml`

3. **Nuovo action_processor.py**:
   - Estrarre logica core da northbound_script.py
   - Mantenere validazione azioni
   - Integrare con ComnetsEMU connector esistente
   - Integrare con retry system esistente
   - Rimuovere dipendenze da API, database, monitoring

4. **Nuovo history_manager.py**:
   - Implementare storage locale in `history/`
   - Formato: `history/results_<timestamp>.json`
   - Struttura JSON: `{"action_id": "...", "status": "success/failure", "timestamp": "...", "details": {...}}`
   - Nessuna dipendenza da PostgreSQL o SQLAlchemy

5. **Nuovo config.yaml Semplificato**:
   - Parametri base: `comnetsemu_host`, `comnetsemu_port`, `max_retries`, `retry_delay`, `log_level`
   - Rimuovere: configurazione database, Redis, InfluxDB, API, autenticazione, backup, monitoring

6. **Nuovo requirements.txt Minimale**:
   - Mantenere solo: `requests` (per HTTP a ComnetsEMU), `pyyaml` (per config), librerie standard Python
   - Rimuovere: `fastapi`, `uvicorn`, `sqlalchemy`, `psycopg2`, `redis`, `prometheus-client`, `influxdb-client`, `pydantic`, `python-jose`, `passlib`

7. **Preservare Componenti Core**:
   - `src/connectors/comnetsemu_connector.py`: Mantenere invariato (già funzionante)
   - `src/core/retry_system.py`: Mantenere invariato (già funzionante)
   - `src/models/action_models.py`: Mantenere solo modelli essenziali (NetworkAction, ActionType)

8. **Rimuovere Completamente**:
   - Cartella `frontend/` (React app)
   - Cartella `deployment/` (Kubernetes, Docker Compose)
   - Cartella `src/api/` (API Gateway, auth, routes)
   - Cartella `src/backup/` (backup system)
   - Cartella `src/monitoring/` (Prometheus, InfluxDB, alerts)
   - Cartella `src/scalability/` (load balancer, connection pool)
   - Cartella `src/orchestrator/` (system orchestrator)
   - File: `docker-compose.yml`, `Dockerfile`, `.github/workflows/ci-cd.yml`
   - File: `start_system.py`, `run_api_gateway.py`

## Testing Strategy

### Validation Approach

La strategia di testing segue un approccio a due fasi: prima, verificare che il sistema semplificato funzioni correttamente con le funzionalità core; poi, verificare che i componenti enterprise siano stati completamente rimossi e il sistema non dipenda più da essi.

### Exploratory Bug Condition Checking

**Goal**: Verificare che i componenti enterprise siano stati rimossi PRIMA di testare il sistema semplificato. Confermare o confutare la root cause analysis. Se confutiamo, dovremo ri-ipotizzare.

**Test Plan**: Scrivere test che verificano l'assenza di dipendenze enterprise e la capacità del sistema di funzionare senza servizi esterni. Eseguire questi test sul codice DOPO la semplificazione per osservare successi e confermare la rimozione.

**Test Cases**:
1. **Test Dipendenze**: Verificare che `requirements.txt` non contenga `fastapi`, `sqlalchemy`, `redis`, `prometheus-client`, `influxdb-client` (dovrebbe passare dopo fix)
2. **Test Struttura Cartelle**: Verificare che non esistano cartelle `src/api/`, `src/backup/`, `src/monitoring/`, `frontend/`, `deployment/` (dovrebbe passare dopo fix)
3. **Test Startup Semplice**: Verificare che `python main.py` si avvii senza richiedere PostgreSQL, Redis, o altri servizi esterni (dovrebbe passare dopo fix)
4. **Test Import**: Verificare che il codice non importi moduli da `src.api`, `src.backup`, `src.monitoring`, `src.scalability` (dovrebbe passare dopo fix)

**Expected Counterexamples** (sul codice NON fixato):
- `requirements.txt` contiene 20+ dipendenze enterprise
- Esistono 8+ cartelle con componenti enterprise
- `python main.py` fallisce con errore "Cannot connect to PostgreSQL"
- Codice importa moduli da `src.api.gateway_app`, `src.monitoring.monitoring_service`

### Fix Checking

**Goal**: Verificare che per tutti gli input dove la bug condition è vera (componenti enterprise), il sistema fixato non includa più quei componenti.

**Pseudocode:**
```
FOR ALL Component WHERE isBugCondition(Component) DO
  ASSERT Component NOT IN system_fixed.dependencies
  ASSERT Component NOT IN system_fixed.codebase
  ASSERT Component NOT IN system_fixed.runtime_requirements
END FOR

// Verify essential functionality works
FOR ALL Action IN valid_network_actions DO
  result := process_action_fixed(Action)
  ASSERT result.applied_to_network = true
  ASSERT result.saved_to_history = true
  ASSERT result.logged = true
END FOR
```

### Preservation Checking

**Goal**: Verificare che per tutti gli input dove la bug condition NON è vera (funzionalità core), il sistema fixato produca lo stesso risultato del sistema originale.

**Pseudocode:**
```
FOR ALL Action WHERE Action.is_valid_network_action DO
  original_network_effect := F(Action).network_effect
  fixed_network_effect := F'(Action).network_effect
  
  ASSERT fixed_network_effect = original_network_effect
  ASSERT F'(Action).retry_logic = F(Action).retry_logic
  ASSERT F'(Action).validation = F(Action).validation
  ASSERT F'(Action).error_handling = F(Action).error_handling
END FOR
```

**Testing Approach**: Property-based testing è raccomandato per preservation checking perché:
- Genera automaticamente molti test case attraverso il dominio di input
- Cattura edge case che i test manuali potrebbero perdere
- Fornisce garanzie forti che il comportamento è invariato per tutti gli input non-buggy

**Test Plan**: Osservare il comportamento sul codice ORIGINALE per azioni di rete valide, poi scrivere property-based test che catturano quel comportamento e verificare che continui dopo il fix.

**Test Cases**:
1. **Preservation Test - Applicazione Azioni**: Osservare che azioni valide vengono applicate correttamente a ComnetsEMU nel codice originale, poi verificare che il comportamento continui nel codice fixato
2. **Preservation Test - Retry Logic**: Osservare che errori di connessione attivano retry con exponential backoff nel codice originale, poi verificare che il comportamento continui nel codice fixato
3. **Preservation Test - Validazione**: Osservare che azioni con parametri invalidi vengono rifiutate nel codice originale, poi verificare che il comportamento continui nel codice fixato
4. **Preservation Test - Logging Errori**: Osservare che errori vengono loggati con stack trace nel codice originale, poi verificare che il comportamento continui nel codice fixato

### Unit Tests

- Test `action_processor.py`: validazione azioni, processing sequenziale, integrazione con connettore
- Test `history_manager.py`: salvataggio file JSON, creazione cartella history, formato risultati
- Test `config_loader.py`: caricamento config.yaml, valori default, gestione errori
- Test `main.py`: loop principale, lettura da actions.jsonl, gestione eccezioni

### Property-Based Tests

- Generare azioni di rete random valide e verificare che vengano processate correttamente
- Generare configurazioni random valide e verificare che il sistema si avvii correttamente
- Testare che per molti scenari di errore, il retry logic funzioni correttamente
- Verificare che per molte azioni, i risultati salvati in history/ contengano tutti i campi richiesti

### Integration Tests

- Test flusso completo: leggi da actions.jsonl → processa → salva in history/ → verifica file creato
- Test con ComnetsEMU mock: verifica che azioni vengano inviate correttamente al connettore
- Test retry logic: simula errori di connessione e verifica che il sistema riprovi con backoff
- Test logging: verifica che errori vengano loggati correttamente in logs/system.log
