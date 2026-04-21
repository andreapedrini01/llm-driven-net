"""
SecurityScanner: esegue scansioni nmap sugli host della rete SDN
tramite il web server Flask/nmap in esecuzione nel container Docker.

Il container espone GET http://<host>:<port>/scan?target=<ip>
e restituisce il JSON con i risultati nmap (inclusi script vuln).

Fornisce:
- SecurityScanner: classe principale per la scansione
- extract_host_ips: estrae IP nel range 10.0.0.x dalla topologia
- resolve_host_filter: risolve nomi Mininet in IP verificandone la presenza
"""

import logging
import os
import time
from typing import List, Dict, Optional

import requests

from llm_integration_module.models.security import NmapResult, OpenPort, NmapNotFoundError
from llm_integration_module.models.core import NetworkSnapshot

logger = logging.getLogger(__name__)

# URL base del web server nmap nel container Docker.
# Può essere sovrascritto con la variabile d'ambiente NMAP_SERVICE_URL.
DEFAULT_NMAP_SERVICE_URL = "http://localhost:5000"


class SecurityScanner:
    """Esegue scansioni nmap sugli host della rete SDN via web server Docker."""

    def __init__(self, timeout: int = 120):
        """
        Args:
            timeout: Timeout HTTP in secondi per ciascun host (default 120).
                     Può essere sovrascritto dalla variabile d'ambiente SECURITY_SCAN_TIMEOUT.
        """
        env_timeout = os.environ.get("SECURITY_SCAN_TIMEOUT")
        if env_timeout is not None:
            try:
                self.timeout = int(env_timeout)
            except ValueError:
                logger.warning(
                    "SECURITY_SCAN_TIMEOUT='%s' non è un intero valido, uso il default %d",
                    env_timeout,
                    timeout,
                )
                self.timeout = timeout
        else:
            self.timeout = timeout

        self.nmap_service_url = os.environ.get(
            "NMAP_SERVICE_URL", DEFAULT_NMAP_SERVICE_URL
        ).rstrip("/")

    def scan(self, ip_addresses: List[str]) -> Dict[str, NmapResult]:
        """
        Esegue nmap su ciascun IP tramite il web server e restituisce i risultati.

        Logga il progresso nel formato "Scansione X/N: <ip>".
        Non solleva eccezioni per singoli host falliti: li marca come error/timeout/unreachable.

        Args:
            ip_addresses: Lista di indirizzi IP da scansionare.

        Returns:
            Dizionario {ip: NmapResult} per tutti gli IP forniti.

        Raises:
            NmapNotFoundError: se il web server nmap non è raggiungibile.
        """
        results: Dict[str, NmapResult] = {}
        total = len(ip_addresses)

        for idx, ip in enumerate(ip_addresses, start=1):
            logger.info("Scansione %d/%d: %s", idx, total, ip)
            start = time.time()
            try:
                result = self._scan_host(ip)
            except NmapNotFoundError:
                raise
            except Exception as e:
                duration = time.time() - start
                logger.warning("Errore durante la scansione di %s: %s", ip, e)
                result = NmapResult(
                    ip=ip,
                    status="error",
                    open_ports=[],
                    os_detection=None,
                    scan_duration_s=duration,
                    error_message=str(e),
                )
            results[ip] = result

        return results

    def _scan_host(self, ip: str) -> NmapResult:
        """
        Scansiona un singolo host chiamando il web server Flask/nmap.

        Args:
            ip: Indirizzo IP da scansionare.

        Returns:
            NmapResult con i dati della scansione.

        Raises:
            NmapNotFoundError: se il web server non è raggiungibile.
        """
        start = time.time()
        url = f"{self.nmap_service_url}/scan"

        try:
            response = requests.get(url, params={"target": ip}, timeout=self.timeout)
            response.raise_for_status()
        except requests.exceptions.ConnectionError as e:
            raise NmapNotFoundError(
                f"Web server nmap non raggiungibile a {self.nmap_service_url}. "
                "Assicurarsi che il container Docker sia in esecuzione."
            ) from e
        except requests.exceptions.Timeout:
            duration = time.time() - start
            logger.warning("Timeout durante la scansione di %s (>%ds)", ip, self.timeout)
            return NmapResult(
                ip=ip,
                status="timeout",
                open_ports=[],
                os_detection=None,
                scan_duration_s=duration,
                error_message=f"Timeout dopo {self.timeout}s",
            )
        except requests.exceptions.HTTPError as e:
            duration = time.time() - start
            logger.warning("Errore HTTP durante la scansione di %s: %s", ip, e)
            return NmapResult(
                ip=ip,
                status="error",
                open_ports=[],
                os_detection=None,
                scan_duration_s=duration,
                error_message=str(e),
            )

        duration = time.time() - start
        return self._parse_nmap_json(ip, response.json(), duration)

    def _parse_nmap_json(self, ip: str, data: dict, duration: float) -> NmapResult:
        """
        Parsa il JSON restituito dal web server Flask/nmap.

        Il formato è quello della libreria python-nmap:
        {
          "tcp": {
            "22": {"state": "open", "name": "ssh", "product": "OpenSSH", "version": "8.0", ...},
            ...
          },
          "status": {"state": "up", ...},
          ...
        }

        Args:
            ip: Indirizzo IP scansionato.
            data: JSON restituito dal web server.
            duration: Durata della scansione in secondi.

        Returns:
            NmapResult con i dati parsati.
        """
        # Controlla se l'host è up
        status_info = data.get("status", {})
        if status_info.get("state") == "down":
            return NmapResult(
                ip=ip,
                status="unreachable",
                open_ports=[],
                os_detection=None,
                scan_duration_s=duration,
            )

        open_ports: List[OpenPort] = []

        # Itera sui protocolli (tcp, udp)
        for protocol in ("tcp", "udp"):
            proto_data = data.get(protocol, {})
            for portid_str, port_info in proto_data.items():
                try:
                    open_ports.append(OpenPort(
                        port=int(portid_str),
                        protocol=protocol,
                        state=port_info.get("state", ""),
                        service=port_info.get("name", ""),
                        version=port_info.get("version", ""),
                    ))
                except (ValueError, TypeError) as e:
                    logger.debug("Impossibile parsare porta %s: %s", portid_str, e)

        # OS detection (presente solo se nmap ha rilevato l'OS)
        os_detection: Optional[str] = None
        osmatch = data.get("osmatch", [])
        if osmatch and isinstance(osmatch, list) and len(osmatch) > 0:
            os_detection = osmatch[0].get("name")

        return NmapResult(
            ip=ip,
            status="scanned",
            open_ports=open_ports,
            os_detection=os_detection,
            scan_duration_s=duration,
        )


