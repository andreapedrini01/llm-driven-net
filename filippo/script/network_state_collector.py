#!/usr/bin/env python3
"""
Persona 1  Network State Collector

Interroga il controller Ryu tramite REST API e produce uno snapshot
dello stato di rete in formato JSON:

- lista degli switch (DPID)
- flow stats per ogni switch
- port stats (byte/packet/errori) per ogni switch
- topologia logica (switch + link) da rest_topology
"""

import json
import time
from pathlib import Path

import requests

# Endpoint REST di Ryu (di default 127.0.0.1:8080)
RYU_REST_BASE = "http://127.0.0.1:8080"

# Dove salvare gli snapshot localmente nel repo
OUTPUT_DIR = Path("persona1/data")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_switches():
    """Restituisce la lista dei DPID degli switch connessi al controller."""
    url = f"{RYU_REST_BASE}/stats/switches"
    resp = requests.get(url, timeout=2)
    resp.raise_for_status()
    return resp.json()  # es. [1, 2, 3]


def get_flow_stats(dpid: int):
    """Flow stats per uno switch (usa ryu.app.ofctl_rest)."""
    url = f"{RYU_REST_BASE}/stats/flow/{dpid}"
    resp = requests.get(url, timeout=3)
    resp.raise_for_status()
    return resp.json()


def get_port_stats(dpid: int):
    """Port stats (bytes, packets, errori) per uno switch."""
    url = f"{RYU_REST_BASE}/stats/port/{dpid}"
    resp = requests.get(url, timeout=3)
    resp.raise_for_status()
    return resp.json()


def get_topology():
    """
    Topologia logica da ryu.app.rest_topology:
    - /v1.0/topology/switches
    - /v1.0/topology/links
    """
    topo = {}
    try:
        sw_resp = requests.get(
            f"{RYU_REST_BASE}/v1.0/topology/switches", timeout=3
        )
        links_resp = requests.get(
            f"{RYU_REST_BASE}/v1.0/topology/links", timeout=3
        )
        sw_resp.raise_for_status()
        links_resp.raise_for_status()
        topo["switches"] = sw_resp.json()
        topo["links"] = links_resp.json()
    except Exception as e:
        topo["error"] = f"topology_request_failed: {e}"
    return topo


def collect_network_state() -> dict:
    """Crea un dizionario con lo stato di rete corrente."""
    snapshot = {
        "timestamp": time.time(),
        "switches": [],
        "flows": {},
        "ports": {},
        "topology": get_topology(),
    }

    dpids = get_switches()
    snapshot["switches"] = dpids

    for dpid in dpids:
        key = str(dpid)
        snapshot["flows"][key] = get_flow_stats(dpid)
        snapshot["ports"][key] = get_port_stats(dpid)

    return snapshot


def main():
    state = collect_network_state()

    # Stampa a schermo in modo leggibile
    print(json.dumps(state, indent=2))

    # Salva con timestamp
    ts = time.strftime("%Y%m%d-%H%M%S")
    out_path = OUTPUT_DIR / f"network_state_{ts}.json"
    out_path.write_text(json.dumps(state, indent=2))
    print(f"\n[INFO] Network state scritto in: {out_path}")


if __name__ == "__main__":
    main()
