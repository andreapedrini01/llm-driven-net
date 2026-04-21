"""
Test script per il modulo LLM usando il file network_context_latest.json
Questo script testa il modulo senza utilizzare ChatGPT API.
"""

import json
from pathlib import Path
from datetime import datetime

# Import dei componenti del modulo
from llm_integration_module.services.state_file_reader import StateFileReader
from llm_integration_module.services.intent_parser import IntentParser
from llm_integration_module.services.context_analyzer import ContextAnalyzer
from llm_integration_module.models.intent import IntentObject
from llm_integration_module.utils.logging import configure_logging, get_logger

# Configura logging
configure_logging(log_level="INFO", json_logs=False)
logger = get_logger(__name__)


def print_separator(title: str):
    """Stampa un separatore visivo."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def test_load_network_state():
    """Test 1: Caricamento del file JSON."""
    print_separator("TEST 1: Caricamento Network State")
    
    # Usa il file JSON convertito
    json_file = "network_context_converted.json"
    
    if not Path(json_file).exists():
        logger.error(f"File {json_file} non trovato!")
        return None
    
    # Crea il reader
    reader = StateFileReader(cache_folder=".", state_file_name=json_file)
    
    # Carica lo stato
    logger.info(f"Caricamento file: {json_file}")
    network_state = reader.load_network_state()
    
    if network_state:
        logger.info("✓ Network state caricato con successo!")
        print(f"\nTimestamp: {network_state.timestamp}")
        print(f"Switches: {len(network_state.topology.switches)}")
        print(f"Links: {len(network_state.topology.links)}")
        print(f"Hosts: {len(network_state.topology.hosts)}")
        print(f"Anomalie rilevate: {len(network_state.anomalies)}")
        
        # Mostra dettagli switches
        print("\nDettagli Switches:")
        for switch in network_state.topology.switches:
            print(f"  - {switch.name} (DPID: {switch.dpid})")
            print(f"    Porte: {switch.ports}")
            print(f"    Status: {switch.status}")
        
        # Mostra dettagli hosts
        print("\nDettagli Hosts:")
        for host in network_state.topology.hosts:
            print(f"  - {host.id}")
            print(f"    MAC: {host.mac_address}, IP: {host.ip_address}")
            print(f"    Connesso a: {host.connected_switch}:{host.connected_port}")
        
        # Mostra anomalie
        if network_state.anomalies:
            print("\nAnomalie Rilevate:")
            for anomaly in network_state.anomalies:
                print(f"  - Tipo: {anomaly.type}")
                print(f"    Severità: {anomaly.severity}")
                print(f"    Descrizione: {anomaly.description}")
                print(f"    Componenti: {anomaly.affected_resources}")
        
        # Mostra metriche
        print("\nMetriche di Rete:")
        print(f"  Bandwidth:")
        print(f"    - Capacità totale: {network_state.metrics.bandwidth.total_capacity}")
        print(f"    - Utilizzata: {network_state.metrics.bandwidth.used_bandwidth}")
        print(f"    - Disponibile: {network_state.metrics.bandwidth.available_bandwidth}")
        print(f"    - Utilizzo: {network_state.metrics.bandwidth.utilization_percentage}%")
        
        return network_state
    else:
        logger.error("✗ Errore nel caricamento del network state")
        return None


def test_intent_parsing():
    """Test 2: Parsing di intent in linguaggio naturale."""
    print_separator("TEST 2: Intent Parsing")
    
    # Intent di esempio in italiano
    test_intents = [
        "Crea un flusso da host_1 a host_2 con priorità alta",
        "Mostra lo stato di switch_0000000000000001",
        "Risolvi l'anomalia sulla porta 3 dello switch 1",
        "Aumenta la bandwidth del link tra switch 1 e switch 2",
    ]
    
    parser = IntentParser()
    parsed_intents = []
    
    for intent_text in test_intents:
        print(f"\nIntent: '{intent_text}'")
        
        # Crea l'intent object
        intent = IntentObject(
            id=f"intent_{len(parsed_intents) + 1}",
            raw_text=intent_text,
            timestamp=datetime.now(),
            user_id="test_user",
            entities=[],  # Lista vuota invece di dict
            intent_type="configuration",
            confidence=0.0,
            parameters={}
        )
        
        # Parsa l'intent
        parsed = parser.parse_intent(intent_text)
        parsed_intents.append(parsed)
        
        print(f"  Tipo: {parsed.intent_type}")
        print(f"  Confidence: {parsed.confidence:.2f}")
        print(f"  Entità estratte: {parsed.entities}")
        
    return parsed_intents


def test_context_analysis(network_state, parsed_intents):
    """Test 3: Analisi del contesto."""
    print_separator("TEST 3: Context Analysis")
    
    if not network_state or not parsed_intents:
        logger.error("Network state o intent non disponibili")
        return
    
    # Crea il ContextAnalyzer e aggiorna manualmente la cache
    analyzer = ContextAnalyzer()
    analyzer.state_cache.update_state(network_state)
    
    for intent in parsed_intents[:2]:  # Testa solo i primi 2 intent
        print(f"\nAnalisi intent: '{intent.raw_text}'")
        
        try:
            # Analizza il contesto
            contextualized = analyzer.analyze_context(intent)
            
            print(f"  Risorse rilevanti identificate: {len(contextualized.relevant_resources)}")
            if contextualized.relevant_resources:
                for resource in contextualized.relevant_resources[:3]:  # Mostra max 3
                    print(f"    - {resource}")
            
            print(f"  Conflitti potenziali: {len(contextualized.conflicts)}")
            if contextualized.conflicts:
                for conflict in contextualized.conflicts:
                    print(f"    - {conflict}")
            
            print(f"  Contesto arricchito: {bool(contextualized.network_context)}")
            
        except Exception as e:
            logger.error(f"Errore nell'analisi del contesto: {e}")


def test_anomaly_analysis(network_state):
    """Test 4: Analisi delle anomalie."""
    print_separator("TEST 4: Anomaly Analysis")
    
    if not network_state:
        logger.error("Network state non disponibile")
        return
    
    print(f"Anomalie totali nel network state: {len(network_state.anomalies)}")
    
    for i, anomaly in enumerate(network_state.anomalies, 1):
        print(f"\nAnomalia {i}:")
        print(f"  Tipo: {anomaly.type}")
        print(f"  Severità: {anomaly.severity} (0-1 scale)")
        print(f"  Descrizione: {anomaly.description}")
        print(f"  Componenti affetti: {', '.join(anomaly.affected_resources)}")
        print(f"  Confidence: {anomaly.metrics.get('confidence', 'N/A')}")
        
        # Suggerisci azioni correttive
        if anomaly.type == "high_utilization":
            print("  → Azione suggerita: Ridistribuire il traffico o aumentare la capacità")
        elif anomaly.type == "high_error_rate":
            print("  → Azione suggerita: Verificare la connessione fisica e i driver")
        elif anomaly.type == "isolated_switch":
            print("  → Azione suggerita: Verificare i link e la connettività dello switch")


def test_metrics_analysis(network_state):
    """Test 5: Analisi delle metriche."""
    print_separator("TEST 5: Metrics Analysis")
    
    if not network_state:
        logger.error("Network state non disponibile")
        return
    
    metrics = network_state.metrics
    
    # Analisi bandwidth
    print("Analisi Bandwidth:")
    utilization = metrics.bandwidth.utilization_percentage
    print(f"  Utilizzo: {utilization}%")
    if utilization > 80:
        print("  ⚠ ATTENZIONE: Utilizzo elevato della bandwidth!")
    elif utilization > 50:
        print("  ⚡ Utilizzo moderato")
    else:
        print("  ✓ Utilizzo normale")
    
    # Analisi latenza
    print("\nAnalisi Latenza:")
    print(f"  Media: {metrics.latency.average_latency} ms")
    print(f"  Min: {metrics.latency.min_latency} ms")
    print(f"  Max: {metrics.latency.max_latency} ms")
    print(f"  Jitter: {metrics.latency.jitter} ms")
    
    if metrics.latency.average_latency > 10:
        print("  ⚠ Latenza elevata rilevata")
    else:
        print("  ✓ Latenza nella norma")
    
    # Analisi utilizzo porte
    print("\nAnalisi Utilizzo Porte:")
    port_utils = metrics.utilization.port_utilization
    
    high_util_ports = [(port, util) for port, util in port_utils.items() if util > 80]
    if high_util_ports:
        print("  Porte con utilizzo elevato (>80%):")
        for port, util in high_util_ports:
            print(f"    - {port}: {util}%")
    else:
        print("  ✓ Nessuna porta con utilizzo critico")


def main():
    """Funzione principale."""
    print("\n" + "=" * 80)
    print("  TEST DEL MODULO LLM CON network_context_latest.json")
    print("  (Senza utilizzo di ChatGPT API)")
    print("=" * 80)
    
    try:
        # Test 1: Carica il network state
        network_state = test_load_network_state()
        
        if not network_state:
            logger.error("Impossibile procedere senza network state")
            return
        
        # Test 2: Parsing intent
        parsed_intents = test_intent_parsing()
        
        # Test 3: Analisi contesto
        test_context_analysis(network_state, parsed_intents)
        
        # Test 4: Analisi anomalie
        test_anomaly_analysis(network_state)
        
        # Test 5: Analisi metriche
        test_metrics_analysis(network_state)
        
        print_separator("TEST COMPLETATI")
        print("✓ Tutti i test sono stati eseguiti con successo!")
        print("\nNOTA: Questi test utilizzano solo la logica locale del modulo,")
        print("senza chiamare l'API di ChatGPT.")
        
    except Exception as e:
        logger.error(f"Errore durante l'esecuzione dei test: {e}", exc_info=True)
        print(f"\n✗ Errore: {e}")


if __name__ == "__main__":
    main()
