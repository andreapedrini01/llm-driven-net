#!/usr/bin/env python3
"""
Test per verificare l'isolamento errori per switch multipli (Task 10.1)
"""

import sys
from network_state_collector.collector import NetworkStateCollector
from network_state_collector.models.config import CollectorConfig, RyuConfig, CollectionConfig
from unittest.mock import Mock, patch

def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_error_isolation():
    """
    Test che verifica:
    1. Se uno switch fallisce, gli altri continuano
    2. Il collector non crasha
    3. I dati degli switch funzionanti vengono raccolti
    """
    
    print_header("🧪 Test Isolamento Errori Switch Multipli")
    
    # Configurazione
    config = CollectorConfig(
        ryu=RyuConfig(host="localhost", port=8080),
        collection=CollectionConfig(parallel_collection=True, max_workers=4)
    )
    
    collector = NetworkStateCollector(config)
    
    # Mock del RyuConnector per simulare errori
    print("📋 Setup: 3 switch, switch 2 fallisce")
    print("   • Switch 1: ✓ Funzionante")
    print("   • Switch 2: ✗ Errore (timeout)")
    print("   • Switch 3: ✓ Funzionante")
    print()
    
    # Simula get_switches che ritorna 3 switch
    from network_state_collector.models.core import SwitchInfo
    mock_switches = [
        SwitchInfo(dpid="0000000000000001", ports=[1, 2, 3]),
        SwitchInfo(dpid="0000000000000002", ports=[1, 2]),  # Questo fallirà
        SwitchInfo(dpid="0000000000000003", ports=[1, 2, 3, 4])
    ]
    
    # Simula get_port_stats che fallisce per switch 2
    def mock_get_port_stats(dpid):
        if dpid == "0000000000000002":
            raise Exception("Connection timeout for switch 2")
        
        # Ritorna stats per gli altri switch
        return {
            dpid: [
                {"port_no": 1, "rx_packets": 1000, "tx_packets": 800, 
                 "rx_bytes": 100000, "tx_bytes": 80000, 
                 "rx_errors": 0, "tx_errors": 0}
            ]
        }
    
    collector.ryu_connector.get_port_stats = mock_get_port_stats
    
    # Test raccolta parallela
    print_header("🔄 Test Raccolta Parallela")
    
    try:
        port_stats = collector._collect_port_stats_parallel(mock_switches)
        
        print("✓ Raccolta completata senza crash")
        print(f"✓ Dati raccolti da {len(port_stats)} switch su 3")
        print()
        
        # Verifica risultati
        print("📊 Risultati:")
        for dpid in ["0000000000000001", "0000000000000002", "0000000000000003"]:
            if dpid in port_stats:
                print(f"   ✓ Switch {dpid}: {len(port_stats[dpid])} porte")
            else:
                print(f"   ✗ Switch {dpid}: Nessun dato (errore isolato)")
        
        print()
        
        # Verifica che almeno 2 switch abbiano dati
        if len(port_stats) >= 2:
            print("✅ Test PASSATO: Isolamento errori funziona!")
            print("   • Switch con errore isolato correttamente")
            print("   • Altri switch continuano a funzionare")
            print("   • Nessun crash del sistema")
            return True
        else:
            print("❌ Test FALLITO: Troppi pochi dati raccolti")
            return False
            
    except Exception as e:
        print(f"❌ Test FALLITO: Eccezione non gestita: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_sequential_error_isolation():
    """Test isolamento errori in modalità sequenziale"""
    
    print_header("🔄 Test Raccolta Sequenziale")
    
    config = CollectorConfig(
        ryu=RyuConfig(host="localhost", port=8080),
        collection=CollectionConfig(parallel_collection=False)
    )
    
    collector = NetworkStateCollector(config)
    
    from network_state_collector.models.core import SwitchInfo
    mock_switches = [
        SwitchInfo(dpid="0000000000000001", ports=[1, 2]),
        SwitchInfo(dpid="0000000000000002", ports=[1]),  # Fallirà
        SwitchInfo(dpid="0000000000000003", ports=[1, 2, 3])
    ]
    
    def mock_get_port_stats(dpid):
        if dpid == "0000000000000002":
            raise Exception("Switch 2 unreachable")
        return {
            dpid: [{"port_no": 1, "rx_packets": 500, "tx_packets": 400,
                   "rx_bytes": 50000, "tx_bytes": 40000,
                   "rx_errors": 0, "tx_errors": 0}]
        }
    
    collector.ryu_connector.get_port_stats = mock_get_port_stats
    
    try:
        port_stats = collector._collect_port_stats_sequential(mock_switches)
        
        print("✓ Raccolta sequenziale completata")
        print(f"✓ Dati raccolti da {len(port_stats)} switch su 3")
        print()
        
        if len(port_stats) >= 2:
            print("✅ Test PASSATO: Isolamento errori sequenziale funziona!")
            return True
        else:
            print("❌ Test FALLITO")
            return False
            
    except Exception as e:
        print(f"❌ Test FALLITO: {e}")
        return False

def main():
    print_header("🚀 Test Task 10.1 - Isolamento Errori Switch")
    
    results = []
    
    # Test 1: Parallelo
    results.append(("Parallelo", test_error_isolation()))
    
    # Test 2: Sequenziale
    results.append(("Sequenziale", test_sequential_error_isolation()))
    
    # Riepilogo
    print_header("📊 Riepilogo Test")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} - Test {name}")
    
    print()
    print(f"Risultato: {passed}/{total} test passati")
    print()
    
    if passed == total:
        print("🎉 Task 10.1 COMPLETATA!")
        print()
        print("✓ Isolamento errori implementato correttamente")
        print("✓ Raccolta parallela gestisce errori individuali")
        print("✓ Raccolta sequenziale gestisce errori individuali")
        print("✓ Sistema continua a funzionare anche con switch falliti")
        return True
    else:
        print("⚠️  Alcuni test falliti")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
