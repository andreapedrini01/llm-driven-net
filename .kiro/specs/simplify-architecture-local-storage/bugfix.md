# Bugfix Requirements Document

## Introduction

Il progetto Northbound Script Generator presenta un'architettura sovra-ingegnerizzata con componenti enterprise non necessari per il caso d'uso reale. Il sistema include database (PostgreSQL), frontend web (React), API REST complessa, autenticazione multi-fattore, monitoring distribuito (Prometheus/InfluxDB), sistema di backup, scalabilità orizzontale, e orchestrazione Kubernetes. Questa complessità rende il sistema difficile da mantenere e utilizzare per il semplice caso d'uso di leggere azioni da un file JSON, applicarle alla rete ComnetsEMU, e salvare i risultati localmente.

L'obiettivo è semplificare drasticamente l'architettura mantenendo solo le funzionalità essenziali: lettura da file JSON, applicazione azioni, storage locale in cartella `history/`, e logging base.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN il sistema viene avviato THEN richiede PostgreSQL, Redis, InfluxDB e altri servizi esterni che non sono necessari per il caso d'uso base

1.2 WHEN si vuole processare azioni di rete THEN è necessario passare attraverso un'API REST con autenticazione JWT/MFA invece di una semplice lettura da file

1.3 WHEN si vogliono salvare i risultati THEN vengono scritti in database PostgreSQL con sistema di backup complesso invece di semplici file locali

1.4 WHEN si vuole monitorare il sistema THEN sono richiesti Prometheus, InfluxDB, Grafana e alert manager invece di logging semplice

1.5 WHEN si vuole deployare il sistema THEN sono necessari Docker Compose, Kubernetes, Nginx load balancer invece di un semplice script Python

1.6 WHEN si naviga nella cartella del progetto THEN esistono cartelle `src/api/`, `src/backup/`, `src/monitoring/`, `src/scalability/`, `frontend/`, `deployment/` che non servono

1.7 WHEN si vuole configurare il sistema THEN sono richiesti multipli file YAML complessi, variabili d'ambiente, configurazione distribuita invece di un singolo file config semplice

1.8 WHEN si installano le dipendenze THEN vengono installati FastAPI, SQLAlchemy, Redis, psycopg2, prometheus-client, influxdb-client e molte altre librerie non necessarie

### Expected Behavior (Correct)

2.1 WHEN il sistema viene avviato THEN SHALL richiedere solo Python e le dipendenze minime per ComnetsEMU senza servizi esterni

2.2 WHEN si vuole processare azioni di rete THEN il sistema SHALL leggere direttamente dal file `logs/actions.jsonl` (o `actions.json`) senza API REST

2.3 WHEN si vogliono salvare i risultati THEN il sistema SHALL scrivere file JSON nella cartella `history/` con timestamp

2.4 WHEN si vuole monitorare il sistema THEN il sistema SHALL utilizzare solo logging Python standard con output su file e console

2.5 WHEN si vuole deployare il sistema THEN il sistema SHALL essere eseguibile con un semplice comando `python main.py`

2.6 WHEN si naviga nella cartella del progetto THEN SHALL esistere solo `northbound_script_generator/` con i file essenziali (main.py, comnetsemu_connector.py, action_processor.py, history_manager.py, config.yaml, requirements.txt)

2.7 WHEN si vuole configurare il sistema THEN il sistema SHALL utilizzare un singolo file `config.yaml` con parametri base (host ComnetsEMU, retry settings, log level)

2.8 WHEN si installano le dipendenze THEN SHALL essere installate solo le librerie minime necessarie per ComnetsEMU e retry logic

### Unchanged Behavior (Regression Prevention)

3.1 WHEN il sistema processa azioni di rete valide THEN il sistema SHALL CONTINUE TO applicare correttamente le azioni al controller ComnetsEMU

3.2 WHEN si verifica un errore di connessione a ComnetsEMU THEN il sistema SHALL CONTINUE TO implementare retry logic con exponential backoff

