"""Comprehensive error handling for LLM Integration Module.

This module provides:
- Error classification and handling strategies
- Graceful degradation for ChatGPT API failures
- Circuit breaker patterns
- File reading error handling
- Retry logic with exponential backoff
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
import asyncio
from collections import deque


logger = logging.getLogger(__name__)


# Type variable for generic error handling
T = TypeVar('T')


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification."""
    API_ERROR = "api_error"
    FILE_ERROR = "file_error"
    NETWORK_ERROR = "network_error"
    VALIDATION_ERROR = "validation_error"
    PARSING_ERROR = "parsing_error"
    TIMEOUT_ERROR = "timeout_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    AUTHENTICATION_ERROR = "authentication_error"
    CONFIGURATION_ERROR = "configuration_error"
    RESOURCE_ERROR = "resource_error"
    UNKNOWN_ERROR = "unknown_error"


class RecoveryStrategy(Enum):
    """Recovery strategies for different error types."""
    RETRY = "retry"
    FALLBACK = "fallback"
    DEGRADE = "degrade"
    FAIL = "fail"
    IGNORE = "ignore"


@dataclass
class ErrorContext:
    """Context information for an error."""
    error_type: str
    error_message: str
    category: ErrorCategory
    severity: ErrorSeverity
    recovery_strategy: RecoveryStrategy
    timestamp: datetime = field(default_factory=datetime.now)
    component: Optional[str] = None
    operation: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class CircuitBreakerState:
    """State of a circuit breaker."""
    name: str
    state: str = "closed"  # closed, open, half_open
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 60.0  # seconds to wait before trying half_open
    total_calls: int = 0
    total_failures: int = 0
    total_successes: int = 0


class ErrorClassifier:
    """Classifies errors and determines appropriate handling strategies."""
    
    def __init__(self):
        """Initialize error classifier."""
        self._classification_rules: Dict[str, Dict[str, Any]] = {
            # API errors
            "RateLimitError": {
                "category": ErrorCategory.RATE_LIMIT_ERROR,
                "severity": ErrorSeverity.MEDIUM,
                "recovery": RecoveryStrategy.RETRY
            },
            "APITimeoutError": {
                "category": ErrorCategory.TIMEOUT_ERROR,
                "severity": ErrorSeverity.MEDIUM,
                "recovery": RecoveryStrategy.RETRY
            },
            "APIConnectionError": {
                "category": ErrorCategory.NETWORK_ERROR,
                "severity": ErrorSeverity.HIGH,
                "recovery": RecoveryStrategy.RETRY
            },
            "AuthenticationError": {
                "category": ErrorCategory.AUTHENTICATION_ERROR,
                "severity": ErrorSeverity.CRITICAL,
                "recovery": RecoveryStrategy.FAIL
            },
            "OpenAIError": {
                "category": ErrorCategory.API_ERROR,
                "severity": ErrorSeverity.HIGH,
                "recovery": RecoveryStrategy.DEGRADE
            },
            
            # File errors
            "FileNotFoundError": {
                "category": ErrorCategory.FILE_ERROR,
                "severity": ErrorSeverity.HIGH,
                "recovery": RecoveryStrategy.RETRY
            },
            "PermissionError": {
                "category": ErrorCategory.FILE_ERROR,
                "severity": ErrorSeverity.HIGH,
                "recovery": RecoveryStrategy.FAIL
            },
            "JSONDecodeError": {
                "category": ErrorCategory.PARSING_ERROR,
                "severity": ErrorSeverity.HIGH,
                "recovery": RecoveryStrategy.RETRY
            },
            
            # Validation errors
            "ValueError": {
                "category": ErrorCategory.VALIDATION_ERROR,
                "severity": ErrorSeverity.MEDIUM,
                "recovery": RecoveryStrategy.FAIL
            },
            "ValidationError": {
                "category": ErrorCategory.VALIDATION_ERROR,
                "severity": ErrorSeverity.MEDIUM,
                "recovery": RecoveryStrategy.FAIL
            },
            
            # Resource errors
            "MemoryError": {
                "category": ErrorCategory.RESOURCE_ERROR,
                "severity": ErrorSeverity.CRITICAL,
                "recovery": RecoveryStrategy.DEGRADE
            },
            "TimeoutError": {
                "category": ErrorCategory.TIMEOUT_ERROR,
                "severity": ErrorSeverity.MEDIUM,
                "recovery": RecoveryStrategy.RETRY
            }
        }
    
    def classify(
        self,
        error: Exception,
        component: Optional[str] = None,
        operation: Optional[str] = None
    ) -> ErrorContext:
        """Classify an error and determine handling strategy.
        
        Args:
            error: The exception to classify
            component: Component where error occurred
            operation: Operation being performed
            
        Returns:
            ErrorContext with classification and handling strategy
        """
        error_type = type(error).__name__
        error_message = str(error)
        
        # Get classification rules for this error type
        rules = self._classification_rules.get(
            error_type,
            {
                "category": ErrorCategory.UNKNOWN_ERROR,
                "severity": ErrorSeverity.MEDIUM,
                "recovery": RecoveryStrategy.RETRY
            }
        )
        
        # Create error context
        context = ErrorContext(
            error_type=error_type,
            error_message=error_message,
            category=rules["category"],
            severity=rules["severity"],
            recovery_strategy=rules["recovery"],
            component=component,
            operation=operation
        )
        
        # Add metadata based on error type
        if hasattr(error, '__dict__'):
            context.metadata = {
                k: v for k, v in error.__dict__.items()
                if not k.startswith('_')
            }
        
        logger.debug(
            f"Classified error: {error_type} -> "
            f"Category: {context.category.value}, "
            f"Severity: {context.severity.value}, "
            f"Recovery: {context.recovery_strategy.value}"
        )
        
        return context
    
    def add_classification_rule(
        self,
        error_type: str,
        category: ErrorCategory,
        severity: ErrorSeverity,
        recovery: RecoveryStrategy
    ) -> None:
        """Add or update a classification rule.
        
        Args:
            error_type: Name of the exception class
            category: Error category
            severity: Error severity
            recovery: Recovery strategy
        """
        self._classification_rules[error_type] = {
            "category": category,
            "severity": severity,
            "recovery": recovery
        }
        logger.info(f"Added classification rule for {error_type}")


