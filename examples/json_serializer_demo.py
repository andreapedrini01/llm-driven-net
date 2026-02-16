#!/usr/bin/env python3
"""
Demo per JSONSerializer

Dimostra le funzionalità di serializzazione/deserializzazione JSON
con pretty printing per i dati di rete.
"""

import sys
import os
import tempfile
from pathlib import Path

# Aggiungi il path del modulo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from network_state_collector.json_serializer import JSONSerializer
from src.models.core import (
    NetworkSnapshot, TopologyData, MetricsData, SwitchInfo, LinkInfo, PortMetrics
)
from src.models.llm import LLMNetworkData, AnomalyIndicator


def create_sample_network_snapshot() -> NetworkSnapshot:
    """Crea un NetworkSnapshot di esempio"""
    print("📊 Creando NetworkSnapshot di esempio...")
    
    # Crea switch
    switches = [
        SwitchInfo(dpid="0000000000000001", active=True, ports=[1, 2, 3]),
        SwitchInfo(dpid="0000000000000002", active=True, ports=[1, 2, 3]),
        SwitchInfo(dpid="0000000000000003", active=True, ports=[1, 2])
    ]
    
    # Crea link
    links = [
        LinkInfo(
            src_dpid="0000000000000001",
            dst_dpid="0000000000000002",
            src_port=2,
            dst_port=1,
            active=True
        ),
        LinkInfo(
            src_dpid="0000000000000002",
            dst_dpid="0000000000000003",
            src_port=3,
            dst_port=1,
            active=True
        )
    ]
    
    # Crea topologia
    topology = TopologyData(
        switches=switches,
        links=links,
        graph_representation={
            "nodes": len(switches),
            "edges": len(links),
            "density": 0.33
        }
    )
    
    # Crea metriche delle porte
    port_stats = {
        "0000000000000001": [
            PortMetrics(
                port_no=1,
                rx_packets=15000,
                tx_packets=12000,
                rx_bytes=960000,
                tx_bytes=768000,
                rx_errors=5,
                tx_errors=2,
                rx_dropped=1,
                tx_dropped=0
            ),
            PortMetrics(
                port_no=2,
                rx_packets=8000,
                tx_packets=9500,
                rx_bytes=512000,
                tx_bytes=608000,
                rx_errors=0,
                tx_errors=1,
                rx_dropped=0,
                tx_dropped=0
            )
        ],
        "0000000000000002": [
            PortMetrics(
                port_no=1,
                rx_packets=9500,
                tx_packets=8000,
                rx_bytes=608000,
                tx_bytes=512000,
                rx_errors=1,
                tx_errors=0,
                rx_dropped=0,
                tx_dropped=0
            ),
            PortMetrics(
                port_no=3,
                rx_packets=5000,
                tx_packets=4800,
                rx_bytes=320000,
                tx_bytes=307200,
                rx_errors=0,
                tx_errors=0,
                rx_dropped=0,
                tx_dropped=0
            )
        ]
    }
    
    # Crea metriche
    metrics = MetricsData(
        port_statistics=port_stats,
        aggregated_metrics={},
        quality_indicators=None
    )
    
    # Crea snapshot
    snapshot = NetworkSnapshot(
        timestamp=1640995200.0,  # 2022-01-01 00:00:00 UTC
        topology=topology,
        metrics=metrics,
        derived_metrics=None,
        metadata={
            "version": "1.0",
            "collector": "demo",
            "environment": "test"
        }
    )
    
    print(f"✅ NetworkSnapshot creato con {len(switches)} switch e {len(links)} link")
    return snapshot


def create_sample_llm_data() -> LLMNetworkData:
    """Crea LLMNetworkData di esempio"""
    print("🤖 Creando LLMNetworkData di esempio...")
    
    llm_data = LLMNetworkData(
        network_context={
            "topology": {
                "nodes": ["0000000000000001", "0000000000000002", "0000000000000003"],
                "edges": [
                    {"src": "0000000000000001", "dst": "0000000000000002", "port_out": 2, "port_in": 1},
                    {"src": "0000000000000002", "dst": "0000000000000003", "port_out": 3, "port_in": 1}
                ],
                "node_count": 3,
                "edge_count": 2
            },
            "performance": {
                "utilization_vectors": [[0.15, 0.0003], [0.12, 0.0001], [0.08, 0.0]],
                "error_rates": [0.0003, 0.0001, 0.0],
                "congestion_indicators": [False, False, False],
                "aggregated_metrics": {
                    "average_utilization": 11.67,
                    "total_errors": 9,
                    "total_throughput_mb": 3.84,
                    "active_ports": 4
                }
            },
            "metadata": {
                "timestamp": 1640995200.0,
                "collection_time": "2022-01-01 00:00:00"
            }
        },
        performance_vectors=[
            [15.0, 0.0003, 1.44],  # Switch 1, Port 1
            [12.0, 0.0001, 1.12],  # Switch 1, Port 2
            [8.0, 0.0001, 0.88],   # Switch 2, Port 1
            [5.0, 0.0, 0.61]       # Switch 2, Port 3
        ],
        topology_embedding={
            "adjacency_matrix": [[0, 1, 0], [1, 0, 1], [0, 1, 0]],
            "node_degrees": [1, 2, 1],
            "average_degree": 1.33,
            "node_count": 3,
            "edge_count": 2,
            "density": 0.33
        },
        temporal_features={
            "timestamp": 1640995200.0,
            "hour_of_day": 0,
            "day_of_week": 5,  # Saturday
            "day_of_month": 1,
            "month": 1,
            "is_weekend": True,
            "is_business_hours": False,
            "time_features": {
                "hour_sin": 0.0,
                "hour_cos": 1.0,
                "day_sin": -0.78,
                "day_cos": 0.62
            }
        },
        anomaly_indicators=[
            AnomalyIndicator(
                type="high_utilization",
                severity=0.15,
                description="Moderate utilization on port 1: 15.0%",
                affected_components=["0000000000000001:1"],
                timestamp=1640995200.0,
                confidence=0.85
            )
        ]
    )
    
    print("✅ LLMNetworkData creato con embedding topologico e features temporali")
    return llm_data


