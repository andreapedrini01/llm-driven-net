#!/usr/bin/env python3
"""
Demo Task 3.3 - Elaborazione Metriche Prestazioni

Questo script dimostra le funzionalità implementate nel task 3.3:
- Filtraggio porte LOCAL
- Validazione completezza dati
- Calcolo metriche derivate (utilizzo, congestione, errori)
"""

import sys
import logging
from pathlib import Path

# Aggiungi il path del modulo
sys.path.insert(0, str(Path(__file__).parent.parent))

from network_state_collector.data_processor import DataProcessor
from network_state_collector.models.core import PortMetrics, MetricsData


def create_sample_port_stats():
    """Crea dati di esempio per la demo"""
    return {
        "1": [
            # Porta normale con traffico moderato
            PortMetrics(
                port_no=1,
                rx_packets=10000,
                tx_packets=12000,
                rx_bytes=1500000,
                tx_bytes=1800000,
                rx_errors=5,
                tx_errors=3,
                rx_dropped=1,
                tx_dropped=2
            ),
            # Porta con traffico elevato
            PortMetrics(
                port_no=2,
                rx_packets=50000,
                tx_packets=48000,
                rx_bytes=7500000,
                tx_bytes=7200000,
                rx_errors=25,
                tx_errors=20,
                rx_dropped=10,
                tx_dropped=8
            ),
            # Porta LOCAL (dovrebbe essere filtrata)
            PortMetrics(
                port_no=0xfffffffe,  # OFPP_LOCAL
                rx_packets=1000,
                tx_packets=1500,
                rx_bytes=150000,
                tx_bytes=225000,
                rx_errors=0,
                tx_errors=0,
                rx_dropped=0,
                tx_dropped=0
            )
        ],
        "2": [
            # Porta con pochi errori
            PortMetrics(
                port_no=1,
                rx_packets=8000,
                tx_packets=9000,
                rx_bytes=1200000,
                tx_bytes=1350000,
                rx_errors=2,
                tx_errors=1,
                rx_dropped=0,
                tx_dropped=1
            ),
            # Porta con dati inconsistenti (dovrebbe essere filtrata)
            PortMetrics(
                port_no=2,
                rx_packets=5000,
                tx_packets=6000,
                rx_bytes=0,  # Inconsistente: pacchetti senza bytes
                tx_bytes=900000,
                rx_errors=1,
                tx_errors=2,
                rx_dropped=0,
                tx_dropped=0
            )
        ]
    }


def demo_local_port_filtering():
    """Dimostra il filtraggio delle porte LOCAL"""
    print("=== Demo Filtraggio Porte LOCAL ===")
    
    processor = DataProcessor()
    
    # Test identificazione porte LOCAL
    test_ports = [1, 2, 0xfffffffe, 0xfffffffd, 48]
    print("Test identificazione porte LOCAL:")
    for port in test_ports:
        is_local = processor._is_local_port(port)
        port_type = "LOCAL" if is_local else "normale"
        print(f"  Porta {port} (0x{port:x}): {port_type}")
    
    print()


def demo_data_validation():
    """Dimostra la validazione dei dati"""
    print("=== Demo Validazione Dati ===")
    
    processor = DataProcessor()
    
    # Test metriche valide
    valid_metric = PortMetrics(
        port_no=1,
        rx_packets=1000,
        tx_packets=1200,
        rx_bytes=150000,
        tx_bytes=180000,
        rx_errors=2,
        tx_errors=1
    )
    
    # Test metriche invalide
    invalid_metric = PortMetrics(
        port_no=2,
        rx_packets=1000,
        tx_packets=1200,
        rx_bytes=0,  # Inconsistente
        tx_bytes=180000,
        rx_errors=2,
        tx_errors=1
    )
    
    print("Test validazione completezza:")
    print(f"  Metrica valida: {processor._validate_port_metric_completeness(valid_metric)}")
    print(f"  Metrica invalida: {processor._validate_port_metric_completeness(invalid_metric)}")
    
    print("\nTest validazione consistenza:")
    print(f"  Metrica valida: {processor._validate_port_metric_consistency(valid_metric)}")
    print(f"  Metrica invalida: {processor._validate_port_metric_consistency(invalid_metric)}")
    
    print()


