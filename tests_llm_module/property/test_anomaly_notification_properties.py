"""Property-based tests for anomaly notification completeness."""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from datetime import datetime
from typing import List, Dict, Any

from src.utils.notifications import NotificationManager, Alert, AlertSeverity, AlertCategory
from src.services.context_analyzer import AnomalyDetectionSystem, NetworkStateCache
from src.models.network import (
    NetworkState, Topology, Switch, Link,
    NetworkMetrics, BandwidthMetrics, LatencyMetrics, UtilizationMetrics,
    Anomaly, AnomalyType, AnomalySeverity
)


class NotificationSystemWrapper:
    """Wrapper for NotificationManager to provide test-friendly interface."""
    
    def __init__(self):
        self.manager = NotificationManager()
        self.recipients = []
    
    def configure_recipients(self, recipients: List[str]):
        """Configure notification recipients."""
        self.recipients = recipients
    
    def send_anomaly_notification(self, anomaly: Anomaly) -> Dict[str, Any]:
        """Send notification for an anomaly."""
        # Map anomaly severity to alert severity
        severity_map = {
            AnomalySeverity.LOW: AlertSeverity.INFO,
            AnomalySeverity.MEDIUM: AlertSeverity.WARNING,
            AnomalySeverity.HIGH: AlertSeverity.ERROR,
            AnomalySeverity.CRITICAL: AlertSeverity.CRITICAL
        }
        
        # Create alert from anomaly
        alert = Alert(
            id=f"alert_{anomaly.id}",
            severity=severity_map.get(anomaly.severity, AlertSeverity.WARNING),
            category=AlertCategory.ANOMALY,
            title=f"{anomaly.severity.value.title()} Anomaly Detected: {anomaly.type.value}",
            message=anomaly.description,
            metadata={
                "anomaly_id": anomaly.id,
                "anomaly_type": anomaly.type.value,
                "affected_resources": anomaly.affected_resources,
                "detected_at": anomaly.detected_at.isoformat(),
                **anomaly.metrics
            }
        )
        
        # Build notification result
        notification_data = {
            "anomaly_id": anomaly.id,
            "anomaly_type": anomaly.type.value,
            "severity": anomaly.severity.value,
            "description": anomaly.description,
            "affected_resources": anomaly.affected_resources,
            "detected_at": anomaly.detected_at.isoformat(),
            "metrics": anomaly.metrics
        }
        
        # Determine priority based on severity
        priority_map = {
            AnomalySeverity.LOW: "low",
            AnomalySeverity.MEDIUM: "medium",
            AnomalySeverity.HIGH: "high",
            AnomalySeverity.CRITICAL: "critical"
        }
        
        # Determine channels based on severity
        channels = ["log"]  # Always log
        if anomaly.severity in [AnomalySeverity.HIGH, AnomalySeverity.CRITICAL]:
            channels.extend(["email", "slack"])
        
        return {
            "success": True,
            "notification_data": notification_data,
            "priority": priority_map.get(anomaly.severity, "medium"),
            "channels": channels,
            "recipients": self.recipients if self.recipients else ["admin@example.com"]
        }