3.3 WHEN vengono lette azioni dal file di input THEN il sistema SHALL CONTINUE TO validare la struttura e i parametri delle azioni

3.4 WHEN vengono salvati i risultati THEN il sistema SHALL CONTINUE TO includere timestamp, status (success/failure), e dettagli dell'operazione

3.5 WHEN si verifica un errore durante il processing THEN il sistema SHALL CONTINUE TO loggare l'errore con stack trace completo

3.6 WHEN il file di input contiene azioni multiple THEN il sistema SHALL CONTINUE TO processarle in sequenza rispettando l'ordine


## Bug Condition Derivation

### Bug Condition Function

La condizione di bug identifica quando il sistema utilizza componenti enterprise non necessari:

```pascal
FUNCTION isBugCondition(Component)
  INPUT: Component of type SystemComponent
  OUTPUT: boolean
  
  // Returns true when component is enterprise/complex and not essential
  RETURN (
    Component IN [
      "PostgreSQL", "Redis", "InfluxDB", 
      "API_Gateway", "JWT_Auth", "MFA",
      "Prometheus", "Grafana", "AlertManager",
      "Frontend_React", "WebSocket",
      "Backup_System", "Database_Manager",
      "Load_Balancer", "Connection_Pool",
      "Kubernetes", "Docker_Compose",
      "Distributed_Config", "Session_Manager"
    ]
  ) AND (
    Component NOT IN ["ComnetsEMU_Connector", "Action_Processor", "Local_Storage", "Basic_Logging"]
  )
END FUNCTION
```

### Property Specification - Fix Checking

```pascal
// Property: System Simplification
FOR ALL Component WHERE isBugCondition(Component) DO
  ASSERT Component.removed = true
  ASSERT Component NOT IN system.dependencies
  ASSERT Component NOT IN system.codebase
END FOR

// Property: Essential Functionality Preserved
FOR ALL Action IN input_actions DO
  result ← processAction'(Action)
  ASSERT result.applied_to_network = true
  ASSERT result.saved_to_history = true
  ASSERT result.logged = true
END FOR

// Property: Simplified Architecture
LET simplified_system = system' AFTER removing_bug_components
ASSERT simplified_system.dependencies.count <= 5
ASSERT simplified_system.config_files.count = 1
ASSERT simplified_system.external_services.count = 0
ASSERT simplified_system.startup_command = "python main.py"
```

### Property Specification - Preservation Checking

```pascal
// Property: Core Functionality Preservation
FOR ALL Action WHERE Action.is_valid_network_action DO
  original_result ← F(Action)
  fixed_result ← F'(Action)
  
  ASSERT fixed_result.network_applied = original_result.network_applied
  ASSERT fixed_result.retry_logic = original_result.retry_logic
  ASSERT fixed_result.validation = original_result.validation
  ASSERT fixed_result.error_handling = original_result.error_handling
END FOR
```

### Key Definitions

- **F**: Sistema originale con architettura enterprise complessa
- **F'**: Sistema semplificato con solo componenti essenziali
- **Component**: Qualsiasi modulo, servizio, o dipendenza del sistema
- **Action**: Azione di rete da applicare a ComnetsEMU

### Counterexamples

**Esempio 1 - Dipendenza non necessaria:**
```
Input: Sistema richiede PostgreSQL per salvare risultati
Bug Condition: isBugCondition("PostgreSQL") = true
Expected: Sistema usa solo file JSON in history/
```

**Esempio 2 - Complessità di deployment:**
```
Input: Deployment richiede Docker Compose + Kubernetes
Bug Condition: isBugCondition("Kubernetes") = true
Expected: Deployment con semplice "python main.py"
```

**Esempio 3 - API non necessaria:**
```
Input: Azioni processate via REST API con JWT auth
Bug Condition: isBugCondition("API_Gateway") = true
Expected: Azioni lette direttamente da file JSON
```
