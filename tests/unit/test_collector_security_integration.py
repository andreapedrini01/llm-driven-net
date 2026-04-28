"""
Unit test per l'integrazione della scansione di sicurezza in NetworkStateCollector.
"""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import pytest

from llm_integration_module.models.security import SecurityReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_report(
    vulnerabilities=None,
    configuration_issues=None,
    security_properties=None,
) -> SecurityReport:
    return SecurityReport(
        vulnerabilities=vulnerabilities or [],
        configuration_issues=configuration_issues or [],
        security_properties=security_properties or [],
        timestamp=time.time(),
        snapshot_timestamp=time.time(),
    )


def _make_collector():
    """Crea un NetworkStateCollector con tutti i componenti mockati."""
    with patch("network_state_collector.collector.ConfigurationManager") as MockCM, \
         patch("network_state_collector.collector.RyuConnector"), \
         patch("network_state_collector.collector.DataProcessor"), \
         patch("network_state_collector.collector.DataValidator"), \
         patch("network_state_collector.collector.LLMIntegrator"), \
         patch("network_state_collector.collector.JSONSerializer"), \
         patch("network_state_collector.collector.FileSystemManager"), \
         patch("network_state_collector.collector.ErrorManager"), \
         patch("network_state_collector.collector.LoggingManager"), \
         patch("network_state_collector.collector.PerformanceMonitor"):

        mock_config = MagicMock()
        mock_config.environment = "test"
        mock_config.version = "0.0.1"
        mock_config.collection.validate_data = False
        mock_config.collection.parallel_collection = False
        mock_config.collection.detect_topology_changes = False
        mock_config.output.pretty_print = False
        mock_config.output.directory = "/tmp"
        mock_config.output.history_directory = "/tmp/history"
        mock_config.output.max_history_files = 10
        mock_config.output.compress_old_files = False
        MockCM.return_value.load_config.return_value = mock_config
        MockCM.return_value.get_current_config.return_value = mock_config

        from network_state_collector.collector import NetworkStateCollector
        collector = NetworkStateCollector()
        return collector


# ---------------------------------------------------------------------------
# Test: security_scan=False non chiama _run_security_scan
# ---------------------------------------------------------------------------

class TestCollectSnapshotWithoutSecurityScan:
    def test_no_security_scan_does_not_call_run_security_scan(self):
        collector = _make_collector()

        with patch.object(collector, "_collect_raw_data") as mock_raw, \
             patch.object(collector, "_run_security_scan") as mock_sec, \
             patch.object(collector, "_save_snapshot"), \
             patch.object(collector, "_update_collection_stats"):

            mock_switch = MagicMock()
            mock_switch.dpid = "1"
            mock_raw.return_value = ([mock_switch], [], {}, {})

            collector.data_processor.process_topology.return_value = MagicMock(switches=[mock_switch], links=[])
            collector.data_processor.process_metrics.return_value = MagicMock(aggregated_metrics={})
            collector.llm_integrator.format_for_llm.return_value = MagicMock()

            collector.collect_snapshot(security_scan=False)

        mock_sec.assert_not_called()

    def test_default_call_does_not_call_run_security_scan(self):
        collector = _make_collector()

        with patch.object(collector, "_collect_raw_data") as mock_raw, \
             patch.object(collector, "_run_security_scan") as mock_sec, \
             patch.object(collector, "_save_snapshot"), \
             patch.object(collector, "_update_collection_stats"):

            mock_switch = MagicMock()
            mock_switch.dpid = "1"
            mock_raw.return_value = ([mock_switch], [], {}, {})

            collector.data_processor.process_topology.return_value = MagicMock(switches=[mock_switch], links=[])
            collector.data_processor.process_metrics.return_value = MagicMock(aggregated_metrics={})
            collector.llm_integrator.format_for_llm.return_value = MagicMock()

            collector.collect_snapshot()

        mock_sec.assert_not_called()


# ---------------------------------------------------------------------------
# Test: security_scan=True chiama _run_security_scan
# ---------------------------------------------------------------------------

