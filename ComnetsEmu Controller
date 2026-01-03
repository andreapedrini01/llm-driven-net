"""
Topologia ComNetsEmu per LLM-Driven Network
Include configurazione container Docker per host
"""

from comnetsemu.net import Containernet, VNFManager
from mininet.node import Controller, RemoteController
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import info, setLogLevel
import time
import os


class LLMNetworkTopology:
    """
    Topologia per testing LLM-driven network con ComNetsEmu
    """
    
    def __init__(self):
        self.net = None
        self.hosts = {}
        self.switches = {}
        
    def create_topology(self):
        """Crea la topologia di rete"""
        
        info("*** Creazione topologia ComNetsEmu\n")
        
        # Inizializza Containernet (versione ComNetsEmu di Mininet)
        self.net = Containernet(
            controller=RemoteController,
            link=TCLink,
            xterms=False,
            autoSetMacs=True
        )
        
        info("*** Aggiunta controller Ryu\n")
        # Controller Ryu remoto (può essere in container separato)
        c0 = self.net.addController(
            'c0',
            controller=RemoteController,
            ip='127.0.0.1',  # O IP del container Ryu
            port=6633
        )
        
        info("*** Creazione switch OpenFlow\n")
        # Switch OpenFlow (supportano OpenFlow 1.3)
        self.switches['s1'] = self.net.addSwitch(
            's1',
            protocols='OpenFlow13',
            failMode='secure'
        )
        self.switches['s2'] = self.net.addSwitch(
            's2',
            protocols='OpenFlow13',
            failMode='secure'
        )
        self.switches['s3'] = self.net.addSwitch(
            's3',
            protocols='OpenFlow13',
            failMode='secure'
        )
        
        info("*** Aggiunta host Docker\n")
        # Host come container Docker (caratteristica unica di ComNetsEmu)
        # Questi possono eseguire applicazioni reali
        
        # Web Server Container
        self.hosts['web1'] = self.net.addDockerHost(
            'web1',
            dimage='nginx:alpine',
            ip='10.0.1.10/24',
            docker_args={
                'cpuset_cpus': '0',
                'cpu_quota': 25000,
                'mem_limit': '128m'
            }
        )
        
        # Database Container
        self.hosts['db1'] = self.net.addDockerHost(
            'db1',
            dimage='postgres:alpine',
            ip='10.0.2.10/24',
            docker_args={
                'environment': {'POSTGRES_PASSWORD': 'password'},
                'cpuset_cpus': '1',
                'cpu_quota': 50000,
                'mem_limit': '256m'
            }
        )
        
        # Application Server Container
        self.hosts['app1'] = self.net.addDockerHost(
            'app1',
            dimage='python:3.9-slim',
            ip='10.0.1.20/24',
            docker_args={
                'cpuset_cpus': '0',
                'cpu_quota': 25000,
                'mem_limit': '128m'
            }
        )
        
        # Client Container (per generare traffico)
        self.hosts['client1'] = self.net.addDockerHost(
            'client1',
            dimage='alpine:latest',
            ip='10.0.0.100/24',
            docker_args={
                'cpuset_cpus': '0',
                'cpu_quota': 25000
            }
        )
        
        # Attacker Container (per simulare attacchi)
        self.hosts['attacker'] = self.net.addDockerHost(
            'attacker',
            dimage='alpine:latest',
            ip='10.0.0.200/24',
            docker_args={
                'cpuset_cpus': '0',
                'cpu_quota': 10000
            }
        )
        
        info("*** Creazione links\n")
        # Links con QoS parameters
        self.net.addLink(
            self.hosts['web1'], 
            self.switches['s1'],
            bw=100,  # Mbps
            delay='5ms',
            loss=0,
            use_htb=True
        )
        
        self.net.addLink(
            self.hosts['app1'], 
            self.switches['s1'],
            bw=100,
            delay='5ms'
        )
        
        self.net.addLink(
            self.hosts['db1'], 
            self.switches['s2'],
            bw=100,
            delay='2ms'
        )
        
        self.net.addLink(
            self.hosts['client1'], 
            self.switches['s1'],
            bw=10,
            delay='10ms'
        )
        
        self.net.addLink(
            self.hosts['attacker'], 
            self.switches['s3'],
            bw=10,
            delay='50ms',
            loss=1
        )
        
        # Inter-switch links
        self.net.addLink(
            self.switches['s1'], 
            self.switches['s2'],
            bw=1000,
            delay='1ms'
        )
        
        self.net.addLink(
            self.switches['s2'], 
            self.switches['s3'],
            bw=1000,
            delay='1ms'
        )
        
        self.net.addLink(
            self.switches['s1'], 
            self.switches['s3'],
            bw=1000,
            delay='1ms'
        )
        
        return self.net
    
    def start_network(self):
        """Avvia la rete"""
        info("*** Avvio rete\n")
        self.net.start()
        
        # Attendi che controller e switch si connettano
        info("*** Attesa connessione controller...\n")
        time.sleep(5)
        
        info("*** Test connettività\n")
        self.net.pingAll()
    
    def setup_services(self):
        """Configura servizi nei container"""
        info("*** Setup servizi nei container\n")
        
        # Avvia nginx nel web server
        self.hosts['web1'].cmd('nginx -g "daemon off;" &')
        
        # Setup applicazione nel container app
        self.hosts['app1'].cmd('pip install flask requests &')
        
        info("*** Servizi avviati\n")
    
    def run_tests(self):
        """Esegue test della rete"""
        info("\n*** Test Scenario 1: Traffic normale\n")
        result = self.hosts['client1'].cmd('wget -O - http://10.0.1.10 2>/dev/null | head -5')
        info(f"Risposta web server: {result}\n")
        
        info("\n*** Test Scenario 2: Latenza tra host\n")
        result = self.hosts['client1'].cmd('ping -c 3 10.0.2.10')
        info(f"{result}\n")
        
        info("\n*** Test Scenario 3: Bandwidth test\n")
        # Avvia iperf server su web1
        self.hosts['web1'].cmd('iperf -s &')
        time.sleep(1)
        result = self.hosts['client1'].cmd('iperf -c 10.0.1.10 -t 5')
        info(f"{result}\n")
    
    def simulate_attack(self):
        """Simula attacco DDoS"""
        info("\n*** Simulazione attacco DDoS\n")
        info("Generazione traffico malevolo da attacker...\n")
        
        # Flooding attack
        self.hosts['attacker'].cmd(
            'ping -f 10.0.1.10 > /dev/null 2>&1 &'
        )
        
        info("Attacco in corso. Usa LLM per mitigare.\n")
        info("Esempio comando LLM: 'Blocca IP 10.0.0.200 su switch s1'\n")
    
    def stop_network(self):
        """Ferma la rete"""
        info("*** Stopping network\n")
        self.net.stop()