def _query_ryu_hosts() -> List[str]:
    """
    Query the Ryu topology REST API for discovered hosts.

    Returns:
        List of host IPs in the 10.0.0.x range, or empty list on failure.
    """
    import os
    ryu_base = os.environ.get("RYU_BASE_URL", "http://localhost:8080")
    try:
        resp = requests.get(f"{ryu_base}/v1.0/topology/hosts", timeout=5)
        resp.raise_for_status()
        hosts_data = resp.json()
        ips: List[str] = []
        if isinstance(hosts_data, list):
            for host in hosts_data:
                ipv4_list = host.get("ipv4", [])
                if isinstance(ipv4_list, str):
                    ipv4_list = [ipv4_list]
                for ip in ipv4_list:
                    if ip and ip.startswith("10.0.0.") and ip not in ips:
                        ips.append(ip)
        return ips
    except Exception as e:
        logger.debug("Ryu hosts API not available: %s", e)
        return []


def extract_host_ips(snapshot: NetworkSnapshot) -> List[str]:
    """
    Extract host IPs from the network topology.

    Strategy (in order):
    1. Ryu topology REST API (/v1.0/topology/hosts) — most accurate.
    2. graph_representation 'hosts' key if populated.
    3. Port-counting heuristic: for each switch, host-facing ports are
       those NOT used by inter-switch links.  Each such port corresponds
       to one host (Mininet convention: hN -> 10.0.0.N).
    4. Last resort: assume N switches -> N hosts (original fallback).

    Args:
        snapshot: NetworkSnapshot with the current topology.

    Returns:
        List of IP addresses in the 10.0.0.x range.
    """
    topology = snapshot.topology

    # --- Strategy 1: Ryu REST API ---
    ryu_ips = _query_ryu_hosts()
    if ryu_ips:
        logger.debug("Host IPs from Ryu API: %s", ryu_ips)
        return ryu_ips

    # --- Strategy 2: graph_representation hosts ---
    ips: List[str] = []
    graph = topology.graph_representation
    if graph:
        hosts = graph.get("hosts", [])
        for host in hosts:
            ip = host.get("ip") if isinstance(host, dict) else None
            if ip and ip.startswith("10.0.0."):
                ips.append(ip)
        if ips:
            return ips

    # --- Strategy 3: port-counting heuristic ---
    # Count ports used by inter-switch links per switch
    link_ports: Dict[str, set] = {}
    for link in topology.links:
        src = link.src_dpid
        dst = link.dst_dpid
        link_ports.setdefault(src, set()).add(link.src_port)
        link_ports.setdefault(dst, set()).add(link.dst_port)

    total_host_ports = 0
    for switch in topology.switches:
        switch_link_ports = link_ports.get(switch.dpid, set())
        host_ports = [p for p in switch.ports if p not in switch_link_ports]
        total_host_ports += len(host_ports)

    if total_host_ports > 0:
        for i in range(1, total_host_ports + 1):
            ips.append(f"10.0.0.{i}")
        logger.debug(
            "Host IPs from port-counting heuristic (%d host-facing ports): %s",
            total_host_ports, ips,
        )
        return ips

    # --- Strategy 4: last resort fallback ---
    num_switches = len(topology.switches)
    for i in range(1, num_switches + 1):
        ips.append(f"10.0.0.{i}")

    return ips


def resolve_host_filter(host_filter: List[str], snapshot: NetworkSnapshot) -> List[str]:
    """
    Risolve nomi Mininet (es. h1 → 10.0.0.1) in indirizzi IP, verificando
    che siano presenti nella topologia.

    Args:
        host_filter: Lista di nomi host Mininet (es. ["h1", "h2"]) o IP diretti.
        snapshot: NetworkSnapshot con la topologia corrente.

    Returns:
        Lista di indirizzi IP validi (presenti nella topologia).
    """
    available_ips = set(extract_host_ips(snapshot))
    resolved: List[str] = []

    for entry in host_filter:
        # Risolve nome Mininet hN → 10.0.0.N
        if entry.startswith("h") and entry[1:].isdigit():
            n = int(entry[1:])
            ip = f"10.0.0.{n}"
        else:
            # Assume sia già un IP
            ip = entry

        if ip in available_ips:
            resolved.append(ip)
        else:
            logger.warning(
                "Host '%s' (IP: %s) non trovato nella topologia corrente, ignorato.",
                entry,
                ip,
            )

    return resolved
