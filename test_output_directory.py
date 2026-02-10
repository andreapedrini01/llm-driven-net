#!/usr/bin/env python3
"""
Test per verificare che i JSON vengano salvati in data/history
"""

import sys
import os
from pathlib import Path

# Aggiungi il path del modulo
sys.path.insert(0, str(Path(__file__).parent))

from network_state_collector.collector import NetworkStateCollector


def test_output_directory():
    """Test per verificare la directory di output"""
    print("🧪 Test Directory Output JSON")
    print("=" * 50)
    
    # Pulisci directory di test se esiste
    test_history_dir = Path("data/history")
    if test_history_dir.exists():
        print(f"\n📁 Directory data/history esiste")
        existing_files = list(test_history_dir.glob("*.json"))
        print(f"   File esistenti: {len(existing_files)}")
    else:
        print(f"\n📁 Directory data/history non esiste ancora")
    
    try:
        # Crea collector
        print("\n1. Inizializzazione collector...")
        collector = NetworkStateCollector(environment="development")
        print("   ✓ Collector inizializzato")
        
        # Verifica configurazione
        print(f"\n2. Configurazione filesystem:")
        print(f"   Base dir: {collector.filesystem_manager.config.base_output_dir}")
        print(f"   LLM output dir: {collector.filesystem_manager.config.llm_output_dir}")
        print(f"   History dir: {collector.filesystem_manager.config.history_dir}")
        
        # Verifica path effettivi
        llm_path = collector.filesystem_manager._get_llm_output_path()
        history_path = collector.filesystem_manager._get_history_path()
        print(f"\n3. Path effettivi:")
        print(f"   LLM output path: {llm_path}")
        print(f"   History path: {history_path}")
        print(f"   Sono uguali? {llm_path == history_path}")
        
        # Prova a raccogliere uno snapshot
        print(f"\n4. Tentativo raccolta snapshot...")
        snapshot = collector.collect_snapshot()
        
        if snapshot:
            print("   ✓ Snapshot raccolto con successo")
            
            # Verifica dove sono stati salvati i file
            print(f"\n5. Verifica file salvati:")
            
            # Lista file in data/history
            history_files = list(test_history_dir.glob("*.json"))
            print(f"   File in data/history: {len(history_files)}")
            for f in sorted(history_files)[-3:]:  # Mostra ultimi 3
                print(f"     - {f.name} ({f.stat().st_size} bytes)")
            
            # Verifica se esiste data/llm_output
            llm_output_dir = Path("data/llm_output")
            if llm_output_dir.exists():
                llm_files = list(llm_output_dir.glob("*.json"))
                print(f"   ⚠️  File in data/llm_output: {len(llm_files)} (dovrebbe essere 0!)")
            else:
                print(f"   ✓ Directory data/llm_output non esiste (corretto!)")
            
            print("\n✅ Test completato!")
            print(f"\n📊 Risultato: I JSON vengono salvati in {llm_path}")
            
        else:
            print("   ⚠️  Snapshot non raccolto (probabilmente Ryu non è in esecuzione)")
            print("   Questo è normale se non hai Ryu attivo localmente")
            
    except Exception as e:
        print(f"\n❌ Errore durante il test: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_output_directory()