class CircuitBreaker:
    """Circuit breaker pattern implementation for fault tolerance.
    
    The circuit breaker prevents cascading failures by:
    - Opening the circuit after a threshold of failures
    - Allowing the system to recover before retrying
    - Gradually testing recovery with half-open state
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 60.0
    ):
        """Initialize circuit breaker.
        
        Args:
            name: Name of the circuit breaker
            failure_threshold: Number of failures before opening circuit
            success_threshold: Number of successes in half-open before closing
            timeout: Seconds to wait before trying half-open state
        """
        self.state = CircuitBreakerState(
            name=name,
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout=timeout
        )
        self._lock = asyncio.Lock()
        logger.info(
            f"Circuit breaker '{name}' initialized: "
            f"failure_threshold={failure_threshold}, timeout={timeout}s"
        )
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function
            
        Returns:
            Result of function execution
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Original exception from function
        """
        async with self._lock:
            self.state.total_calls += 1
            
            # Check circuit state
            if self.state.state == "open":
                # Check if timeout has elapsed
                if self._should_attempt_reset():
                    logger.info(f"Circuit breaker '{self.state.name}' entering half-open state")
                    self.state.state = "half_open"
                    self.state.success_count = 0
                else:
                    # Circuit is still open
                    wait_time = self._get_remaining_timeout()
                    logger.warning(
                        f"Circuit breaker '{self.state.name}' is OPEN. "
                        f"Retry in {wait_time:.1f}s"
                    )
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.state.name}' is open. "
                        f"Retry in {wait_time:.1f}s"
                    )
        
        # Execute function
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Record success
            await self._record_success()
            return result
            
        except Exception as e:
            # Record failure
            await self._record_failure()
            raise
    
    async def _record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            self.state.success_count += 1
            self.state.total_successes += 1
            self.state.last_success_time = datetime.now()
            
            if self.state.state == "half_open":
                # Check if we should close the circuit
                if self.state.success_count >= self.state.success_threshold:
                    logger.info(
                        f"Circuit breaker '{self.state.name}' closing after "
                        f"{self.state.success_count} successes"
                    )
                    self.state.state = "closed"
                    self.state.failure_count = 0
                    self.state.success_count = 0
            elif self.state.state == "closed":
                # Reset failure count on success
                self.state.failure_count = 0
    
    async def _record_failure(self) -> None:
        """Record a failed call."""
        async with self._lock:
            self.state.failure_count += 1
            self.state.total_failures += 1
            self.state.last_failure_time = datetime.now()
            
            if self.state.state == "half_open":
                # Failure in half-open state reopens circuit
                logger.warning(
                    f"Circuit breaker '{self.state.name}' reopening after failure in half-open state"
                )
                self.state.state = "open"
                self.state.opened_at = datetime.now()
                self.state.success_count = 0
                
            elif self.state.state == "closed":
                # Check if we should open the circuit
                if self.state.failure_count >= self.state.failure_threshold:
                    logger.error(
                        f"Circuit breaker '{self.state.name}' OPENING after "
                        f"{self.state.failure_count} failures"
                    )
                    self.state.state = "open"
                    self.state.opened_at = datetime.now()
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if not self.state.opened_at:
            return False
        
        elapsed = (datetime.now() - self.state.opened_at).total_seconds()
        return elapsed >= self.state.timeout
    
    def _get_remaining_timeout(self) -> float:
        """Get remaining timeout before attempting reset."""
        if not self.state.opened_at:
            return 0.0
        
        elapsed = (datetime.now() - self.state.opened_at).total_seconds()
        remaining = max(0.0, self.state.timeout - elapsed)
        return remaining
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state.
        
        Returns:
            Dictionary with state information
        """
        return {
            "name": self.state.name,
            "state": self.state.state,
            "failure_count": self.state.failure_count,
            "success_count": self.state.success_count,
            "total_calls": self.state.total_calls,
            "total_failures": self.state.total_failures,
            "total_successes": self.state.total_successes,
            "failure_rate": (
                self.state.total_failures / self.state.total_calls
                if self.state.total_calls > 0 else 0.0
            ),
            "last_failure_time": self.state.last_failure_time,
            "last_success_time": self.state.last_success_time,
            "opened_at": self.state.opened_at,
            "remaining_timeout": self._get_remaining_timeout() if self.state.state == "open" else None
        }
    
    async def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        async with self._lock:
            logger.info(f"Manually resetting circuit breaker '{self.state.name}'")
            self.state.state = "closed"
            self.state.failure_count = 0
            self.state.success_count = 0
            self.state.opened_at = None


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class DegradedModeManager:
    """Manages graceful degradation when services are unavailable."""
    
    def __init__(self):
        """Initialize degraded mode manager."""
        self._degraded_services: Dict[str, Dict[str, Any]] = {}
        self._fallback_handlers: Dict[str, Callable] = {}
        logger.info("Degraded mode manager initialized")
    
    def enter_degraded_mode(
        self,
        service_name: str,
        reason: str,
        fallback_handler: Optional[Callable] = None
    ) -> None:
        """Enter degraded mode for a service.
        
        Args:
            service_name: Name of the service
            reason: Reason for degradation
            fallback_handler: Optional fallback function to use
        """
        self._degraded_services[service_name] = {
            "reason": reason,
            "entered_at": datetime.now(),
            "has_fallback": fallback_handler is not None
        }
        
        if fallback_handler:
            self._fallback_handlers[service_name] = fallback_handler
        
        logger.warning(
            f"Service '{service_name}' entering degraded mode: {reason}"
        )
    
    def exit_degraded_mode(self, service_name: str) -> None:
        """Exit degraded mode for a service.
        
        Args:
            service_name: Name of the service
        """
        if service_name in self._degraded_services:
            duration = (
                datetime.now() - self._degraded_services[service_name]["entered_at"]
            ).total_seconds()
            
            del self._degraded_services[service_name]
            if service_name in self._fallback_handlers:
                del self._fallback_handlers[service_name]
            
            logger.info(
                f"Service '{service_name}' exiting degraded mode "
                f"(duration: {duration:.1f}s)"
            )
    
    def is_degraded(self, service_name: str) -> bool:
        """Check if a service is in degraded mode.
        
        Args:
            service_name: Name of the service
            
        Returns:
            True if service is degraded
        """
        return service_name in self._degraded_services
    
    def get_fallback_handler(self, service_name: str) -> Optional[Callable]:
        """Get fallback handler for a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Fallback handler function or None
        """
        return self._fallback_handlers.get(service_name)
    
    def get_degraded_services(self) -> Dict[str, Dict[str, Any]]:
        """Get all services in degraded mode.
        
        Returns:
            Dictionary of degraded services and their info
        """
        return self._degraded_services.copy()


class RetryHandler:
    """Handles retry logic with exponential backoff."""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
        max_backoff: float = 60.0,
        backoff_multiplier: float = 2.0,
        jitter: bool = True
    ):
        """Initialize retry handler.
        
        Args:
            max_retries: Maximum number of retry attempts
            initial_backoff: Initial backoff delay in seconds
            max_backoff: Maximum backoff delay in seconds
            backoff_multiplier: Multiplier for exponential backoff
            jitter: Whether to add random jitter to backoff
        """
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter
    
    def calculate_backoff(self, attempt: int) -> float:
        """Calculate backoff delay for an attempt.
        
        Args:
            attempt: Current attempt number (0-indexed)
            
        Returns:
            Backoff delay in seconds
        """
        import random
        
        # Exponential backoff
        delay = min(
            self.initial_backoff * (self.backoff_multiplier ** attempt),
            self.max_backoff
        )
        
        # Add jitter to prevent thundering herd
        if self.jitter:
            delay = delay * (0.5 + random.random() * 0.5)
        
        return delay
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        error_classifier: Optional[ErrorClassifier] = None,
        **kwargs
    ) -> Any:
        """Execute function with retry logic.
        
        Args:
            func: Function to execute
            *args: Positional arguments for function
            error_classifier: Optional error classifier for smart retries
            **kwargs: Keyword arguments for function
            
        Returns:
            Result of function execution
            
        Raises:
            Exception: Last exception if all retries fail
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                if attempt > 0:
                    logger.info(f"Retry succeeded on attempt {attempt + 1}")
                
                return result
                
            except Exception as e:
                last_error = e
                
                # Check if we should retry this error
                if error_classifier:
                    context = error_classifier.classify(e)
                    if context.recovery_strategy != RecoveryStrategy.RETRY:
                        logger.info(
                            f"Not retrying {context.error_type}: "
                            f"recovery strategy is {context.recovery_strategy.value}"
                        )
                        raise
                
                # If not last attempt, wait and retry
                if attempt < self.max_retries - 1:
                    backoff = self.calculate_backoff(attempt)
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_retries} failed: {e}. "
                        f"Retrying in {backoff:.2f}s"
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error(
                        f"All {self.max_retries} retry attempts failed: {e}"
                    )
        
        raise last_error


# Global instances
_error_classifier = ErrorClassifier()
_degraded_mode_manager = DegradedModeManager()


def get_error_classifier() -> ErrorClassifier:
    """Get global error classifier instance."""
    return _error_classifier


def get_degraded_mode_manager() -> DegradedModeManager:
    """Get global degraded mode manager instance."""
    return _degraded_mode_manager


# Decorator for automatic error handling
def handle_errors(
    component: str,
    operation: str,
    fallback_value: Any = None,
    raise_on_failure: bool = True
):
    """Decorator for automatic error handling.
    
    Args:
        component: Component name
        operation: Operation name
        fallback_value: Value to return on error if not raising
        raise_on_failure: Whether to raise exception after handling
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                context = _error_classifier.classify(e, component, operation)
                logger.error(
                    f"Error in {component}.{operation}: {context.error_type} - {context.error_message}",
                    extra={"error_context": context}
                )
                
                if raise_on_failure:
                    raise
                return fallback_value
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                context = _error_classifier.classify(e, component, operation)
                logger.error(
                    f"Error in {component}.{operation}: {context.error_type} - {context.error_message}",
                    extra={"error_context": context}
                )
                
                if raise_on_failure:
                    raise
                return fallback_value
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator
