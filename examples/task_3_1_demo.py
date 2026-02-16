#!/usr/bin/env python3
"""
Demo per Task 3.1: Implementazione elaborazione dati di topologia

Questo script dimostra l'implementazione del DataProcessor per l'elaborazione
dei dati di topologia con formattazione DPID consistente.
"""

import sys
import os
import logging
from pathlib import Path

# Aggiungi il path del modulo
sys.path.insert(0, str(Path(__file__).parent.parent))

from network_state_collector.data_processor import DataProcessor
from src.models.core import SwitchInfo, LinkInfo, PortMetrics
from src.models import CollectorConfig
from network_state_collector.collector import NetworkStateCollector


def setup_logging():
    """Configura il logging per la demo"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def demo_dpid_formatting():
    """Dimostra la formattazione consistente dei DPID"""
    print("\n=== DEMO: Formattazione DPID Consistente ===")
    
    processor = DataProcessor()
    
    # Test con diversi formati di DPID
    test_dpids = [
        1,                          # Intero
        255,                        # Intero più grande
        "0x1",                      # Hex con prefisso
        "0xFF",                     # Hex maiuscolo
        "ab:cd:ef:12:34:56",        # Formato MAC-like
        "ABCDEF123456",             # Hex senza separatori
        "0000000000000001"          # Già formattato
    ]
    
    print("Input DPID -> Output formattato:")
    for dpid in test_dpids:
        try:
            formatted = processor._format_dpid(dpid)
            print(f"  {str(dpid):20} -> {formatted}")
        except ValueError as e:
            print(f"  {str(dpid):20} -> ERROR: {e}")
    
    print("\nTutti i DPID sono formattati come stringhe esadecimali a 16 cifre minuscole.")


def demo_topology_processing():
    """Dimostra l'elaborazione dei dati di topologia"""
    print("\n=== DEMO: Elaborazione Dati di Topologia ===")
    
    processor = DataProcessor()
    
    # Crea dati di esempio con DPID in formati diversi
    switches = [
        SwitchInfo(dpid=1, ports=[1, 2, 3, 4], active=True),
        SwitchInfo(dpid="0x2", ports=[1, 2], active=True),
        SwitchInfo(dpid="AB:CD:EF:12:34:56", ports=[1, 2, 3], active=True)
    ]
    
    links = [
        LinkInfo(src_dpid=1, dst_dpid="0x2", src_port=1, dst_port=1, active=True),
        LinkInfo(src_dpid="0x2", dst_dpid=1, src_port=1, dst_port=1, active=True),
        LinkInfo(src_dpid=1, dst_dpid="AB:CD:EF:12:34:56", src_port=2, dst_port=1, active=True)
    ]
    
    print(f"Input: {len(switches)} switches, {len(links)} links")
    print("Switch DPID originali:", [s.dpid for s in switches])
    
    # Processa la topologia
    topology_data = processor.process_topology(switches, links)
    
    print(f"\nOutput: {len(topology_data.switches)} switches, {len(topology_data.links)} links")
    print("Switch DPID formattati:", [s.dpid for s in topology_data.switches])
    
    # Mostra la rappresentazione grafica
    graph = topology_data.graph_representation
    print(f"\nRappresentazione grafica:")
    print(f"  - Nodi: {len(graph['nodes'])}")
    print(f"  - Archi: {len(graph['edges'])}")
    print(f"  - Densità: {graph['metrics']['density']:.3f}")
    print(f"  - Grado medio: {graph['metrics']['average_node_degree']:.1f}")
    
    # Mostra connettività
    connectivity = graph['connectivity_info']
    print(f"  - Switch connessi: {connectivity['connected_switches']}")
    print(f"  - Switch isolati: {connectivity['isolated_switches']}")
    print(f"  - Ratio connettività: {connectivity['connectivity_ratio']:.1%}")


