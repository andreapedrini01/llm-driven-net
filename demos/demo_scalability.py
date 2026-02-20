#!/usr/bin/env python3
"""Demo script for scalability and performance features."""

import sys
import os
import time
import logging
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.scalability import (
    LoadBalancer,
    LoadBalancingStrategy,
    RateLimiter,
    RateLimitConfig,
    RateLimitStrategy,
    BackpressureManager,
    CapacityMonitor,
    ParallelActionProcessor,
    ProcessingMode,
    GarbageCollectionOptimizer,
    GCMode
)
from src.models.action_models import NetworkAction, ActionType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def demo_load_balancer():
    """Demonstrate load balancer functionality."""
    logger.info("=" * 60)
    logger.info("LOAD BALANCER DEMO")
    logger.info("=" * 60)
    
    # Create load balancer
    lb = LoadBalancer(
        strategy=LoadBalancingStrategy.ROUND_ROBIN,
        health_check_interval=10
    )
    
    # Add backend instances
    lb.add_instance("instance-1", "localhost", 8001, weight=1)
    lb.add_instance("instance-2", "localhost", 8002, weight=2)
    lb.add_instance("instance-3", "localhost", 8003, weight=1)
    
    logger.info("Added 3 backend instances")
    
    # Simulate requests
    logger.info("\nSimulating 10 requests with round-robin:")
    for i in range(10):
        instance = lb.get_instance()
        if instance:
            logger.info(f"Request {i+1} -> {instance.instance_id}")
            
            # Simulate processing
            time.sleep(0.1)
            
            # Release instance
            lb.release_instance(instance.instance_id, success=True, response_time=0.05)
    
    # Get statistics
    stats = lb.get_all_stats()
    logger.info(f"\nLoad Balancer Stats:")
    logger.info(f"  Total Requests: {stats['load_balancer']['total_requests']}")
    logger.info(f"  Successful: {stats['load_balancer']['successful_requests']}")
    logger.info(f"  Healthy Instances: {stats['load_balancer']['healthy_instances']}")
    
    # Stop health checks
    lb.stop_health_checks()
    
    logger.info("\n✓ Load balancer demo completed\n")


def demo_rate_limiter():
    """Demonstrate rate limiter functionality."""
    logger.info("=" * 60)
    logger.info("RATE LIMITER DEMO")
    logger.info("=" * 60)
    
    # Create rate limiter
    config = RateLimitConfig(
        requests_per_second=5.0,
        burst_size=10,
        strategy=RateLimitStrategy.TOKEN_BUCKET
    )
    
    limiter = RateLimiter(
        default_config=config,
        enable_global_limit=True,
        global_requests_per_second=20.0
    )
    
    logger.info("Created rate limiter: 5 req/s, burst=10")
    
    # Simulate requests from different clients
    logger.info("\nSimulating requests from 2 clients:")
    
    for i in range(15):
        client_id = f"client-{i % 2 + 1}"
        result = limiter.check_rate_limit(client_id)
        
        status = "✓ ALLOWED" if result.allowed else "✗ REJECTED"
        logger.info(
            f"Request {i+1} from {client_id}: {status} "
            f"(remaining: {result.remaining})"
        )
        
        time.sleep(0.1)
    
    # Get statistics
    stats = limiter.get_stats()
    logger.info(f"\nRate Limiter Stats:")
    logger.info(f"  Total Requests: {stats['total_requests']}")
    logger.info(f"  Allowed: {stats['allowed_requests']}")
    logger.info(f"  Rejected: {stats['rejected_requests']}")
    logger.info(f"  Rejection Rate: {stats['rejection_rate']:.1f}%")
    
    logger.info("\n✓ Rate limiter demo completed\n")


