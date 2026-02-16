"""
Core data models for Network State Collector

Implementa le dataclass principali per rappresentare lo stato della rete:
- NetworkSnapshot: Snapshot completo dello stato della rete
- TopologyData: Dati di topologia (switch e link)
- MetricsData: Metriche di prestazioni delle porte
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import json
from datetime import datetime


@dataclass
class SwitchInfo:
    """Informazioni su uno switch della rete"""
    dpid: str  # DPID formattato come stringa esadecimale a 16 cifre
    ports: List[int]
    active: bool = True
    
    def __post_init__(self):
        """Valida e formatta il DPID"""
        if isinstance(self.dpid, int):
            self.dpid = f"{self.dpid:016x}"
        elif isinstance(self.dpid, str):
            # Rimuovi prefissi comuni e formatta
            dpid_clean = self.dpid.replace("0x", "").replace(":", "")
            self.dpid = f"{int(dpid_clean, 16):016x}"


@dataclass
class LinkInfo:
    """Informazioni su un link tra switch"""
    src_dpid: str
    dst_dpid: str
    src_port: int
    dst_port: int
    active: bool = True
    
    def __post_init__(self):
        """Formatta i DPID dei link"""
        if isinstance(self.src_dpid, int):
            self.src_dpid = f"{self.src_dpid:016x}"
        elif isinstance(self.src_dpid, str):
            dpid_clean = self.src_dpid.replace("0x", "").replace(":", "")
            self.src_dpid = f"{int(dpid_clean, 16):016x}"
            
        if isinstance(self.dst_dpid, int):
            self.dst_dpid = f"{self.dst_dpid:016x}"
        elif isinstance(self.dst_dpid, str):
            dpid_clean = self.dst_dpid.replace("0x", "").replace(":", "")
            self.dst_dpid = f"{int(dpid_clean, 16):016x}"


@dataclass
class TopologyData:
    """Dati di topologia della rete"""
    switches: List[SwitchInfo]
    links: List[LinkInfo]
    graph_representation: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione JSON"""
        return {
            "switches": [
                {
                    "dpid": switch.dpid,
                    "ports": switch.ports,
                    "active": switch.active
                }
                for switch in self.switches
            ],
            "links": [
                {
                    "src_dpid": link.src_dpid,
                    "dst_dpid": link.dst_dpid,
                    "src_port": link.src_port,
                    "dst_port": link.dst_port,
                    "active": link.active
                }
                for link in self.links
            ],
            "graph_representation": self.graph_representation
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TopologyData':
        """Crea istanza da dizionario"""
        switches = [
            SwitchInfo(
                dpid=switch_data["dpid"],
                ports=switch_data["ports"],
                active=switch_data.get("active", True)
            )
            for switch_data in data.get("switches", [])
        ]
        
        links = [
            LinkInfo(
                src_dpid=link_data["src_dpid"],
                dst_dpid=link_data["dst_dpid"],
                src_port=link_data["src_port"],
                dst_port=link_data["dst_port"],
                active=link_data.get("active", True)
            )
            for link_data in data.get("links", [])
        ]
        
        return cls(
            switches=switches,
            links=links,
            graph_representation=data.get("graph_representation", {})
        )


@dataclass
class PortMetrics:
    """Metriche per una singola porta"""
    port_no: int
    rx_packets: int
    tx_packets: int
    rx_bytes: int
    tx_bytes: int
    rx_errors: int
    tx_errors: int
    rx_dropped: int = 0
    tx_dropped: int = 0
    
    def calculate_utilization(self, link_capacity_bps: int = 1000000000) -> float:
        """Calcola l'utilizzo della porta (0.0 - 1.0)"""
        total_bytes = self.rx_bytes + self.tx_bytes
        if link_capacity_bps == 0:
            return 0.0
        return min(1.0, (total_bytes * 8) / link_capacity_bps)
    
    def calculate_error_rate(self) -> float:
        """Calcola il tasso di errore (0.0 - 1.0)"""
        total_packets = self.rx_packets + self.tx_packets
        total_errors = self.rx_errors + self.tx_errors
        if total_packets == 0:
            return 0.0
        return total_errors / total_packets
    
    def is_congested(self, threshold: float = 0.8) -> bool:
        """Determina se la porta è congestionata"""
        return self.calculate_utilization() > threshold


@dataclass
class AggregatedMetrics:
    """Metriche aggregate per uno switch"""
    dpid: str
    total_rx_packets: int
    total_tx_packets: int
    total_rx_bytes: int
    total_tx_bytes: int
    total_errors: int
    average_utilization: float
    congested_ports: int
    
    def __post_init__(self):
        """Formatta il DPID"""
        if isinstance(self.dpid, int):
            self.dpid = f"{self.dpid:016x}"
        elif isinstance(self.dpid, str):
            dpid_clean = self.dpid.replace("0x", "").replace(":", "")
            self.dpid = f"{int(dpid_clean, 16):016x}"


@dataclass
class MetricsData:
    """Dati delle metriche di prestazioni"""
    port_statistics: Dict[str, List[PortMetrics]]  # dpid -> list of port metrics
    aggregated_metrics: Dict[str, AggregatedMetrics] = field(default_factory=dict)
    quality_indicators: Optional['QualityMetrics'] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione JSON"""
        return {
            "port_statistics": {
                dpid: [
                    {
                        "port_no": port.port_no,
                        "rx_packets": port.rx_packets,
                        "tx_packets": port.tx_packets,
                        "rx_bytes": port.rx_bytes,
                        "tx_bytes": port.tx_bytes,
                        "rx_errors": port.rx_errors,
                        "tx_errors": port.tx_errors,
                        "rx_dropped": port.rx_dropped,
                        "tx_dropped": port.tx_dropped
                    }
                    for port in ports
                ]
                for dpid, ports in self.port_statistics.items()
            },
            "aggregated_metrics": {
                dpid: {
                    "dpid": metrics.dpid,
                    "total_rx_packets": metrics.total_rx_packets,
                    "total_tx_packets": metrics.total_tx_packets,
                    "total_rx_bytes": metrics.total_rx_bytes,
                    "total_tx_bytes": metrics.total_tx_bytes,
                    "total_errors": metrics.total_errors,
                    "average_utilization": metrics.average_utilization,
                    "congested_ports": metrics.congested_ports
                }
                for dpid, metrics in self.aggregated_metrics.items()
            },
            "quality_indicators": self.quality_indicators.to_dict() if self.quality_indicators else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MetricsData':
        """Crea istanza da dizionario"""
        port_statistics = {}
        for dpid, ports_data in data.get("port_statistics", {}).items():
            port_statistics[dpid] = [
                PortMetrics(
                    port_no=port_data["port_no"],
                    rx_packets=port_data["rx_packets"],
                    tx_packets=port_data["tx_packets"],
                    rx_bytes=port_data["rx_bytes"],
                    tx_bytes=port_data["tx_bytes"],
                    rx_errors=port_data["rx_errors"],
                    tx_errors=port_data["tx_errors"],
                    rx_dropped=port_data.get("rx_dropped", 0),
                    tx_dropped=port_data.get("tx_dropped", 0)
                )
                for port_data in ports_data
            ]
        
        aggregated_metrics = {}
        for dpid, metrics_data in data.get("aggregated_metrics", {}).items():
            aggregated_metrics[dpid] = AggregatedMetrics(
                dpid=metrics_data["dpid"],
                total_rx_packets=metrics_data["total_rx_packets"],
                total_tx_packets=metrics_data["total_tx_packets"],
                total_rx_bytes=metrics_data["total_rx_bytes"],
                total_tx_bytes=metrics_data["total_tx_bytes"],
                total_errors=metrics_data["total_errors"],
                average_utilization=metrics_data["average_utilization"],
                congested_ports=metrics_data["congested_ports"]
            )
        
        quality_indicators = None
        if data.get("quality_indicators"):
            from .health import QualityMetrics
            quality_indicators = QualityMetrics.from_dict(data["quality_indicators"])
        
        return cls(
            port_statistics=port_statistics,
            aggregated_metrics=aggregated_metrics,
            quality_indicators=quality_indicators
        )


@dataclass
class SnapshotMetadata:
    """Metadati per uno snapshot di rete"""
    collection_duration_ms: float
    switches_count: int
    links_count: int
    total_ports: int
    data_quality_score: float = 1.0
    errors_encountered: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione JSON"""
        return {
            "collection_duration_ms": self.collection_duration_ms,
            "switches_count": self.switches_count,
            "links_count": self.links_count,
            "total_ports": self.total_ports,
            "data_quality_score": self.data_quality_score,
            "errors_encountered": self.errors_encountered
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SnapshotMetadata':
        """Crea istanza da dizionario"""
        return cls(
            collection_duration_ms=data["collection_duration_ms"],
            switches_count=data["switches_count"],
            links_count=data["links_count"],
            total_ports=data["total_ports"],
            data_quality_score=data.get("data_quality_score", 1.0),
            errors_encountered=data.get("errors_encountered", [])
        )


@dataclass
class DerivedMetrics:
    """Metriche derivate calcolate dai dati grezzi"""
    network_utilization: float
    congestion_level: float
    error_rate: float
    topology_stability: float
    performance_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione JSON"""
        return {
            "network_utilization": self.network_utilization,
            "congestion_level": self.congestion_level,
            "error_rate": self.error_rate,
            "topology_stability": self.topology_stability,
            "performance_score": self.performance_score
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DerivedMetrics':
        """Crea istanza da dizionario"""
        return cls(
            network_utilization=data["network_utilization"],
            congestion_level=data["congestion_level"],
            error_rate=data["error_rate"],
            topology_stability=data["topology_stability"],
            performance_score=data["performance_score"]
        )


@dataclass
class NetworkSnapshot:
    """Snapshot completo dello stato della rete"""
    timestamp: float
    topology: TopologyData
    metrics: MetricsData
    derived_metrics: Optional[DerivedMetrics] = None
    metadata: Optional[SnapshotMetadata] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione JSON"""
        return {
            "timestamp": self.timestamp,
            "topology": self.topology.to_dict(),
            "metrics": self.metrics.to_dict(),
            "derived_metrics": self.derived_metrics.to_dict() if self.derived_metrics else None,
            "metadata": self.metadata.to_dict() if self.metadata else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NetworkSnapshot':
        """Crea istanza da dizionario"""
        topology = TopologyData.from_dict(data["topology"])
        metrics = MetricsData.from_dict(data["metrics"])
        
        derived_metrics = None
        if data.get("derived_metrics"):
            derived_metrics = DerivedMetrics.from_dict(data["derived_metrics"])
        
        metadata = None
        if data.get("metadata"):
            metadata = SnapshotMetadata.from_dict(data["metadata"])
        
        return cls(
            timestamp=data["timestamp"],
            topology=topology,
            metrics=metrics,
            derived_metrics=derived_metrics,
            metadata=metadata
        )
    
    def to_json(self, indent: int = 2) -> str:
        """Serializza in JSON con pretty printing"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'NetworkSnapshot':
        """Crea istanza da stringa JSON"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def get_timestamp_iso(self) -> str:
        """Restituisce il timestamp in formato ISO"""
        return datetime.fromtimestamp(self.timestamp).isoformat()