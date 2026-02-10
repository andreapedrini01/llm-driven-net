#!/usr/bin/env python3
"""Test anomaly detection"""

import time
import json
from network_state_collector import NetworkStateCollector

# Usa config di default
collector = NetworkStateCollector()

print("🔍 Avvio monitoraggio anomalie...")
print("   Raccolgo 3 snapshot prima della disconnessione...")

for i in range(3):
    snapshot = collector.collect_snapshot()
    print(f"   ✓ Snapshot {i+1}/3 raccolto")
    time.sleep(2)

print("\n⚠️  ORA DISCONNETTI LO SWITCH s2 in Mininet:")
print("   mininet> sh ovs-vsctl del-br s2")
print("\n   Premi INVIO quando hai disconnesso lo switch...")
input()

print("\n🔍 Raccolgo 3 snapshot dopo la disconnessione...")
for i in range(3):
    snapshot = collector.collect_snapshot()
    print(f"   ✓ Snapshot {i+1}/3 raccolto")
    time.sleep(2)

# Mostra anomalie finali
with open('data/llm_output/network_context_latest.json') as f:
    data = json.load(f)
    
print("\n📊 Anomalie rilevate:")
if data['anomaly_indicators']:
    for a in data['anomaly_indicators']:
        print(f"   🚨 {a['type']}: {a['description']}")
        print(f"      Severity: {a['severity']}, Confidence: {a['confidence']}")
else:
    print("   ✅ Nessuna anomalia rilevata")
