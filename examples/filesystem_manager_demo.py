#!/usr/bin/env python3
"""
Demo per FileSystemManager

Dimostra le funzionalità di gestione file system, directory configurabili
e storico dati per il Network State Collector.
"""

import sys
import os
import tempfile
import time
from pathlib import Path
from datetime import datetime, timedelta

# Aggiungi il path del modulo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from network_state_collector.filesystem_manager import FileSystemManager, FileSystemConfig
from src.models.core import (
    NetworkSnapshot, TopologyData, MetricsData, SwitchInfo, LinkInfo, PortMetrics
)
from src.models.llm import LLMNetworkData, AnomalyIndicator


def create_sample_network_snapshot(timestamp: float = None) -> NetworkSnapshot:
    """Crea un NetworkSnapshot di esempio"""
    if timestamp is None:
        timestamp = datetime.now().timestamp()
    
    switches = [
        SwitchInfo(dpid="0000000000000001", active=True, ports=[1, 2, 3]),
        SwitchInfo(dpid="0000000000000002", active=True, ports=[1, 2, 3]),
        SwitchInfo(dpid="0000000000000003", active=True, ports=[1, 2])
    ]
    
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
    
    topology = TopologyData(
        switches=switches,
        links=links,
        graph_representation={
            "nodes": len(switches),
            "edges": len(links),
            "density": 0.33
        }
    )
    
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
            )
        ]
    }
    
    metrics = MetricsData(
        port_statistics=port_stats,
        aggregated_metrics={},
        quality_indicators=None
    )
    
    return NetworkSnapshot(
        timestamp=timestamp,
        topology=topology,
        metrics=metrics,
        derived_metrics=None,
        metadata={
            "version": "1.0",
            "collector": "demo",
            "environment": "test"
        }
    )


def create_sample_llm_data(timestamp: float = None) -> LLMNetworkData:
    """Crea LLMNetworkData di esempio"""
    if timestamp is None:
        timestamp = datetime.now().timestamp()
    
    return LLMNetworkData(
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
                "congestion_indicators": [False, False, False]
            },
            "metadata": {
                "timestamp": timestamp,
                "collection_time": datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            }
        },
        performance_vectors=[
            [15.0, 0.0003, 1.44],  # Switch 1, Port 1
            [12.0, 0.0001, 1.12],  # Switch 1, Port 2
            [8.0, 0.0001, 0.88]    # Switch 2, Port 1
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
            "timestamp": timestamp,
            "hour_of_day": datetime.fromtimestamp(timestamp).hour,
            "day_of_week": datetime.fromtimestamp(timestamp).weekday(),
            "is_weekend": datetime.fromtimestamp(timestamp).weekday() >= 5,
            "is_business_hours": 9 <= datetime.fromtimestamp(timestamp).hour <= 17
        },
        anomaly_indicators=[
            AnomalyIndicator(
                type="high_utilization",
                severity=0.15,
                description="Moderate utilization on port 1: 15.0%",
                affected_components=["0000000000000001:1"],
                timestamp=timestamp,
                confidence=0.85
            )
        ]
    )


def demo_basic_operations():
    """Dimostra operazioni base del FileSystemManager"""
    print("\n" + "="*60)
    print("📁 DEMO: Operazioni Base FileSystemManager")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Configura FileSystemManager
        config = FileSystemConfig(
            base_output_dir=temp_dir,
            max_history_files=10,
            max_file_age_days=7
        )
        fs_manager = FileSystemManager(config)
        
        print(f"📂 Directory base: {temp_dir}")
        print(f"📊 Max file history: {config.max_history_files}")
        print(f"📅 Max file age: {config.max_file_age_days} giorni")
        
        # Crea dati di esempio
        snapshot = create_sample_network_snapshot()
        llm_data = create_sample_llm_data()
        
        print("\n💾 Salvataggio NetworkSnapshot...")
        snapshot_path = fs_manager.save_network_snapshot(snapshot)
        print(f"✅ Salvato in: {snapshot_path.name}")
        print(f"📏 Dimensione: {snapshot_path.stat().st_size} bytes")
        
        print("\n💾 Salvataggio LLMNetworkData...")
        llm_path = fs_manager.save_llm_data(llm_data)
        print(f"✅ Salvato in: {llm_path.name}")
        print(f"📏 Dimensione: {llm_path.stat().st_size} bytes")
        
        # Verifica file latest
        latest_path = fs_manager._get_llm_output_path() / "network_context_latest.json"
        if latest_path.exists():
            print(f"✅ File latest creato: {latest_path.stat().st_size} bytes")
        
        print("\n📂 Caricamento dati...")
        loaded_snapshot = fs_manager.load_network_snapshot(snapshot_path.name)
        loaded_llm = fs_manager.load_llm_data()  # Carica latest
        
        print(f"✅ NetworkSnapshot caricato: timestamp={loaded_snapshot.timestamp}")
        print(f"✅ LLMNetworkData caricato: {len(loaded_llm.performance_vectors)} vettori performance")


