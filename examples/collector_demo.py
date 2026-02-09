#!/usr/bin/env python3
"""
Demo per NetworkStateCollector

Dimostra l'utilizzo della classe principale del sistema:
- Raccolta singola snapshot
- Raccolta continua
- Monitoraggio stato di salute
- Gestione configurazione
- Statistiche di raccolta
"""

import sys
import time
import signal
from pathlib import Path

# Aggiungi il path del modulo
sys.path.insert(0, str(Path(__file__).parent.parent))

from network_state_collector.collector import NetworkStateCollector
from network_state_collector.models.config import CollectorConfig


def demo_single_snapshot():
    """Demo raccolta singola snapshot"""
    print("=== Demo Raccolta Singola Snapshot ===")
    
    try:
        # Crea collector con configurazione development
        print("\n1. Inizializzazione NetworkStateCollector...")
        collector = NetworkStateCollector(environment="development")
        print("   ✓ Collector inizializzato")
        
        # Verifica stato di salute
        print("\n2. Verifica stato di salute...")
        health = collector.get_health_status()
        print(f"   ✓ Stato: {health.status}")
        print(f"   ✓ Componenti: {health.details}")
        
        # Raccoglie snapshot
        print("\n3. Raccolta snapshot...")
        snapshot = collector.collect_snapshot()
        
        if snapshot:
            print("   ✓ Snapshot raccolto con successo!")
            print(f"   ✓ Timestamp: {snapshot.timestamp}")
            print(f"   ✓ Switch: {len(snapshot.topology.switches)}")
            print(f"   ✓ Link: {len(snapshot.topology.links)}")
            print(f"   ✓ Metadata: {snapshot.metadata}")
        else:
            print("   ⚠ Nessuno snapshot raccolto (controller non disponibile?)")
        
        # Mostra statistiche
        print("\n4. Statistiche raccolta...")
        stats = collector.get_collection_stats()
        print(f"   ✓ Snapshot totali: {stats['total_snapshots']}")
        print(f"   ✓ Snapshot riusciti: {stats['successful_snapshots']}")
        print(f"   ✓ Snapshot falliti: {stats['failed_snapshots']}")
        print(f"   ✓ Tempo medio raccolta: {stats['average_collection_time']:.2f}s")
        
    except Exception as e:
        print(f"   ✗ Errore: {e}")


def demo_continuous_collection():
    """Demo raccolta continua"""
    print("\n=== Demo Raccolta Continua ===")
    
    try:
        # Crea collector
        print("\n1. Inizializzazione collector per raccolta continua...")
        collector = NetworkStateCollector(environment="development")
        
        # Configura handler per interruzione
        def signal_handler(signum, frame):
            print("\n   Interruzione ricevuta, fermando raccolta...")
            collector.stop_collection()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        
        # Avvia raccolta continua
        print("\n2. Avvio raccolta continua (intervallo 5s)...")
        print("   (Premi Ctrl+C per fermare)")
        
        collector.start_continuous_collection(interval=5.0)
        
        # Monitora per 30 secondi
        start_time = time.time()
        while time.time() - start_time < 30:
            time.sleep(2)
            
            # Mostra statistiche periodicamente
            stats = collector.get_collection_stats()
            health = collector.get_health_status()
            
            print(f"\n   📊 Statistiche (t={time.time() - start_time:.0f}s):")
            print(f"      - Snapshot: {stats['successful_snapshots']}/{stats['total_snapshots']}")
            print(f"      - Stato: {health.status}")
            print(f"      - Raccolta attiva: {stats['is_collecting']}")
            
            # Ricarica configurazione se modificata
            if collector.reload_configuration():
                print("      - Configurazione ricaricata!")
        
        # Ferma raccolta
        print("\n3. Fermata raccolta continua...")
        collector.stop_collection()
        
        # Statistiche finali
        final_stats = collector.get_collection_stats()
        print(f"\n4. Statistiche finali:")
        print(f"   ✓ Snapshot totali: {final_stats['total_snapshots']}")
        print(f"   ✓ Snapshot riusciti: {final_stats['successful_snapshots']}")
        print(f"   ✓ Snapshot falliti: {final_stats['failed_snapshots']}")
        print(f"   ✓ Tempo medio: {final_stats['average_collection_time']:.2f}s")
        
    except KeyboardInterrupt:
        print("\n   Raccolta interrotta dall'utente")
        if 'collector' in locals():
            collector.stop_collection()
    except Exception as e:
        print(f"   ✗ Errore: {e}")


def demo_health_monitoring():
    """Demo monitoraggio stato di salute"""
    print("\n=== Demo Monitoraggio Stato di Salute ===")
    
    try:
        collector = NetworkStateCollector(environment="development")
        
        print("\n1. Monitoraggio stato componenti...")
        
        for i in range(5):
            health = collector.get_health_status()
            
            print(f"\n   Check #{i+1}:")
            print(f"   ✓ Stato generale: {health.status}")
            print(f"   ✓ Timestamp: {health.timestamp}")
            
            details = health.details
            print(f"   ✓ Ryu Connector: {details.get('ryu_connector', 'unknown')}")
            print(f"   ✓ Filesystem: {details.get('filesystem', 'unknown')}")
            print(f"   ✓ Raccolta attiva: {details.get('is_collecting', False)}")
            
            if details.get('last_snapshot_age'):
                print(f"   ✓ Età ultimo snapshot: {details['last_snapshot_age']:.1f}s")
            
            time.sleep(2)
        
    except Exception as e:
        print(f"   ✗ Errore: {e}")


