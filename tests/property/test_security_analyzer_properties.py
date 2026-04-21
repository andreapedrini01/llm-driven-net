"""
Property-based test per SecurityAnalyzer.

Proprietà implementate:
- Proprietà 6: Completezza del prompt (Requisito 3.1)
- Proprietà 7: Prompt entro il limite di token (Requisito 3.6)
- Proprietà 8: Parsing della risposta LLM valida (Requisito 3.3)
"""

import json
from unittest.mock import MagicMock, AsyncMock

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from llm_integration_module.models.security import (
    SecuritySnapshot, NmapResult, OpenPort, SecurityReport
)
from llm_integration_module.models.core import (
    NetworkSnapshot, TopologyData, MetricsData, SwitchInfo, LinkInfo,
    AggregatedMetrics
)
from llm_integration_module.services.security_analyzer import SecurityAnalyzer
from llm_integration_module.services.chatgpt_client import ChatGPTResponse
from datetime import datetime


# ---------------------------------------------------------------------------
# Generatori
# ---------------------------------------------------------------------------

@st.composite
def ip_addresses(draw):
    """Genera indirizzi IP nel range 10.0.0.x."""
    n = draw(st.integers(min_value=1, max_value=254))
    return f"10.0.0.{n}"


@st.composite
def open_ports(draw):
    port = draw(st.integers(min_value=1, max_value=65535))
    protocol = draw(st.sampled_from(["tcp", "udp"]))
    service = draw(st.text(alphabet=st.characters(whitelist_categories=("Ll",)), min_size=1, max_size=10))
    version = draw(st.text(alphabet=st.characters(whitelist_categories=("Ll", "Nd")), max_size=10))
    return OpenPort(port=port, protocol=protocol, state="open", service=service, version=version)


@st.composite
def nmap_results(draw, ip=None):
    if ip is None:
        ip = draw(ip_addresses())
    status = draw(st.sampled_from(["scanned", "unreachable", "timeout", "error"]))
    ports = draw(st.lists(open_ports(), max_size=10)) if status == "scanned" else []
    return NmapResult(
        ip=ip,
        status=status,
        open_ports=ports,
        os_detection=draw(st.one_of(st.none(), st.just("Linux"), st.just("Windows"))),
        scan_duration_s=draw(st.floats(min_value=0.0, max_value=10.0, allow_nan=False)),
    )


@st.composite
def switch_infos(draw):
    dpid_int = draw(st.integers(min_value=1, max_value=0xFFFFFFFFFFFFFFFF))
    dpid = f"{dpid_int:016x}"
    ports = draw(st.lists(st.integers(min_value=1, max_value=48), max_size=8, unique=True))
    return SwitchInfo(dpid=dpid, ports=ports)


@st.composite
def link_infos(draw, switches):
    if len(switches) < 2:
        src = switches[0]
        dst = switches[0]
    else:
        src, dst = draw(st.sampled_from(switches)), draw(st.sampled_from(switches))
    return LinkInfo(
        src_dpid=src.dpid,
        dst_dpid=dst.dpid,
        src_port=draw(st.integers(min_value=1, max_value=48)),
        dst_port=draw(st.integers(min_value=1, max_value=48)),
    )


@st.composite
def topology_data(draw):
    switches = draw(st.lists(switch_infos(), min_size=1, max_size=5))
    links = draw(st.lists(link_infos(switches), max_size=5))
    return TopologyData(switches=switches, links=links)


@st.composite
def metrics_data(draw):
    return MetricsData(port_statistics={}, aggregated_metrics={})


@st.composite
def network_snapshots(draw):
    return NetworkSnapshot(
        timestamp=draw(st.floats(min_value=0.0, max_value=1e12, allow_nan=False)),
        topology=draw(topology_data()),
        metrics=draw(metrics_data()),
    )


@st.composite
def security_snapshots(draw):
    snapshot = draw(network_snapshots())
    ips = draw(st.lists(ip_addresses(), min_size=0, max_size=10, unique=True))
    scan = {}
    for ip in ips:
        scan[ip] = draw(nmap_results(ip=ip))
    return SecuritySnapshot(snapshot=snapshot, security_scan=scan)


@st.composite
def security_snapshots_nonempty(draw):
    snapshot = draw(network_snapshots())
    ips = draw(st.lists(ip_addresses(), min_size=1, max_size=10, unique=True))
    scan = {}
    for ip in ips:
        scan[ip] = draw(nmap_results(ip=ip))
    return SecuritySnapshot(snapshot=snapshot, security_scan=scan)


