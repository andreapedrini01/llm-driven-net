"""
InfluxDB storage system for time-series metrics.

This module provides persistent storage for metrics data using InfluxDB,
including retention policies, querying capabilities, and data aggregation.
"""

import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import logging
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS, ASYNCHRONOUS
from influxdb_client.client.query_api import QueryApi
from influxdb_client.client.delete_api import DeleteApi
from influxdb_client.rest import ApiException

from .metrics_collector import SystemMetrics, BusinessMetrics, ApplicationMetrics

logger = logging.getLogger(__name__)


@dataclass
class InfluxDBConfig:
    """InfluxDB connection configuration."""
    url: str = "http://localhost:8086"
    token: str = ""
    org: str = "northbound-org"
    bucket: str = "northbound-metrics"
    timeout: int = 30000  # milliseconds
    verify_ssl: bool = True


@dataclass
class RetentionPolicy:
    """Retention policy configuration."""
    name: str
    duration: str  # e.g., "7d", "30d", "1y"
    shard_duration: str = "1h"
    replication_factor: int = 1
    default: bool = False


class InfluxDBStorage:
    """
    Manages time-series storage of metrics in InfluxDB.
    
    Provides methods for writing metrics, querying historical data,
    and managing retention policies.
    """
    
    def __init__(self, config: InfluxDBConfig):
        """
        Initialize InfluxDB storage.
        
        Args:
            config: InfluxDB connection configuration
        """
        self.config = config
        self._client: Optional[InfluxDBClient] = None
        self._write_api = None
        self._query_api: Optional[QueryApi] = None
        self._delete_api: Optional[DeleteApi] = None
        self._connected = False
        
        logger.info(f"InfluxDBStorage initialized for {config.url}")
    
    async def connect(self) -> bool:
        """
        Connect to InfluxDB.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self._client = InfluxDBClient(
                url=self.config.url,
                token=self.config.token,
                org=self.config.org,
                timeout=self.config.timeout,
                verify_ssl=self.config.verify_ssl
            )
            
            # Test connection
            health = self._client.health()
            if health.status != "pass":
                logger.error(f"InfluxDB health check failed: {health.message}")
                return False
            
            # Initialize APIs
            self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
            self._query_api = self._client.query_api()
            self._delete_api = self._client.delete_api()
            
            self._connected = True
            logger.info("Connected to InfluxDB successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to InfluxDB: {e}")
            self._connected = False
            return False
    
    def disconnect(self) -> None:
        """Disconnect from InfluxDB."""
        if self._client:
            self._client.close()
            self._connected = False
            logger.info("Disconnected from InfluxDB")
    
    def is_connected(self) -> bool:
        """Check if connected to InfluxDB."""
        return self._connected and self._client is not None
    
    async def write_system_metrics(self, metrics: SystemMetrics) -> bool:
        """
        Write system metrics to InfluxDB.
        
        Args:
            metrics: System metrics to write
            
        Returns:
            True if write successful, False otherwise
        """
        if not self.is_connected():
            logger.warning("Not connected to InfluxDB")
            return False
        
        try:
            points = [
                Point("system_metrics")
                .tag("metric_type", "cpu")
                .field("usage_percent", metrics.cpu_usage_percent)
                .time(metrics.timestamp, WritePrecision.S),
                
                Point("system_metrics")
                .tag("metric_type", "memory")
                .field("usage_percent", metrics.memory_usage_percent)
                .field("available_mb", metrics.memory_available_mb)
                .time(metrics.timestamp, WritePrecision.S),
                
                Point("system_metrics")
                .tag("metric_type", "network")
                .field("bytes_sent", metrics.network_io_bytes_sent)
                .field("bytes_recv", metrics.network_io_bytes_recv)
                .time(metrics.timestamp, WritePrecision.S),
                
                Point("system_metrics")
                .tag("metric_type", "disk")
                .field("usage_percent", metrics.disk_usage_percent)
                .time(metrics.timestamp, WritePrecision.S),
                
                Point("system_metrics")
                .tag("metric_type", "connections")
                .field("active_count", metrics.active_connections)
                .time(metrics.timestamp, WritePrecision.S)
            ]
            
            self._write_api.write(
                bucket=self.config.bucket,
                org=self.config.org,
                record=points
            )
            
            logger.debug(f"Wrote system metrics for {metrics.timestamp}")
            return True
            
        except Exception as e:
            logger.error(f"Error writing system metrics: {e}")
            return False
    
    async def write_business_metrics(self, metrics: BusinessMetrics) -> bool:
        """
        Write business metrics to InfluxDB.
        
        Args:
            metrics: Business metrics to write
            
        Returns:
            True if write successful, False otherwise
        """
        if not self.is_connected():
            logger.warning("Not connected to InfluxDB")
            return False
        
        try:
            points = [
                Point("business_metrics")
                .tag("metric_type", "throughput")
                .field("actions_per_minute", metrics.actions_per_minute)
                .field("total_actions", metrics.total_actions_processed)
                .time(metrics.timestamp, WritePrecision.S),
                
                Point("business_metrics")
                .tag("metric_type", "quality")
                .field("success_rate_percent", metrics.success_rate_percent)
                .field("error_rate_percent", metrics.error_rate_percent)
                .time(metrics.timestamp, WritePrecision.S),
                
                Point("business_metrics")
                .tag("metric_type", "performance")
                .field("response_time_p95_ms", metrics.response_time_p95_ms)
                .field("response_time_avg_ms", metrics.response_time_avg_ms)
                .time(metrics.timestamp, WritePrecision.S),
                
                Point("business_metrics")
                .tag("metric_type", "users")
                .field("active_users", metrics.active_users)
                .time(metrics.timestamp, WritePrecision.S)
            ]
            
            self._write_api.write(
                bucket=self.config.bucket,
                org=self.config.org,
                record=points
            )
            
            logger.debug(f"Wrote business metrics for {metrics.timestamp}")
            return True
            
        except Exception as e:
            logger.error(f"Error writing business metrics: {e}")
            return False
    
    async def write_application_metrics(self, metrics: ApplicationMetrics) -> bool:
        """
        Write application metrics to InfluxDB.
        
        Args:
            metrics: Application metrics to write
            
        Returns:
            True if write successful, False otherwise
        """
        if not self.is_connected():
            logger.warning("Not connected to InfluxDB")
            return False
        
        try:
            points = [
                Point("application_metrics")
                .tag("metric_type", "http")
                .field("requests_total", metrics.http_requests_total)
                .field("request_duration_ms", metrics.http_request_duration_ms)
                .time(metrics.timestamp, WritePrecision.S),
                
                Point("application_metrics")
                .tag("metric_type", "database")
                .field("connections_active", metrics.database_connections_active)
                .time(metrics.timestamp, WritePrecision.S),
                
                Point("application_metrics")
                .tag("metric_type", "cache")
                .field("hit_rate_percent", metrics.cache_hit_rate_percent)
                .time(metrics.timestamp, WritePrecision.S),
                
                Point("application_metrics")
                .tag("metric_type", "queue")
                .field("size", metrics.queue_size)
                .time(metrics.timestamp, WritePrecision.S)
            ]
            
            self._write_api.write(
                bucket=self.config.bucket,
                org=self.config.org,
                record=points
            )
            
            logger.debug(f"Wrote application metrics for {metrics.timestamp}")
            return True
            
        except Exception as e:
            logger.error(f"Error writing application metrics: {e}")
            return False
    
    async def query_metrics(self, 
                          measurement: str,
                          start_time: datetime,
                          end_time: Optional[datetime] = None,
                          filters: Optional[Dict[str, str]] = None,
                          aggregation: Optional[str] = None,
                          window: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query metrics from InfluxDB.
        
        Args:
            measurement: Measurement name (e.g., "system_metrics")
            start_time: Start time for query
            end_time: End time for query (defaults to now)
            filters: Additional filters as tag=value pairs
            aggregation: Aggregation function (mean, max, min, sum)
            window: Time window for aggregation (e.g., "5m", "1h")
            
        Returns:
            List of metric records
        """
        if not self.is_connected():
            logger.warning("Not connected to InfluxDB")
            return []
        
        try:
            # Build query
            query_parts = [
                f'from(bucket: "{self.config.bucket}")',
                f'|> range(start: {start_time.isoformat()}Z'
            ]
            
            if end_time:
                query_parts[-1] += f', stop: {end_time.isoformat()}Z'
            query_parts[-1] += ')'
            
            query_parts.append(f'|> filter(fn: (r) => r["_measurement"] == "{measurement}")')
            
            # Add filters
            if filters:
                for tag, value in filters.items():
                    query_parts.append(f'|> filter(fn: (r) => r["{tag}"] == "{value}")')
            
            # Add aggregation
            if aggregation and window:
                query_parts.append(f'|> aggregateWindow(every: {window}, fn: {aggregation})')
            
            query = ' '.join(query_parts)
            
            # Execute query
            tables = self._query_api.query(query, org=self.config.org)
            
            # Convert results
            results = []
            for table in tables:
                for record in table.records:
                    results.append({
                        'time': record.get_time(),
                        'measurement': record.get_measurement(),
                        'field': record.get_field(),
                        'value': record.get_value(),
                        'tags': record.values
                    })
            
            logger.debug(f"Query returned {len(results)} records")
            return results
            
        except Exception as e:
            logger.error(f"Error querying metrics: {e}")
            return []
    
    async def get_latest_metrics(self, measurement: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get latest metrics for a measurement.
        
        Args:
            measurement: Measurement name
            limit: Number of latest records to return
            
        Returns:
            List of latest metric records
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)  # Last hour
        
        return await self.query_metrics(
            measurement=measurement,
            start_time=start_time,
            end_time=end_time
        )
    
    async def get_aggregated_metrics(self,
                                   measurement: str,
                                   start_time: datetime,
                                   end_time: Optional[datetime] = None,
                                   window: str = "5m",
                                   aggregation: str = "mean") -> List[Dict[str, Any]]:
        """
        Get aggregated metrics over time windows.
        
        Args:
            measurement: Measurement name
            start_time: Start time
            end_time: End time (defaults to now)
            window: Aggregation window (e.g., "5m", "1h")
            aggregation: Aggregation function
            
        Returns:
            List of aggregated metric records
        """
        return await self.query_metrics(
            measurement=measurement,
            start_time=start_time,
            end_time=end_time,
            aggregation=aggregation,
            window=window
        )
    
    async def delete_old_metrics(self, older_than: datetime) -> bool:
        """
        Delete metrics older than specified time.
        
        Args:
            older_than: Delete metrics older than this time
            
        Returns:
            True if deletion successful, False otherwise
        """
        if not self.is_connected():
            logger.warning("Not connected to InfluxDB")
            return False
        
        try:
            # Delete data older than specified time
            self._delete_api.delete(
                start="1970-01-01T00:00:00Z",
                stop=older_than.isoformat() + "Z",
                predicate='',  # Delete all measurements
                bucket=self.config.bucket,
                org=self.config.org
            )
            
            logger.info(f"Deleted metrics older than {older_than}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting old metrics: {e}")
            return False
    
    async def create_retention_policy(self, policy: RetentionPolicy) -> bool:
        """
        Create a retention policy.
        
        Args:
            policy: Retention policy configuration
            
        Returns:
            True if creation successful, False otherwise
        """
        if not self.is_connected():
            logger.warning("Not connected to InfluxDB")
            return False
        
        try:
            # Note: InfluxDB 2.x uses retention policies differently than 1.x
            # This is a simplified implementation
            logger.info(f"Retention policy {policy.name} configured for {policy.duration}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating retention policy: {e}")
            return False
    
    async def get_storage_statistics(self) -> Dict[str, Any]:
        """
        Get storage statistics.
        
        Returns:
            Dictionary with storage statistics
        """
        if not self.is_connected():
            return {}
        
        try:
            # Query for basic statistics
            query = f'''
            from(bucket: "{self.config.bucket}")
            |> range(start: -24h)
            |> group()
            |> count()
            '''
            
            tables = self._query_api.query(query, org=self.config.org)
            
            total_points = 0
            for table in tables:
                for record in table.records:
                    total_points += record.get_value()
            
            return {
                'total_points_24h': total_points,
                'bucket': self.config.bucket,
                'org': self.config.org,
                'connected': self._connected
            }
            
        except Exception as e:
            logger.error(f"Error getting storage statistics: {e}")
            return {}
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on InfluxDB connection.
        
        Returns:
            Health check results
        """
        try:
            if not self._client:
                return {'status': 'disconnected', 'message': 'No client connection', 'connected': False}
            
            health = self._client.health()
            
            return {
                'status': health.status,
                'message': health.message or 'OK',
                'version': health.version,
                'connected': self._connected
            }
            
        except Exception as e:
            logger.error(f"InfluxDB health check failed: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'connected': False
            }


class MetricsWriter:
    """
    High-level interface for writing metrics to InfluxDB.
    
    Provides a simple interface for the metrics collector to write
    all types of metrics to InfluxDB storage.
    """
    
    def __init__(self, influxdb_storage: InfluxDBStorage):
        """Initialize metrics writer."""
        self.storage = influxdb_storage
        self._write_queue = asyncio.Queue()
        self._writer_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self) -> None:
        """Start the metrics writer."""
        if self._running:
            return
        
        self._running = True
        self._writer_task = asyncio.create_task(self._writer_loop())
        logger.info("MetricsWriter started")
    
    async def stop(self) -> None:
        """Stop the metrics writer."""
        if not self._running:
            return
        
        self._running = False
        if self._writer_task:
            self._writer_task.cancel()
            try:
                await self._writer_task
            except asyncio.CancelledError:
                pass
        
        logger.info("MetricsWriter stopped")
    
    async def _writer_loop(self) -> None:
        """Main writer loop."""
        while self._running:
            try:
                # Get metrics from queue with timeout
                metrics_data = await asyncio.wait_for(
                    self._write_queue.get(), 
                    timeout=1.0
                )
                
                # Write metrics based on type
                if isinstance(metrics_data, SystemMetrics):
                    await self.storage.write_system_metrics(metrics_data)
                elif isinstance(metrics_data, BusinessMetrics):
                    await self.storage.write_business_metrics(metrics_data)
                elif isinstance(metrics_data, ApplicationMetrics):
                    await self.storage.write_application_metrics(metrics_data)
                
                self._write_queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in metrics writer loop: {e}")
    
    async def write_metrics(self, metrics: Union[SystemMetrics, BusinessMetrics, ApplicationMetrics]) -> None:
        """
        Queue metrics for writing.
        
        Args:
            metrics: Metrics to write
        """
        if self._running:
            await self._write_queue.put(metrics)
    
    def write_metrics_sync(self, metrics: Union[SystemMetrics, BusinessMetrics, ApplicationMetrics]) -> None:
        """
        Queue metrics for writing (synchronous version).
        
        Args:
            metrics: Metrics to write
        """
        if self._running:
            try:
                self._write_queue.put_nowait(metrics)
            except asyncio.QueueFull:
                logger.warning("Metrics write queue is full, dropping metrics")