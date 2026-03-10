"""
Test suite for necessary_scripts modules
Verifies core functionality without external dependencies
"""

import sys
import os
import json
import tempfile
from pathlib import Path

# Add necessary_scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'necessary_scripts'))

import pytest
from models import NetworkAction, ActionType
from retry_system import SimpleRetrySystem, RetryConfig, RetryStrategy
from config_loader import ConfigLoader, SystemConfig
from history_manager import HistoryManager, ExecutionRecord
from comnetsemu_connector import ComnetsEMUConnector, ComnetsEMUConfig
from action_processor import ActionProcessor, ExecutionStatus


class TestModels:
    """Test data models."""
    
    def test_network_action_creation(self):
        """Test creating a valid NetworkAction."""
        action = NetworkAction(
            id="test-action-1",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={"operation": "add", "match": {}, "actions": []},
            priority=1000,
            timeout=30
        )
        
        assert action.id == "test-action-1"
        assert action.type == ActionType.FLOW_MOD
        assert action.target == "switch-1"
        assert action.priority == 1000
    
    def test_network_action_validation(self):
        """Test action parameter validation."""
        action = NetworkAction(
            id="test-action-2",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={"operation": "add", "match": {}, "actions": []},
            priority=1000,
            timeout=30
        )
        
        validation = action.validate_action_parameters()
        assert validation["is_valid"] == True
    
    def test_invalid_action_id(self):
        """Test that invalid action IDs are rejected."""
        with pytest.raises(ValueError):
            NetworkAction(
                id="invalid id with spaces",
                type=ActionType.FLOW_MOD,
                target="switch-1",
                parameters={},
                priority=1000,
                timeout=30
            )
    
    def test_invalid_priority(self):
        """Test that invalid priorities are rejected."""
        with pytest.raises(ValueError):
            NetworkAction(
                id="test-action",
                type=ActionType.FLOW_MOD,
                target="switch-1",
                parameters={},
                priority=70000,  # Too high
                timeout=30
            )


class TestRetrySystem:
    """Test retry system functionality."""
    
    def test_retry_success_first_attempt(self):
        """Test successful operation on first attempt."""
        config = RetryConfig(max_attempts=3, base_delay=0.1)
        retry_system = SimpleRetrySystem(config)
        
        def successful_operation():
            return "success"
        
        result = retry_system.execute_with_retry(successful_operation)
        
        assert result.success == True
        assert result.result == "success"
        assert len(result.attempts) == 1
    
    def test_retry_with_failures(self):
        """Test retry logic with initial failures."""
        config = RetryConfig(max_attempts=3, base_delay=0.1)
        retry_system = SimpleRetrySystem(config)
        
        attempt_count = [0]
        
        def failing_then_success():
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = retry_system.execute_with_retry(failing_then_success)
        
        assert result.success == True
        assert result.result == "success"
        assert len(result.attempts) == 3
    
    def test_retry_max_attempts_exceeded(self):
        """Test that max attempts limit is respected."""
        config = RetryConfig(max_attempts=3, base_delay=0.1)
        retry_system = SimpleRetrySystem(config)
        
        def always_fails():
            raise Exception("Always fails")
        
        result = retry_system.execute_with_retry(always_fails)
        
        assert result.success == False
        assert len(result.attempts) == 3
    
    def test_exponential_backoff(self):
        """Test exponential backoff delay calculation."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=1.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            backoff_multiplier=2.0,
            jitter=False
        )
        retry_system = SimpleRetrySystem(config)
        
        # Test delay calculation
        delay1 = retry_system.calculate_delay(1)
        delay2 = retry_system.calculate_delay(2)
        delay3 = retry_system.calculate_delay(3)
        
        assert delay1 == 1.0
        assert delay2 == 2.0
        assert delay3 == 4.0


class TestConfigLoader:
    """Test configuration loader."""
    
    def test_load_config_from_yaml(self):
        """Test loading configuration from YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
