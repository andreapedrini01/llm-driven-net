#!/usr/bin/env python3
"""
Mock Ryu Controller Server per testing del Network State Collector

Simula le API REST del controller Ryu per permettere test senza un controller reale.
Esegui con: python mock_ryu_server.py
"""

from flask import Flask, jsonify
import random
import time

app = Flask(__name__)

# Dati mock per simulare una rete semplice
MOCK_SWITCHES = [
    {"dpid": 1, "ports": [1, 2, 3, 4]},
    {"dpid": 2, "ports": [1, 2, 3]},
    {"dpid": 3, "ports": [1, 2]}
]

MOCK_LINKS = [
    {
        "src": {"dpid": "0000000000000001", "port_no": 2, "name": "s1-eth2"},
        "dst": {"dpid": "0000000000000002", "port_no": 1, "name": "s2-eth1"}
    },
    {
        "src": {"dpid": "0000000000000002", "port_no": 2, "name": "s2-eth2"},
        "dst": {"dpid": "0000000000000003", "port_no": 1, "name": "s3-eth1"}
    }
]

@app.route('/stats/switches')
@app.route('/v1.0/stats/switches')
def get_switches():
    """Restituisce la lista degli switch attivi"""
    return jsonify(MOCK_SWITCHES)

@app.route('/topology/links')
@app.route('/v1.0/topology/links')
def get_links():
    """Restituisce i link di topologia"""
    return jsonify(MOCK_LINKS)

@app.route('/stats/port/<dpid>')
@app.route('/v1.0/stats/port/<dpid>')
def get_port_stats(dpid):
    """Restituisce statistiche delle porte per uno switch"""
    # Simula statistiche realistiche con valori casuali
    base_time = int(time.time())
    
    # Converti DPID in formato numerico
    try:
        if dpid.startswith('0x') or dpid.startswith('0000'):
            dpid_int = int(dpid.replace('0x', ''), 16)
        else:
            dpid_int = int(dpid)
    except:
        return jsonify([]), 404
    
    # Trova lo switch
    switch = None
    for s in MOCK_SWITCHES:
        if s["dpid"] == dpid_int:
            switch = s
            break
    
    if not switch:
        return jsonify([]), 404
    
    stats = {str(dpid_int): []}
    for port in switch["ports"]:
        # Simula traffico realistico
        rx_packets = random.randint(1000, 10000)
        tx_packets = random.randint(800, 8000)
        rx_bytes = rx_packets * random.randint(64, 1500)
        tx_bytes = tx_packets * random.randint(64, 1500)
        
        stats[str(dpid_int)].append({
            "port_no": port,
            "rx_packets": rx_packets,
            "tx_packets": tx_packets,
            "rx_bytes": rx_bytes,
            "tx_bytes": tx_bytes,
            "rx_dropped": random.randint(0, 10),
            "tx_dropped": random.randint(0, 5),
            "rx_errors": random.randint(0, 2),
            "tx_errors": random.randint(0, 1),
            "rx_frame_err": 0,
            "rx_over_err": 0,
            "rx_crc_err": 0,
            "collisions": 0,
            "duration_sec": base_time - random.randint(100, 1000),
            "duration_nsec": random.randint(0, 999999999)
        })
    
    return jsonify(stats)

@app.route('/stats/flow/<dpid>')
@app.route('/v1.0/stats/flow/<dpid>')
def get_flow_stats(dpid):
    """Restituisce statistiche dei flussi (opzionale)"""
    return jsonify([])

@app.route('/health')
@app.route('/v1.0/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": time.time(),
        "switches": len(MOCK_SWITCHES),
        "links": len(MOCK_LINKS)
    })

if __name__ == '__main__':
    print("🚀 Avvio Mock Ryu Controller Server...")
    print("📡 Server disponibile su: http://localhost:8080")
    print("🔗 Endpoints disponibili:")
    print("   - GET /stats/switches")
    print("   - GET /topology/links") 
    print("   - GET /stats/port/<dpid>")
    print("   - GET /health")
    print("\n💡 Per testare: curl http://localhost:8080/stats/switches")
    print("🛑 Premi Ctrl+C per fermare il server\n")
    
    app.run(host='0.0.0.0', port=8080, debug=True)