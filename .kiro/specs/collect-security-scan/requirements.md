# Documento dei Requisiti

## Introduzione

Questa funzionalità estende il comando `collect` del sistema di monitoraggio SDN per eseguire,
in modo opzionale, una scansione di sicurezza attiva degli host e degli switch della rete tramite
`nmap`. I risultati della scansione vengono integrati nello snapshot di rete esistente
(`NetworkSnapshot`) e inviati al `ChatGPTClient` per ottenere un'analisi delle vulnerabilità,
dei problemi di configurazione e delle proprietà di sicurezza da verificare.
La scansione non analizza il traffico di rete: si basa esclusivamente su scansione attiva con nmap.

## Glossario

- **Security_Scanner**: Componente responsabile dell'esecuzione di nmap sugli host/switch target e della raccolta dei risultati.
- **Nmap_Result**: Struttura dati che contiene l'output di nmap per un singolo host/switch (porte aperte, servizi rilevati, OS detection, ecc.).
- **Security_Snapshot**: Estensione del `NetworkSnapshot` che include i risultati nmap per ciascun host/switch scansionato.
- **Security_Analyzer**: Componente che costruisce il prompt per il `ChatGPTClient` a partire dal `Security_Snapshot` e interpreta la risposta.
- **Security_Report**: Struttura dati che contiene l'analisi LLM: lista di vulnerabilità potenziali, problemi di configurazione e proprietà di sicurezza da verificare.
- **ChatGPTClient**: Client esistente per le chiamate all'API OpenAI.
- **NetworkSnapshot**: Modello dati esistente che rappresenta lo snapshot completo della rete (topologia, metriche, switch, link).
- **NetworkStateCollector**: Componente esistente che raccoglie lo snapshot della rete dal controller Ryu.
- **Target_Host**: Host o switch della rete SDN identificato da un indirizzo IP nel range 10.0.0.x.
- **Host_Filter**: Lista opzionale di nomi host Mininet (es. `h1`, `h2`) o indirizzi IP forniti dall'utente per limitare la scansione a un sottoinsieme della topologia.

---

## Requisiti

### Requisito 1: Esecuzione della scansione nmap

**User Story:** Come operatore di rete, voglio che il comando `collect` possa eseguire una scansione nmap sugli host e switch della rete, in modo da raccogliere informazioni sulle porte aperte e i servizi esposti.

#### Criteri di Accettazione

1. WHEN il comando `collect` viene invocato con il flag `--security-scan`, THE `Security_Scanner` SHALL eseguire una scansione nmap su ciascun `Target_Host` identificato nella topologia corrente.
2. WHEN la topologia contiene N host/switch con indirizzi IP nel range 10.0.0.x, THE `Security_Scanner` SHALL scansionare tutti gli N indirizzi IP identificati.
3. WHEN la scansione nmap di un `Target_Host` viene completata entro 120 secondi, THE `Security_Scanner` SHALL raccogliere il relativo `Nmap_Result` contenente almeno: lista delle porte aperte, servizi associati e versione rilevata.
4. IF nmap non è installato sul sistema, THEN THE `Security_Scanner` SHALL restituire un errore descrittivo e interrompere la scansione senza modificare il `NetworkSnapshot`.
5. IF la scansione nmap di un singolo `Target_Host` supera 120 secondi, THEN THE `Security_Scanner` SHALL interrompere la scansione per quell'host, registrare un avviso nel log e continuare con i `Target_Host` rimanenti.
6. IF la scansione nmap di un singolo `Target_Host` fallisce per un errore di rete, THEN THE `Security_Scanner` SHALL registrare l'errore nel log e continuare con i `Target_Host` rimanenti.
7. WHEN il comando `collect` viene invocato con `--security-scan <host1> [host2 ...]`, THE `Security_Scanner` SHALL scansionare esclusivamente gli host specificati nell'`Host_Filter`, ignorando gli altri host presenti nella topologia.
8. WHEN un nome host Mininet (es. `h1`, `h2`) viene fornito nell'`Host_Filter`, THE `Security_Scanner` SHALL risolverlo nell'indirizzo IP corrispondente (convenzione: `hN` → `10.0.0.N`) prima di eseguire la scansione.
9. IF un nome host fornito nell'`Host_Filter` non corrisponde ad alcun host nella topologia corrente, THEN THE `Security_Scanner` SHALL registrare un avviso nel log e ignorare quell'host senza interrompere la scansione degli altri.

---

### Requisito 2: Integrazione dei risultati nmap nel NetworkSnapshot

**User Story:** Come operatore di rete, voglio che i risultati nmap vengano aggiunti allo snapshot di rete esistente, in modo da avere una visione unificata della topologia e della superficie di attacco.

#### Criteri di Accettazione

1. WHEN tutti i `Nmap_Result` sono stati raccolti, THE `Security_Scanner` SHALL produrre un `Security_Snapshot` che estende il `NetworkSnapshot` esistente aggiungendo un campo `security_scan` contenente i risultati nmap indicizzati per indirizzo IP.
2. THE `Security_Snapshot` SHALL mantenere tutti i campi originali del `NetworkSnapshot` (timestamp, topology, metrics, derived_metrics, metadata) invariati.
3. WHEN un `Target_Host` non è raggiungibile durante la scansione, THE `Security_Snapshot` SHALL includere per quell'host un `Nmap_Result` con stato `unreachable` e lista porte vuota.
4. THE `Security_Snapshot` SHALL essere serializzabile in JSON tramite il metodo `to_json()` esistente, includendo il campo `security_scan`.
5. FOR ALL `Security_Snapshot` validi, la serializzazione JSON seguita dalla deserializzazione SHALL produrre un oggetto equivalente all'originale (proprietà round-trip).

