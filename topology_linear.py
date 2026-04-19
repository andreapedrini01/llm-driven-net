#!/usr/bin/env python3
"""
Linear topology: chain of switches, each with a configurable number of hosts.

Layout (default switches=6, hosts_per_switch=2):

  h1 h2     h3 h4     h5 h6     h7 h8     h9 h10    h11 h12
   | |       | |       | |       | |       | |        |  |
  [s1]------[s2]------[s3]------[s4]------[s5]------[s6]
                                                      |
                                                  [scanner]  (Docker, if available)

Good for testing:
  - Multi-hop path latency (traffic from h1 to h12 crosses 5 switches)
  - Flow rule installation on specific switches
  - Bandwidth slicing between distant hosts
  - Intent-driven routing changes

Usage:
  sudo python3 topology_linear.py
  sudo python3 topology_linear.py --switches 8 --hosts-per-switch 3
"""

import argparse
import sys
import traceback
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info

# Try to import Containernet
HAS_CONTAINERNET = False
try:
    from comnetsemu.net import Containernet
    HAS_CONTAINERNET = True
except ImportError:
    pass

if not HAS_CONTAINERNET:
    from mininet.net import Mininet


def build_linear(net, num_switches, hosts_per_switch):
    """
    Build a linear chain of switches, each with `hosts_per_switch` hosts.
    Returns the list of switches created.
    """
    switches = []
    host_counter = 0

    for i in range(1, num_switches + 1):
        sw = net.addSwitch(f's{i}', protocols='OpenFlow13')
        switches.append(sw)

        # Attach hosts to this switch
        for _ in range(hosts_per_switch):
            host_counter += 1
            h = net.addHost(f'h{host_counter}', ip=f'10.0.0.{host_counter}/24')
            net.addLink(h, sw, bw=100, delay='1ms', cls=TCLink)

    # Chain switches together: s1--s2--s3--...--sN
    for i in range(len(switches) - 1):
        net.addLink(switches[i], switches[i + 1], bw=100, delay='5ms', cls=TCLink)

    return switches, host_counter


def run():
    parser = argparse.ArgumentParser(description='Linear topology for llm-driven-net')
    parser.add_argument('--switches', type=int, default=6,
                        help='Number of switches in the chain (default: 6)')
    parser.add_argument('--hosts-per-switch', type=int, default=2,
                        help='Hosts attached to each switch (default: 2)')
    args = parser.parse_args()

    setLogLevel('info')

    info(f'*** HAS_CONTAINERNET = {HAS_CONTAINERNET}\n')

    if HAS_CONTAINERNET:
        info('*** Using Containernet\n')
        net = Containernet(
            controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6653),
            switch=OVSKernelSwitch,
            autoSetMacs=True,
        )
    else:
        info('*** Using Mininet (no Docker)\n')
        net = Mininet(
            controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6653),
            switch=OVSKernelSwitch,
            autoSetMacs=True,
        )

    net.addController('c0')

    info(f'*** Building linear topology: {args.switches} switches, '
         f'{args.hosts_per_switch} hosts each\n')
    switches, total_hosts = build_linear(net, args.switches, args.hosts_per_switch)

    # Add Docker scanner host on the last switch
    scanner_added = False
    if HAS_CONTAINERNET:
        info('*** Attempting to add Docker scanner host...\n')
        try:
            scanner = net.addDockerHost(
                'scanner',
                dimage='progetto-nmap-manet',
                ip='10.0.0.100/24',
                docker_args={
                    'ports': {'5000/tcp': 5000},
                    'publish_all_ports': True,
                },
            )
            net.addLink(scanner, switches[-1], bw=100, delay='1ms', cls=TCLink)
            scanner_added = True
            info('*** Docker scanner host added successfully\n')
        except Exception as e:
            info(f'*** ERROR adding Docker scanner: {e}\n')
            traceback.print_exc()

    net.start()

    if scanner_added:
        info('*** Starting Flask in scanner container...\n')
        scanner_node = net.get('scanner')
        scanner_node.cmd('cd /app && python app.py &')
        import time
        time.sleep(2)
        info('*** Scanner Docker at 10.0.0.100:5000\n')
        info('*** Test: scanner curl http://10.0.0.100:5000/scan?target=10.0.0.1\n')
    else:
        info('*** Docker scanner NOT added.\n')
        if HAS_CONTAINERNET:
            info('*** Build image first: docker build -t progetto-nmap-manet '
                 'deployment/progetto-nmap-manet/\n')
        else:
            info('*** Containernet not available. Start Flask manually:\n')
            info(f'***   h{total_hosts} python3 deployment/progetto-nmap-manet/app.py &\n')

    info(f'\n*** Switches: {len(net.switches)}, Hosts: {len(net.hosts)}\n\n')

    CLI(net)
    net.stop()


if __name__ == '__main__':
    run()
