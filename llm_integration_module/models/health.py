"""
Health monitoring models for Network State Collector

Implementa le dataclass per il monitoraggio della salute del sistema,
inclusi health status, metriche di qualità e indicatori di performance.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum
import time
import json


class HealthStatus(Enum):
    """Stati di salute del sistema"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentType(Enum):
    """Tipi di componenti monitorati"""
    RYU_CONNECTOR = "ryu_connector"
    DATA_PROCESSOR = "data_processor"
    VALIDATOR = "validator"
    SERIALIZER = "serializer"
    FILE_SYSTEM = "file_system"


@dataclass
class HealthCheck:
    """Risultato di un health check"""
    component: ComponentType
    status: HealthStatus
    message: str
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione"""
        return {
            "component": self.component.value,
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp,
            "details": self.details
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HealthCheck':
        """Crea istanza da dizionario"""
        return cls(
            component=ComponentType(data["component"]),
            status=HealthStatus(data["status"]),
            message=data["message"],
            timestamp=data["timestamp"],
            details=data.get("details", {})
        )


@dataclass
class ConnectionHealth:
    """Salute della connessione al controller Ryu"""
    is_reachable: bool
    response_time_ms: float
    last_successful_request: Optional[float] = None
    last_error: Optional[str] = None
    consecutive_failures: int = 0
    success_rate: float = 0.0
    
    @property
    def status(self) -> HealthStatus:
        """Determina lo stato di salute basato sui parametri"""
        if not self.is_reachable:
            return HealthStatus.UNHEALTHY
        elif self.consecutive_failures > 3:
            return HealthStatus.DEGRADED
        elif self.success_rate < 0.5 and self.success_rate > 0:  # Solo se ci sono state richieste
            return HealthStatus.DEGRADED
        elif self.response_time_ms > 5000:  # 5 secondi
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione"""
        return {
            "is_reachable": self.is_reachable,
            "response_time_ms": self.response_time_ms,
            "last_successful_request": self.last_successful_request,
            "last_error": self.last_error,
            "consecutive_failures": self.consecutive_failures,
            "success_rate": self.success_rate,
            "status": self.status.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConnectionHealth':
        """Crea istanza da dizionario"""
        return cls(
            is_reachable=data["is_reachable"],
            response_time_ms=data["response_time_ms"],
            last_successful_request=data.get("last_successful_request"),
            last_error=data.get("last_error"),
            consecutive_failures=data.get("consecutive_failures", 0),
            success_rate=data.get("success_rate", 0.0)
        )


@dataclass
class QualityMetrics:
    """Metriche di qualità dei dati raccolti"""
    completeness_score: float  # 0.0 - 1.0
    consistency_score: float   # 0.0 - 1.0
    timeliness_score: float    # 0.0 - 1.0
    accuracy_score: float      # 0.0 - 1.0
    overall_score: float       # 0.0 - 1.0
    issues_detected: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Calcola il punteggio complessivo"""
        if self.overall_score == 0.0:  # Se non è stato impostato manualmente
            scores = [
                self.completeness_score,
                self.consistency_score,
                self.timeliness_score,
                self.accuracy_score
            ]
            self.overall_score = sum(scores) / len(scores)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione"""
        return {
            "completeness_score": self.completeness_score,
            "consistency_score": self.consistency_score,
            "timeliness_score": self.timeliness_score,
            "accuracy_score": self.accuracy_score,
            "overall_score": self.overall_score,
            "issues_detected": self.issues_detected
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QualityMetrics':
        """Crea istanza da dizionario"""
        return cls(
            completeness_score=data["completeness_score"],
            consistency_score=data["consistency_score"],
            timeliness_score=data["timeliness_score"],
            accuracy_score=data["accuracy_score"],
            overall_score=data["overall_score"],
            issues_detected=data.get("issues_detected", [])
        )


@dataclass
class SystemHealth:
    """Salute complessiva del sistema"""
    overall_status: HealthStatus
    components: Dict[ComponentType, HealthCheck] = field(default_factory=dict)
    connection_health: Optional[ConnectionHealth] = None
    data_quality: Optional[QualityMetrics] = None
    last_update: float = field(default_factory=time.time)
    uptime_seconds: float = 0.0
    
    def add_component_check(self, check: HealthCheck) -> None:
        """Aggiunge un health check per un componente"""
        self.components[check.component] = check
        self._update_overall_status()
    
    def _update_overall_status(self) -> None:
        """Aggiorna lo stato complessivo basato sui componenti"""
        if not self.components:
            self.overall_status = HealthStatus.UNKNOWN
            return
        
        statuses = [check.status for check in self.components.values()]
        
        if any(status == HealthStatus.UNHEALTHY for status in statuses):
            self.overall_status = HealthStatus.UNHEALTHY
        elif any(status == HealthStatus.DEGRADED for status in statuses):
            self.overall_status = HealthStatus.DEGRADED
        elif all(status == HealthStatus.HEALTHY for status in statuses):
            self.overall_status = HealthStatus.HEALTHY
        else:
            self.overall_status = HealthStatus.UNKNOWN
    
    def get_unhealthy_components(self) -> List[ComponentType]:
        """Restituisce i componenti non sani"""
        return [
            component for component, check in self.components.items()
            if check.status in [HealthStatus.UNHEALTHY, HealthStatus.DEGRADED]
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione"""
        return {
            "overall_status": self.overall_status.value,
            "components": {
                component.value: check.to_dict()
                for component, check in self.components.items()
            },
            "connection_health": self.connection_health.to_dict() if self.connection_health else None,
            "data_quality": self.data_quality.to_dict() if self.data_quality else None,
            "last_update": self.last_update,
            "uptime_seconds": self.uptime_seconds
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SystemHealth':
        """Crea istanza da dizionario"""
        components = {}
        for component_str, check_data in data.get("components", {}).items():
            component = ComponentType(component_str)
            components[component] = HealthCheck.from_dict(check_data)
        
        connection_health = None
        if data.get("connection_health"):
            connection_health = ConnectionHealth.from_dict(data["connection_health"])
        
        data_quality = None
        if data.get("data_quality"):
            data_quality = QualityMetrics.from_dict(data["data_quality"])
        
        return cls(
            overall_status=HealthStatus(data["overall_status"]),
            components=components,
            connection_health=connection_health,
            data_quality=data_quality,
            last_update=data["last_update"],
            uptime_seconds=data.get("uptime_seconds", 0.0)
        )
    
    def to_json(self, indent: int = 2) -> str:
        """Serializza in JSON con pretty printing"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'SystemHealth':
        """Crea istanza da stringa JSON"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class StructuredLogEntry:
    """Entry di log strutturato per errori di connessione"""
    timestamp: float
    level: str
    component: str
    event_type: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    error_details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione"""
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "component": self.component,
            "event_type": self.event_type,
            "message": self.message,
            "context": self.context,
            "error_details": self.error_details
        }
    
    def to_json(self) -> str:
        """Serializza in JSON per logging strutturato"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def create_connection_error(
        cls,
        message: str,
        endpoint: str,
        error_type: str,
        attempt: int,
        max_attempts: int,
        response_time_ms: Optional[float] = None,
        status_code: Optional[int] = None,
        **kwargs
    ) -> 'StructuredLogEntry':
        """Crea un log entry per errori di connessione"""
        context = {
            "endpoint": endpoint,
            "attempt": attempt,
            "max_attempts": max_attempts,
            **kwargs
        }
        
        error_details = {
            "error_type": error_type,
            "response_time_ms": response_time_ms,
            "status_code": status_code
        }
        
        return cls(
            timestamp=time.time(),
            level="ERROR",
            component="ryu_connector",
            event_type="connection_error",
            message=message,
            context=context,
            error_details=error_details
        )
    
    @classmethod
    def create_connection_success(
        cls,
        message: str,
        endpoint: str,
        response_time_ms: float,
        **kwargs
    ) -> 'StructuredLogEntry':
        """Crea un log entry per connessioni riuscite"""
        context = {
            "endpoint": endpoint,
            "response_time_ms": response_time_ms,
            **kwargs
        }
        
        return cls(
            timestamp=time.time(),
            level="INFO",
            component="ryu_connector",
            event_type="connection_success",
            message=message,
            context=context
        )