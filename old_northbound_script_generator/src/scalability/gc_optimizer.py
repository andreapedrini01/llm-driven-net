"""Garbage collection optimization for memory management."""

import gc
import logging
import psutil
import threading
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class GCMode(str, Enum):
    """Garbage collection modes."""
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    ADAPTIVE = "adaptive"


@dataclass
class MemoryStats:
    """Memory statistics."""
    timestamp: datetime
    total_memory_mb: float
    available_memory_mb: float
    used_memory_mb: float
    memory_percent: float
    gc_collections: Dict[int, int]


class GarbageCollectionOptimizer:
    """
    Garbage collection optimizer for memory management.
    
    Features:
    - Adaptive GC based on memory pressure
    - Configurable thresholds
    - Memory monitoring
    - Statistics tracking
    """
    
    def __init__(
        self,
        mode: GCMode = GCMode.ADAPTIVE,
        memory_threshold_percent: float = 80.0,
        critical_threshold_percent: float = 90.0,
        check_interval: int = 30,
        enable_monitoring: bool = True
    ):
        self.logger = logging.getLogger("GCOptimizer")
        self.mode = mode
        self.memory_threshold_percent = memory_threshold_percent
        self.critical_threshold_percent = critical_threshold_percent
        self.check_interval = check_interval
        self.enable_monitoring = enable_monitoring
        
        # Get process
        self.process = psutil.Process()
        
        # Monitoring thread
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Statistics
        self.stats = {
            "total_gc_runs": 0,
            "manual_gc_runs": 0,
            "automatic_gc_runs": 0,
            "memory_warnings": 0,
            "memory_critical": 0,
            "last_gc_time": None,
            "last_memory_check": None
        }
        
        # Memory history
        self.memory_history: list = []
        self.max_history_size = 100
        
        # Configure GC based on mode
        self._configure_gc()
        
        # Start monitoring if enabled
        if self.enable_monitoring:
            self.start_monitoring()
        
        self.logger.info(f"GC Optimizer initialized with mode: {mode}")
    
    def _configure_gc(self):
        """Configure garbage collection based on mode."""
        if self.mode == GCMode.MANUAL:
            # Disable automatic GC
            gc.disable()
            self.logger.info("Automatic GC disabled")
        
        elif self.mode == GCMode.AUTOMATIC:
            # Enable automatic GC with default settings
            gc.enable()
            self.logger.info("Automatic GC enabled")
        
        elif self.mode == GCMode.ADAPTIVE:
            # Enable GC but we'll trigger it adaptively
            gc.enable()
            
            # Adjust GC thresholds for better performance
            # Default is (700, 10, 10)
            # We increase gen0 threshold to reduce frequency
            gc.set_threshold(1000, 15, 15)
            
            self.logger.info("Adaptive GC enabled with custom thresholds")
    
    def get_memory_stats(self) -> MemoryStats:
        """Get current memory statistics."""
        # System memory
        vm = psutil.virtual_memory()
        
        # Process memory
        mem_info = self.process.memory_info()
        
        # GC stats
        gc_stats = gc.get_stats()
        gc_collections = {
            i: gc.get_count()[i] for i in range(len(gc.get_count()))
        }
        
        return MemoryStats(
            timestamp=datetime.now(),
            total_memory_mb=vm.total / (1024 * 1024),
            available_memory_mb=vm.available / (1024 * 1024),
            used_memory_mb=mem_info.rss / (1024 * 1024),
            memory_percent=vm.percent,
            gc_collections=gc_collections
        )
    
    def check_memory_pressure(self) -> str:
        """
        Check memory pressure level.
        
        Returns:
            "normal", "warning", or "critical"
        """
        stats = self.get_memory_stats()
        
        if stats.memory_percent >= self.critical_threshold_percent:
            return "critical"
        elif stats.memory_percent >= self.memory_threshold_percent:
            return "warning"
        else:
            return "normal"
    
    def run_gc(self, generation: int = 2, force: bool = False) -> Dict[str, Any]:
        """
        Run garbage collection.
        
        Args:
            generation: GC generation to collect (0, 1, or 2)
            force: Force GC even if not needed
        
        Returns:
            Dictionary with GC results
        """
        if not force and self.mode == GCMode.AUTOMATIC:
            self.logger.debug("Skipping manual GC in automatic mode")
            return {"skipped": True}
        
        start_time = time.time()
        
        # Get memory before GC
        mem_before = self.get_memory_stats()
        
        # Run GC
        collected = gc.collect(generation)
        
        # Get memory after GC
        mem_after = self.get_memory_stats()
        
        gc_time = time.time() - start_time
        
        # Calculate memory freed
        memory_freed_mb = mem_before.used_memory_mb - mem_after.used_memory_mb
        
        # Update statistics
        self.stats["total_gc_runs"] += 1
        self.stats["manual_gc_runs"] += 1
        self.stats["last_gc_time"] = datetime.now().isoformat()
        
        result = {
            "generation": generation,
            "objects_collected": collected,
            "memory_before_mb": mem_before.used_memory_mb,
            "memory_after_mb": mem_after.used_memory_mb,
            "memory_freed_mb": memory_freed_mb,
            "gc_time_seconds": gc_time,
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.info(
            f"GC generation {generation}: collected {collected} objects, "
            f"freed {memory_freed_mb:.2f} MB in {gc_time:.3f}s"
        )
        
        return result
    
    def adaptive_gc(self) -> Optional[Dict[str, Any]]:
        """
        Run adaptive garbage collection based on memory pressure.
        
        Returns:
            GC results if GC was run, None otherwise
        """
        pressure = self.check_memory_pressure()
        
        if pressure == "critical":
            self.logger.warning("Critical memory pressure detected, running full GC")
            self.stats["memory_critical"] += 1
            
            # Run full GC (generation 2)
            return self.run_gc(generation=2, force=True)
        
        elif pressure == "warning":
            self.logger.info("Memory pressure warning, running incremental GC")
            self.stats["memory_warnings"] += 1
            
            # Run incremental GC (generation 1)
            return self.run_gc(generation=1, force=True)
        
        else:
            # Normal pressure, let automatic GC handle it
            return None
    
    def start_monitoring(self):
        """Start memory monitoring thread."""
        if self._running:
            self.logger.warning("Monitoring already running")
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="GCMonitor"
        )
        self._monitor_thread.start()
        
        self.logger.info("Started memory monitoring")
    
    def stop_monitoring(self):
        """Stop memory monitoring thread."""
        if not self._running:
            return
        
        self._running = False
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=10)
        
        self.logger.info("Stopped memory monitoring")
    
    def _monitoring_loop(self):
        """Memory monitoring loop."""
        self.logger.info("Memory monitoring loop started")
        
        while self._running:
            try:
                # Get memory stats
                stats = self.get_memory_stats()
                
                # Add to history
                self.memory_history.append(stats)
                
                # Trim history
                if len(self.memory_history) > self.max_history_size:
                    self.memory_history.pop(0)
                
                # Update statistics
                self.stats["last_memory_check"] = datetime.now().isoformat()
                
                # Run adaptive GC if in adaptive mode
                if self.mode == GCMode.ADAPTIVE:
                    self.adaptive_gc()
                
                # Sleep
                time.sleep(self.check_interval)
            
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5)
        
        self.logger.info("Memory monitoring loop stopped")
    
    def get_memory_trend(self, window: int = 10) -> Dict[str, Any]:
        """
        Get memory usage trend.
        
        Args:
            window: Number of recent samples to analyze
        
        Returns:
            Dictionary with trend information
        """
        if len(self.memory_history) < 2:
            return {
                "trend": "unknown",
                "samples": len(self.memory_history)
            }
        
        # Get recent samples
        recent = self.memory_history[-window:]
        
        # Calculate trend
        first_mem = recent[0].used_memory_mb
        last_mem = recent[-1].used_memory_mb
        
        change_mb = last_mem - first_mem
        change_percent = (change_mb / first_mem) * 100 if first_mem > 0 else 0
        
        # Determine trend
        if abs(change_percent) < 5:
            trend = "stable"
        elif change_percent > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        
        return {
            "trend": trend,
            "change_mb": change_mb,
            "change_percent": change_percent,
            "first_memory_mb": first_mem,
            "last_memory_mb": last_mem,
            "samples": len(recent),
            "time_span_seconds": (recent[-1].timestamp - recent[0].timestamp).total_seconds()
        }
    
    def optimize_for_low_memory(self):
        """Optimize GC for low memory conditions."""
        self.logger.info("Optimizing for low memory")
        
        # Run full GC
        self.run_gc(generation=2, force=True)
        
        # Adjust GC thresholds to be more aggressive
        gc.set_threshold(500, 10, 10)
        
        # Clear any caches (application-specific)
        # This would need to be implemented by the application
        
        self.logger.info("Low memory optimization complete")
    
    def optimize_for_performance(self):
        """Optimize GC for performance (less frequent GC)."""
        self.logger.info("Optimizing for performance")
        
        # Adjust GC thresholds to be less aggressive
        gc.set_threshold(2000, 20, 20)
        
        self.logger.info("Performance optimization complete")
    
    def get_gc_stats(self) -> Dict[str, Any]:
        """Get garbage collection statistics."""
        # Get GC stats
        gc_stats = gc.get_stats()
        gc_count = gc.get_count()
        
        # Get current thresholds
        thresholds = gc.get_threshold()
        
        return {
            "enabled": gc.isenabled(),
            "count": {
                "generation_0": gc_count[0],
                "generation_1": gc_count[1],
                "generation_2": gc_count[2]
            },
            "thresholds": {
                "generation_0": thresholds[0],
                "generation_1": thresholds[1],
                "generation_2": thresholds[2]
            },
            "stats": gc_stats
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get optimizer statistics."""
        current_memory = self.get_memory_stats()
        memory_trend = self.get_memory_trend()
        gc_stats = self.get_gc_stats()
        
        return {
            "mode": self.mode.value,
            "current_memory": {
                "used_mb": current_memory.used_memory_mb,
                "percent": current_memory.memory_percent,
                "available_mb": current_memory.available_memory_mb
            },
            "memory_trend": memory_trend,
            "gc_stats": gc_stats,
            "optimizer_stats": self.stats,
            "monitoring_enabled": self._running
        }


# Global GC optimizer instance
_gc_optimizer: Optional[GarbageCollectionOptimizer] = None


def get_gc_optimizer(
    mode: GCMode = GCMode.ADAPTIVE,
    **kwargs
) -> GarbageCollectionOptimizer:
    """Get or create global GC optimizer instance."""
    global _gc_optimizer
    
    if _gc_optimizer is None:
        _gc_optimizer = GarbageCollectionOptimizer(mode, **kwargs)
    
    return _gc_optimizer
