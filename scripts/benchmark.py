#!/usr/bin/env python3
"""
Performance benchmarking script for Northbound Script Generator
Tracks performance metrics over time to detect regressions
"""

import json
import time
import statistics
from datetime import datetime
from pathlib import Path
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from connectors.ryu_connector import create_ryu_connector, RYUConfig
from connectors.comnetsemu_connector import create_comnetsemu_connector, ComnetsEMUConfig
from models.action_models import NetworkAction, ActionType


class PerformanceBenchmark:
    """Performance benchmarking suite."""
    
    def __init__(self):
        self.results = {
            "timestamp": datetime.utcnow().isoformat(),
            "benchmarks": {}
        }
        self.results_dir = Path("benchmark_results")
        self.results_dir.mkdir(exist_ok=True)
    
    def benchmark_ryu_operations(self, num_iterations=100):
        """Benchmark RYU connector operations."""
        print("\n=== Benchmarking RYU Operations ===")
        
        config = RYUConfig(
            host="localhost",
            port=8080,
            timeout_seconds=10,
            max_retries=2
        )
        connector = create_ryu_connector(config=config)
        
        # Benchmark connection status
        times = []
        for i in range(num_iterations):
            start = time.time()
            try:
                connector.get_connection_status()
                times.append((time.time() - start) * 1000)
            except Exception:
                pass
        
        if times:
            self.results["benchmarks"]["ryu_connection_status"] = {
                "iterations": len(times),
                "mean_ms": statistics.mean(times),
                "median_ms": statistics.median(times),
                "stdev_ms": statistics.stdev(times) if len(times) > 1 else 0,
                "min_ms": min(times),
                "max_ms": max(times),
                "p95_ms": statistics.quantiles(times, n=20)[18] if len(times) >= 20 else max(times)
            }
            print(f"Connection Status: {statistics.mean(times):.2f}ms avg")
        
        # Benchmark flow operations
        times = []
        for i in range(min(num_iterations, 50)):  # Fewer iterations for flow ops
            action = NetworkAction(
                id=f"bench_flow_{i}",
                type=ActionType.FLOW_MOD,
                target="1",
                parameters={
                    "operation": "add",
                    "match": {"eth_type": 2048, "ip_src": f"10.0.{i // 256}.{i % 256}"},
                    "actions": ["output:1"],
                    "priority": 1000 + i,
                    "idle_timeout": 60,
                    "hard_timeout": 120
                },
                priority=1000,
                timeout=30
            )
            
            start = time.time()
            try:
                connector.execute_flow_mod(action)
                times.append((time.time() - start) * 1000)
            except Exception:
                pass
        
        if times:
            self.results["benchmarks"]["ryu_flow_operations"] = {
                "iterations": len(times),
                "mean_ms": statistics.mean(times),
                "median_ms": statistics.median(times),
                "stdev_ms": statistics.stdev(times) if len(times) > 1 else 0,
                "min_ms": min(times),
                "max_ms": max(times),
                "p95_ms": statistics.quantiles(times, n=20)[18] if len(times) >= 20 else max(times)
            }
            print(f"Flow Operations: {statistics.mean(times):.2f}ms avg")
        
        connector.close()
    
    def benchmark_comnetsemu_operations(self, num_iterations=100):
        """Benchmark ComnetsEMU connector operations."""
        print("\n=== Benchmarking ComnetsEMU Operations ===")
        
        config = ComnetsEMUConfig(
            host="localhost",
            port=6653,
            api_port=8181,
            timeout_seconds=10,
            max_retries=2
        )
        connector = create_comnetsemu_connector(config=config)
        
        # Benchmark topology discovery
        times = []
        for i in range(num_iterations):
            start = time.time()
            try:
                connector.get_network_topology()
                times.append((time.time() - start) * 1000)
            except Exception:
                pass
        
        if times:
            self.results["benchmarks"]["comnetsemu_topology_discovery"] = {
                "iterations": len(times),
                "mean_ms": statistics.mean(times),
                "median_ms": statistics.median(times),
                "stdev_ms": statistics.stdev(times) if len(times) > 1 else 0,
                "min_ms": min(times),
                "max_ms": max(times),
                "p95_ms": statistics.quantiles(times, n=20)[18] if len(times) >= 20 else max(times)
            }
            print(f"Topology Discovery: {statistics.mean(times):.2f}ms avg")
        
        # Benchmark QoS operations
        times = []
        for i in range(min(num_iterations, 50)):
            action = NetworkAction(
                id=f"bench_qos_{i}",
                type=ActionType.CONFIG_CHANGE,
                target="s1",
                parameters={
                    "config_type": "qos",
                    "config_data": {
                        "policy_id": f"bench_policy_{i}",
                        "target_type": "switch",
                        "target_id": "s1",
                        "bandwidth_limit": 100 + i,
                        "latency_limit": 10,
                        "packet_loss_limit": 0.01
                    }
                },
                priority=1000,
                timeout=30
            )
            
            start = time.time()
            try:
                connector.execute_qos_policy(action)
                times.append((time.time() - start) * 1000)
            except Exception:
                pass
        
        if times:
            self.results["benchmarks"]["comnetsemu_qos_operations"] = {
                "iterations": len(times),
                "mean_ms": statistics.mean(times),
                "median_ms": statistics.median(times),
                "stdev_ms": statistics.stdev(times) if len(times) > 1 else 0,
                "min_ms": min(times),
                "max_ms": max(times),
                "p95_ms": statistics.quantiles(times, n=20)[18] if len(times) >= 20 else max(times)
            }
            print(f"QoS Operations: {statistics.mean(times):.2f}ms avg")
        
        connector.close()
    
    def save_results(self):
        """Save benchmark results to file."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = self.results_dir / f"benchmark_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n=== Results saved to {filename} ===")
        
        # Also save as latest
        latest_file = self.results_dir / "benchmark_latest.json"
        with open(latest_file, 'w') as f:
            json.dump(self.results, f, indent=2)
    
    def compare_with_baseline(self):
        """Compare current results with baseline."""
        baseline_file = self.results_dir / "benchmark_baseline.json"
        
        if not baseline_file.exists():
            print("\n=== No baseline found, saving current as baseline ===")
            with open(baseline_file, 'w') as f:
                json.dump(self.results, f, indent=2)
            return
        
        with open(baseline_file, 'r') as f:
            baseline = json.load(f)
        
        print("\n=== Comparison with Baseline ===")
        
        for bench_name, current_data in self.results["benchmarks"].items():
            if bench_name not in baseline["benchmarks"]:
                print(f"{bench_name}: NEW BENCHMARK")
                continue
            
            baseline_data = baseline["benchmarks"][bench_name]
            current_mean = current_data["mean_ms"]
            baseline_mean = baseline_data["mean_ms"]
            
            diff_pct = ((current_mean - baseline_mean) / baseline_mean) * 100
            
            status = "✓" if diff_pct < 10 else "⚠" if diff_pct < 25 else "✗"
            
            print(f"{bench_name}:")
            print(f"  Current: {current_mean:.2f}ms")
            print(f"  Baseline: {baseline_mean:.2f}ms")
            print(f"  Difference: {diff_pct:+.1f}% {status}")
    
    def run_all_benchmarks(self):
        """Run all benchmarks."""
        print("=" * 60)
        print("PERFORMANCE BENCHMARKING")
        print("=" * 60)
        
        try:
            self.benchmark_ryu_operations()
        except Exception as e:
            print(f"RYU benchmarks failed: {e}")
        
        try:
            self.benchmark_comnetsemu_operations()
        except Exception as e:
            print(f"ComnetsEMU benchmarks failed: {e}")
        
        self.save_results()
        self.compare_with_baseline()
        
        print("\n" + "=" * 60)
        print("BENCHMARKING COMPLETE")
        print("=" * 60)


def main():
    """Main entry point."""
    benchmark = PerformanceBenchmark()
    benchmark.run_all_benchmarks()


if __name__ == "__main__":
    main()
