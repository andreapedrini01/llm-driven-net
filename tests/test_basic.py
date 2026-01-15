"""Test base - VERSIONE SENZA VENV"""

import sys
import os
# Aggiungi directory parent al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from northbound_script import NorthboundScript

print("\n" + "="*60)
print("TEST NORTHBOUND SCRIPT (Senza venv)")
print("="*60)

# TEST 1: Verifica imports
print("\n[TEST 0] Verifica dipendenze...")
try:
    import pydantic
    import requests
    import flask
    print("✅ Tutte le dipendenze sono installate!")
    print(f"   - pydantic: {pydantic.__version__}")
    print(f"   - requests: {requests.__version__}")
    print(f"   - flask: {flask.__version__}")
except ImportError as e:
    print(f"❌ ERRORE: Manca una dipendenza: {e}")
    print("   Esegui: pip install pydantic requests flask")
    sys.exit(1)

# TEST 1: PARSING
print("\n[TEST 1] Parsing LLM Output...")
try:
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
    
    sequence = northbound.parse_llm_output(llm_output)
    print(f"✅ SUCCESSO")
    print(f"   Sequence ID: {sequence.id}")
    print(f"   Azioni: {len(sequence.actions)}")
except Exception as e:
    print(f"❌ FALLITO: {e}")
    import traceback
    traceback.print_exc()

# TEST 2: VALIDAZIONE
print("\n[TEST 2] Validazione...")
try:
    llm_invalid = json.dumps({
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
    
    sequence = northbound.parse_llm_output(llm_invalid)
    validation = northbound.validate_sequence(sequence)
    
    if not validation.is_valid:
        print(f"✅ SUCCESSO - Errori rilevati: {len(validation.errors)}")
    else:
        print(f"❌ FALLITO - Nessun errore rilevato")
except Exception as e:
    print(f"⚠️  ECCEZIONE: {e}")

# TEST 3: DRY RUN
print("\n[TEST 3] Dry Run...")
try:
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
        print(f"✅ SUCCESSO")
    else:
        print(f"❌ FALLITO")
except Exception as e:
    print(f"❌ FALLITO: {e}")

# TEST 4: LOGGING
print("\n[TEST 4] Sistema di Logging...")
try:
    if os.path.exists("./logs"):
        log_files = os.listdir("./logs")
        print(f"✅ SUCCESSO - File log: {len(log_files)}")
        
        if "network_changes.db" in log_files:
            print(f"   → Database presente")
    else:
        print(f"⚠️  Cartella logs non ancora creata")
except Exception as e:
    print(f"⚠️  {e}")

print("\n" + "="*60)
print("TEST COMPLETATI!")
print("="*60 + "\n")