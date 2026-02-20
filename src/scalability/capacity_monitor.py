"""Capacity monitoring and auto-scaling recommendations."""

import logging
import psutil
import threading
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class ScalingAction(str, Enum):
    """Scaling actions."""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NO_ACTION = "no_action"


@dataclass
class CapacityMetrics:
    """Capacity metrics."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_io_mbps: float
    active_connections: int
    request_rate: float
    error_rate: float
    response_time_p95: float


@dataclass
class ScalingRecommendation:
    """Scaling recommendation."""
    action: ScalingAction
    reason: str
    confidence: float
    metrics: CapacityMetrics
    recommended_instances: int


class CapacityMonitor:
    """
    Capacity monitor for auto-scaling recommendations.
    
    Features:
    - Multi-metric monitoring
    - Trend analysis
    - Scaling recommendations
    - Configurable thresholds
    """
    
    def __init__(
        self,
        cpu_scale_up_threshold: float = 70.0,
        cpu_scale_down_threshold: float = 30.0,
        memory_scale_up_threshold: float = 80.0,
        memory_scale_down_threshold: float = 40.0,
        response_time_threshold_ms: float = 100.0,
        error_rate_threshold: float = 5.0,
        monitoring_interval: int = 30,
        trend_window: int = 10,
        min_instances: int = 1,
        max_instances: int = 10
    ):
        self.logger = logging.getLogger("CapacityMonitor")
        self.cpu_scale_up_threshold = cpu_scale_up_threshold
        self.cpu_scale_down_threshold = cpu_scale_down_threshold
        self.memory_scale_up_threshold = memory_scale_up_threshold
        self.memory_scale_down_threshold = memory_scale_down_threshold
        self.response_time_threshold_ms = response_time_threshold_ms
        self.error_rate_threshold = error_rate_threshold
        self.monitoring_interval = monitoring_interval
        self.trend_window = trend_window
        self.min_instances = min_instances
        self.max_instances = max_instances
        
        # Current instance count
        self.current_instances = 1
        
        # Metrics history
        self.metrics_history: List[CapacityMetrics] = []
        self.max_history_size = 1000
        
        # Process
        self.process = psutil.Process()
        
        # Network tracking
        self.last_net_io = psutil.net_io_counters()
        self.last_net_check = time.time()
        
        # Monitoring thread
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Statistics
        self.stats = {
            "total_checks": 0,
            "scale_up_recommendations": 0,
            "scale_down_recommendations": 0,
            "last_recommendation": None,
            "last_scaling_action": None
        }
        
        # Callbacks
        self.scaling_callbacks: List[Callable[[ScalingRecommendation], None]] = []
        
        # Start monitoring
        self.start_monitoring()
        
        self.logger.info("CapacityMonitor initialized")
    
    def collect_metrics(
        self,
        active_connections: int = 0,
        request_rate: float = 0.0,
        error_rate: float = 0.0,
        response_time_p95: float = 0.0
    ) -> CapacityMetrics:
        """
        Collect current capacity metrics.
        
        Args:
            active_connections: Number of active connections
            request_rate: Requests per second
            error_rate: Error rate percentage
            response_time_p95: 95th percentile response time in ms
        
        Returns:
            CapacityMetrics object
        """
        # CPU and memory
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        # Disk
        disk = psutil.disk_usage('/')
        
        # Network I/O
        net_io = psutil.net_io_counters()
        now = time.time()
        elapsed = now - self.last_net_check
        
        if elapsed > 0:
            bytes_sent = net_io.bytes_sent - self.last_net_io.bytes_sent
            bytes_recv = net_io.bytes_recv - self.last_net_io.bytes_recv
            network_io_mbps = ((bytes_sent + bytes_recv) / elapsed) / (1024 * 1024)
        else:
            network_io_mbps = 0.0
        
        self.last_net_io = net_io
        self.last_net_check = now
        
        return CapacityMetrics(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            disk_percent=disk.percent,
            network_io_mbps=network_io_mbps,
            active_connections=active_connections,
            request_rate=request_rate,
            error_rate=error_rate,
            response_time_p95=response_time_p95
        )
    
    def analyze_capacity(
        self,
        metrics: CapacityMetrics
    ) -> ScalingRecommendation:
        """
        Analyze capacity and provide scaling recommendation.
        
        Args:
            metrics: Current capacity metrics
        
        Returns:
            ScalingRecommendation
        """
        reasons = []
        scale_up_score = 0
        scale_down_score = 0
        
        # Check CPU
        if metrics.cpu_percent > self.cpu_scale_up_threshold:
            scale_up_score += 2
            reasons.append(f"CPU usage high ({metrics.cpu_percent:.1f}%)")
        elif metrics.cpu_percent < self.cpu_scale_down_threshold:
            scale_down_score += 1
            reasons.append(f"CPU usage low ({metrics.cpu_percent:.1f}%)")
        
        # Check memory
        if metrics.memory_percent > self.memory_scale_up_threshold:
            scale_up_score += 2
            reasons.append(f"Memory usage high ({metrics.memory_percent:.1f}%)")
        elif metrics.memory_percent < self.memory_scale_down_threshold:
            scale_down_score += 1
            reasons.append(f"Memory usage low ({metrics.memory_percent:.1f}%)")
        
        # Check response time
        if metrics.response_time_p95 > self.response_time_threshold_ms:
            scale_up_score += 1
            reasons.append(f"Response time high ({metrics.response_time_p95:.1f}ms)")
        
        # Check error rate
        if metrics.error_rate > self.error_rate_threshold:
            scale_up_score += 1
            reasons.append(f"Error rate high ({metrics.error_rate:.1f}%)")
        
        # Check trend
        trend = self._analyze_trend()
        if trend == "increasing":
            scale_up_score += 1
            reasons.append("Resource usage trending up")
        elif trend == "decreasing":
            scale_down_score += 1
            reasons.append("Resource usage trending down")
        
        # Determine action
        if scale_up_score >= 2 and self.current_instances < self.max_instances:
            action = ScalingAction.SCALE_UP
            recommended_instances = min(
                self.current_instances + 1,
                self.max_instances
            )
            confidence = min(scale_up_score / 5.0, 1.0)
        
        elif scale_down_score >= 2 and self.current_instances > self.min_instances:
            action = ScalingAction.SCALE_DOWN
            recommended_instances = max(
                self.current_instances - 1,
                self.min_instances
            )
            confidence = min(scale_down_score / 3.0, 1.0)
        
        else:
            action = ScalingAction.NO_ACTION
            recommended_instances = self.current_instances
            confidence = 0.5
        
        return ScalingRecommendation(
            action=action,
            reason="; ".join(reasons) if reasons else "All metrics within normal range",
            confidence=confidence,
            metrics=metrics,
            recommended_instances=recommended_instances
        )
    
    def _analyze_trend(self) -> str:
        """
        Analyze resource usage trend.
        
        Returns:
            "increasing", "decreasing", or "stable"
        """
        if len(self.metrics_history) < self.trend_window:
            return "stable"
        
        recent = self.metrics_history[-self.trend_window:]
        
        # Calculate average CPU and memory for first and second half
        mid = len(recent) // 2
        first_half = recent[:mid]
        second_half = recent[mid:]
        
        first_avg_cpu = sum(m.cpu_percent for m in first_half) / len(first_half)
        second_avg_cpu = sum(m.cpu_percent for m in second_half) / len(second_half)
        
        first_avg_mem = sum(m.memory_percent for m in first_half) / len(first_half)
        second_avg_mem = sum(m.memory_percent for m in second_half) / len(second_half)
        
        # Calculate change
        cpu_change = ((second_avg_cpu - first_avg_cpu) / first_avg_cpu) * 100 if first_avg_cpu > 0 else 0
        mem_change = ((second_avg_mem - first_avg_mem) / first_avg_mem) * 100 if first_avg_mem > 0 else 0
        
        avg_change = (cpu_change + mem_change) / 2
        
        if avg_change > 10:
            return "increasing"
        elif avg_change < -10:
            return "decreasing"
        else:
            return "stable"
    
    def register_scaling_callback(
        self,
        callback: Callable[[ScalingRecommendation], None]
    ):
        """Register callback for scaling recommendations."""
        self.scaling_callbacks.append(callback)
        self.logger.info(f"Registered scaling callback: {callback.__name__}")
    
    def start_monitoring(self):
        """Start monitoring thread."""
        if self._running:
            self.logger.warning("Monitoring already running")
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="CapacityMonitor"
        )
        self._monitor_thread.start()
        
        self.logger.info("Started capacity monitoring")
    
    def stop_monitoring(self):
        """Stop monitoring thread."""
        if not self._running:
            return
        
        self._running = False
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=10)
        
        self.logger.info("Stopped capacity monitoring")
    
    def _monitoring_loop(self):
        """Monitoring loop for capacity analysis."""
        self.logger.info("Capacity monitoring loop started")
        
        while self._running:
            try:
                # Collect metrics
                metrics = self.collect_metrics()
                
                # Add to history
                self.metrics_history.append(metrics)
                
                # Trim history
                if len(self.metrics_history) > self.max_history_size:
                    self.metrics_history.pop(0)
                
                # Analyze capacity
                recommendation = self.analyze_capacity(metrics)
                
                # Update statistics
                self.stats["total_checks"] += 1
                
                if recommendation.action == ScalingAction.SCALE_UP:
                    self.stats["scale_up_recommendations"] += 1
                    self.stats["last_recommendation"] = {
                        "action": "scale_up",
                        "timestamp": datetime.now().isoformat(),
                        "reason": recommendation.reason
                    }
                    
                    self.logger.info(
                        f"Scale up recommended: {recommendation.reason} "
                        f"(confidence: {recommendation.confidence:.2f})"
                    )
                    
                    # Trigger callbacks
                    for callback in self.scaling_callbacks:
                        try:
                            callback(recommendation)
                        except Exception as e:
                            self.logger.error(f"Error in scaling callback: {e}")
                
                elif recommendation.action == ScalingAction.SCALE_DOWN:
                    self.stats["scale_down_recommendations"] += 1
                    self.stats["last_recommendation"] = {
                        "action": "scale_down",
                        "timestamp": datetime.now().isoformat(),
                        "reason": recommendation.reason
                    }
                    
                    self.logger.info(
                        f"Scale down recommended: {recommendation.reason} "
                        f"(confidence: {recommendation.confidence:.2f})"
                    )
                    
                    # Trigger callbacks
                    for callback in self.scaling_callbacks:
                        try:
                            callback(recommendation)
                        except Exception as e:
                            self.logger.error(f"Error in scaling callback: {e}")
                
                # Sleep
                time.sleep(self.monitoring_interval)
            
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5)
        
        self.logger.info("Capacity monitoring loop stopped")
    
    def set_instance_count(self, count: int):
        """Set current instance count."""
        if count < self.min_instances or count > self.max_instances:
            self.logger.warning(
                f"Instance count {count} outside valid range "
                f"[{self.min_instances}, {self.max_instances}]"
            )
            return
        
        old_count = self.current_instances
        self.current_instances = count
        
        self.stats["last_scaling_action"] = {
            "from": old_count,
            "to": count,
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.info(f"Instance count updated: {old_count} -> {count}")
    
    def get_current_metrics(self) -> Optional[CapacityMetrics]:
        """Get most recent metrics."""
        if not self.metrics_history:
            return None
        
        return self.metrics_history[-1]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get capacity monitor statistics."""
        current_metrics = self.get_current_metrics()
        
        stats = {
            "current_instances": self.current_instances,
            "min_instances": self.min_instances,
            "max_instances": self.max_instances,
            **self.stats
        }
        
        if current_metrics:
            stats["current_metrics"] = {
                "cpu_percent": current_metrics.cpu_percent,
                "memory_percent": current_metrics.memory_percent,
                "disk_percent": current_metrics.disk_percent,
                "network_io_mbps": current_metrics.network_io_mbps,
                "timestamp": current_metrics.timestamp.isoformat()
            }
        
        return stats


# Global capacity monitor instance
_capacity_monitor: Optional[CapacityMonitor] = None


def get_capacity_monitor(**kwargs) -> CapacityMonitor:
    """Get or create global capacity monitor instance."""
    global _capacity_monitor
    
    if _capacity_monitor is None:
        _capacity_monitor = CapacityMonitor(**kwargs)
    
    return _capacity_monitor
