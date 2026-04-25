"""Tests for logging utilities."""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import structlog

from llm_integration_module.utils.logging import (
    configure_logging,
    get_logger,
    set_correlation_id,
    get_correlation_id,
    clear_correlation_id,
    CorrelationIDProcessor,
    AuditLogger,
    PerformanceLogger,
    ChatGPTUsageLogger,
    audit_logger,
    performance_logger,
    chatgpt_usage_logger,
)


class TestLoggingConfiguration:
    """Tests for logging configuration."""
    
    def test_configure_logging_default(self):
        """Test default logging configuration."""
        configure_logging()
        logger = get_logger("test")
        assert logger is not None
        # Logger is a BoundLoggerLazyProxy which wraps BoundLogger
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'error')
        assert hasattr(logger, 'warning')
    
    def test_configure_logging_custom_level(self):
        """Test logging configuration with custom level."""
        configure_logging(log_level="DEBUG")
        logger = get_logger("test")
        assert logger is not None
    
    def test_configure_logging_json_format(self):
        """Test logging configuration with JSON format."""
        configure_logging(json_logs=True)
        logger = get_logger("test")
        assert logger is not None
    
    def test_configure_logging_console_format(self):
        """Test logging configuration with console format."""
        configure_logging(json_logs=False)
        logger = get_logger("test")
        assert logger is not None


class TestCorrelationID:
    """Tests for correlation ID management."""
    
    def test_set_correlation_id_auto_generate(self):
        """Test auto-generation of correlation ID."""
        correlation_id = set_correlation_id()
        assert correlation_id is not None
        assert len(correlation_id) > 0
        # Should be a valid UUID
        uuid.UUID(correlation_id)
    
    def test_set_correlation_id_custom(self):
        """Test setting custom correlation ID."""
        custom_id = "custom-correlation-id"
        correlation_id = set_correlation_id(custom_id)
        assert correlation_id == custom_id
    
    def test_get_correlation_id(self):
        """Test getting correlation ID."""
        custom_id = "test-correlation-id"
        set_correlation_id(custom_id)
        retrieved_id = get_correlation_id()
        assert retrieved_id == custom_id
    
    def test_get_correlation_id_not_set(self):
        """Test getting correlation ID when not set."""
        clear_correlation_id()
        correlation_id = get_correlation_id()
        assert correlation_id is None
    
    def test_clear_correlation_id(self):
        """Test clearing correlation ID."""
        set_correlation_id("test-id")
        clear_correlation_id()
        correlation_id = get_correlation_id()
        assert correlation_id is None


class TestCorrelationIDProcessor:
    """Tests for CorrelationIDProcessor."""
    
    def test_processor_adds_correlation_id(self):
        """Test that processor adds correlation ID to event dict."""
        processor = CorrelationIDProcessor()
        set_correlation_id("test-correlation-id")
        
        event_dict = {"message": "test"}
        result = processor(None, None, event_dict)
        
        assert "correlation_id" in result
        assert result["correlation_id"] == "test-correlation-id"
    
    def test_processor_no_correlation_id(self):
        """Test processor when no correlation ID is set."""
        processor = CorrelationIDProcessor()
        clear_correlation_id()
        
        event_dict = {"message": "test"}
        result = processor(None, None, event_dict)
        
        # Should not add correlation_id if not set
        assert "correlation_id" not in result


class TestAuditLogger:
    """Tests for AuditLogger."""
    
    def test_log_intent_received(self):
        """Test logging intent received event."""
        logger = AuditLogger()
        
        with patch.object(logger.logger, 'info') as mock_info:
            logger.log_intent_received(
                intent_id="intent-123",
                user_id="user-456",
                raw_text="Configure network slice"
            )
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert call_args[0][0] == "Intent received"
            assert call_args[1]["intent_id"] == "intent-123"
            assert call_args[1]["user_id"] == "user-456"
            assert call_args[1]["event_type"] == "intent_received"
    
    def test_log_action_generated(self):
        """Test logging action generated event."""
        logger = AuditLogger()
        
        with patch.object(logger.logger, 'info') as mock_info:
            logger.log_action_generated(
                intent_id="intent-123",
                action_sequence_id="seq-456",
                action_count=3
            )
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert call_args[0][0] == "Actions generated"
            assert call_args[1]["action_count"] == 3
    
    def test_log_action_executed(self):
        """Test logging action executed event."""
        logger = AuditLogger()
        
        with patch.object(logger.logger, 'info') as mock_info:
            logger.log_action_executed(
                action_id="action-789",
                success=True
            )
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert call_args[1]["success"] is True
    
    def test_log_anomaly_detected(self):
        """Test logging anomaly detected event."""
        logger = AuditLogger()
        
        with patch.object(logger.logger, 'warning') as mock_warning:
            logger.log_anomaly_detected(
                anomaly_id="anomaly-123",
                anomaly_type="traffic_spike",
                severity="high"
            )
            
            mock_warning.assert_called_once()
            call_args = mock_warning.call_args
            assert call_args[1]["severity"] == "high"
    
    def test_log_error(self):
        """Test logging system error."""
        logger = AuditLogger()
        
        with patch.object(logger.logger, 'error') as mock_error:
            logger.log_error(
                error_type="APIError",
                error_message="Connection failed",
                context={"retry_count": 3}
            )
            
            mock_error.assert_called_once()
            call_args = mock_error.call_args
            assert call_args[1]["error_type"] == "APIError"
            assert call_args[1]["context"]["retry_count"] == 3


class TestPerformanceLogger:
    """Tests for PerformanceLogger."""
    
    def test_log_operation_start(self):
        """Test logging operation start."""
        logger = PerformanceLogger()
        
        with patch.object(logger.logger, 'info') as mock_info:
            operation_id = logger.log_operation_start(
                operation_name="parse_intent",
                component="intent_parser"
            )
            
            assert operation_id is not None
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert call_args[0][0] == "Operation started"
            assert call_args[1]["operation_name"] == "parse_intent"
    
    def test_log_operation_end(self):
        """Test logging operation end."""
        logger = PerformanceLogger()
        
        with patch.object(logger.logger, 'info') as mock_info:
            logger.log_operation_end(
                operation_id="op-123",
                operation_name="parse_intent",
                component="intent_parser",
                duration_ms=150.5,
                success=True
            )
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert call_args[1]["duration_ms"] == 150.5
            assert call_args[1]["success"] is True
    
    def test_log_operation_end_failure(self):
        """Test logging operation end with failure."""
        logger = PerformanceLogger()
        
        with patch.object(logger.logger, 'error') as mock_error:
            logger.log_operation_end(
                operation_id="op-123",
                operation_name="parse_intent",
                component="intent_parser",
                duration_ms=50.0,
                success=False
            )
            
            mock_error.assert_called_once()
    
    def test_log_metric(self):
        """Test logging performance metric."""
        logger = PerformanceLogger()
        
        with patch.object(logger.logger, 'info') as mock_info:
            logger.log_metric(
                metric_name="response_time",
                metric_value=125.5,
                metric_unit="ms",
                component="api_gateway"
            )
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert call_args[1]["metric_value"] == 125.5
            assert call_args[1]["metric_unit"] == "ms"
    
    def test_log_resource_usage(self):
        """Test logging resource usage."""
        logger = PerformanceLogger()
        
        with patch.object(logger.logger, 'info') as mock_info:
            logger.log_resource_usage(
                component="chatgpt_client",
                memory_mb=256.5,
                cpu_percent=45.2
            )
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert call_args[1]["memory_mb"] == 256.5
            assert call_args[1]["cpu_percent"] == 45.2


