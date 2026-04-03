"""SecurityAnalyzer: costruisce il prompt e chiama ChatGPTClient per l'analisi di sicurezza."""

import asyncio
import json
import logging
import time
from typing import List

from src.models.security import SecuritySnapshot, SecurityReport
from src.services.chatgpt_client import ChatGPTClient

logger = logging.getLogger(__name__)

SYSTEM_MESSAGE = """Sei un esperto di sicurezza di rete. Analizza la topologia SDN e i risultati nmap forniti.
Rispondi ESCLUSIVAMENTE con un JSON valido con questa struttura:
{
  "vulnerabilities": ["descrizione vulnerabilità 1", "..."],
  "configuration_issues": ["problema di configurazione 1", "..."],
  "security_properties": ["proprietà di sicurezza da verificare 1", "..."]
}
Non aggiungere testo prima o dopo il JSON."""


class SecurityAnalyzer:
    MAX_TOKENS_ESTIMATE = 12000

    def __init__(self, chatgpt_client: ChatGPTClient):
        self.chatgpt_client = chatgpt_client

    def analyze(self, security_snapshot: SecuritySnapshot) -> SecurityReport:
        """
        Costruisce il prompt, chiama ChatGPTClient,
        parsa la risposta JSON e restituisce un SecurityReport.
        Propaga le eccezioni di ChatGPTClient dopo averle loggato.
        """
        prompt = self._build_prompt(security_snapshot)
        try:
            # Gestisce sia il caso con event loop già attivo che senza
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # Event loop già attivo: crea un nuovo loop in un thread separato
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    response = pool.submit(
                        asyncio.run,
                        self.chatgpt_client.generate_response(
                            prompt=prompt,
                            system_message=SYSTEM_MESSAGE
                        )
                    ).result()
            else:
                response = asyncio.run(
                    self.chatgpt_client.generate_response(
                        prompt=prompt,
                        system_message=SYSTEM_MESSAGE
                    )
                )
        except Exception as e:
            logger.error("Errore chiamata ChatGPTClient: %s", e)
            raise

        snapshot_timestamp = security_snapshot.snapshot.timestamp
        return self._parse_response(response.content, snapshot_timestamp)

    def _build_prompt(self, security_snapshot: SecuritySnapshot) -> str:
        """
        Costruisce il prompt. Se supera MAX_TOKENS_ESTIMATE,
        tronca i NmapResult meno rilevanti (meno porte aperte) mantenendo la topologia completa.
        """
        topology = security_snapshot.snapshot.topology
        metrics = security_snapshot.snapshot.metrics

        # Sezione topologia
        switches_str = ", ".join(sw.dpid for sw in topology.switches) if topology.switches else "nessuno"
        links_str = "; ".join(
            f"{lk.src_dpid}:{lk.src_port} -> {lk.dst_dpid}:{lk.dst_port}"
            for lk in topology.links
        ) if topology.links else "nessuno"

        topology_section = (
            f"=== TOPOLOGIA SDN ===\n"
            f"Switch: {switches_str}\n"
            f"Link: {links_str}\n"
        )

        # Sezione metriche
        agg = metrics.aggregated_metrics
        if agg:
            metrics_lines = []
            for dpid, m in agg.items():
                metrics_lines.append(
                    f"  {dpid}: rx={m.total_rx_bytes}B tx={m.total_tx_bytes}B "
                    f"errors={m.total_errors} util={m.average_utilization:.2f}"
                )
            metrics_section = "=== METRICHE AGGREGATE ===\n" + "\n".join(metrics_lines) + "\n"
        else:
            metrics_section = "=== METRICHE AGGREGATE ===\nnessuna\n"

        # Sezione nmap — costruiamo le stringhe per ciascun NmapResult
        nmap_results = list(security_snapshot.security_scan.values())

        def _nmap_result_str(result) -> str:
            ports_str = ", ".join(
                f"{p.port}/{p.protocol} ({p.service}{' ' + p.version if p.version else ''})"
                for p in result.open_ports
            ) if result.open_ports else "nessuna"
            os_str = result.os_detection or "sconosciuto"
            return (
                f"  IP: {result.ip} | status: {result.status} | "
                f"OS: {os_str} | porte aperte: {ports_str}"
            )

        def _build_nmap_section(results: List) -> str:
            if not results:
                return "=== RISULTATI NMAP ===\nnessuno\n"
            lines = ["=== RISULTATI NMAP ==="]
            for r in results:
                lines.append(_nmap_result_str(r))
            return "\n".join(lines) + "\n"

        # Prompt completo con tutti i risultati
        nmap_section = _build_nmap_section(nmap_results)
        prompt = (
            topology_section
            + metrics_section
            + nmap_section
            + "\nAnalizza la topologia e i risultati nmap sopra e identifica vulnerabilità, "
            "problemi di configurazione e proprietà di sicurezza da verificare."
        )

        # Stima token
        def _estimate_tokens(text: str) -> float:
            return len(text.split()) * 1.3

        if _estimate_tokens(prompt) <= self.MAX_TOKENS_ESTIMATE:
            return prompt

        # Troncamento: ordina per numero di porte aperte crescente (meno rilevanti prima)
        sorted_results = sorted(nmap_results, key=lambda r: len(r.open_ports))

        while sorted_results and _estimate_tokens(
            topology_section + metrics_section + _build_nmap_section(sorted_results) +
            "\nAnalizza la topologia e i risultati nmap sopra e identifica vulnerabilità, "
            "problemi di configurazione e proprietà di sicurezza da verificare."
        ) > self.MAX_TOKENS_ESTIMATE:
            sorted_results.pop(0)  # rimuove il meno rilevante

        nmap_section = _build_nmap_section(sorted_results)
        return (
            topology_section
            + metrics_section
            + nmap_section
            + "\nAnalizza la topologia e i risultati nmap sopra e identifica vulnerabilità, "
            "problemi di configurazione e proprietà di sicurezza da verificare."
        )

    def _parse_response(self, raw: str, snapshot_timestamp: float) -> SecurityReport:
        """
        Parsa il JSON della risposta LLM.
        In caso di JSON non valido, restituisce SecurityReport con liste vuote e raw_response popolato.
        """
        try:
            start = raw.find('{')
            end = raw.rfind('}')
            if start != -1 and end != -1:
                json_str = raw[start:end + 1]
                data = json.loads(json_str)
                return SecurityReport(
                    vulnerabilities=data.get("vulnerabilities", []),
                    configuration_issues=data.get("configuration_issues", []),
                    security_properties=data.get("security_properties", []),
                    timestamp=time.time(),
                    snapshot_timestamp=snapshot_timestamp,
                    raw_response=None,
                )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Impossibile parsare la risposta LLM come JSON: %s", e)

        return SecurityReport(
            vulnerabilities=[],
            configuration_issues=[],
            security_properties=[],
            timestamp=time.time(),
            snapshot_timestamp=snapshot_timestamp,
            raw_response=raw,
        )