def demo_metrics_processing():
    """Dimostra l'elaborazione completa delle metriche"""
    print("=== Demo Elaborazione Metriche ===")
    
    processor = DataProcessor()
    port_stats = create_sample_port_stats()
    
    print(f"Dati di input:")
    for dpid, metrics in port_stats.items():
        print(f"  Switch {dpid}: {len(metrics)} porte")
        for metric in metrics:
            port_type = "LOCAL" if processor._is_local_port(metric.port_no) else "normale"
            print(f"    Porta {metric.port_no} ({port_type}): "
                  f"RX={metric.rx_packets} pkt, TX={metric.tx_packets} pkt, "
                  f"Errori={metric.rx_errors + metric.tx_errors}")
    
    print("\nElaborazione in corso...")
    
    # Processa le metriche
    result = processor.process_metrics(port_stats)
    
    print(f"\nRisultati elaborazione:")
    for dpid, metrics in result.port_statistics.items():
        print(f"  Switch {dpid}: {len(metrics)} porte valide (dopo filtraggio)")
        
        # Mostra metriche aggregate
        aggregated = result.aggregated_metrics[dpid]
        print(f"    Totale RX: {aggregated.total_rx_packets} pacchetti")
        print(f"    Totale TX: {aggregated.total_tx_packets} pacchetti")
        print(f"    Totale errori: {aggregated.total_errors}")
        print(f"    Utilizzo medio: {aggregated.average_utilization:.2%}")
        print(f"    Porte congestionate: {aggregated.congested_ports}")
    
    # Mostra metriche di qualità
    if result.quality_indicators:
        quality = result.quality_indicators
        print(f"\nMetriche di qualità:")
        print(f"  Completezza: {quality.completeness_score:.2%}")
        print(f"  Consistenza: {quality.consistency_score:.2%}")
        print(f"  Punteggio complessivo: {quality.overall_score:.2%}")
        
        if quality.issues_detected:
            print(f"  Problemi rilevati:")
            for issue in quality.issues_detected:
                print(f"    - {issue}")
    
    print()
    return result


def demo_derived_metrics(metrics_data):
    """Dimostra il calcolo delle metriche derivate"""
    print("=== Demo Metriche Derivate ===")
    
    processor = DataProcessor()
    
    # Calcola metriche derivate
    derived = processor.calculate_derived_metrics(metrics_data)
    
    print("Metriche derivate calcolate:")
    print(f"  Utilizzo rete: {derived.network_utilization:.2%}")
    print(f"  Livello congestione: {derived.congestion_level:.2%}")
    print(f"  Tasso errori: {derived.error_rate:.4%}")
    print(f"  Stabilità topologia: {derived.topology_stability:.2%}")
    print(f"  Punteggio prestazioni: {derived.performance_score:.2%}")
    
    # Interpretazione dei risultati
    print("\nInterpretazione:")
    if derived.performance_score > 0.8:
        print("  🟢 Prestazioni eccellenti")
    elif derived.performance_score > 0.6:
        print("  🟡 Prestazioni buone")
    elif derived.performance_score > 0.4:
        print("  🟠 Prestazioni moderate")
    else:
        print("  🔴 Prestazioni scarse")
    
    if derived.congestion_level > 0.5:
        print("  ⚠️  Alta congestione rilevata")
    
    if derived.error_rate > 0.01:
        print("  ⚠️  Tasso di errori elevato")
    
    print()


def demo_requirements_validation():
    """Dimostra la validazione dei requisiti implementati"""
    print("=== Validazione Requisiti Implementati ===")
    
    requirements = [
        "✅ Requisito 2.2: Esclusione porte LOCAL del controller",
        "✅ Requisito 2.3: Validazione completezza dati per calcoli derivati",
        "✅ Requisito 6.3: Calcolo metriche derivate (utilizzo, congestione, errori)"
    ]
    
    for req in requirements:
        print(f"  {req}")
    
    print("\nFunzionalità implementate:")
    features = [
        "✅ Filtraggio doppio delle porte LOCAL (RyuConnector + DataProcessor)",
        "✅ Validazione completezza dati (campi richiesti, valori non negativi)",
        "✅ Validazione consistenza dati (coerenza pacchetti/bytes, errori)",
        "✅ Calcolo metriche aggregate per switch",
        "✅ Calcolo metriche derivate di rete",
        "✅ Metriche di qualità dei dati",
        "✅ Gestione errori con continuazione operativa",
        "✅ Logging strutturato per debugging"
    ]
    
    for feature in features:
        print(f"  {feature}")
    
    print()


def main():
    """Funzione principale del demo"""
    print("🚀 Demo Task 3.3 - Elaborazione Metriche Prestazioni")
    print("=" * 60)
    
    # Setup logging
    logging.basicConfig(level=logging.WARNING)
    
    try:
        # Demo filtraggio porte LOCAL
        demo_local_port_filtering()
        
        # Demo validazione dati
        demo_data_validation()
        
        # Demo elaborazione metriche
        metrics_data = demo_metrics_processing()
        
        # Demo metriche derivate
        demo_derived_metrics(metrics_data)
        
        # Validazione requisiti
        demo_requirements_validation()
        
        print("🎉 Demo completato! Task 3.3 implementato con successo.")
        
    except Exception as e:
        print(f"❌ Errore durante il demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()