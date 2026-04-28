"""
Comprehensive integration test suite for the LLM Integration Module.

This test suite covers:
- End-to-end test scenarios with mock JSON files
- Load testing and performance validation
- Chaos engineering tests (corrupted files, missing files)
- Rate limiting and cost management
- File watching and automatic state refresh

Task 12.1: Create integration test suite
Requirements: All
"""

import pytest
import asyncio
import json
import time
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import Mock, patch, AsyncMock
import threading

from llm_integration_module.services.state_file_reader import StateFileReader, FileReadResult
from llm_integration_module.services.chatgpt_client import ChatGPTClient, ChatGPTConfig, BudgetAlert
from llm_integration_module.services.action_output import ActionOutputInterface, ActionStatus
from llm_integration_module.services.intent_parser import IntentParser
from llm_integration_module.services.context_analyzer import ContextAnalyzer
from llm_integration_module.models.network import NetworkState, Topology, Switch, Host, Link
from llm_integration_module.models.network import NetworkMetrics, BandwidthMetrics, LatencyMetrics, UtilizationMetrics
from llm_integration_module.models.intent import IntentObject, IntentType
from llm_integration_module.models.actions import NetworkAction, ActionType, ActionSequence


class TestEndToEndScenarios:
    """End-to-end integration tests with mock JSON files."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "cache"
        self.output_dir = Path(self.temp_dir) / "output"
        self.cache_dir.mkdir(parents=True)
        self.output_dir.mkdir(parents=True)
        
        self.state_file_path = self.cache_dir / "network_state.json"
        self.parser = IntentParser()
        self.context_analyzer = ContextAnalyzer()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def _create_mock_network_state_json(self, **overrides) -> Dict[str, Any]:
        """Create a mock network state JSON with optional overrides."""
        base_state = {
            "timestamp": datetime.now().isoformat(),
            "topology": {
                "switches": [
                    {
                        "id": "sw1",
                        "name": "switch1",
                        "dpid": "0000000000000001",
                        "ports": [1, 2, 3],
                        "status": "active"
                    },
                    {
                        "id": "sw2",
                        "name": "switch2",
                        "dpid": "0000000000000002",
                        "ports": [1, 2, 3],
                        "status": "active"
                    }
                ],
                "hosts": [
                    {
                        "id": "h1",
                        "mac_address": "00:00:00:00:00:01",
                        "ip_address": "10.0.0.1",
                        "connected_switch": "sw1",
                        "connected_port": 1,
                        "status": "active"
                    }
                ],
                "links": [
                    {
                        "id": "link1",
                        "source_switch": "sw1",
                        "source_port": 2,
                        "destination_switch": "sw2",
                        "destination_port": 2,
                        "bandwidth": 1000,
                        "status": "active"
                    }
                ]
            },
            "flows": [],
            "slices": [],
            "metrics": {
                "bandwidth": {
                    "total_capacity": 1000,
                    "used_bandwidth": 200,
                    "available_bandwidth": 800,
                    "utilization_percentage": 20.0
                },
                "latency": {
                    "average_latency": 5.0,
                    "min_latency": 1.0,
                    "max_latency": 10.0,
                    "jitter": 1.5
                },
                "utilization": {
                    "cpu_utilization": 30.0,
                    "memory_utilization": 40.0
                }
            },
            "anomalies": []
        }
        
        # Apply overrides
        for key, value in overrides.items():
            if '.' in key:
                # Handle nested keys like "metrics.bandwidth.used_bandwidth"
                keys = key.split('.')
                current = base_state
                for k in keys[:-1]:
                    current = current[k]
                current[keys[-1]] = value
            else:
                base_state[key] = value
        
        return base_state
    
    def _write_state_file(self, state_data: Dict[str, Any]) -> None:
        """Write state data to the mock state file."""
        with open(self.state_file_path, 'w') as f:
            json.dump(state_data, f, indent=2)
    
    def test_complete_workflow_with_valid_state(self):
        """Test complete workflow from state file to action output."""
        # Create and write valid state file
        state_data = self._create_mock_network_state_json()
        self._write_state_file(state_data)
        
        # Initialize state file reader
        reader = StateFileReader(
            cache_folder=str(self.cache_dir),
            state_file_name="network_state.json"
        )
        
        # Load network state
        network_state = reader.load_network_state()
        assert network_state is not None
        assert len(network_state.topology.switches) == 2
        assert network_state.metrics.bandwidth.available_bandwidth == 800
        
        # Parse intent
        intent_text = "configure switch sw1 with bandwidth 500mbps"
        result = self.parser.analyze_and_clarify_intent(intent_text, network_state)
        
        assert result['intent'] is not None
        assert result['intent'].intent_type == IntentType.CONFIGURATION
        
        # Verify context analysis
        contextualized = result['contextualized_intent']
        assert 'sw1' in contextualized.relevant_resources
        
        # Create action sequence
        action = NetworkAction(
            id="action-1",
            type=ActionType.CONFIG_CHANGE,
            target="sw1",
            parameters={"bandwidth": 500},
            priority=100,
            timeout=30
        )
        
        sequence = ActionSequence(
            id="seq-1",
            intent_id=result['intent'].id,
            actions=[action],
            estimated_duration=30
        )
        
        # Output actions
        output_interface = ActionOutputInterface(
            output_directory=str(self.output_dir / "actions"),
            log_directory=str(self.output_dir / "logs")
        )
        
        from llm_integration_module.models.actions import ValidationResult, SafetyReport
        validation = ValidationResult(is_valid=True, errors=[], warnings=[])
        safety = SafetyReport(is_safe=True, risk_level="low", risks=[])
        
        result = output_interface.output_actions(
            sequence=sequence,
            validation_result=validation,
            safety_report=safety
        )
        
        assert result['success'] is True
        assert result['file_path'] is not None
        assert Path(result['file_path']).exists()
    
    def test_workflow_with_multiple_intents(self):
        """Test processing multiple intents in sequence."""
        state_data = self._create_mock_network_state_json()
        self._write_state_file(state_data)
        
        reader = StateFileReader(cache_folder=str(self.cache_dir))
        network_state = reader.load_network_state()
        
        intents = [
            "show status of switch sw1",
            "configure switch sw2 with bandwidth 1000mbps",
            "create flow from h1 to sw2"
        ]
        
        results = []
        for intent_text in intents:
            result = self.parser.analyze_and_clarify_intent(intent_text, network_state)
            results.append(result)
            assert result['intent'] is not None
        
        # Verify all intents were processed
        assert len(results) == 3
        assert results[0]['intent'].intent_type in [IntentType.QUERY, IntentType.CONFIGURATION]
        assert results[1]['intent'].intent_type == IntentType.CONFIGURATION
        assert results[2]['intent'].intent_type == IntentType.CONFIGURATION


class TestChaosEngineering:
    """Chaos engineering tests for resilience."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "cache"
        self.cache_dir.mkdir(parents=True)
        self.state_file_path = self.cache_dir / "network_state.json"
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def test_missing_state_file(self):
        """Test handling of missing state file."""
        reader = StateFileReader(
            cache_folder=str(self.cache_dir),
            max_retries=3,
            initial_backoff=0.1
        )
        
        # Try to load non-existent file
        result = reader.read_json_file()
        
        assert result.success is False
        assert result.error_type == "FileNotFoundError"
        assert result.attempts == 3
    
    def test_corrupted_json_file(self):
        """Test handling of corrupted JSON file."""
        # Write corrupted JSON
        with open(self.state_file_path, 'w') as f:
            f.write('{"timestamp": "2024-01-01", "topology": {invalid json')
        
        reader = StateFileReader(
            cache_folder=str(self.cache_dir),
            max_retries=3,
            initial_backoff=0.1
        )
        
        result = reader.read_json_file()
        
        assert result.success is False
        assert result.error_type == "JSONDecodeError"
        assert "JSON decode error" in result.error
    
    def test_empty_json_file(self):
        """Test handling of empty JSON file."""
        # Write empty file
        with open(self.state_file_path, 'w') as f:
            f.write('')
        
        reader = StateFileReader(
            cache_folder=str(self.cache_dir),
            max_retries=2,
            initial_backoff=0.1
        )
        
        result = reader.read_json_file()
        
        assert result.success is False
        assert result.error_type == "ValueError"
        assert "empty" in result.error.lower()
    
    def test_invalid_json_structure(self):
        """Test handling of JSON with invalid structure."""
        # Write JSON with missing required fields
        invalid_state = {
            "timestamp": "2024-01-01T00:00:00Z",
            # Missing topology, flows, metrics
        }
        
        with open(self.state_file_path, 'w') as f:
            json.dump(invalid_state, f)
        
        reader = StateFileReader(
            cache_folder=str(self.cache_dir),
            max_retries=2,
            initial_backoff=0.1
        )
        
        result = reader.read_json_file()
        
        assert result.success is False
        assert result.error_type == "ValueError"
        assert "Invalid JSON structure" in result.error
    
    def test_file_permission_error(self):
        """Test handling of file permission errors."""
        # Create file
        with open(self.state_file_path, 'w') as f:
            json.dump({"test": "data"}, f)
        
        # Make file unreadable (Unix-like systems only)
        import os
        import stat
        if os.name != 'nt':  # Skip on Windows
            os.chmod(self.state_file_path, 0o000)
            
            reader = StateFileReader(
                cache_folder=str(self.cache_dir),
                max_retries=2,
                initial_backoff=0.1
            )
            
            result = reader.read_json_file()
            
            # Restore permissions for cleanup
            os.chmod(self.state_file_path, stat.S_IRUSR | stat.S_IWUSR)
            
            assert result.success is False
            assert result.error_type == "PermissionError"
    
    def test_retry_with_exponential_backoff(self):
        """Test that retry logic uses exponential backoff."""
        reader = StateFileReader(
            cache_folder=str(self.cache_dir),
            max_retries=4,
            initial_backoff=0.1,
            max_backoff=1.0
        )
        
        start_time = time.time()
        result = reader.read_json_file()
        elapsed = time.time() - start_time
        
        # Should have waited: 0.1 + 0.2 + 0.4 = 0.7 seconds minimum (3 waits for 4 attempts)
        assert result.success is False
        assert elapsed >= 0.6  # At least some backoff occurred
        assert result.attempts == 4