def demo_configuration_management():
    """Demo gestione configurazione"""
    print("\n=== Demo Gestione Configurazione ===")
    
    try:
        print("\n1. Caricamento configurazioni diverse...")
        
        # Test configurazione development
        print("\n   Development:")
        collector_dev = NetworkStateCollector(environment="development")
        config_dev = collector_dev.config
        print(f"   ✓ Environment: {config_dev.environment}")
        print(f"   ✓ Log level: {config_dev.logging.level}")
        print(f"   ✓ Continuous mode: {config_dev.collection.continuous_mode}")
        print(f"   ✓ Interval: {config_dev.collection.interval}s")
        
        # Test configurazione production
        print("\n   Production:")
        try:
            collector_prod = NetworkStateCollector(environment="production")
            config_prod = collector_prod.config
            print(f"   ✓ Environment: {config_prod.environment}")
            print(f"   ✓ Log level: {config_prod.logging.level}")
            print(f"   ✓ Continuous mode: {config_prod.collection.continuous_mode}")
            print(f"   ✓ Interval: {config_prod.collection.interval}s")
        except Exception as e:
            print(f"   ⚠ Configurazione production non disponibile: {e}")
        
        # Test ricaricamento configurazione
        print("\n2. Test ricaricamento configurazione...")
        reloaded = collector_dev.reload_configuration()
        print(f"   ✓ Configurazione ricaricata: {reloaded}")
        
    except Exception as e:
        print(f"   ✗ Errore: {e}")


def demo_context_manager():
    """Demo utilizzo come context manager"""
    print("\n=== Demo Context Manager ===")
    
    try:
        print("\n1. Utilizzo con context manager...")
        
        with NetworkStateCollector(environment="development") as collector:
            print("   ✓ Collector inizializzato nel context")
            
            # Raccoglie alcuni snapshot
            for i in range(3):
                print(f"   📸 Raccolta snapshot #{i+1}...")
                snapshot = collector.collect_snapshot()
                if snapshot:
                    print(f"      ✓ Snapshot raccolto (timestamp: {snapshot.timestamp})")
                else:
                    print("      ⚠ Snapshot non raccolto")
                time.sleep(1)
            
            # Mostra statistiche
            stats = collector.get_collection_stats()
            print(f"\n   📊 Statistiche finali:")
            print(f"      - Totali: {stats['total_snapshots']}")
            print(f"      - Riusciti: {stats['successful_snapshots']}")
            print(f"      - Falliti: {stats['failed_snapshots']}")
        
        print("   ✓ Context manager completato (cleanup automatico)")
        
    except Exception as e:
        print(f"   ✗ Errore: {e}")


def demo_error_handling():
    """Demo gestione errori"""
    print("\n=== Demo Gestione Errori ===")
    
    try:
        # Crea collector con configurazione che potrebbe causare errori
        print("\n1. Test resilienza agli errori...")
        
        collector = NetworkStateCollector(environment="development")
        
        # Simula raccolta con possibili errori
        print("\n2. Raccolta con gestione errori...")
        
        for i in range(5):
            print(f"\n   Tentativo #{i+1}:")
            
            try:
                snapshot = collector.collect_snapshot()
                if snapshot:
                    print("   ✓ Snapshot raccolto con successo")
                else:
                    print("   ⚠ Snapshot non raccolto (normale se controller non disponibile)")
                
            except Exception as e:
                print(f"   ✗ Errore durante raccolta: {e}")
            
            # Mostra statistiche correnti
            stats = collector.get_collection_stats()
            success_rate = (stats['successful_snapshots'] / max(stats['total_snapshots'], 1)) * 100
            print(f"   📊 Tasso successo: {success_rate:.1f}%")
            
            time.sleep(1)
        
        # Statistiche finali
        final_stats = collector.get_collection_stats()
        print(f"\n3. Statistiche finali gestione errori:")
        print(f"   ✓ Snapshot totali: {final_stats['total_snapshots']}")
        print(f"   ✓ Snapshot riusciti: {final_stats['successful_snapshots']}")
        print(f"   ✗ Snapshot falliti: {final_stats['failed_snapshots']}")
        
        if final_stats['total_snapshots'] > 0:
            success_rate = (final_stats['successful_snapshots'] / final_stats['total_snapshots']) * 100
            print(f"   📊 Tasso successo finale: {success_rate:.1f}%")
        
    except Exception as e:
        print(f"   ✗ Errore: {e}")


def main():
    """Esegue tutte le demo"""
    print("🔧 Demo NetworkStateCollector - Network State Collector")
    print("=" * 60)
    
    try:
        demo_single_snapshot()
        demo_health_monitoring()
        demo_configuration_management()
        demo_context_manager()
        demo_error_handling()
        
        print("\n" + "=" * 60)
        print("✅ Tutte le demo completate!")
        print("\nPer testare la raccolta continua, esegui:")
        print("python examples/collector_demo.py --continuous")
        
    except Exception as e:
        print(f"\n❌ Errore durante l'esecuzione delle demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--continuous":
        demo_continuous_collection()
    else:
        main()