#!/usr/bin/env python3
"""
Integration tests for RYU Connector
Tests the real RYU Controller integration with various scenarios
"""

import pytest
import json
import time
from datetime import datetime
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from connectors.ryu_connector import create_ryu_connector, RYUConfig
from models.action_models import NetworkAction, ActionType


class TestRYUIntegration:
    """Integration tests for RYU connector."""
    
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
    
    def test_connection_initialization(self, ryu_connector):
        """Test RYU connector initialization."""
        status = ryu_connector.get_connection_status()
        
        assert status is not None
        assert "status" in status
        assert "config" in status
        assert status["config"]["host"] == "localhost"
        assert status["config"]["port"] == 8080
    
    def test_switches_retrieval(self, ryu_connector):
        """Test retrieving switches from RYU."""
        try:
            switches = ryu_connector.get_switches()
            assert isinstance(switches, list)
            # Note: May be empty if no switches connected
        except Exception as e:
            # Expected if RYU is not running
            assert "Connection" in str(e) or "timeout" in str(e).lower()
    
    def test_flow_operations(self, ryu_connector):
        """Test flow operations with RYU."""
        # Create a test flow action
        action = NetworkAction(
            id="test_flow_001",
            type=ActionType.FLOW_MOD,
            target="1",  # Switch DPID
            parameters={
                "operation": "add",
                "match": {
                    "ip_src": "10.0.0.1",
                    "eth_type": 2048
                },
                "actions": ["output:2"],
                "priority": 1000,
                "idle_timeout": 60,
                "hard_timeout": 120
            },
            priority=1000,
            timeout=30
        )
        
        try:
            result = ryu_connector.execute_flow_mod(action)
            assert isinstance(result, dict)
            assert "success" in result
            assert "message" in result
            
        except Exception as e:
            # Expected if RYU is not running or switch not connected
            assert "Connection" in str(e) or "timeout" in str(e).lower()
    
    def test_network_topology(self, ryu_connector):
        """Test network topology retrieval."""
        try:
            topology = ryu_connector.get_network_topology()
            assert isinstance(topology, dict)
            assert "switches" in topology
            assert "links" in topology
            assert "timestamp" in topology
            
        except Exception as e:
            # Expected if RYU is not running
            assert "Connection" in str(e) or "timeout" in str(e).lower()
    
    def test_connection_pooling(self, ryu_connector):
        """Test connection pooling functionality."""
        status = ryu_connector.get_connection_status()
        
        if "pool_stats" in status:
            stats = status["pool_stats"]
            assert "total_requests" in stats
            assert "successful_requests" in stats
            assert "failed_requests" in stats
            assert "average_response_time" in stats
    
    def test_error_handling(self):
        """Test error handling with invalid configuration."""
        # Test with invalid host
        config = RYUConfig(
            host="invalid-host-12345",
            port=8080,
            timeout_seconds=5,
            max_retries=1
        )
        
        connector = create_ryu_connector(config=config)
        
        try:
            switches = connector.get_switches()
            # Should raise an exception
            assert False, "Expected connection error"
        except Exception as e:
            assert "Connection" in str(e) or "timeout" in str(e).lower()
        finally:
            connector.close()
    
    def test_action_verification(self, ryu_connector):
        """Test action verification functionality."""
        action = NetworkAction(
            id="test_verify_001",
            type=ActionType.FLOW_MOD,
            target="1",
            parameters={
                "match": {"ip_src": "10.0.0.1"},
                "actions": ["drop"]
            },
            priority=1000
        )
        
        try:
            # This will likely fail if RYU is not running, which is expected
            result = ryu_connector.verify_action_applied(action)
            assert isinstance(result, bool)
            
        except Exception as e:
            # Expected if RYU is not running
            assert "Connection" in str(e) or "timeout" in str(e).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])