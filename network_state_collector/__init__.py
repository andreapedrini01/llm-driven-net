"""
Network State Collector

Un sistema modulare e robusto per raccogliere, elaborare e fornire dati di stato 
della rete in tempo reale per l'integrazione con modelli LLM.
"""

__version__ = "1.0.0"
__author__ = "Network State Collector Team"

from llm_integration_module.models import NetworkSnapshot, TopologyData, MetricsData, CollectorConfig
from llm_integration_module.models.config import RyuConfig, RetryConfig
from .collector import NetworkStateCollector
from .ryu_connector import RyuConnector, RyuConnectionError, RyuTimeoutError, RyuDataError

__all__ = [
    "NetworkSnapshot",
    "TopologyData", 
    "MetricsData",
    "CollectorConfig",
    "RyuConfig",
    "RetryConfig",
    "NetworkStateCollector",
    "RyuConnector",
    "RyuConnectionError",
    "RyuTimeoutError", 
    "RyuDataError"
]