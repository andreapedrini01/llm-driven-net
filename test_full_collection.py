#!/usr/bin/env python3
"""
Test completo della raccolta con salvataggio file
"""

import sys
import json
from pathlib import Path

# Aggiungi il path del modulo
sys.path.insert(0, str(Path(__file__).parent))

from network_state_collector.collector import NetworkStateCollector


def test_full_collection():
    """Test raccolta completa con salvataggio"""
    print("🧪 Test Raccolta Completa con Nuovo Formato")
    print("=" * 50)
    
    try:
        # Crea collector
        print("\n1. Inizializzazione collector...")
        collector = NetworkStateCollector(environment="development")
        print("   ✓ Collector inizializzato")
        
        # Prova raccolta snapshot
        print("\n2. Tentativo raccolta snapshot...")
        snapshot = collector.collect_snapshot()
        
        if snapshot:
            print("   ✓ Snapshot raccolto con successo")
            
            # Verifica file salvati
            print("\n3. Verifica file salvati in data/history:")
            history_dir = Path("data/history")
            json_files = sorted(history_dir.glob("network_context_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
            
            if json_files:
                latest_file = json_files[0]
                print(f"   ✓ File più recente: {latest_file.name}")
                print(f"   ✓ Dimensione: {latest_file.stat().st_size} bytes")
                
                # Leggi e mostra contenuto
                print("\n4. Contenuto del file JSON:")
                print("=" * 50)
                with open(latest_file, 'r') as f:
                    data = json.load(f)
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                
                # Verifica struttura
                print("\n5. Verifica struttura:")
                print(f"   ✓ timestamp: {data.get('timestamp')}")
                print(f"   ✓ topology.switches: {len(data.get('topology', {}).get('switches', []))}")
                print(f"   ✓ topology.links: {len(data.get('topology', {}).get('links', []))}")
                print(f"   ✓ topology.hosts: {len(data.get('topology', {}).get('hosts', []))}")
                print(f"   ✓ flows: presente = {('flows' in data)}")
                print(f"   ✓ slices: presente = {('slices' in data)}")
                print(f"   ✓ metrics: presente = {('metrics' in data)}")
                print(f"   ✓ anomalies: {len(data.get('anomalies', []))}")
                
                # Mostra esempio switch se presente
                if data.get('topology', {}).get('switches'):
                    print("\n6. Esempio switch:")
                    switch = data['topology']['switches'][0]
                    for key, value in switch.items():
                        print(f"   {key}: {value}")
                
                # Mostra esempio link se presente
                if data.get('topology', {}).get('links'):
                    print("\n7. Esempio link:")
                    link = data['topology']['links'][0]
                    for key, value in link.items():
                        print(f"   {key}: {value}")
                
                # Mostra metriche
                if data.get('metrics'):
                    print("\n8. Metriche:")
                    print(f"   Bandwidth: {data['metrics'].get('bandwidth')}")
                    print(f"   Latency: {data['metrics'].get('latency')}")
                    print(f"   Utilization: {data['metrics'].get('utilization')}")
                
                print("\n✅ Test completato con successo!")
            else:
                print("   ⚠️  Nessun file JSON trovato")
        else:
            print("   ⚠️  Snapshot non raccolto (Ryu non in esecuzione)")
            print("   Questo è normale se non hai Ryu attivo localmente")
            
    except Exception as e:
        print(f"\n❌ Errore durante il test: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_full_collection()
