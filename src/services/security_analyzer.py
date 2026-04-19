"""SecurityAnalyzer: costruisce il prompt e chiama ChatGPTClient per l'analisi di sicurezza."""

import asyncio
import json
import logging
import time
from typing import List

from src.models.security import SecuritySnapshot, SecurityReport
from src.services.chatgpt_client import ChatGPTClient

logger = logging.getLogger(__name__)

SYSTEM_MESSAGE = (
    "You are a senior network security analyst specializing in SDN environments.\n"
    "You will receive an SDN topology, aggregated traffic metrics, and nmap scan results.\n"
    "\n"
    "Your task:\n"
    "1. Cross-correlate the data: an open port on a host with abnormal traffic is more critical\n"
    "   than an open port on an idle host.\n"
    "2. Classify each finding by severity (CRITICAL / HIGH / MEDIUM / LOW).\n"
    "3. Provide a concrete remediation action for every vulnerability and configuration issue.\n"
    "4. Explicitly list hosts with NO open ports as compliant.\n"
    "\n"
    "Respond EXCLUSIVELY with valid JSON in this exact structure:\n"
    "{\n"
    '  "vulnerabilities": [\n'
    '    "[SEVERITY] host <ip>: <description> — Remediation: <action>",\n'
    '    "..."\n'
    "  ],\n"
    '  "configuration_issues": [\n'
    '    "[SEVERITY] <description> — Remediation: <action>",\n'
    '    "..."\n'
    "  ],\n"
    '  "security_properties": [\n'
    '    "<property to verify and how to verify it>",\n'
    '    "..."\n'
    "  ]\n"
    "}\n"
    "\n"
    "Rules:\n"
    "- Sort vulnerabilities by severity (CRITICAL first).\n"
    "- If a host has no open ports, do NOT list it under vulnerabilities; mention it in\n"
    "  security_properties as a compliant baseline.\n"
    "- Do NOT add any text before or after the JSON."
)


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
            # Handle both cases: running event loop and no event loop (Python 3.8+)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # Event loop already running: run in a separate thread
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
                # No running loop — create one explicitly for Python 3.8 compatibility
                _loop = asyncio.new_event_loop()
                asyncio.set_event_loop(_loop)
                try:
                    response = _loop.run_until_complete(
                        self.chatgpt_client.generate_response(
                            prompt=prompt,
                            system_message=SYSTEM_MESSAGE
                        )
                    )
                finally:
                    _loop.close()
        except Exception as e:
            logger.error("ChatGPTClient call error: %s", e)
            raise

        snapshot_timestamp = security_snapshot.snapshot.timestamp
        return self._parse_response(response.content, snapshot_timestamp)

    def _build_prompt(self, security_snapshot: SecuritySnapshot) -> str:
        """
        Build the user prompt. If it exceeds MAX_TOKENS_ESTIMATE,
        truncate the least relevant NmapResults (fewest open ports)
        while always keeping the full topology.
        """
        topology = security_snapshot.snapshot.topology
        metrics = security_snapshot.snapshot.metrics

        # Topology section
        switches_str = ", ".join(sw.dpid for sw in topology.switches) if topology.switches else "none"
        links_str = "; ".join(
            f"{lk.src_dpid}:{lk.src_port} -> {lk.dst_dpid}:{lk.dst_port}"
            for lk in topology.links
        ) if topology.links else "none"

        topology_section = (
            f"=== SDN TOPOLOGIA ===\n"
            f"Switch: {switches_str}\n"
            f"Link: {links_str}\n"
        )

        # Aggregated metrics section
        agg = metrics.aggregated_metrics
        if agg:
            metrics_lines = []
            for dpid, m in agg.items():
                metrics_lines.append(
                    f"  {dpid}: rx={m.total_rx_bytes}B tx={m.total_tx_bytes}B "
                    f"errors={m.total_errors} util={m.average_utilization:.2f}"
                )
            metrics_section = "=== AGGREGATED METRICS ===\n" + "\n".join(metrics_lines) + "\n"
        else:
            metrics_section = "=== AGGREGATED METRICS ===\nnone\n"

        # Nmap results section — separate hosts with findings from clean hosts
        nmap_results = list(security_snapshot.security_scan.values())

        hosts_with_ports = []
        clean_hosts = []
        for result in nmap_results:
            if result.open_ports:
                hosts_with_ports.append(result)
            else:
                clean_hosts.append(result)

        def _nmap_result_str(result) -> str:
            ports_str = ", ".join(
                f"{p.port}/{p.protocol} ({p.service}{' ' + p.version if p.version else ''})"
                for p in result.open_ports
            ) if result.open_ports else "none"
            os_str = result.os_detection or "unknown"
            return (
                f"  IP: {result.ip} | status: {result.status} | "
                f"OS: {os_str} | open ports: {ports_str}"
            )

        def _build_nmap_section(results_with_ports: List, results_clean: List) -> str:
            lines = ["=== NMAP RESULTS ==="]
            if results_with_ports:
                lines.append("-- Hosts with open ports --")
                for r in results_with_ports:
                    lines.append(_nmap_result_str(r))
            if results_clean:
                clean_ips = ", ".join(r.ip for r in results_clean)
                lines.append(f"-- Clean hosts (no open ports): {clean_ips}")
            if not results_with_ports and not results_clean:
                lines.append("none")
            return "\n".join(lines) + "\n"

        closing_instruction = (
            "\nAnalyze the topology, metrics, and nmap results above.\n"
            "Cross-correlate traffic metrics with open ports to assess risk.\n"
            "Identify vulnerabilities (with severity and remediation), "
            "configuration issues, and security properties to verify."
        )

        # Full prompt
        nmap_section = _build_nmap_section(hosts_with_ports, clean_hosts)
        prompt = topology_section + metrics_section + nmap_section + closing_instruction

        # Token estimation
        def _estimate_tokens(text: str) -> float:
            return len(text.split()) * 1.3

        if _estimate_tokens(prompt) <= self.MAX_TOKENS_ESTIMATE:
            return prompt

        # Truncation: sort by number of open ports ascending (least relevant first)
        sorted_with_ports = sorted(hosts_with_ports, key=lambda r: len(r.open_ports))

        while sorted_with_ports and _estimate_tokens(
            topology_section + metrics_section
            + _build_nmap_section(sorted_with_ports, clean_hosts)
            + closing_instruction
        ) > self.MAX_TOKENS_ESTIMATE:
            sorted_with_ports.pop(0)

        nmap_section = _build_nmap_section(sorted_with_ports, clean_hosts)
        return topology_section + metrics_section + nmap_section + closing_instruction

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
            logger.error("Failed to parse LLM response as JSON: %s", e)

        return SecurityReport(
            vulnerabilities=[],
            configuration_issues=[],
            security_properties=[],
            timestamp=time.time(),
            snapshot_timestamp=snapshot_timestamp,
            raw_response=raw,
        )