def demo_backpressure():
    """Demonstrate backpressure management."""
    logger.info("=" * 60)
    logger.info("BACKPRESSURE DEMO")
    logger.info("=" * 60)
    
    # Create backpressure manager
    bp = BackpressureManager(
        queue_capacity=20,
        low_threshold=0.5,
        medium_threshold=0.7,
        high_threshold=0.85,
        enable_load_shedding=True,
        monitoring_interval=2
    )
    
    logger.info("Created backpressure manager: capacity=20")
    
    # Simulate increasing load
    logger.info("\nSimulating increasing load:")
    
    for i in range(25):
        priority = 5 if i < 15 else 3  # Lower priority for later requests
        success = bp.enqueue(f"request-{i}", priority=priority, timeout=0.5)
        
        level = bp.get_backpressure_level()
        status = "✓ ENQUEUED" if success else "✗ REJECTED"
        
        logger.info(
            f"Request {i+1} (priority={priority}): {status} "
            f"[Level: {level.value}]"
        )
        
        time.sleep(0.05)
    
    # Get metrics
    metrics = bp.get_metrics()
    logger.info(f"\nBackpressure Metrics:")
    logger.info(f"  Queue Size: {metrics.queue_size}/{metrics.queue_capacity}")
    logger.info(f"  Utilization: {metrics.queue_utilization*100:.1f}%")
    logger.info(f"  Current Level: {metrics.level.value}")
    
    # Get statistics
    stats = bp.get_stats()
    logger.info(f"\nBackpressure Stats:")
    logger.info(f"  Total Arrivals: {stats['total_arrivals']}")
    logger.info(f"  Rejected: {stats['total_rejected']}")
    logger.info(f"  Rejection Rate: {stats['rejection_rate']:.1f}%")
    
    # Stop monitoring
    bp.stop_monitoring()
    
    logger.info("\n✓ Backpressure demo completed\n")


def demo_parallel_processor():
    """Demonstrate parallel action processing."""
    logger.info("=" * 60)
    logger.info("PARALLEL PROCESSOR DEMO")
    logger.info("=" * 60)
    
    # Create processor
    processor = ParallelActionProcessor(
        mode=ProcessingMode.THREADED,
        max_workers=4
    )
    
    logger.info("Created parallel processor: mode=threaded, workers=4")
    
    # Create test actions
    actions = []
    for i in range(10):
        action = NetworkAction(
            id=f"action-{i}",
            type=ActionType.FLOW_RULE,
            target=f"switch-{i % 3}",
            parameters={"rule": f"test-rule-{i}"},
            priority=i % 3 + 1
        )
        actions.append(action)
    
    logger.info(f"\nCreated {len(actions)} test actions")
    
    # Define processor function
    def process_action(action: NetworkAction):
        """Simulate action processing."""
        time.sleep(0.2)  # Simulate work
        return {"success": True, "action_id": action.id}
    
    # Process actions
    logger.info("\nProcessing actions in parallel:")
    
    start_time = time.time()
    results = processor.process_actions(actions, process_action)
    elapsed = time.time() - start_time
    
    # Show results
    successful = sum(1 for r in results if r.success)
    logger.info(f"\nProcessing completed in {elapsed:.2f}s")
    logger.info(f"  Successful: {successful}/{len(results)}")
    
    # Get statistics
    stats = processor.get_stats()
    logger.info(f"\nProcessor Stats:")
    logger.info(f"  Total Processed: {stats['total_processed']}")
    logger.info(f"  Avg Time: {stats['avg_time_per_action']:.3f}s")
    logger.info(f"  Max Time: {stats['max_time']:.3f}s")
    
    logger.info("\n✓ Parallel processor demo completed\n")