---

### Requisito 3: Analisi LLM del Security Snapshot

**User Story:** Come operatore di rete, voglio che l'LLM analizzi la topologia e i risultati nmap in modo da identificare vulnerabilità, problemi di configurazione e proprietà di sicurezza da verificare.

#### Criteri di Accettazione

1. WHEN un `Security_Snapshot` è disponibile, THE `Security_Analyzer` SHALL costruire un prompt strutturato che includa: la topologia della rete, le metriche aggregate e tutti i `Nmap_Result` del `Security_Snapshot`.
2. WHEN il prompt viene inviato al `ChatGPTClient`, THE `Security_Analyzer` SHALL includere un system message che istruisce l'LLM a rispondere con un JSON strutturato contenente i campi: `vulnerabilities`, `configuration_issues` e `security_properties`.
3. WHEN il `ChatGPTClient` restituisce una risposta valida, THE `Security_Analyzer` SHALL produrre un `Security_Report` con: una lista di vulnerabilità potenziali (campo `vulnerabilities`), una lista di problemi di configurazione (campo `configuration_issues`) e una lista di proprietà di sicurezza da verificare (campo `security_properties`).
4. IF il `ChatGPTClient` restituisce una risposta non parsabile come JSON valido, THEN THE `Security_Analyzer` SHALL registrare l'errore nel log e restituire un `Security_Report` con i tre campi valorizzati come liste vuote e un campo `raw_response` contenente la risposta originale.
5. IF il `ChatGPTClient` solleva un'eccezione durante la chiamata API, THEN THE `Security_Analyzer` SHALL propagare l'eccezione al chiamante dopo averla registrata nel log.
6. THE `Security_Analyzer` SHALL inviare al `ChatGPTClient` un prompt la cui lunghezza totale non superi 12000 token stimati; WHERE il `Security_Snapshot` supera tale limite, THE `Security_Analyzer` SHALL troncare i campi `Nmap_Result` meno rilevanti mantenendo sempre la topologia completa.

---

### Requisito 4: Integrazione nel comando collect

**User Story:** Come operatore di rete, voglio attivare la scansione di sicurezza tramite un flag opzionale del comando `collect`, in modo da non impattare il comportamento esistente quando la scansione non è richiesta.

#### Criteri di Accettazione

1. WHEN il comando `collect` viene invocato senza il flag `--security-scan`, THE `NetworkStateCollector` SHALL eseguire la raccolta dello snapshot con il comportamento esistente, senza eseguire alcuna scansione nmap.
2. WHEN il comando `collect` viene invocato con il flag `--security-scan` senza argomenti aggiuntivi, THE `NetworkStateCollector` SHALL eseguire prima la raccolta dello snapshot standard e poi avviare il `Security_Scanner` su tutti gli host della topologia.
3. WHEN il comando `collect` viene invocato con `--security-scan <host1> [host2 ...]`, THE `NetworkStateCollector` SHALL passare l'`Host_Filter` al `Security_Scanner` per limitare la scansione agli host specificati.
4. WHEN la scansione di sicurezza è completata, THE `NetworkStateCollector` SHALL stampare a schermo il `Security_Report` in formato leggibile, includendo le sezioni: "Vulnerabilità Potenziali", "Problemi di Configurazione" e "Proprietà di Sicurezza da Verificare".
5. WHILE la scansione nmap è in esecuzione, THE `Security_Scanner` SHALL aggiornare il log con il progresso indicando il numero di host scansionati sul totale (es. "Scansione 2/5: 10.0.0.2").
6. WHERE la variabile d'ambiente `SECURITY_SCAN_TIMEOUT` è configurata, THE `Security_Scanner` SHALL utilizzare il valore specificato (in secondi interi) come timeout per ciascun host al posto del valore predefinito di 120 secondi.

---

### Requisito 5: Serializzazione e parsing del Security Report

**User Story:** Come operatore di rete, voglio che il `Security_Report` possa essere salvato su file e riletto in seguito, in modo da conservare uno storico delle analisi di sicurezza.

#### Criteri di Accettazione

1. THE `Security_Report` SHALL essere serializzabile in JSON tramite un metodo `to_json()` che produca un JSON valido con i campi `vulnerabilities`, `configuration_issues`, `security_properties`, `timestamp` e `snapshot_timestamp`.
2. THE `Security_Report` SHALL essere deserializzabile da JSON tramite un metodo di classe `from_json()` che ricostruisca un oggetto equivalente.
3. FOR ALL `Security_Report` validi, la serializzazione tramite `to_json()` seguita dalla deserializzazione tramite `from_json()` SHALL produrre un oggetto con campi identici all'originale (proprietà round-trip).
4. WHEN il `NetworkStateCollector` completa una scansione di sicurezza, THE `NetworkStateCollector` SHALL salvare il `Security_Report` su file nella directory `data/security_history/` con nome `security_report_{timestamp_iso}.json`.
5. IF la directory `data/security_history/` non esiste, THEN THE `NetworkStateCollector` SHALL crearla prima di salvare il file.
