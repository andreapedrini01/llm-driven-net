"""Logging configuration and utilities."""

import logging
import sys
from typing import Any, Dict, Optional
import structlog
from structlog.stdlib import LoggerFactory


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


class CorrelationIDProcessor:
    """Processor to add correlation IDs to log entries."""
    
    def __init__(self, correlation_id_key: str = "correlation_id"):
        self.correlation_id_key = correlation_id_key
    
    def __call__(self, logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Add correlation ID to log entry if available."""
        # This would typically get the correlation ID from context
        # For now, we'll just ensure the key exists
        if self.correlation_id_key not in event_dict:
            event_dict[self.correlation_id_key] = None
        return event_dict


class AuditLogger:
    """Specialized logger for audit events."""
    
    def __init__(self):
        self.logger = get_logger("audit")
    
    def log_intent_received(self, intent_id: str, user_id: str, raw_text: str) -> None:
        """Log when an intent is received."""
        self.logger.info(
            "Intent received",
            intent_id=intent_id,
            user_id=user_id,
            raw_text=raw_text,
            event_type="intent_received"
        )
    
    def log_action_generated(self, intent_id: str, action_sequence_id: str, action_count: int) -> None:
        """Log when actions are generated."""
        self.logger.info(
            "Actions generated",
            intent_id=intent_id,
            action_sequence_id=action_sequence_id,
            action_count=action_count,
            event_type="actions_generated"
        )
    
    def log_action_executed(self, action_id: str, success: bool, error: Optional[str] = None) -> None:
        """Log when an action is executed."""
        self.logger.info(
            "Action executed",
            action_id=action_id,
            success=success,
            error=error,
            event_type="action_executed"
        )
    
    def log_anomaly_detected(self, anomaly_id: str, anomaly_type: str, severity: str) -> None:
        """Log when an anomaly is detected."""
        self.logger.warning(
            "Anomaly detected",
            anomaly_id=anomaly_id,
            anomaly_type=anomaly_type,
            severity=severity,
            event_type="anomaly_detected"
        )
    
    def log_error(self, error_type: str, error_message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log system errors."""
        self.logger.error(
            "System error",
            error_type=error_type,
            error_message=error_message,
            context=context or {},
            event_type="system_error"
        )