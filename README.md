# Network State Collector

Un sistema modulare e robusto per raccogliere, elaborare e fornire dati di stato della rete in tempo reale per l'integrazione con modelli LLM.

## Caratteristiche

- **Raccolta dati completa**: Topologia di rete e metriche di prestazioni dal controller Ryu
- **Integrazione LLM**: Formato dati ottimizzato per modelli di linguaggio
- **Resilienza**: Gestione errori robusta con retry automatico e backoff esponenziale
- **Configurabilità**: Configurazione flessibile tramite file YAML/JSON
- **Monitoraggio**: Health check e metriche di qualità dati integrate
- **Testing**: Test unitari e property-based testing con Hypothesis

## Installazione

### Requisiti

- Python 3.8+
- Controller Ryu SDN accessibile via HTTP

### Installazione da sorgenti

```bash
# Clona il repository
git clone https://github.com/andreapedrini01/llm-driven-net.git
cd network-state-collector

# Installa dipendenze
pip install -r requirements.txt

# Installa il pacchetto
pip install -e .
```

### Installazione per sviluppo

```bash
# Installa dipendenze di sviluppo
pip install -r requirements.txt
pip install -e ".[dev,test]"

# Esegui i test
pytest

# Formattazione codice
black network_state_collector tests
isort network_state_collector tests
```

## Configurazione

Il sistema utilizza file di configurazione YAML o JSON. Esempi disponibili in `config/`:

- `development.yaml`: Configurazione per sviluppo
- `production.yaml`: Configurazione per produzione  
- `example.json`: Esempio in formato JSON

### Configurazione base

```yaml
# config/my_config.yaml
ryu:
  host: localhost
  port: 8080
  timeout: 30.0

collection:
  interval: 30.0
  continuous_mode: false

output:
  directory: "data"
  pretty_print: true

logging:
  level: "INFO"
  console_output: true
```

## Utilizzo

### Command Line Interface

```bash
# Raccolta singola snapshot
network-state-collector collect --config config/development.yaml

# Raccolta continua
network-state-collector continuous --config config/production.yaml --interval 10

# Verifica stato di salute
network-state-collector health --config config/production.yaml

# Aiuto
network-state-collector --help
```

### Utilizzo programmatico

```python
from network_state_collector import NetworkStateCollector, CollectorConfig

# Carica configurazione
config = CollectorConfig.load_from_file("config/development.yaml")

# Crea collector
collector = NetworkStateCollector(config)

# Raccolta singola
snapshot = collector.collect_snapshot()
if snapshot:
    print(f"Raccolti {len(snapshot.topology.switches)} switch")
    print(f"Timestamp: {snapshot.get_timestamp_iso()}")

# Raccolta continua
collector.start_continuous_collection(interval=30.0)
```

## Struttura dati

### NetworkSnapshot

Snapshot completo dello stato della rete:

```python
@dataclass
class NetworkSnapshot:
    timestamp: float
    topology: TopologyData
    metrics: MetricsData
    derived_metrics: Optional[DerivedMetrics]
    metadata: Optional[SnapshotMetadata]
```

### TopologyData

Dati di topologia (switch e link):

```python
@dataclass
class TopologyData:
    switches: List[SwitchInfo]
    links: List[LinkInfo]
    graph_representation: Dict[str, Any]
```

### MetricsData

Metriche di prestazioni delle porte:

```python
@dataclass
class MetricsData:
    port_statistics: Dict[str, List[PortMetrics]]
    aggregated_metrics: Dict[str, AggregatedMetrics]
    quality_indicators: Optional[QualityMetrics]
```

## Integrazione LLM

Il sistema genera dati nel formato ottimizzato per il repository [llm-driven-net](https://github.com/andreapedrini01/llm-driven-net):

```json
{
  "timestamp": 1640995200.0,
  "network_context": {
    "topology": {
      "nodes": ["0000000000000001", "0000000000000002"],
      "edges": [{"src": "0000000000000001", "dst": "0000000000000002", "port_out": 1, "port_in": 2}]
    },
    "performance": {
      "utilization_vectors": [[0.1, 0.2], [0.3, 0.4]],
      "error_rates": [0.001, 0.002],
      "congestion_indicators": [false, true]
    }
  }
}
```

### Directory di output

```
data/
├── network_context_latest.json      # Snapshot più recente
├── network_context_history/         # Storico per training
├── embeddings/                      # Embedding pre-calcolati
└── metadata/                        # Metadati per LLM
```

## Testing

Il progetto utilizza un approccio di testing duale:

### Test unitari

```bash
# Esegui tutti i test
pytest

# Test specifici
pytest tests/test_models.py -v

# Con copertura
pytest --cov=network_state_collector
```

### Property-based testing

Utilizza [Hypothesis](https://hypothesis.readthedocs.io/) per test basati su proprietà:

```python
@given(network_snapshot_strategy())
def test_round_trip_serialization(snapshot):
    """Property 22: Round-trip Serializzazione"""
    json_str = snapshot.to_json()
    parsed = NetworkSnapshot.from_json(json_str)
    assert parsed.timestamp == snapshot.timestamp
```

## Architettura

Il sistema è organizzato in layer modulari:

- **Data Collection Layer**: Connessione e raccolta dati da Ryu
- **Processing Layer**: Elaborazione, validazione e formattazione
- **Integration Layer**: Integrazione LLM e serializzazione
- **Control Layer**: Configurazione, errori e logging

## Contribuire

1. Fork del repository
2. Crea branch per la feature (`git checkout -b feature/amazing-feature`)
3. Commit delle modifiche (`git commit -m 'Add amazing feature'`)
4. Push del branch (`git push origin feature/amazing-feature`)
5. Apri una Pull Request

### Linee guida

- Segui PEP 8 per lo stile del codice
- Aggiungi test per nuove funzionalità
- Aggiorna la documentazione
- Usa type hints

## Licenza

Questo progetto è rilasciato sotto licenza MIT. Vedi il file `LICENSE` per dettagli.

## Supporto

Per domande, bug report o richieste di feature:

- Apri un issue su GitHub
- Consulta la documentazione nel repository [llm-driven-net](https://github.com/andreapedrini01/llm-driven-net)

## Roadmap

- [ ] Implementazione completa RyuConnector
- [ ] DataProcessor per elaborazione dati
- [ ] Validazione e qualità dati
- [ ] Integrazione LLM avanzata
- [ ] Modalità daemon
- [ ] Metriche Prometheus
- [ ] Dashboard web