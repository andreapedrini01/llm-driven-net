"""
Unit test per SecurityScanner, extract_host_ips e resolve_host_filter.

Copre i casi limite richiesti dal Task 2.3:
- nmap non installato → NmapNotFoundError
- host non raggiungibile → status="unreachable"
- timeout da env var SECURITY_SCAN_TIMEOUT
- formato log progresso "Scansione X/N: ip"
- nome host h1 risolto a 10.0.0.1
- nome host non in topologia → WARNING loggato, host ignorato
"""

import os
import subprocess
import pytest
from unittest.mock import patch, MagicMock

from network_state_collector.security_scanner import (
    SecurityScanner,
    extract_host_ips,
    resolve_host_filter,
)
from src.models.security import NmapResult, NmapNotFoundError
from src.models.core import NetworkSnapshot, TopologyData, MetricsData, SwitchInfo, LinkInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_snapshot(num_switches: int = 3) -> NetworkSnapshot:
    """Crea un NetworkSnapshot minimale con N switch."""
    switches = [SwitchInfo(dpid=f"{i:016x}", ports=[1]) for i in range(1, num_switches + 1)]
    topology = TopologyData(switches=switches, links=[])
    metrics = MetricsData(port_statistics={})
    return NetworkSnapshot(timestamp=1000.0, topology=topology, metrics=metrics)


NMAP_XML_UP = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <ports>
      <port protocol="tcp" portid="22">
        <state state="open"/>
        <service name="ssh" version="OpenSSH 8.0"/>
      </port>
      <port protocol="tcp" portid="80">
        <state state="open"/>
        <service name="http" version=""/>
      </port>
    </ports>
  </host>
</nmaprun>"""

NMAP_XML_DOWN = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="down"/>
  </host>
</nmaprun>"""


# ---------------------------------------------------------------------------
# Test: NmapNotFoundError quando nmap non è installato
# ---------------------------------------------------------------------------

class TestNmapNotFound:
    def test_raises_nmap_not_found_error(self):
        scanner = SecurityScanner(timeout=5)
        with patch("subprocess.run", side_effect=FileNotFoundError("nmap not found")):
            with pytest.raises(NmapNotFoundError):
                scanner._scan_host("10.0.0.1")

    def test_scan_propagates_nmap_not_found(self):
        scanner = SecurityScanner(timeout=5)
        with patch("subprocess.run", side_effect=FileNotFoundError("nmap not found")):
            with pytest.raises(NmapNotFoundError):
                scanner.scan(["10.0.0.1", "10.0.0.2"])


# ---------------------------------------------------------------------------
# Test: host non raggiungibile → status="unreachable"
# ---------------------------------------------------------------------------

class TestHostUnreachable:
    def test_host_down_returns_unreachable(self):
        scanner = SecurityScanner(timeout=5)
        mock_result = MagicMock()
        mock_result.stdout = NMAP_XML_DOWN
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = scanner._scan_host("10.0.0.1")
        assert result.status == "unreachable"
        assert result.open_ports == []
        assert result.ip == "10.0.0.1"

    def test_empty_xml_returns_unreachable(self):
        scanner = SecurityScanner(timeout=5)
        mock_result = MagicMock()
        mock_result.stdout = "<nmaprun></nmaprun>"
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = scanner._scan_host("10.0.0.1")
        assert result.status == "unreachable"


# ---------------------------------------------------------------------------
# Test: timeout da env var SECURITY_SCAN_TIMEOUT
# ---------------------------------------------------------------------------

class TestTimeoutEnvVar:
    def test_timeout_from_env_var(self, monkeypatch):
        monkeypatch.setenv("SECURITY_SCAN_TIMEOUT", "30")
        scanner = SecurityScanner(timeout=120)
        assert scanner.timeout == 30

    def test_default_timeout_without_env_var(self, monkeypatch):
        monkeypatch.delenv("SECURITY_SCAN_TIMEOUT", raising=False)
        scanner = SecurityScanner(timeout=120)
        assert scanner.timeout == 120

    def test_invalid_env_var_uses_default(self, monkeypatch):
        monkeypatch.setenv("SECURITY_SCAN_TIMEOUT", "not_a_number")
        scanner = SecurityScanner(timeout=60)
        assert scanner.timeout == 60

    def test_timeout_passed_to_subprocess(self, monkeypatch):
        monkeypatch.setenv("SECURITY_SCAN_TIMEOUT", "45")
        scanner = SecurityScanner()
        mock_result = MagicMock()
        mock_result.stdout = NMAP_XML_UP
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            scanner._scan_host("10.0.0.1")
        _, kwargs = mock_run.call_args
        assert kwargs.get("timeout") == 45

    def test_timeout_expired_returns_timeout_status(self):
        scanner = SecurityScanner(timeout=5)
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="nmap", timeout=5)):
            result = scanner._scan_host("10.0.0.1")
        assert result.status == "timeout"
        assert result.ip == "10.0.0.1"


# ---------------------------------------------------------------------------
# Test: formato log progresso "Scansione X/N: ip"
# ---------------------------------------------------------------------------

