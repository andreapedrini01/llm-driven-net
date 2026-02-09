#!/usr/bin/env python3
"""
Test rapido per la modalità raccolta continua
"""

import sys
import time
from pathlib import Path

# Aggiungi il path del modulo
sys.path.insert(0, str(Path(__file__).parent.parent))

from network_state_collector.collector import NetworkStateCollector


def test_continuous_mode():
    """Test modalità raccolta continua"""
    print("🔧 Test Modalità Raccolta Continua")
    print("=" * 50)
    
    try:
        # Crea collector
        print("\n1. Inizializzazione collector...")
        collector = NetworkStateCollector(environment="development")
        print("   ✓ Collector inizializzato")
        
        # Test avvio raccolta continua
        print("\n2. Avvio raccolta continua (intervallo 2s)...")
        collector.start_continuous_collection(interval=2.0)
        print("   ✓ Raccolta continua avviata")
        print(f"   ✓ Thread attivo: {collector._collection_thread.is_alive()}")
        print(f"   ✓ Raccolta in corso: {collector._is_collecting}")
        
        # Monitora per alcuni secondi
        print("\n3. Monitoraggio per 6 secondi...")
        for i in range(3):
            time.sleep(2)
            stats = collector.get_collection_stats()
            print(f"   📊 Secondo {(i+1)*2}: {stats['total_snapshots']} tentativi, "
                  f"{stats['successful_snapshots']} successi, "
                  f"{stats['failed_snapshots']} fallimenti")
        
        # Test stop raccolta
        print("\n4. Stop raccolta continua...")
        collector.stop_collection()
        print("   ✓ Raccolta fermata")
        print(f"   ✓ Thread attivo: {collector._collection_thread.is_alive()}")
        print(f"   ✓ Raccolta in corso: {collector._is_collecting}")
        
        # Statistiche finali
        final_stats = collector.get_collection_stats()
        print(f"\n5. Statistiche finali:")
        print(f"   ✓ Tentativi totali: {final_stats['total_snapshots']}")
        print(f"   ✓ Successi: {final_stats['successful_snapshots']}")
        print(f"   ✓ Fallimenti: {final_stats['failed_snapshots']}")
        
        print("\n✅ Test modalità continua completato con successo!")
        
    except Exception as e:
        print(f"\n❌ Errore durante il test: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_continuous_mode()