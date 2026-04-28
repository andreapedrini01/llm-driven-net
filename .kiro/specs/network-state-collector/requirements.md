# Documento dei Requisiti

## Introduzione

Il Network State Collector è un componente critico del sistema di intent-based networking con LLM che raccoglie, elabora e fornisce dati di stato della rete in tempo reale. Il sistema deve integrarsi perfettamente con i modelli LLM del team per supportare l'analisi intelligente della rete, il rilevamento di anomalie e l'ottimizzazione automatica delle prestazioni.

## Glossario

- **Collector**: Il sistema di raccolta dati di stato della rete
- **Ryu_Controller**: Il controller SDN che espone le API REST per i dati di rete
- **LLM_Models**: I modelli di linguaggio del team per l'analisi della rete
- **Network_State**: Lo stato completo della rete inclusi topologia e metriche
- **Snapshot**: Un'istantanea temporale dello stato della rete
- **Intent_Engine**: Il motore che interpreta gli intent di rete tramite LLM
- **Anomaly_Detector**: Il componente LLM per il rilevamento di anomalie

## Requisiti

### Requisito 1: Raccolta Dati di Topologia

**User Story:** Come sviluppatore di modelli LLM, voglio ricevere dati di topologia strutturati e consistenti, così da poter addestrare e utilizzare modelli per l'analisi della rete.

#### Criteri di Accettazione

1. QUANDO il Collector si connette al Ryu_Controller, IL Sistema DEVE recuperare la lista completa degli switch attivi
2. QUANDO il Collector richiede i link di topologia, IL Sistema DEVE ottenere tutte le connessioni tra switch con porte di ingresso e uscita
3. QUANDO il Collector formatta i dati di topologia, IL Sistema DEVE convertire tutti i DPID in formato esadecimale a 16 cifre per consistenza
4. QUANDO si verifica un errore di connessione, IL Sistema DEVE gestire l'errore e continuare con i dati disponibili
5. IL Collector DEVE fornire i dati di topologia in formato JSON strutturato per l'integrazione con LLM_Models

### Requisito 2: Raccolta Metriche di Prestazioni

**User Story:** Come data scientist che lavora sui modelli LLM, voglio metriche dettagliate delle prestazioni di rete, così da poter identificare pattern e anomalie per l'ottimizzazione automatica.

#### Criteri di Accettazione

1. QUANDO il Collector raccoglie statistiche delle porte, IL Sistema DEVE ottenere pacchetti RX/TX, errori RX/TX e bytes RX/TX per ogni porta
2. QUANDO il Collector elabora le statistiche, IL Sistema DEVE escludere le porte LOCAL del controller per evitare dati irrilevanti
3. QUANDO il Collector calcola le metriche, IL Sistema DEVE fornire dati sufficienti per calcolare utilizzo, congestione e tasso di errore
4. IL Collector DEVE associare ogni metrica al timestamp di raccolta per l'analisi temporale
5. QUANDO si verificano errori nella raccolta metriche, IL Sistema DEVE registrare l'errore e continuare con gli altri switch

### Requisito 3: Integrazione con Modelli LLM

**User Story:** Come sviluppatore del team LLM, voglio ricevere dati in un formato ottimizzato per i nostri modelli, così da poter implementare efficacemente l'analisi intelligente della rete.

#### Criteri di Accettazione

1. QUANDO il Collector salva i dati, IL Sistema DEVE utilizzare il formato JSON compatibile con il repository github.com/andreapedrini01/llm-driven-net
2. QUANDO il Collector genera uno snapshot, IL Sistema DEVE includere timestamp, topologia e metriche di prestazioni in una struttura unificata
3. QUANDO il Collector scrive i file di output, IL Sistema DEVE salvare in una directory configurabile per l'integrazione con LLM_Models
4. IL Collector DEVE generare file con nomi consistenti per il caricamento automatico da parte di LLM_Models
5. QUANDO i dati sono pronti, IL Sistema DEVE notificare la disponibilità per l'elaborazione LLM

### Requisito 4: Raccolta Dati in Tempo Reale

**User Story:** Come operatore di rete, voglio monitoraggio continuo dello stato della rete, così da poter reagire rapidamente a cambiamenti e problemi.

