#!/usr/bin/env python3
"""
Demo per DataValidator - Validazione rigorosa e gestione qualità dati

Dimostra l'utilizzo del DataValidator per validare snapshot di rete,
rilevare anomalie e generare metriche di qualità.
"""

import time
import json
from network_state_collector.data_validator import DataValidator, ValidationSeverity
from src.models.core import (
    NetworkSnapshot, TopologyData, MetricsData, SwitchInfo, LinkInfo, 
    PortMetrics, AggregatedMetrics, DerivedMetrics
)


def create_valid_snapshot():
    """Crea uno snapshot di rete valido per il test"""
    switches = [
        SwitchInfo(dpid="0000000000000001", ports=[1, 2, 3], active=True),
        SwitchInfo(dpid="0000000000000002", ports=[1, 2, 3], active=True),
        SwitchInfo(dpid="0000000000000003", ports=[1, 2], active=True)
    ]
    
    links = [
        LinkInfo(src_dpid="0000000000000001", dst_dpid="0000000000000002", 
                src_port=1, dst_port=1, active=True),
        LinkInfo(src_dpid="0000000000000002", dst_dpid="0000000000000003", 
                src_port=2, dst_port=1, active=True)
    ]
    
    topology = TopologyData(switches=switches, links=links)
    
    port_stats = {
        "0000000000000001": [
            PortMetrics(port_no=1, rx_packets=1000, tx_packets=1200, 
                      rx_bytes=100000, tx_bytes=120000, rx_errors=5, tx_errors=3),
            PortMetrics(port_no=2, rx_packets=800, tx_packets=900, 
                      rx_bytes=80000, tx_bytes=90000, rx_errors=2, tx_errors=1),
            PortMetrics(port_no=3, rx_packets=500, tx_packets=600, 
                      rx_bytes=50000, tx_bytes=60000, rx_errors=1, tx_errors=0)
        ],
        "0000000000000002": [
            PortMetrics(port_no=1, rx_packets=1200, tx_packets=1000, 
                      rx_bytes=120000, tx_bytes=100000, rx_errors=3, tx_errors=5),
            PortMetrics(port_no=2, rx_packets=900, tx_packets=800, 
                      rx_bytes=90000, tx_bytes=80000, rx_errors=1, tx_errors=2)
        ],
        "0000000000000003": [
            PortMetrics(port_no=1, rx_packets=600, tx_packets=500, 
                      rx_bytes=60000, tx_bytes=50000, rx_errors=0, tx_errors=1)
        ]
    }
    
    aggregated = {
        "0000000000000001": AggregatedMetrics(
            dpid="0000000000000001", total_rx_packets=2300, total_tx_packets=2700,
            total_rx_bytes=230000, total_tx_bytes=270000, total_errors=12,
            average_utilization=0.35, congested_ports=0
        ),
        "0000000000000002": AggregatedMetrics(
            dpid="0000000000000002", total_rx_packets=2100, total_tx_packets=1800,
            total_rx_bytes=210000, total_tx_bytes=180000, total_errors=11,
            average_utilization=0.28, congested_ports=0
        ),
        "0000000000000003": AggregatedMetrics(
            dpid="0000000000000003", total_rx_packets=600, total_tx_packets=500,
            total_rx_bytes=60000, total_tx_bytes=50000, total_errors=1,
            average_utilization=0.15, congested_ports=0
        )
    }
    
    metrics = MetricsData(port_statistics=port_stats, aggregated_metrics=aggregated)
    
    derived_metrics = DerivedMetrics(
        network_utilization=0.26,
        congestion_level=0.1,
        error_rate=0.005,
        topology_stability=0.95,
        performance_score=0.85
    )
    
    return NetworkSnapshot(
        timestamp=time.time(),
        topology=topology,
        metrics=metrics,
        derived_metrics=derived_metrics
    )