class TestProgressLog:
    def test_progress_log_format(self, caplog):
        import logging
        scanner = SecurityScanner(timeout=5)
        mock_result = MagicMock()
        mock_result.stdout = NMAP_XML_UP
        with patch("subprocess.run", return_value=mock_result):
            with caplog.at_level(logging.INFO, logger="network_state_collector.security_scanner"):
                scanner.scan(["10.0.0.1", "10.0.0.2", "10.0.0.3"])

        log_messages = [r.message for r in caplog.records]
        assert any("Scansione 1/3: 10.0.0.1" in m for m in log_messages)
        assert any("Scansione 2/3: 10.0.0.2" in m for m in log_messages)
        assert any("Scansione 3/3: 10.0.0.3" in m for m in log_messages)

    def test_progress_log_single_host(self, caplog):
        import logging
        scanner = SecurityScanner(timeout=5)
        mock_result = MagicMock()
        mock_result.stdout = NMAP_XML_UP
        with patch("subprocess.run", return_value=mock_result):
            with caplog.at_level(logging.INFO, logger="network_state_collector.security_scanner"):
                scanner.scan(["10.0.0.5"])

        log_messages = [r.message for r in caplog.records]
        assert any("Scansione 1/1: 10.0.0.5" in m for m in log_messages)


# ---------------------------------------------------------------------------
# Test: risoluzione nomi Mininet
# ---------------------------------------------------------------------------

class TestResolveHostFilter:
    def test_h1_resolves_to_10_0_0_1(self):
        snapshot = _make_snapshot(num_switches=3)
        result = resolve_host_filter(["h1"], snapshot)
        assert result == ["10.0.0.1"]

    def test_h2_resolves_to_10_0_0_2(self):
        snapshot = _make_snapshot(num_switches=3)
        result = resolve_host_filter(["h2"], snapshot)
        assert result == ["10.0.0.2"]

    def test_direct_ip_accepted(self):
        snapshot = _make_snapshot(num_switches=3)
        result = resolve_host_filter(["10.0.0.3"], snapshot)
        assert result == ["10.0.0.3"]

    def test_mixed_names_and_ips(self):
        snapshot = _make_snapshot(num_switches=3)
        result = resolve_host_filter(["h1", "10.0.0.2"], snapshot)
        assert set(result) == {"10.0.0.1", "10.0.0.2"}

    def test_host_not_in_topology_is_ignored(self, caplog):
        import logging
        snapshot = _make_snapshot(num_switches=2)  # solo 10.0.0.1 e 10.0.0.2
        with caplog.at_level(logging.WARNING, logger="network_state_collector.security_scanner"):
            result = resolve_host_filter(["h5"], snapshot)
        assert result == []
        assert any("h5" in m for m in [r.message for r in caplog.records])

    def test_ip_not_in_topology_is_ignored(self, caplog):
        import logging
        snapshot = _make_snapshot(num_switches=2)
        with caplog.at_level(logging.WARNING, logger="network_state_collector.security_scanner"):
            result = resolve_host_filter(["10.0.0.99"], snapshot)
        assert result == []

    def test_empty_filter_returns_empty(self):
        snapshot = _make_snapshot(num_switches=3)
        result = resolve_host_filter([], snapshot)
        assert result == []


# ---------------------------------------------------------------------------
# Test: extract_host_ips
# ---------------------------------------------------------------------------

class TestExtractHostIps:
    def test_extracts_ips_from_switches(self):
        snapshot = _make_snapshot(num_switches=3)
        ips = extract_host_ips(snapshot)
        assert set(ips) == {"10.0.0.1", "10.0.0.2", "10.0.0.3"}

    def test_empty_topology_returns_empty(self):
        snapshot = _make_snapshot(num_switches=0)
        ips = extract_host_ips(snapshot)
        assert ips == []

    def test_graph_representation_hosts_used_if_present(self):
        switches = [SwitchInfo(dpid=f"{1:016x}", ports=[1])]
        topology = TopologyData(
            switches=switches,
            links=[],
            graph_representation={
                "hosts": [
                    {"ip": "10.0.0.10"},
                    {"ip": "10.0.0.20"},
                    {"ip": "192.168.1.1"},  # non nel range 10.0.0.x, ignorato
                ]
            },
        )
        metrics = MetricsData(port_statistics={})
        snapshot = NetworkSnapshot(timestamp=1000.0, topology=topology, metrics=metrics)
        ips = extract_host_ips(snapshot)
        assert set(ips) == {"10.0.0.10", "10.0.0.20"}


# ---------------------------------------------------------------------------
# Test: scan con host scansionato con successo
# ---------------------------------------------------------------------------

class TestScanSuccess:
    def test_scan_returns_scanned_status(self):
        scanner = SecurityScanner(timeout=5)
        mock_result = MagicMock()
        mock_result.stdout = NMAP_XML_UP
        with patch("subprocess.run", return_value=mock_result):
            results = scanner.scan(["10.0.0.1"])
        assert "10.0.0.1" in results
        r = results["10.0.0.1"]
        assert r.status == "scanned"
        assert len(r.open_ports) == 2
        assert r.open_ports[0].port == 22
        assert r.open_ports[0].service == "ssh"
        assert r.open_ports[1].port == 80

    def test_scan_error_does_not_stop_other_hosts(self):
        scanner = SecurityScanner(timeout=5)
        mock_ok = MagicMock()
        mock_ok.stdout = NMAP_XML_UP

        call_count = 0

        def side_effect(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise subprocess.CalledProcessError(1, "nmap")
            return mock_ok

        with patch("subprocess.run", side_effect=side_effect):
            results = scanner.scan(["10.0.0.1", "10.0.0.2"])

        assert "10.0.0.1" in results
        assert "10.0.0.2" in results
        assert results["10.0.0.1"].status == "error"
        assert results["10.0.0.2"].status == "scanned"
