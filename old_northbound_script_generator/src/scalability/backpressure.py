"""Backpressure management for handling system overload."""

import logging
import threading
import time
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from queue import Queue, Full, Empty


class BackpressureLevel(str, Enum):
    """Backpressure levels."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class BackpressureMetrics:
    """Backpressure metrics."""
    timestamp: datetime
    queue_size: int
    queue_capacity: int
    queue_utilization: float
    processing_rate: float
    arrival_rate: float
    level: BackpressureLevel


class BackpressureManager:
    """
    Backpressure manager for handling system overload.
    
    Features:
    - Queue-based backpressure
    - Adaptive thresholds
    - Automatic shedding of low-priority requests
    - Metrics and monitoring
    """
    
    def __init__(
        self,
        queue_capacity: int = 1000,
        low_threshold: float = 0.5,
        medium_threshold: float = 0.7,
        high_threshold: float = 0.85,
        critical_threshold: float = 0.95,
        enable_load_shedding: bool = True,
        monitoring_interval: int = 5
    ):
        self.logger = logging.getLogger("BackpressureManager")
        self.queue_capacity = queue_capacity
        self.low_threshold = low_threshold
        self.medium_threshold = medium_threshold
        self.high_threshold = high_threshold
        self.critical_threshold = critical_threshold
        self.enable_load_shedding = enable_load_shedding
        self.monitoring_interval = monitoring_interval
        
        # Request queue
        self.queue: Queue = Queue(maxsize=queue_capacity)
        
        # Backpressure state
        self.current_level = BackpressureLevel.NONE
        self._level_lock = threading.RLock()
        
        # Rate tracking
        self.arrival_count = 0
        self.processing_count = 0
        self.last_rate_check = time.time()
        self._rate_lock = threading.Lock()
        
        # Statistics
        self.stats = {
            "total_arrivals": 0,
            "total_processed": 0,
            "total_rejected": 0,
            "total_shed": 0,
            "level_changes": 0,
            "time_in_critical": 0.0,
            "last_level_change": None
        }
        
        # Monitoring thread
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Callbacks
        self.level_change_callbacks: list = []
        
        # Start monitoring
        self.start_monitoring()
        
        self.logger.info(
            f"BackpressureManager initialized: capacity={queue_capacity}, "
            f"load_shedding={enable_load_shedding}"
        )
    
    def enqueue(
        self,
        item: Any,
        priority: int = 5,
        timeout: float = 1.0
    ) -> bool:
        """
        Enqueue an item with backpressure handling.
        
        Args:
            item: Item to enqueue
            priority: Priority (1-10, higher is more important)
            timeout: Timeout for enqueue operation
        
        Returns:
            True if enqueued, False if rejected
        """
        with self._rate_lock:
            self.arrival_count += 1
            self.stats["total_arrivals"] += 1
        
        # Check backpressure level
        level = self.get_backpressure_level()
        
        # Apply backpressure based on level and priority
        if level == BackpressureLevel.CRITICAL:
            # Only accept high priority requests
            if priority < 8:
                self.stats["total_rejected"] += 1
                self.logger.warning(
                    f"Rejected request (priority={priority}) due to critical backpressure"
                )
                return False
        
        elif level == BackpressureLevel.HIGH:
            # Only accept medium-high priority requests
            if priority < 6:
                self.stats["total_rejected"] += 1
                self.logger.debug(
                    f"Rejected request (priority={priority}) due to high backpressure"
                )
                return False
        
        elif level == BackpressureLevel.MEDIUM:
            # Reject low priority requests
            if priority < 4:
                self.stats["total_rejected"] += 1
                self.logger.debug(
                    f"Rejected request (priority={priority}) due to medium backpressure"
                )
                return False
        
        # Try to enqueue
        try:
            self.queue.put((priority, item), timeout=timeout)
            return True
        
        except Full:
            self.stats["total_rejected"] += 1
            self.logger.warning("Queue full, rejected request")
            return False
    
    def dequeue(self, timeout: float = 1.0) -> Optional[Any]:
        """
        Dequeue an item.
        
        Args:
            timeout: Timeout for dequeue operation
        
        Returns:
            Dequeued item or None if timeout
        """
        try:
            priority, item = self.queue.get(timeout=timeout)
            
            with self._rate_lock:
                self.processing_count += 1
                self.stats["total_processed"] += 1
            
            return item
        
        except Empty:
            return None
    
    def get_backpressure_level(self) -> BackpressureLevel:
        """Get current backpressure level."""
        with self._level_lock:
            return self.current_level
    
    def _calculate_backpressure_level(self) -> BackpressureLevel:
        """Calculate backpressure level based on queue utilization."""
        utilization = self.queue.qsize() / self.queue_capacity
        
        if utilization >= self.critical_threshold:
            return BackpressureLevel.CRITICAL
        elif utilization >= self.high_threshold:
            return BackpressureLevel.HIGH
        elif utilization >= self.medium_threshold:
            return BackpressureLevel.MEDIUM
        elif utilization >= self.low_threshold:
            return BackpressureLevel.LOW
        else:
            return BackpressureLevel.NONE
    
    def _update_backpressure_level(self):
        """Update backpressure level and trigger callbacks if changed."""
        new_level = self._calculate_backpressure_level()
        
        with self._level_lock:
            if new_level != self.current_level:
                old_level = self.current_level
                self.current_level = new_level
                
                self.stats["level_changes"] += 1
                self.stats["last_level_change"] = datetime.now().isoformat()
                
                self.logger.info(f"Backpressure level changed: {old_level} -> {new_level}")
                
                # Trigger callbacks
                for callback in self.level_change_callbacks:
                    try:
                        callback(old_level, new_level)
                    except Exception as e:
                        self.logger.error(f"Error in level change callback: {e}")
    
    def register_level_change_callback(self, callback: Callable[[BackpressureLevel, BackpressureLevel], None]):
        """Register callback for backpressure level changes."""
        self.level_change_callbacks.append(callback)
        self.logger.info(f"Registered level change callback: {callback.__name__}")
    
    def start_monitoring(self):
        """Start monitoring thread."""
        if self._running:
            self.logger.warning("Monitoring already running")
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="BackpressureMonitor"
        )
        self._monitor_thread.start()
        
        self.logger.info("Started backpressure monitoring")
    
    def stop_monitoring(self):
        """Stop monitoring thread."""
        if not self._running:
            return
        
        self._running = False
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=10)
        
        self.logger.info("Stopped backpressure monitoring")
    
    def _monitoring_loop(self):
        """Monitoring loop for backpressure management."""
        self.logger.info("Backpressure monitoring loop started")
        
        critical_start = None
        
        while self._running:
            try:
                # Update backpressure level
                self._update_backpressure_level()
                
                # Track time in critical state
                if self.current_level == BackpressureLevel.CRITICAL:
                    if critical_start is None:
                        critical_start = time.time()
                else:
                    if critical_start is not None:
                        self.stats["time_in_critical"] += time.time() - critical_start
                        critical_start = None
                
                # Calculate rates
                now = time.time()
                elapsed = now - self.last_rate_check
                
                if elapsed >= 1.0:
                    with self._rate_lock:
                        arrival_rate = self.arrival_count / elapsed
                        processing_rate = self.processing_count / elapsed
                        
                        self.arrival_count = 0
                        self.processing_count = 0
                        self.last_rate_check = now
                    
                    # Log rates if significant backpressure
                    if self.current_level in [BackpressureLevel.HIGH, BackpressureLevel.CRITICAL]:
                        self.logger.info(
                            f"Rates - Arrival: {arrival_rate:.1f}/s, "
                            f"Processing: {processing_rate:.1f}/s, "
                            f"Queue: {self.queue.qsize()}/{self.queue_capacity}"
                        )
                    
                    # Perform load shedding if enabled and in critical state
                    if self.enable_load_shedding and self.current_level == BackpressureLevel.CRITICAL:
                        self._perform_load_shedding()
                
                # Sleep
                time.sleep(self.monitoring_interval)
            
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(1)
        
        self.logger.info("Backpressure monitoring loop stopped")
    
    def _perform_load_shedding(self):
        """Perform load shedding by dropping low-priority items."""
        if self.queue.qsize() < self.queue_capacity * 0.9:
            return
        
        # This is a simplified implementation
        # In production, you'd want a more sophisticated approach
        shed_count = 0
        max_shed = int(self.queue_capacity * 0.1)
        
        # Try to shed low-priority items
        temp_items = []
        
        try:
            while shed_count < max_shed and not self.queue.empty():
                try:
                    priority, item = self.queue.get_nowait()
                    
                    if priority < 5:
                        # Shed this item
                        shed_count += 1
                        self.stats["total_shed"] += 1
                    else:
                        # Keep this item
                        temp_items.append((priority, item))
                
                except Empty:
                    break
            
            # Put back kept items
            for priority, item in temp_items:
                try:
                    self.queue.put_nowait((priority, item))
                except Full:
                    break
            
            if shed_count > 0:
                self.logger.warning(f"Load shedding: dropped {shed_count} low-priority items")
        
        except Exception as e:
            self.logger.error(f"Error during load shedding: {e}")
    
    def get_metrics(self) -> BackpressureMetrics:
        """Get current backpressure metrics."""
        queue_size = self.queue.qsize()
        utilization = queue_size / self.queue_capacity
        
        # Calculate rates
        now = time.time()
        elapsed = now - self.last_rate_check
        
        with self._rate_lock:
            if elapsed > 0:
                arrival_rate = self.arrival_count / elapsed
                processing_rate = self.processing_count / elapsed
            else:
                arrival_rate = 0.0
                processing_rate = 0.0
        
        return BackpressureMetrics(
            timestamp=datetime.now(),
            queue_size=queue_size,
            queue_capacity=self.queue_capacity,
            queue_utilization=utilization,
            processing_rate=processing_rate,
            arrival_rate=arrival_rate,
            level=self.current_level
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get backpressure statistics."""
        metrics = self.get_metrics()
        
        rejection_rate = 0.0
        if self.stats["total_arrivals"] > 0:
            rejection_rate = (
                self.stats["total_rejected"] / self.stats["total_arrivals"] * 100
            )
        
        return {
            "current_level": self.current_level.value,
            "queue_size": metrics.queue_size,
            "queue_capacity": metrics.queue_capacity,
            "queue_utilization": metrics.queue_utilization,
            "arrival_rate": metrics.arrival_rate,
            "processing_rate": metrics.processing_rate,
            "rejection_rate": rejection_rate,
            **self.stats
        }
    
    def reset_stats(self):
        """Reset statistics."""
        self.stats = {
            "total_arrivals": 0,
            "total_processed": 0,
            "total_rejected": 0,
            "total_shed": 0,
            "level_changes": 0,
            "time_in_critical": 0.0,
            "last_level_change": None
        }
        
        self.logger.info("Reset backpressure statistics")


# Global backpressure manager instance
_backpressure_manager: Optional[BackpressureManager] = None


def get_backpressure_manager(**kwargs) -> BackpressureManager:
    """Get or create global backpressure manager instance."""
    global _backpressure_manager
    
    if _backpressure_manager is None:
        _backpressure_manager = BackpressureManager(**kwargs)
    
    return _backpressure_manager
