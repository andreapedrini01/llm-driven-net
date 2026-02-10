#!/usr/bin/env python3
"""
Test salvataggio con nuovo formato usando dati mock
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


def test_save_new_format():
    """Test salvataggio nuovo formato"""
    print("🧪 Test Salvataggio Nuovo Formato JSON")
    print("=" * 50)
    
    # Crea dati mock realistici
    timestamp = time.time()
    
    # Switches (4 switch come in tree topology)
    switches = [
        SwitchInfo(dpid=1, ports=[1, 2, 3, 4], active=True),
        SwitchInfo(dpid=2, ports=[1, 2, 3], active=True),
        SwitchInfo(dpid=3, ports=[1, 2, 3], active=True),
        SwitchInfo(dpid=4, ports=[1, 2, 3], active=True),
    ]
    
    # Links (tree topology)
    links = [
        LinkInfo(src_dpid=1, dst_dpid=2, src_port=1, dst_port=1, active=True),
        LinkInfo(src_dpid=1, dst_dpid=3, src_port=2, dst_port=1, active=True),
        LinkInfo(src_dpid=1, dst_dpid=4, src_port=3, dst_port=1, active=True),
    ]
    
    # Port metrics con traffico realistico
    port_stats = {
        1: [
            PortMetrics(port_no=1, rx_packets=15000, tx_packets=15000, rx_bytes=1500000, tx_bytes=1500000,
                       rx_errors=0, tx_errors=0, rx_dropped=0, tx_dropped=0),
            PortMetrics(port_no=2, rx_packets=12000, tx_packets=12000, rx_bytes=1200000, tx_bytes=1200000,
                       rx_errors=0, tx_errors=0, rx_dropped=0, tx_dropped=0),
            PortMetrics(port_no=3, rx_packets=10000, tx_packets=10000, rx_bytes=1000000, tx_bytes=1000000,
                       rx_errors=0, tx_errors=0, rx_dropped=0, tx_dropped=0),
        ],
        2: [
            PortMetrics(port_no=1, rx_packets=15000, tx_packets=15000, rx_bytes=1500000, tx_bytes=1500000,
                       rx_errors=0, tx_errors=0, rx_dropped=0, tx_dropped=0),
            PortMetrics(port_no=2, rx_packets=5000, tx_packets=5000, rx_bytes=500000, tx_bytes=500000,
                       rx_errors=0, tx_errors=0, rx_dropped=0, tx_dropped=0),
        ],
        3: [
            PortMetrics(port_no=1, rx_packets=12000, tx_packets=12000, rx_bytes=1200000, tx_bytes=1200000,
                       rx_errors=0, tx_errors=0, rx_dropped=0, tx_dropped=0),
            PortMetrics(port_no=2, rx_packets=8000, tx_packets=8000, rx_bytes=800000, tx_bytes=800000,
                       rx_errors=0, tx_errors=0, rx_dropped=0, tx_dropped=0),
        ],
        4: [
            PortMetrics(port_no=1, rx_packets=10000, tx_packets=10000, rx_bytes=1000000, tx_bytes=1000000,
                       rx_errors=0, tx_errors=0, rx_dropped=0, tx_dropped=0),
            PortMetrics(port_no=2, rx_packets=6000, tx_packets=6000, rx_bytes=600000, tx_bytes=600000,
                       rx_errors=0, tx_errors=0, rx_dropped=0, tx_dropped=0),
        ]
    }
    
    # Crea snapshot
    topology = TopologyData(switches=switches, links=links)
    metrics = MetricsData(port_statistics=port_stats)
    snapshot = NetworkSnapshot(timestamp=timestamp, topology=topology, metrics=metrics, metadata={})
    
    print("\n1. Generazione formato LLM...")
    integrator = LLMIntegrator(enable_anomaly_detection=True)
    llm_data = integrator.format_for_llm(snapshot)
    print("   ✓ Formato generato")
    
    print("\n2. Salvataggio su file...")
    fs_config = FileSystemConfig(
        base_output_dir="data",
        llm_output_dir="history",
        history_dir="history"
    )
    fs_manager = FileSystemManager(fs_config)
    
    saved_file = fs_manager.save_llm_data(llm_data, as_latest=True)
    print(f"   ✓ File salvato: {saved_file}")
    print(f"   ✓ Dimensione: {saved_file.stat().st_size} bytes")
    
    print("\n3. Contenuto del file salvato:")
    print("=" * 70)
    with open(saved_file, 'r') as f:
        content = f.read()
        print(content)
    
    print("\n" + "=" * 70)
    
    # Verifica anche il file latest
    latest_file = Path("data/history/network_context_latest.json")
    if latest_file.exists():
        print(f"\n4. File latest aggiornato:")
        print(f"   ✓ {latest_file}")
        print(f"   ✓ Dimensione: {latest_file.stat().st_size} bytes")
        
        # Verifica che sia identico
        with open(latest_file, 'r') as f:
            latest_data = json.load(f)
        
        print(f"\n5. Verifica struttura:")
        print(f"   ✓ timestamp: {latest_data.get('timestamp')}")
        print(f"   ✓ switches: {len(latest_data.get('topology', {}).get('switches', []))}")
        print(f"   ✓ links: {len(latest_data.get('topology', {}).get('links', []))}")
        print(f"   ✓ metrics.bandwidth.total_capacity: {latest_data.get('metrics', {}).get('bandwidth', {}).get('total_capacity')}")
        print(f"   ✓ metrics.bandwidth.utilization_percentage: {latest_data.get('metrics', {}).get('bandwidth', {}).get('utilization_percentage')}%")
        print(f"   ✓ anomalies: {len(latest_data.get('anomalies', []))}")
    
    print("\n✅ Test completato con successo!")
    print(f"\n📊 Il file JSON è stato salvato correttamente in data/history/")


if __name__ == "__main__":
    test_save_new_format()