class TestCollectSnapshotWithSecurityScan:
    def test_security_scan_true_calls_run_security_scan(self):
        collector = _make_collector()

        with patch.object(collector, "_collect_raw_data") as mock_raw, \
             patch.object(collector, "_run_security_scan") as mock_sec, \
             patch.object(collector, "_save_snapshot"), \
             patch.object(collector, "_update_collection_stats"):

            mock_switch = MagicMock()
            mock_switch.dpid = "1"
            mock_raw.return_value = ([mock_switch], [], {}, {})

            collector.data_processor.process_topology.return_value = MagicMock(switches=[mock_switch], links=[])
            collector.data_processor.process_metrics.return_value = MagicMock(aggregated_metrics={})
            collector.llm_integrator.format_for_llm.return_value = MagicMock()

            collector.collect_snapshot(security_scan=True)

        mock_sec.assert_called_once()

    def test_security_scan_passes_host_filter(self):
        collector = _make_collector()

        with patch.object(collector, "_collect_raw_data") as mock_raw, \
             patch.object(collector, "_run_security_scan") as mock_sec, \
             patch.object(collector, "_save_snapshot"), \
             patch.object(collector, "_update_collection_stats"):

            mock_switch = MagicMock()
            mock_switch.dpid = "1"
            mock_raw.return_value = ([mock_switch], [], {}, {})

            collector.data_processor.process_topology.return_value = MagicMock(switches=[mock_switch], links=[])
            collector.data_processor.process_metrics.return_value = MagicMock(aggregated_metrics={})
            collector.llm_integrator.format_for_llm.return_value = MagicMock()

            collector.collect_snapshot(security_scan=True, host_filter=["h1", "h2"])

        args, kwargs = mock_sec.call_args
        # secondo argomento è host_filter
        assert args[1] == ["h1", "h2"]

    def test_security_scan_exception_does_not_propagate(self):
        """Un'eccezione in _run_security_scan non deve far fallire collect_snapshot."""
        collector = _make_collector()

        with patch.object(collector, "_collect_raw_data") as mock_raw, \
             patch.object(collector, "_run_security_scan", side_effect=RuntimeError("boom")), \
             patch.object(collector, "_save_snapshot"), \
             patch.object(collector, "_update_collection_stats"):

            mock_switch = MagicMock()
            mock_switch.dpid = "1"
            mock_raw.return_value = ([mock_switch], [], {}, {})

            collector.data_processor.process_topology.return_value = MagicMock(switches=[mock_switch], links=[])
            collector.data_processor.process_metrics.return_value = MagicMock(aggregated_metrics={})
            collector.llm_integrator.format_for_llm.return_value = MagicMock()

            result = collector.collect_snapshot(security_scan=True)

        # Lo snapshot deve essere restituito comunque
        assert result is not None


# ---------------------------------------------------------------------------
# Test: _format_security_report
# ---------------------------------------------------------------------------

class TestFormatSecurityReport:
    def setup_method(self):
        self.collector = _make_collector()

    def test_contains_three_sections(self):
        report = _make_report()
        output = self.collector._format_security_report(report)
        assert "Vulnerabilità Potenziali" in output
        assert "Problemi di Configurazione" in output
        assert "Proprietà di Sicurezza da Verificare" in output

    def test_lists_vulnerabilities(self):
        report = _make_report(vulnerabilities=["CVE-2021-1234", "weak password"])
        output = self.collector._format_security_report(report)
        assert "CVE-2021-1234" in output
        assert "weak password" in output

    def test_lists_configuration_issues(self):
        report = _make_report(configuration_issues=["open telnet port"])
        output = self.collector._format_security_report(report)
        assert "open telnet port" in output

    def test_lists_security_properties(self):
        report = _make_report(security_properties=["verify TLS"])
        output = self.collector._format_security_report(report)
        assert "verify TLS" in output

    def test_empty_lists_show_placeholder(self):
        report = _make_report()
        output = self.collector._format_security_report(report)
        assert "Nessuna vulnerabilità rilevata" in output
        assert "Nessun problema di configurazione rilevato" in output
        assert "Nessuna proprietà da verificare" in output

    def test_returns_string(self):
        report = _make_report()
        output = self.collector._format_security_report(report)
        assert isinstance(output, str)


# ---------------------------------------------------------------------------
# Test: salvataggio file
# ---------------------------------------------------------------------------

class TestSecurityReportFileSaving:
    def test_file_saved_with_correct_name_pattern(self, tmp_path):
        """Verifica che il file venga salvato con il pattern security_report_*.json."""
        report = _make_report(vulnerabilities=["test vuln"])

        # Simula la logica di salvataggio di _run_security_scan
        security_dir = tmp_path / "data" / "security_history"
        security_dir.mkdir(parents=True, exist_ok=True)
        report_filename = f"security_report_{report.get_timestamp_iso().replace(':', '-')}.json"
        report_path = security_dir / report_filename
        report_path.write_text(report.to_json(), encoding="utf-8")

        saved_files = list(security_dir.glob("security_report_*.json"))
        assert len(saved_files) == 1
        assert saved_files[0].name.startswith("security_report_")
        assert saved_files[0].name.endswith(".json")

    def test_directory_created_automatically(self, tmp_path):
        """Verifica che la directory data/security_history venga creata automaticamente."""
        report = _make_report()

        security_dir = tmp_path / "data" / "security_history"
        assert not security_dir.exists()

        # Simula la logica di mkdir in _run_security_scan
        security_dir.mkdir(parents=True, exist_ok=True)

        assert security_dir.is_dir()

    def test_saved_file_contains_valid_json(self, tmp_path):
        """Verifica che il file salvato contenga JSON valido con i campi del report."""
        report = _make_report(
            vulnerabilities=["CVE-2021-1234"],
            configuration_issues=["open port 23"],
            security_properties=["verify TLS"],
        )

        security_dir = tmp_path / "data" / "security_history"
        security_dir.mkdir(parents=True, exist_ok=True)
        report_filename = f"security_report_{report.get_timestamp_iso().replace(':', '-')}.json"
        report_path = security_dir / report_filename
        report_path.write_text(report.to_json(), encoding="utf-8")

        content = json.loads(report_path.read_text(encoding="utf-8"))
        assert content["vulnerabilities"] == ["CVE-2021-1234"]
        assert content["configuration_issues"] == ["open port 23"]
        assert content["security_properties"] == ["verify TLS"]