def demo_pretty_printing():
    """Dimostra le funzionalità di pretty printing"""
    print("\n" + "="*60)
    print("🎨 DEMO: Pretty Printing")
    print("="*60)
    
    # Crea serializzatori con diverse configurazioni
    pretty_serializer = JSONSerializer(pretty_print=True, indent=2, sort_keys=True)
    compact_serializer = JSONSerializer(pretty_print=False)
    
    # Crea dati di test
    test_data = {
        "network": "test",
        "switches": ["sw1", "sw2"],
        "metrics": {"utilization": 0.5, "errors": 0}
    }
    
    # Serializza in formato compatto
    compact_json = compact_serializer.pretty_format(str(test_data).replace("'", '"'))
    print("📦 Formato compatto:")
    print(compact_json)
    
    # Applica pretty formatting
    pretty_json = pretty_serializer.pretty_format(compact_json)
    print("\n✨ Formato pretty print:")
    print(pretty_json)
    
    # Valida formato
    validation = pretty_serializer.validate_json_format(pretty_json)
    print(f"\n✅ Validazione: {'VALIDO' if validation.is_valid else 'NON VALIDO'}")
    if validation.issues:
        print(f"⚠️  Issues: {validation.issues}")


def demo_serialization():
    """Dimostra serializzazione/deserializzazione"""
    print("\n" + "="*60)
    print("🔄 DEMO: Serializzazione/Deserializzazione")
    print("="*60)
    
    serializer = JSONSerializer(pretty_print=True, indent=2)
    
    # Crea dati di esempio
    snapshot = create_sample_network_snapshot()
    llm_data = create_sample_llm_data()
    
    print("\n📤 Serializzazione NetworkSnapshot...")
    snapshot_json = serializer.serialize_network_snapshot(snapshot)
    print(f"✅ JSON generato: {len(snapshot_json)} caratteri")
    print("📋 Anteprima (prime 200 caratteri):")
    print(snapshot_json[:200] + "..." if len(snapshot_json) > 200 else snapshot_json)
    
    print("\n📤 Serializzazione LLMNetworkData...")
    llm_json = serializer.serialize_llm_data(llm_data)
    print(f"✅ JSON generato: {len(llm_json)} caratteri")
    print("📋 Anteprima (prime 200 caratteri):")
    print(llm_json[:200] + "..." if len(llm_json) > 200 else llm_json)
    
    print("\n📥 Deserializzazione...")
    deserialized_snapshot = serializer.deserialize_network_snapshot(snapshot_json)
    deserialized_llm = serializer.deserialize_llm_data(llm_json)
    
    print(f"✅ NetworkSnapshot deserializzato: timestamp={deserialized_snapshot.timestamp}")
    print(f"✅ LLMNetworkData deserializzato: {len(deserialized_llm.performance_vectors)} vettori performance")
    
    return snapshot_json, llm_json


