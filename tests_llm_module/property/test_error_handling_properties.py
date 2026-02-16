"""Property-based tests for error handling completeness.

Feature: llm-integration-module, Property 24: Error handling completeness
**Validates: Requirements 6.4**
"""

import pytest
import uuid
from datetime import datetime
from unittest.mock import patch
from hypothesis import given, strategies as st, settings, assume

from src.utils.logging import (
    AuditLogger,
    ChatGPTUsageLogger,
    set_correlation_id,
    clear_correlation_id
)
from src.utils.notifications import Alert, AlertSeverity, AlertCategory
from src.utils.alert_helpers import (
    send_system_error_alert,
    send_api_error_alert,
    send_security_alert
)


@st.composite
def error_scenario(draw):
    error_types = ["APIError", "DatabaseError", "NetworkError", "ValidationError"]
    has_context = draw(st.booleans())
    context = None
    if has_context:
        context = {"retry_count": draw(st.integers(min_value=0, max_value=5)), "operation_id": str(uuid.uuid4())}
    return {"error_type": draw(st.sampled_from(error_types)), "error_message": draw(st.text(min_size=10, max_size=200)), "component": draw(st.sampled_from(["intent_parser", "action_generator", "validator"])), "context": context}


@st.composite
def api_error_scenario(draw):
    return {"api_name": draw(st.sampled_from(["ChatGPT", "RYU Controller"])), "error_type": draw(st.sampled_from(["TimeoutError", "RateLimitError"])), "error_message": draw(st.text(min_size=10, max_size=150)), "retry_attempt": draw(st.integers(min_value=1, max_value=5))}


class TestErrorHandlingCompleteness:
    
    @given(error_scenario())
    @settings(max_examples=100, deadline=1000)
    def test_system_error_logging_completeness(self, scenario):
        audit_logger = AuditLogger()
        correlation_id = set_correlation_id()
        with patch.object(audit_logger.logger, 'error') as mock_error:
            audit_logger.log_error(error_type=scenario["error_type"], error_message=scenario["error_message"], context=scenario["context"] or {}, correlation_id=correlation_id)
            assert mock_error.called
            kwargs = mock_error.call_args[1]
            assert kwargs["error_type"] == scenario["error_type"]
            assert kwargs["error_message"] == scenario["error_message"]
            assert "context" in kwargs
            assert kwargs["correlation_id"] == correlation_id
            assert kwargs["event_type"] == "system_error"
        clear_correlation_id()
    
    @given(error_scenario())
    @settings(max_examples=100, deadline=1000)
    @pytest.mark.asyncio
    async def test_system_error_notification_completeness(self, scenario):
        with patch('src.utils.alert_helpers.notification_manager.send_alert') as mock_send:
            mock_send.return_value = {}
            await send_system_error_alert(error_type=scenario["error_type"], error_message=scenario["error_message"], component=scenario["component"], metadata=scenario["context"])
            assert mock_send.called
            call_args = mock_send.call_args[0][0]
            assert isinstance(call_args, Alert)
            assert call_args.severity == AlertSeverity.ERROR
            assert call_args.category == AlertCategory.SYSTEM_ERROR
    
    @given(api_error_scenario())
    @settings(max_examples=100, deadline=1000)
    def test_api_error_logging_completeness(self, scenario):
        chatgpt_logger = ChatGPTUsageLogger()
        request_id = str(uuid.uuid4())
        correlation_id = set_correlation_id()
        with patch.object(chatgpt_logger.logger, 'error') as mock_error:
            chatgpt_logger.log_api_error(request_id=request_id, model="gpt-4-turbo", error_type=scenario["error_type"], error_message=scenario["error_message"], retry_attempt=scenario["retry_attempt"], correlation_id=correlation_id)
            assert mock_error.called
            kwargs = mock_error.call_args[1]
            assert kwargs["request_id"] == request_id
            assert kwargs["error_type"] == scenario["error_type"]
            assert kwargs["error_message"] == scenario["error_message"]
            assert kwargs["retry_attempt"] == scenario["retry_attempt"]
            assert kwargs["correlation_id"] == correlation_id
        clear_correlation_id()
    
    @given(api_error_scenario())
    @settings(max_examples=100, deadline=1000)
    @pytest.mark.asyncio
    async def test_api_error_notification_on_final_retry(self, scenario):
        assume(scenario["retry_attempt"] >= 3)
        with patch('src.utils.alert_helpers.notification_manager.send_alert') as mock_send:
            mock_send.return_value = {}
            await send_api_error_alert(api_name=scenario["api_name"], error_type=scenario["error_type"], error_message=scenario["error_message"], retry_attempt=scenario["retry_attempt"])
            assert mock_send.called
            call_args = mock_send.call_args[0][0]
            assert isinstance(call_args, Alert)
            assert call_args.category == AlertCategory.API_ERROR


class TestErrorHandlingEdgeCases:
    
    def test_error_with_empty_message(self):
        audit_logger = AuditLogger()
        with patch.object(audit_logger.logger, 'error') as mock_error:
            audit_logger.log_error(error_type="TestError", error_message="", context={})
            assert mock_error.called
            assert "error_message" in mock_error.call_args[1]
    
    def test_error_with_none_context(self):
        audit_logger = AuditLogger()
        with patch.object(audit_logger.logger, 'error') as mock_error:
            audit_logger.log_error(error_type="TestError", error_message="Test error", context=None)
            assert mock_error.called
            assert mock_error.call_args[1]["context"] == {}
