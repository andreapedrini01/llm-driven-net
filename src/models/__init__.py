"""
Data models for Network State Collector

Questo modulo contiene tutte le dataclass e modelli dati utilizzati
dal Network State Collector per rappresentare lo stato della rete.
"""

from .core import NetworkSnapshot, TopologyData, MetricsData
from .llm import LLMNetworkData, ContextEmbedding
from .config import CollectorConfig, RetryConfig
from .health import HealthStatus, QualityMetrics

__all__ = [
    "NetworkSnapshot",
    "TopologyData",
    "MetricsData", 
    "LLMNetworkData",
    "ContextEmbedding",
    "CollectorConfig",
    "RetryConfig",
    "HealthStatus",
    "QualityMetrics"
]