def demo_file_operations():
    """Dimostra operazioni su file"""
    print("\n" + "="*60)
    print("💾 DEMO: Operazioni su File")
    print("="*60)
    
    serializer = JSONSerializer(pretty_print=True, indent=2)
    
    # Crea dati di esempio
    snapshot = create_sample_network_snapshot()
    llm_data = create_sample_llm_data()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Salva su file
        snapshot_file = temp_path / "network_snapshot.json"
        llm_file = temp_path / "llm_data.json"
        
        print(f"💾 Salvando NetworkSnapshot in {snapshot_file.name}...")
        serializer.save_to_file(snapshot, snapshot_file)
        
        print(f"💾 Salvando LLMNetworkData in {llm_file.name}...")
        serializer.save_to_file(llm_data, llm_file)
        
        # Verifica file creati
        print(f"✅ File NetworkSnapshot: {snapshot_file.stat().st_size} bytes")
        print(f"✅ File LLMNetworkData: {llm_file.stat().st_size} bytes")
        
        # Carica da file
        print("\n📂 Caricamento da file...")
        loaded_snapshot = serializer.load_from_file(snapshot_file, 'snapshot')
        loaded_llm = serializer.load_from_file(llm_file, 'llm')
        
        print(f"✅ NetworkSnapshot caricato: {len(loaded_snapshot.topology.switches)} switch")
        print(f"✅ LLMNetworkData caricato: {len(loaded_llm.anomaly_indicators)} anomalie")
        
        # Test auto-detect
        print("\n🔍 Test auto-detect tipo file...")
        auto_snapshot = serializer.load_from_file(snapshot_file, 'auto')
        auto_llm = serializer.load_from_file(llm_file, 'auto')
        
        print(f"✅ Auto-detect NetworkSnapshot: {type(auto_snapshot).__name__}")
        print(f"✅ Auto-detect LLMNetworkData: {type(auto_llm).__name__}")


def demo_validation():
    """Dimostra funzionalità di validazione"""
    print("\n" + "="*60)
    print("✅ DEMO: Validazione JSON")
    print("="*60)
    
    serializer = JSONSerializer(pretty_print=True, indent=2)
    
    # Test JSON validi e non validi
    test_cases = [
        ('{"valid": "json"}', "JSON compatto valido"),
        ('{\n  "pretty": "json"\n}', "JSON pretty formatted"),
        ('{"invalid": json}', "JSON non valido"),
        ('', "JSON vuoto"),
        ('{"nested": {"data": [1, 2, 3]}}', "JSON nested compatto")
    ]
    
    for json_str, description in test_cases:
        print(f"\n🧪 Test: {description}")
        print(f"📝 Input: {json_str}")
        
        result = serializer.validate_json_format(json_str)
        
        status = "✅ VALIDO" if result.is_valid else "❌ NON VALIDO"
        print(f"🔍 Risultato: {status} (score: {result.quality_score:.1f})")
        
        if result.issues:
            for issue in result.issues:
                print(f"⚠️  Issue: {issue}")


def demo_round_trip():
    """Dimostra round-trip serialization"""
    print("\n" + "="*60)
    print("🔄 DEMO: Round-trip Serialization")
    print("="*60)
    
    serializer = JSONSerializer(pretty_print=True, indent=2)
    
    # Crea dati originali
    original_snapshot = create_sample_network_snapshot()
    original_llm = create_sample_llm_data()
    
    print("🔄 Test round-trip NetworkSnapshot...")
    # NetworkSnapshot: Original -> JSON -> Deserialized
    json_str = serializer.serialize_network_snapshot(original_snapshot)
    deserialized = serializer.deserialize_network_snapshot(json_str)
    
    print(f"✅ Timestamp originale: {original_snapshot.timestamp}")
    print(f"✅ Timestamp deserializzato: {deserialized.timestamp}")
    print(f"✅ Switch originali: {len(original_snapshot.topology.switches)}")
    print(f"✅ Switch deserializzati: {len(deserialized.topology.switches)}")
    
    print("\n🔄 Test round-trip LLMNetworkData...")
    # LLMNetworkData: Original -> JSON -> Deserialized
    llm_json = serializer.serialize_llm_data(original_llm)
    deserialized_llm = serializer.deserialize_llm_data(llm_json)
    
    print(f"✅ Performance vectors originali: {len(original_llm.performance_vectors)}")
    print(f"✅ Performance vectors deserializzati: {len(deserialized_llm.performance_vectors)}")
    print(f"✅ Network context preservato: {deserialized_llm.network_context == original_llm.network_context}")


def main():
    """Funzione principale del demo"""
    print("🚀 JSONSerializer Demo")
    print("=" * 60)
    print("Dimostra le funzionalità del JSONSerializer per il Network State Collector")
    
    try:
        # Esegui tutti i demo
        demo_pretty_printing()
        demo_serialization()
        demo_file_operations()
        demo_validation()
        demo_round_trip()
        
        print("\n" + "="*60)
        print("🎉 Demo completato con successo!")
        print("="*60)
        print("\n📋 Funzionalità dimostrate:")
        print("  ✅ Pretty printing configurabile")
        print("  ✅ Serializzazione NetworkSnapshot e LLMNetworkData")
        print("  ✅ Deserializzazione con ricostruzione oggetti")
        print("  ✅ Operazioni su file con auto-detect tipo")
        print("  ✅ Validazione formato JSON")
        print("  ✅ Round-trip serialization")
        print("\n🔧 Il JSONSerializer è pronto per l'integrazione!")
        
    except Exception as e:
        print(f"\n❌ Errore durante il demo: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())