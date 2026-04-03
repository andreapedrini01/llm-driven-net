# Piano di Implementazione: Network Change Summary

## Panoramica

Implementazione del modulo `src/services/change_summary.py` con funzioni pure per la formattazione del riepilogo delle modifiche di rete, integrazione in `main.py` tra Step 8 e Step 9, e test property-based con Hypothesis.

## Task

- [ ] 1. Creare il modulo `src/services/change_summary.py` con le funzioni di formattazione
  - [ ] 1.1 Implementare `format_action_detail(action, result)` che formatta il dettaglio di una singola azione eseguita con tipo, target, parametri (se successo) o errore (se fallimento), icona di stato (✓/✗) e durata
    - Usare `NetworkAction` da `src/models/actions.py` e `ExecutionResult` / `ExecutionStatus` da `northbound_script_generator/action_processor.py`
    - _Requisiti: 1.1, 1.2, 1.3, 4.1_

  - [ ] 1.2 Implementare `compute_state_diff(state_before, state_after)` che calcola le differenze tra due dizionari di stato di rete, identificando chiavi aggiunte, rimosse e modificate
    - Ritornare `None` se uno dei due stati è `None`
    - _Requisiti: 2.1, 2.2_

  - [ ] 1.3 Implementare `format_summary_header(intent_text, confidence, threshold)` che formatta l'intestazione con intent originale, modalità (Rule-based/LLM) e confidence
    - _Requisiti: 1.4, 4.2_

  - [ ] 1.4 Implementare `format_summary_footer(results)` che formatta il riepilogo finale con conteggio successi/fallimenti e percentuale
    - _Requisiti: 4.1, 4.2_

  - [ ] 1.5 Implementare `generate_summary(intent_text, confidence, actions, results, llm_summary, threshold)` come funzione di orchestrazione che combina header, dettagli azioni, diff, footer e sezione LLM opzionale
    - Gestire input malformati (None, liste vuote, parametri mancanti) senza lanciare eccezioni
    - _Requisiti: 4.2, 4.3, 5.3_

- [ ] 2. Implementare le funzioni per il riepilogo LLM
  - [ ] 2.1 Implementare `build_llm_prompt(intent_text, actions, results)` che costruisce il prompt per il ChatGPTClient contenente intent originale, tipo/target di ogni azione e stato di ogni risultato
    - _Requisiti: 3.4_

  - [ ] 2.2 Implementare `generate_llm_summary(chatgpt_client, intent_text, actions, results)` come funzione async che invoca il ChatGPTClient e ritorna il testo del riepilogo o `None` in caso di errore
    - Non deve lanciare eccezioni; loggare warning in caso di errore
    - _Requisiti: 3.1, 3.2, 3.3_

- [ ] 3. Checkpoint - Verificare che il modulo sia completo e importabile
  - Assicurarsi che tutti i test passino, chiedere all'utente in caso di dubbi.

- [ ] 4. Integrare il modulo in `main.py`
  - [ ] 4.1 Aggiungere l'import di `generate_summary` e `generate_llm_summary` da `src.services.change_summary` in `main.py`
    - _Requisiti: 5.1_

  - [ ] 4.2 Inserire la chiamata al riepilogo nel flusso di `main.py` dopo lo Step 8 (esecuzione azioni) e prima dello Step 9 (verifica stato finale)
    - Controllare la variabile d'ambiente `ENABLE_LLM_SUMMARY` per abilitare il riepilogo LLM
    - Wrappare in try/except per non interrompere il flusso in caso di errore
    - _Requisiti: 5.1, 5.2, 5.3_

- [ ] 5. Checkpoint - Verificare integrazione in main.py
  - Assicurarsi che tutti i test passino, chiedere all'utente in caso di dubbi.

- [ ] 6. Test property-based e unit test
  - [ ]* 6.1 Scrivere property test per la completezza del riepilogo per azione
    - **Proprietà 1: Completezza del riepilogo per azione**
    - **Valida: Requisiti 1.1, 1.2, 1.3**
    - File: `tests/property/test_change_summary_properties.py`

  - [ ]* 6.2 Scrivere property test per modalità e confidence nel riepilogo
    - **Proprietà 2: Modalità e confidence nel riepilogo**
    - **Valida: Requisito 1.4**

  - [ ]* 6.3 Scrivere property test per la correttezza del diff di stato
    - **Proprietà 3: Correttezza del diff di stato di rete**
    - **Valida: Requisiti 2.1, 2.2**

  - [ ]* 6.4 Scrivere property test per la completezza del prompt LLM
    - **Proprietà 4: Completezza del prompt LLM**
    - **Valida: Requisito 3.4**

  - [ ]* 6.5 Scrivere property test per formattazione e conteggio corretti
    - **Proprietà 5: Formattazione e conteggio corretti**
    - **Valida: Requisiti 4.1, 4.2**

  - [ ]* 6.6 Scrivere property test per resilienza a input malformati
    - **Proprietà 6: Resilienza a input malformati**
    - **Valida: Requisito 5.3**

  - [ ]* 6.7 Scrivere unit test per il riepilogo LLM (sezione separata, gestione errori ChatGPTClient)
    - Test che il riepilogo LLM appaia in sezione separata dopo il riepilogo strutturato
    - Test che `generate_llm_summary` ritorni `None` quando il ChatGPTClient lancia eccezione
    - File: `tests/unit/test_change_summary.py`
    - _Requisiti: 3.3, 4.3_

- [ ] 7. Checkpoint finale - Verificare che tutti i test passino
  - Assicurarsi che tutti i test passino, chiedere all'utente in caso di dubbi.

## Note

- I task con `*` sono opzionali e possono essere saltati per un MVP più rapido
- Ogni task referenzia i requisiti specifici per tracciabilità
- I checkpoint garantiscono validazione incrementale
- I property test validano le proprietà di correttezza universali definite nel design
- Gli unit test validano esempi specifici e casi limite
