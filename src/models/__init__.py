"""Data models package."""

from .intent import (
    IntentType,
    Entity,
    IntentObject,
    ContextualizedIntent,
)

from .network import (
    Switch,
    Link,
    Host,
    Flow,
    BandwidthMetrics,
    LatencyMetrics,
    UtilizationMetrics,
    NetworkMetrics,
    Topology,
    AnomalyType,
    AnomalySeverity,
    Anomaly,
    NetworkState,
)

from .actions import (
    ActionType,
    NetworkAction,
    ActionSequence,
    ValidationResult,
    SafetyReport,
    SimulationResult,
    ImpactAssessment,
)

from .slices import (
    SliceStatus,
    Path,
    SliceResources,
    Policy,
    ServiceLevelAgreement,
    NetworkSlice,
)

from .config import (
    RetryConfig,
    RyuConfig,
    OutputConfig,
    CollectionConfig,
    LoggingConfig,
    CollectorConfig,
)

from .core import (
    SwitchInfo,
    LinkInfo,
    TopologyData,
    PortMetrics,
    AggregatedMetrics,
    MetricsData,
    SnapshotMetadata,
    DerivedMetrics,
    NetworkSnapshot,
)

from .llm import (
    AnomalyIndicator,
    ContextEmbedding,
    LLMNetworkData,
)

__all__ = [
    # Intent models
    "IntentType",
    "Entity",
    "IntentObject",
    "ContextualizedIntent",
    
    # Network models
    "Switch",
    "Link",
    "Host",
    "Flow",
    "BandwidthMetrics",
    "LatencyMetrics",
    "UtilizationMetrics",
    "NetworkMetrics",
    "Topology",
    "AnomalyType",
    "AnomalySeverity",
    "Anomaly",
    "NetworkState",
    
    # Action models
    "ActionType",
    "NetworkAction",
    "ActionSequence",
    "ValidationResult",
    "SafetyReport",
    "SimulationResult",
    "ImpactAssessment",
    
    # Slice models
    "SliceStatus",
    "Path",
    "SliceResources",
    "Policy",
    "ServiceLevelAgreement",
    "NetworkSlice",
    
    # Config models
    "RetryConfig",
    "RyuConfig",
    "OutputConfig",
    "CollectionConfig",
    "LoggingConfig",
    "CollectorConfig",
    
    # Core models
    "SwitchInfo",
    "LinkInfo",
    "TopologyData",
    "PortMetrics",
    "AggregatedMetrics",
    "MetricsData",
    "SnapshotMetadata",
    "DerivedMetrics",
    "NetworkSnapshot",
]