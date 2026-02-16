"""Logging configuration and utilities."""

import logging
import sys
import uuid
import contextvars
from typing import Any, Dict, Optional
from datetime import datetime
import structlog
from structlog.stdlib import LoggerFactory


# Context variable for correlation ID
correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'correlation_id', default=None
)


def configure_logging(
    log_level: str = "INFO",
    json_logs: bool = True,
    include_timestamp: bool = True,
) -> None:
    """Configure structured logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: Whether to output logs in JSON format
        include_timestamp: Whether to include timestamps in logs
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )
    
    # Configure structlog processors
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        CorrelationIDProcessor(),  # Add correlation ID to all logs
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    if include_timestamp:
        processors.append(structlog.processors.TimeStamper(fmt="iso"))
    
    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a configured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return structlog.get_logger(name)


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Set correlation ID for the current context.
    
    Args:
        correlation_id: Correlation ID to set. If None, generates a new UUID.
        
    Returns:
        The correlation ID that was set
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    correlation_id_var.set(correlation_id)
    return correlation_id


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID from context.
    
    Returns:
        Current correlation ID or None if not set
    """
    return correlation_id_var.get()


def clear_correlation_id() -> None:
    """Clear the correlation ID from context."""
    correlation_id_var.set(None)


class CorrelationIDProcessor:
    """Processor to add correlation IDs to log entries."""
    
    def __init__(self, correlation_id_key: str = "correlation_id"):
        self.correlation_id_key = correlation_id_key
    
    def __call__(self, logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Add correlation ID to log entry if available."""
        correlation_id = correlation_id_var.get()
        if correlation_id:
            event_dict[self.correlation_id_key] = correlation_id
        return event_dict


class AuditLogger:
    """Specialized logger for audit events."""
    
    def __init__(self):
        self.logger = get_logger("audit")
    
    def log_intent_received(
        self, 
        intent_id: str, 
        user_id: str, 
        raw_text: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log when an intent is received."""
        self.logger.info(
            "Intent received",
            intent_id=intent_id,
            user_id=user_id,
            raw_text=raw_text,
            event_type="intent_received",
            correlation_id=correlation_id or get_correlation_id()
        )
    
    def log_action_generated(
        self, 
        intent_id: str, 
        action_sequence_id: str, 
        action_count: int,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log when actions are generated."""
        self.logger.info(
            "Actions generated",
            intent_id=intent_id,
            action_sequence_id=action_sequence_id,
            action_count=action_count,
            event_type="actions_generated",
            correlation_id=correlation_id or get_correlation_id()
        )
    
    def log_action_executed(
        self, 
        action_id: str, 
        success: bool, 
        error: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log when an action is executed."""
        self.logger.info(
            "Action executed",
            action_id=action_id,
            success=success,
            error=error,
            event_type="action_executed",
            correlation_id=correlation_id or get_correlation_id()
        )
    
    def log_anomaly_detected(
        self, 
        anomaly_id: str, 
        anomaly_type: str, 
        severity: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log when an anomaly is detected."""
        self.logger.warning(
            "Anomaly detected",
            anomaly_id=anomaly_id,
            anomaly_type=anomaly_type,
            severity=severity,
            event_type="anomaly_detected",
            correlation_id=correlation_id or get_correlation_id()
        )
    
    def log_error(
        self, 
        error_type: str, 
        error_message: str, 
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Log system errors."""
        self.logger.error(
            "System error",
            error_type=error_type,
            error_message=error_message,
            context=context or {},
            event_type="system_error",
            correlation_id=correlation_id or get_correlation_id()
        )



class PerformanceLogger:
    """Logger for performance metrics and monitoring."""
    
    def __init__(self):
        self.logger = get_logger("performance")
    
    def log_operation_start(
        self,
        operation_name: str,
        component: str,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """Log the start of an operation.
        
        Args:
            operation_name: Name of the operation
            component: Component performing the operation
            correlation_id: Optional correlation ID
            **kwargs: Additional context
            
        Returns:
            Operation ID for tracking
        """
        operation_id = str(uuid.uuid4())
        self.logger.info(
            "Operation started",
            operation_id=operation_id,
            operation_name=operation_name,
            component=component,
            event_type="operation_start",
            correlation_id=correlation_id or get_correlation_id(),
            **kwargs
        )
        return operation_id
    
    def log_operation_end(
        self,
        operation_id: str,
        operation_name: str,
        component: str,
        duration_ms: float,
        success: bool,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log the end of an operation.
        
        Args:
            operation_id: Operation ID from log_operation_start
            operation_name: Name of the operation
            component: Component performing the operation
            duration_ms: Duration in milliseconds
            success: Whether operation succeeded
            correlation_id: Optional correlation ID
            **kwargs: Additional context
        """
        log_method = self.logger.info if success else self.logger.error
        log_method(
            "Operation completed",
            operation_id=operation_id,
            operation_name=operation_name,
            component=component,
            duration_ms=duration_ms,
            success=success,
            event_type="operation_end",
            correlation_id=correlation_id or get_correlation_id(),
            **kwargs
        )
    
    def log_metric(
        self,
        metric_name: str,
        metric_value: float,
        metric_unit: str,
        component: str,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log a performance metric.
        
        Args:
            metric_name: Name of the metric
            metric_value: Value of the metric
            metric_unit: Unit of measurement
            component: Component reporting the metric
            correlation_id: Optional correlation ID
            **kwargs: Additional context
        """
        self.logger.info(
            "Performance metric",
            metric_name=metric_name,
            metric_value=metric_value,
            metric_unit=metric_unit,
            component=component,
            event_type="performance_metric",
            correlation_id=correlation_id or get_correlation_id(),
            **kwargs
        )
    
    def log_resource_usage(
        self,
        component: str,
        memory_mb: Optional[float] = None,
        cpu_percent: Optional[float] = None,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log resource usage metrics.
        
        Args:
            component: Component reporting usage
            memory_mb: Memory usage in MB
            cpu_percent: CPU usage percentage
            correlation_id: Optional correlation ID
            **kwargs: Additional context
        """
        self.logger.info(
            "Resource usage",
            component=component,
            memory_mb=memory_mb,
            cpu_percent=cpu_percent,
            event_type="resource_usage",
            correlation_id=correlation_id or get_correlation_id(),
            **kwargs
        )


class ChatGPTUsageLogger:
    """Logger for ChatGPT API usage and costs."""
    
    def __init__(self):
        self.logger = get_logger("chatgpt_usage")
    
    def log_api_request(
        self,
        request_id: str,
        model: str,
        prompt_tokens: int,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log a ChatGPT API request.
        
        Args:
            request_id: Unique request ID
            model: Model used for the request
            prompt_tokens: Number of prompt tokens
            correlation_id: Optional correlation ID
            **kwargs: Additional context
        """
        self.logger.info(
            "ChatGPT API request",
            request_id=request_id,
            model=model,
            prompt_tokens=prompt_tokens,
            event_type="chatgpt_request",
            correlation_id=correlation_id or get_correlation_id(),
            **kwargs
        )
    
    def log_api_response(
        self,
        request_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        latency_ms: float,
        estimated_cost: float,
        success: bool,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log a ChatGPT API response.
        
        Args:
            request_id: Unique request ID
            model: Model used for the request
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            total_tokens: Total tokens used
            latency_ms: Request latency in milliseconds
            estimated_cost: Estimated cost in USD
            success: Whether request succeeded
            correlation_id: Optional correlation ID
            **kwargs: Additional context
        """
        log_method = self.logger.info if success else self.logger.error
        log_method(
            "ChatGPT API response",
            request_id=request_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            estimated_cost=estimated_cost,
            success=success,
            event_type="chatgpt_response",
            correlation_id=correlation_id or get_correlation_id(),
            **kwargs
        )
    
    def log_api_error(
        self,
        request_id: str,
        model: str,
        error_type: str,
        error_message: str,
        retry_attempt: int,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log a ChatGPT API error.
        
        Args:
            request_id: Unique request ID
            model: Model used for the request
            error_type: Type of error
            error_message: Error message
            retry_attempt: Current retry attempt number
            correlation_id: Optional correlation ID
            **kwargs: Additional context
        """
        self.logger.error(
            "ChatGPT API error",
            request_id=request_id,
            model=model,
            error_type=error_type,
            error_message=error_message,
            retry_attempt=retry_attempt,
            event_type="chatgpt_error",
            correlation_id=correlation_id or get_correlation_id(),
            **kwargs
        )
    
    def log_rate_limit(
        self,
        model: str,
        remaining_requests: int,
        reset_time: datetime,
        is_throttled: bool,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log rate limit status.
        
        Args:
            model: Model being rate limited
            remaining_requests: Remaining requests in current window
            reset_time: When rate limit resets
            is_throttled: Whether currently throttled
            correlation_id: Optional correlation ID
            **kwargs: Additional context
        """
        self.logger.info(
            "ChatGPT rate limit status",
            model=model,
            remaining_requests=remaining_requests,
            reset_time=reset_time.isoformat(),
            is_throttled=is_throttled,
            event_type="chatgpt_rate_limit",
            correlation_id=correlation_id or get_correlation_id(),
            **kwargs
        )
    
    def log_budget_alert(
        self,
        alert_type: str,
        current_cost: float,
        threshold: float,
        message: str,
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log a budget alert.
        
        Args:
            alert_type: Type of alert (warning, critical)
            current_cost: Current total cost
            threshold: Threshold that was exceeded
            message: Alert message
            correlation_id: Optional correlation ID
            **kwargs: Additional context
        """
        log_method = self.logger.warning if alert_type == "warning" else self.logger.critical
        log_method(
            "ChatGPT budget alert",
            alert_type=alert_type,
            current_cost=current_cost,
            threshold=threshold,
            message=message,
            event_type="chatgpt_budget_alert",
            correlation_id=correlation_id or get_correlation_id(),
            **kwargs
        )
    
    def log_usage_summary(
        self,
        period_start: datetime,
        period_end: datetime,
        total_requests: int,
        total_tokens: int,
        total_cost: float,
        models_used: Dict[str, int],
        correlation_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log a usage summary for a time period.
        
        Args:
            period_start: Start of the period
            period_end: End of the period
            total_requests: Total number of requests
            total_tokens: Total tokens used
            total_cost: Total cost in USD
            models_used: Dictionary of model names to request counts
            correlation_id: Optional correlation ID
            **kwargs: Additional context
        """
        self.logger.info(
            "ChatGPT usage summary",
            period_start=period_start.isoformat(),
            period_end=period_end.isoformat(),
            total_requests=total_requests,
            total_tokens=total_tokens,
            total_cost=total_cost,
            models_used=models_used,
            event_type="chatgpt_usage_summary",
            correlation_id=correlation_id or get_correlation_id(),
            **kwargs
        )


# Global logger instances
audit_logger = AuditLogger()
performance_logger = PerformanceLogger()
chatgpt_usage_logger = ChatGPTUsageLogger()