#### Criteri di Accettazione

1. QUANDO il Collector viene avviato in modalità continua, IL Sistema DEVE raccogliere dati a intervalli configurabili
2. QUANDO il Collector rileva cambiamenti significativi nella topologia, IL Sistema DEVE generare immediatamente un nuovo snapshot
3. QUANDO il Collector monitora le prestazioni, IL Sistema DEVE mantenere uno storico delle metriche per l'analisi dei trend
4. IL Collector DEVE supportare sia raccolta on-demand che continua per diversi casi d'uso
5. QUANDO il sistema è sotto carico, IL Sistema DEVE mantenere la raccolta dati senza impattare le prestazioni del controller

### Requisito 5: Gestione Errori e Resilienza

**User Story:** Come amministratore di sistema, voglio che il collector sia robusto e resiliente, così da garantire continuità nella raccolta dati anche in presenza di problemi di rete.

#### Criteri di Accettazione

1. QUANDO il Ryu_Controller non è raggiungibile, IL Sistema DEVE ritentare la connessione con backoff esponenziale
2. QUANDO si verificano timeout nelle richieste API, IL Sistema DEVE gestire l'errore e continuare con le altre operazioni
3. QUANDO i dati ricevuti sono malformati, IL Sistema DEVE validare e scartare dati inconsistenti
4. IL Collector DEVE registrare tutti gli errori per il debugging e il monitoraggio
5. QUANDO si verifica un errore critico, IL Sistema DEVE notificare l'amministratore mantenendo il servizio attivo

### Requisito 6: Configurabilità e Estensibilità

**User Story:** Come sviluppatore del sistema, voglio un collector configurabile e estensibile, così da poter adattarlo a diversi ambienti e requisiti futuri.

#### Criteri di Accettazione

1. QUANDO il Collector viene configurato, IL Sistema DEVE supportare configurazione di endpoint Ryu, directory di output e intervalli di raccolta
2. QUANDO si aggiungono nuove metriche, IL Sistema DEVE permettere estensione senza modificare il codice core
3. QUANDO si cambia ambiente, IL Sistema DEVE supportare diversi formati di output per diversi consumer LLM
4. IL Collector DEVE supportare plugin per metriche personalizzate e trasformazioni dati
5. QUANDO si integra con nuovi controller, IL Sistema DEVE permettere adapter per diverse API SDN

### Requisito 7: Validazione e Qualità Dati

**User Story:** Come data scientist, voglio dati di alta qualità e validati, così da poter costruire modelli LLM affidabili per l'analisi della rete.

#### Criteri di Accettazione

1. QUANDO il Collector riceve dati dal controller, IL Sistema DEVE validare la completezza e consistenza dei dati
2. QUANDO il Collector rileva dati anomali, IL Sistema DEVE segnalare le anomalie e applicare correzioni quando possibile
3. QUANDO il Collector genera snapshot, IL Sistema DEVE verificare l'integrità dei dati prima del salvataggio
4. IL Collector DEVE fornire metriche di qualità dei dati per il monitoraggio
5. QUANDO i dati non superano la validazione, IL Sistema DEVE scartare lo snapshot e registrare l'evento

### Requisito 8: Parsing e Serializzazione Dati

**User Story:** Come sviluppatore di sistema, voglio parsing e serializzazione affidabili dei dati di rete, così da garantire integrità e consistenza nell'elaborazione.

#### Criteri di Accettazione

1. QUANDO il Collector riceve dati JSON dal Ryu_Controller, IL Sistema DEVE parsificarli secondo la specifica API Ryu
2. QUANDO il Collector serializza i dati per LLM_Models, IL Sistema DEVE utilizzare la codifica JSON con formattazione consistente
3. IL Pretty_Printer DEVE formattare gli oggetti Network_State in file JSON validi e leggibili
4. PER TUTTI gli oggetti Network_State validi, il parsing seguito dalla serializzazione seguito dal parsing DEVE produrre un oggetto equivalente (proprietà round-trip)
5. QUANDO si verificano errori di parsing, IL Sistema DEVE restituire errori descrittivi per il debugging