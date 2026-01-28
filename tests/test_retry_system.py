"""
Tests for the Advanced Retry System
"""

import pytest
import time
import tempfile
import os
from unittest.mock import Mock, patch
from datetime import datetime

from src.core.retry_system import (
    AdvancedRetrySystem, RetryConfig, RetryStrategy,
    CircuitBreaker, PersistentActionQueue, CircuitBreakerState
)
from src.models.action_models import NetworkAction, ActionType


class TestRetryConfig:
    """Test retry configuration."""
    
    def test_default_config(self):
        """Test default retry configuration."""
        config = RetryConfig()
        
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF
        assert config.backoff_multiplier == 2.0
        assert config.jitter is True
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 60.0
        assert config.enable_persistent_queue is True
    
    def test_custom_config(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=2.0,
            strategy=RetryStrategy.LINEAR_BACKOFF,
            failure_threshold=3
        )
        
        assert config.max_attempts == 5
        assert config.base_delay == 2.0
        assert config.strategy == RetryStrategy.LINEAR_BACKOFF
        assert config.failure_threshold == 3


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    def test_initial_state(self):
        """Test circuit breaker initial state."""
        config = RetryConfig(failure_threshold=3)
        cb = CircuitBreaker("test_service", config)
        
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.can_execute() is True
        assert cb.failure_count == 0
        assert cb.success_count == 0
    
    def test_failure_threshold(self):
        """Test circuit breaker opens after failure threshold."""
        config = RetryConfig(failure_threshold=3)
        cb = CircuitBreaker("test_service", config)
        
        # Record failures up to threshold
        for i in range(3):
            cb.record_failure()
            if i < 2:
                assert cb.state == CircuitBreakerState.CLOSED
            else:
                assert cb.state == CircuitBreakerState.OPEN
        
        assert cb.can_execute() is False
    
    def test_success_resets_failures(self):
        """Test that success resets failure count in closed state."""
        config = RetryConfig(failure_threshold=3)
        cb = CircuitBreaker("test_service", config)
        
        # Record some failures
        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2
        
        # Record success
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == CircuitBreakerState.CLOSED
    
    def test_half_open_transition(self):
        """Test transition to half-open state after recovery timeout."""
        config = RetryConfig(failure_threshold=2, recovery_timeout=0.1)
        cb = CircuitBreaker("test_service", config)
        
        # Trigger circuit breaker to open
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        
        # Wait for recovery timeout
        time.sleep(0.2)
        
        # Should allow execution and transition to half-open
        assert cb.can_execute() is True
        assert cb.state == CircuitBreakerState.HALF_OPEN
    
    def test_half_open_to_closed(self):
        """Test transition from half-open to closed after successes."""
        config = RetryConfig(failure_threshold=2, success_threshold=2, recovery_timeout=0.1)
        cb = CircuitBreaker("test_service", config)
        
        # Open circuit breaker
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        
        # Wait and transition to half-open
        time.sleep(0.2)
        cb.can_execute()
        assert cb.state == CircuitBreakerState.HALF_OPEN
        
        # Record successes to close circuit
        cb.record_success()
        assert cb.state == CircuitBreakerState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitBreakerState.CLOSED
    
    def test_stats(self):
        """Test circuit breaker statistics."""
        config = RetryConfig()
        cb = CircuitBreaker("test_service", config)
        
        cb.record_success()
        cb.record_failure()
        cb.record_success()
        
        stats = cb.get_stats()
        
        assert stats["name"] == "test_service"
        assert stats["total_calls"] == 3
        assert stats["total_successes"] == 2
        assert stats["total_failures"] == 1
        assert stats["success_rate"] == pytest.approx(66.67, rel=1e-2)


