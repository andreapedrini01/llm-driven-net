"""
SecurityScanner: esegue scansioni nmap sugli host della rete SDN.

Fornisce:
- SecurityScanner: classe principale per la scansione
- extract_host_ips: estrae IP nel range 10.0.0.x dalla topologia
- resolve_host_filter: risolve nomi Mininet in IP verificandone la presenza
"""

import subprocess
import xml.etree.ElementTree as ET
import logging
import os
import time
from typing import List, Dict, Optional

from src.models.security import NmapResult, OpenPort, NmapNotFoundError
from src.models.core import NetworkSnapshot

logger = logging.getLogger(__name__)


class SecurityScanner:
    """Esegue scansioni nmap sugli host della rete SDN."""

    def __init__(self, timeout: int = 120):
        """
        Args:
            timeout: Timeout in secondi per ciascun host (default 120).
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

    def scan(self, ip_addresses: List[str]) -> Dict[str, NmapResult]:
        """
        Esegue nmap su ciascun IP e restituisce i risultati indicizzati per IP.

        Logga il progresso nel formato "Scansione X/N: <ip>".
        Non solleva eccezioni per singoli host falliti: li marca come error/timeout/unreachable.

        Args:
            ip_addresses: Lista di indirizzi IP da scansionare.

        Returns:
            Dizionario {ip: NmapResult} per tutti gli IP forniti.

        Raises:
            NmapNotFoundError: se nmap non è installato sul sistema.
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
        Scansiona un singolo host con subprocess e timeout.

        Args:
            ip: Indirizzo IP da scansionare.

        Returns:
            NmapResult con i dati della scansione.

        Raises:
            NmapNotFoundError: se nmap non è installato.
        """
        start = time.time()
        try:
            proc = subprocess.run(
                ["nmap", "-sV", "-oX", "-", ip],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
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
        except FileNotFoundError:
            raise NmapNotFoundError(
                "nmap non trovato. Assicurarsi che nmap sia installato e nel PATH."
            )
        except subprocess.CalledProcessError as e:
            duration = time.time() - start
            logger.warning("CalledProcessError durante la scansione di %s: %s", ip, e)
            return NmapResult(
                ip=ip,
                status="error",
                open_ports=[],
                os_detection=None,
                scan_duration_s=duration,
                error_message=str(e),
            )
        except Exception as e:
            duration = time.time() - start
            logger.warning("Errore imprevisto durante la scansione di %s: %s", ip, e)
            return NmapResult(
                ip=ip,
                status="error",
                open_ports=[],
                os_detection=None,
                scan_duration_s=duration,
                error_message=str(e),
            )

        duration = time.time() - start
        return self._parse_nmap_output(ip, proc.stdout, duration)

    def _parse_nmap_output(self, ip: str, xml_output: str, duration: float) -> NmapResult:
        """
        Parsa l'output XML di nmap e restituisce un NmapResult.

        Args:
            ip: Indirizzo IP scansionato.
            xml_output: Output XML di nmap (stdout).
            duration: Durata della scansione in secondi.

        Returns:
            NmapResult con i dati parsati.
        """
        try:
            root = ET.fromstring(xml_output)
        except ET.ParseError as e:
            logger.warning("Impossibile parsare l'output XML di nmap per %s: %s", ip, e)
            return NmapResult(
                ip=ip,
                status="error",
                open_ports=[],
                os_detection=None,
                scan_duration_s=duration,
                error_message=f"XML parse error: {e}",
            )

        for host in root.findall("host"):
            status_elem = host.find("status")
            host_status = status_elem.get("state") if status_elem is not None else "unknown"

            if host_status == "down":
                return NmapResult(
                    ip=ip,
                    status="unreachable",
                    open_ports=[],
                    os_detection=None,
                    scan_duration_s=duration,
                )

            # Raccoglie le porte aperte
            open_ports: List[OpenPort] = []
            ports_elem = host.find("ports")
            if ports_elem is not None:
                for port in ports_elem.findall("port"):
                    state_elem = port.find("state")
                    state = state_elem.get("state") if state_elem is not None else ""
                    service_elem = port.find("service")
                    open_ports.append(
                        OpenPort(
                            port=int(port.get("portid", 0)),
                            protocol=port.get("protocol", ""),
                            state=state,
                            service=service_elem.get("name", "") if service_elem is not None else "",
                            version=service_elem.get("version", "") if service_elem is not None else "",
                        )
                    )

            # OS detection (richiede -O, normalmente None senza privilegi root)
            os_detection: Optional[str] = None
            os_elem = host.find("os")
            if os_elem is not None:
                osmatch = os_elem.find("osmatch")
                if osmatch is not None:
                    os_detection = osmatch.get("name")

            return NmapResult(
                ip=ip,
                status="scanned",
                open_ports=open_ports,
                os_detection=os_detection,
                scan_duration_s=duration,
            )

        # Nessun host trovato nell'output XML
        return NmapResult(
            ip=ip,
            status="unreachable",
            open_ports=[],
            os_detection=None,
            scan_duration_s=duration,
        )


def extract_host_ips(snapshot: NetworkSnapshot) -> List[str]:
    """
    Estrae gli indirizzi IP nel range 10.0.0.x dalla topologia del NetworkSnapshot.

    La convenzione Mininet assegna IP 10.0.0.N agli host hN.
    Gli IP vengono derivati dal numero di switch presenti nella topologia
    (ogni switch corrisponde a un host nella topologia Mininet standard).

    Args:
        snapshot: NetworkSnapshot con la topologia corrente.

    Returns:
        Lista di indirizzi IP nel range 10.0.0.x.
    """
    topology = snapshot.topology
    ips: List[str] = []

    # Usa graph_representation se disponibile
    graph = topology.graph_representation
    if graph:
        hosts = graph.get("hosts", [])
        for host in hosts:
            ip = host.get("ip") if isinstance(host, dict) else None
            if ip and ip.startswith("10.0.0."):
                ips.append(ip)
        if ips:
            return ips

    # Fallback: deriva gli IP dal numero di switch (convenzione Mininet)
    # In una topologia Mininet standard, N switch → N host con IP 10.0.0.1..N
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