@st.composite
def valid_llm_json(draw):
    """Genera un JSON valido con i tre campi attesi dall'LLM."""
    vulnerabilities = draw(st.lists(
        st.text(alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd", "Zs")), min_size=1, max_size=50),
        max_size=5
    ))
    configuration_issues = draw(st.lists(
        st.text(alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd", "Zs")), min_size=1, max_size=50),
        max_size=5
    ))
    security_properties = draw(st.lists(
        st.text(alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd", "Zs")), min_size=1, max_size=50),
        max_size=5
    ))
    return {
        "vulnerabilities": vulnerabilities,
        "configuration_issues": configuration_issues,
        "security_properties": security_properties,
    }


def _make_analyzer() -> SecurityAnalyzer:
    client = MagicMock()
    return SecurityAnalyzer(chatgpt_client=client)


# ---------------------------------------------------------------------------
# Proprietà 6: Completezza del prompt
# Feature: collect-security-scan, Property 6
# Validates: Requirements 3.1
# ---------------------------------------------------------------------------

class TestPromptCompleteness:
    """
    Proprietà 6: Completezza del prompt

    Per qualsiasi SecuritySnapshot, il prompt costruito da _build_prompt()
    deve contenere la topologia (switch e link) e gli indirizzi IP di tutti
    i NmapResult presenti nel security_scan.

    **Validates: Requirements 3.1**
    """

    @given(sec_snapshot=security_snapshots_nonempty())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_prompt_contains_all_nmap_ips(self, sec_snapshot):
        # Feature: collect-security-scan, Property 6
        analyzer = _make_analyzer()
        prompt = analyzer._build_prompt(sec_snapshot)

        for ip in sec_snapshot.security_scan:
            assert ip in prompt, f"IP {ip} non trovato nel prompt"

    @given(sec_snapshot=security_snapshots_nonempty())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_prompt_contains_topology_switches(self, sec_snapshot):
        # Feature: collect-security-scan, Property 6
        analyzer = _make_analyzer()
        prompt = analyzer._build_prompt(sec_snapshot)

        for switch in sec_snapshot.snapshot.topology.switches:
            assert switch.dpid in prompt, f"Switch DPID {switch.dpid} non trovato nel prompt"

    @given(sec_snapshot=security_snapshots())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_prompt_contains_topology_section(self, sec_snapshot):
        # Feature: collect-security-scan, Property 6
        analyzer = _make_analyzer()
        prompt = analyzer._build_prompt(sec_snapshot)

        assert "TOPOLOGIA" in prompt or "topologia" in prompt.lower()


# ---------------------------------------------------------------------------
# Proprietà 7: Prompt entro il limite di token
# Feature: collect-security-scan, Property 7
# Validates: Requirements 3.6
# ---------------------------------------------------------------------------

class TestPromptTokenLimit:
    """
    Proprietà 7: Prompt entro il limite di token

    Per qualsiasi SecuritySnapshot, il prompt costruito da _build_prompt()
    deve avere una stima token non superiore a 12000.
    Se il contenuto supera il limite, la topologia deve essere sempre inclusa.

    **Validates: Requirements 3.6**
    """

    @given(sec_snapshot=security_snapshots())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_prompt_within_token_limit(self, sec_snapshot):
        # Feature: collect-security-scan, Property 7
        analyzer = _make_analyzer()
        prompt = analyzer._build_prompt(sec_snapshot)

        estimated_tokens = len(prompt.split()) * 1.3
        assert estimated_tokens <= SecurityAnalyzer.MAX_TOKENS_ESTIMATE, (
            f"Stima token {estimated_tokens:.0f} supera il limite {SecurityAnalyzer.MAX_TOKENS_ESTIMATE}"
        )

    @given(sec_snapshot=security_snapshots_nonempty())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_topology_always_included_after_truncation(self, sec_snapshot):
        # Feature: collect-security-scan, Property 7
        analyzer = _make_analyzer()
        prompt = analyzer._build_prompt(sec_snapshot)

        # La topologia deve sempre essere presente
        for switch in sec_snapshot.snapshot.topology.switches:
            assert switch.dpid in prompt, (
                f"Switch DPID {switch.dpid} mancante dopo eventuale troncamento"
            )


# ---------------------------------------------------------------------------
# Proprietà 8: Parsing della risposta LLM valida
# Feature: collect-security-scan, Property 8
# Validates: Requirements 3.3
# ---------------------------------------------------------------------------

class TestParseValidLlmResponse:
    """
    Proprietà 8: Parsing della risposta LLM valida

    Per qualsiasi stringa JSON valida con i campi vulnerabilities,
    configuration_issues e security_properties (liste di stringhe),
    _parse_response() deve produrre un SecurityReport con quei campi
    popolati correttamente e raw_response pari a None.

    **Validates: Requirements 3.3**
    """

    @given(data=valid_llm_json())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_valid_json_raw_response_is_none(self, data):
        # Feature: collect-security-scan, Property 8
        analyzer = _make_analyzer()
        raw = json.dumps(data)
        report = analyzer._parse_response(raw, snapshot_timestamp=1000.0)

        assert report.raw_response is None

    @given(data=valid_llm_json())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_valid_json_vulnerabilities_populated(self, data):
        # Feature: collect-security-scan, Property 8
        analyzer = _make_analyzer()
        raw = json.dumps(data)
        report = analyzer._parse_response(raw, snapshot_timestamp=1000.0)

        assert report.vulnerabilities == data["vulnerabilities"]

    @given(data=valid_llm_json())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_valid_json_configuration_issues_populated(self, data):
        # Feature: collect-security-scan, Property 8
        analyzer = _make_analyzer()
        raw = json.dumps(data)
        report = analyzer._parse_response(raw, snapshot_timestamp=1000.0)

        assert report.configuration_issues == data["configuration_issues"]

    @given(data=valid_llm_json())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_valid_json_security_properties_populated(self, data):
        # Feature: collect-security-scan, Property 8
        analyzer = _make_analyzer()
        raw = json.dumps(data)
        report = analyzer._parse_response(raw, snapshot_timestamp=1000.0)

        assert report.security_properties == data["security_properties"]

    @given(data=valid_llm_json())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_valid_json_with_surrounding_text(self, data):
        # Feature: collect-security-scan, Property 8
        # Il parser deve funzionare anche con testo attorno al JSON
        analyzer = _make_analyzer()
        raw = f"Ecco l'analisi:\n{json.dumps(data)}\nFine."
        report = analyzer._parse_response(raw, snapshot_timestamp=1000.0)

        assert report.raw_response is None
        assert report.vulnerabilities == data["vulnerabilities"]

    @given(data=valid_llm_json())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_valid_json_snapshot_timestamp_preserved(self, data):
        # Feature: collect-security-scan, Property 8
        analyzer = _make_analyzer()
        raw = json.dumps(data)
        ts = 42.0
        report = analyzer._parse_response(raw, snapshot_timestamp=ts)

        assert report.snapshot_timestamp == ts