def demo_file_listing():
    """Dimostra listing e gestione file"""
    print("\n" + "="*60)
    print("📋 DEMO: Listing e Gestione File")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = FileSystemConfig(base_output_dir=temp_dir)
        fs_manager = FileSystemManager(config)
        
        # Crea diversi file con timestamp diversi
        print("📝 Creando file di esempio...")
        base_time = datetime.now().timestamp()
        
        for i in range(5):
            timestamp = base_time - (i * 3600)  # Ogni ora indietro
            snapshot = create_sample_network_snapshot(timestamp)
            llm_data = create_sample_llm_data(timestamp)
            
            fs_manager.save_network_snapshot(snapshot)
            fs_manager.save_llm_data(llm_data, as_latest=(i == 0))
        
        print(f"✅ Creati 5 file di ogni tipo")
        
        # Lista file history
        print("\n📋 File di history:")
        history_files = fs_manager.list_history_files()
        for i, file_path in enumerate(history_files):
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            size = file_path.stat().st_size
            print(f"  {i+1}. {file_path.name} ({size} bytes, {mtime.strftime('%H:%M:%S')})")
        
        # Lista file LLM
        print("\n📋 File LLM:")
        llm_files = fs_manager.list_llm_files()
        for i, file_path in enumerate(llm_files):
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            size = file_path.stat().st_size
            is_latest = "latest" in file_path.name
            marker = "🔥" if is_latest else "  "
            print(f"{marker}{i+1}. {file_path.name} ({size} bytes, {mtime.strftime('%H:%M:%S')})")
        
        # Lista con limite
        print("\n📋 Ultimi 3 file history:")
        recent_files = fs_manager.list_history_files(limit=3)
        for i, file_path in enumerate(recent_files):
            print(f"  {i+1}. {file_path.name}")


def demo_storage_stats():
    """Dimostra statistiche storage"""
    print("\n" + "="*60)
    print("📊 DEMO: Statistiche Storage")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = FileSystemConfig(base_output_dir=temp_dir)
        fs_manager = FileSystemManager(config)
        
        # Crea diversi file
        print("📝 Creando file per statistiche...")
        for i in range(8):
            snapshot = create_sample_network_snapshot()
            llm_data = create_sample_llm_data()
            
            fs_manager.save_network_snapshot(snapshot)
            fs_manager.save_llm_data(llm_data)
        
        # Ottieni statistiche
        stats = fs_manager.get_storage_stats()
        
        print(f"\n📊 Statistiche Storage:")
        print(f"📂 Directory base: {stats['base_dir']}")
        print(f"📁 File totali: {stats['total_files']}")
        print(f"💾 Dimensione totale: {stats['total_size_mb']:.2f} MB")
        print(f"💿 Dimensione totale: {stats['total_size_gb']:.4f} GB")
        
        print(f"\n📋 Dettaglio per directory:")
        for dir_name, dir_stats in stats['directories'].items():
            if dir_stats['file_count'] > 0:
                print(f"  📁 {dir_name}:")
                print(f"    📄 File: {dir_stats['file_count']}")
                print(f"    💾 Dimensione: {dir_stats['total_size'] / 1024:.1f} KB")
                
                if dir_stats['latest_file']:
                    latest_time = datetime.fromtimestamp(dir_stats['latest_file']['mtime'])
                    print(f"    🔥 Più recente: {dir_stats['latest_file']['name']} ({latest_time.strftime('%H:%M:%S')})")
                
                if dir_stats['oldest_file']:
                    oldest_time = datetime.fromtimestamp(dir_stats['oldest_file']['mtime'])
                    print(f"    📜 Più vecchio: {dir_stats['oldest_file']['name']} ({oldest_time.strftime('%H:%M:%S')})")


