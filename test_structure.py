#!/usr/bin/env python3
"""
Test della nuova struttura del progetto

Verifica che la riorganizzazione con src/models/ funzioni correttamente.
"""

import sys
import os

# Aggiungi la root del progetto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test degli import dalla nuova struttura"""
    print("="*70)
    print("TEST STRUTTURA PROGETTO")
    print("="*70)
    print()
    
    try:
        # Test 1: Import modelli core
        from src.models.core import NetworkSnapshot, TopologyData, MetricsData, SwitchInfo, LinkInfo, PortMetrics
        print("✓ Test 1: Import src.models.core OK")
        
        # Test 2: Import modelli health
        from src.models.health import HealthStatus, ComponentType, HealthCheck
        print("✓ Test 2: Import src.models.health OK")
        
        # Test 3: Import modelli LLM
        from src.models.llm import LLMNetworkData, AnomalyIndicator
        print("✓ Test 3: Import src.models.llm OK")
        
        # Test 4: Import config (richiede PyYAML)
        try:
            from src.models.config import CollectorConfig, RyuConfig
            print("✓ Test 4: Import src.models.config OK")
        except ImportError as e:
            print(f"⚠ Test 4: Import src.models.config SKIP (manca PyYAML)")
            print(f"   Installa con: pip3 install pyyaml")
        
        # Test 5: Import da network_state_collector
        from network_state_collector import NetworkStateCollector
        print("✓ Test 5: Import network_state_collector OK")
        
        # Test 6: Creazione oggetti
        switch = SwitchInfo(dpid='0000000000000001', ports=[1, 2, 3], active=True)
        assert switch.dpid == '0000000000000001'
        print(f"✓ Test 6: Creazione SwitchInfo OK - DPID: {switch.dpid}")
        
        link = LinkInfo(
            src_dpid='0000000000000001',
            dst_dpid='0000000000000002',
            src_port=1,
            dst_port=1,
            active=True
        )
        assert link.src_dpid == '0000000000000001'
        assert link.dst_dpid == '0000000000000002'
        print(f"✓ Test 7: Creazione LinkInfo OK")
        
        port_metrics = PortMetrics(
            port_no=1,
            rx_packets=1000,
            tx_packets=2000,
            rx_bytes=50000,
            tx_bytes=100000,
            rx_errors=0,
            tx_errors=0,
            rx_dropped=0,
            tx_dropped=0
        )
        assert port_metrics.port_no == 1
        print(f"✓ Test 8: Creazione PortMetrics OK")
        
        print()
        print("="*70)
        print("✅ TUTTI I TEST PASSATI!")
        print("="*70)
        print()
        print("Struttura finale:")
        print("  ├── src/")
        print("  │   └── models/      (config.py, core.py, health.py, llm.py)")
        print("  ├── network_state_collector/")
        print("  │   ├── __init__.py  (API pubbliche)")
        print("  │   ├── main.py      (CLI)")
        print("  │   └── *.py         (servizi)")
        print("  ├── tests/")
        print("  └── examples/")
        print()
        
        return True
        
    except Exception as e:
        print()
        print("="*70)
        print("❌ TEST FALLITO!")
        print("="*70)
        print(f"Errore: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
