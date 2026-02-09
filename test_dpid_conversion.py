#!/usr/bin/env python3
"""
Test rapido per verificare la conversione DPID e le chiamate API Ryu
"""

import requests
import json

def test_dpid_conversion():
    """Testa la conversione DPID"""
    print("=== Test Conversione DPID ===\n")
    
    test_cases = [
        "0000000000000001",
        "0000000000000002", 
        "0000000000000003",
        "1",
        "2",
        "3"
    ]
    
    for dpid in test_cases:
        # Converte da hex string a int e poi a string decimale
        try:
            dpid_int = int(str(dpid), 16) if isinstance(dpid, str) and len(str(dpid)) > 2 else int(str(dpid))
            dpid_param = str(dpid_int)
            print(f"  {dpid:20s} -> {dpid_param}")
        except (ValueError, TypeError) as e:
            print(f"  {dpid:20s} -> ERROR: {e}")

def test_ryu_endpoints():
    """Testa gli endpoint Ryu con diversi formati DPID"""
    print("\n=== Test Endpoint Ryu ===\n")
    
    base_url = "http://127.0.0.1:8080"
    
    # Ottieni lista switch
    print("1. Lista switches:")
    try:
        response = requests.get(f"{base_url}/stats/switches", timeout=5)
        switches = response.json()
        print(f"   Status: {response.status_code}")
        print(f"   Switches: {switches}\n")
    except Exception as e:
        print(f"   ERROR: {e}\n")
        return
    
    # Testa port stats con diversi formati
    dpid_formats = [
        ("Hex lungo", "0000000000000001"),
        ("Decimale", "1")
    ]
    
    for name, dpid in dpid_formats:
        print(f"2. Port stats per DPID {name} ({dpid}):")
        try:
            response = requests.get(f"{base_url}/stats/port/{dpid}", timeout=5)
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                if dpid in data:
                    print(f"   Porte trovate: {len(data[dpid])}")
                else:
                    print(f"   Chiavi disponibili: {list(data.keys())}")
            else:
                print(f"   Errore: {response.text[:200]}")
        except Exception as e:
            print(f"   ERROR: {e}")
        print()

if __name__ == "__main__":
    test_dpid_conversion()
    test_ryu_endpoints()
