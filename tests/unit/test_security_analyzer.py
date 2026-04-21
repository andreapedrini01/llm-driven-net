"""
Unit test per SecurityAnalyzer.

Casi coperti:
- Risposta LLM non JSON → raw_response popolato, liste vuote
- System message corretto (contiene i tre campi JSON)
- Eccezione ChatGPTClient propagata
- Risposta JSON valida → SecurityReport con campi popolati e raw_response=None
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from llm_integration_module.models.security import (
    SecuritySnapshot, SecurityReport, NmapResult, OpenPort
)
from llm_integration_module.models.core import (
    NetworkSnapshot, TopologyData, MetricsData, SwitchInfo, LinkInfo
)
from llm_integration_module.services.security_analyzer import SecurityAnalyzer, SYSTEM_MESSAGE
from llm_integration_module.services.chatgpt_client import ChatGPTResponse
from datetime import datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_snapshot(nmap_results=None) -> SecuritySnapshot:
    topology = TopologyData(
        switches=[SwitchInfo(dpid="1", ports=[1, 2])],
        links=[LinkInfo(src_dpid="1", dst_dpid="1", src_port=1, dst_port=2)],
    )
    metrics = MetricsData(port_statistics={}, aggregated_metrics={})
    snapshot = NetworkSnapshot(
        timestamp=1000.0,
        topology=topology,
        metrics=metrics,
    )
    if nmap_results is None:
        nmap_results = {
            "10.0.0.1": NmapResult(
                ip="10.0.0.1",
                status="scanned",
                open_ports=[OpenPort(port=22, protocol="tcp", state="open", service="ssh")],
                os_detection=None,
                scan_duration_s=1.0,
            )
        }
    return SecuritySnapshot(snapshot=snapshot, security_scan=nmap_results)


def _make_chatgpt_response(content: str) -> ChatGPTResponse:
    return ChatGPTResponse(
        content=content,
        model="gpt-test",
        tokens_used=10,
        latency=0.1,
        finish_reason="stop",
        timestamp=datetime.now(),
    )


def _make_analyzer(response_content: str) -> SecurityAnalyzer:
    """Crea un SecurityAnalyzer con ChatGPTClient mockato."""
    client = MagicMock()
    client.generate_response = AsyncMock(return_value=_make_chatgpt_response(response_content))
    return SecurityAnalyzer(chatgpt_client=client)


# ---------------------------------------------------------------------------
# Test: risposta LLM non JSON → raw_response popolato, liste vuote
# ---------------------------------------------------------------------------

class TestNonJsonResponse:
    def test_non_json_response_returns_empty_lists(self):
        analyzer = _make_analyzer("Questo non è JSON valido.")
        snapshot = _make_snapshot()
        report = analyzer.analyze(snapshot)

        assert report.vulnerabilities == []
        assert report.configuration_issues == []
        assert report.security_properties == []

    def test_non_json_response_populates_raw_response(self):
        raw = "Questo non è JSON valido."
        analyzer = _make_analyzer(raw)
        snapshot = _make_snapshot()
        report = analyzer.analyze(snapshot)

        assert report.raw_response == raw

    def test_empty_string_response(self):
        analyzer = _make_analyzer("")
        snapshot = _make_snapshot()
        report = analyzer.analyze(snapshot)

        assert report.vulnerabilities == []
        assert report.raw_response == ""


# ---------------------------------------------------------------------------
# Test: system message corretto
# ---------------------------------------------------------------------------

class TestSystemMessage:
    def test_system_message_contains_vulnerabilities(self):
        assert "vulnerabilities" in SYSTEM_MESSAGE

    def test_system_message_contains_configuration_issues(self):
        assert "configuration_issues" in SYSTEM_MESSAGE

    def test_system_message_contains_security_properties(self):
        assert "security_properties" in SYSTEM_MESSAGE

    def test_system_message_passed_to_client(self):
        client = MagicMock()
        valid_json = '{"vulnerabilities": [], "configuration_issues": [], "security_properties": []}'
        client.generate_response = AsyncMock(return_value=_make_chatgpt_response(valid_json))
        analyzer = SecurityAnalyzer(chatgpt_client=client)
        snapshot = _make_snapshot()

        analyzer.analyze(snapshot)

        call_kwargs = client.generate_response.call_args
        assert call_kwargs.kwargs.get("system_message") == SYSTEM_MESSAGE


# ---------------------------------------------------------------------------
# Test: eccezione ChatGPTClient propagata
# ---------------------------------------------------------------------------

class TestExceptionPropagation:
    def test_exception_is_propagated(self):
        client = MagicMock()
        client.generate_response = AsyncMock(side_effect=RuntimeError("API error"))
        analyzer = SecurityAnalyzer(chatgpt_client=client)
        snapshot = _make_snapshot()

        with pytest.raises(RuntimeError, match="API error"):
            analyzer.analyze(snapshot)

    def test_exception_type_preserved(self):
        client = MagicMock()
        client.generate_response = AsyncMock(side_effect=ValueError("bad value"))
        analyzer = SecurityAnalyzer(chatgpt_client=client)
        snapshot = _make_snapshot()

        with pytest.raises(ValueError):
            analyzer.analyze(snapshot)


# ---------------------------------------------------------------------------
# Test: risposta JSON valida → SecurityReport con campi popolati e raw_response=None
# ---------------------------------------------------------------------------

class TestValidJsonResponse:
    def test_valid_json_populates_vulnerabilities(self):
        content = '{"vulnerabilities": ["vuln1", "vuln2"], "configuration_issues": [], "security_properties": []}'
        analyzer = _make_analyzer(content)
        report = analyzer.analyze(_make_snapshot())

        assert report.vulnerabilities == ["vuln1", "vuln2"]

    def test_valid_json_populates_configuration_issues(self):
        content = '{"vulnerabilities": [], "configuration_issues": ["issue1"], "security_properties": []}'
        analyzer = _make_analyzer(content)
        report = analyzer.analyze(_make_snapshot())

        assert report.configuration_issues == ["issue1"]

    def test_valid_json_populates_security_properties(self):
        content = '{"vulnerabilities": [], "configuration_issues": [], "security_properties": ["prop1", "prop2"]}'
        analyzer = _make_analyzer(content)
        report = analyzer.analyze(_make_snapshot())

        assert report.security_properties == ["prop1", "prop2"]

    def test_valid_json_raw_response_is_none(self):
        content = '{"vulnerabilities": ["v"], "configuration_issues": ["c"], "security_properties": ["p"]}'
        analyzer = _make_analyzer(content)
        report = analyzer.analyze(_make_snapshot())

        assert report.raw_response is None

    def test_json_with_surrounding_text_is_parsed(self):
        content = 'Ecco il risultato:\n{"vulnerabilities": ["v1"], "configuration_issues": [], "security_properties": []}\nFine.'
        analyzer = _make_analyzer(content)
        report = analyzer.analyze(_make_snapshot())

        assert report.vulnerabilities == ["v1"]
        assert report.raw_response is None

    def test_snapshot_timestamp_preserved(self):
        content = '{"vulnerabilities": [], "configuration_issues": [], "security_properties": []}'
        analyzer = _make_analyzer(content)
        snapshot = _make_snapshot()
        report = analyzer.analyze(snapshot)

        assert report.snapshot_timestamp == snapshot.snapshot.timestamp