def demo_gc_optimizer():
    """Demonstrate garbage collection optimizer."""
    logger.info("=" * 60)
    logger.info("GC OPTIMIZER DEMO")
    logger.info("=" * 60)
    
    # Create GC optimizer
    gc_opt = GarbageCollectionOptimizer(
        mode=GCMode.ADAPTIVE,
        memory_threshold_percent=70.0,
        enable_monitoring=True
    )
    
    logger.info("Created GC optimizer: mode=adaptive")
    
    # Get initial memory stats
    initial_stats = gc_opt.get_memory_stats()
    logger.info(f"\nInitial Memory:")
    logger.info(f"  Used: {initial_stats.used_memory_mb:.1f} MB")
    logger.info(f"  Percent: {initial_stats.memory_percent:.1f}%")
    
    # Allocate some memory
    logger.info("\nAllocating memory...")
    data = []
    for i in range(1000):
        data.append([0] * 10000)
    
    # Get memory stats after allocation
    after_alloc = gc_opt.get_memory_stats()
    logger.info(f"\nAfter Allocation:")
    logger.info(f"  Used: {after_alloc.used_memory_mb:.1f} MB")
    logger.info(f"  Percent: {after_alloc.memory_percent:.1f}%")
    
    # Run manual GC
    logger.info("\nRunning manual GC...")
    gc_result = gc_opt.run_gc(generation=2, force=True)
    
    logger.info(f"GC Results:")
    logger.info(f"  Objects Collected: {gc_result['objects_collected']}")
    logger.info(f"  Memory Freed: {gc_result['memory_freed_mb']:.1f} MB")
    logger.info(f"  GC Time: {gc_result['gc_time_seconds']:.3f}s")
    
    # Get final stats
    stats = gc_opt.get_stats()
    logger.info(f"\nGC Optimizer Stats:")
    logger.info(f"  Total GC Runs: {stats['optimizer_stats']['total_gc_runs']}")
    logger.info(f"  Current Memory: {stats['current_memory']['used_mb']:.1f} MB")
    
    # Stop monitoring
    gc_opt.stop_monitoring()
    
    # Clean up
    del data
    
    logger.info("\n✓ GC optimizer demo completed\n")


def demo_capacity_monitor():
    """Demonstrate capacity monitoring."""
    logger.info("=" * 60)
    logger.info("CAPACITY MONITOR DEMO")
    logger.info("=" * 60)
    
    # Create capacity monitor
    monitor = CapacityMonitor(
        cpu_scale_up_threshold=70.0,
        memory_scale_up_threshold=80.0,
        monitoring_interval=5,
        min_instances=1,
        max_instances=5
    )
    
    logger.info("Created capacity monitor")
    
    # Wait for initial metrics
    time.sleep(2)
    
    # Get current metrics
    metrics = monitor.get_current_metrics()
    if metrics:
        logger.info(f"\nCurrent Metrics:")
        logger.info(f"  CPU: {metrics.cpu_percent:.1f}%")
        logger.info(f"  Memory: {metrics.memory_percent:.1f}%")
        logger.info(f"  Disk: {metrics.disk_percent:.1f}%")
        logger.info(f"  Network I/O: {metrics.network_io_mbps:.2f} MB/s")
    
    # Get statistics
    stats = monitor.get_stats()
    logger.info(f"\nCapacity Monitor Stats:")
    logger.info(f"  Current Instances: {stats['current_instances']}")
    logger.info(f"  Total Checks: {stats['total_checks']}")
    logger.info(f"  Scale Up Recommendations: {stats['scale_up_recommendations']}")
    logger.info(f"  Scale Down Recommendations: {stats['scale_down_recommendations']}")
    
    # Stop monitoring
    monitor.stop_monitoring()
    
    logger.info("\n✓ Capacity monitor demo completed\n")


def main():
    """Run all demos."""
    logger.info("\n" + "=" * 60)
    logger.info("SCALABILITY AND PERFORMANCE DEMO")
    logger.info("=" * 60 + "\n")
    
    try:
        # Run demos
        demo_load_balancer()
        demo_rate_limiter()
        demo_backpressure()
        demo_parallel_processor()
        demo_gc_optimizer()
        demo_capacity_monitor()
        
        logger.info("=" * 60)
        logger.info("ALL DEMOS COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
