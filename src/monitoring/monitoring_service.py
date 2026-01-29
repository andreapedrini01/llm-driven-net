"""
Integrated monitoring service for Northbound Script Generator.

This module provides a unified monitoring service that coordinates
metrics collection, Prometheus export, alerting, and InfluxDB storage.
"""

import asyncio
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from .metrics_collector import MetricsCollector
from .prometheus_exporter import PrometheusExporter
from .alert_manager import AlertManager, AlertThreshold, NotificationChannel
from .influxdb_storage import InfluxDBStorage, InfluxDBConfig, MetricsWriter

logger = logging.getLogger(__name__)


class MonitoringService:
    """
    Unified monitoring service that coordinates all monitoring components.
    
    Provides a single interface for starting/stopping monitoring,
    configuring alerts, and accessing metrics data.
    """
    
    def __init__(self, 
                 collection_interval: int = 60,
                 influxdb_config: Optional[InfluxDBConfig] = None,
                 enable_prometheus: bool = True,
                 enable_influxdb: bool = True,
                 enable_alerting: bool = True):
        """
        Initialize monitoring service.
        
        Args:
            collection_interval: Metrics collection interval in seconds
            influxdb_config: InfluxDB configuration (optional)
            enable_prometheus: Enable Prometheus metrics export
            enable_influxdb: Enable InfluxDB storage
            enable_alerting: Enable alerting system
        """
        self.collection_interval = collection_interval
        self.enable_prometheus = enable_prometheus
        self.enable_influxdb = enable_influxdb
        self.enable_alerting = enable_alerting
        
        # Initialize components
        self.metrics_collector = MetricsCollector(
            collection_interval=collection_interval,
            retention_minutes=60
        )
        
        # Prometheus exporter
        self.prometheus_exporter = None
        if enable_prometheus:
            self.prometheus_exporter = PrometheusExporter(self.metrics_collector)
        
        # InfluxDB storage
        self.influxdb_storage = None
        self.metrics_writer = None
        if enable_influxdb and influxdb_config:
            self.influxdb_storage = InfluxDBStorage(influxdb_config)
            self.metrics_writer = MetricsWriter(self.influxdb_storage)
        
        # Alert manager
        self.alert_manager = None
        if enable_alerting:
            self.alert_manager = AlertManager()
            self.alert_manager.set_metrics_callback(self._get_current_metrics)
        
        # State
        self._running = False
        self._storage_sync_task: Optional[asyncio.Task] = None
        
        logger.info("MonitoringService initialized")
    
    async def start(self) -> None:
        """Start all monitoring components."""
        if self._running:
            logger.warning("MonitoringService already running")
            return
        
        logger.info("Starting MonitoringService...")
        
        try:
            # Start metrics collector
            self.metrics_collector.start()
            
            # Connect to InfluxDB and start metrics writer
            if self.influxdb_storage and self.metrics_writer:
                connected = await self.influxdb_storage.connect()
                if connected:
                    await self.metrics_writer.start()
                    # Start storage sync task
                    self._storage_sync_task = asyncio.create_task(self._storage_sync_loop())
                else:
                    logger.warning("Failed to connect to InfluxDB, storage disabled")
            
            # Start alert manager
            if self.alert_manager:
                self.alert_manager.start()
            
            # Start Prometheus HTTP server (optional)
            if self.prometheus_exporter:
                try:
                    self.prometheus_exporter.start_http_server(port=8000)
                except Exception as e:
                    logger.warning(f"Failed to start Prometheus HTTP server: {e}")
            
            self._running = True
            logger.info("MonitoringService started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start MonitoringService: {e}")
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """Stop all monitoring components."""
        if not self._running:
            return
        
        logger.info("Stopping MonitoringService...")
        
        # Stop storage sync task
        if self._storage_sync_task:
            self._storage_sync_task.cancel()
            try:
                await self._storage_sync_task
            except asyncio.CancelledError:
                pass
        
        # Stop metrics writer
        if self.metrics_writer:
            await self.metrics_writer.stop()
        
        # Disconnect from InfluxDB
        if self.influxdb_storage:
            self.influxdb_storage.disconnect()
        
        # Stop alert manager
        if self.alert_manager:
            self.alert_manager.stop()
        
        # Stop metrics collector
        self.metrics_collector.stop()
        
        self._running = False
        logger.info("MonitoringService stopped")
    
    async def _storage_sync_loop(self) -> None:
        """Sync metrics to InfluxDB storage."""
        while self._running:
            try:
                # Get latest metrics
                system_metrics = self.metrics_collector.get_latest_system_metrics()
                business_metrics = self.metrics_collector.get_latest_business_metrics()
                app_metrics = self.metrics_collector.get_latest_application_metrics()
                
                # Write to InfluxDB
                if system_metrics and self.metrics_writer:
                    await self.metrics_writer.write_metrics(system_metrics)
                
                if business_metrics and self.metrics_writer:
                    await self.metrics_writer.write_metrics(business_metrics)
                
                if app_metrics and self.metrics_writer:
                    await self.metrics_writer.write_metrics(app_metrics)
                
                # Wait for next sync
                await asyncio.sleep(self.collection_interval)
                
            except Exception as e:
                logger.error(f"Error in storage sync loop: {e}")
                await asyncio.sleep(self.collection_interval)
    
    def _get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics for alert manager."""
        return self.metrics_collector.get_all_metrics()
    
    # Metrics recording methods
    
    def record_action_success(self, response_time_ms: float) -> None:
        """Record a successful action."""
        self.metrics_collector.record_action_success(response_time_ms)
    
    def record_action_error(self, response_time_ms: float) -> None:
        """Record a failed action."""
        self.metrics_collector.record_action_error(response_time_ms)
    
    def record_user_activity(self, user_id: str) -> None:
        """Record user activity."""
        self.metrics_collector.record_user_activity(user_id)
    
    def record_http_request(self, method: str, endpoint: str, status_code: int, duration_ms: float) -> None:
        """Record HTTP request metrics."""
        self.metrics_collector.record_http_request(duration_ms)
        if self.prometheus_exporter:
            self.prometheus_exporter.record_http_request(method, endpoint, status_code, duration_ms)
    
    def update_queue_size(self, queue_name: str, size: int) -> None:
        """Update queue size metrics."""
        self.metrics_collector.update_queue_size(size)
        if self.prometheus_exporter:
            self.prometheus_exporter.update_queue_size(queue_name, size)
    
    # Alert management methods
    
    def add_alert_threshold(self, threshold: AlertThreshold) -> None:
        """Add an alert threshold."""
        if self.alert_manager:
            self.alert_manager.add_threshold(threshold)
    
    def add_notification_channel(self, channel: NotificationChannel) -> None:
        """Add a notification channel."""
        if self.alert_manager:
            self.alert_manager.add_notification_channel(channel)
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert."""
        if self.alert_manager:
            return self.alert_manager.acknowledge_alert(alert_id, acknowledged_by)
        return False
    
    def get_active_alerts(self) -> List:
        """Get active alerts."""
        if self.alert_manager:
            return self.alert_manager.get_active_alerts()
        return []
    
    # Metrics access methods
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        return self.metrics_collector.get_all_metrics()
    
    def get_prometheus_metrics(self) -> str:
        """Get Prometheus metrics text."""
        if self.prometheus_exporter:
            return self.prometheus_exporter.get_metrics_text()
        return ""
    
    async def get_historical_metrics(self, 
                                   measurement: str,
                                   start_time: datetime,
                                   end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get historical metrics from InfluxDB."""
        if self.influxdb_storage:
            return await self.influxdb_storage.query_metrics(
                measurement=measurement,
                start_time=start_time,
                end_time=end_time
            )
        return []
    
    # Health check methods
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        health = {
            'status': 'healthy',
            'components': {},
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Check metrics collector
        health['components']['metrics_collector'] = {
            'status': 'healthy' if self.metrics_collector else 'disabled',
            'latest_metrics': self.metrics_collector.get_latest_system_metrics() is not None
        }
        
        # Check Prometheus exporter
        if self.prometheus_exporter:
            health['components']['prometheus'] = {
                'status': 'healthy',
                'metrics_available': len(self.get_prometheus_metrics()) > 0
            }
        else:
            health['components']['prometheus'] = {'status': 'disabled'}
        
        # Check InfluxDB
        if self.influxdb_storage:
            influx_health = await self.influxdb_storage.health_check()
            health['components']['influxdb'] = influx_health
        else:
            health['components']['influxdb'] = {'status': 'disabled'}
        
        # Check alert manager
        if self.alert_manager:
            alert_stats = self.alert_manager.get_alert_statistics()
            health['components']['alerting'] = {
                'status': 'healthy',
                'active_alerts': alert_stats['active_alerts'],
                'thresholds': alert_stats['total_thresholds']
            }
        else:
            health['components']['alerting'] = {'status': 'disabled'}
        
        # Determine overall status
        component_statuses = [comp.get('status', 'unknown') for comp in health['components'].values()]
        if any(status == 'error' for status in component_statuses):
            health['status'] = 'unhealthy'
        elif any(status == 'warning' for status in component_statuses):
            health['status'] = 'degraded'
        
        return health
    
    # Configuration methods
    
    def configure_default_alerts(self) -> None:
        """Configure default alert thresholds."""
        if not self.alert_manager:
            return
        
        from .alert_manager import AlertSeverity
        
        # System alerts
        default_thresholds = [
            AlertThreshold(
                metric_name="system.cpu_usage_percent",
                operator=">",
                value=80.0,
                severity=AlertSeverity.WARNING,
                duration_seconds=300,
                description="High CPU usage detected"
            ),
            AlertThreshold(
                metric_name="system.cpu_usage_percent", 
                operator=">",
                value=95.0,
                severity=AlertSeverity.CRITICAL,
                duration_seconds=60,
                description="Critical CPU usage detected"
            ),
            AlertThreshold(
                metric_name="system.memory_usage_percent",
                operator=">",
                value=85.0,
                severity=AlertSeverity.WARNING,
                duration_seconds=300,
                description="High memory usage detected"
            ),
            AlertThreshold(
                metric_name="system.memory_usage_percent",
                operator=">",
                value=95.0,
                severity=AlertSeverity.CRITICAL,
                duration_seconds=60,
                description="Critical memory usage detected"
            ),
            AlertThreshold(
                metric_name="business.error_rate_percent",
                operator=">",
                value=5.0,
                severity=AlertSeverity.WARNING,
                duration_seconds=120,
                description="High error rate detected"
            ),
            AlertThreshold(
                metric_name="business.error_rate_percent",
                operator=">",
                value=15.0,
                severity=AlertSeverity.CRITICAL,
                duration_seconds=60,
                description="Critical error rate detected"
            )
        ]
        
        for threshold in default_thresholds:
            self.alert_manager.add_threshold(threshold)
        
        logger.info("Default alert thresholds configured")
    
    def is_running(self) -> bool:
        """Check if monitoring service is running."""
        return self._running