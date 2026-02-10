#!/usr/bin/env python3
"""
Test con hosts e anomalie intenzionali
"""

import sys
import json
import time
from pathlib import Path

# Aggiungi il path del modulo
sys.path.insert(0, str(Path(__file__).parent))

from network_state_collector.llm_integrator import LLMIntegrator
from network_state_collector.filesystem_manager import FileSystemManager, FileSystemConfig
from network_state_collector.models.core import NetworkSnapshot, TopologyData, MetricsData, SwitchInfo, LinkInfo, PortMetrics


def test_with_hosts_and_anomalies():
    """Test con hosts e anomalie"""
    print("🧪 Test con Hosts e Anomalie")
    print("=" * 70)
    
    # Crea dati mock con anomalie
    timestamp = time.time()
    
    # Switches (uno sarà isolato per creare anomalia)
    switches = [
        SwitchInfo(dpid=1, ports=[1, 2, 3, 4], active=True),
        SwitchInfo(dpid=2, ports=[1, 2, 3], active=True),
        SwitchInfo(dpid=3, ports=[1, 2, 3], active=True),
        SwitchInfo(dpid=4, ports=[1, 2], active=True),  # Switch isolato!
    ]
    
    # Links (switch 4 non è collegato - anomalia!)
    links = [
        LinkInfo(src_dpid=1, dst_dpid=2, src_port=1, dst_port=1, active=True),
        LinkInfo(src_dpid=1, dst_dpid=3, src_port=2, dst_port=1, active=True),
        # Switch 4 non ha link - sarà rilevato come isolato
    ]
    
    # Port metrics con anomalie:
    # - Switch 1 porta 3: alta utilizzazione (>80%)
    # - Switch 2 porta 2: alto tasso di errori
    # - Switch 3 porta 2: packet loss
    port_stats = {
        1: [
            # Porta normale
            PortMetrics(port_no=1, rx_packets=15000, tx_packets=15000, 
                       rx_bytes=1500000, tx_bytes=1500000,
                       rx_errors=0, tx_errors=0, rx_dropped=0, tx_dropped=0),
            # Porta normale
            PortMetrics(port_no=2, rx_packets=12000, tx_packets=12000, 
                       rx_bytes=1200000, tx_bytes=1200000,
                       rx_errors=0, tx_errors=0, rx_dropped=0, tx_dropped=0),
            # ANOMALIA: Alta utilizzazione (90%)
            PortMetrics(port_no=3, rx_packets=90000, tx_packets=90000, 
                       rx_bytes=90000000, tx_bytes=90000000,
                       rx_errors=0, tx_errors=0, rx_dropped=0, tx_dropped=0),
            # Porta host
            PortMetrics(port_no=4, rx_packets=5000, tx_packets=5000, 
                       rx_bytes=500000, tx_bytes=500000,
                       rx_errors=0, tx_errors=0, rx_dropped=0, tx_dropped=0),
        ],
        2: [
            # Porta normale
            PortMetrics(port_no=1, rx_packets=15000, tx_packets=15000, 
                       rx_bytes=1500000, tx_bytes=1500000,
                       rx_errors=0, tx_errors=0, rx_dropped=0, tx_dropped=0),
            # ANOMALIA: Alto tasso di errori (2%)
            PortMetrics(port_no=2, rx_packets=10000, tx_packets=10000, 
                       rx_bytes=1000000, tx_bytes=1000000,
                       rx_errors=200, tx_errors=200, rx_dropped=0, tx_dropped=0),
            # Porta host
            PortMetrics(port_no=3, rx_packets=3000, tx_packets=3000, 
                       rx_bytes=300000, tx_bytes=300000,
                       rx_errors=0, tx_errors=0, rx_dropped=0, tx_dropped=0),
        ],
        3: [
            # Porta normale
            PortMetrics(port_no=1, rx_packets=12000, tx_packets=12000, 
                       rx_bytes=1200000, tx_bytes=1200000,
                       rx_errors=0, tx_errors=0, rx_dropped=0, tx_dropped=0),
            # ANOMALIA: Packet loss (1%)
            PortMetrics(port_no=2, rx_packets=8000, tx_packets=8000, 
                       rx_bytes=800000, tx_bytes=800000,
                       rx_errors=0, tx_errors=0, rx_dropped=80, tx_dropped=80),
            # Porta host
            PortMetrics(port_no=3, rx_packets=2000, tx_packets=2000, 
                       rx_bytes=200000, tx_bytes=200000,
                       rx_errors=0, tx_errors=0, rx_dropped=0, tx_dropped=0),
        ],
        4: [
            # Switch isolato - solo porte host
            PortMetrics(port_no=1, rx_packets=1000, tx_packets=1000, 
                       rx_bytes=100000, tx_bytes=100000,
                       rx_errors=0, tx_errors=0, rx_dropped=0, tx_dropped=0),
            PortMetrics(port_no=2, rx_packets=500, tx_packets=500, 
                       rx_bytes=50000, tx_bytes=50000,
                       rx_errors=0, tx_errors=0, rx_dropped=0, tx_dropped=0),
        ]
    }
    
    # Crea snapshot
    topology = TopologyData(switches=switches, links=links)
    metrics = MetricsData(port_statistics=port_stats)
    snapshot = NetworkSnapshot(timestamp=timestamp, topology=topology, metrics=metrics, metadata={})
    
    print("\n1. Generazione formato LLM con rilevamento anomalie...")
    integrator = LLMIntegrator(enable_anomaly_detection=True)
    llm_data = integrator.format_for_llm(snapshot)
    print("   ✓ Formato generato")
    print(f"   ✓ Anomalie rilevate: {len(llm_data.get('anomalies', []))}")
    
    # Aggiungi hosts manualmente (Ryu non fornisce info hosts)
    print("\n2. Aggiunta hosts al JSON...")
    llm_data['topology']['hosts'] = [
        {
            "id": "host_1",
            "mac_address": "00:00:00:00:00:01",
            "ip_address": "10.0.0.1",
            "connected_switch": "switch_0000000000000001",
            "connected_port": 4,
            "status": "active"
        },
        {
            "id": "host_2",
            "mac_address": "00:00:00:00:00:02",
            "ip_address": "10.0.0.2",
            "connected_switch": "switch_0000000000000002",
            "connected_port": 3,
            "status": "active"
        },
        {
            "id": "host_3",
            "mac_address": "00:00:00:00:00:03",
            "ip_address": "10.0.0.3",
            "connected_switch": "switch_0000000000000003",
            "connected_port": 3,
            "status": "active"
        },
        {
            "id": "host_4",
            "mac_address": "00:00:00:00:00:04",
            "ip_address": "10.0.0.4",
            "connected_switch": "switch_0000000000000004",
            "connected_port": 1,
            "status": "active"
        }
    ]
    print(f"   ✓ Hosts aggiunti: {len(llm_data['topology']['hosts'])}")
    
    print("\n3. Salvataggio su file...")
    fs_config = FileSystemConfig(
        base_output_dir="data",
        llm_output_dir="history",
        history_dir="history"
    )
    fs_manager = FileSystemManager(fs_config)
    
    saved_file = fs_manager.save_llm_data(llm_data, as_latest=True)
    print(f"   ✓ File salvato: {saved_file}")
    print(f"   ✓ Dimensione: {saved_file.stat().st_size} bytes")
    
    print("\n4. Contenuto del file salvato:")
    print("=" * 70)
    with open(saved_file, 'r') as f:
        content = f.read()
        print(content)
    
    print("\n" + "=" * 70)
    
    # Analisi anomalie
    print("\n5. Analisi Anomalie Rilevate:")
    if llm_data.get('anomalies'):
        for i, anomaly in enumerate(llm_data['anomalies'], 1):
            print(f"\n   Anomalia {i}:")
            print(f"   - Tipo: {anomaly.get('type')}")
            print(f"   - Severità: {anomaly.get('severity'):.2f}")
            print(f"   - Descrizione: {anomaly.get('description')}")
            print(f"   - Componenti: {', '.join(anomaly.get('affected_components', []))}")
            print(f"   - Confidenza: {anomaly.get('confidence'):.2%}")
    else:
        print("   Nessuna anomalia rilevata")
    
    # Verifica struttura
    print("\n6. Verifica Struttura Completa:")
    print(f"   ✓ timestamp: {llm_data.get('timestamp')}")
    print(f"   ✓ switches: {len(llm_data.get('topology', {}).get('switches', []))}")
    print(f"   ✓ links: {len(llm_data.get('topology', {}).get('links', []))}")
    print(f"   ✓ hosts: {len(llm_data.get('topology', {}).get('hosts', []))}")
    print(f"   ✓ flows: {len(llm_data.get('flows', []))}")
    print(f"   ✓ slices: {len(llm_data.get('slices', []))}")
    print(f"   ✓ anomalies: {len(llm_data.get('anomalies', []))}")
    
    # Metriche
    metrics = llm_data.get('metrics', {})
    print(f"\n7. Metriche:")
    print(f"   Bandwidth:")
    print(f"     - Total: {metrics.get('bandwidth', {}).get('total_capacity')} Mbps")
    print(f"     - Used: {metrics.get('bandwidth', {}).get('used_bandwidth')} Mbps")
    print(f"     - Utilization: {metrics.get('bandwidth', {}).get('utilization_percentage')}%")
    print(f"   Latency:")
    print(f"     - Average: {metrics.get('latency', {}).get('average_latency')} ms")
    print(f"     - Min: {metrics.get('latency', {}).get('min_latency')} ms")
    print(f"     - Max: {metrics.get('latency', {}).get('max_latency')} ms")
    
    print("\n✅ Test completato con successo!")
    print(f"\n📊 File JSON con hosts e anomalie salvato in data/history/")
    print(f"🔍 Anomalie rilevate: {len(llm_data.get('anomalies', []))}")
    print(f"👥 Hosts configurati: {len(llm_data['topology']['hosts'])}")


if __name__ == "__main__":
    test_with_hosts_and_anomalies()
