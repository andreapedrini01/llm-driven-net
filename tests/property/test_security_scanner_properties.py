"""
Property-based test per SecurityScanner.

Proprietà implementate:
- Proprietà 1: Copertura completa degli host (Requisiti 1.1, 1.2)
- Proprietà 3: Resilienza per host falliti (Requisiti 1.5, 1.6)
"""

import subprocess
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from network_state_collector.security_scanner import SecurityScanner
from src.models.security import NmapResult


# ---------------------------------------------------------------------------
# Generatori
# ---------------------------------------------------------------------------

def _nmap_xml_up(port: int = 22) -> str:
    return f"""<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <ports>
      <port protocol="tcp" portid="{port}">
        <state state="open"/>
        <service name="ssh" version=""/>
      </port>
    </ports>
  </host>
</nmaprun>"""


@st.composite
def ip_addresses(draw):
    """Genera indirizzi IP nel range 10.0.0.x."""
    n = draw(st.integers(min_value=1, max_value=254))
    return f"10.0.0.{n}"


@st.composite
def unique_ip_list(draw, min_size=1, max_size=10):
    """Genera una lista di IP unici nel range 10.0.0.x."""
    ips = draw(st.lists(ip_addresses(), min_size=min_size, max_size=max_size, unique=True))
    return ips


# ---------------------------------------------------------------------------
# Proprietà 1: Copertura completa degli host
# Feature: collect-security-scan, Property 1
# Validates: Requirements 1.1, 1.2
# ---------------------------------------------------------------------------

class TestScannerCoversAllHosts:
    """
    Proprietà 1: Copertura completa degli host

    Per qualsiasi lista di N IP, scan() deve restituire un dizionario
    con esattamente N chiavi corrispondenti agli IP forniti.

    **Validates: Requirements 1.1, 1.2**
    """

    @given(ip_list=unique_ip_list(min_size=1, max_size=10))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_scanner_covers_all_hosts(self, ip_list):
        # Feature: collect-security-scan, Property 1
        scanner = SecurityScanner(timeout=5)
        mock_result = MagicMock()
        mock_result.stdout = _nmap_xml_up()

        with patch("subprocess.run", return_value=mock_result):
            results = scanner.scan(ip_list)

        # Il dizionario deve avere esattamente N chiavi
        assert len(results) == len(ip_list)
        # Le chiavi devono corrispondere esattamente agli IP forniti
        assert set(results.keys()) == set(ip_list)

    @given(ip_list=unique_ip_list(min_size=1, max_size=10))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_scanner_keys_match_input_ips(self, ip_list):
        # Feature: collect-security-scan, Property 1
        scanner = SecurityScanner(timeout=5)
        mock_result = MagicMock()
        mock_result.stdout = _nmap_xml_up()

        with patch("subprocess.run", return_value=mock_result):
            results = scanner.scan(ip_list)

        for ip in ip_list:
            assert ip in results
            assert isinstance(results[ip], NmapResult)
            assert results[ip].ip == ip

    @given(ip_list=unique_ip_list(min_size=1, max_size=10))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_scanner_no_extra_keys(self, ip_list):
        # Feature: collect-security-scan, Property 1
        scanner = SecurityScanner(timeout=5)
        mock_result = MagicMock()
        mock_result.stdout = _nmap_xml_up()

        with patch("subprocess.run", return_value=mock_result):
            results = scanner.scan(ip_list)

        # Nessuna chiave extra oltre agli IP forniti
        for key in results:
            assert key in ip_list


# ---------------------------------------------------------------------------
# Proprietà 3: Resilienza per host falliti
# Feature: collect-security-scan, Property 3
# Validates: Requirements 1.5, 1.6
# ---------------------------------------------------------------------------

class TestScannerResilience:
    """
    Proprietà 3: Resilienza per host falliti

    Per qualsiasi lista di N host in cui uno o più vanno in timeout o producono
    un errore, scan() deve restituire risultati per tutti gli N host.
    Gli host falliti devono avere status "timeout" o "error".

    **Validates: Requirements 1.5, 1.6**
    """

    @given(
        good_ips=unique_ip_list(min_size=1, max_size=5),
        bad_ips=unique_ip_list(min_size=1, max_size=5),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_scanner_resilience_timeout(self, good_ips, bad_ips):
        # Feature: collect-security-scan, Property 3
        # Evita sovrapposizioni tra good e bad
        bad_ips = [ip for ip in bad_ips if ip not in good_ips]
        if not bad_ips:
            bad_ips = ["10.0.0.254"]
            if bad_ips[0] in good_ips:
                return  # skip se non possiamo costruire un caso valido

        all_ips = good_ips + bad_ips
        scanner = SecurityScanner(timeout=5)
        mock_ok = MagicMock()
        mock_ok.stdout = _nmap_xml_up()

        def side_effect(cmd, **kwargs):
            # L'IP è l'ultimo argomento del comando nmap
            ip = cmd[-1]
            if ip in bad_ips:
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=5)
            return mock_ok

        with patch("subprocess.run", side_effect=side_effect):
            results = scanner.scan(all_ips)

        # Tutti gli IP devono avere un risultato
        assert len(results) == len(all_ips)
        assert set(results.keys()) == set(all_ips)

        # Gli host in timeout devono avere status="timeout"
        for ip in bad_ips:
            assert results[ip].status == "timeout", f"Atteso timeout per {ip}, ottenuto {results[ip].status}"

        # Gli host buoni devono avere status="scanned"
        for ip in good_ips:
            assert results[ip].status == "scanned", f"Atteso scanned per {ip}, ottenuto {results[ip].status}"

    @given(
        good_ips=unique_ip_list(min_size=1, max_size=5),
        bad_ips=unique_ip_list(min_size=1, max_size=5),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_scanner_resilience_network_error(self, good_ips, bad_ips):
        # Feature: collect-security-scan, Property 3
        bad_ips = [ip for ip in bad_ips if ip not in good_ips]
        if not bad_ips:
            bad_ips = ["10.0.0.253"]
            if bad_ips[0] in good_ips:
                return

        all_ips = good_ips + bad_ips
        scanner = SecurityScanner(timeout=5)
        mock_ok = MagicMock()
        mock_ok.stdout = _nmap_xml_up()

        def side_effect(cmd, **kwargs):
            ip = cmd[-1]
            if ip in bad_ips:
                raise subprocess.CalledProcessError(1, cmd)
            return mock_ok

        with patch("subprocess.run", side_effect=side_effect):
            results = scanner.scan(all_ips)

        # Tutti gli IP devono avere un risultato
        assert len(results) == len(all_ips)
        assert set(results.keys()) == set(all_ips)

        # Gli host con errore devono avere status="error"
        for ip in bad_ips:
            assert results[ip].status == "error", f"Atteso error per {ip}, ottenuto {results[ip].status}"

    @given(ip_list=unique_ip_list(min_size=2, max_size=8))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_scanner_all_results_have_valid_status(self, ip_list):
        # Feature: collect-security-scan, Property 3
        # Verifica che ogni risultato abbia uno status valido
        valid_statuses = {"scanned", "unreachable", "timeout", "error"}
        scanner = SecurityScanner(timeout=5)
        mock_ok = MagicMock()
        mock_ok.stdout = _nmap_xml_up()

        with patch("subprocess.run", return_value=mock_ok):
            results = scanner.scan(ip_list)

        for ip, result in results.items():
            assert result.status in valid_statuses, (
                f"Status non valido per {ip}: '{result.status}'"
            )
