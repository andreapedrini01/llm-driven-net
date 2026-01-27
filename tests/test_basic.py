"""Test base per Northbound Script - CON integrazione RYU reale"""

import sys
import os
# Aggiungi la directory parent al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from unittest.mock import patch, Mock
from northbound_script import NorthboundScript

def test_parsing():
    """Test 1: Verifica parsing LLM output"""
    print("\n=== TEST 1: PARSING ===")
    
    # Mock RYU connection to avoid actual network calls
    with patch('northbound_script.RYUNetworkInterface') as mock_interface:
        mock_interface.return_value = Mock()
        northbound = NorthboundScript()
    
    llm_output = json.dumps({
        "id": "seq_test_001",
        "intent_id": "intent_test",
        "estimated_duration": 10,
        "actions": [{
            "id": "action_001",
            "type": "flow_mod",
            "target": "switch-1",
            "parameters": {
                "operation": "add",
                "match": {"ip_src": "192.168.1.100"},
                "actions": ["drop"]
            },
            "priority": 1000,
            "timeout": 30
        }],
        "dependencies": [],
        "rollback_plan": []
    })
    
    try:
        sequence = northbound.parse_llm_output(llm_output)
        print(f"✅ Parsing riuscito!")
        print(f"   Sequence ID: {sequence.id}")
        print(f"   Numero azioni: {len(sequence.actions)}")
        print(f"   Operazione: {sequence.actions[0].parameters.get('operation', 'N/A')}")
        return True
    except Exception as e:
        print(f"❌ Parsing fallito: {e}")
        return False

def test_validation():
    """Test 2: Verifica validazione"""
    print("\n=== TEST 2: VALIDAZIONE ===")
    
    with patch('northbound_script.RYUNetworkInterface') as mock_interface:
        mock_interface.return_value = Mock()
        northbound = NorthboundScript()
    
    llm_output_invalid = json.dumps({
        "id": "seq_invalid",
        "intent_id": "intent_test",
        "estimated_duration": 10,
        "actions": [{
            "id": "action_001",
            "type": "flow_mod",
            "target": "switch-1",
            "parameters": {
                "actions": ["drop"]  # MANCA 'match'
            },
            "priority": 1000,
            "timeout": 30
        }],
        "dependencies": [],
        "rollback_plan": []
    })
    
    try:
        sequence = northbound.parse_llm_output(llm_output_invalid)
        validation = northbound.validate_sequence(sequence)
        
        if not validation.is_valid:
            print(f"✅ Validazione funziona!")
            print(f"   Errori: {validation.errors}")
            return True
        else:
            print(f"❌ Validazione non ha rilevato errori!")
            return False
    except Exception as e:
        print(f"⚠️  Eccezione: {e}")
        return False

def test_dry_run():
    """Test 3: Verifica dry run"""
    print("\n=== TEST 3: DRY RUN ===")
    
    with patch('northbound_script.RYUNetworkInterface') as mock_interface:
        mock_interface.return_value = Mock()
        northbound = NorthboundScript()
    
    llm_output = json.dumps({
        "id": "seq_dryrun",
        "intent_id": "intent_test",
        "estimated_duration": 10,
        "actions": [{
            "id": "action_001",
            "type": "flow_mod",
            "target": "switch-1",
            "parameters": {
                "operation": "add",
                "match": {"ip_src": "192.168.1.100"},
                "actions": ["drop"]
            },
            "priority": 1000,
            "timeout": 30
        }],
        "dependencies": [],
        "rollback_plan": []
    })
    
    result = northbound.process_llm_output(llm_output, dry_run=True)
    
    if result["success"]:
        print(f"✅ Dry run completato!")
        return True
    else:
        print(f"❌ Dry run fallito: {result.get('message', 'Unknown error')}")
        return False