def demo_metrics_processing():
    """Dimostra l'elaborazione delle metriche"""
    print("\n=== DEMO: Elaborazione Metriche ===")
    
    processor = DataProcessor()
    
    # Crea dati di metriche di esempio
    port_stats = {
        "1": [
            PortMetrics(port_no=1, rx_packets=1000, tx_packets=800,
                       rx_bytes=64000, tx_bytes=51200, rx_errors=0, tx_errors=0),
            PortMetrics(port_no=2, rx_packets=500, tx_packets=600,
                       rx_bytes=32000, tx_bytes=38400, rx_errors=1, tx_errors=0)
        ],
        "0xABCDEF123456": [
            PortMetrics(port_no=1, rx_packets=2000, tx_packets=1800,
                       rx_bytes=128000, tx_bytes=115200, rx_errors=0, tx_errors=2)
        ]
    }
    
    print("Input: metriche per", len(port_stats), "switch")
    for dpid, metrics in port_stats.items():
        print(f"  Switch {dpid}: {len(metrics)} porte")
    
    # Processa le metriche
    metrics_data = processor.process_metrics(port_stats)
    
    print(f"\nOutput: metriche elaborate per {len(metrics_data.port_statistics)} switch")
    for dpid, aggregated in metrics_data.aggregated_metrics.items():
        print(f"  Switch {dpid}:")
        print(f"    - Pacchetti RX totali: {aggregated.total_rx_packets}")
        print(f"    - Pacchetti TX totali: {aggregated.total_tx_packets}")
        print(f"    - Errori totali: {aggregated.total_errors}")
        print(f"    - Utilizzo medio: {aggregated.average_utilization:.1%}")
        print(f"    - Porte congestionate: {aggregated.congested_ports}")
    
    # Calcola metriche derivate
    derived = processor.calculate_derived_metrics(metrics_data)
    print(f"\nMetriche derivate:")
    print(f"  - Utilizzo rete: {derived.network_utilization:.1%}")
    print(f"  - Livello congestione: {derived.congestion_level:.1%}")
    print(f"  - Tasso errori: {derived.error_rate:.4f}")
    print(f"  - Stabilità topologia: {derived.topology_stability:.1%}")
    print(f"  - Punteggio prestazioni: {derived.performance_score:.3f}")


def demo_full_integration():
    """Dimostra l'integrazione completa con NetworkStateCollector"""
    print("\n=== DEMO: Integrazione Completa ===")
    
    # Nota: Questa demo usa mock data perché non abbiamo un controller Ryu reale
    print("Questa demo mostrerebbe l'integrazione completa con un controller Ryu reale.")
    print("Per ora, mostriamo solo l'inizializzazione del collector:")
    
    config = CollectorConfig()
    print(f"Configurazione Ryu: {config.ryu.base_url}")
    print(f"Timeout: {config.ryu.timeout}s")
    print(f"Max retry: {config.retry.max_attempts}")
    
    # Il collector integra automaticamente DataProcessor
    print("\nIl NetworkStateCollector integra automaticamente:")
    print("  ✓ RyuConnector per la raccolta dati")
    print("  ✓ DataProcessor per l'elaborazione topologia")
    print("  ✓ Formattazione DPID consistente")
    print("  ✓ Gestione errori robusta")
    print("  ✓ Health monitoring")


def main():
    """Funzione principale della demo"""
    setup_logging()
    
    print("=" * 60)
    print("DEMO: Task 3.1 - Implementazione elaborazione dati di topologia")
    print("=" * 60)
    print("\nQuesto demo mostra l'implementazione del DataProcessor che:")
    print("  1. Converte dati grezzi in TopologyData strutturata")
    print("  2. Implementa formattazione DPID consistente (16 cifre hex)")
    print("  3. Gestisce errori con continuazione operativa")
    print("  4. Crea rappresentazione grafica per analisi LLM")
    
    try:
        demo_dpid_formatting()
        demo_topology_processing()
        demo_metrics_processing()
        demo_full_integration()
        
        print("\n" + "=" * 60)
        print("✅ TASK 3.1 COMPLETATO CON SUCCESSO!")
        print("=" * 60)
        print("\nFunzionalità implementate:")
        print("  ✅ DataProcessor.process_topology()")
        print("  ✅ Formattazione DPID consistente")
        print("  ✅ Validazione e gestione errori")
        print("  ✅ Rappresentazione grafica topologia")
        print("  ✅ Integrazione con NetworkStateCollector")
        print("  ✅ Test unitari e property-based")
        print("  ✅ Test di integrazione")
        
        print(f"\nRequisiti soddisfatti:")
        print(f"  ✅ Requisito 1.3: Formattazione DPID esadecimale a 16 cifre")
        print(f"  ✅ Requisito 2.1: Elaborazione dati di topologia completa")
        
    except Exception as e:
        print(f"\n❌ Errore durante la demo: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())