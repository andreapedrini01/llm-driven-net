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

from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info

try:
    from comnetsemu.net import Containernet
    HAS_CONTAINERNET = True
except ImportError:
    try:
        from mininet.net import Containernet
        HAS_CONTAINERNET = True
    except ImportError:
        HAS_CONTAINERNET = False


class TreeTopo(Topo):
    """Topologia ad albero depth=3, fanout=3."""

    def build(self, depth=3, fanout=3):
        self._build_tree(depth, fanout, 1)

    def _build_tree(self, depth, fanout, switch_num):
        """Costruisce ricorsivamente l'albero di switch e host."""
        switch = self.addSwitch(f's{switch_num}', protocols='OpenFlow13')

        if depth == 1:
            # Foglia: aggiungi host
            for i in range(fanout):
                host_num = self._next_host_num()
                host = self.addHost(f'h{host_num}', ip=f'10.0.0.{host_num}/24')
                self.addLink(host, switch, bw=100, delay='2ms')
        else:
            # Nodo interno: aggiungi sotto-alberi
            for i in range(fanout):
                child_num = self._get_next_switch_num()
                child_switch = self._build_tree(depth - 1, fanout, child_num)
                self.addLink(switch, child_switch, bw=100, delay='2ms')

        return switch

    def _next_host_num(self):
        if not hasattr(self, '_host_counter'):
            self._host_counter = 0
        self._host_counter += 1
        return self._host_counter

    def _get_next_switch_num(self):
        if not hasattr(self, '_switch_counter'):
            self._switch_counter = 1  # s1 è già usato
        self._switch_counter += 1
        return self._switch_counter


def run():
    setLogLevel('info')

    if HAS_CONTAINERNET:
        info('*** Usando Containernet (con supporto Docker)\n')
        net = Containernet(
            topo=TreeTopo(depth=3, fanout=3),
            controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6653),
            switch=OVSKernelSwitch,
            link=TCLink,
            autoSetMacs=True,
        )
    else:
        info('*** Usando Mininet standard (senza Docker)\n')
        net = Mininet(
            topo=TreeTopo(depth=3, fanout=3),
            controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6653),
            switch=OVSKernelSwitch,
            link=TCLink,
            autoSetMacs=True,
        )

    net.start()

    # Aggiungi host Docker per nmap scanner (solo con Containernet)
    if HAS_CONTAINERNET:
        info('*** Aggiunta host Docker scanner (10.0.0.100)\n')
        try:
            from mininet.node import Docker
            scanner = net.addDocker(
                'scanner',
                ip='10.0.0.100/24',
                dimage='progetto-nmap-manet',
            )
            # Collega allo switch root (s1)
            net.addLink(scanner, net.get('s1'), bw=100, delay='2ms')
            info('*** Scanner Docker avviato su 10.0.0.100:5000\n')
            info('*** Testa con: scanner curl http://10.0.0.100:5000/scan?target=10.0.0.1\n')
        except Exception as e:
            info(f'*** ATTENZIONE: impossibile aggiungere host Docker: {e}\n')
            info('*** Assicurati di aver buildato: docker build -t progetto-nmap-manet deployment/progetto-nmap-manet/\n')
    else:
        info('*** Containernet non disponibile, scanner Docker non aggiunto\n')
        info('*** Per usare nmap, avvia Flask manualmente su un host:\n')
        info('***   h27 python3 deployment/progetto-nmap-manet/app.py &\n')

    info('\n*** Topologia: tree,depth=3,fanout=3\n')
    info(f'*** Switch: {len(net.switches)}\n')
    info(f'*** Host: {len(net.hosts)}\n')
    info('*** Controller: remote 127.0.0.1:6653\n')
    info('*** Link: bw=100Mbps, delay=2ms\n\n')

    CLI(net)
    net.stop()


if __name__ == '__main__':
    run()
