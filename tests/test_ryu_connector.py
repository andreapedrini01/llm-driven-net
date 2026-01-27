"""
Unit tests for RYU Connector
Tests the real RYU Controller integration with connection pooling and error handling
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import time
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ryu_connector import (
    RYUConnector, RYUConfig, RYUConnectionPool, 
    ConnectionStatus, ConnectionPoolStats,
    create_ryu_connector
)
from action_models import NetworkAction, ActionType


class TestRYUConfig(unittest.TestCase):
    """Test RYU configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = RYUConfig()
        
        self.assertEqual(config.host, "localhost")
        self.assertEqual(config.port, 8080)
        self.assertEqual(config.api_version, "v1.0")
        self.assertEqual(config.timeout_seconds, 30)
        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.retry_delay, 2.0)
        self.assertFalse(config.ssl_enabled)
        self.assertTrue(config.ssl_verify)
        self.assertEqual(config.connection_pool_size, 10)
        self.assertEqual(config.max_connections_per_host, 5)
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = RYUConfig(
            host="192.168.1.100",
            port=9090,
            timeout_seconds=60,
            ssl_enabled=True
        )
        
        self.assertEqual(config.host, "192.168.1.100")
        self.assertEqual(config.port, 9090)
        self.assertEqual(config.timeout_seconds, 60)
        self.assertTrue(config.ssl_enabled)
    
    def test_base_url_http(self):
        """Test base URL generation for HTTP."""
        config = RYUConfig(host="example.com", port=8080, ssl_enabled=False)
        self.assertEqual(config.base_url, "http://example.com:8080")
    
    def test_base_url_https(self):
        """Test base URL generation for HTTPS."""
        config = RYUConfig(host="example.com", port=8443, ssl_enabled=True)
        self.assertEqual(config.base_url, "https://example.com:8443")


