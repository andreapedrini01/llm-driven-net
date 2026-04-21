"""
Property-based test per la Proprietà 9 della feature collect-security-scan.

# Feature: collect-security-scan, Property 9: Per qualsiasi SecurityReport,
# _format_security_report produce una stringa con le tre sezioni e tutti gli
# elementi delle liste.

**Validates: Requirements 4.3**
"""

import time
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from llm_integration_module.models.security import SecurityReport


# ---------------------------------------------------------------------------
# Strategie Hypothesis
# ---------------------------------------------------------------------------

security_string = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=1,
    max_size=80,
)

security_report_strategy = st.builds(
    SecurityReport,
    vulnerabilities=st.lists(security_string, max_size=10),
    configuration_issues=st.lists(security_string, max_size=10),
    security_properties=st.lists(security_string, max_size=10),
    timestamp=st.floats(min_value=0.0, max_value=2e9, allow_nan=False, allow_infinity=False),
    snapshot_timestamp=st.floats(min_value=0.0, max_value=2e9, allow_nan=False, allow_infinity=False),
    raw_response=st.none(),
)


# ---------------------------------------------------------------------------
# Helper: crea un collector mockato senza dipendenze esterne
# ---------------------------------------------------------------------------

def _make_collector():
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
        return NetworkStateCollector()


# ---------------------------------------------------------------------------
# Proprietà 9
# ---------------------------------------------------------------------------

@given(report=security_report_strategy)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_report_format_sections(report: SecurityReport):
    """
    # Feature: collect-security-scan, Property 9
    Per qualsiasi SecurityReport, _format_security_report produce una stringa
    che contiene le tre sezioni e tutti gli elementi delle rispettive liste.

    **Validates: Requirements 4.3**
    """
    collector = _make_collector()
    output = collector._format_security_report(report)

    # La stringa deve contenere le tre sezioni
    assert "Vulnerabilità Potenziali" in output, "Sezione 'Vulnerabilità Potenziali' mancante"
    assert "Problemi di Configurazione" in output, "Sezione 'Problemi di Configurazione' mancante"
    assert "Proprietà di Sicurezza da Verificare" in output, "Sezione 'Proprietà di Sicurezza da Verificare' mancante"

    # Tutti gli elementi delle liste devono essere presenti nell'output
    for v in report.vulnerabilities:
        assert v in output, f"Vulnerabilità '{v}' non trovata nell'output"

    for c in report.configuration_issues:
        assert c in output, f"Problema di configurazione '{c}' non trovato nell'output"

    for p in report.security_properties:
        assert p in output, f"Proprietà di sicurezza '{p}' non trovata nell'output"