def demo_cleanup_operations():
    """Dimostra operazioni di pulizia"""
    print("\n" + "="*60)
    print("🧹 DEMO: Operazioni di Pulizia")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = FileSystemConfig(
            base_output_dir=temp_dir,
            max_history_files=3,  # Limite basso per demo
            max_file_age_days=1   # 1 giorno per demo
        )
        fs_manager = FileSystemManager(config)
        
        print(f"⚙️  Configurazione pulizia:")
        print(f"   📊 Max file history: {config.max_history_files}")
        print(f"   📅 Max età file: {config.max_file_age_days} giorni")
        
        # Crea file "vecchi"
        print("\n📝 Creando file vecchi...")
        old_time = datetime.now() - timedelta(days=2)
        
        for i in range(5):
            timestamp = old_time.timestamp() - (i * 3600)
            snapshot = create_sample_network_snapshot(timestamp)
            llm_data = create_sample_llm_data(timestamp)
            
            # Salva i file
            snapshot_path = fs_manager.save_network_snapshot(snapshot)
            llm_path = fs_manager.save_llm_data(llm_data, as_latest=False)
            
            # Modifica timestamp per simulare file vecchi
            old_timestamp = old_time.timestamp()
            os.utime(snapshot_path, (old_timestamp, old_timestamp))
            os.utime(llm_path, (old_timestamp, old_timestamp))
        
        print(f"✅ Creati 5 file vecchi di ogni tipo")
        
        # Statistiche prima della pulizia
        stats_before = fs_manager.get_storage_stats()
        print(f"\n📊 Prima della pulizia:")
        print(f"   📁 File totali: {stats_before['total_files']}")
        print(f"   💾 Dimensione: {stats_before['total_size_mb']:.2f} MB")
        
        # Dry run cleanup
        print(f"\n🔍 Simulazione pulizia (dry run)...")
        dry_stats = fs_manager.cleanup_old_files(dry_run=True)
        print(f"   🗑️  File da rimuovere: {dry_stats['files_removed']}")
        print(f"   📦 File da archiviare: {dry_stats['files_archived']}")
        print(f"   💾 Spazio da liberare: {dry_stats['bytes_freed'] / 1024:.1f} KB")
        print(f"   ❌ Errori: {dry_stats['errors']}")
        
        # Cleanup effettivo
        print(f"\n🧹 Pulizia effettiva...")
        cleanup_stats = fs_manager.cleanup_old_files(dry_run=False)
        print(f"   ✅ File rimossi: {cleanup_stats['files_removed']}")
        print(f"   📦 File archiviati: {cleanup_stats['files_archived']}")
        print(f"   💾 Spazio liberato: {cleanup_stats['bytes_freed'] / 1024:.1f} KB")
        print(f"   ❌ Errori: {cleanup_stats['errors']}")
        
        # Statistiche dopo la pulizia
        stats_after = fs_manager.get_storage_stats()
        print(f"\n📊 Dopo la pulizia:")
        print(f"   📁 File totali: {stats_after['total_files']}")
        print(f"   💾 Dimensione: {stats_after['total_size_mb']:.2f} MB")
        print(f"   📉 Riduzione: {stats_before['total_files'] - stats_after['total_files']} file")


