# Piano di Implementazione: collect-security-scan

## Panoramica

Implementazione della modalità di scansione di sicurezza attiva per il sistema di monitoraggio SDN.
La feature aggiunge il flag `--security-scan` al comando `collect`, esegue scansioni nmap sugli host
della rete, costruisce un `SecuritySnapshot` e lo invia al `ChatGPTClient` per ottenere un
`SecurityReport` strutturato. Il comportamento esistente di `collect_snapshot()` rimane invariato.

## Task

- [x] 1. Creare i modelli dati in `llm_integration_module/models/security.py`
  - Implementare le dataclass `OpenPort`, `NmapResult` (con metodi `to_dict` / `from_dict`), `SecuritySnapshot` (composizione con `NetworkSnapshot`, metodi `to_dict`, `to_json`, `from_dict`, `from_json`) e `SecurityReport` (con `to_dict`, `to_json`, `from_dict`, `from_json`, `get_timestamp_iso`)
  - Aggiungere `NmapNotFoundError` come eccezione custom nel modulo
  - Aggiornare `llm_integration_module/models/__init__.py` per esportare i nuovi tipi
  - _Requisiti: 1.3, 2.1, 2.2, 2.4, 5.1, 5.2_

  - [ ]* 1.1 Scrivere property test per il round-trip di `SecuritySnapshot`
    - **Proprietà 5: Round-trip SecuritySnapshot**
    - **Valida: Requisito 2.4, 2.5**
    - Usare generatori Hypothesis per `NmapResult` e `NetworkSnapshot`
    - `@settings(max_examples=100)`
    - `# Feature: collect-security-scan, Property 5`

  - [ ]* 1.2 Scrivere property test per l'invarianza dei campi `NetworkSnapshot`
    - **Proprietà 4: Invarianza dei campi NetworkSnapshot**
    - **Valida: Requisito 2.2**
    - Verificare che `snapshot.timestamp`, `topology`, `metrics`, `derived_metrics`, `metadata` siano identici all'originale
    - `# Feature: collect-security-scan, Property 4`

  - [ ]* 1.3 Scrivere property test per il round-trip di `SecurityReport`
    - **Proprietà 10: Round-trip SecurityReport**
    - **Valida: Requisiti 5.1, 5.2, 5.3**
    - `# Feature: collect-security-scan, Property 10`

  - [ ]* 1.4 Scrivere property test per la struttura di `NmapResult`
    - **Proprietà 2: Struttura del NmapResult**
    - **Valida: Requisito 1.3**
    - Per ogni `NmapResult` con `status="scanned"`, verificare che ogni elemento di `open_ports` abbia i campi `port`, `protocol`, `service`, `version`
    - `# Feature: collect-security-scan, Property 2`

- [x] 2. Implementare `SecurityScanner` in `network_state_collector/security_scanner.py`
  - Implementare la classe `SecurityScanner` con `__init__(timeout)`, `scan(ip_addresses)` e `_scan_host(ip)`
  - Leggere il timeout da `SECURITY_SCAN_TIMEOUT` env var se presente (Requisito 4.6)
  - Loggare il progresso nel formato "Scansione X/N: ip" (Requisito 4.5)
  - Gestire `FileNotFoundError` di subprocess sollevando `NmapNotFoundError` (Requisito 1.4)
  - Marcare host in timeout come `status="timeout"`, errori di rete come `status="error"`, host non raggiungibili come `status="unreachable"` (Requisiti 1.5, 1.6, 2.3)
  - Implementare la funzione helper `extract_host_ips(snapshot: NetworkSnapshot) -> List[str]` per estrarre IP nel range 10.0.0.x dalla topologia
  - Implementare la funzione helper `resolve_host_filter(host_filter: List[str], snapshot: NetworkSnapshot) -> List[str]` che risolve nomi Mininet (es. `h1` → `10.0.0.1`) e logga WARNING per host non trovati in topologia (Requisiti 1.7, 1.8, 1.9)
  - _Requisiti: 1.1, 1.2, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.3, 4.5, 4.6_

  - [ ]* 2.1 Scrivere property test per la copertura completa degli host
    - **Proprietà 1: Copertura completa degli host**
    - **Valida: Requisiti 1.1, 1.2**
    - Mockare `subprocess.run`; verificare che il dizionario restituito abbia esattamente N chiavi corrispondenti agli IP
    - `# Feature: collect-security-scan, Property 1`

  - [ ]* 2.2 Scrivere property test per la resilienza con host falliti
    - **Proprietà 3: Resilienza per host falliti**
    - **Valida: Requisiti 1.5, 1.6**
    - Generare liste di N host con uno o più in timeout/errore; verificare che tutti N abbiano un risultato
    - `# Feature: collect-security-scan, Property 3`

  - [ ]* 2.3 Scrivere unit test per casi limite del SecurityScanner
    - nmap non installato → `NmapNotFoundError`
    - host non raggiungibile → `status="unreachable"`
    - timeout da env var `SECURITY_SCAN_TIMEOUT`
    - formato log progresso "Scansione X/N: ip"
    - nome host `h1` risolto a `10.0.0.1`
    - nome host non in topologia → WARNING loggato, host ignorato
    - _Requisiti: 1.4, 1.5, 1.8, 1.9, 2.3, 4.5, 4.6_

- [x] 3. Checkpoint — Verificare che tutti i test passino
  - Assicurarsi che tutti i test passino; chiedere all'utente se sorgono dubbi.