class TestChatGPTUsageLogger:
    """Tests for ChatGPTUsageLogger."""
    
    def test_log_api_request(self):
        """Test logging API request."""
        logger = ChatGPTUsageLogger()
        
        with patch.object(logger.logger, 'info') as mock_info:
            logger.log_api_request(
                request_id="req-123",
                model="gpt-4-turbo",
                prompt_tokens=150
            )
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert call_args[1]["model"] == "gpt-4-turbo"
            assert call_args[1]["prompt_tokens"] == 150
    
    def test_log_api_response_success(self):
        """Test logging successful API response."""
        logger = ChatGPTUsageLogger()
        
        with patch.object(logger.logger, 'info') as mock_info:
            logger.log_api_response(
                request_id="req-123",
                model="gpt-4-turbo",
                prompt_tokens=150,
                completion_tokens=200,
                total_tokens=350,
                latency_ms=1250.5,
                estimated_cost=0.0105,
                success=True
            )
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert call_args[1]["total_tokens"] == 350
            assert call_args[1]["estimated_cost"] == 0.0105
    
    def test_log_api_response_failure(self):
        """Test logging failed API response."""
        logger = ChatGPTUsageLogger()
        
        with patch.object(logger.logger, 'error') as mock_error:
            logger.log_api_response(
                request_id="req-123",
                model="gpt-4-turbo",
                prompt_tokens=150,
                completion_tokens=0,
                total_tokens=150,
                latency_ms=500.0,
                estimated_cost=0.0,
                success=False
            )
            
            mock_error.assert_called_once()
    
    def test_log_api_error(self):
        """Test logging API error."""
        logger = ChatGPTUsageLogger()
        
        with patch.object(logger.logger, 'error') as mock_error:
            logger.log_api_error(
                request_id="req-123",
                model="gpt-4-turbo",
                error_type="RateLimitError",
                error_message="Rate limit exceeded",
                retry_attempt=2
            )
            
            mock_error.assert_called_once()
            call_args = mock_error.call_args
            assert call_args[1]["error_type"] == "RateLimitError"
            assert call_args[1]["retry_attempt"] == 2
    
    def test_log_rate_limit(self):
        """Test logging rate limit status."""
        logger = ChatGPTUsageLogger()
        
        with patch.object(logger.logger, 'info') as mock_info:
            reset_time = datetime.now() + timedelta(minutes=1)
            logger.log_rate_limit(
                model="gpt-4-turbo",
                remaining_requests=45,
                reset_time=reset_time,
                is_throttled=False
            )
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert call_args[1]["remaining_requests"] == 45
            assert call_args[1]["is_throttled"] is False
    
    def test_log_budget_alert_warning(self):
        """Test logging budget warning alert."""
        logger = ChatGPTUsageLogger()
        
        with patch.object(logger.logger, 'warning') as mock_warning:
            logger.log_budget_alert(
                alert_type="warning",
                current_cost=12.50,
                threshold=10.0,
                message="Budget warning threshold exceeded"
            )
            
            mock_warning.assert_called_once()
            call_args = mock_warning.call_args
            assert call_args[1]["current_cost"] == 12.50
    
    def test_log_budget_alert_critical(self):
        """Test logging budget critical alert."""
        logger = ChatGPTUsageLogger()
        
        with patch.object(logger.logger, 'critical') as mock_critical:
            logger.log_budget_alert(
                alert_type="critical",
                current_cost=55.0,
                threshold=50.0,
                message="CRITICAL: Budget exceeded"
            )
            
            mock_critical.assert_called_once()
    
    def test_log_usage_summary(self):
        """Test logging usage summary."""
        logger = ChatGPTUsageLogger()
        
        with patch.object(logger.logger, 'info') as mock_info:
            period_start = datetime.now() - timedelta(days=1)
            period_end = datetime.now()
            
            logger.log_usage_summary(
                period_start=period_start,
                period_end=period_end,
                total_requests=150,
                total_tokens=45000,
                total_cost=13.50,
                models_used={"gpt-4-turbo": 100, "gpt-3.5-turbo": 50}
            )
            
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert call_args[1]["total_requests"] == 150
            assert call_args[1]["total_cost"] == 13.50


class TestGlobalLoggerInstances:
    """Tests for global logger instances."""
    
    def test_audit_logger_instance(self):
        """Test global audit logger instance."""
        assert audit_logger is not None
        assert isinstance(audit_logger, AuditLogger)
    
    def test_performance_logger_instance(self):
        """Test global performance logger instance."""
        assert performance_logger is not None
        assert isinstance(performance_logger, PerformanceLogger)
    
    def test_chatgpt_usage_logger_instance(self):
        """Test global ChatGPT usage logger instance."""
        assert chatgpt_usage_logger is not None
        assert isinstance(chatgpt_usage_logger, ChatGPTUsageLogger)


class TestCorrelationIDInLogs:
    """Tests for correlation ID integration in logs."""
    
    def test_audit_logger_uses_correlation_id(self):
        """Test that audit logger includes correlation ID."""
        logger = AuditLogger()
        correlation_id = set_correlation_id("test-correlation-123")
        
        with patch.object(logger.logger, 'info') as mock_info:
            logger.log_intent_received(
                intent_id="intent-123",
                user_id="user-456",
                raw_text="Test intent"
            )
            
            call_args = mock_info.call_args
            assert call_args[1]["correlation_id"] == correlation_id
    
    def test_performance_logger_uses_correlation_id(self):
        """Test that performance logger includes correlation ID."""
        logger = PerformanceLogger()
        correlation_id = set_correlation_id("test-correlation-456")
        
        with patch.object(logger.logger, 'info') as mock_info:
            logger.log_metric(
                metric_name="test_metric",
                metric_value=100.0,
                metric_unit="ms",
                component="test_component"
            )
            
            call_args = mock_info.call_args
            assert call_args[1]["correlation_id"] == correlation_id
    
    def test_chatgpt_logger_uses_correlation_id(self):
        """Test that ChatGPT logger includes correlation ID."""
        logger = ChatGPTUsageLogger()
        correlation_id = set_correlation_id("test-correlation-789")
        
        with patch.object(logger.logger, 'info') as mock_info:
            logger.log_api_request(
                request_id="req-123",
                model="gpt-4-turbo",
                prompt_tokens=150
            )
            
            call_args = mock_info.call_args
            assert call_args[1]["correlation_id"] == correlation_id
