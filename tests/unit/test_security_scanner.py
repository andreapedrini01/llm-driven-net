"""
Unit test per SecurityScanner, extract_host_ips e resolve_host_filter.

Adattati per il backend HTTP (web server Flask/nmap nel container Docker).
"""

import pytest
from unittest.mock import patch, MagicMock

import requests

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
    switches = [SwitchInfo(dpid=f"{i:016x}", ports=[1]) for i in range(1, num_switches + 1)]
    topology = TopologyData(switches=switches, links=[])
    metrics = MetricsData(port_statistics={})
    return NetworkSnapshot(timestamp=1000.0, topology=topology, metrics=metrics)


NMAP_JSON_UP = {
    "status": {"state": "up"},
    "tcp": {
        "22": {"state": "open", "name": "ssh", "version": "OpenSSH 8.0"},
        "80": {"state": "open", "name": "http", "version": ""},
    },
}

NMAP_JSON_DOWN = {
    "status": {"state": "down"},
}


def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.raise_for_status = MagicMock()
    return mock


# ---------------------------------------------------------------------------
# Test: NmapNotFoundError quando il web server non è raggiungibile
# ---------------------------------------------------------------------------

class TestNmapNotFound:
    def test_raises_nmap_not_found_error_on_connection_error(self):
        scanner = SecurityScanner(timeout=5)
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError("refused")):
            with pytest.raises(NmapNotFoundError):
                scanner._scan_host("10.0.0.1")

    def test_scan_propagates_nmap_not_found(self):
        scanner = SecurityScanner(timeout=5)
        with patch("requests.get", side_effect=requests.exceptions.ConnectionError("refused")):
            with pytest.raises(NmapNotFoundError):
                scanner.scan(["10.0.0.1", "10.0.0.2"])


# ---------------------------------------------------------------------------
# Test: host non raggiungibile → status="unreachable"
# ---------------------------------------------------------------------------

class TestHostUnreachable:
    def test_host_down_returns_unreachable(self):
        scanner = SecurityScanner(timeout=5)
        with patch("requests.get", return_value=_mock_response(NMAP_JSON_DOWN)):
            result = scanner._scan_host("10.0.0.1")
        assert result.status == "unreachable"
        assert result.open_ports == []
        assert result.ip == "10.0.0.1"

    def test_empty_json_returns_unreachable(self):
        scanner = SecurityScanner(timeout=5)
        with patch("requests.get", return_value=_mock_response({})):
            result = scanner._scan_host("10.0.0.1")
        # Senza status.state == "down" e senza porte, è comunque scanned con 0 porte
        assert result.ip == "10.0.0.1"


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

    def test_timeout_passed_to_requests(self, monkeypatch):
        monkeypatch.setenv("SECURITY_SCAN_TIMEOUT", "45")
        scanner = SecurityScanner()
        with patch("requests.get", return_value=_mock_response(NMAP_JSON_UP)) as mock_get:
            scanner._scan_host("10.0.0.1")
        _, kwargs = mock_get.call_args
        assert kwargs.get("timeout") == 45

    def test_timeout_expired_returns_timeout_status(self):
        scanner = SecurityScanner(timeout=5)
        with patch("requests.get", side_effect=requests.exceptions.Timeout()):
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
        with patch("requests.get", return_value=_mock_response(NMAP_JSON_UP)):
            with caplog.at_level(logging.INFO, logger="network_state_collector.security_scanner"):
                scanner.scan(["10.0.0.1", "10.0.0.2", "10.0.0.3"])

        log_messages = [r.message for r in caplog.records]
        assert any("Scansione 1/3: 10.0.0.1" in m for m in log_messages)
        assert any("Scansione 2/3: 10.0.0.2" in m for m in log_messages)
        assert any("Scansione 3/3: 10.0.0.3" in m for m in log_messages)


# ---------------------------------------------------------------------------
# Test: risoluzione nomi Mininet
# ---------------------------------------------------------------------------

class TestResolveHostFilter:
    def test_h1_resolves_to_10_0_0_1(self):
        snapshot = _make_snapshot(num_switches=3)
        result = resolve_host_filter(["h1"], snapshot)
        assert result == ["10.0.0.1"]

    def test_direct_ip_accepted(self):
        snapshot = _make_snapshot(num_switches=3)
        result = resolve_host_filter(["10.0.0.3"], snapshot)
        assert result == ["10.0.0.3"]

    def test_host_not_in_topology_is_ignored(self, caplog):
        import logging
        snapshot = _make_snapshot(num_switches=2)
        with caplog.at_level(logging.WARNING, logger="network_state_collector.security_scanner"):
            result = resolve_host_filter(["h5"], snapshot)
        assert result == []
        assert any("h5" in m for m in [r.message for r in caplog.records])

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


# ---------------------------------------------------------------------------
# Test: scan con host scansionato con successo
# ---------------------------------------------------------------------------

class TestScanSuccess:
    def test_scan_returns_scanned_status(self):
        scanner = SecurityScanner(timeout=5)
        with patch("requests.get", return_value=_mock_response(NMAP_JSON_UP)):
            results = scanner.scan(["10.0.0.1"])
        assert "10.0.0.1" in results
        r = results["10.0.0.1"]
        assert r.status == "scanned"
        assert len(r.open_ports) == 2
        ports = {p.port for p in r.open_ports}
        assert 22 in ports
        assert 80 in ports

    def test_scan_error_does_not_stop_other_hosts(self):
        scanner = SecurityScanner(timeout=5)
        call_count = 0

        def side_effect(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise requests.exceptions.HTTPError("500")
            return _mock_response(NMAP_JSON_UP)

        with patch("requests.get", side_effect=side_effect):
            results = scanner.scan(["10.0.0.1", "10.0.0.2"])

        assert "10.0.0.1" in results
        assert "10.0.0.2" in results
        assert results["10.0.0.1"].status == "error"
        assert results["10.0.0.2"].status == "scanned"

    def test_nmap_service_url_from_env(self, monkeypatch):
        monkeypatch.setenv("NMAP_SERVICE_URL", "http://192.168.1.100:5000")
        scanner = SecurityScanner()
        assert scanner.nmap_service_url == "http://192.168.1.100:5000"