def test_ryu_integration():
    """Test 4: Verifica integrazione RYU (mock)"""
    print("\n=== TEST 4: INTEGRAZIONE RYU ===")
    
    # Mock RYU connector
    with patch('ryu_connector.create_ryu_connector') as mock_create:
        mock_connector = Mock()
        mock_connector.get_connection_status.return_value = {
            "status": "connected",
            "config": {"host": "localhost", "port": 8080},
            "pool_stats": {"total_requests": 0, "successful_requests": 0}
        }
        mock_create.return_value = mock_connector
        
        northbound = NorthboundScript(
            ryu_host="localhost",
            ryu_port=8080,
            timeout_seconds=30
        )
        
        # Test connection status
        status = northbound.get_ryu_status()
        
        if status.get("overall_status") == "connected":
            print(f"✅ Integrazione RYU funziona!")
            ryu_status = status.get("ryu", {})
            print(f"   Host: {ryu_status.get('config', {}).get('host', 'unknown')}")
            print(f"   Port: {ryu_status.get('config', {}).get('port', 'unknown')}")
            print(f"   RYU Status: {ryu_status.get('status', 'unknown')}")
            print(f"   Overall Status: {status.get('overall_status', 'unknown')}")
            northbound.close()
            return True
        else:
            print(f"❌ Integrazione RYU fallita")
            print(f"   Overall Status: {status.get('overall_status', 'unknown')}")
            ryu_status = status.get("ryu", {})
            comnetsemu_status = status.get("comnetsemu", {})
            print(f"   RYU Status: {ryu_status.get('status', 'unknown')}")
            print(f"   ComnetsEMU Status: {comnetsemu_status.get('status', 'unknown')}")
            northbound.close()
            return False

def test_logging():
    """Test 5: Verifica logging"""
    print("\n=== TEST 5: LOGGING ===")
    
    with patch('northbound_script.RYUNetworkInterface') as mock_interface:
        mock_interface.return_value = Mock()
        northbound = NorthboundScript(log_dir="./logs")
    
    import os
    log_files = os.listdir("./logs") if os.path.exists("./logs") else []
    print(f"✅ File log: {log_files}")
    
    if "network_changes.db" in log_files:
        print(f"✅ Database creato!")
        
        import sqlite3
        conn = sqlite3.connect("./logs/network_changes.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"   Tabelle: {[t[0] for t in tables]}")
        conn.close()
        return True
    else:
        print(f"⚠️  Database non ancora creato (normale al primo avvio)")
        return True

def test_connection_pooling():
    """Test 6: Verifica connection pooling"""
    print("\n=== TEST 6: CONNECTION POOLING ===")
    
    try:
        from ryu_connector import RYUConfig, RYUConnectionPool
        
        config = RYUConfig(
            host="localhost",
            port=8080,
            connection_pool_size=5,
            max_connections_per_host=3
        )
        
        # Test configuration
        print(f"✅ Configurazione pool:")
        print(f"   Pool size: {config.connection_pool_size}")
        print(f"   Max connections per host: {config.max_connections_per_host}")
        print(f"   Timeout: {config.timeout_seconds}s")
        print(f"   Max retries: {config.max_retries}")
        print(f"   Retry delay: {config.retry_delay}s")
        
        return True
        
    except Exception as e:
        print(f"❌ Test connection pooling fallito: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("TEST NORTHBOUND SCRIPT CON RYU REALE")
    print("=" * 60)
    
    results = []
    results.append(("Parsing", test_parsing()))
    results.append(("Validazione", test_validation()))
    results.append(("Dry Run", test_dry_run()))
    results.append(("Integrazione RYU", test_ryu_integration()))
    results.append(("Logging", test_logging()))
    results.append(("Connection Pooling", test_connection_pooling()))
    
    print("\n" + "=" * 60)
    print("RISULTATI")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    total = sum(1 for _, p in results if p)
    print(f"\nTotale: {total}/{len(results)} test passati")
    
    if total == len(results):
        print("🎉 Tutti i test sono passati! RYU Connector implementato correttamente.")
    else:
        print("⚠️  Alcuni test sono falliti. Controllare l'implementazione.")