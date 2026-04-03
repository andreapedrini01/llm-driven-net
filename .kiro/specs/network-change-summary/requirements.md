# Documento dei Requisiti

## Introduzione

Quando l'utente esegue un comando `intent` in `main.py`, il sistema applica modifiche alla rete ma non fornisce alcun feedback dettagliato su quali parametri siano stati effettivamente modificati. Questa feature aggiunge un riepilogo chiaro delle modifiche applicate, stampato a schermo dopo ogni esecuzione, sia nel caso rule-based (alta confidence) sia quando interviene l'LLM. Opzionalmente, l'LLM può generare un riassunto in linguaggio naturale delle modifiche effettuate.

## Glossario

- **Sistema_Riepilogo**: Il modulo responsabile della generazione e visualizzazione del riepilogo delle modifiche di rete dopo l'esecuzione di un intent.
- **ActionProcessor**: Il componente esistente (`northbound_script_generator`) che esegue le azioni di rete e restituisce un `ExecutionResult`.
- **ExecutionResult**: La struttura dati restituita dall'`ActionProcessor` dopo l'esecuzione di un'azione, contenente `status`, `duration`, `error`, `network_state_before` e `network_state_after`.
- **NetworkAction**: La struttura dati che rappresenta un'azione di rete, contenente `type`, `target`, `parameters`, `priority`, `timeout` e `description`.
- **ChatGPTClient**: Il client esistente per comunicare con l'LLM e generare risposte in linguaggio naturale.
- **Riepilogo_Strutturato**: L'output testuale che elenca i parametri modificati in formato tabellare o a lista.
- **Riepilogo_LLM**: L'output testuale generato dall'LLM che descrive le modifiche in linguaggio naturale.
- **Intent**: Un comando in linguaggio naturale fornito dall'utente per modificare la configurazione di rete.

## Requisiti

### Requisito 1: Generazione del riepilogo strutturato dopo l'esecuzione

**User Story:** Come operatore di rete, voglio vedere un riepilogo strutturato dei parametri modificati dopo ogni esecuzione di un intent, così da poter verificare che le modifiche siano state applicate correttamente.

#### Criteri di Accettazione

1. WHEN tutte le azioni di un intent sono state eseguite, THE Sistema_Riepilogo SHALL stampare a schermo un riepilogo contenente, per ogni azione eseguita: il tipo di azione, il target (switch/risorsa), i parametri applicati, lo stato di esecuzione (successo/fallimento) e la durata.
2. WHEN un'azione viene eseguita con successo, THE Sistema_Riepilogo SHALL includere nel riepilogo i valori specifici dei parametri modificati estratti dal campo `parameters` della NetworkAction (ad esempio: match fields, flow actions, bandwidth, cookie, priority).
3. WHEN un'azione fallisce durante l'esecuzione, THE Sistema_Riepilogo SHALL includere nel riepilogo il messaggio di errore restituito dall'ExecutionResult.
4. THE Sistema_Riepilogo SHALL indicare nel riepilogo se le azioni sono state generate in modalità rule-based oppure tramite LLM, mostrando il valore di confidence dell'intent.

### Requisito 2: Confronto stato di rete prima e dopo l'esecuzione

**User Story:** Come operatore di rete, voglio vedere le differenze tra lo stato della rete prima e dopo l'applicazione delle modifiche, così da avere conferma visiva dell'effetto delle azioni.

#### Criteri di Accettazione

1. WHEN lo stato della rete prima e dopo l'esecuzione è disponibile (campi `network_state_before` e `network_state_after` dell'ExecutionResult), THE Sistema_Riepilogo SHALL calcolare e mostrare le differenze tra i due stati.
2. IF i campi `network_state_before` o `network_state_after` dell'ExecutionResult sono assenti, THEN THE Sistema_Riepilogo SHALL mostrare il riepilogo basandosi esclusivamente sui parametri della NetworkAction e sullo stato di esecuzione, senza il confronto degli stati.

### Requisito 3: Riepilogo in linguaggio naturale tramite LLM

**User Story:** Come operatore di rete, voglio poter ottenere un riassunto in linguaggio naturale delle modifiche effettuate, così da avere una descrizione leggibile e comprensibile delle operazioni eseguite.

#### Criteri di Accettazione

1. WHEN l'utente ha abilitato l'opzione di riepilogo LLM, THE Sistema_Riepilogo SHALL inviare al ChatGPTClient i dati delle azioni eseguite e i risultati di esecuzione per generare un riassunto in linguaggio naturale.
2. WHEN il ChatGPTClient restituisce una risposta valida, THE Sistema_Riepilogo SHALL stampare il riassunto in linguaggio naturale dopo il riepilogo strutturato.
3. IF il ChatGPTClient non è disponibile o restituisce un errore, THEN THE Sistema_Riepilogo SHALL mostrare un messaggio informativo e continuare a visualizzare il riepilogo strutturato senza interrompere il flusso.
4. THE Sistema_Riepilogo SHALL includere nel prompt inviato al ChatGPTClient l'intent originale dell'utente, le azioni eseguite e i risultati di esecuzione.

### Requisito 4: Formattazione e leggibilità del riepilogo

**User Story:** Come operatore di rete, voglio che il riepilogo sia formattato in modo chiaro e leggibile nel terminale, così da poter individuare rapidamente le informazioni rilevanti.

#### Criteri di Accettazione

1. THE Sistema_Riepilogo SHALL formattare il riepilogo utilizzando separatori visivi, indentazione e icone di stato (ad esempio ✓ per successo, ✗ per fallimento) coerenti con lo stile di logging già presente in main.py.
2. THE Sistema_Riepilogo SHALL raggruppare le informazioni del riepilogo in sezioni distinte: intestazione con intent originale e modalità di generazione, dettaglio per ogni azione, e riepilogo finale con conteggio successi/fallimenti.
3. WHEN il riepilogo LLM è presente, THE Sistema_Riepilogo SHALL visualizzarlo in una sezione separata e chiaramente identificata dopo il riepilogo strutturato.

### Requisito 5: Integrazione nel flusso esistente di main.py

**User Story:** Come sviluppatore, voglio che il riepilogo si integri nel flusso di esecuzione esistente di main.py senza modificare il comportamento corrente delle azioni, così da mantenere la retrocompatibilità.

#### Criteri di Accettazione

1. THE Sistema_Riepilogo SHALL essere invocato nel flusso di main.py dopo lo Step 8 (esecuzione azioni) e prima della raccolta dello stato finale (Step 9), senza alterare la logica di esecuzione delle azioni.
2. THE Sistema_Riepilogo SHALL funzionare sia quando le azioni sono generate in modalità rule-based (confidence >= 0.8) sia quando sono generate tramite ChatGPT (confidence < 0.8).
3. IF il Sistema_Riepilogo genera un errore interno, THEN THE Sistema_Riepilogo SHALL registrare l'errore nel log e continuare l'esecuzione normale del programma senza interrompere il flusso.