def create_problematic_snapshot():
    """Crea uno snapshot con vari problemi per testare il rilevamento anomalie"""
    switches = [
        SwitchInfo(dpid="0000000000000001", ports=[1, 2], active=True),
        SwitchInfo(dpid="0000000000000002", ports=[], active=True),  # Nessuna porta
    ]
    
    # Link che punta a switch inesistente
    links = [
        LinkInfo(src_dpid="0000000000000001", dst_dpid="0000000000000999", 
                src_port=1, dst_port=1, active=True)
    ]
    
    topology = TopologyData(switches=switches, links=links)
    
    # Metriche con problemi
    port_stats = {
        "0000000000000001": [
            PortMetrics(port_no=1, rx_packets=100, tx_packets=200, 
                      rx_bytes=0, tx_bytes=20000, rx_errors=150, tx_errors=50),  # Problemi: no RX bytes, troppi errori
            PortMetrics(port_no=2, rx_packets=0, tx_packets=0, 
                      rx_bytes=0, tx_bytes=0, rx_errors=0, tx_errors=0)
        ],
        "0000000000000999": [  # Switch inesistente
            PortMetrics(port_no=1, rx_packets=50, tx_packets=100, 
                      rx_bytes=5000, tx_bytes=10000, rx_errors=0, tx_errors=1)
        ]
    }
    
    # Metriche aggregate inconsistenti
    aggregated = {
        "0000000000000001": AggregatedMetrics(
            dpid="0000000000000001", total_rx_packets=999,  # Dovrebbe essere 100
            total_tx_packets=200, total_rx_bytes=0, total_tx_bytes=20000,
            total_errors=200, average_utilization=1.5, congested_ports=2  # Utilizzo > 100%
        )
    }
    
    metrics = MetricsData(port_statistics=port_stats, aggregated_metrics=aggregated)
    
    # Prestazioni degradate
    derived_metrics = DerivedMetrics(
        network_utilization=0.95,
        congestion_level=0.8,  # Alta congestione
        error_rate=0.6,        # Alto tasso di errore
        topology_stability=0.3,
        performance_score=0.2  # Prestazioni basse
    )
    
    return NetworkSnapshot(
        timestamp=time.time() - 3600,  # Timestamp vecchio di 1 ora
        topology=topology,
        metrics=metrics,
        derived_metrics=derived_metrics
    )


def demo_basic_validation():
    """Dimostra validazione base di uno snapshot valido"""
    print("=== Demo Validazione Base ===")
    
    validator = DataValidator(enable_auto_correction=True)
    snapshot = create_valid_snapshot()
    
    print(f"Validando snapshot con timestamp: {snapshot.timestamp}")
    print(f"Switch: {len(snapshot.topology.switches)}, Link: {len(snapshot.topology.links)}")
    
    result = validator.validate_network_snapshot(snapshot)
    
    print(f"\nRisultato validazione:")
    print(f"  Valido: {result.is_valid}")
    print(f"  Punteggio qualità: {result.quality_score:.3f}")
    print(f"  Issue rilevate: {len(result.issues)}")
    print(f"  Durata validazione: {result.validation_duration_ms:.1f}ms")
    
    if result.issues:
        print(f"\nIssue rilevate:")
        for issue in result.issues:
            print(f"  - {issue.severity.value.upper()}: {issue.message}")
    
    # Genera metriche di qualità dettagliate
    quality_metrics = validator.generate_quality_metrics(result)
    print(f"\nMetriche di qualità:")
    print(f"  Completezza: {quality_metrics.completeness_score:.3f}")
    print(f"  Consistenza: {quality_metrics.consistency_score:.3f}")
    print(f"  Tempestività: {quality_metrics.timeliness_score:.3f}")
    print(f"  Accuratezza: {quality_metrics.accuracy_score:.3f}")
    print(f"  Punteggio complessivo: {quality_metrics.overall_score:.3f}")


def demo_anomaly_detection():
    """Dimostra rilevamento anomalie su snapshot problematico"""
    print("\n=== Demo Rilevamento Anomalie ===")
    
    validator = DataValidator(enable_auto_correction=True)
    
    # Prima valida uno snapshot valido per avere dati storici
    valid_snapshot = create_valid_snapshot()
    validator.validate_network_snapshot(valid_snapshot)
    
    # Poi valida uno snapshot problematico
    problematic_snapshot = create_problematic_snapshot()
    
    print(f"Validando snapshot problematico...")
    
    result = validator.validate_network_snapshot(problematic_snapshot)
    
    print(f"\nRisultato validazione:")
    print(f"  Valido: {result.is_valid}")
    print(f"  Punteggio qualità: {result.quality_score:.3f}")
    print(f"  Issue rilevate: {len(result.issues)}")
    
    # Raggruppa issue per severità
    critical_issues = result.get_issues_by_severity(ValidationSeverity.CRITICAL)
    error_issues = result.get_issues_by_severity(ValidationSeverity.ERROR)
    warning_issues = result.get_issues_by_severity(ValidationSeverity.WARNING)
    info_issues = result.get_issues_by_severity(ValidationSeverity.INFO)
    
    if critical_issues:
        print(f"\nIssue CRITICHE ({len(critical_issues)}):")
        for issue in critical_issues:
            print(f"  - {issue.component}: {issue.message}")
    
    if error_issues:
        print(f"\nERRORI ({len(error_issues)}):")
        for issue in error_issues:
            print(f"  - {issue.component}: {issue.message}")
    
    if warning_issues:
        print(f"\nAVVISI ({len(warning_issues)}):")
        for issue in warning_issues:
            print(f"  - {issue.component}: {issue.message}")
    
    if info_issues:
        print(f"\nINFORMAZIONI ({len(info_issues)}):")
        for issue in info_issues:
            print(f"  - {issue.component}: {issue.message}")
    
    # Mostra correzioni automatiche se applicate
    if result.corrected_data:
        print(f"\nCorrezioni automatiche applicate!")
    
    # Statistiche del validatore
    stats = validator.get_validation_stats()
    print(f"\nStatistiche validatore:")
    print(f"  Validazioni totali: {stats['total_validations']}")
    print(f"  Validazioni riuscite: {stats['successful_validations']}")
    print(f"  Validazioni fallite: {stats['failed_validations']}")
    print(f"  Anomalie rilevate: {stats['anomalies_detected']}")
    print(f"  Correzioni applicate: {stats['auto_corrections_applied']}")


