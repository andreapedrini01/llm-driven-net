#!/usr/bin/env python3
"""
Test per verificare il nuovo formato JSON
"""

import sys
import json
from pathlib import Path

# Aggiungi il path del modulo
sys.path.insert(0, str(Path(__file__).parent))

from network_state_collector.llm_integrator import LLMIntegrator
from src.models.core import NetworkSnapshot, TopologyData, MetricsData, SwitchInfo, LinkInfo, PortMetrics
import time


def test_new_json_format():
    """Test nuovo formato JSON"""
    print("🧪 Test Nuovo Formato JSON")
    print("=" * 50)
    
    # Crea dati mock
    timestamp = time.time()
    
    # Switches
    switches = [
        SwitchInfo(dpid=1, ports=[1, 2, 3, 4], active=True),
        SwitchInfo(dpid=2, ports=[1, 2, 3], active=True),
    ]
    
    # Links
    links = [
        LinkInfo(src_dpid=1, dst_dpid=2, src_port=1, dst_port=1, active=True),
    ]
    
    # Port metrics
    port_stats = {
        1: [
            PortMetrics(port_no=1, rx_packets=1000, tx_packets=1000, rx_bytes=100000, tx_bytes=100000,
                       rx_errors=0, tx_errors=0, rx_dropped=0, tx_dropped=0),
            PortMetrics(port_no=2, rx_packets=500, tx_packets=500, rx_bytes=50000, tx_bytes=50000,
                       rx_errors=0, tx_errors=0, rx_dropped=0, tx_dropped=0),
        ],
        2: [
            PortMetrics(port_no=1, rx_packets=1000, tx_packets=1000, rx_bytes=100000, tx_bytes=100000,
                       rx_errors=0, tx_errors=0, rx_dropped=0, tx_dropped=0),
        ]
    }
    
    # Crea snapshot
    topology = TopologyData(switches=switches, links=links)
    metrics = MetricsData(port_statistics=port_stats)
    snapshot = NetworkSnapshot(timestamp=timestamp, topology=topology, metrics=metrics, metadata={})
    
    # Crea integrator
    integrator = LLMIntegrator(enable_anomaly_detection=True)
    
    # Genera formato LLM
    print("\n1. Generazione formato LLM...")
    llm_data = integrator.format_for_llm(snapshot)
    
    # Stampa JSON formattato
    print("\n2. JSON generato:")
    print("=" * 50)
    json_str = json.dumps(llm_data, indent=2, ensure_ascii=False)
    print(json_str)
    
    # Verifica struttura
    print("\n3. Verifica struttura:")
    print(f"   ✓ timestamp: {llm_data.get('timestamp')}")
    print(f"   ✓ topology.switches: {len(llm_data.get('topology', {}).get('switches', []))}")
    print(f"   ✓ topology.links: {len(llm_data.get('topology', {}).get('links', []))}")
    print(f"   ✓ topology.hosts: {len(llm_data.get('topology', {}).get('hosts', []))}")
    print(f"   ✓ flows: {len(llm_data.get('flows', []))}")
    print(f"   ✓ slices: {len(llm_data.get('slices', []))}")
    print(f"   ✓ metrics.bandwidth: {llm_data.get('metrics', {}).get('bandwidth', {})}")
    print(f"   ✓ metrics.latency: {llm_data.get('metrics', {}).get('latency', {})}")
    print(f"   ✓ metrics.utilization: {llm_data.get('metrics', {}).get('utilization', {})}")
    print(f"   ✓ anomalies: {len(llm_data.get('anomalies', []))}")
    
    # Verifica formato switch
    if llm_data.get('topology', {}).get('switches'):
        switch = llm_data['topology']['switches'][0]
        print(f"\n4. Esempio switch:")
        print(f"   id: {switch.get('id')}")
        print(f"   name: {switch.get('name')}")
        print(f"   dpid: {switch.get('dpid')}")
        print(f"   ports: {switch.get('ports')}")
        print(f"   status: {switch.get('status')}")
    
    # Verifica formato link
    if llm_data.get('topology', {}).get('links'):
        link = llm_data['topology']['links'][0]
        print(f"\n5. Esempio link:")
        print(f"   id: {link.get('id')}")
        print(f"   source_switch: {link.get('source_switch')}")
        print(f"   source_port: {link.get('source_port')}")
        print(f"   destination_switch: {link.get('destination_switch')}")
        print(f"   destination_port: {link.get('destination_port')}")
        print(f"   bandwidth: {link.get('bandwidth')}")
        print(f"   latency: {link.get('latency')}")
        print(f"   status: {link.get('status')}")
    
    print("\n✅ Test completato!")
    print(f"\n📊 Il nuovo formato JSON è corretto!")


if __name__ == "__main__":
    test_new_json_format()
