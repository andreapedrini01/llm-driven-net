#!/usr/bin/env python3
"""
Esempio di utilizzo base del Network State Collector

Questo script dimostra come utilizzare il collector programmaticamente
per raccogliere dati di rete e integrarli con modelli LLM.
"""

import time
from pathlib import Path
from network_state_collector import NetworkStateCollector, CollectorConfig
from network_state_collector.models.core import (
    NetworkSnapshot, TopologyData, MetricsData,
    SwitchInfo, LinkInfo, PortMetrics
)


def create_sample_data():
    """Crea dati di esempio per dimostrare il funzionamento"""
    
    # Crea alcuni switch di esempio
    switch1 = SwitchInfo(dpid="0000000000000001", ports=[1, 2, 3, 4])
    switch2 = SwitchInfo(dpid="0000000000000002", ports=[1, 2, 3, 4])
    
    # Crea link tra gli switch
    link1 = LinkInfo(
        src_dpid="0000000000000001",
        dst_dpid="0000000000000002",
        src_port=1,
        dst_port=1
    )
    
    # Crea topologia
    topology = TopologyData(
        switches=[switch1, switch2],
        links=[link1],
        graph_representation={"nodes": 2, "edges": 1}
    )
    
    # Crea metriche di esempio
    port_metrics_1 = [
        PortMetrics(
            port_no=1,
            rx_packets=1000,
            tx_packets=800,
            rx_bytes=64000,
            tx_bytes=51200,
            rx_errors=0,
            tx_errors=0
        ),
        PortMetrics(
            port_no=2,
            rx_packets=500,
            tx_packets=600,
            rx_bytes=32000,
            tx_bytes=38400,
            rx_errors=1,
            tx_errors=0
        )
    ]
    
    port_metrics_2 = [
        PortMetrics(
            port_no=1,
            rx_packets=800,
            tx_packets=1000,
            rx_bytes=51200,
            tx_bytes=64000,
            rx_errors=0,
            tx_errors=0
        )
    ]
    
    metrics = MetricsData(
        port_statistics={
            "0000000000000001": port_metrics_1,
            "0000000000000002": port_metrics_2
        }
    )
    
    # Crea snapshot completo
    snapshot = NetworkSnapshot(
        timestamp=time.time(),
        topology=topology,
        metrics=metrics
    )
    
    return snapshot


def demonstrate_serialization():
    """Dimostra la serializzazione JSON"""
    print("=== Dimostrazione Serializzazione ===")
    
    snapshot = create_sample_data()
    
    # Serializza in JSON
    json_str = snapshot.to_json()
    print("Snapshot serializzato in JSON:")
    print(json_str[:200] + "..." if len(json_str) > 200 else json_str)
    
    # Deserializza da JSON
    parsed_snapshot = NetworkSnapshot.from_json(json_str)
    print(f"\nSnapshot deserializzato:")
    print(f"- Timestamp: {parsed_snapshot.get_timestamp_iso()}")
    print(f"- Switch: {len(parsed_snapshot.topology.switches)}")
    print(f"- Link: {len(parsed_snapshot.topology.links)}")
    print(f"- Porte totali: {sum(len(ports) for ports in parsed_snapshot.metrics.port_statistics.values())}")


def demonstrate_metrics_calculation():
    """Dimostra il calcolo delle metriche"""
    print("\n=== Dimostrazione Calcolo Metriche ===")
    
    snapshot = create_sample_data()
    
    for dpid, ports in snapshot.metrics.port_statistics.items():
        print(f"\nSwitch {dpid}:")
        for port in ports:
            utilization = port.calculate_utilization()
            error_rate = port.calculate_error_rate()
            is_congested = port.is_congested()
            
            print(f"  Porta {port.port_no}:")
            print(f"    - Utilizzo: {utilization:.2%}")
            print(f"    - Tasso errori: {error_rate:.2%}")
            print(f"    - Congestionata: {'Sì' if is_congested else 'No'}")


def demonstrate_config_loading():
    """Dimostra il caricamento della configurazione"""
    print("\n=== Dimostrazione Configurazione ===")
    
    # Carica configurazione da file
    config_path = Path("config/development.yaml")
    if config_path.exists():
        config = CollectorConfig.load_from_file(str(config_path))
        print(f"Configurazione caricata da: {config_path}")
        print(f"- Ambiente: {config.environment}")
        print(f"- Host Ryu: {config.ryu.host}:{config.ryu.port}")
        print(f"- Intervallo raccolta: {config.collection.interval}s")
        print(f"- Directory output: {config.output.directory}")
    else:
        print("File di configurazione non trovato, uso configurazione default")
        config = CollectorConfig()
    
    return config


def demonstrate_collector_usage():
    """Dimostra l'utilizzo del collector"""
    print("\n=== Dimostrazione Collector ===")
    
    config = CollectorConfig()
    collector = NetworkStateCollector(config)
    
    print(f"Collector inizializzato")
    print(f"- Uptime: {collector.uptime:.2f}s")
    print(f"- In esecuzione: {collector.is_running}")
    
    # Verifica stato di salute
    health = collector.get_health_status()
    print(f"- Stato salute: {health.overall_status.value}")


def save_example_output():
    """Salva un esempio di output per riferimento"""
    print("\n=== Salvataggio Esempio ===")
    
    snapshot = create_sample_data()
    
    # Crea directory di output
    output_dir = Path("examples/output")
    output_dir.mkdir(exist_ok=True)
    
    # Salva snapshot
    output_file = output_dir / "example_snapshot.json"
    output_file.write_text(snapshot.to_json(), encoding='utf-8')
    
    print(f"Esempio salvato in: {output_file}")
    print(f"Dimensione file: {output_file.stat().st_size} bytes")


def main():
    """Funzione principale dell'esempio"""
    print("Network State Collector - Esempio di Utilizzo")
    print("=" * 50)
    
    try:
        demonstrate_serialization()
        demonstrate_metrics_calculation()
        config = demonstrate_config_loading()
        demonstrate_collector_usage()
        save_example_output()
        
        print("\n" + "=" * 50)
        print("Esempio completato con successo!")
        print("\nPer utilizzare il collector con un controller Ryu reale:")
        print("1. Configura l'endpoint Ryu in config/development.yaml")
        print("2. Esegui: python -m network_state_collector.main collect")
        
    except Exception as e:
        print(f"\nErrore durante l'esecuzione dell'esempio: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())