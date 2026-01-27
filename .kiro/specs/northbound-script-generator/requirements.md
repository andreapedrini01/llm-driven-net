# Documento dei Requisiti

## Introduzione

Il modulo Northbound Script Generator è un sistema avanzato per la gestione di reti controllate da LLM che riceve azioni da un Large Language Model e le applica alla rete ComnetsEMU/RYU. Il sistema attuale include una base solida con modelli di dati, logging avanzato, gestione retry e rollback, ma necessita di miglioramenti significativi per diventare un sistema di produzione completo.

## Glossario

- **Northbound_Module**: Il modulo principale che riceve e processa le azioni di rete
- **ComnetsEMU**: Emulatore di rete utilizzato per simulare topologie di rete
- **RYU_Controller**: Controller SDN (Software Defined Networking) per la gestione della rete
- **LLM**: Large Language Model che genera azioni di rete
- **Action_Model**: Modello di dati che rappresenta un'azione di rete
- **REST_API**: Interfaccia di programmazione per ricevere comandi HTTP
- **Web_Interface**: Interfaccia web per visualizzazione e controllo del sistema
- **Monitoring_System**: Sistema di monitoraggio in tempo reale delle metriche
- **Authentication_System**: Sistema di sicurezza per l'autenticazione degli utenti
- **Backup_System**: Sistema di backup e recovery dei dati

## Requisiti

### Requisito 1: Integrazione ComnetsEMU/RYU Reale

**User Story:** Come amministratore di rete, voglio che il sistema si integri realmente con ComnetsEMU e RYU controller, così da poter applicare effettivamente le azioni di rete generate dall'LLM.

#### Criteri di Accettazione

1. QUANDO il Northbound_Module riceve un'azione di rete, ALLORA il sistema DEVE connettersi al RYU_Controller e applicare l'azione
2. QUANDO si verifica un errore di connessione con ComnetsEMU, ALLORA il sistema DEVE registrare l'errore e tentare il rollback
3. QUANDO un'azione viene applicata con successo, ALLORA il sistema DEVE verificare lo stato della rete e confermare l'applicazione
4. QUANDO il RYU_Controller non è disponibile, ALLORA il sistema DEVE mettere in coda le azioni e riprovare automaticamente
5. IL sistema DEVE supportare tutte le operazioni di rete standard (creazione/modifica/eliminazione di flussi, topologie, QoS)

### Requisito 2: API REST per Comandi LLM

**User Story:** Come sviluppatore LLM, voglio un'API REST per inviare comandi di rete, così da poter integrare facilmente il sistema con diversi LLM.

#### Criteri di Accettazione

1. QUANDO un LLM invia una richiesta POST all'endpoint /api/actions, ALLORA il sistema DEVE validare e processare l'azione
2. QUANDO viene ricevuta una richiesta malformata, ALLORA il sistema DEVE restituire un errore HTTP 400 con dettagli specifici
3. QUANDO un'azione viene processata con successo, ALLORA il sistema DEVE restituire un ID di tracking e lo stato
4. IL sistema DEVE supportare autenticazione tramite API key per ogni richiesta
5. IL sistema DEVE fornire endpoint per interrogare lo stato delle azioni in corso
6. IL sistema DEVE supportare operazioni batch per multiple azioni simultanee

### Requisito 3: Sistema di Monitoraggio e Metriche

**User Story:** Come amministratore di sistema, voglio monitorare le prestazioni e lo stato del sistema in tempo reale, così da poter identificare e risolvere problemi rapidamente.

#### Criteri di Accettazione

1. QUANDO il sistema è in esecuzione, ALLORA il Monitoring_System DEVE raccogliere metriche di prestazione ogni secondo
2. QUANDO una metrica supera una soglia critica, ALLORA il sistema DEVE generare un alert automatico
3. QUANDO si verifica un errore, ALLORA il sistema DEVE registrare metriche dettagliate per l'analisi
4. IL sistema DEVE esporre metriche via endpoint /metrics in formato Prometheus
5. IL sistema DEVE mantenere uno storico delle metriche per almeno 30 giorni
6. QUANDO la memoria o CPU raggiungono il 90%, ALLORA il sistema DEVE attivare modalità di protezione

### Requisito 4: Sistema di Sicurezza e Autenticazione

**User Story:** Come amministratore di sicurezza, voglio un sistema robusto di autenticazione e autorizzazione, così da proteggere l'accesso alle funzionalità critiche di rete.

#### Criteri di Accettazione

1. QUANDO un utente tenta di accedere al sistema, ALLORA l'Authentication_System DEVE richiedere credenziali valide
2. QUANDO vengono fornite credenziali errate per 3 volte consecutive, ALLORA il sistema DEVE bloccare l'account per 15 minuti
3. QUANDO un utente è autenticato, ALLORA il sistema DEVE verificare i permessi per ogni azione richiesta
4. IL sistema DEVE supportare autenticazione multi-fattore (MFA) per utenti amministratori
5. IL sistema DEVE registrare tutti i tentativi di accesso e le azioni privilegiate
6. QUANDO una sessione è inattiva per più di 30 minuti, ALLORA il sistema DEVE invalidarla automaticamente

### Requisito 5: Interfaccia Web di Controllo

**User Story:** Come operatore di rete, voglio un'interfaccia web intuitiva per visualizzare lo stato del sistema e controllare le operazioni, così da poter gestire efficacemente la rete.