@pytest.mark.slow
class TestFileWatching:
    """Tests for file watching and automatic state refresh."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "cache"
        self.cache_dir.mkdir(parents=True)
        self.state_file_path = self.cache_dir / "network_state.json"
        self.callback_called = False
        self.callback_state = None
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def _file_change_callback(self, state: NetworkState):
        """Callback for file changes."""
        self.callback_called = True
        self.callback_state = state
    
    def _create_valid_state_json(self) -> Dict[str, Any]:
        """Create a valid state JSON."""
        return {
            "timestamp": datetime.now().isoformat(),
            "topology": {
                "switches": [],
                "hosts": [],
                "links": []
            },
            "flows": [],
            "slices": [],
            "metrics": {
                "bandwidth": {
                    "total_capacity": 1000,
                    "used_bandwidth": 100,
                    "available_bandwidth": 900,
                    "utilization_percentage": 10.0
                },
                "latency": {
                    "average_latency": 5.0,
                    "min_latency": 1.0,
                    "max_latency": 10.0,
                    "jitter": 1.0
                },
                "utilization": {
                    "cpu_utilization": 20.0,
                    "memory_utilization": 30.0
                }
            },
            "anomalies": []
        }
    
    def test_file_watching_start_stop(self):
        """Test starting and stopping file watching."""
        # Create initial file
        with open(self.state_file_path, 'w') as f:
            json.dump(self._create_valid_state_json(), f)
        
        reader = StateFileReader(
            cache_folder=str(self.cache_dir),
            enable_file_watching=False,
            file_change_callback=self._file_change_callback
        )
        
        # Start watching
        assert reader.start_file_watching() is True
        assert reader.is_watching() is True
        
        # Stop watching
        assert reader.stop_file_watching() is True
        assert reader.is_watching() is False
    
    def test_file_watching_detects_changes(self):
        """Test that file watching detects file modifications."""
        # Create initial file
        with open(self.state_file_path, 'w') as f:
            json.dump(self._create_valid_state_json(), f)
        
        reader = StateFileReader(
            cache_folder=str(self.cache_dir),
            enable_file_watching=True,
            file_change_callback=self._file_change_callback
        )
        
        # Wait for watcher to initialize
        time.sleep(0.5)
        
        # Modify the file
        state_data = self._create_valid_state_json()
        state_data['metrics']['bandwidth']['used_bandwidth'] = 500
        
        with open(self.state_file_path, 'w') as f:
            json.dump(state_data, f)
        
        # Wait for file system event to be processed
        time.sleep(3.0)
        
        # Verify callback was called
        assert self.callback_called is True
        assert self.callback_state is not None
        assert self.callback_state.metrics.bandwidth.used_bandwidth == 500
        
        # Cleanup
        reader.stop_file_watching()
    
    def test_automatic_state_refresh_on_file_change(self):
        """Test automatic state refresh when file changes."""
        # Create initial file
        initial_state = self._create_valid_state_json()
        initial_state['metrics']['bandwidth']['used_bandwidth'] = 100
        
        with open(self.state_file_path, 'w') as f:
            json.dump(initial_state, f)
        
        states_received = []
        
        def callback(state):
            states_received.append(state)
        
        reader = StateFileReader(
            cache_folder=str(self.cache_dir),
            enable_file_watching=True,
            file_change_callback=callback
        )
        
        # Wait for initialization
        time.sleep(0.5)
        
        # Modify file multiple times
        for i in range(3):
            state_data = self._create_valid_state_json()
            state_data['metrics']['bandwidth']['used_bandwidth'] = 200 + (i * 100)
            
            with open(self.state_file_path, 'w') as f:
                json.dump(state_data, f)
            
            time.sleep(1.5)  # Wait for event processing
        
        # Verify multiple updates were received
        assert len(states_received) >= 2  # At least some updates
        
        # Cleanup
        reader.stop_file_watching()


class TestRateLimitingAndCostManagement:
    """Tests for API rate limiting and cost management."""
    
    @pytest.mark.asyncio
    async def test_rate_limiting_enforcement(self):
        """Test that rate limiting is enforced."""
        config = ChatGPTConfig(
            api_key="test-key",
            model="gpt-4-turbo",
            rate_limit_rpm=5,  # Low limit for testing
            timeout=10,
            max_retries=1
        )
        
        client = ChatGPTClient(config)
        
        # Mock the API call
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="test"), finish_reason="stop")]
            mock_response.usage = Mock(total_tokens=100, prompt_tokens=50, completion_tokens=50)
            mock_response.model = "gpt-4-turbo"
            mock_request.return_value = mock_response
            
            # Make requests up to the limit
            start_time = time.time()
            for i in range(6):
                try:
                    await client.generate_response(f"test prompt {i}")
                except Exception:
                    pass
            elapsed = time.time() - start_time
            
            # Should have been throttled
            rate_limit_info = client.get_rate_limit_status()
            assert rate_limit_info.remaining_requests <= 5
    
    @pytest.mark.asyncio
    async def test_budget_alert_warning_threshold(self):
        """Test that budget warning alerts are triggered."""
        config = ChatGPTConfig(
            api_key="test-key",
            model="gpt-4-turbo",
            budget_warning_threshold=0.05,  # Very low for testing
            budget_critical_threshold=0.10,
            timeout=10
        )
        
        client = ChatGPTClient(config)
        alerts_received = []
        
        def alert_callback(alert: BudgetAlert):
            alerts_received.append(alert)
        
        client.register_alert_callback(alert_callback)
        
        # Mock API call with token usage
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="test"), finish_reason="stop")]
            mock_response.usage = Mock(total_tokens=5000, prompt_tokens=2500, completion_tokens=2500)
            mock_response.model = "gpt-4-turbo"
            mock_request.return_value = mock_response
            
            # Make request that should trigger warning
            await client.generate_response("test prompt")
            
            # Check that warning alert was triggered
            assert len(alerts_received) >= 1
            assert alerts_received[0].alert_type == "warning"
            assert alerts_received[0].current_cost >= config.budget_warning_threshold
    
    @pytest.mark.asyncio
    async def test_budget_alert_critical_threshold(self):
        """Test that budget critical alerts are triggered."""
        config = ChatGPTConfig(
            api_key="test-key",
            model="gpt-4-turbo",
            budget_warning_threshold=0.05,
            budget_critical_threshold=0.10,
            timeout=10
        )
        
        client = ChatGPTClient(config)
        alerts_received = []
        
        def alert_callback(alert: BudgetAlert):
            alerts_received.append(alert)
        
        client.register_alert_callback(alert_callback)
        
        # Mock API call with high token usage
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="test"), finish_reason="stop")]
            mock_response.usage = Mock(total_tokens=10000, prompt_tokens=5000, completion_tokens=5000)
            mock_response.model = "gpt-4-turbo"
            mock_request.return_value = mock_response
            
            # Make requests that should trigger both warning and critical
            await client.generate_response("test prompt 1")
            await client.generate_response("test prompt 2")
            
            # Check that both alerts were triggered
            assert len(alerts_received) >= 2
            alert_types = [alert.alert_type for alert in alerts_received]
            assert "warning" in alert_types
            assert "critical" in alert_types
    
    @pytest.mark.asyncio
    async def test_request_queue_management(self):
        """Test request queue for rate limit management."""
        config = ChatGPTConfig(
            api_key="test-key",
            model="gpt-4-turbo",
            rate_limit_rpm=10,
            max_queue_size=20,
            timeout=10
        )
        
        client = ChatGPTClient(config)
        
        # Mock API call
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="test"), finish_reason="stop")]
            mock_response.usage = Mock(total_tokens=100, prompt_tokens=50, completion_tokens=50)
            mock_response.model = "gpt-4-turbo"
            mock_request.return_value = mock_response
            
            # Enqueue multiple requests
            tasks = []
            for i in range(5):
                task = asyncio.create_task(
                    client.enqueue_request(f"test prompt {i}", priority=i)
                )
                tasks.append(task)
            
            # Wait for all to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Verify all completed
            assert len(results) == 5
            for result in results:
                if not isinstance(result, Exception):
                    assert result.content == "test"



class TestLoadAndPerformance:
    """Load testing and performance validation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "cache"
        self.cache_dir.mkdir(parents=True)
        self.state_file_path = self.cache_dir / "network_state.json"
        self.parser = IntentParser()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def _create_large_network_state(self, num_switches: int = 100) -> Dict[str, Any]:
        """Create a large network state for load testing."""
        switches = []
        hosts = []
        links = []
        
        for i in range(num_switches):
            switches.append({
                "id": f"sw{i}",
                "name": f"switch{i}",
                "dpid": f"{i:016x}",
                "ports": list(range(1, 11)),
                "status": "active"
            })
            
            # Add 2 hosts per switch
            for j in range(2):
                host_id = i * 2 + j
                hosts.append({
                    "id": f"h{host_id}",
                    "mac_address": f"00:00:00:00:{i:02x}:{j:02x}",
                    "ip_address": f"10.{i // 256}.{i % 256}.{j + 1}",
                    "connected_switch": f"sw{i}",
                    "connected_port": j + 1,
                    "status": "active"
                })
            
            # Add links between adjacent switches
            if i > 0:
                links.append({
                    "id": f"link{i}",
                    "source_switch": f"sw{i-1}",
                    "source_port": 10,
                    "destination_switch": f"sw{i}",
                    "destination_port": 10,
                    "bandwidth": 1000,
                    "status": "active"
                })
        
        return {
            "timestamp": datetime.now().isoformat(),
            "topology": {
                "switches": switches,
                "hosts": hosts,
                "links": links
            },
            "flows": [],
            "slices": [],
            "metrics": {
                "bandwidth": {
                    "total_capacity": num_switches * 1000,
                    "used_bandwidth": num_switches * 200,
                    "available_bandwidth": num_switches * 800,
                    "utilization_percentage": 20.0
                },
                "latency": {
                    "average_latency": 5.0,
                    "min_latency": 1.0,
                    "max_latency": 10.0,
                    "jitter": 1.5
                },
                "utilization": {
                    "cpu_utilization": 30.0,
                    "memory_utilization": 40.0
                }
            },
            "anomalies": []
        }
    
    def test_load_large_network_state(self):
        """Test loading a large network state."""
        # Create large state (100 switches, 200 hosts, 99 links)
        large_state = self._create_large_network_state(100)
        
        with open(self.state_file_path, 'w') as f:
            json.dump(large_state, f)
        
        reader = StateFileReader(cache_folder=str(self.cache_dir))
        
        start_time = time.time()
        network_state = reader.load_network_state()
        load_time = time.time() - start_time
        
        assert network_state is not None
        assert len(network_state.topology.switches) == 100
        assert len(network_state.topology.hosts) == 200
        assert len(network_state.topology.links) == 99
        
        # Should load in reasonable time (< 2 seconds)
        assert load_time < 2.0, f"Load time {load_time:.2f}s exceeds threshold"
    
    def test_multiple_concurrent_intent_processing(self):
        """Test processing multiple intents concurrently."""
        # Create state
        state_data = self._create_large_network_state(50)
        with open(self.state_file_path, 'w') as f:
            json.dump(state_data, f)
        
        reader = StateFileReader(cache_folder=str(self.cache_dir))
        network_state = reader.load_network_state()
        
        # Create multiple intents
        intents = [
            f"configure switch sw{i} with bandwidth 500mbps"
            for i in range(20)
        ]
        
        start_time = time.time()
        results = []
        
        for intent_text in intents:
            result = self.parser.analyze_and_clarify_intent(intent_text, network_state)
            results.append(result)
        
        processing_time = time.time() - start_time
        
        # Verify all processed
        assert len(results) == 20
        for result in results:
            assert result['intent'] is not None
        
        # Average processing time should be reasonable
        avg_time = processing_time / len(intents)
        assert avg_time < 1.0, f"Average processing time {avg_time:.2f}s is too high"
    
    def test_file_read_performance_with_retries(self):
        """Test file read performance with retry scenarios."""
        reader = StateFileReader(
            cache_folder=str(self.cache_dir),
            max_retries=5,
            initial_backoff=0.05,
            max_backoff=0.5
        )
        
        # Test with missing file (will retry)
        start_time = time.time()
        result = reader.read_json_file()
        retry_time = time.time() - start_time
        
        assert result.success is False
        assert result.attempts == 5
        
        # Should complete retries in reasonable time
        # Expected: 0.05 + 0.1 + 0.2 + 0.4 = 0.75s minimum (4 waits for 5 attempts)
        assert retry_time >= 0.6
        assert retry_time < 3.0  # But not too long
    
    def test_action_output_performance(self):
        """Test action output performance with many actions."""
        output_dir = Path(self.temp_dir) / "output"
        output_interface = ActionOutputInterface(
            output_directory=str(output_dir / "actions"),
            log_directory=str(output_dir / "logs")
        )
        
        # Create sequence with many actions
        actions = []
        for i in range(50):
            action = NetworkAction(
                id=f"action-{i}",
                type=ActionType.CONFIG_CHANGE,
                target=f"sw{i}",
                parameters={"bandwidth": 500 + i},
                priority=100 + i,
                timeout=30
            )
            actions.append(action)
        
        sequence = ActionSequence(
            id="seq-load-test",
            intent_id="intent-load-test",
            actions=actions,
            estimated_duration=1500
        )
        
        from llm_integration_module.models.actions import ValidationResult, SafetyReport
        validation = ValidationResult(is_valid=True, errors=[], warnings=[])
        safety = SafetyReport(is_safe=True, risk_level="low", risks=[])
        
        start_time = time.time()
        result = output_interface.output_actions(
            sequence=sequence,
            validation_result=validation,
            safety_report=safety
        )
        output_time = time.time() - start_time
        
        assert result['success'] is True
        assert result['file_path'] is not None
        
        # Should output in reasonable time
        assert output_time < 2.0, f"Output time {output_time:.2f}s exceeds threshold"



