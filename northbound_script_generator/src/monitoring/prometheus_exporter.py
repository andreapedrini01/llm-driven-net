"""
Prometheus metrics exporter for Northbound Script Generator.

This module exposes collected metrics in Prometheus format for scraping
by Prometheus server or compatible monitoring systems.
"""

import time
from typing import Optional, Dict, Any
from prometheus_client import (
    Counter, Gauge, Histogram, Info, 
    CollectorRegistry, generate_latest,
    CONTENT_TYPE_LATEST, start_http_server
)
import logging
from .metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)


class PrometheusExporter:
    """
    Exports metrics to Prometheus format.
    
    Creates and maintains Prometheus metrics that are updated from
    the MetricsCollector data.
    """
    
    def __init__(self, metrics_collector: MetricsCollector, registry: Optional[CollectorRegistry] = None):
        """
        Initialize Prometheus exporter.
        
        Args:
            metrics_collector: The metrics collector to export data from
            registry: Optional custom registry (uses default if None)
        """
        self.metrics_collector = metrics_collector
        self.registry = registry or CollectorRegistry()
        
        # System metrics
        self.cpu_usage = Gauge(
            'system_cpu_usage_percent',
            'CPU usage percentage',
            registry=self.registry
        )
        
        self.memory_usage = Gauge(
            'system_memory_usage_percent', 
            'Memory usage percentage',
            registry=self.registry
        )
        
        self.memory_available = Gauge(
            'system_memory_available_mb',
            'Available memory in MB',
            registry=self.registry
        )
        
        self.network_bytes_sent = Counter(
            'system_network_bytes_sent_total',
            'Total network bytes sent',
            registry=self.registry
        )
        
        self.network_bytes_recv = Counter(
            'system_network_bytes_recv_total',
            'Total network bytes received', 
            registry=self.registry
        )
        
        self.disk_usage = Gauge(
            'system_disk_usage_percent',
            'Disk usage percentage',
            registry=self.registry
        )
        
        self.active_connections = Gauge(
            'system_active_connections',
            'Number of active network connections',
            registry=self.registry
        )
        
        # Business metrics
        self.actions_per_minute = Gauge(
            'business_actions_per_minute',
            'Number of actions processed per minute',
            registry=self.registry
        )
        
        self.success_rate = Gauge(
            'business_success_rate_percent',
            'Success rate percentage',
            registry=self.registry
        )
        
        self.error_rate = Gauge(
            'business_error_rate_percent',
            'Error rate percentage',
            registry=self.registry
        )
        
        self.response_time_p95 = Gauge(
            'business_response_time_p95_ms',
            '95th percentile response time in milliseconds',
            registry=self.registry
        )
        
        self.response_time_avg = Gauge(
            'business_response_time_avg_ms',
            'Average response time in milliseconds',
            registry=self.registry
        )
        
        self.active_users = Gauge(
            'business_active_users',
            'Number of active users',
            registry=self.registry
        )
        
        self.total_actions = Counter(
            'business_total_actions_processed',
            'Total number of actions processed',
            registry=self.registry
        )
        
        # Application metrics
        self.http_requests_total = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status'],
            registry=self.registry
        )
        
        self.http_request_duration = Histogram(
            'http_request_duration_ms',
            'HTTP request duration in milliseconds',
            ['method', 'endpoint'],
            registry=self.registry
        )
        
        self.database_connections = Gauge(
            'database_connections_active',
            'Number of active database connections',
            registry=self.registry
        )
        
        self.cache_hit_rate = Gauge(
            'cache_hit_rate_percent',
            'Cache hit rate percentage',
            registry=self.registry
        )
        
        self.queue_size = Gauge(
            'queue_size',
            'Current queue size',
            ['queue_name'],
            registry=self.registry
        )
        
        # Application info
        self.app_info = Info(
            'northbound_script_generator_info',
            'Application information',
            registry=self.registry
        )
        
        # Set application info
        self.app_info.info({
            'version': '1.0.0',
            'component': 'northbound-script-generator',
            'environment': 'production'
        })
        
        # Track last values to handle counter resets
        self._last_network_sent = 0
        self._last_network_recv = 0
        self._last_total_actions = 0
        
        logger.info("PrometheusExporter initialized")
    
    def update_metrics(self) -> None:
        """Update all Prometheus metrics from the metrics collector."""
        try:
            # Get latest metrics
            system_metrics = self.metrics_collector.get_latest_system_metrics()
            business_metrics = self.metrics_collector.get_latest_business_metrics()
            app_metrics = self.metrics_collector.get_latest_application_metrics()
            
            # Update system metrics
            if system_metrics:
                self.cpu_usage.set(system_metrics.cpu_usage_percent)
                self.memory_usage.set(system_metrics.memory_usage_percent)
                self.memory_available.set(system_metrics.memory_available_mb)
                self.disk_usage.set(system_metrics.disk_usage_percent)
                self.active_connections.set(system_metrics.active_connections)
                
                # Handle network counters (only increment)
                if system_metrics.network_io_bytes_sent > self._last_network_sent:
                    self.network_bytes_sent._value._value = system_metrics.network_io_bytes_sent
                    self._last_network_sent = system_metrics.network_io_bytes_sent
                
                if system_metrics.network_io_bytes_recv > self._last_network_recv:
                    self.network_bytes_recv._value._value = system_metrics.network_io_bytes_recv
                    self._last_network_recv = system_metrics.network_io_bytes_recv
            
            # Update business metrics
            if business_metrics:
                self.actions_per_minute.set(business_metrics.actions_per_minute)
                self.success_rate.set(business_metrics.success_rate_percent)
                self.error_rate.set(business_metrics.error_rate_percent)
                self.response_time_p95.set(business_metrics.response_time_p95_ms)
                self.response_time_avg.set(business_metrics.response_time_avg_ms)
                self.active_users.set(business_metrics.active_users)
                
                # Handle total actions counter
                if business_metrics.total_actions_processed > self._last_total_actions:
                    self.total_actions._value._value = business_metrics.total_actions_processed
                    self._last_total_actions = business_metrics.total_actions_processed
            
            # Update application metrics
            if app_metrics:
                self.database_connections.set(app_metrics.database_connections_active)
                self.cache_hit_rate.set(app_metrics.cache_hit_rate_percent)
                
            logger.debug("Prometheus metrics updated")
            
        except Exception as e:
            logger.error(f"Error updating Prometheus metrics: {e}")
    
    def record_http_request(self, method: str, endpoint: str, status_code: int, duration_ms: float) -> None:
        """Record an HTTP request for Prometheus metrics."""
        try:
            # Increment request counter
            self.http_requests_total.labels(
                method=method,
                endpoint=endpoint, 
                status=str(status_code)
            ).inc()
            
            # Record request duration
            self.http_request_duration.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration_ms)
            
        except Exception as e:
            logger.error(f"Error recording HTTP request metrics: {e}")
    
    def update_queue_size(self, queue_name: str, size: int) -> None:
        """Update queue size metric."""
        try:
            self.queue_size.labels(queue_name=queue_name).set(size)
        except Exception as e:
            logger.error(f"Error updating queue size metric: {e}")
    
    def get_metrics_text(self) -> str:
        """Get metrics in Prometheus text format."""
        try:
            self.update_metrics()
            return generate_latest(self.registry).decode('utf-8')
        except Exception as e:
            logger.error(f"Error generating Prometheus metrics: {e}")
            return ""
    
    def get_metrics_content_type(self) -> str:
        """Get the content type for Prometheus metrics."""
        return CONTENT_TYPE_LATEST
    
    def start_http_server(self, port: int = 8000, addr: str = '') -> None:
        """
        Start HTTP server to serve Prometheus metrics.
        
        Args:
            port: Port to listen on
            addr: Address to bind to (empty string for all interfaces)
        """
        try:
            start_http_server(port, addr, registry=self.registry)
            logger.info(f"Prometheus metrics server started on {addr}:{port}")
        except Exception as e:
            logger.error(f"Error starting Prometheus HTTP server: {e}")
            raise


class PrometheusMiddleware:
    """
    Middleware to automatically collect HTTP request metrics.
    
    Can be used with FastAPI or other web frameworks to automatically
    track request metrics.
    """
    
    def __init__(self, prometheus_exporter: PrometheusExporter):
        """Initialize middleware with Prometheus exporter."""
        self.prometheus_exporter = prometheus_exporter
    
    async def __call__(self, request, call_next):
        """Process request and record metrics."""
        start_time = time.time()
        
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            
            # Record metrics
            self.prometheus_exporter.record_http_request(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms
            )
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            # Record error metrics
            self.prometheus_exporter.record_http_request(
                method=request.method,
                endpoint=request.url.path,
                status_code=500,
                duration_ms=duration_ms
            )
            
            raise e