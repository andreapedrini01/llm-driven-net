"""
Metrics collection system for system and business metrics.

This module collects various metrics including:
- System metrics: CPU, memory, network I/O
- Business metrics: actions per minute, success rate
- Application metrics: response times, error rates
"""

import time
import psutil
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """System-level metrics."""
    timestamp: datetime
    cpu_usage_percent: float
    memory_usage_percent: float
    memory_available_mb: float
    network_io_bytes_sent: int
    network_io_bytes_recv: int
    disk_usage_percent: float
    active_connections: int


@dataclass
class BusinessMetrics:
    """Business-level metrics."""
    timestamp: datetime
    actions_per_minute: int
    success_rate_percent: float
    error_rate_percent: float
    response_time_p95_ms: float
    response_time_avg_ms: float
    active_users: int
    total_actions_processed: int


@dataclass
class ApplicationMetrics:
    """Application-level metrics."""
    timestamp: datetime
    http_requests_total: int
    http_request_duration_ms: float
    database_connections_active: int
    cache_hit_rate_percent: float
    queue_size: int


class MetricsCollector:
    """
    Collects system, business, and application metrics.
    
    Provides thread-safe collection of various metrics with configurable
    collection intervals and retention periods.
    """
    
    def __init__(self, collection_interval: int = 60, retention_minutes: int = 60):
        """
        Initialize metrics collector.
        
        Args:
            collection_interval: Interval in seconds between metric collections
            retention_minutes: How long to retain metrics in memory
        """
        self.collection_interval = collection_interval
        self.retention_minutes = retention_minutes
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Metric storage
        self._system_metrics: deque = deque(maxlen=retention_minutes)
        self._business_metrics: deque = deque(maxlen=retention_minutes)
        self._application_metrics: deque = deque(maxlen=retention_minutes)
        
        # Business metric tracking
        self._action_timestamps: deque = deque()
        self._response_times: deque = deque(maxlen=1000)  # Last 1000 requests
        self._success_count = 0
        self._error_count = 0
        self._total_actions = 0
        self._active_users = set()
        
        # Application metric tracking
        self._http_requests = 0
        self._http_durations: deque = deque(maxlen=1000)
        self._db_connections = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._queue_size = 0
        
        logger.info(f"MetricsCollector initialized with {collection_interval}s interval")
    
    def start(self) -> None:
        """Start the metrics collection thread."""
        if self._running:
            logger.warning("MetricsCollector already running")
            return
            
        self._running = True
        self._thread = threading.Thread(target=self._collection_loop, daemon=True)
        self._thread.start()
        logger.info("MetricsCollector started")
    
    def stop(self) -> None:
        """Stop the metrics collection thread."""
        if not self._running:
            return
            
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("MetricsCollector stopped")
    
    def _collection_loop(self) -> None:
        """Main collection loop running in separate thread."""
        while self._running:
            try:
                self._collect_all_metrics()
                time.sleep(self.collection_interval)
            except Exception as e:
                logger.error(f"Error in metrics collection: {e}")
                time.sleep(self.collection_interval)
    
    def _collect_all_metrics(self) -> None:
        """Collect all types of metrics."""
        timestamp = datetime.utcnow()
        
        with self._lock:
            # Collect system metrics
            system_metrics = self._collect_system_metrics(timestamp)
            self._system_metrics.append(system_metrics)
            
            # Collect business metrics
            business_metrics = self._collect_business_metrics(timestamp)
            self._business_metrics.append(business_metrics)
            
            # Collect application metrics
            app_metrics = self._collect_application_metrics(timestamp)
            self._application_metrics.append(app_metrics)
            
        logger.debug(f"Collected metrics at {timestamp}")
    
    def _collect_system_metrics(self, timestamp: datetime) -> SystemMetrics:
        """Collect system-level metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available_mb = memory.available / (1024 * 1024)
            
            # Network I/O
            network_io = psutil.net_io_counters()
            network_sent = network_io.bytes_sent if network_io else 0
            network_recv = network_io.bytes_recv if network_io else 0
            
            # Disk usage
            disk_usage = psutil.disk_usage('/')
            disk_percent = (disk_usage.used / disk_usage.total) * 100
            
            # Active connections (approximate)
            connections = len(psutil.net_connections())
            
            return SystemMetrics(
                timestamp=timestamp,
                cpu_usage_percent=cpu_percent,
                memory_usage_percent=memory_percent,
                memory_available_mb=memory_available_mb,
                network_io_bytes_sent=network_sent,
                network_io_bytes_recv=network_recv,
                disk_usage_percent=disk_percent,
                active_connections=connections
            )
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return SystemMetrics(
                timestamp=timestamp,
                cpu_usage_percent=0.0,
                memory_usage_percent=0.0,
                memory_available_mb=0.0,
                network_io_bytes_sent=0,
                network_io_bytes_recv=0,
                disk_usage_percent=0.0,
                active_connections=0
            )
    
    def _collect_business_metrics(self, timestamp: datetime) -> BusinessMetrics:
        """Collect business-level metrics."""
        # Clean old action timestamps (older than 1 minute)
        cutoff_time = timestamp - timedelta(minutes=1)
        while self._action_timestamps and self._action_timestamps[0] < cutoff_time:
            self._action_timestamps.popleft()
        
        # Calculate actions per minute
        actions_per_minute = len(self._action_timestamps)
        
        # Calculate success rate
        total_recent = self._success_count + self._error_count
        success_rate = (self._success_count / total_recent * 100) if total_recent > 0 else 100.0
        error_rate = (self._error_count / total_recent * 100) if total_recent > 0 else 0.0
        
        # Calculate response times
        if self._response_times:
            sorted_times = sorted(self._response_times)
            p95_index = int(len(sorted_times) * 0.95)
            response_time_p95 = sorted_times[p95_index] if sorted_times else 0.0
            response_time_avg = sum(self._response_times) / len(self._response_times)
        else:
            response_time_p95 = 0.0
            response_time_avg = 0.0
        
        return BusinessMetrics(
            timestamp=timestamp,
            actions_per_minute=actions_per_minute,
            success_rate_percent=success_rate,
            error_rate_percent=error_rate,
            response_time_p95_ms=response_time_p95,
            response_time_avg_ms=response_time_avg,
            active_users=len(self._active_users),
            total_actions_processed=self._total_actions
        )
    
    def _collect_application_metrics(self, timestamp: datetime) -> ApplicationMetrics:
        """Collect application-level metrics."""
        # Calculate cache hit rate
        total_cache_ops = self._cache_hits + self._cache_misses
        cache_hit_rate = (self._cache_hits / total_cache_ops * 100) if total_cache_ops > 0 else 0.0
        
        # Calculate average HTTP request duration
        avg_duration = sum(self._http_durations) / len(self._http_durations) if self._http_durations else 0.0
        
        return ApplicationMetrics(
            timestamp=timestamp,
            http_requests_total=self._http_requests,
            http_request_duration_ms=avg_duration,
            database_connections_active=self._db_connections,
            cache_hit_rate_percent=cache_hit_rate,
            queue_size=self._queue_size
        )
    
    # Public methods for recording business events
    
    def record_action_success(self, response_time_ms: float) -> None:
        """Record a successful action."""
        with self._lock:
            self._action_timestamps.append(datetime.utcnow())
            self._response_times.append(response_time_ms)
            self._success_count += 1
            self._total_actions += 1
    
    def record_action_error(self, response_time_ms: float) -> None:
        """Record a failed action."""
        with self._lock:
            self._action_timestamps.append(datetime.utcnow())
            self._response_times.append(response_time_ms)
            self._error_count += 1
            self._total_actions += 1
    
    def record_user_activity(self, user_id: str) -> None:
        """Record user activity."""
        with self._lock:
            self._active_users.add(user_id)
    
    def record_http_request(self, duration_ms: float) -> None:
        """Record HTTP request."""
        with self._lock:
            self._http_requests += 1
            self._http_durations.append(duration_ms)
    
    def record_cache_hit(self) -> None:
        """Record cache hit."""
        with self._lock:
            self._cache_hits += 1
    
    def record_cache_miss(self) -> None:
        """Record cache miss."""
        with self._lock:
            self._cache_misses += 1
    
    def update_db_connections(self, count: int) -> None:
        """Update database connection count."""
        with self._lock:
            self._db_connections = count
    
    def update_queue_size(self, size: int) -> None:
        """Update queue size."""
        with self._lock:
            self._queue_size = size
    
    # Getter methods for current metrics
    
    def get_latest_system_metrics(self) -> Optional[SystemMetrics]:
        """Get the latest system metrics."""
        with self._lock:
            return self._system_metrics[-1] if self._system_metrics else None
    
    def get_latest_business_metrics(self) -> Optional[BusinessMetrics]:
        """Get the latest business metrics."""
        with self._lock:
            return self._business_metrics[-1] if self._business_metrics else None
    
    def get_latest_application_metrics(self) -> Optional[ApplicationMetrics]:
        """Get the latest application metrics."""
        with self._lock:
            return self._application_metrics[-1] if self._application_metrics else None
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all current metrics as a dictionary."""
        with self._lock:
            return {
                'system': self._system_metrics[-1] if self._system_metrics else None,
                'business': self._business_metrics[-1] if self._business_metrics else None,
                'application': self._application_metrics[-1] if self._application_metrics else None,
                'collection_time': datetime.utcnow().isoformat()
            }
    
    def get_metrics_history(self, minutes: int = 60) -> Dict[str, List]:
        """Get metrics history for the specified number of minutes."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        
        with self._lock:
            system_history = [m for m in self._system_metrics if m.timestamp >= cutoff_time]
            business_history = [m for m in self._business_metrics if m.timestamp >= cutoff_time]
            app_history = [m for m in self._application_metrics if m.timestamp >= cutoff_time]
            
            return {
                'system': system_history,
                'business': business_history,
                'application': app_history
            }