def demo_custom_thresholds():
    """Dimostra utilizzo di soglie personalizzate per anomalie"""
    print("\n=== Demo Soglie Personalizzate ===")
    
    # Soglie più restrittive
    custom_thresholds = {
        'max_utilization': 0.5,      # 50% invece di 100%
        'max_error_rate': 0.01,      # 1% invece di 50%
        'max_packet_loss': 0.05      # 5% invece di 30%
    }
    
    validator = DataValidator(
        enable_auto_correction=True,
        anomaly_thresholds=custom_thresholds
    )
    
    print(f"Soglie personalizzate:")
    for key, value in custom_thresholds.items():
        print(f"  {key}: {value}")
    
    # Crea snapshot che supera le nuove soglie
    switches = [SwitchInfo(dpid="0000000000000001", ports=[1], active=True)]
    topology = TopologyData(switches=switches, links=[])
    
    port_stats = {
        "0000000000000001": [
            PortMetrics(port_no=1, rx_packets=1000, tx_packets=1000, 
                      rx_bytes=100000, tx_bytes=100000, rx_errors=50, tx_errors=50)  # 5% errori
        ]
    }
    
    aggregated = {
        "0000000000000001": AggregatedMetrics(
            dpid="0000000000000001", total_rx_packets=1000, total_tx_packets=1000,
            total_rx_bytes=100000, total_tx_bytes=100000, total_errors=100,
            average_utilization=0.7, congested_ports=0  # 70% utilizzo
        )
    }
    
    metrics = MetricsData(port_statistics=port_stats, aggregated_metrics=aggregated)
    
    snapshot = NetworkSnapshot(
        timestamp=time.time(),
        topology=topology,
        metrics=metrics
    )
    
    result = validator.validate_network_snapshot(snapshot)
    
    print(f"\nRisultato con soglie personalizzate:")
    print(f"  Issue rilevate: {len(result.issues)}")
    
    performance_issues = [i for i in result.issues 
                         if i.anomaly_type.value == "performance_degradation"]
    
    if performance_issues:
        print(f"\nAnomalie prestazioni rilevate:")
        for issue in performance_issues:
            print(f"  - {issue.message}")
            if 'utilization' in issue.details:
                print(f"    Utilizzo: {issue.details['utilization']:.1%}")
            if 'error_rate' in issue.details:
                print(f"    Tasso errore: {issue.details['error_rate']:.1%}")


def demo_json_serialization():
    """Dimostra serializzazione JSON dei risultati di validazione"""
    print("\n=== Demo Serializzazione JSON ===")
    
    validator = DataValidator()
    snapshot = create_valid_snapshot()
    result = validator.validate_network_snapshot(snapshot)
    
    # Serializza le issue in JSON
    issues_json = []
    for issue in result.issues:
        issues_json.append(issue.to_dict())
    
    validation_report = {
        "timestamp": time.time(),
        "snapshot_timestamp": snapshot.timestamp,
        "validation_result": {
            "is_valid": result.is_valid,
            "quality_score": result.quality_score,
            "validation_duration_ms": result.validation_duration_ms,
            "issues_count": len(result.issues)
        },
        "issues": issues_json,
        "validator_stats": validator.get_validation_stats()
    }
    
    print("Report di validazione JSON:")
    print(json.dumps(validation_report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    print("DataValidator Demo - Validazione rigorosa e gestione qualità dati")
    print("=" * 70)
    
    try:
        demo_basic_validation()
        demo_anomaly_detection()
        demo_custom_thresholds()
        demo_json_serialization()
        
        print("\n" + "=" * 70)
        print("Demo completato con successo!")
        
    except Exception as e:
        print(f"\nErrore durante il demo: {e}")
        import traceback
        traceback.print_exc()