"""
Integration tests for RYU Connector
Tests the complete integration between Northbound Script and RYU Controller
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import time
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.northbound_script import NorthboundScript
from src.connectors.ryu_connector import RYUConnector, RYUConfig, ConnectionStatus
from src.models.action_models import NetworkAction, ActionType


class TestRYUIntegration(unittest.TestCase):
    """Test complete integration with RYU Controller."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock RYU connector to avoid actual network calls
        self.mock_ryu_connector = Mock()
        self.mock_ryu_connector.get_connection_status.return_value = {
            "status": "connected",
            "config": {"host": "localhost", "port": 8080},
            "pool_stats": {"total_requests": 0, "successful_requests": 0}
        }
        
        with patch('ryu_connector.create_ryu_connector', return_value=self.mock_ryu_connector):
            self.northbound = NorthboundScript(
                log_dir="./logs",
                ryu_host="localhost",
                ryu_port=8080,
                timeout_seconds=30,
                max_retries=3
            )
    
    def tearDown(self):
        """Clean up after tests."""
        self.northbound.close()
    
    def test_northbound_initialization_with_ryu(self):
        """Test Northbound Script initialization with RYU configuration."""
        # Verify RYU configuration was passed correctly
        self.assertEqual(self.northbound.max_retries, 3)
        self.assertIsNotNone(self.northbound.network_interface)
        
        # Test connection status
        status = self.northbound.get_ryu_status()
        self.assertEqual(status["status"], "connected")
        self.assertEqual(status["config"]["host"], "localhost")
        self.assertEqual(status["config"]["port"], 8080)
    
    def test_flow_mod_execution_with_ryu(self):
        """Test flow modification execution through RYU."""
        # Mock successful flow modification
        self.mock_ryu_connector.execute_flow_mod.return_value = {
            "success": True,
            "operation": "add",
            "switch_id": "1",
            "message": "Flow rule added successfully"
        }
        
        self.mock_ryu_connector.verify_action_applied.return_value = True
        
        # Mock network state
        self.mock_ryu_connector.get_switches.return_value = [{"dpid": 1}]
        self.mock_ryu_connector.get_flows.return_value = []
        self.mock_ryu_connector.get_port_stats.return_value = []
        
        # Create test action
        llm_output = json.dumps({
            "id": "seq_integration_test",
            "intent_id": "intent_test_flow",
            "estimated_duration": 10,
            "actions": [{
                "id": "action_flow_001",
                "type": "flow_mod",
                "target": "switch-1",
                "parameters": {
                    "operation": "add",
                    "match": {"ip_src": "192.168.1.100"},
                    "actions": ["drop"],
                    "idle_timeout": 60,
                    "hard_timeout": 120
                },
                "priority": 1000,
                "timeout": 30,
                "description": "Block suspicious traffic"
            }],
            "dependencies": [],
            "rollback_plan": []
        })
        
        # Execute the action
        result = self.northbound.process_llm_output(llm_output, dry_run=False)
        
        # Verify results
        self.assertTrue(result["success"])
        self.assertEqual(result["total_actions"], 1)
        self.assertEqual(result["successful_actions"], 1)
        self.assertEqual(result["failed_actions"], 0)
        
        # Verify RYU connector was called
        self.mock_ryu_connector.execute_flow_mod.assert_called_once()
        self.mock_ryu_connector.verify_action_applied.assert_called_once()
    
    def test_flow_mod_failure_with_retry(self):
        """Test flow modification failure and retry logic."""
        # Mock first attempt failure, second attempt success
        self.mock_ryu_connector.execute_flow_mod.side_effect = [
            Exception("Connection timeout"),
            {
                "success": True,
                "operation": "add",
                "switch_id": "1",
                "message": "Flow rule added successfully"
            }
        ]
        
        self.mock_ryu_connector.verify_action_applied.return_value = True
        
        # Mock network state
        self.mock_ryu_connector.get_switches.return_value = [{"dpid": 1}]
        self.mock_ryu_connector.get_flows.return_value = []
        self.mock_ryu_connector.get_port_stats.return_value = []
        
        llm_output = json.dumps({
            "id": "seq_retry_test",
            "intent_id": "intent_test_retry",
            "estimated_duration": 10,
            "actions": [{
                "id": "action_retry_001",
                "type": "flow_mod",
                "target": "switch-1",
                "parameters": {
                    "operation": "add",
                    "match": {"ip_src": "192.168.1.200"},
                    "actions": ["drop"]
                },
                "priority": 1000,
                "timeout": 30
            }],
            "dependencies": [],
            "rollback_plan": []
        })
        
        # Execute with retry
        result = self.northbound.process_llm_output(llm_output, dry_run=False)
        
        # Should succeed after retry
        self.assertTrue(result["success"])
        self.assertEqual(self.mock_ryu_connector.execute_flow_mod.call_count, 2)
    
    def test_network_state_retrieval(self):
        """Test network state retrieval through RYU."""
        # Mock network state data
        mock_switches = [{"dpid": 1, "ports": [{"port_no": 1, "name": "eth1"}]}]
        mock_flows = [{"priority": 1000, "match": {"ip_src": "192.168.1.100"}}]
        mock_port_stats = [{"port_no": 1, "rx_packets": 1000, "tx_packets": 500}]
        
        self.mock_ryu_connector.get_switches.return_value = mock_switches
        self.mock_ryu_connector.get_flows.return_value = mock_flows
        self.mock_ryu_connector.get_port_stats.return_value = mock_port_stats
        
        # Get network state
        state = self.northbound.network_interface.get_network_state("switch-1")
        
        # Verify state structure
        self.assertEqual(state["target"], "switch-1")
        self.assertEqual(state["switch_id"], "1")
        self.assertEqual(state["status"], "active")
        self.assertIn("switch_info", state)
        self.assertIn("flows", state)
        self.assertIn("port_stats", state)
        self.assertIn("timestamp", state)
        
        # Verify RYU connector calls
        self.mock_ryu_connector.get_switches.assert_called_once()
        self.mock_ryu_connector.get_flows.assert_called_once_with("1")
        self.mock_ryu_connector.get_port_stats.assert_called_once_with("1")
    
    def test_connection_error_handling(self):
        """Test handling of RYU connection errors."""
        # Mock connection error
        self.mock_ryu_connector.get_switches.side_effect = Exception("Connection refused")
        
        # Try to get network state
        state = self.northbound.network_interface.get_network_state("switch-1")
        
        # Should handle error gracefully
        self.assertEqual(state["status"], "error")
        self.assertIn("error", state)
        self.assertEqual(state["target"], "switch-1")
    
    def test_action_verification(self):
        """Test action verification through RYU."""
        # Create test action
        action = NetworkAction(
            id="test_verify",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={
                "match": {"ip_src": "192.168.1.100"},
                "actions": ["drop"]
            },
            priority=1000
        )
        
        # Mock successful verification
        self.mock_ryu_connector.verify_action_applied.return_value = True
        
        # Verify action
        result = self.northbound.network_interface.verify_action_applied(action)
        
        self.assertTrue(result)
        self.mock_ryu_connector.verify_action_applied.assert_called_once_with(action)
    
    def test_action_verification_failure(self):
        """Test action verification failure."""
        action = NetworkAction(
            id="test_verify_fail",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={
                "match": {"ip_src": "192.168.1.100"},
                "actions": ["drop"]
            },
            priority=1000
        )
        
        # Mock verification failure
        self.mock_ryu_connector.verify_action_applied.return_value = False
        
        # Verify action
        result = self.northbound.network_interface.verify_action_applied(action)
        
        self.assertFalse(result)
    
    def test_multiple_actions_sequence(self):
        """Test execution of multiple actions in sequence."""
        # Mock successful execution for all actions
        self.mock_ryu_connector.execute_flow_mod.return_value = {
            "success": True,
            "operation": "add",
            "switch_id": "1",
            "message": "Flow rule added successfully"
        }
        
        self.mock_ryu_connector.verify_action_applied.return_value = True
        
        # Mock network state
        self.mock_ryu_connector.get_switches.return_value = [{"dpid": 1}]
        self.mock_ryu_connector.get_flows.return_value = []
        self.mock_ryu_connector.get_port_stats.return_value = []
        
        llm_output = json.dumps({
            "id": "seq_multiple_test",
            "intent_id": "intent_multiple",
            "estimated_duration": 20,
            "actions": [
                {
                    "id": "action_001",
                    "type": "flow_mod",
                    "target": "switch-1",
                    "parameters": {
                        "operation": "add",
                        "match": {"ip_src": "192.168.1.100"},
                        "actions": ["drop"]
                    },
                    "priority": 1000,
                    "timeout": 30
                },
                {
                    "id": "action_002",
                    "type": "flow_mod",
                    "target": "switch-1",
                    "parameters": {
                        "operation": "add",
                        "match": {"ip_src": "192.168.1.200"},
                        "actions": ["drop"]
                    },
                    "priority": 1000,
                    "timeout": 30
                }
            ],
            "dependencies": [],
            "rollback_plan": []
        })
        
        # Execute multiple actions
        result = self.northbound.process_llm_output(llm_output, dry_run=False)
        
        # Verify all actions succeeded
        self.assertTrue(result["success"])
        self.assertEqual(result["total_actions"], 2)
        self.assertEqual(result["successful_actions"], 2)
        self.assertEqual(result["failed_actions"], 0)
        
        # Verify RYU connector was called for each action
        self.assertEqual(self.mock_ryu_connector.execute_flow_mod.call_count, 2)
        self.assertEqual(self.mock_ryu_connector.verify_action_applied.call_count, 2)
    
    def test_rollback_on_failure(self):
        """Test rollback execution when an action fails."""
        # Mock first action success, second action failure
        self.mock_ryu_connector.execute_flow_mod.side_effect = [
            {
                "success": True,
                "operation": "add",
                "switch_id": "1",
                "message": "First flow rule added"
            },
            Exception("Second action failed")
        ]
        
        # Mock verification success for first action
        self.mock_ryu_connector.verify_action_applied.side_effect = [True, False]
        
        # Mock network state
        self.mock_ryu_connector.get_switches.return_value = [{"dpid": 1}]
        self.mock_ryu_connector.get_flows.return_value = []
        self.mock_ryu_connector.get_port_stats.return_value = []
        
        llm_output = json.dumps({
            "id": "seq_rollback_test",
            "intent_id": "intent_rollback",
            "estimated_duration": 20,
            "actions": [
                {
                    "id": "action_001",
                    "type": "flow_mod",
                    "target": "switch-1",
                    "parameters": {
                        "operation": "add",
                        "match": {"ip_src": "192.168.1.100"},
                        "actions": ["drop"]
                    },
                    "priority": 1000,
                    "timeout": 30
                },
                {
                    "id": "action_002",
                    "type": "flow_mod",
                    "target": "switch-1",
                    "parameters": {
                        "operation": "add",
                        "match": {"ip_src": "192.168.1.200"},
                        "actions": ["drop"]
                    },
                    "priority": 1000,
                    "timeout": 30
                }
            ],
            "dependencies": [],
            "rollback_plan": [
                {
                    "id": "rollback_001",
                    "type": "flow_mod",
                    "target": "switch-1",
                    "parameters": {
                        "operation": "delete",
                        "match": {"ip_src": "192.168.1.100"}
                    },
                    "priority": 1000,
                    "timeout": 30
                }
            ]
        })
        
        # Execute with rollback
        result = self.northbound.process_llm_output(llm_output, dry_run=False)
        
        # Should fail overall but execute rollback
        self.assertFalse(result["success"])
        self.assertEqual(result["total_actions"], 3)  # 2 original + 1 rollback
        self.assertEqual(result["successful_actions"], 2)  # 1 original + 1 rollback
        self.assertEqual(result["failed_actions"], 1)  # 1 failed original action