class TestSystemResilience:
    """Tests for overall system resilience and error recovery."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "cache"
        self.cache_dir.mkdir(parents=True)
        self.state_file_path = self.cache_dir / "network_state.json"
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def test_recovery_from_corrupted_to_valid_state(self):
        """Test system recovery when file changes from corrupted to valid."""
        # Start with corrupted file
        with open(self.state_file_path, 'w') as f:
            f.write('invalid json {')
        
        reader = StateFileReader(
            cache_folder=str(self.cache_dir),
            max_retries=2,
            initial_backoff=0.1
        )
        
        # First attempt should fail
        result1 = reader.read_json_file()
        assert result1.success is False
        
        # Fix the file
        valid_state = {
            "timestamp": datetime.now().isoformat(),
            "topology": {"switches": [], "hosts": [], "links": []},
            "flows": [],
            "slices": [],
            "metrics": {
                "bandwidth": {
                    "total_capacity": 1000,
                    "used_bandwidth": 100,
                    "available_bandwidth": 900,
                    "utilization_percentage": 10.0
                },
                "latency": {
                    "average_latency": 5.0,
                    "min_latency": 1.0,
                    "max_latency": 10.0,
                    "jitter": 1.0
                },
                "utilization": {
                    "cpu_utilization": 20.0,
                    "memory_utilization": 30.0
                }
            },
            "anomalies": []
        }
        
        with open(self.state_file_path, 'w') as f:
            json.dump(valid_state, f)
        
        # Second attempt should succeed
        result2 = reader.read_json_file()
        assert result2.success is True
        assert result2.data is not None
    
    def test_graceful_degradation_with_partial_data(self):
        """Test graceful handling of partial/incomplete data."""
        # Create state with minimal required fields
        minimal_state = {
            "timestamp": datetime.now().isoformat(),
            "topology": {
                "switches": [],
                "hosts": [],
                "links": []
            },
            "flows": [],
            "metrics": {
                "bandwidth": {
                    "total_capacity": 1000,
                    "used_bandwidth": 0,
                    "available_bandwidth": 1000,
                    "utilization_percentage": 0.0
                },
                "latency": {
                    "average_latency": 0.0,
                    "min_latency": 0.0,
                    "max_latency": 0.0,
                    "jitter": 0.0
                },
                "utilization": {
                    "cpu_utilization": 0.0,
                    "memory_utilization": 0.0
                }
            }
        }
        
        with open(self.state_file_path, 'w') as f:
            json.dump(minimal_state, f)
        
        reader = StateFileReader(cache_folder=str(self.cache_dir))
        network_state = reader.load_network_state()
        
        # Should load successfully even with minimal data
        assert network_state is not None
        assert len(network_state.topology.switches) == 0
        assert network_state.metrics.bandwidth.total_capacity == 1000
    
    @pytest.mark.asyncio
    async def test_api_failure_and_recovery(self):
        """Test system behavior during API failures and recovery."""
        config = ChatGPTConfig(
            api_key="test-key",
            model="gpt-4-turbo",
            timeout=10,
            max_retries=3
        )
        
        client = ChatGPTClient(config)
        
        # Simulate API failures followed by success
        call_count = [0]
        
        async def mock_request_with_failures(messages):
            call_count[0] += 1
            if call_count[0] < 3:
                # First 2 calls fail
                from openai import APIConnectionError
                raise APIConnectionError(request=None)
            else:
                # Third call succeeds
                mock_response = Mock()
                mock_response.choices = [Mock(message=Mock(content="recovered"), finish_reason="stop")]
                mock_response.usage = Mock(total_tokens=100, prompt_tokens=50, completion_tokens=50)
                mock_response.model = "gpt-4-turbo"
                return mock_response
        
        with patch.object(client, '_make_request', side_effect=mock_request_with_failures):
            response = await client.generate_response("test prompt")
            
            assert response.content == "recovered"
            assert call_count[0] == 3  # Should have retried
    
    def test_concurrent_file_access(self):
        """Test concurrent file access from multiple readers."""
        # Create valid state file
        state_data = {
            "timestamp": datetime.now().isoformat(),
            "topology": {"switches": [], "hosts": [], "links": []},
            "flows": [],
            "slices": [],
            "metrics": {
                "bandwidth": {
                    "total_capacity": 1000,
                    "used_bandwidth": 100,
                    "available_bandwidth": 900,
                    "utilization_percentage": 10.0
                },
                "latency": {
                    "average_latency": 5.0,
                    "min_latency": 1.0,
                    "max_latency": 10.0,
                    "jitter": 1.0
                },
                "utilization": {
                    "cpu_utilization": 20.0,
                    "memory_utilization": 30.0
                }
            },
            "anomalies": []
        }
        
        with open(self.state_file_path, 'w') as f:
            json.dump(state_data, f)
        
        results = []
        
        def read_state():
            reader = StateFileReader(cache_folder=str(self.cache_dir))
            result = reader.load_network_state()
            results.append(result is not None)
        
        # Create multiple threads reading concurrently
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=read_state)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # All reads should succeed
        assert len(results) == 10
        assert all(results)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