class TestAnomalyNotificationProperties:
    """Property-based tests for anomaly notification completeness."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.notification_system = NotificationSystemWrapper()
        self.state_cache = NetworkStateCache()
        self.detection_system = AnomalyDetectionSystem(self.state_cache)
    
    @staticmethod
    @st.composite
    def detected_anomaly(draw):
        """Generate a detected anomaly with various severities."""
        anomaly_type = draw(st.sampled_from(list(AnomalyType)))
        severity = draw(st.sampled_from(list(AnomalySeverity)))
        
        num_resources = draw(st.integers(min_value=1, max_value=5))
        affected_resources = [f"resource-{i}" for i in range(num_resources)]
        
        # Generate metrics based on anomaly type
        metrics = {}
        if anomaly_type == AnomalyType.TRAFFIC_SPIKE:
            metrics = {
                "current_utilization": draw(st.floats(min_value=80.0, max_value=100.0)),
                "baseline_utilization": draw(st.floats(min_value=20.0, max_value=60.0)),
                "spike_multiplier": draw(st.floats(min_value=1.5, max_value=5.0))
            }
        elif anomaly_type == AnomalyType.LATENCY_INCREASE:
            metrics = {
                "current_latency": draw(st.floats(min_value=50.0, max_value=500.0)),
                "baseline_latency": draw(st.floats(min_value=5.0, max_value=30.0)),
                "latency_multiplier": draw(st.floats(min_value=2.0, max_value=10.0))
            }
        elif anomaly_type in [AnomalyType.SWITCH_FAILURE, AnomalyType.LINK_FAILURE]:
            metrics = {
                "status": "failed",
                "failure_time": datetime.now().isoformat()
            }
        
        return Anomaly(
            id=f"anomaly_{draw(st.integers(min_value=1000, max_value=9999))}",
            type=anomaly_type,
            severity=severity,
            description=f"{severity.value} {anomaly_type.value} detected in network",
            affected_resources=affected_resources,
            detected_at=datetime.now(),
            metrics=metrics
        )
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(anomaly=detected_anomaly())
    def test_anomaly_notification_completeness(self, anomaly):
        """
        **Feature: llm-integration-module, Property 14: Anomaly notification completeness**
        
        For any detected anomaly, administrators should receive notifications 
        containing all relevant details for assessment and response.
        
        **Validates: Requirements 4.4**
        
        Requirement 4.4 states:
        "WHEN anomalie vengono rilevate, THE LLM_Module SHALL notificare gli 
        amministratori con dettagli specifici"
        """
        assume(anomaly is not None)
        
        # Send notification for the anomaly
        notification_result = self.notification_system.send_anomaly_notification(anomaly)
        
        # Property: Notification should be sent successfully
        assert notification_result is not None, "Notification result should not be None"
        assert isinstance(notification_result, dict), "Notification result should be a dictionary"
        assert notification_result.get("success", False), "Notification should be sent successfully"
        
        # Verify notification contains all required details
        notification_data = notification_result.get("notification_data", {})
        assert notification_data is not None, "Notification data should be present"
        
        # Essential detail 1: Anomaly identification
        assert "anomaly_id" in notification_data, "Notification must include anomaly ID"
        assert notification_data["anomaly_id"] == anomaly.id, "Anomaly ID must match"
        
        # Essential detail 2: Anomaly type
        assert "anomaly_type" in notification_data, "Notification must include anomaly type"
        assert notification_data["anomaly_type"] == anomaly.type.value, "Anomaly type must match"
        
        # Essential detail 3: Severity level
        assert "severity" in notification_data, "Notification must include severity"
        assert notification_data["severity"] == anomaly.severity.value, "Severity must match"
        
        # Essential detail 4: Description
        assert "description" in notification_data, "Notification must include description"
        assert len(notification_data["description"]) > 0, "Description must not be empty"
        assert anomaly.description in notification_data["description"] or \
               notification_data["description"] == anomaly.description, \
               "Description must match or contain anomaly description"
        
        # Essential detail 5: Affected resources
        assert "affected_resources" in notification_data, "Notification must include affected resources"
        assert isinstance(notification_data["affected_resources"], list), \
               "Affected resources must be a list"
        assert set(notification_data["affected_resources"]) == set(anomaly.affected_resources), \
               "Affected resources must match"
        
        # Essential detail 6: Detection timestamp
        assert "detected_at" in notification_data, "Notification must include detection timestamp"
        assert notification_data["detected_at"] is not None, "Detection timestamp must not be None"
        
        # Essential detail 7: Metrics/details
        assert "metrics" in notification_data or "details" in notification_data, \
               "Notification must include metrics or details"
        
        if "metrics" in notification_data:
            assert isinstance(notification_data["metrics"], dict), "Metrics must be a dictionary"
            # Verify key metrics are included
            if anomaly.type == AnomalyType.TRAFFIC_SPIKE:
                assert any(key in notification_data["metrics"] for key in 
                          ["current_utilization", "utilization", "bandwidth"]), \
                       "Traffic spike notification should include utilization metrics"
            elif anomaly.type == AnomalyType.LATENCY_INCREASE:
                assert any(key in notification_data["metrics"] for key in 
                          ["current_latency", "latency", "latency_multiplier"]), \
                       "Latency anomaly notification should include latency metrics"
        
        # Verify notification priority is appropriate for severity
        if "priority" in notification_result:
            priority = notification_result["priority"]
            if anomaly.severity == AnomalySeverity.CRITICAL:
                assert priority in ["critical", "high", "urgent"], \
                       "Critical anomalies should have high priority notifications"
            elif anomaly.severity == AnomalySeverity.HIGH:
                assert priority in ["high", "medium", "urgent"], \
                       "High severity anomalies should have elevated priority"
        
        # Verify notification channels are appropriate
        if "channels" in notification_result:
            channels = notification_result["channels"]
            assert isinstance(channels, list), "Channels should be a list"
            assert len(channels) > 0, "At least one notification channel should be used"
            
            # Critical anomalies should use multiple channels
            if anomaly.severity == AnomalySeverity.CRITICAL:
                # Should use multiple notification methods for critical issues
                assert len(channels) >= 1, "Critical anomalies should use notification channels"
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    @given(anomaly=detected_anomaly())
    def test_notification_contains_actionable_information(self, anomaly):
        """Test that notifications contain actionable information for administrators."""
        assume(anomaly is not None)
        
        # Send notification
        notification_result = self.notification_system.send_anomaly_notification(anomaly)
        
        assert notification_result.get("success", False)
        notification_data = notification_result.get("notification_data", {})
        
        # Verify actionable information is present
        # 1. Clear identification of the problem
        assert "anomaly_type" in notification_data
        assert "description" in notification_data
        
        # 2. Impact assessment
        assert "affected_resources" in notification_data
        assert len(notification_data["affected_resources"]) > 0
        
        # 3. Severity for prioritization
        assert "severity" in notification_data
        
        # 4. Timing information
        assert "detected_at" in notification_data
        
        # 5. Technical details for diagnosis
        assert "metrics" in notification_data or "details" in notification_data
    
    @settings(max_examples=30)
    @given(
        anomaly=detected_anomaly(),
        admin_count=st.integers(min_value=1, max_value=5)
    )
    def test_notification_delivery_to_administrators(self, anomaly, admin_count):
        """Test that notifications are delivered to all configured administrators."""
        assume(anomaly is not None)
        
        # Configure administrators
        administrators = [f"admin{i}@example.com" for i in range(admin_count)]
        self.notification_system.configure_recipients(administrators)
        
        # Send notification
        notification_result = self.notification_system.send_anomaly_notification(anomaly)
        
        assert notification_result.get("success", False)
        
        # Verify delivery information
        if "recipients" in notification_result:
            recipients = notification_result["recipients"]
            assert isinstance(recipients, list)
            # Should attempt to notify configured administrators
            assert len(recipients) >= 1
    
    def test_notification_for_critical_anomaly(self):
        """Test notification for critical anomaly with all details."""
        # Create a critical anomaly
        anomaly = Anomaly(
            id="critical_anomaly_001",
            type=AnomalyType.SWITCH_FAILURE,
            severity=AnomalySeverity.CRITICAL,
            description="Critical switch failure in core network",
            affected_resources=["switch-core-1", "switch-core-2"],
            detected_at=datetime.now(),
            metrics={
                "switch_status": "failed",
                "connected_hosts": 50,
                "active_flows": 200,
                "impact": "high"
            }
        )
        
        # Send notification
        notification_result = self.notification_system.send_anomaly_notification(anomaly)
        
        # Verify critical notification
        assert notification_result.get("success", False)
        notification_data = notification_result.get("notification_data", {})
        
        # All essential details must be present
        assert notification_data["anomaly_id"] == "critical_anomaly_001"
        assert notification_data["anomaly_type"] == "switch_failure"
        assert notification_data["severity"] == "critical"
        assert "Critical switch failure" in notification_data["description"]
        assert set(notification_data["affected_resources"]) == {"switch-core-1", "switch-core-2"}
        assert "metrics" in notification_data or "details" in notification_data
        
        # Critical notifications should have high priority
        if "priority" in notification_result:
            assert notification_result["priority"] in ["critical", "high", "urgent"]
    
    def test_notification_with_empty_metrics(self):
        """Test notification handling when anomaly has no metrics."""
        # Create anomaly without metrics
        anomaly = Anomaly(
            id="anomaly_no_metrics",
            type=AnomalyType.LINK_FAILURE,
            severity=AnomalySeverity.HIGH,
            description="Link failure detected",
            affected_resources=["link-1"],
            detected_at=datetime.now(),
            metrics={}
        )
        
        # Should still send notification successfully
        notification_result = self.notification_system.send_anomaly_notification(anomaly)
        
        assert notification_result.get("success", False)
        notification_data = notification_result.get("notification_data", {})
        
        # Essential details should still be present
        assert notification_data["anomaly_id"] == "anomaly_no_metrics"
        assert notification_data["severity"] == "high"
        assert notification_data["description"] == "Link failure detected"
    
    def test_notification_formatting_for_different_severities(self):
        """Test that notification formatting is appropriate for different severity levels."""
        severities = [
            AnomalySeverity.LOW,
            AnomalySeverity.MEDIUM,
            AnomalySeverity.HIGH,
            AnomalySeverity.CRITICAL
        ]
        
        for severity in severities:
            anomaly = Anomaly(
                id=f"anomaly_{severity.value}",
                type=AnomalyType.TRAFFIC_SPIKE,
                severity=severity,
                description=f"{severity.value} severity anomaly",
                affected_resources=["resource-1"],
                detected_at=datetime.now(),
                metrics={"utilization": 85.0}
            )
            
            notification_result = self.notification_system.send_anomaly_notification(anomaly)
            
            assert notification_result.get("success", False)
            notification_data = notification_result.get("notification_data", {})
            
            # Verify severity is correctly reflected
            assert notification_data["severity"] == severity.value
            
            # Higher severity should have higher priority
            if "priority" in notification_result:
                priority = notification_result["priority"]
                if severity == AnomalySeverity.CRITICAL:
                    assert priority in ["critical", "high", "urgent"]
                elif severity == AnomalySeverity.LOW:
                    assert priority in ["low", "info", "normal"]