class TestRYUConnectorConfiguration(unittest.TestCase):
    """Test RYU connector configuration and customization."""
    
    def test_custom_ryu_configuration(self):
        """Test Northbound Script with custom RYU configuration."""
        custom_config = {
            "ryu_host": "192.168.1.100",
            "ryu_port": 9090,
            "timeout_seconds": 60,
            "max_retries": 5,
            "retry_delay": 3.0,
            "connection_pool_size": 20
        }
        
        with patch('ryu_connector.create_ryu_connector') as mock_create:
            mock_connector = Mock()
            mock_connector.get_connection_status.return_value = {
                "status": "connected",
                "config": {
                    "host": custom_config["ryu_host"],
                    "port": custom_config["ryu_port"],
                    "timeout": custom_config["timeout_seconds"]
                }
            }
            mock_create.return_value = mock_connector
            
            northbound = NorthboundScript(
                log_dir="./logs",
                **custom_config
            )
            
            # Verify configuration was passed to RYU connector
            mock_create.assert_called_once()
            call_args = mock_create.call_args
            
            # Check that custom configuration was passed
            self.assertEqual(call_args[1]["host"], custom_config["ryu_host"])
            self.assertEqual(call_args[1]["port"], custom_config["ryu_port"])
            self.assertEqual(call_args[1]["timeout_seconds"], custom_config["timeout_seconds"])
            
            # Verify Northbound Script configuration
            self.assertEqual(northbound.max_retries, custom_config["max_retries"])
            self.assertEqual(northbound.retry_delay, custom_config["retry_delay"])
            
            northbound.close()
    
    def test_default_ryu_configuration(self):
        """Test Northbound Script with default RYU configuration."""
        with patch('ryu_connector.create_ryu_connector') as mock_create:
            mock_connector = Mock()
            mock_connector.get_connection_status.return_value = {
                "status": "connected",
                "config": {"host": "localhost", "port": 8080}
            }
            mock_create.return_value = mock_connector
            
            northbound = NorthboundScript(log_dir="./logs")
            
            # Verify default configuration was used
            mock_create.assert_called_once()
            call_args = mock_create.call_args
            
            self.assertEqual(call_args[1]["host"], "localhost")
            self.assertEqual(call_args[1]["port"], 8080)
            
            northbound.close()


if __name__ == "__main__":
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_classes = [
        TestRYUIntegration,
        TestRYUConnectorConfiguration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"RYU INTEGRATION TESTS SUMMARY")
    print(f"{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print(f"\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}")
    
    if result.errors:
        print(f"\nERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}")
    
    if result.testsRun > 0 and len(result.failures) == 0 and len(result.errors) == 0:
        print(f"\n🎉 All integration tests passed! RYU integration is working correctly.")