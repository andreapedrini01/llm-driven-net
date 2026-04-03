#!/usr/bin/env python3
"""
Topologia tree,depth=3,fanout=3 con host Docker per nmap scanner.

Equivalente a:
  sudo mn --topo tree,depth=3,fanout=3 --controller remote,ip=127.0.0.1,port=6653
         --switch ovsk,protocols=OpenFlow13 --link tc,bw=100,delay=2ms

In più aggiunge un host Docker 'scanner' (10.0.0.100) con il web server
Flask/nmap per la scansione di sicurezza.

Uso:
  sudo python3 topology.py
"""

from mininet.topo import Topo
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info

try:
    from comnetsemu.net import Containernet
    HAS_CONTAINERNET = True
except ImportError:
    HAS_CONTAINERNET = False

if not HAS_CONTAINERNET:
    from mininet.net import Mininet


def build_tree(net, depth, fanout, switch_counter, host_counter):
    """Costruisce ricorsivamente l'albero e restituisce (switch, switch_counter, host_counter)."""
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

    if HAS_CONTAINERNET:
        info('*** Usando Containernet (con supporto Docker)\n')
        net = Containernet(
            controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6653),
            switch=OVSKernelSwitch,
            autoSetMacs=True,
        )
    else:
        info('*** Usando Mininet standard (senza Docker)\n')
        net = Mininet(
            controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6653),
            switch=OVSKernelSwitch,
            autoSetMacs=True,
        )

    info('*** Aggiunta controller\n')
    net.addController('c0')

    info('*** Costruzione topologia tree depth=3 fanout=3\n')
    root_sw, _, _ = build_tree(net, depth=3, fanout=3, switch_counter=0, host_counter=0)

    # Aggiungi host Docker per nmap scanner PRIMA di net.start()
    scanner_added = False
    if HAS_CONTAINERNET:
        info('*** Aggiunta host Docker scanner (10.0.0.100)\n')
        try:
            scanner = net.addDockerHost(
                'scanner',
                dimage='progetto-nmap-manet',
                ip='10.0.0.100/24',
            )
            net.addLink(scanner, root_sw, bw=100, delay='2ms', cls=TCLink)
            scanner_added = True
        except Exception as e:
            info(f'*** ATTENZIONE: impossibile aggiungere host Docker: {e}\n')
            info('*** Assicurati di aver buildato: docker build -t progetto-nmap-manet deployment/progetto-nmap-manet/\n')

    info('*** Avvio rete\n')
    net.start()

    if scanner_added:
        info('*** Scanner Docker avviato su 10.0.0.100:5000\n')
        info('*** Testa con: scanner curl http://10.0.0.100:5000/scan?target=10.0.0.1\n')
    elif not HAS_CONTAINERNET:
        info('*** Containernet non disponibile, scanner Docker non aggiunto\n')
        info('*** Per usare nmap, avvia Flask manualmente su un host:\n')
        info('***   h27 python3 deployment/progetto-nmap-manet/app.py &\n')

    info(f'\n*** Switch: {len(net.switches)}\n')
    info(f'*** Host: {len(net.hosts)}\n')
    info('*** Controller: remote 127.0.0.1:6653\n\n')

    CLI(net)
    net.stop()


if __name__ == '__main__':
    run()
