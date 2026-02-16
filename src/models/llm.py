"""
Modelli dati per l'integrazione con LLM

Contiene le strutture dati ottimizzate per l'integrazione con i modelli
di linguaggio del team per l'analisi intelligente della rete.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import json


@dataclass
class AnomalyIndicator:
    """Indicatore di anomalia per l'analisi LLM"""
    type: str  # "performance", "topology", "error_rate", etc.
    severity: float  # 0.0 - 1.0
    description: str
    affected_components: List[str]
    timestamp: float
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione JSON"""
        return {
            "type": self.type,
            "severity": self.severity,
            "description": self.description,
            "affected_components": self.affected_components,
            "timestamp": self.timestamp,
            "confidence": self.confidence
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnomalyIndicator':
        """Crea istanza da dizionario"""
        return cls(
            type=data["type"],
            severity=data["severity"],
            description=data["description"],
            affected_components=data["affected_components"],
            timestamp=data["timestamp"],
            confidence=data.get("confidence", 1.0)
        )


@dataclass
class ContextEmbedding:
    """Embedding del contesto di rete per LLM"""
    topology_embedding: Dict[str, Any]
    performance_embedding: Dict[str, Any]
    temporal_embedding: Dict[str, Any]
    dimension: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione JSON"""
        return {
            "topology_embedding": self.topology_embedding,
            "performance_embedding": self.performance_embedding,
            "temporal_embedding": self.temporal_embedding,
            "dimension": self.dimension
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContextEmbedding':
        """Crea istanza da dizionario"""
        return cls(
            topology_embedding=data["topology_embedding"],
            performance_embedding=data["performance_embedding"],
            temporal_embedding=data["temporal_embedding"],
            dimension=data["dimension"]
        )


@dataclass
class LLMNetworkData:
    """Dati di rete ottimizzati per l'integrazione LLM"""
    network_context: Dict[str, Any]
    performance_vectors: List[List[float]]
    topology_embedding: Dict[str, Any]
    temporal_features: Dict[str, Any]
    anomaly_indicators: List[AnomalyIndicator] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione JSON"""
        return {
            "network_context": self.network_context,
            "performance_vectors": self.performance_vectors,
            "topology_embedding": self.topology_embedding,
            "temporal_features": self.temporal_features,
            "anomaly_indicators": [
                indicator.to_dict() for indicator in self.anomaly_indicators
            ]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LLMNetworkData':
        """Crea istanza da dizionario"""
        anomaly_indicators = [
            AnomalyIndicator.from_dict(indicator_data)
            for indicator_data in data.get("anomaly_indicators", [])
        ]
        
        return cls(
            network_context=data["network_context"],
            performance_vectors=data["performance_vectors"],
            topology_embedding=data["topology_embedding"],
            temporal_features=data["temporal_features"],
            anomaly_indicators=anomaly_indicators
        )
    
    def to_json(self, indent: int = 2) -> str:
        """Serializza in JSON con pretty printing"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'LLMNetworkData':
        """Crea istanza da stringa JSON"""
        data = json.loads(json_str)
        return cls.from_dict(data)