#!/usr/bin/env python3
"""
Ring topology with data-center-style clusters.

Layout (default core_switches=4, hosts_per_cluster=3):

                    [s1]---h1,h2,h3
                   /    \\
                  /      \\
  h10,h11,h12--[s4]      [s2]---h4,h5,h6
                  \\      /
                   \\    /
                    [s3]---h7,h8,h9
                     |
                 [scanner]  (Docker, if available)

The core switches form a ring (s1-s2-s3-s4-s1).
Each core switch has a cluster of hosts attached directly.

Good for testing:
  - Redundant paths (traffic can go clockwise or counter-clockwise)
  - Load balancing across multiple paths
  - Security scanning of isolated clusters
  - Slice creation between clusters on different ring segments
  - Topology discovery with loops (STP / controller handling)

Usage:
  sudo python3 topology_ring.py
  sudo python3 topology_ring.py --core-switches 6 --hosts-per-cluster 4
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


def build_ring(net, num_core, hosts_per_cluster):
    """
    Build a ring of core switches, each with a cluster of hosts.
    Returns the list of core switches and total host count.
    """
    core_switches = []
    host_counter = 0

    # Create core switches and their host clusters
    for i in range(1, num_core + 1):
        sw = net.addSwitch(f's{i}', protocols='OpenFlow13')
        core_switches.append(sw)

        for _ in range(hosts_per_cluster):
            host_counter += 1
            h = net.addHost(f'h{host_counter}', ip=f'10.0.0.{host_counter}/24')
            net.addLink(h, sw, bw=100, delay='1ms', cls=TCLink)

    # Connect core switches in a ring: s1-s2, s2-s3, ..., sN-s1
    for i in range(len(core_switches)):
        next_i = (i + 1) % len(core_switches)
        net.addLink(
            core_switches[i], core_switches[next_i],
            bw=1000, delay='2ms', cls=TCLink
        )

    return core_switches, host_counter


def run():
    parser = argparse.ArgumentParser(
        description='Ring topology with clusters for llm-driven-net'
    )
    parser.add_argument('--core-switches', type=int, default=4,
                        help='Number of core switches in the ring (default: 4)')
    parser.add_argument('--hosts-per-cluster', type=int, default=3,
                        help='Hosts per cluster on each core switch (default: 3)')
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

    info(f'*** Building ring topology: {args.core_switches} core switches, '
         f'{args.hosts_per_cluster} hosts per cluster\n')
    core_switches, total_hosts = build_ring(
        net, args.core_switches, args.hosts_per_cluster
    )

    # Add Docker scanner host on the last core switch
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
            # Attach scanner to the last core switch
            net.addLink(scanner, core_switches[-1], bw=100, delay='1ms', cls=TCLink)
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
