import json
import time
import requests
from pathlib import Path

RYU_REST_BASE = "http://127.0.0.1:8080"
OUTPUT_DIR = Path("persona1/data")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def format_dpid(dpid):
    """Assicura che il DPID sia nel formato esadecimale a 16 cifre."""
    return f"{int(dpid):016x}"

def get_network_data(endpoint):
    try:
        resp = requests.get(f"{RYU_REST_BASE}{endpoint}", timeout=3)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Errore su {endpoint}: {e}")
        return {}

def collect_network_state():
    # 1. Recupero dati grezzi
    raw_switches = get_network_data("/stats/switches")
    raw_links = get_network_data("/v1.0/topology/links")
    
    snapshot = {
        "timestamp": time.time(),
        "topology": [],
        "performance": {}
    }

    # 2. Costruzione Topologia Semplificata (per il grafo di Andrea)
    for link in raw_links:
        snapshot["topology"].append({
            "src": format_dpid(link["src"]["dpid"]),
            "dst": format_dpid(link["dst"]["dpid"]),
            "port_out": link["src"]["port_no"],
            "port_in": link["dst"]["port_no"]
        })

    # 3. Estrazione Metriche (per Anomaly Detection dell'LLM)
    for dpid_int in raw_switches:
        dpid_hex = format_dpid(dpid_int)
        port_stats = get_network_data(f"/stats/port/{dpid_int}")
        
        # Prendiamo solo i dati che servono per calcolare congestione o errori
        snapshot["performance"][dpid_hex] = []
        if str(dpid_int) in port_stats:
            for p in port_stats[str(dpid_int)]:
                if p["port_no"] != "LOCAL": # Escludiamo la porta interna del controller
                    snapshot["performance"][dpid_hex].append({
                        "port": p["port_no"],
                        "rx_packets": p["rx_packets"],
                        "tx_packets": p["tx_packets"],
                        "rx_errors": p["rx_errors"],
                        "tx_errors": p["tx_errors"],
                        "rx_bytes": p["rx_bytes"],
                        "tx_bytes": p["tx_bytes"]
                    })
    
    return snapshot

def main():
    state = collect_network_state()
    
    # Salvataggio per il modulo di Andrea
    file_name = f"network_context_latest.json"
    with open(OUTPUT_DIR / file_name, "w") as f:
        json.dump(state, f, indent=2)
    
    print(f"Snapshot creato alle {time.ctime(state['timestamp'])}")
    print(f"Switch rilevati: {len(state['performance'])}")

if __name__ == "__main__":
    main()