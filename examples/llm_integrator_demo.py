#!/usr/bin/env python3
"""
Demo per LLMIntegrator

Dimostra l'utilizzo dell'LLMIntegrator per convertire dati di rete
in formato ottimizzato per l'integrazione con modelli LLM.
"""

import time
import json
from pathlib import Path

from network_state_collector.llm_integrator import LLMIntegrator
from network_state_collector.models.core import (
    NetworkSnapshot, TopologyData, MetricsData, SwitchInfo, LinkInfo, PortMetrics
)
from network_state_collector.models.health import QualityMetrics


def create_sample_network_data():
    """Crea dati di rete di esempio per il demo"""
    
    # Crea una topologia di esempio con 4 switch
    switches = [
        SwitchInfo(dpid=f"000000000000000{i}", ports=[1, 2, 3, 4])
        for i in range(1, 5)
    ]
    
    # Crea collegamenti in topologia ad anello
    links = [
        LinkInfo("0000000000000001", "0000000000000002", 1, 1),
        LinkInfo("0000000000000002", "0000000000000003", 2, 1),
        LinkInfo("0000000000000003", "0000000000000004", 2, 1),
        LinkInfo("0000000000000004", "0000000000000001", 2, 2)
    ]
    
    # Crea metriche delle porte con diversi livelli di utilizzo
    port_statistics = {}
    
    for i, switch in enumerate(switches):
        port_metrics = []
        for port_no in range(1, 4):  # 3 porte per switch
            # Varia l'utilizzo e gli errori per creare scenari interessanti
            base_traffic = 1000000 * (i + 1) * port_no
            error_factor = 1 if i < 2 else 5  # Switch 3 e 4 hanno più errori
            
            # Switch 4 ha alta utilizzazione per dimostrare anomalie
            if i == 3:  # Switch 4 (indice 3)
                base_traffic *= 10  # 10x traffico per alta utilizzazione
            
            port_metrics.append(PortMetrics(
                port_no=port_no,
                rx_packets=base_traffic // 1000,
                tx_packets=int(base_traffic // 1000 * 0.9),
                rx_bytes=base_traffic,
                tx_bytes=int(base_traffic * 0.9),
                rx_errors=error_factor * port_no,
                tx_errors=error_factor * port_no // 2
            ))
        
        port_statistics[switch.dpid] = port_metrics
    
    # Crea snapshot completo
    topology = TopologyData(
        switches=switches,
        links=links,
        graph_representation={}
    )
    
    metrics = MetricsData(
        port_statistics=port_statistics,
        aggregated_metrics={},
        quality_indicators=QualityMetrics(
            completeness_score=0.95,
            consistency_score=0.98,
            timeliness_score=0.92,
            accuracy_score=0.96,
            overall_score=0.95
        )
    )
    
    return NetworkSnapshot(
        timestamp=time.time(),
        topology=topology,
        metrics=metrics,
        derived_metrics={},
        metadata={
            "collection_source": "demo",
            "controller_version": "1.0.0"
        }
    )


def main():
    """Funzione principale del demo"""
    print("🤖 Network State Collector - LLM Integration Demo")
    print("=" * 55)
    
    # Crea dati di rete di esempio
    print("\n1. Creating sample network data...")
    snapshot = create_sample_network_data()
    
    print(f"   ✅ Created network snapshot with:")
    print(f"      - {len(snapshot.topology.switches)} switches")
    print(f"      - {len(snapshot.topology.links)} links")
    print(f"      - {sum(len(ports) for ports in snapshot.metrics.port_statistics.values())} ports")
    
    # Inizializza LLMIntegrator con rilevamento anomalie
    print("\n2. Initializing LLM Integrator...")
    integrator = LLMIntegrator(enable_anomaly_detection=True)
    
    # Personalizza soglie per il demo
    integrator.anomaly_thresholds.update({
        'high_utilization': 0.7,    # 70%
        'high_error_rate': 0.005,   # 0.5%
        'congestion_threshold': 0.8  # 80%
    })
    
    print("   ✅ LLM Integrator initialized with custom thresholds")
    
    # Converti in formato LLM
    print("\n3. Converting to LLM format...")
    llm_data = integrator.format_for_llm(snapshot)
    
    print("   ✅ Conversion completed!")
    print(f"      - Network context: {len(llm_data.network_context)} sections")
    print(f"      - Performance vectors: {len(llm_data.performance_vectors)} vectors")
    print(f"      - Anomalies detected: {len(llm_data.anomaly_indicators)}")
    
    # Mostra dettagli del contesto di rete
    print("\n4. Network Context Details:")
    context = llm_data.network_context
    topology_info = context['topology']
    performance_info = context['performance']
    
    print(f"   📊 Topology:")
    print(f"      - Nodes: {topology_info['node_count']}")
    print(f"      - Edges: {topology_info['edge_count']}")
    print(f"      - Density: {llm_data.topology_embedding['density']:.3f}")
    print(f"      - Average degree: {llm_data.topology_embedding['average_degree']:.1f}")
    
    print(f"   📈 Performance:")
    agg_metrics = performance_info['aggregated_metrics']
    print(f"      - Active ports: {agg_metrics['active_ports']}")
    print(f"      - Average utilization: {agg_metrics['average_utilization']:.1f}%")
    print(f"      - Total errors: {agg_metrics['total_errors']}")
    print(f"      - Total throughput: {agg_metrics['total_throughput_mb']:.1f} MB")
    
    # Mostra anomalie rilevate
    if llm_data.anomaly_indicators:
        print("\n5. Detected Anomalies:")
        for i, anomaly in enumerate(llm_data.anomaly_indicators, 1):
            print(f"   🚨 Anomaly {i}:")
            print(f"      - Type: {anomaly.type}")
            print(f"      - Severity: {anomaly.severity:.2f}")
            print(f"      - Description: {anomaly.description}")
            print(f"      - Affected: {', '.join(anomaly.affected_components)}")
            print(f"      - Confidence: {anomaly.confidence:.2f}")
    else:
        print("\n5. No anomalies detected ✅")
    
    # Crea embedding del contesto
    print("\n6. Creating context embedding...")
    embedding = integrator.create_context_embedding(llm_data)
    
    print(f"   ✅ Context embedding created:")
    print(f"      - Total dimension: {embedding.dimension}")
    print(f"      - Topology features: {len(embedding.topology_embedding['features'])}")
    print(f"      - Performance features: {len(embedding.performance_embedding['features'])}")
    print(f"      - Temporal features: {len(embedding.temporal_embedding['features'])}")
    
    # Valida schema LLM
    print("\n7. Validating LLM schema...")
    validation = integrator.validate_llm_schema(llm_data)
    
    if validation.is_valid:
        print(f"   ✅ Schema validation passed!")
        print(f"      - Quality score: {validation.quality_score:.2f}")
    else:
        print(f"   ❌ Schema validation failed:")
        for issue in validation.issues:
            print(f"      - {issue}")
    
    # Mostra features temporali
    print("\n8. Temporal Features:")
    temporal = llm_data.temporal_features
    print(f"   🕐 Time context:")
    print(f"      - Hour of day: {temporal['hour_of_day']}")
    print(f"      - Day of week: {temporal['day_of_week']}")
    print(f"      - Is weekend: {temporal['is_weekend']}")
    print(f"      - Business hours: {temporal['is_business_hours']}")
    
    # Salva output JSON
    print("\n9. Saving LLM-formatted data...")
    output_dir = Path("data/history")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # File principale
    main_file = output_dir / "network_context_latest.json"
    with open(main_file, 'w', encoding='utf-8') as f:
        f.write(llm_data.to_json(indent=2))
    
    # File con timestamp per storico
    timestamp_str = time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime(snapshot.timestamp))
    history_file = output_dir / f"network_state_{timestamp_str}.json"
    with open(history_file, 'w', encoding='utf-8') as f:
        f.write(llm_data.to_json(indent=2))
    
    # Salva embedding separatamente
    embedding_file = output_dir / "context_embedding.json"
    with open(embedding_file, 'w', encoding='utf-8') as f:
        json.dump(embedding.to_dict(), f, indent=2, ensure_ascii=False)
    
    print(f"   ✅ Files saved:")
    print(f"      - Latest context: {main_file}")
    print(f"      - Historical data: {history_file}")
    print(f"      - Context embedding: {embedding_file}")
    
    # Statistiche finali
    print("\n10. Summary Statistics:")
    json_size = len(llm_data.to_json()) / 1024  # KB
    print(f"    📊 Data size: {json_size:.1f} KB")
    print(f"    🔢 Performance vectors: {len(llm_data.performance_vectors)}")
    print(f"    🎯 Anomalies: {len(llm_data.anomaly_indicators)}")
    print(f"    📐 Embedding dimension: {embedding.dimension}")
    print(f"    ✨ Quality score: {validation.quality_score:.2f}")
    
    print("\n🎉 LLM Integration Demo completed successfully!")
    print("\nThe generated JSON data is now ready for LLM model consumption.")
    print("You can use this data for:")
    print("  • Network anomaly detection")
    print("  • Performance analysis")
    print("  • Topology optimization")
    print("  • Predictive maintenance")


if __name__ == "__main__":
    main()