- [x] 4. Implementare `SecurityAnalyzer` in `llm_integration_module/services/security_analyzer.py`
  - Implementare la classe `SecurityAnalyzer` con `__init__(chatgpt_client)`, `analyze(security_snapshot)`, `_build_prompt(security_snapshot)` e `_parse_response(raw)`
  - Usare `asyncio.run()` come bridge sync/async per chiamare `ChatGPTClient.generate_response()`
  - Includere il system message corretto con la struttura JSON attesa (Requisito 3.2)
  - Implementare la stima token con `len(text.split()) * 1.3` e il troncamento dei `NmapResult` meno rilevanti (ordinati per numero di porte aperte decrescente) se il prompt supera 12000 token (Requisito 3.6)
  - In caso di JSON non valido nella risposta, restituire `SecurityReport` con liste vuote e `raw_response` popolato (Requisito 3.4)
  - Propagare le eccezioni di `ChatGPTClient` dopo averle loggato (Requisito 3.5)
  - Aggiornare `llm_integration_module/services/__init__.py` per esportare `SecurityAnalyzer`
  - _Requisiti: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 4.1 Scrivere property test per la completezza del prompt
    - **Proprietà 6: Completezza del prompt**
    - **Valida: Requisito 3.1**
    - Per qualsiasi `SecuritySnapshot`, verificare che il prompt contenga la topologia, le metriche aggregate e tutti gli IP dei `NmapResult`
    - `# Feature: collect-security-scan, Property 6`

  - [ ]* 4.2 Scrivere property test per il limite di token del prompt
    - **Proprietà 7: Prompt entro il limite di token**
    - **Valida: Requisito 3.6**
    - Verificare che la stima token del prompt non superi 12000 e che la topologia sia sempre inclusa
    - `# Feature: collect-security-scan, Property 7`

  - [ ]* 4.3 Scrivere property test per il parsing della risposta LLM valida
    - **Proprietà 8: Parsing della risposta LLM valida**
    - **Valida: Requisito 3.3**
    - Per qualsiasi JSON valido con `vulnerabilities`, `configuration_issues`, `security_properties`, verificare che `raw_response` sia `None` e i campi siano popolati correttamente
    - `# Feature: collect-security-scan, Property 8`

  - [ ]* 4.4 Scrivere unit test per casi limite del SecurityAnalyzer
    - Risposta LLM non JSON → `raw_response` popolato, liste vuote
    - System message corretto con i tre campi JSON
    - Eccezione `ChatGPTClient` propagata
    - _Requisiti: 3.2, 3.4, 3.5_

- [x] 5. Integrare la scansione di sicurezza in `NetworkStateCollector`
  - Aggiungere i parametri `security_scan: bool = False` e `host_filter: Optional[List[str]] = None` a `collect_snapshot()`
  - Quando `security_scan=True` e `host_filter=None`: estrarre tutti gli IP con `extract_host_ips`
  - Quando `security_scan=True` e `host_filter` fornito: risolvere i nomi con `resolve_host_filter`
  - Istanziare `SecurityScanner`, chiamare `scan()`, costruire `SecuritySnapshot`, istanziare `SecurityAnalyzer`, chiamare `analyze()`, salvare il report in `data/security_history/` (creando la directory se assente), stampare il report formattato a schermo
  - Quando `security_scan=False`: comportamento esistente invariato (Requisito 4.1)
  - Implementare la funzione di formattazione del report con le sezioni "Vulnerabilità Potenziali", "Problemi di Configurazione", "Proprietà di Sicurezza da Verificare" (Requisito 4.4)
  - Salvare il file con nome `security_report_{timestamp_iso}.json` (Requisito 5.4)
  - _Requisiti: 4.1, 4.2, 4.3, 4.4, 5.4, 5.5_

  - [ ]* 5.1 Scrivere property test per il formato output leggibile
    - **Proprietà 9: Formato output leggibile**
    - **Valida: Requisito 4.3**
    - Per qualsiasi `SecurityReport`, verificare che la stringa formattata contenga "Vulnerabilità Potenziali", "Problemi di Configurazione", "Proprietà di Sicurezza da Verificare" e tutti gli elementi delle rispettive liste
    - `# Feature: collect-security-scan, Property 9`

  - [ ]* 5.2 Scrivere unit test per l'integrazione nel collector
    - `collect_snapshot(security_scan=False)` non istanzia `SecurityScanner`
    - Ordinamento operazioni: snapshot standard precede la scansione
    - Salvataggio file con nome corretto `security_report_{timestamp_iso}.json`
    - Directory `data/security_history/` creata automaticamente se assente
    - _Requisiti: 4.1, 4.2, 5.4, 5.5_

- [x] 6. Aggiungere il flag `--security-scan` alla CLI
  - Aggiungere il flag `--security-scan` al comando `collect` in `main_auto.py` (o nel modulo CLI esistente) come argomento con `nargs='*'` per accettare zero o più nomi host opzionali
  - Esempio: `collect --security-scan` → tutti gli host; `collect --security-scan h1 h3` → solo h1 e h3
  - Passare `security_scan=True` e `host_filter=<lista o None>` a `collect_snapshot()`
  - _Requisiti: 1.1, 1.7, 4.1, 4.2, 4.3_

- [x] 7. Checkpoint finale — Verificare che tutti i test passino
  - Assicurarsi che tutti i test passino; chiedere all'utente se sorgono dubbi.

## Note

- I task contrassegnati con `*` sono opzionali e possono essere saltati per un MVP più rapido
- Ogni task fa riferimento ai requisiti specifici per la tracciabilità
- I property test usano `@settings(max_examples=100)` e il tag `# Feature: collect-security-scan, Property N`
- I test unitari coprono casi limite e condizioni di errore non catturabili dai property test
- Il bridge sync/async tramite `asyncio.run()` in `SecurityAnalyzer.analyze()` è sicuro perché il metodo viene sempre chiamato da contesto sincrono
