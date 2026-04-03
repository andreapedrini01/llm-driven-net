#!/usr/bin/env python3
"""
Topologia tree,depth=3,fanout=3 con host Docker per nmap scanner.

Uso:
  sudo python3 topology.py
"""

import sys
import traceback
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info

# Prova a importare Containernet
HAS_CONTAINERNET = False
try:
    from comnetsemu.net import Containernet
    HAS_CONTAINERNET = True
except ImportError:
    pass

if not HAS_CONTAINERNET:
    from mininet.net import Mininet


def build_tree(net, depth, fanout, switch_counter, host_counter):
    """Costruisce ricorsivamente l'albero."""
    switch_counter += 1
    sw = net.addSwitch(f's{switch_counter}', protocols='OpenFlow13')

    if depth == 1:
        for _ in range(fanout):
            host_counter += 1
            h = net.addHost(f'h{host_counter}', ip=f'10.0.0.{host_counter}/24')
            net.addLink(h, sw, bw=100, delay='2ms', cls=TCLink)
    else:
        for _ in range(fanout):
            child_sw, switch_counter, host_counter = build_tree(
                net, depth - 1, fanout, switch_counter, host_counter
            )
            net.addLink(sw, child_sw, bw=100, delay='2ms', cls=TCLink)

    return sw, switch_counter, host_counter


def run():
    setLogLevel('info')

    info(f'*** HAS_CONTAINERNET = {HAS_CONTAINERNET}\n')

    if HAS_CONTAINERNET:
        info('*** Usando Containernet\n')
        net = Containernet(
            controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6653),
            switch=OVSKernelSwitch,
            autoSetMacs=True,
        )
    else:
        info('*** Usando Mininet (senza Docker)\n')
        net = Mininet(
            controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6653),
            switch=OVSKernelSwitch,
            autoSetMacs=True,
        )

    net.addController('c0')

    info('*** Costruzione topologia tree depth=3 fanout=3\n')
    root_sw, _, _ = build_tree(net, depth=3, fanout=3, switch_counter=0, host_counter=0)

    # Aggiungi host Docker scanner PRIMA di net.start()
    scanner_added = False
    if HAS_CONTAINERNET:
        info('*** Tentativo aggiunta host Docker scanner...\n')
        try:
            scanner = net.addDockerHost(
                'scanner',
                dimage='progetto-nmap-manet',
                ip='10.0.0.100/24',
                docker_args={},
            )
            net.addLink(scanner, root_sw, bw=100, delay='2ms', cls=TCLink)
            scanner_added = True
            info('*** Host Docker scanner aggiunto con successo\n')
        except Exception as e:
            info(f'*** ERRORE aggiunta Docker scanner: {e}\n')
            traceback.print_exc()

    net.start()

    if scanner_added:
        info('*** Scanner Docker su 10.0.0.100:5000\n')
        info('*** Testa: scanner curl http://10.0.0.100:5000/scan?target=10.0.0.1\n')
    else:
        info('*** Scanner Docker NON aggiunto.\n')
        if HAS_CONTAINERNET:
            info('*** Buildata immagine? docker build -t progetto-nmap-manet deployment/progetto-nmap-manet/\n')
        else:
            info('*** Containernet non disponibile. Avvia Flask manualmente:\n')
            info('***   h27 python3 deployment/progetto-nmap-manet/app.py &\n')

    info(f'\n*** Switch: {len(net.switches)}, Host: {len(net.hosts)}\n\n')

    CLI(net)
    net.stop()


if __name__ == '__main__':
    run()
