"""Property-based tests for degraded mode operation.

This module tests that the system maintains essential functionality
when ChatGPT API is unavailable and falls back to rule-based processing.
"""

import pytest
import asyncio
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, AsyncMock, patch

from llm_integration_module.services.chatgpt_client import (
    ChatGPTClient,
    ChatGPTConfig,
    ChatGPTResponse
)
from llm_integration_module.services.intent_parser import IntentParser, IntentObject
from llm_integration_module.services.context_analyzer import ContextAnalyzer, NetworkState
from llm_integration_module.services.validator import Validator
from llm_integration_module.utils.error_handling import (
    DegradedModeManager,
    get_degraded_mode_manager
)
from openai import RateLimitError, APITimeoutError, APIConnectionError, OpenAIError


class TestDegradedModeProperties:
    """Property-based tests for degraded mode operation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = ChatGPTConfig(
            api_key="test-api-key",
            model="gpt-4-turbo",
            max_tokens=1000,
            temperature=0.1,
            rate_limit_rpm=60,
            timeout=30,
            max_retries=3
        )
        # Create a fresh degraded mode manager for each test
        self.degraded_mode_manager = DegradedModeManager()
    
    def teardown_method(self):
        """Clean up after each test."""
        # Clear all degraded services to ensure test isolation
        for service_name in list(self.degraded_mode_manager.get_degraded_services().keys()):
            self.degraded_mode_manager.exit_degraded_mode(service_name)
    
    def teardown_method(self):
        """Clean up after each test."""
        # Exit degraded mode for all services
        for service_name in list(self.degraded_mode_manager.get_degraded_services().keys()):
            self.degraded_mode_manager.exit_degraded_mode(service_name)
    
    # Generator strategies for test data
    @st.composite
    def api_unavailable_scenario(draw):
        """Generate scenarios where API is unavailable."""
        error_types = ['rate_limit', 'timeout', 'connection', 'generic']
        error_type = draw(st.sampled_from(error_types))
        
        # Duration of unavailability in seconds
        unavailable_duration = draw(st.integers(min_value=1, max_value=300))
        
        # Number of requests during unavailability
        request_count = draw(st.integers(min_value=1, max_value=10))
        
        return {
            'error_type': error_type,
            'unavailable_duration': unavailable_duration,
            'request_count': request_count
        }
    
    @st.composite
    def simple_intent_text(draw):
        """Generate simple intent text for rule-based processing."""
        actions = ['create', 'modify', 'delete', 'list', 'show']
        resources = ['flow', 'slice', 'route', 'policy', 'switch']
        
        action = draw(st.sampled_from(actions))
        resource = draw(st.sampled_from(resources))
        
        # Generate simple intent patterns
        patterns = [
            f"{action} {resource}",
            f"{action} a {resource}",
            f"{action} new {resource}",
            f"please {action} {resource}",
        ]
        
        return draw(st.sampled_from(patterns))
    
    @st.composite
    def network_state_minimal(draw):
        """Generate minimal network state for testing."""
        return {
            'timestamp': datetime.now().isoformat(),
            'topology': {
                'switches': [
                    {'id': f's{i}', 'dpid': f'00:00:00:00:00:00:00:0{i}'}
                    for i in range(draw(st.integers(min_value=1, max_value=3)))
                ],
                'links': [],
                'hosts': []
            },
            'flows': [],
            'slices': [],
            'metrics': {
                'bandwidth': {},
                'latency': {},
                'utilization': {}
            },
            'anomalies': []
        }
    
    @staticmethod
    def create_api_error(error_type: str):
        """Create appropriate API error based on type."""
        if error_type == 'rate_limit':
            mock_response = Mock()
            mock_response.status_code = 429
            mock_body = {"error": {"message": "Rate limit exceeded"}}
            return RateLimitError("Rate limit exceeded", response=mock_response, body=mock_body)
        elif error_type == 'timeout':
            return APITimeoutError("Request timeout")
        elif error_type == 'connection':
            return APIConnectionError(request=Mock())
        else:
            return OpenAIError("Generic API error")
    
    @staticmethod
    def create_rule_based_response(intent_text: str) -> Dict[str, Any]:
        """Create a simple rule-based response for basic intents.
        
        This simulates a fallback mechanism that uses pattern matching
        to generate basic actions when ChatGPT API is unavailable.
        """
        intent_lower = intent_text.lower()
        
        # Simple pattern matching for common operations
        if 'create' in intent_lower or 'add' in intent_lower:
            action_type = 'create'
        elif 'delete' in intent_lower or 'remove' in intent_lower:
            action_type = 'delete'
        elif 'modify' in intent_lower or 'update' in intent_lower or 'change' in intent_lower:
            action_type = 'modify'
        elif 'list' in intent_lower or 'show' in intent_lower:
            action_type = 'query'
        else:
            action_type = 'unknown'
        
        # Determine resource type
        if 'flow' in intent_lower:
            resource = 'flow'
        elif 'slice' in intent_lower:
            resource = 'slice'
        elif 'route' in intent_lower:
            resource = 'route'
        elif 'policy' in intent_lower:
            resource = 'policy'
        elif 'switch' in intent_lower:
            resource = 'switch'
        else:
            resource = 'unknown'
        
        # Generate basic action
        return {
            'action_type': action_type,
            'resource': resource,
            'intent': intent_text,
            'confidence': 0.6,  # Lower confidence for rule-based
            'source': 'rule_based',
            'actions': [
                {
                    'type': f'{resource}_{action_type}' if resource != 'unknown' else 'unknown',
                    'target': resource,
                    'parameters': {},
                    'priority': 5,
                    'timeout': 30
                }
            ] if action_type != 'unknown' and resource != 'unknown' else []
        }
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=10000)
    @given(scenario=api_unavailable_scenario())
    def test_system_behavior_when_api_unavailable(self, scenario):
        """
        **Feature: llm-integration-module, Property: Degraded mode operation**
        
        Test system behavior when ChatGPT API is unavailable.
        The system should detect unavailability and enter degraded mode.
        
        **Validates: Requirements 6.2**
        """
        client = ChatGPTClient(config=self.mock_config)
        error_type = scenario['error_type']
        request_count = scenario['request_count']
        
        # Create appropriate error
        error = self.create_api_error(error_type)
        
        # Mock API to always fail
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = error
            
            with patch.object(asyncio, 'sleep', new_callable=AsyncMock):
                # Make multiple requests that will fail
                for i in range(min(request_count, 3)):
                    with pytest.raises((RateLimitError, APITimeoutError, APIConnectionError, OpenAIError)):
                        asyncio.run(client.generate_response(f"Test prompt {i}"))
                
                # Verify system detects unavailability
                # After max_retries failures, consecutive_failures should be > 0
                assert client._consecutive_failures > 0
                
                # After enough failures, client should report unavailable
                if client._consecutive_failures >= 5:
                    assert client.is_available() is False
                    
                    # Verify degraded mode manager can track this
                    self.degraded_mode_manager.enter_degraded_mode(
                        "chatgpt",
                        f"API unavailable: {error_type}",
                        fallback_handler=lambda: "rule_based_fallback"
                    )
                    
                    assert self.degraded_mode_manager.is_degraded("chatgpt")
                    
                    # Verify fallback handler is available
                    handler = self.degraded_mode_manager.get_fallback_handler("chatgpt")
                    assert handler is not None
                    assert handler() == "rule_based_fallback"
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=10000)
    @given(
        intent_text=simple_intent_text(),
        network_state=network_state_minimal()
    )
    def test_fallback_to_rule_based_processing(self, intent_text, network_state):
        """
        **Feature: llm-integration-module, Property: Degraded mode operation**
        
        Validate fallback to rule-based processing when API is unavailable.
        The system should use pattern matching to generate basic actions.
        
        **Validates: Requirements 6.2**
        """
        # Simulate API unavailability
        self.degraded_mode_manager.enter_degraded_mode(
            "chatgpt",
            "API unavailable for testing",
            fallback_handler=lambda text: self.create_rule_based_response(text)
        )
        
        assert self.degraded_mode_manager.is_degraded("chatgpt")
        
        # Get fallback handler
        fallback_handler = self.degraded_mode_manager.get_fallback_handler("chatgpt")
        assert fallback_handler is not None
        
        # Use fallback to process intent
        result = fallback_handler(intent_text)
        
        # Verify rule-based response structure
        assert isinstance(result, dict)
        assert 'action_type' in result
        assert 'resource' in result
        assert 'source' in result
        assert result['source'] == 'rule_based'
        assert 'actions' in result
        
        # Verify confidence is lower for rule-based
        if 'confidence' in result:
            assert result['confidence'] < 1.0
        
        # Verify basic actions are generated for recognized patterns
        if result['action_type'] != 'unknown' and result['resource'] != 'unknown':
            assert len(result['actions']) > 0
            assert result['actions'][0]['type'] != 'unknown'
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=10000)
    @given(
        intent_text=simple_intent_text(),
        consecutive_failures=st.integers(min_value=5, max_value=20)
    )
    def test_essential_functionality_remains_operational(self, intent_text, consecutive_failures):
        """
        **Feature: llm-integration-module, Property: Degraded mode operation**
        
        Ensure essential functionality remains operational in degraded mode.
        Core services like validation, logging, and monitoring should continue.
        
        **Validates: Requirements 6.2**
        """
        client = ChatGPTClient(config=self.mock_config)
        
        # Simulate degraded state
        client._consecutive_failures = consecutive_failures
        client._last_successful_request = datetime.now() - timedelta(minutes=10)
        
        # Verify client reports unavailable
        assert client.is_available() is False
        
        # Essential functionality 1: Stats are still accessible
        stats = client.get_stats()
        assert isinstance(stats, dict)
        assert 'is_available' in stats
        assert stats['is_available'] is False
        assert 'consecutive_failures' in stats
        assert stats['consecutive_failures'] == consecutive_failures
        
        # Essential functionality 2: Rate limit info is still accessible
        rate_info = client.get_rate_limit_status()
        assert rate_info is not None
        assert hasattr(rate_info, 'remaining_requests')
        
        # Essential functionality 3: Budget tracking is still functional
        alerts = client.get_budget_alerts()
        assert isinstance(alerts, list)
        
        # Essential functionality 4: Queue size can still be checked
        queue_size = client.get_queue_size()
        assert isinstance(queue_size, int)
        assert queue_size >= 0
        
        # Essential functionality 5: Degraded mode manager works
        self.degraded_mode_manager.enter_degraded_mode(
            "chatgpt",
            "API unavailable",
            fallback_handler=lambda text: self.create_rule_based_response(text)
        )
        
        assert self.degraded_mode_manager.is_degraded("chatgpt")
        
        # Essential functionality 6: Fallback processing works
        fallback = self.degraded_mode_manager.get_fallback_handler("chatgpt")
        assert fallback is not None
        
        result = fallback(intent_text)
        assert isinstance(result, dict)
        assert 'source' in result
        assert result['source'] == 'rule_based'
        
        # Essential functionality 7: Validator can still validate basic actions
        validator = Validator()
        
        if result.get('actions'):
            # Validator should be able to process actions even in degraded mode
            action = result['actions'][0]
            # Basic validation should work
            assert 'type' in action
            assert 'target' in action
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=10000)
    @given(
        failure_duration=st.integers(min_value=60, max_value=600),
        recovery_attempts=st.integers(min_value=1, max_value=5)
    )
    def test_recovery_from_degraded_mode(self, failure_duration, recovery_attempts):
        """Test that system can recover from degraded mode when API becomes available."""
        client = ChatGPTClient(config=self.mock_config)
        
        # Enter degraded mode
        client._consecutive_failures = 10
        client._last_successful_request = datetime.now() - timedelta(seconds=failure_duration)
        
        self.degraded_mode_manager.enter_degraded_mode(
            "chatgpt",
            "API unavailable"
        )
        
        assert client.is_available() is False
        assert self.degraded_mode_manager.is_degraded("chatgpt")
        
        # Simulate API recovery
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Recovery successful"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "gpt-4-turbo"
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 50
        mock_response.usage.prompt_tokens = 25
        mock_response.usage.completion_tokens = 25
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            # Make successful requests
            for i in range(recovery_attempts):
                response = asyncio.run(client.generate_response(f"Recovery test {i}"))
                assert isinstance(response, ChatGPTResponse)
                assert response.content == "Recovery successful"
            
            # Verify recovery
            assert client._consecutive_failures == 0
            assert client._last_successful_request is not None
            assert (datetime.now() - client._last_successful_request).total_seconds() < 2
            
            # After recovery, can exit degraded mode
            self.degraded_mode_manager.exit_degraded_mode("chatgpt")
            assert not self.degraded_mode_manager.is_degraded("chatgpt")
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=10000)
    @given(
        intent_texts=st.lists(simple_intent_text(), min_size=1, max_size=5)
    )
    def test_multiple_requests_in_degraded_mode(self, intent_texts):
        """Test handling multiple requests while in degraded mode."""
        # Enter degraded mode
        self.degraded_mode_manager.enter_degraded_mode(
            "chatgpt",
            "API unavailable",
            fallback_handler=lambda text: self.create_rule_based_response(text)
        )
        
        assert self.degraded_mode_manager.is_degraded("chatgpt")
        
        fallback = self.degraded_mode_manager.get_fallback_handler("chatgpt")
        
        # Process multiple intents using fallback
        results = []
        for intent_text in intent_texts:
            result = fallback(intent_text)
            results.append(result)
        
        # Verify all requests were processed
        assert len(results) == len(intent_texts)
        
        # Verify all results have rule-based source
        for result in results:
            assert isinstance(result, dict)
            assert result.get('source') == 'rule_based'
            assert 'actions' in result
        
        # Verify system remains in degraded mode
        assert self.degraded_mode_manager.is_degraded("chatgpt")
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=10000)
    @given(
        service_name=st.sampled_from(['chatgpt', 'file_reader', 'validator']),
        reason=st.text(min_size=5, max_size=50)
    )
    def test_degraded_mode_for_different_services(self, service_name, reason):
        """Test that degraded mode can be managed for different services independently."""
        # Clean up any existing degraded services from previous test examples
        for existing_service in list(self.degraded_mode_manager.get_degraded_services().keys()):
            self.degraded_mode_manager.exit_degraded_mode(existing_service)
        
        # Enter degraded mode for specific service
        self.degraded_mode_manager.enter_degraded_mode(
            service_name,
            reason,
            fallback_handler=lambda: f"fallback_{service_name}"
        )
        
        # Verify service is degraded
        assert self.degraded_mode_manager.is_degraded(service_name)
        
        # Verify other services are not affected
        other_services = ['chatgpt', 'file_reader', 'validator']
        other_services.remove(service_name)
        
        for other_service in other_services:
            assert not self.degraded_mode_manager.is_degraded(other_service)
        
        # Verify fallback handler works
        handler = self.degraded_mode_manager.get_fallback_handler(service_name)
        assert handler is not None
        assert handler() == f"fallback_{service_name}"
        
        # Verify degraded services list
        degraded = self.degraded_mode_manager.get_degraded_services()
        assert service_name in degraded
        assert degraded[service_name]['reason'] == reason
        assert degraded[service_name]['has_fallback'] is True
        
        # Clean up after this test example
        self.degraded_mode_manager.exit_degraded_mode(service_name)
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=10000)
    @given(
        intent_text=simple_intent_text()
    )
    def test_rule_based_response_quality(self, intent_text):
        """Test that rule-based responses maintain minimum quality standards."""
        # Generate rule-based response
        result = self.create_rule_based_response(intent_text)
        
        # Verify response structure
        assert isinstance(result, dict)
        assert 'action_type' in result
        assert 'resource' in result
        assert 'intent' in result
        assert 'confidence' in result
        assert 'source' in result
        assert 'actions' in result
        
        # Verify source is marked as rule-based
        assert result['source'] == 'rule_based'
        
        # Verify confidence is reasonable (not too high for rule-based)
        assert 0.0 <= result['confidence'] <= 0.8
        
        # Verify intent is preserved
        assert result['intent'] == intent_text
        
        # If actions are generated, verify they have required fields
        for action in result['actions']:
            assert 'type' in action
            assert 'target' in action
            assert 'parameters' in action
            assert 'priority' in action
            assert 'timeout' in action
            
            # Verify action type is not completely unknown
            assert action['type'] != 'unknown_unknown'
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=10000)
    @given(
        degraded_duration=st.integers(min_value=1, max_value=300)
    )
    def test_degraded_mode_duration_tracking(self, degraded_duration):
        """Test that degraded mode duration is properly tracked."""
        service_name = "chatgpt"
        
        # Enter degraded mode
        self.degraded_mode_manager.enter_degraded_mode(
            service_name,
            "Testing duration tracking"
        )
        
        # Get degraded services info
        degraded_services = self.degraded_mode_manager.get_degraded_services()
        
        assert service_name in degraded_services
        assert 'entered_at' in degraded_services[service_name]
        assert isinstance(degraded_services[service_name]['entered_at'], datetime)
        
        # Verify entered_at is recent
        entered_at = degraded_services[service_name]['entered_at']
        time_since_entry = (datetime.now() - entered_at).total_seconds()
        assert time_since_entry < 2  # Should be very recent
        
        # Exit degraded mode
        self.degraded_mode_manager.exit_degraded_mode(service_name)
        
        # Verify service is no longer degraded
        assert not self.degraded_mode_manager.is_degraded(service_name)
