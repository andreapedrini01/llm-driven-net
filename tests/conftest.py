"""
Shared pytest configuration and fixtures for all tests.
"""

import asyncio
import pytest
from hypothesis import settings, Verbosity
from llm_integration_module.models import CollectorConfig


# Hypothesis profiles
settings.register_profile("default", max_examples=100, verbosity=Verbosity.normal)
settings.register_profile("ci", max_examples=1000, verbosity=Verbosity.verbose)
settings.register_profile("dev", max_examples=10, verbosity=Verbosity.verbose)

settings.load_profile("default")


# ---------------------------------------------------------------------------
# Python 3.9 compatibility: ensure an event loop always exists.
# asyncio.Lock() (used in ChatGPTClient.__init__) calls get_event_loop()
# which raises RuntimeError in Python 3.9 when no loop is set.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _ensure_event_loop():
    """Ensure an asyncio event loop exists for the current thread.
    
    In Python 3.9, asyncio.Lock() calls get_event_loop() which raises
    RuntimeError if no loop exists. asyncio.run() closes the loop when done,
    so subsequent Lock() calls fail. This fixture patches asyncio.Lock to
    auto-create a loop when needed.
    """
    _original_lock_init = asyncio.Lock.__init__

    def _patched_lock_init(self, *args, **kwargs):
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())
        _original_lock_init(self, *args, **kwargs)

    asyncio.Lock.__init__ = _patched_lock_init
    yield
    asyncio.Lock.__init__ = _original_lock_init


def run_async(coro):
    """Run an async coroutine, ensuring the event loop is restored afterwards.
    
    asyncio.run() closes the event loop when done, which breaks asyncio.Lock()
    in Python 3.9. This wrapper restores the loop after each call.
    """
    try:
        return asyncio.run(coro)
    finally:
        asyncio.set_event_loop(asyncio.new_event_loop())


# ---------------------------------------------------------------------------
# Network State Collector fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_config():
    """Provide a sample CollectorConfig instance."""
    return CollectorConfig()


@pytest.fixture
def sample_dpid():
    """Provide a sample DPID string."""
    return "0000000000000001"


@pytest.fixture
def sample_switch_data():
    """Provide sample switch data dictionary."""
    return {
        "dpid": "0000000000000001",
        "ports": [1, 2, 3, 4],
        "active": True,
    }


@pytest.fixture
def sample_link_data():
    """Provide sample link data dictionary."""
    return {
        "src_dpid": "0000000000000001",
        "dst_dpid": "0000000000000002",
        "src_port": 1,
        "dst_port": 2,
        "active": True,
    }


@pytest.fixture
def sample_port_metrics():
    """Provide sample port metrics dictionary."""
    return {
        "port_no": 1,
        "rx_packets": 1000,
        "tx_packets": 800,
        "rx_bytes": 64000,
        "tx_bytes": 51200,
        "rx_errors": 0,
        "tx_errors": 0,
        "rx_dropped": 0,
        "tx_dropped": 0,
    }