class TestPersistentActionQueue:
    """Test persistent action queue functionality."""
    
    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = RetryConfig(
            queue_persistence_path=os.path.join(self.temp_dir, "test_queue.db"),
            queue_max_size=10
        )
        self.queue = PersistentActionQueue(self.config)
    
    def teardown_method(self):
        """Cleanup test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_enqueue_dequeue(self):
        """Test basic enqueue and dequeue operations."""
        action = NetworkAction(
            id="test_action_1",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={"match": {"in_port": 1}, "actions": ["output:2"]}
        )
        
        # Enqueue action
        success = self.queue.enqueue(action)
        assert success is True
        
        # Dequeue action
        queue_item = self.queue.dequeue(timeout=1.0)
        assert queue_item is not None
        assert queue_item["action"].id == "test_action_1"
        assert queue_item["action"].type == ActionType.FLOW_MOD
        assert queue_item["retry_count"] == 0
    
    def test_queue_persistence(self):
        """Test that queue persists across instances."""
        action = NetworkAction(
            id="persistent_action",
            type=ActionType.CONFIG_CHANGE,
            target="switch-2",
            parameters={"config_type": "qos"}
        )
        
        # Enqueue in first instance
        self.queue.enqueue(action)
        
        # Create new queue instance with same database
        new_queue = PersistentActionQueue(self.config)
        
        # Should be able to dequeue from new instance
        queue_item = new_queue.dequeue(timeout=1.0)
        assert queue_item is not None
        assert queue_item["action"].id == "persistent_action"
    
    def test_mark_completed(self):
        """Test marking actions as completed."""
        action = NetworkAction(
            id="completed_action",
            type=ActionType.FLOW_MOD,
            target="switch-3"
        )
        
        self.queue.enqueue(action)
        queue_item = self.queue.dequeue(timeout=1.0)
        
        # Mark as completed
        success = self.queue.mark_completed(queue_item["id"])
        assert success is True
        
        # Should not be dequeued again
        next_item = self.queue.dequeue(timeout=0.1)
        assert next_item is None
    
    def test_mark_failed(self):
        """Test marking actions as failed."""
        action = NetworkAction(
            id="failed_action",
            type=ActionType.FLOW_MOD,
            target="switch-4"
        )
        
        self.queue.enqueue(action)
        queue_item = self.queue.dequeue(timeout=1.0)
        
        # Mark as failed
        success = self.queue.mark_failed(queue_item["id"])
        assert success is True
        
        # Check stats
        stats = self.queue.get_stats()
        assert stats["total_failed"] == 1
    
    def test_stats(self):
        """Test queue statistics."""
        # Enqueue some actions
        for i in range(3):
            action = NetworkAction(
                id=f"stats_action_{i}",
                type=ActionType.FLOW_MOD,
                target=f"switch-{i}"
            )
            self.queue.enqueue(action)
        
        stats = self.queue.get_stats()
        
        assert stats["total_enqueued"] == 3
        assert stats["current_size"] >= 0  # May vary due to memory queue
        assert stats["database_pending"] >= 0


class TestAdvancedRetrySystem:
    """Test advanced retry system functionality."""
    
    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = RetryConfig(
            max_attempts=3,
            base_delay=0.1,  # Short delay for tests
            max_delay=1.0,
            queue_persistence_path=os.path.join(self.temp_dir, "retry_test.db")
        )
        self.retry_system = AdvancedRetrySystem(self.config)
    
    def teardown_method(self):
        """Cleanup test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_successful_operation(self):
        """Test successful operation without retries."""
        def successful_operation():
            return "success"
        
        result = self.retry_system.execute_with_retry(
            successful_operation,
            service_name="test_service"
        )
        
        assert result.success is True
        assert result.result == "success"
        assert len(result.attempts) == 1
        assert result.attempts[0].success is True
    
    def test_operation_with_retries(self):
        """Test operation that succeeds after retries."""
        call_count = 0
        
        def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = self.retry_system.execute_with_retry(
            failing_then_success,
            service_name="test_service"
        )
        
        assert result.success is True
        assert result.result == "success"
        assert len(result.attempts) == 3
        assert result.attempts[0].success is False
        assert result.attempts[1].success is False
        assert result.attempts[2].success is True
    
    def test_operation_max_retries_exceeded(self):
        """Test operation that fails after max retries."""
        def always_failing():
            raise Exception("Persistent failure")
        
        result = self.retry_system.execute_with_retry(
            always_failing,
            service_name="test_service"
        )
        
        assert result.success is False
        assert "Persistent failure" in result.error
        assert len(result.attempts) == 3  # max_attempts
        assert all(not attempt.success for attempt in result.attempts)
    
    def test_circuit_breaker_integration(self):
        """Test circuit breaker integration with retry system."""
        # First, trigger circuit breaker to open
        def always_failing():
            raise Exception("Service unavailable")
        
        # Execute multiple failing operations to open circuit breaker
        for _ in range(6):  # More than failure_threshold (5)
            self.retry_system.execute_with_retry(
                always_failing,
                service_name="circuit_test"
            )
        
        # Next operation should be rejected by circuit breaker
        result = self.retry_system.execute_with_retry(
            always_failing,
            service_name="circuit_test"
        )
        
        assert result.success is False
        assert result.circuit_breaker_triggered is True
        assert "Circuit breaker" in result.error
    
    def test_delay_calculation(self):
        """Test different delay calculation strategies."""
        # Test exponential backoff
        self.retry_system.config.strategy = RetryStrategy.EXPONENTIAL_BACKOFF
        self.retry_system.config.base_delay = 1.0
        self.retry_system.config.backoff_multiplier = 2.0
        self.retry_system.config.jitter = False
        
        assert self.retry_system.calculate_delay(1) == 1.0
        assert self.retry_system.calculate_delay(2) == 2.0
        assert self.retry_system.calculate_delay(3) == 4.0
        
        # Test linear backoff
        self.retry_system.config.strategy = RetryStrategy.LINEAR_BACKOFF
        assert self.retry_system.calculate_delay(1) == 1.0
        assert self.retry_system.calculate_delay(2) == 2.0
        assert self.retry_system.calculate_delay(3) == 3.0
        
        # Test fixed delay
        self.retry_system.config.strategy = RetryStrategy.FIXED_DELAY
        assert self.retry_system.calculate_delay(1) == 1.0
        assert self.retry_system.calculate_delay(2) == 1.0
        assert self.retry_system.calculate_delay(3) == 1.0
    
    def test_queue_action_for_retry(self):
        """Test queuing actions for later retry."""
        action = NetworkAction(
            id="queued_action",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={"match": {"in_port": 1}}
        )
        
        success = self.retry_system.queue_action_for_retry(action, max_retries=5)
        assert success is True
        
        # Verify action is in queue
        stats = self.retry_system.get_system_stats()
        assert stats["retry_system"]["queue_operations"] == 1
    
    def test_process_queued_actions(self):
        """Test processing queued actions."""
        # Queue some actions
        actions = []
        for i in range(3):
            action = NetworkAction(
                id=f"process_action_{i}",
                type=ActionType.FLOW_MOD,
                target=f"switch-{i}"
            )
            actions.append(action)
            self.retry_system.queue_action_for_retry(action)
        
        # Mock processor that succeeds for all actions
        def mock_processor(action):
            return True
        
        result = self.retry_system.process_queued_actions(
            mock_processor,
            service_name="test_service",
            max_actions=5
        )
        
        assert result["processed"] == 3
        assert result["successful"] == 3
        assert result["failed"] == 0
        assert result["requeued"] == 0
    
    def test_system_stats(self):
        """Test comprehensive system statistics."""
        # Execute some operations
        def test_operation():
            return "test"
        
        self.retry_system.execute_with_retry(test_operation, "service1")
        self.retry_system.execute_with_retry(test_operation, "service2")
        
        stats = self.retry_system.get_system_stats()
        
        assert "retry_system" in stats
        assert "circuit_breakers" in stats
        assert "persistent_queue" in stats
        assert "config" in stats
        
        assert stats["retry_system"]["total_operations"] == 2
        assert stats["retry_system"]["successful_operations"] == 2
        assert len(stats["circuit_breakers"]) == 2  # service1 and service2


if __name__ == "__main__":
    pytest.main([__file__])