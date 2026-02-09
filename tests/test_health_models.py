"""
Test per i modelli di health monitoring

Include test unitari per validare i modelli di salute del sistema,
logging strutturato e metriche di qualità.
"""

import pytest
import json
import time
from network_state_collector.models.health import (
    HealthStatus, ComponentType, HealthCheck, ConnectionHealth,
    QualityMetrics, SystemHealth, StructuredLogEntry
)


class TestHealthModels:
    """Test per i modelli di health monitoring"""
    
    def test_health_check_creation(self):
        """Test creazione HealthCheck"""
        check = HealthCheck(
            component=ComponentType.RYU_CONNECTOR,
            status=HealthStatus.HEALTHY,
            message="All systems operational",
            details={"uptime": 3600}
        )
        
        assert check.component == ComponentType.RYU_CONNECTOR
        assert check.status == HealthStatus.HEALTHY
        assert check.message == "All systems operational"
        assert check.details["uptime"] == 3600
        assert isinstance(check.timestamp, float)
    
    def test_health_check_serialization(self):
        """Test serializzazione HealthCheck"""
        check = HealthCheck(
            component=ComponentType.RYU_CONNECTOR,
            status=HealthStatus.DEGRADED,
            message="Performance issues detected"
        )
        
        # Test to_dict
        data = check.to_dict()
        assert data["component"] == "ryu_connector"
        assert data["status"] == "degraded"
        assert data["message"] == "Performance issues detected"
        
        # Test from_dict
        restored = HealthCheck.from_dict(data)
        assert restored.component == check.component
        assert restored.status == check.status
        assert restored.message == check.message
    
    def test_connection_health_status_logic(self):
        """Test logica di determinazione stato ConnectionHealth"""
        # Test healthy
        health = ConnectionHealth(
            is_reachable=True,
            response_time_ms=100.0,
            consecutive_failures=0,
            success_rate=0.95
        )
        assert health.status == HealthStatus.HEALTHY
        
        # Test unhealthy (not reachable)
        health.is_reachable = False
        assert health.status == HealthStatus.UNHEALTHY
        
        # Test degraded (high response time)
        health.is_reachable = True
        health.response_time_ms = 6000.0
        assert health.status == HealthStatus.DEGRADED
        
        # Test degraded (consecutive failures)
        health.response_time_ms = 100.0
        health.consecutive_failures = 5
        assert health.status == HealthStatus.DEGRADED
        
        # Test degraded (low success rate with requests)
        health.consecutive_failures = 0
        health.success_rate = 0.3
        assert health.status == HealthStatus.DEGRADED
        
        # Test healthy (low success rate but no requests yet)
        health.success_rate = 0.0
        assert health.status == HealthStatus.HEALTHY
    
    def test_quality_metrics_calculation(self):
        """Test calcolo automatico punteggio complessivo QualityMetrics"""
        metrics = QualityMetrics(
            completeness_score=0.9,
            consistency_score=0.8,
            timeliness_score=0.95,
            accuracy_score=0.85,
            overall_score=0.0  # Dovrebbe essere calcolato automaticamente
        )
        
        expected_overall = (0.9 + 0.8 + 0.95 + 0.85) / 4
        assert abs(metrics.overall_score - expected_overall) < 0.001
    
    def test_quality_metrics_manual_override(self):
        """Test override manuale punteggio complessivo"""
        metrics = QualityMetrics(
            completeness_score=0.9,
            consistency_score=0.8,
            timeliness_score=0.95,
            accuracy_score=0.85,
            overall_score=0.7  # Override manuale
        )
        
        assert metrics.overall_score == 0.7
    
    def test_system_health_overall_status(self):
        """Test determinazione stato complessivo SystemHealth"""
        system_health = SystemHealth(overall_status=HealthStatus.UNKNOWN)
        
        # Aggiungi componente healthy
        healthy_check = HealthCheck(
            component=ComponentType.RYU_CONNECTOR,
            status=HealthStatus.HEALTHY,
            message="OK"
        )
        system_health.add_component_check(healthy_check)
        assert system_health.overall_status == HealthStatus.HEALTHY
        
        # Aggiungi componente degraded
        degraded_check = HealthCheck(
            component=ComponentType.DATA_PROCESSOR,
            status=HealthStatus.DEGRADED,
            message="Slow"
        )
        system_health.add_component_check(degraded_check)
        assert system_health.overall_status == HealthStatus.DEGRADED
        
        # Aggiungi componente unhealthy
        unhealthy_check = HealthCheck(
            component=ComponentType.VALIDATOR,
            status=HealthStatus.UNHEALTHY,
            message="Failed"
        )
        system_health.add_component_check(unhealthy_check)
        assert system_health.overall_status == HealthStatus.UNHEALTHY
    
    def test_system_health_unhealthy_components(self):
        """Test identificazione componenti non sani"""
        system_health = SystemHealth(overall_status=HealthStatus.UNKNOWN)
        
        # Aggiungi vari componenti
        system_health.add_component_check(HealthCheck(
            component=ComponentType.RYU_CONNECTOR,
            status=HealthStatus.HEALTHY,
            message="OK"
        ))
        
        system_health.add_component_check(HealthCheck(
            component=ComponentType.DATA_PROCESSOR,
            status=HealthStatus.DEGRADED,
            message="Slow"
        ))
        
        system_health.add_component_check(HealthCheck(
            component=ComponentType.VALIDATOR,
            status=HealthStatus.UNHEALTHY,
            message="Failed"
        ))
        
        unhealthy = system_health.get_unhealthy_components()
        assert len(unhealthy) == 2
        assert ComponentType.DATA_PROCESSOR in unhealthy
        assert ComponentType.VALIDATOR in unhealthy
        assert ComponentType.RYU_CONNECTOR not in unhealthy
    
    def test_structured_log_entry_connection_error(self):
        """Test creazione log entry per errori di connessione"""
        log_entry = StructuredLogEntry.create_connection_error(
            message="Connection timeout",
            endpoint="/stats/switches",
            error_type="timeout",
            attempt=2,
            max_attempts=3,
            response_time_ms=5000.0,
            status_code=None
        )
        
        assert log_entry.level == "ERROR"
        assert log_entry.component == "ryu_connector"
        assert log_entry.event_type == "connection_error"
        assert log_entry.message == "Connection timeout"
        assert log_entry.context["endpoint"] == "/stats/switches"
        assert log_entry.context["attempt"] == 2
        assert log_entry.context["max_attempts"] == 3
        assert log_entry.error_details["error_type"] == "timeout"
        assert log_entry.error_details["response_time_ms"] == 5000.0
    
    def test_structured_log_entry_connection_success(self):
        """Test creazione log entry per connessioni riuscite"""
        log_entry = StructuredLogEntry.create_connection_success(
            message="Request successful",
            endpoint="/stats/switches",
            response_time_ms=150.0
        )
        
        assert log_entry.level == "INFO"
        assert log_entry.component == "ryu_connector"
        assert log_entry.event_type == "connection_success"
        assert log_entry.message == "Request successful"
        assert log_entry.context["endpoint"] == "/stats/switches"
        assert log_entry.context["response_time_ms"] == 150.0
    
    def test_structured_log_entry_json_serialization(self):
        """Test serializzazione JSON dei log entry"""
        log_entry = StructuredLogEntry.create_connection_error(
            message="Test error",
            endpoint="/test",
            error_type="test",
            attempt=1,
            max_attempts=3
        )
        
        json_str = log_entry.to_json()
        data = json.loads(json_str)
        
        assert data["level"] == "ERROR"
        assert data["component"] == "ryu_connector"
        assert data["event_type"] == "connection_error"
        assert data["message"] == "Test error"
        assert data["context"]["endpoint"] == "/test"
    
    def test_health_models_round_trip_serialization(self):
        """Test serializzazione round-trip per tutti i modelli"""
        # Test ConnectionHealth
        conn_health = ConnectionHealth(
            is_reachable=True,
            response_time_ms=200.0,
            last_successful_request=time.time(),
            last_error="Previous error",
            consecutive_failures=1,
            success_rate=0.8
        )
        
        data = conn_health.to_dict()
        restored = ConnectionHealth.from_dict(data)
        assert restored.is_reachable == conn_health.is_reachable
        assert restored.response_time_ms == conn_health.response_time_ms
        assert restored.success_rate == conn_health.success_rate
        
        # Test QualityMetrics
        quality = QualityMetrics(
            completeness_score=0.9,
            consistency_score=0.8,
            timeliness_score=0.95,
            accuracy_score=0.85,
            overall_score=0.0,  # Will be calculated automatically
            issues_detected=["Issue 1", "Issue 2"]
        )
        
        data = quality.to_dict()
        restored = QualityMetrics.from_dict(data)
        assert restored.completeness_score == quality.completeness_score
        assert restored.issues_detected == quality.issues_detected
        
        # Test SystemHealth
        system_health = SystemHealth(
            overall_status=HealthStatus.HEALTHY,
            connection_health=conn_health,
            data_quality=quality,
            uptime_seconds=3600.0
        )
        
        json_str = system_health.to_json()
        restored = SystemHealth.from_json(json_str)
        assert restored.overall_status == system_health.overall_status
        assert restored.uptime_seconds == system_health.uptime_seconds
        assert restored.connection_health.is_reachable == conn_health.is_reachable
        assert restored.data_quality.completeness_score == quality.completeness_score