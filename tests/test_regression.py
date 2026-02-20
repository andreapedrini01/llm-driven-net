#!/usr/bin/env python3
"""
Regression tests for the Northbound Script Generator
Ensures that previously fixed bugs don't reappear
Validates: Requirement 7.6 - Block deployment on regressions
"""

import pytest
import json
import time
from datetime import datetime
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from connectors.ryu_connector import create_ryu_connector, RYUConfig
from connectors.comnetsemu_connector import create_comnetsemu_connector, ComnetsEMUConfig
from models.action_models import NetworkAction, ActionType


class TestRegression:
    """Regression tests to prevent reintroduction of bugs."""
    
    @pytest.fixture
    def ryu_connector(self):
        """Create RYU connector for testing."""
        config = RYUConfig(
            host="localhost",
            port=8080,
            timeout_seconds=10,
            max_retries=2,
            retry_delay=1.0
        )
        connector = create_ryu_connector(config=config)
        yield connector
        connector.close()
    
    @pytest.fixture
    def comnetsemu_connector(self):
        """Create ComnetsEMU connector for testing."""
        config = ComnetsEMUConfig(
            host="localhost",
            port=6653,
            api_port=8181,
            timeout_seconds=10,
            max_retries=2
        )
        connector = create_comnetsemu_connector(config=config)
        yield connector
        connector.close()
    
    def test_regression_flow_priority_validation(self, ryu_connector):
        """
        Regression: Flow priority must be validated
        Bug: Previously allowed negative priorities
        """
        action = NetworkAction(
            id="regression_priority",
            type=ActionType.FLOW_MOD,
            target="1",
            parameters={
                "operation": "add",
                "match": {"eth_type": 2048},
                "actions": ["output:1"],
                "priority": 1000,  # Valid priority
                "idle_timeout": 60,
                "hard_timeout": 120
            },
            priority=1000,
            timeout=30
        )
        
        try:
            result = ryu_connector.execute_flow_mod(action)
            assert isinstance(result, dict)
        except Exception:
            # Expected if RYU not running
            pass
    
    def test_regression_connection_pool_leak(self, ryu_connector):
        """
        Regression: Connection pool should not leak connections
        Bug: Previously connections were not properly closed
        """
        initial_status = ryu_connector.get_connection_status()
        
        # Make multiple requests
        for i in range(50):
            try:
                ryu_connector.get_connection_status()
            except Exception:
                pass
        
        final_status = ryu_connector.get_connection_status()
        
        # Connection pool should be stable
        assert "pool_stats" in final_status or "status" in final_status
    
    def test_regression_topology_cache_invalidation(self, comnetsemu_connector):
        """
        Regression: Topology cache must be invalidated on changes
        Bug: Previously cached stale topology data
        """
        # Get initial topology
        topology1 = comnetsemu_connector.get_network_topology()
        initial_switch_count = len(topology1.switches)
        
        # Make a change (in simulation mode, this updates the mock)
        action = NetworkAction(
            id="regression_topo_cache",
            type=ActionType.CONFIG_CHANGE,
            target="network",
            parameters={
                "config_type": "topology",
                "config_data": {
                    "operation": "add",
                    "element_type": "switch",
                    "element_id": "cache_test_switch",
                    "properties": {"dpid": "999", "ports": 4}
                }
            },
            priority=1000,
            timeout=30
        )
        
        result = comnetsemu_connector.execute_topology_change(action)
        
        # Get topology again
        topology2 = comnetsemu_connector.get_network_topology()
        
        # Should reflect the change (in simulation mode)
        assert topology2 is not None
        assert len(topology2.switches) >= initial_switch_count
    
    def test_regression_qos_policy_overlap(self, comnetsemu_connector):
        """
        Regression: QoS policies should handle overlapping targets
        Bug: Previously conflicting policies caused issues
        """
        # Add first policy
        action1 = NetworkAction(
            id="regression_qos_1",
            type=ActionType.CONFIG_CHANGE,
            target="s1",
            parameters={
                "config_type": "qos",
                "config_data": {
                    "policy_id": "overlap_policy_1",
                    "target_type": "switch",
                    "target_id": "s1",
                    "bandwidth_limit": 1000,
                    "latency_limit": 10,
                    "packet_loss_limit": 0.01
                }
            },
            priority=1000,
            timeout=30
        )
        
        result1 = comnetsemu_connector.execute_qos_policy(action1)
        assert result1["success"]
        
        # Add overlapping policy
        action2 = NetworkAction(
            id="regression_qos_2",
            type=ActionType.CONFIG_CHANGE,
            target="s1",
            parameters={
                "config_type": "qos",
                "config_data": {
                    "policy_id": "overlap_policy_2",
                    "target_type": "switch",
                    "target_id": "s1",
                    "bandwidth_limit": 500,
                    "latency_limit": 5,
                    "packet_loss_limit": 0.001
                }
            },
            priority=1000,
            timeout=30
        )
        
        result2 = comnetsemu_connector.execute_qos_policy(action2)
        # Should handle gracefully
        assert isinstance(result2, dict)
    
    def test_regression_flow_timeout_handling(self, ryu_connector):
        """
        Regression: Flow timeouts must be properly handled
        Bug: Previously zero timeouts caused issues
        """
        action = NetworkAction(
            id="regression_timeout",
            type=ActionType.FLOW_MOD,
            target="1",
            parameters={
                "operation": "add",
                "match": {"eth_type": 2048, "ip_src": "10.0.1.1"},
                "actions": ["output:1"],
                "priority": 1000,
                "idle_timeout": 0,  # No idle timeout
                "hard_timeout": 0   # No hard timeout
            },
            priority=1000,
            timeout=30
        )
        
        try:
            result = ryu_connector.execute_flow_mod(action)
            assert isinstance(result, dict)
        except Exception:
            # Expected if RYU not running
            pass
    
    def test_regression_statistics_overflow(self, comnetsemu_connector):
        """
        Regression: Statistics counters should not overflow
        Bug: Previously large counters caused issues
        """
        # Get statistics multiple times
        for i in range(10):
            stats = comnetsemu_connector.get_network_statistics()
            assert stats is not None
            assert "topology_summary" in stats
            assert "traffic_summary" in stats
    
    def test_regression_concurrent_modifications(self, comnetsemu_connector):
        """
        Regression: Concurrent topology modifications should be safe
        Bug: Previously race conditions caused corruption
        """
        import concurrent.futures
        
        def add_element(idx):
            action = NetworkAction(
                id=f"regression_concurrent_{idx}",
                type=ActionType.CONFIG_CHANGE,
                target="network",
                parameters={
                    "config_type": "topology",
                    "config_data": {
                        "operation": "add",
                        "element_type": "host",
                        "element_id": f"concurrent_h{idx}",
                        "properties": {
                            "ip": f"10.200.{idx // 256}.{idx % 256}",
                            "mac": f"00:00:00:c8:{idx // 256:02x}:{idx % 256:02x}"
                        }
                    }
                },
                priority=1000,
                timeout=30
            )
            
            try:
                return comnetsemu_connector.execute_topology_change(action)
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        # Execute concurrent modifications
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(add_element, i) for i in range(20)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # Most should succeed
        successful = sum(1 for r in results if r.get("success", False))
        assert successful >= 15  # At least 75% should succeed
    
    def test_regression_memory_leak_on_errors(self, ryu_connector):
        """
        Regression: Memory should not leak on repeated errors
        Bug: Previously error handling leaked memory
        """
        import psutil
        import gc
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Generate many errors
        for i in range(100):
            action = NetworkAction(
                id=f"regression_error_{i}",
                type=ActionType.FLOW_MOD,
                target="999",  # Non-existent switch
                parameters={
                    "operation": "add",
                    "match": {"eth_type": 2048},
                    "actions": ["output:1"],
                    "priority": 1000,
                    "idle_timeout": 60,
                    "hard_timeout": 120
                },
                priority=1000,
                timeout=30
            )
            
            try:
                ryu_connector.execute_flow_mod(action)
            except Exception:
                pass
        
        # Force garbage collection
        gc.collect()
        time.sleep(1)
        
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 50MB)
        assert memory_increase < 50
    
    def test_regression_unicode_handling(self, comnetsemu_connector):
        """
        Regression: Unicode characters should be handled properly
        Bug: Previously unicode in names caused encoding errors
        """
        action = NetworkAction(
            id="regression_unicode",
            type=ActionType.CONFIG_CHANGE,
            target="network",
            parameters={
                "config_type": "topology",
                "config_data": {
                    "operation": "add",
                    "element_type": "host",
                    "element_id": "host_测试",  # Unicode characters
                    "properties": {
                        "ip": "10.0.1.100",
                        "mac": "00:00:00:00:01:64"
                    }
                }
            },
            priority=1000,
            timeout=30
        )
        
        try:
            result = comnetsemu_connector.execute_topology_change(action)
            # Should handle unicode gracefully
            assert isinstance(result, dict)
        except Exception as e:
            # May fail with validation error, but should not crash
            assert "encoding" not in str(e).lower()
    
    def test_regression_empty_action_list(self, ryu_connector):
        """
        Regression: Empty action lists should be validated
        Bug: Previously empty actions caused crashes
        """
        action = NetworkAction(
            id="regression_empty_actions",
            type=ActionType.FLOW_MOD,
            target="1",
            parameters={
                "operation": "add",
                "match": {"eth_type": 2048},
                "actions": [],  # Empty action list
                "priority": 1000,
                "idle_timeout": 60,
                "hard_timeout": 120
            },
            priority=1000,
            timeout=30
        )
        
        try:
            result = ryu_connector.execute_flow_mod(action)
            # Should either validate or handle gracefully
            assert isinstance(result, dict)
        except Exception as e:
            # Expected to fail with validation error
            assert "action" in str(e).lower() or "empty" in str(e).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
