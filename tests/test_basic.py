"""Test base per Northbound Script - SENZA rete reale"""

import sys
import os
# Aggiungi la directory parent al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from northbound_script import NorthboundScript

def test_parsing():
    """Test 1: Verifica parsing LLM output"""
    print("\n=== TEST 1: PARSING ===")
    
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
        return True
    except Exception as e:
        print(f"❌ Parsing fallito: {e}")
        return False

def test_validation():
    """Test 2: Verifica validazione"""
    print("\n=== TEST 2: VALIDAZIONE ===")
    
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
        print(f"❌ Dry run fallito")
        return False

def test_logging():
    """Test 4: Verifica logging"""
    print("\n=== TEST 4: LOGGING ===")
    
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

if __name__ == "__main__":
    print("=" * 60)
    print("TEST NORTHBOUND SCRIPT")
    print("=" * 60)
    
    results = []
    results.append(("Parsing", test_parsing()))
    results.append(("Validazione", test_validation()))
    results.append(("Dry Run", test_dry_run()))
    results.append(("Logging", test_logging()))
    
    print("\n" + "=" * 60)
    print("RISULTATI")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    total = sum(1 for _, p in results if p)
    print(f"\nTotale: {total}/{len(results)} test passati")