def demo_backup_operations():
    """Dimostra operazioni di backup"""
    print("\n" + "="*60)
    print("💼 DEMO: Operazioni di Backup")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = FileSystemConfig(base_output_dir=temp_dir)
        fs_manager = FileSystemManager(config)
        
        # Crea alcuni file
        print("📝 Creando dati per backup...")
        for i in range(3):
            snapshot = create_sample_network_snapshot()
            llm_data = create_sample_llm_data()
            
            fs_manager.save_network_snapshot(snapshot)
            fs_manager.save_llm_data(llm_data)
        
        print("✅ Creati 3 file di ogni tipo")
        
        # Statistiche prima del backup
        stats = fs_manager.get_storage_stats()
        print(f"\n📊 Dati da backuppare:")
        print(f"   📁 File totali: {stats['total_files']}")
        print(f"   💾 Dimensione: {stats['total_size_mb']:.2f} MB")
        
        # Crea backup con nome personalizzato
        print(f"\n💼 Creando backup personalizzato...")
        backup_path = fs_manager.create_backup("demo_backup")
        print(f"✅ Backup creato in: {backup_path.name}")
        
        # Verifica contenuto backup
        backup_files = list(backup_path.rglob("*.json"))
        backup_size = sum(f.stat().st_size for f in backup_files)
        
        print(f"📋 Contenuto backup:")
        print(f"   📁 File nel backup: {len(backup_files)}")
        print(f"   💾 Dimensione backup: {backup_size / 1024:.1f} KB")
        
        # Verifica directory nel backup
        backup_dirs = [d for d in backup_path.iterdir() if d.is_dir()]
        print(f"   📂 Directory: {[d.name for d in backup_dirs]}")
        
        # Verifica metadata
        metadata_path = backup_path / "backup_metadata.json"
        if metadata_path.exists():
            print(f"   📄 Metadata: {metadata_path.stat().st_size} bytes")
            
            import json
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            created_at = datetime.fromisoformat(metadata['created_at'])
            print(f"   🕐 Creato: {created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Crea backup con nome automatico
        print(f"\n💼 Creando backup automatico...")
        auto_backup_path = fs_manager.create_backup()
        print(f"✅ Backup automatico: {auto_backup_path.name}")


def demo_advanced_features():
    """Dimostra funzionalità avanzate"""
    print("\n" + "="*60)
    print("🚀 DEMO: Funzionalità Avanzate")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Configurazione avanzata
        config = FileSystemConfig(
            base_output_dir=temp_dir,
            llm_output_dir="custom_llm",
            history_dir="custom_history",
            archive_dir="custom_archive",
            max_history_files=5,
            enable_compression=True,  # Abilita archiviazione
            file_permissions=0o600,   # Permessi restrittivi
            dir_permissions=0o700
        )
        
        fs_manager = FileSystemManager(config)
        
        print(f"⚙️  Configurazione avanzata:")
        print(f"   📂 Directory LLM: {config.llm_output_dir}")
        print(f"   📂 Directory history: {config.history_dir}")
        print(f"   📂 Directory archive: {config.archive_dir}")
        print(f"   🗜️  Compressione: {'Abilitata' if config.enable_compression else 'Disabilitata'}")
        print(f"   🔒 Permessi file: {oct(config.file_permissions)}")
        print(f"   🔒 Permessi directory: {oct(config.dir_permissions)}")
        
        # Crea file con nomi personalizzati
        print(f"\n📝 Salvataggio con nomi personalizzati...")
        snapshot = create_sample_network_snapshot()
        llm_data = create_sample_llm_data()
        
        custom_snapshot_path = fs_manager.save_network_snapshot(
            snapshot, 
            filename="custom_network_snapshot.json"
        )
        custom_llm_path = fs_manager.save_llm_data(
            llm_data, 
            filename="custom_llm_data.json",
            as_latest=False
        )
        
        print(f"✅ Snapshot personalizzato: {custom_snapshot_path.name}")
        print(f"✅ LLM personalizzato: {custom_llm_path.name}")
        
        # Verifica permessi file
        snapshot_perms = oct(custom_snapshot_path.stat().st_mode)[-3:]
        llm_perms = oct(custom_llm_path.stat().st_mode)[-3:]
        print(f"🔒 Permessi snapshot: {snapshot_perms}")
        print(f"🔒 Permessi LLM: {llm_perms}")
        
        # Test ricerca file
        print(f"\n🔍 Test ricerca file...")
        found_snapshot = fs_manager._find_file("custom_network_snapshot.json")
        found_llm = fs_manager._find_file("custom_llm_data.json")
        found_missing = fs_manager._find_file("missing_file.json")
        
        print(f"✅ Snapshot trovato: {'Sì' if found_snapshot else 'No'}")
        print(f"✅ LLM trovato: {'Sì' if found_llm else 'No'}")
        print(f"❌ File mancante: {'Sì' if found_missing else 'No'}")
        
        # Test archiviazione
        print(f"\n📦 Test archiviazione...")
        old_file = fs_manager._get_history_path() / "old_test_file.json"
        old_file.write_text('{"test": "archive"}')
        
        print(f"📄 File creato: {old_file.name}")
        fs_manager._archive_file(old_file)
        
        archived_file = fs_manager._get_archive_path() / "old_test_file.json"
        print(f"📦 File archiviato: {'Sì' if archived_file.exists() else 'No'}")
        print(f"🗑️  File originale rimosso: {'Sì' if not old_file.exists() else 'No'}")


def main():
    """Funzione principale del demo"""
    print("🚀 FileSystemManager Demo")
    print("=" * 60)
    print("Dimostra le funzionalità del FileSystemManager per il Network State Collector")
    
    try:
        # Esegui tutti i demo
        demo_basic_operations()
        demo_file_listing()
        demo_storage_stats()
        demo_cleanup_operations()
        demo_backup_operations()
        demo_advanced_features()
        
        print("\n" + "="*60)
        print("🎉 Demo completato con successo!")
        print("="*60)
        print("\n📋 Funzionalità dimostrate:")
        print("  ✅ Salvataggio e caricamento NetworkSnapshot e LLMNetworkData")
        print("  ✅ Gestione directory configurabili")
        print("  ✅ Nomi file consistenti per integrazione LLM")
        print("  ✅ Listing e gestione file con ordinamento temporale")
        print("  ✅ Statistiche dettagliate di utilizzo storage")
        print("  ✅ Pulizia automatica file vecchi con dry-run")
        print("  ✅ Sistema di backup completo con metadata")
        print("  ✅ Archiviazione file con compressione opzionale")
        print("  ✅ Gestione permessi file e directory")
        print("  ✅ Ricerca file in multiple directory")
        print("\n🔧 Il FileSystemManager è pronto per l'integrazione!")
        
    except Exception as e:
        print(f"\n❌ Errore durante il demo: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())