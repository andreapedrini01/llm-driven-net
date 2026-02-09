"""
Configurazione pytest e fixture condivise per i test
"""

import pytest
from hypothesis import settings, Verbosity
from network_state_collector.models import CollectorConfig


# Configurazione Hypothesis per i test
settings.register_profile("default", max_examples=100, verbosity=Verbosity.normal)
settings.register_profile("ci", max_examples=1000, verbosity=Verbosity.verbose)
settings.register_profile("dev", max_examples=10, verbosity=Verbosity.verbose)

# Usa il profilo appropriato
settings.load_profile("default")


@pytest.fixture
def sample_config():
    """Fixture che fornisce una configurazione di esempio"""
    return CollectorConfig()


@pytest.fixture
def sample_dpid():
    """Fixture che fornisce un DPID di esempio"""
    return "0000000000000001"


@pytest.fixture
def sample_switch_data():
    """Fixture che fornisce dati di switch di esempio"""
    return {
        "dpid": "0000000000000001",
        "ports": [1, 2, 3, 4],
        "active": True
    }


@pytest.fixture
def sample_link_data():
    """Fixture che fornisce dati di link di esempio"""
    return {
        "src_dpid": "0000000000000001",
        "dst_dpid": "0000000000000002", 
        "src_port": 1,
        "dst_port": 2,
        "active": True
    }


@pytest.fixture
def sample_port_metrics():
    """Fixture che fornisce metriche di porta di esempio"""
    return {
        "port_no": 1,
        "rx_packets": 1000,
        "tx_packets": 800,
        "rx_bytes": 64000,
        "tx_bytes": 51200,
        "rx_errors": 0,
        "tx_errors": 0,
        "rx_dropped": 0,
        "tx_dropped": 0
    }