#### Criteri di Accettazione

1. QUANDO un utente accede alla Web_Interface, ALLORA il sistema DEVE mostrare una dashboard con lo stato corrente della rete
2. QUANDO vengono visualizzate le azioni in corso, ALLORA il sistema DEVE mostrare progress bar e tempi stimati
3. QUANDO un utente seleziona un'azione, ALLORA il sistema DEVE mostrare dettagli completi e log associati
4. IL sistema DEVE permettere l'annullamento di azioni in corso tramite interfaccia web
5. IL sistema DEVE aggiornare la visualizzazione in tempo reale senza refresh manuale
6. QUANDO si verifica un errore critico, ALLORA l'interfaccia DEVE mostrare notifiche prominenti

### Requisito 6: Sistema di Backup e Recovery

**User Story:** Come amministratore di sistema, voglio un sistema automatico di backup e recovery, così da poter ripristinare il sistema in caso di guasti.

#### Criteri di Accettazione

1. QUANDO il sistema è in esecuzione, ALLORA il Backup_System DEVE creare backup automatici ogni ora
2. QUANDO viene richiesto un ripristino, ALLORA il sistema DEVE permettere la selezione di un punto di ripristino specifico
3. QUANDO si verifica un guasto critico, ALLORA il sistema DEVE tentare il recovery automatico dall'ultimo backup valido
4. IL sistema DEVE mantenere backup per almeno 7 giorni con rotazione automatica
5. IL sistema DEVE verificare l'integrità dei backup durante la creazione
6. QUANDO un backup fallisce, ALLORA il sistema DEVE notificare immediatamente gli amministratori

### Requisito 7: Testing Automatizzato e Simulazione

**User Story:** Come sviluppatore, voglio un sistema completo di testing automatizzato, così da poter validare le modifiche e garantire la qualità del codice.

#### Criteri di Accettazione

1. QUANDO viene eseguita la suite di test, ALLORA il sistema DEVE validare tutte le funzionalità core in meno di 5 minuti
2. QUANDO vengono eseguiti test di integrazione, ALLORA il sistema DEVE simulare scenari di rete realistici
3. QUANDO si verifica un test fallito, ALLORA il sistema DEVE fornire log dettagliati per il debugging
4. IL sistema DEVE supportare test di carico per validare le prestazioni sotto stress
5. IL sistema DEVE eseguire test automatici ad ogni commit nel repository
6. QUANDO vengono rilevate regressioni, ALLORA il sistema DEVE bloccare il deployment automaticamente

### Requisito 8: Documentazione API e Deployment

**User Story:** Come sviluppatore integratore, voglio documentazione completa delle API e procedure di deployment, così da poter utilizzare e deployare il sistema efficacemente.

#### Criteri di Accettazione

1. QUANDO un sviluppatore accede alla documentazione API, ALLORA il sistema DEVE fornire esempi interattivi per ogni endpoint
2. QUANDO viene rilasciata una nuova versione, ALLORA la documentazione DEVE essere aggiornata automaticamente
3. QUANDO viene eseguito il deployment, ALLORA il sistema DEVE seguire procedure automatizzate e verificabili
4. IL sistema DEVE fornire guide step-by-step per l'installazione in diversi ambienti
5. IL sistema DEVE includere troubleshooting guide per problemi comuni
6. QUANDO la documentazione viene modificata, ALLORA il sistema DEVE validare la correttezza degli esempi

### Requisito 9: Gestione Configurazione e Logging Avanzato

**User Story:** Come amministratore di sistema, voglio un sistema flessibile di configurazione e logging avanzato, così da poter personalizzare il comportamento del sistema e diagnosticare problemi.

#### Criteri di Accettazione

1. QUANDO viene modificata una configurazione, ALLORA il sistema DEVE applicare le modifiche senza riavvio quando possibile
2. QUANDO si verifica un evento significativo, ALLORA il sistema DEVE registrarlo con livello di dettaglio appropriato
3. QUANDO vengono consultati i log, ALLORA il sistema DEVE permettere filtri avanzati per timestamp, livello, componente
4. IL sistema DEVE supportare configurazione tramite file YAML, variabili d'ambiente e API
5. IL sistema DEVE validare la configurazione all'avvio e segnalare errori chiaramente
6. QUANDO i log raggiungono dimensioni critiche, ALLORA il sistema DEVE eseguire rotazione automatica

### Requisito 10: Scalabilità e Performance

**User Story:** Come architetto di sistema, voglio che il sistema sia scalabile e performante, così da poter gestire carichi di lavoro crescenti senza degradazione.

#### Criteri di Accettazione

1. QUANDO il carico aumenta, ALLORA il sistema DEVE mantenere tempi di risposta sotto i 100ms per il 95% delle richieste
2. QUANDO vengono processate azioni multiple, ALLORA il sistema DEVE supportare elaborazione parallela efficiente
3. QUANDO la memoria è sotto pressione, ALLORA il sistema DEVE implementare strategie di garbage collection ottimizzate
4. IL sistema DEVE supportare deployment distribuito su multiple istanze
5. IL sistema DEVE implementare connection pooling per le connessioni database e di rete
6. QUANDO si raggiungono limiti di capacità, ALLORA il sistema DEVE implementare backpressure e rate limiting