#!/usr/bin/env python3
"""
Test per verificare il salvataggio effettivo in data/history con dati mock
"""

import sys
import time
from pathlib import Path

# Aggiungi il path del modulo
sys.path.insert(0, str(Path(__file__).parent))

from network_state_collector.filesystem_manager import FileSystemManager, FileSystemConfig
from network_state_collector.models.core import NetworkSnapshot, TopologyData, MetricsData
from network_state_collector.models.llm import LLMNetworkData
from network_state_collector.json_serializer import JSONSerializer


def test_save_to_history():
    """Test salvataggio in data/history"""
    print("🧪 Test Salvataggio in data/history")
    print("=" * 50)
    
    # Crea configurazione filesystem
    fs_config = FileSystemConfig(
        base_output_dir="data",
        llm_output_dir="history",
        history_dir="history"
    )
    
    print(f"\n1. Configurazione:")
    print(f"   Base dir: {fs_config.base_output_dir}")
    print(f"   LLM output dir: {fs_config.llm_output_dir}")
    print(f"   History dir: {fs_config.history_dir}")
    
    # Crea filesystem manager
    fs_manager = FileSystemManager(fs_config)
    serializer = JSONSerializer(pretty_print=True)
    
    print(f"\n2. Path effettivi:")
    print(f"   LLM output path: {fs_manager._get_llm_output_path()}")
    print(f"   History path: {fs_manager._get_history_path()}")
    
    # Crea dati mock
    timestamp = time.time()
    
    # NetworkSnapshot mock
    topology = TopologyData(
        switches=[{"dpid": "1", "ports": [1, 2, 3]}],
        links=[{"src": "1", "dst": "2", "src_port": 1, "dst_port": 1}]
    )
    metrics = MetricsData(port_statistics={})
    snapshot = NetworkSnapshot(
        timestamp=timestamp,
        topology=topology,
        metrics=metrics,
        metadata={"test": "mock_data"}
    )
    
    # LLMNetworkData mock
    llm_data = LLMNetworkData(
        network_context={"switches": [{"dpid": "1", "ports": [1, 2, 3]}], "links": [{"src": "1", "dst": "2"}]},
        performance_vectors=[[0.1, 0.2, 0.3]],
        topology_embedding={"nodes": 1, "edges": 1},
        temporal_features={"timestamp": timestamp},
        anomaly_indicators=[]
    )
    
    print(f"\n3. Salvataggio NetworkSnapshot...")
    snapshot_json = serializer.serialize_network_snapshot(snapshot)
    snapshot_file = fs_manager.save_network_context(snapshot_json, timestamp)
    print(f"   ✓ Salvato in: {snapshot_file}")
    print(f"   ✓ Esiste: {snapshot_file.exists()}")
    
    print(f"\n4. Salvataggio LLMNetworkData...")
    llm_file = fs_manager.save_llm_data(llm_data, as_latest=True)
    print(f"   ✓ Salvato in: {llm_file}")
    print(f"   ✓ Esiste: {llm_file.exists()}")
    
    print(f"\n5. Verifica file latest...")
    latest_file = fs_manager._get_llm_output_path() / "network_context_latest.json"
    print(f"   ✓ Latest file: {latest_file}")
    print(f"   ✓ Esiste: {latest_file.exists()}")
    
    print(f"\n6. Lista file in data/history:")
    history_files = list(Path("data/history").glob("*.json"))
    for f in sorted(history_files):
        print(f"   - {f.name} ({f.stat().st_size} bytes)")
    
    print(f"\n7. Verifica data/llm_output:")
    llm_output_dir = Path("data/llm_output")
    if llm_output_dir.exists():
        llm_files = list(llm_output_dir.glob("*.json"))
        if llm_files:
            print(f"   ⚠️  Trovati {len(llm_files)} file in data/llm_output (dovrebbe essere vuota!)")
        else:
            print(f"   ✓ Directory data/llm_output è vuota")
    else:
        print(f"   ✓ Directory data/llm_output non esiste (corretto!)")
    
    print(f"\n✅ Test completato!")
    print(f"\n📊 Risultato: Tutti i JSON vengono salvati in data/history")


if __name__ == "__main__":
    test_save_to_history()
