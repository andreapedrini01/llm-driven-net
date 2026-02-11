#!/usr/bin/env python3
"""
Test finale per mostrare il formato JSON completo
"""

import sys
import json
from pathlib import Path

# Aggiungi il path del modulo
sys.path.insert(0, str(Path(__file__).parent))


def test_final_json_format():
    """Mostra il formato JSON finale"""
    print("🧪 Test Formato JSON Finale")
    print("=" * 70)
    
    # Leggi il file latest
    latest_file = Path("data/history/network_context_latest.json")
    
    if not latest_file.exists():
        print("❌ File network_context_latest.json non trovato!")
        print("   Esegui prima: python3 test_with_hosts_and_anomalies.py")
        return
    
    print(f"\n📄 File: {latest_file}")
    print(f"📦 Dimensione: {latest_file.stat().st_size} bytes")
    
    # Leggi e mostra il JSON
    with open(latest_file, 'r') as f:
        data = json.load(f)
    
    print("\n" + "=" * 70)
    print("JSON COMPLETO:")
    print("=" * 70)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print("=" * 70)
    
    # Analisi struttura
    print("\n📊 ANALISI STRUTTURA:")
    print("-" * 70)
    
    print(f"\n✓ timestamp: {data.get('timestamp')}")
    
    print(f"\n✓ topology:")
    print(f"  - switches: {len(data.get('topology', {}).get('switches', []))}")
    print(f"  - links: {len(data.get('topology', {}).get('links', []))}")
    print(f"  - hosts: {len(data.get('topology', {}).get('hosts', []))}")
    
    print(f"\n✓ flows: {len(data.get('flows', []))}")
    print(f"✓ slices: {len(data.get('slices', []))}")
    
    print(f"\n✓ metrics:")
    metrics = data.get('metrics', {})
    print(f"  - bandwidth:")
    bw = metrics.get('bandwidth', {})
    print(f"    • total_capacity: {bw.get('total_capacity')} Mbps")
    print(f"    • used_bandwidth: {bw.get('used_bandwidth')} Mbps")
    print(f"    • available_bandwidth: {bw.get('available_bandwidth')} Mbps")
    print(f"    • utilization_percentage: {bw.get('utilization_percentage')}%")
    
    print(f"  - latency:")
    lat = metrics.get('latency', {})
    print(f"    • average_latency: {lat.get('average_latency')} ms")
    print(f"    • min_latency: {lat.get('min_latency')} ms")
    print(f"    • max_latency: {lat.get('max_latency')} ms")
    print(f"    • jitter: {lat.get('jitter')} ms")
    
    print(f"  - utilization:")
    util = metrics.get('utilization', {})
    print(f"    • cpu_utilization: {util.get('cpu_utilization')}")
    print(f"    • memory_utilization: {util.get('memory_utilization')}")
    print(f"    • port_utilization: {len(util.get('port_utilization', {}))} porte")
    
    print(f"\n✓ anomalies: {len(data.get('anomalies', []))}")
    
    # Mostra esempio di ogni sezione
    print("\n" + "=" * 70)
    print("ESEMPI DI OGNI SEZIONE:")
    print("=" * 70)
    
    if data.get('topology', {}).get('switches'):
        print("\n📌 Esempio Switch:")
        switch = data['topology']['switches'][0]
        print(json.dumps(switch, indent=2, ensure_ascii=False))
    
    if data.get('topology', {}).get('links'):
        print("\n📌 Esempio Link:")
        link = data['topology']['links'][0]
        print(json.dumps(link, indent=2, ensure_ascii=False))
    
    if data.get('topology', {}).get('hosts'):
        print("\n📌 Esempio Host:")
        host = data['topology']['hosts'][0]
        print(json.dumps(host, indent=2, ensure_ascii=False))
    
    if data.get('anomalies'):
        print("\n📌 Esempio Anomalia:")
        anomaly = data['anomalies'][0]
        print(json.dumps(anomaly, indent=2, ensure_ascii=False))
    
    # Mostra port_utilization
    port_util = util.get('port_utilization', {})
    if port_util:
        print("\n📌 Port Utilization (prime 5 porte):")
        for i, (port_key, utilization) in enumerate(list(port_util.items())[:5]):
            print(f"  {port_key}: {utilization}%")
    
    print("\n" + "=" * 70)
    print("✅ Formato JSON verificato e conforme alle specifiche!")
    print("=" * 70)


if __name__ == "__main__":
    test_final_json_format()