def create_docker_compose():
    """
    Crea docker-compose.yml per orchestrare controller e servizi
    """
    compose_content = """
version: '3.8'

services:
  ryu-controller:
    image: osrg/ryu
    container_name: ryu_controller
    network_mode: host
    volumes:
      - ./src/llm_network_controller.py:/app/controller.py
      - ./logs:/app/logs
    command: ryu-manager --ofp-tcp-listen-port 6633 --wsapi-port 8080 /app/controller.py
    restart: unless-stopped
    
  northbound-script:
    build:
      context: .
      dockerfile: Dockerfile.northbound
    container_name: northbound_script
    network_mode: host
    volumes:
      - ./src:/app/src
      - ./config:/app/config
      - ./logs:/app/logs
    environment:
      - RYU_HOST=localhost
      - RYU_PORT=8080
    depends_on:
      - ryu-controller
    restart: unless-stopped
    
  prometheus:
    image: prom/prometheus
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    restart: unless-stopped
    
  grafana:
    image: grafana/grafana
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-storage:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
    depends_on:
      - prometheus
    restart: unless-stopped

volumes:
  grafana-storage:
"""
    
    with open('docker-compose.yml', 'w') as f:
        f.write(compose_content)
    
    info("docker-compose.yml creato\n")


def create_dockerfile():
    """Crea Dockerfile per northbound script"""
    dockerfile_content = """
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir requests

# Copy application
COPY src/ /app/src/
COPY config/ /app/config/

# Run script
CMD ["python3", "src/northbound_script.py"]
"""
    
    with open('Dockerfile.northbound', 'w') as f:
        f.write(dockerfile_content)
    
    info("Dockerfile.northbound creato\n")


def create_monitoring_config():
    """Crea configurazione Prometheus"""
    os.makedirs('monitoring', exist_ok=True)
    
    prometheus_config = """
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'ryu-controller'
    static_configs:
      - targets: ['localhost:8080']
  
  - job_name: 'northbound-script'
    static_configs:
      - targets: ['localhost:9091']
"""
    
    with open('monitoring/prometheus.yml', 'w') as f:
        f.write(prometheus_config)
    
    info("prometheus.yml creato\n")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Funzione principale"""
    
    setLogLevel('info')
    
    # Crea topologia
    topology = LLMNetworkTopology()
    net = topology.create_topology()
    
    # Avvia rete
    topology.start_network()
    
    # Setup servizi
    topology.setup_services()
    
    # Test iniziali
    topology.run_tests()
    
    info("\n" + "="*70 + "\n")
    info("*** Rete pronta per LLM-driven management\n")
    info("="*70 + "\n")
    info("\nComandi utili:\n")
    info("  - pingall: testa connettività\n")
    info("  - links: mostra links\n")
    info("  - net: mostra topologia\n")
    info("  - client1 wget http://10.0.1.10: testa web server\n")
    info("  - xterm client1: apri terminale su host\n")
    info("\nPer simulare attacco: topology.simulate_attack()\n")
    info("Per fermare: exit o Ctrl+D\n")
    info("="*70 + "\n\n")
    
    # Avvia CLI
    CLI(net)
    
    # Cleanup
    topology.stop_network()


if __name__ == '__main__':
    # Setup file necessari
    create_docker_compose()
    create_dockerfile()
    create_monitoring_config()
    
    # Avvia topologia
    main()