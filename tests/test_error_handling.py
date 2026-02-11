"""Unit tests for error handling module."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import json

from src.utils.error_handling import (
    ErrorClassifier,
    ErrorCategory,
    ErrorSeverity,
    RecoveryStrategy,
    CircuitBreaker,
    CircuitBreakerOpenError,
    DegradedModeManager,
    RetryHandler,
    get_error_classifier,
    get_degraded_mode_manager,
    handle_errors
)


class TestErrorClassifier:
    """Test error classification."""
    
    def test_classify_rate_limit_error(self):
        """Test classification of rate limit errors."""
        classifier = ErrorClassifier()
        
        # Create a custom rate limit error class
        class RateLimitError(Exception):
            pass
        
        error = RateLimitError("Rate limit exceeded")
        
        context = classifier.classify(error, component="api", operation="request")
        
        assert context.category == ErrorCategory.RATE_LIMIT_ERROR
        assert context.severity == ErrorSeverity.MEDIUM
        assert context.recovery_strategy == RecoveryStrategy.RETRY
        assert context.component == "api"
        assert context.operation == "request"
    
    def test_classify_file_not_found_error(self):
        """Test classification of file not found errors."""
        classifier = ErrorClassifier()
        
        error = FileNotFoundError("File not found")
        context = classifier.classify(error)
        
        assert context.category == ErrorCategory.FILE_ERROR
        assert context.severity == ErrorSeverity.HIGH
        assert context.recovery_strategy == RecoveryStrategy.RETRY
    
    def test_classify_json_decode_error(self):
        """Test classification of JSON decode errors."""
        classifier = ErrorClassifier()
        
        try:
            json.loads("invalid json")
        except json.JSONDecodeError as e:
            context = classifier.classify(e)
            
            assert context.category == ErrorCategory.PARSING_ERROR
            assert context.severity == ErrorSeverity.HIGH
            assert context.recovery_strategy == RecoveryStrategy.RETRY
    
    def test_classify_unknown_error(self):
        """Test classification of unknown errors."""
        classifier = ErrorClassifier()
        
        error = RuntimeError("Unknown error")
        context = classifier.classify(error)
        
        assert context.category == ErrorCategory.UNKNOWN_ERROR
        assert context.severity == ErrorSeverity.MEDIUM
        assert context.recovery_strategy == RecoveryStrategy.RETRY
    
    def test_add_classification_rule(self):
        """Test adding custom classification rules."""
        classifier = ErrorClassifier()
        
        classifier.add_classification_rule(
            "CustomError",
            ErrorCategory.API_ERROR,
            ErrorSeverity.LOW,
            RecoveryStrategy.IGNORE
        )
        
        # Create a custom error class
        class CustomError(Exception):
            pass
        
        error = CustomError("Custom error")
        
        context = classifier.classify(error)
        
        assert context.category == ErrorCategory.API_ERROR
        assert context.severity == ErrorSeverity.LOW
        assert context.recovery_strategy == RecoveryStrategy.IGNORE


class TestCircuitBreaker:
    """Test circuit breaker pattern."""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state."""
        breaker = CircuitBreaker("test", failure_threshold=3)
        
        async def success_func():
            return "success"
        
        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state.state == "closed"
        assert breaker.state.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures."""
        breaker = CircuitBreaker("test", failure_threshold=3, timeout=1.0)
        
        async def failing_func():
            raise Exception("Test failure")
        
        # Trigger failures to open circuit
        for i in range(3):
            with pytest.raises(Exception):
                await breaker.call(failing_func)
        
        assert breaker.state.state == "open"
        assert breaker.state.failure_count == 3
        
        # Next call should raise CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(failing_func)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_to_closed(self):
        """Test circuit breaker transitions from half-open to closed."""
        breaker = CircuitBreaker("test", failure_threshold=2, success_threshold=2, timeout=0.1)
        
        async def failing_func():
            raise Exception("Test failure")
        
        async def success_func():
            return "success"
        
        # Open the circuit
        for i in range(2):
            with pytest.raises(Exception):
                await breaker.call(failing_func)
        
        assert breaker.state.state == "open"
        
        # Wait for timeout
        await asyncio.sleep(0.2)
        
        # Should enter half-open state and succeed
        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state.state == "half_open"
        
        # Another success should close the circuit
        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state.state == "closed"
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_to_open(self):
        """Test circuit breaker reopens on failure in half-open state."""
        breaker = CircuitBreaker("test", failure_threshold=2, timeout=0.1)
        
        async def failing_func():
            raise Exception("Test failure")
        
        async def success_func():
            return "success"
        
        # Open the circuit
        for i in range(2):
            with pytest.raises(Exception):
                await breaker.call(failing_func)
        
        assert breaker.state.state == "open"
        
        # Wait for timeout
        await asyncio.sleep(0.2)
        
        # Should enter half-open state but fail
        with pytest.raises(Exception):
            await breaker.call(failing_func)
        
        assert breaker.state.state == "open"
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_get_state(self):
        """Test getting circuit breaker state."""
        breaker = CircuitBreaker("test", failure_threshold=3)
        
        state = breaker.get_state()
        
        assert state["name"] == "test"
        assert state["state"] == "closed"
        assert state["failure_count"] == 0
        assert state["total_calls"] == 0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_manual_reset(self):
        """Test manual reset of circuit breaker."""
        breaker = CircuitBreaker("test", failure_threshold=2)
        
        async def failing_func():
            raise Exception("Test failure")
        
        # Open the circuit
        for i in range(2):
            with pytest.raises(Exception):
                await breaker.call(failing_func)
        
        assert breaker.state.state == "open"
        
        # Manual reset
        await breaker.reset()
        
        assert breaker.state.state == "closed"
        assert breaker.state.failure_count == 0


class TestDegradedModeManager:
    """Test degraded mode management."""
    
    def test_enter_degraded_mode(self):
        """Test entering degraded mode."""
        manager = DegradedModeManager()
        
        manager.enter_degraded_mode("chatgpt", "API unavailable")
        
        assert manager.is_degraded("chatgpt")
        assert "chatgpt" in manager.get_degraded_services()
    
    def test_exit_degraded_mode(self):
        """Test exiting degraded mode."""
        manager = DegradedModeManager()
        
        manager.enter_degraded_mode("chatgpt", "API unavailable")
        assert manager.is_degraded("chatgpt")
        
        manager.exit_degraded_mode("chatgpt")
        assert not manager.is_degraded("chatgpt")
    
    def test_fallback_handler(self):
        """Test fallback handler registration."""
        manager = DegradedModeManager()
        
        def fallback():
            return "fallback result"
        
        manager.enter_degraded_mode("chatgpt", "API unavailable", fallback_handler=fallback)
        
        handler = manager.get_fallback_handler("chatgpt")
        assert handler is not None
        assert handler() == "fallback result"
    
    def test_get_degraded_services(self):
        """Test getting all degraded services."""
        manager = DegradedModeManager()
        
        manager.enter_degraded_mode("chatgpt", "API unavailable")
        manager.enter_degraded_mode("file_reader", "File not found")
        
        services = manager.get_degraded_services()
        
        assert len(services) == 2
        assert "chatgpt" in services
        assert "file_reader" in services


class TestRetryHandler:
    """Test retry logic."""
    
    @pytest.mark.asyncio
    async def test_retry_success_on_first_attempt(self):
        """Test successful execution on first attempt."""
        handler = RetryHandler(max_retries=3)
        
        async def success_func():
            return "success"
        
        result = await handler.execute_with_retry(success_func)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self):
        """Test successful execution after some failures."""
        handler = RetryHandler(max_retries=3, initial_backoff=0.1)
        
        call_count = 0
        
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = await handler.execute_with_retry(flaky_func)
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_all_attempts_fail(self):
        """Test all retry attempts fail."""
        handler = RetryHandler(max_retries=3, initial_backoff=0.1)
        
        async def failing_func():
            raise Exception("Permanent failure")
        
        with pytest.raises(Exception, match="Permanent failure"):
            await handler.execute_with_retry(failing_func)
    
    @pytest.mark.asyncio
    async def test_retry_with_error_classifier(self):
        """Test retry with error classifier."""
        handler = RetryHandler(max_retries=3, initial_backoff=0.1)
        classifier = ErrorClassifier()
        
        # Add rule to not retry ValueError
        classifier.add_classification_rule(
            "ValueError",
            ErrorCategory.VALIDATION_ERROR,
            ErrorSeverity.MEDIUM,
            RecoveryStrategy.FAIL
        )
        
        async def failing_func():
            raise ValueError("Validation error")
        
        # Should not retry and fail immediately
        with pytest.raises(ValueError):
            await handler.execute_with_retry(failing_func, error_classifier=classifier)
    
    def test_calculate_backoff(self):
        """Test backoff calculation."""
        handler = RetryHandler(
            initial_backoff=1.0,
            max_backoff=10.0,
            backoff_multiplier=2.0,
            jitter=False
        )
        
        # Test exponential backoff
        assert handler.calculate_backoff(0) == 1.0
        assert handler.calculate_backoff(1) == 2.0
        assert handler.calculate_backoff(2) == 4.0
        assert handler.calculate_backoff(3) == 8.0
        
        # Test max backoff cap
        assert handler.calculate_backoff(10) == 10.0


class TestErrorHandlingDecorator:
    """Test error handling decorator."""
    
    @pytest.mark.asyncio
    async def test_decorator_with_success(self):
        """Test decorator with successful execution."""
        
        @handle_errors("test_component", "test_operation")
        async def success_func():
            return "success"
        
        result = await success_func()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_decorator_with_failure_raise(self):
        """Test decorator with failure and raise."""
        
        @handle_errors("test_component", "test_operation", raise_on_failure=True)
        async def failing_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            await failing_func()
    
    @pytest.mark.asyncio
    async def test_decorator_with_failure_fallback(self):
        """Test decorator with failure and fallback value."""
        
        @handle_errors("test_component", "test_operation", fallback_value="fallback", raise_on_failure=False)
        async def failing_func():
            raise ValueError("Test error")
        
        result = await failing_func()
        assert result == "fallback"


class TestGlobalInstances:
    """Test global instance getters."""
    
    def test_get_error_classifier(self):
        """Test getting global error classifier."""
        classifier = get_error_classifier()
        assert isinstance(classifier, ErrorClassifier)
    
    def test_get_degraded_mode_manager(self):
        """Test getting global degraded mode manager."""
        manager = get_degraded_mode_manager()
        assert isinstance(manager, DegradedModeManager)


class TestIntegrationScenarios:
    """Test integrated error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_with_retry(self):
        """Test circuit breaker combined with retry logic."""
        breaker = CircuitBreaker("test", failure_threshold=2, success_threshold=1, timeout=0.1)
        
        async def failing_func():
            raise Exception("Temporary failure")
        
        async def success_func():
            return "success"
        
        # Trigger failures to open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                await breaker.call(failing_func)
        
        assert breaker.state.state == "open"
        
        # Wait for circuit to enter half-open
        await asyncio.sleep(0.2)
        
        # Should succeed after circuit recovers
        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state.state == "closed"
    
    @pytest.mark.asyncio
    async def test_degraded_mode_with_fallback(self):
        """Test degraded mode with fallback handler."""
        manager = DegradedModeManager()
        
        def fallback_handler():
            return "fallback result"
        
        manager.enter_degraded_mode("service", "unavailable", fallback_handler)
        
        # Simulate using fallback
        if manager.is_degraded("service"):
            handler = manager.get_fallback_handler("service")
            result = handler()
            assert result == "fallback result"
