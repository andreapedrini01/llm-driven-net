#!/usr/bin/env python3
"""
Test semplice degli import senza dipendenze esterne
"""

import sys
import os

# Aggiungi la root del progetto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_basic_imports():
    """Test degli import base senza PyYAML"""
    print("="*70)
    print("TEST IMPORT STRUTTURA PROGETTO (senza dipendenze)")
    print("="*70)
    print()
    
    try:
        # Test 1: Import modelli core (non richiede yaml)
        print("Test 1: Import src.models.core...")
        from src.models.core import (
            NetworkSnapshot, TopologyData, MetricsData, 
            SwitchInfo, LinkInfo, PortMetrics
        )
        print("✓ Import src.models.core OK")
        
        # Test 2: Import modelli health
        print("\nTest 2: Import src.models.health...")
        from src.models.health import HealthStatus, ComponentType, HealthCheck
        print("✓ Import src.models.health OK")
        
        # Test 3: Import modelli LLM
        print("\nTest 3: Import src.models.llm...")
        from src.models.llm import LLMNetworkData, AnomalyIndicator
        print("✓ Import src.models.llm OK")
        
        # Test 4: Creazione oggetti
        print("\nTest 4: Creazione oggetti...")
        switch = SwitchInfo(dpid='0000000000000001', ports=[1, 2, 3], active=True)
        assert switch.dpid == '0000000000000001'
        print(f"✓ SwitchInfo creato - DPID: {switch.dpid}")
        
        link = LinkInfo(
            src_dpid='0000000000000001',
            dst_dpid='0000000000000002',
            src_port=1,
            dst_port=1,
            active=True
        )
        assert link.src_dpid == '0000000000000001'
        assert link.dst_dpid == '0000000000000002'
        print(f"✓ LinkInfo creato - {link.src_dpid} -> {link.dst_dpid}")
        
        port_metrics = PortMetrics(
            port_no=1,
            rx_packets=1000,
            tx_packets=2000,
            rx_bytes=50000,
            tx_bytes=100000,
            rx_errors=0,
            tx_errors=0
        )
        assert port_metrics.port_no == 1
        utilization = port_metrics.calculate_utilization()
        print(f"✓ PortMetrics creato - Porta {port_metrics.port_no}, Utilizzo: {utilization*100:.1f}%")
        
        # Test 5: Creazione TopologyData
        print("\nTest 5: Creazione TopologyData...")
        topology = TopologyData(
            switches=[switch],
            links=[link]
        )
        assert len(topology.switches) == 1
        assert len(topology.links) == 1
        print(f"✓ TopologyData creato - {len(topology.switches)} switch, {len(topology.links)} link")
        
        # Test 6: Serializzazione
        print("\nTest 6: Serializzazione TopologyData...")
        topology_dict = topology.to_dict()
        assert 'switches' in topology_dict
        assert 'links' in topology_dict
        print(f"✓ TopologyData serializzato correttamente")
        
        print()
        print("="*70)
        print("✅ TUTTI I TEST PASSATI!")
        print("="*70)
        print()
        print("Struttura verificata:")
        print("  ✓ src/models/core.py    - Import e creazione oggetti OK")
        print("  ✓ src/models/health.py  - Import OK")
        print("  ✓ src/models/llm.py     - Import OK")
        print()
        print("NOTA: Per test completi, installa le dipendenze:")
        print("  python3 -m venv venv")
        print("  source venv/bin/activate")
        print("  pip install -r requirements.txt")
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
    success = test_basic_imports()
    sys.exit(0 if success else 1)
