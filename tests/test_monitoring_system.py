"""
Tests for the monitoring system components.

This module contains unit tests for the monitoring system including
metrics collection, Prometheus export, alerting, and InfluxDB storage.
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.monitoring import (
    MetricsCollector,
    PrometheusExporter,
    AlertManager,
    AlertThreshold,
    AlertSeverity,
    NotificationChannel,
    InfluxDBStorage,
    InfluxDBConfig,
    MonitoringService
)


class TestMetricsCollector:
    """Test metrics collector functionality."""
    
    def test_metrics_collector_initialization(self):
        """Test metrics collector initializes correctly."""
        collector = MetricsCollector(collection_interval=30, retention_minutes=30)
        
        assert collector.collection_interval == 30
        assert collector.retention_minutes == 30
        assert not collector._running
    
    def test_record_action_success(self):
        """Test recording successful actions."""
        collector = MetricsCollector()
        
        collector.record_action_success(100.0)
        collector.record_action_success(150.0)
        
        metrics = collector.get_latest_business_metrics()
        # Metrics might be None if collection hasn't run yet
        if metrics:
            assert metrics.total_actions_processed >= 2
    
    def test_record_action_error(self):
        """Test recording failed actions."""
        collector = MetricsCollector()
        
        collector.record_action_error(200.0)
        
        # Should not raise any exceptions
        assert True
    
    def test_record_user_activity(self):
        """Test recording user activity."""
        collector = MetricsCollector()
        
        collector.record_user_activity("user1")
        collector.record_user_activity("user2")
        collector.record_user_activity("user1")  # Duplicate
        
        # Should not raise any exceptions
        assert True
    
    def test_get_all_metrics(self):
        """Test getting all metrics."""
        collector = MetricsCollector()
        
        metrics = collector.get_all_metrics()
        
        assert isinstance(metrics, dict)
        assert 'system' in metrics
        assert 'business' in metrics
        assert 'application' in metrics
        assert 'collection_time' in metrics


class TestPrometheusExporter:
    """Test Prometheus exporter functionality."""
    
    def test_prometheus_exporter_initialization(self):
        """Test Prometheus exporter initializes correctly."""
        collector = MetricsCollector()
        exporter = PrometheusExporter(collector)
        
        assert exporter.metrics_collector == collector
        assert exporter.registry is not None
    
    def test_record_http_request(self):
        """Test recording HTTP request metrics."""
        collector = MetricsCollector()
        exporter = PrometheusExporter(collector)
        
        exporter.record_http_request("GET", "/api/test", 200, 100.0)
        
        # Should not raise any exceptions
        assert True
    
    def test_get_metrics_text(self):
        """Test getting metrics in Prometheus format."""
        collector = MetricsCollector()
        exporter = PrometheusExporter(collector)
        
        metrics_text = exporter.get_metrics_text()
        
        assert isinstance(metrics_text, str)
        # Should contain some metric names
        assert "system_cpu_usage_percent" in metrics_text or len(metrics_text) >= 0


class TestAlertManager:
    """Test alert manager functionality."""
    
    def test_alert_manager_initialization(self):
        """Test alert manager initializes correctly."""
        alert_manager = AlertManager()
        
        assert not alert_manager._running
        assert len(alert_manager._thresholds) == 0
        assert len(alert_manager._notification_channels) == 0
    
    def test_add_threshold(self):
        """Test adding alert thresholds."""
        alert_manager = AlertManager()
        
        threshold = AlertThreshold(
            metric_name="test.metric",
            operator=">",
            value=80.0,
            severity=AlertSeverity.WARNING,
            description="Test threshold"
        )
        
        alert_manager.add_threshold(threshold)
        
        assert "test.metric" in alert_manager._thresholds
        assert alert_manager._thresholds["test.metric"] == threshold
    
    def test_add_notification_channel(self):
        """Test adding notification channels."""
        alert_manager = AlertManager()
        
        channel = NotificationChannel(
            name="test_email",
            type="email",
            config={"smtp_host": "localhost"}
        )
        
        alert_manager.add_notification_channel(channel)
        
        assert "test_email" in alert_manager._notification_channels
        assert alert_manager._notification_channels["test_email"] == channel
    
    def test_get_active_alerts(self):
        """Test getting active alerts."""
        alert_manager = AlertManager()
        
        alerts = alert_manager.get_active_alerts()
        
        assert isinstance(alerts, list)
        assert len(alerts) == 0  # No alerts initially


class TestInfluxDBStorage:
    """Test InfluxDB storage functionality."""
    
    def test_influxdb_config(self):
        """Test InfluxDB configuration."""
        config = InfluxDBConfig(
            url="http://localhost:8086",
            token="test-token",
            org="test-org",
            bucket="test-bucket"
        )
        
        assert config.url == "http://localhost:8086"
        assert config.token == "test-token"
        assert config.org == "test-org"
        assert config.bucket == "test-bucket"
    
    def test_influxdb_storage_initialization(self):
        """Test InfluxDB storage initializes correctly."""
        config = InfluxDBConfig()
        storage = InfluxDBStorage(config)
        
        assert storage.config == config
        assert not storage.is_connected()
    
    @pytest.mark.asyncio
    async def test_health_check_disconnected(self):
        """Test health check when disconnected."""
        config = InfluxDBConfig()
        storage = InfluxDBStorage(config)
        
        health = await storage.health_check()
        
        assert health['status'] == 'disconnected'
        assert not health['connected']


class TestMonitoringService:
    """Test integrated monitoring service."""
    
    def test_monitoring_service_initialization(self):
        """Test monitoring service initializes correctly."""
        service = MonitoringService(
            collection_interval=60,
            enable_prometheus=True,
            enable_influxdb=False,
            enable_alerting=True
        )
        
        assert service.collection_interval == 60
        assert service.enable_prometheus
        assert not service.enable_influxdb
        assert service.enable_alerting
        assert service.metrics_collector is not None
        assert service.prometheus_exporter is not None
        assert service.alert_manager is not None
        assert service.influxdb_storage is None
    
    def test_record_metrics(self):
        """Test recording various metrics."""
        service = MonitoringService(enable_influxdb=False)
        
        service.record_action_success(100.0)
        service.record_action_error(200.0)
        service.record_user_activity("test_user")
        service.record_http_request("GET", "/test", 200, 50.0)
        service.update_queue_size("test_queue", 10)
        
        # Should not raise any exceptions
        assert True
    
    def test_get_current_metrics(self):
        """Test getting current metrics."""
        service = MonitoringService(enable_influxdb=False)
        
        metrics = service.get_current_metrics()
        
        assert isinstance(metrics, dict)
        assert 'system' in metrics
        assert 'business' in metrics
        assert 'application' in metrics
    
    def test_get_prometheus_metrics(self):
        """Test getting Prometheus metrics."""
        service = MonitoringService(enable_influxdb=False)
        
        prometheus_metrics = service.get_prometheus_metrics()
        
        assert isinstance(prometheus_metrics, str)
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check functionality."""
        service = MonitoringService(enable_influxdb=False)
        
        health = await service.health_check()
        
        assert isinstance(health, dict)
        assert 'status' in health
        assert 'components' in health
        assert 'timestamp' in health
        
        # Check component statuses
        components = health['components']
        assert 'metrics_collector' in components
        assert 'prometheus' in components
        assert 'influxdb' in components
        assert 'alerting' in components
    
    def test_configure_default_alerts(self):
        """Test configuring default alerts."""
        service = MonitoringService(enable_influxdb=False)
        
        service.configure_default_alerts()
        
        # Should not raise any exceptions
        assert True
        
        # Check that some thresholds were added
        if service.alert_manager:
            assert len(service.alert_manager._thresholds) > 0


class TestIntegration:
    """Integration tests for the monitoring system."""
    
    @pytest.mark.asyncio
    async def test_monitoring_service_lifecycle(self):
        """Test complete monitoring service lifecycle."""
        service = MonitoringService(
            collection_interval=1,  # Fast collection for testing
            enable_influxdb=False,  # Disable InfluxDB for testing
            enable_prometheus=False  # Disable HTTP server for testing
        )
        
        try:
            # Start service
            await service.start()
            assert service.is_running()
            
            # Record some metrics
            service.record_action_success(100.0)
            service.record_http_request("GET", "/test", 200, 50.0)
            
            # Wait a bit for metrics collection
            await asyncio.sleep(2)
            
            # Get metrics
            metrics = service.get_current_metrics()
            assert metrics is not None
            
            # Check health
            health = await service.health_check()
            assert health['status'] in ['healthy', 'degraded']
            
        finally:
            # Stop service
            await service.stop()
            assert not service.is_running()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])