comnetsemu_host: testhost
comnetsemu_port: 6653
max_retries: 5
retry_delay: 3.0
timeout_seconds: 60
log_level: DEBUG
history_dir: test/history
actions_file: test/actions.jsonl
""")
            config_path = f.name
        
        try:
            loader = ConfigLoader(config_path)
            config = loader.load()
            
            assert config.comnetsemu_host == "testhost"
            assert config.comnetsemu_port == 6653
            assert config.max_retries == 5
            assert config.retry_delay == 3.0
            assert config.log_level == "DEBUG"
        finally:
            os.unlink(config_path)
    
    def test_config_validation(self):
        """Test configuration validation."""
        loader = ConfigLoader()
        
        # Valid config
        valid_config = SystemConfig(
            comnetsemu_host="localhost",
            comnetsemu_port=6653,
            max_retries=3,
            retry_delay=2.0
        )
        
        validation = loader.validate(valid_config)
        assert validation["is_valid"] == True
        
        # Invalid config (bad port)
        invalid_config = SystemConfig(
            comnetsemu_host="localhost",
            comnetsemu_port=99999,  # Invalid port
            max_retries=3,
            retry_delay=2.0
        )
        
        validation = loader.validate(invalid_config)
        assert validation["is_valid"] == False
        assert len(validation["errors"]) > 0


class TestHistoryManager:
    """Test history manager functionality."""
    
    def test_save_and_retrieve_result(self):
        """Test saving and retrieving execution results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            history_manager = HistoryManager(tmpdir)
            
            record = ExecutionRecord(
                action_id="test-action-1",
                status="success",
                timestamp="2024-01-27T10:00:00",
                duration=2.5,
                message="Test completed",
                target="switch-1",
                action_type="flow_mod"
            )
            
            # Save result
            filepath = history_manager.save_result(record)
            assert os.path.exists(filepath)
            
            # Retrieve recent results
            recent = history_manager.get_recent_results(limit=10)
            assert len(recent) == 1
            assert recent[0]["action_id"] == "test-action-1"
    
    def test_get_statistics(self):
        """Test statistics calculation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            history_manager = HistoryManager(tmpdir)
            
            # Save multiple results
            for i in range(5):
                record = ExecutionRecord(
                    action_id=f"action-{i}",
                    status="success" if i < 3 else "failed",
                    timestamp="2024-01-27T10:00:00",
                    duration=1.0,
                    message="Test",
                    target="switch-1",
                    action_type="flow_mod"
                )
                history_manager.save_result(record)
            
            stats = history_manager.get_statistics()
            assert stats["total_results"] == 5
            assert stats["successful"] == 3
            assert stats["failed"] == 2


class TestComnetsEMUConnector:
    """Test ComnetsEMU connector."""
    
    def test_connector_initialization(self):
        """Test connector initialization."""
        config = ComnetsEMUConfig(
            host="localhost",
            port=6653,
            timeout_seconds=30,
            max_retries=3
        )
        
        connector = ComnetsEMUConnector(config)
        
        assert connector.config.host == "localhost"
        assert connector.config.port == 6653
    
    def test_get_network_state(self):
        """Test getting network state."""
        config = ComnetsEMUConfig(host="localhost", port=6653)
        connector = ComnetsEMUConnector(config)
        
        state = connector.get_network_state("switch-1")
        
        assert "target" in state
        assert state["target"] == "switch-1"
        assert "status" in state
    
    def test_connection_status(self):
        """Test getting connection status."""
        config = ComnetsEMUConfig(host="localhost", port=6653)
        connector = ComnetsEMUConnector(config)
        
        status = connector.get_connection_status()
        
        assert "status" in status
        assert "config" in status
        assert "stats" in status


class TestActionProcessor:
    """Test action processor."""
    
    def test_action_validation(self):
        """Test action validation."""
        config = {
            "comnetsemu_host": "localhost",
            "comnetsemu_port": 6653,
            "max_retries": 3,
            "retry_delay": 2.0,
            "timeout_seconds": 30
        }
        
        processor = ActionProcessor(config)
        
        action = NetworkAction(
            id="test-action",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={"operation": "add", "match": {}, "actions": []},
            priority=1000,
            timeout=30
        )
        
        validation = processor.validate_action(action)
        assert validation["is_valid"] == True
    
    def test_execute_action(self):
        """Test action execution."""
        config = {
            "comnetsemu_host": "localhost",
            "comnetsemu_port": 6653,
            "max_retries": 3,
            "retry_delay": 0.1,
            "timeout_seconds": 30
        }
        
        processor = ActionProcessor(config)
        
        action = NetworkAction(
            id="test-action",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={"operation": "add", "match": {}, "actions": []},
            priority=1000,
            timeout=30
        )
        
        result = processor.execute_action(action)
        
        assert result.action_id == "test-action"
        assert result.status in [ExecutionStatus.SUCCESS, ExecutionStatus.FAILED]
        assert result.duration >= 0


class TestIntegration:
    """Integration tests for complete workflow."""
    
    def test_complete_workflow(self):
        """Test complete action processing workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup
            config = {
                "comnetsemu_host": "localhost",
                "comnetsemu_port": 6653,
                "max_retries": 3,
                "retry_delay": 0.1,
                "timeout_seconds": 30
            }
            
            processor = ActionProcessor(config)
            history_manager = HistoryManager(tmpdir)
            
            # Create action
            action = NetworkAction(
                id="integration-test-1",
                type=ActionType.CONFIG_CHANGE,
                target="switch-1",
                parameters={"config_type": "qos", "bandwidth": 100},
                priority=1000,
                timeout=30
            )
            
            # Execute action
            result = processor.execute_action(action)
            
            # Save to history
            record = ExecutionRecord(
                action_id=result.action_id,
                status=result.status.value,
                timestamp=result.timestamp.isoformat(),
                duration=result.duration,
                message=result.message,
                target=action.target,
                action_type=action.type.value,
                error=result.error
            )
            
            history_manager.save_result(record)
            
            # Verify
            recent = history_manager.get_recent_results(limit=1)
            assert len(recent) == 1
            assert recent[0]["action_id"] == "integration-test-1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