class TestRYUConnectionPool(unittest.TestCase):
    """Test RYU connection pool functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = RYUConfig(host="localhost", port=8080)
        self.pool = RYUConnectionPool(self.config)
    
    def tearDown(self):
        """Clean up after tests."""
        self.pool.close()
    
    def test_pool_initialization(self):
        """Test connection pool initialization."""
        self.assertIsNotNone(self.pool.session)
        self.assertEqual(self.pool.config, self.config)
        self.assertIsInstance(self.pool.stats, ConnectionPoolStats)
    
    def test_stats_update(self):
        """Test statistics update functionality."""
        initial_requests = self.pool.stats.total_requests
        
        self.pool._update_stats(True, 0.5)
        
        self.assertEqual(self.pool.stats.total_requests, initial_requests + 1)
        self.assertEqual(self.pool.stats.successful_requests, 1)
        self.assertEqual(self.pool.stats.failed_requests, 0)
        self.assertGreater(self.pool.stats.average_response_time, 0)
    
    def test_stats_failure(self):
        """Test statistics update for failures."""
        self.pool._update_stats(False, 1.0)
        
        self.assertEqual(self.pool.stats.total_requests, 1)
        self.assertEqual(self.pool.stats.successful_requests, 0)
        self.assertEqual(self.pool.stats.failed_requests, 1)
    
    @patch('requests.Session.get')
    def test_health_check_success(self, mock_get):
        """Test successful health check."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = self.pool.health_check()
        
        self.assertTrue(result)
        self.assertIsNotNone(self.pool.last_health_check)
        mock_get.assert_called_once()
    
    @patch('requests.Session.get')
    def test_health_check_failure(self, mock_get):
        """Test failed health check."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        result = self.pool.health_check()
        
        self.assertFalse(result)
        mock_get.assert_called_once()
    
    @patch('requests.Session.get')
    def test_health_check_exception(self, mock_get):
        """Test health check with connection exception."""
        mock_get.side_effect = Exception("Connection failed")
        
        result = self.pool.health_check()
        
        self.assertFalse(result)
        mock_get.assert_called_once()
    
    def test_should_perform_health_check(self):
        """Test health check timing logic."""
        # Initially should perform health check
        self.assertTrue(self.pool.should_perform_health_check())
        
        # After setting last check, should not perform immediately
        self.pool.last_health_check = datetime.now()
        self.assertFalse(self.pool.should_perform_health_check())
        
        # After interval passes, should perform again
        self.pool.last_health_check = datetime.now() - timedelta(minutes=10)
        self.assertTrue(self.pool.should_perform_health_check())


class TestRYUConnector(unittest.TestCase):
    """Test RYU connector functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = RYUConfig(host="localhost", port=8080)
        
        # Mock the connection pool to avoid actual network calls
        with patch('ryu_connector.RYUConnectionPool') as mock_pool_class:
            mock_pool = Mock()
            mock_pool.health_check.return_value = True
            mock_pool_class.return_value = mock_pool
            
            self.connector = RYUConnector(self.config)
            self.mock_pool = mock_pool
    
    def tearDown(self):
        """Clean up after tests."""
        self.connector.close()
    
    def test_connector_initialization(self):
        """Test connector initialization."""
        self.assertEqual(self.connector.config, self.config)
        self.assertEqual(self.connector.status, ConnectionStatus.CONNECTED)
        self.assertIsNotNone(self.connector.last_successful_request)
    
    @patch('ryu_connector.RYUConnectionPool')
    def test_initialization_failure(self, mock_pool_class):
        """Test connector initialization failure."""
        mock_pool = Mock()
        mock_pool.health_check.return_value = False
        mock_pool_class.return_value = mock_pool
        
        connector = RYUConnector(self.config)
        
        self.assertEqual(connector.status, ConnectionStatus.ERROR)
        connector.close()
    
    def test_create_flow_rule_data(self):
        """Test flow rule data preparation."""
        action = NetworkAction(
            id="test_action",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={
                "operation": "add",
                "match": {"ip_src": "192.168.1.100"},
                "actions": ["drop"],
                "idle_timeout": 60,
                "hard_timeout": 120
            },
            priority=1000
        )
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        
        with patch.object(self.connector, '_make_request_with_retry', return_value=mock_response):
            result = self.connector.execute_flow_mod(action)
        
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "add")
        self.assertEqual(result["switch_id"], "switch-1")
    
    def test_get_switches(self):
        """Test getting switches list."""
        expected_switches = [{"dpid": 1}, {"dpid": 2}]
        mock_response = Mock()
        mock_response.json.return_value = expected_switches
        
        with patch.object(self.connector, '_make_request_with_retry', return_value=mock_response):
            switches = self.connector.get_switches()
        
        self.assertEqual(switches, expected_switches)
    
    def test_get_flows(self):
        """Test getting flows for a switch."""
        switch_id = "1"
        expected_flows = [{"priority": 1000, "match": {"ip_src": "192.168.1.100"}}]
        mock_response = Mock()
        mock_response.json.return_value = {switch_id: expected_flows}
        
        with patch.object(self.connector, '_make_request_with_retry', return_value=mock_response):
            flows = self.connector.get_flows(switch_id)
        
        self.assertEqual(flows, expected_flows)
    
    def test_add_flow_success(self):
        """Test successful flow addition."""
        switch_id = "1"
        flow_rule = {
            "priority": 1000,
            "match": {"ip_src": "192.168.1.100"},
            "actions": ["drop"]
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        
        with patch.object(self.connector, '_make_request_with_retry', return_value=mock_response):
            result = self.connector.add_flow(switch_id, flow_rule)
        
        self.assertTrue(result)
    
    def test_add_flow_failure(self):
        """Test failed flow addition."""
        switch_id = "1"
        flow_rule = {"priority": 1000}
        
        mock_response = Mock()
        mock_response.status_code = 400
        
        with patch.object(self.connector, '_make_request_with_retry', return_value=mock_response):
            result = self.connector.add_flow(switch_id, flow_rule)
        
        self.assertFalse(result)
    
    def test_delete_flow(self):
        """Test flow deletion."""
        switch_id = "1"
        flow_rule = {
            "priority": 1000,
            "match": {"ip_src": "192.168.1.100"}
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        
        with patch.object(self.connector, '_make_request_with_retry', return_value=mock_response):
            result = self.connector.delete_flow(switch_id, flow_rule)
        
        self.assertTrue(result)
    
    def test_modify_flow(self):
        """Test flow modification."""
        switch_id = "1"
        flow_rule = {
            "priority": 1000,
            "match": {"ip_src": "192.168.1.100"},
            "actions": ["normal"]
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        
        with patch.object(self.connector, '_make_request_with_retry', return_value=mock_response):
            result = self.connector.modify_flow(switch_id, flow_rule)
        
        self.assertTrue(result)
    
    def test_get_network_topology(self):
        """Test getting network topology."""
        expected_switches = [{"dpid": 1}]
        expected_links = [{"src": {"dpid": 1, "port_no": 1}, "dst": {"dpid": 2, "port_no": 1}}]
        
        with patch.object(self.connector, 'get_switches', return_value=expected_switches):
            mock_response = Mock()
            mock_response.json.return_value = expected_links
            
            with patch.object(self.connector, '_make_request_with_retry', return_value=mock_response):
                topology = self.connector.get_network_topology()
        
        self.assertEqual(topology["switches"], expected_switches)
        self.assertEqual(topology["links"], expected_links)
        self.assertIn("timestamp", topology)
    
    def test_verify_flow_mod_success(self):
        """Test successful flow modification verification."""
        action = NetworkAction(
            id="test_action",
            type=ActionType.FLOW_MOD,
            target="1",
            parameters={"match": {"ip_src": "192.168.1.100"}},
            priority=1000
        )
        
        # Mock flows that include our expected flow
        expected_flows = [
            {"priority": 1000, "match": {"ip_src": "192.168.1.100"}},
            {"priority": 500, "match": {"ip_dst": "192.168.1.200"}}
        ]
        
        with patch.object(self.connector, 'get_flows', return_value=expected_flows):
            result = self.connector.verify_action_applied(action)
        
        self.assertTrue(result)
    
    def test_verify_flow_mod_failure(self):
        """Test failed flow modification verification."""
        action = NetworkAction(
            id="test_action",
            type=ActionType.FLOW_MOD,
            target="1",
            parameters={"match": {"ip_src": "192.168.1.100"}},
            priority=1000
        )
        
        # Mock flows that don't include our expected flow
        expected_flows = [
            {"priority": 500, "match": {"ip_dst": "192.168.1.200"}}
        ]
        
        with patch.object(self.connector, 'get_flows', return_value=expected_flows):
            result = self.connector.verify_action_applied(action)
        
        self.assertFalse(result)
    
    def test_matches_flow_criteria(self):
        """Test flow criteria matching logic."""
        # Exact match
        actual = {"ip_src": "192.168.1.100", "tcp_dst": 80}
        expected = {"ip_src": "192.168.1.100"}
        self.assertTrue(self.connector._matches_flow_criteria(actual, expected))
        
        # No match
        actual = {"ip_src": "192.168.1.200"}
        expected = {"ip_src": "192.168.1.100"}
        self.assertFalse(self.connector._matches_flow_criteria(actual, expected))
        
        # Missing field
        actual = {"tcp_dst": 80}
        expected = {"ip_src": "192.168.1.100"}
        self.assertFalse(self.connector._matches_flow_criteria(actual, expected))
    
    def test_get_connection_status(self):
        """Test getting connection status."""
        # Mock the stats properly
        mock_stats = Mock()
        mock_stats.total_requests = 10
        mock_stats.successful_requests = 8
        mock_stats.failed_requests = 2
        mock_stats.average_response_time = 0.5
        mock_stats.last_updated = datetime.now()
        
        with patch.object(self.connector.connection_pool, 'get_stats', return_value=mock_stats):
            status = self.connector.get_connection_status()
        
        self.assertIn("status", status)
        self.assertIn("config", status)
        self.assertIn("pool_stats", status)
        self.assertEqual(status["status"], ConnectionStatus.CONNECTED.value)
        self.assertEqual(status["config"]["host"], "localhost")
        self.assertEqual(status["config"]["port"], 8080)
        self.assertEqual(status["pool_stats"]["total_requests"], 10)
        self.assertEqual(status["pool_stats"]["successful_requests"], 8)


class TestRYUConnectorRetryLogic(unittest.TestCase):
    """Test RYU connector retry logic and error handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = RYUConfig(host="localhost", port=8080, max_retries=2, retry_delay=0.1)
        
        with patch('ryu_connector.RYUConnectionPool') as mock_pool_class:
            mock_pool = Mock()
            mock_pool.health_check.return_value = True
            mock_pool_class.return_value = mock_pool
            
            self.connector = RYUConnector(self.config)
            self.mock_pool = mock_pool
    
    def tearDown(self):
        """Clean up after tests."""
        self.connector.close()
    
    @patch('time.sleep')  # Speed up tests by mocking sleep
    def test_retry_on_server_error(self, mock_sleep):
        """Test retry logic on server errors."""
        # First two attempts fail with 500, third succeeds
        responses = [
            Mock(status_code=500),
            Mock(status_code=500),
            Mock(status_code=200)
        ]
        
        with patch.object(self.connector.connection_pool, 'request') as mock_request:
            mock_request.return_value.__enter__.side_effect = responses
            mock_request.return_value.__exit__.return_value = None
            
            result = self.connector._make_request_with_retry("GET", "/test")
        
        self.assertEqual(result.status_code, 200)
        self.assertEqual(mock_sleep.call_count, 2)  # Two retries
    
    @patch('time.sleep')
    def test_no_retry_on_client_error(self, mock_sleep):
        """Test no retry on client errors."""
        mock_response = Mock(status_code=400)
        mock_response.raise_for_status.side_effect = Exception("Bad Request")
        
        with patch.object(self.connector.connection_pool, 'request') as mock_request:
            mock_request.return_value.__enter__.return_value = mock_response
            mock_request.return_value.__exit__.return_value = None
            
            with self.assertRaises(Exception):
                self.connector._make_request_with_retry("GET", "/test")
        
        mock_sleep.assert_not_called()  # No retries for client errors
    
    @patch('time.sleep')
    def test_retry_exhaustion(self, mock_sleep):
        """Test behavior when all retries are exhausted."""
        mock_response = Mock(status_code=500)
        mock_response.raise_for_status.side_effect = Exception("Server Error")
        
        with patch.object(self.connector.connection_pool, 'request') as mock_request:
            mock_request.return_value.__enter__.return_value = mock_response
            mock_request.return_value.__exit__.return_value = None
            
            with self.assertRaises(Exception):
                self.connector._make_request_with_retry("GET", "/test")
        
        # Should have made max_retries + 1 attempts
        self.assertEqual(mock_request.call_count, self.config.max_retries + 1)


class TestFactoryFunction(unittest.TestCase):
    """Test factory function for creating RYU connectors."""
    
    def test_create_ryu_connector_defaults(self):
        """Test factory function with default parameters."""
        with patch('ryu_connector.RYUConnector') as mock_connector_class:
            mock_connector = Mock()
            mock_connector_class.return_value = mock_connector
            
            connector = create_ryu_connector()
            
            # Verify RYUConfig was created with defaults
            args, kwargs = mock_connector_class.call_args
            config = args[0]
            self.assertEqual(config.host, "localhost")
            self.assertEqual(config.port, 8080)
    
    def test_create_ryu_connector_custom(self):
        """Test factory function with custom parameters."""
        with patch('ryu_connector.RYUConnector') as mock_connector_class:
            mock_connector = Mock()
            mock_connector_class.return_value = mock_connector
            
            connector = create_ryu_connector(
                host="192.168.1.100",
                port=9090,
                timeout_seconds=60
            )
            
            # Verify RYUConfig was created with custom values
            args, kwargs = mock_connector_class.call_args
            config = args[0]
            self.assertEqual(config.host, "192.168.1.100")
            self.assertEqual(config.port, 9090)
            self.assertEqual(config.timeout_seconds, 60)


if __name__ == "__main__":
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_classes = [
        TestRYUConfig,
        TestRYUConnectionPool,
        TestRYUConnector,
        TestRYUConnectorRetryLogic,
        TestFactoryFunction
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"RYU CONNECTOR TESTS SUMMARY")
    print(f"{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print(f"\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback.split('AssertionError: ')[-1].split('\\n')[0]}")
    
    if result.errors:
        print(f"\nERRORS:")
        for test, traceback in result.errors:
            error_lines = traceback.split('\n')
            error_msg = next((line for line in error_lines if line.strip() and not line.startswith('  File')), "Unknown error")
            print(f"- {test}: {error_msg}")