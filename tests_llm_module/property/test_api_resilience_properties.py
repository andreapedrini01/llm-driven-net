"""Property-based tests for API resilience."""

import pytest
import asyncio
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import Mock, AsyncMock, patch

from llm_integration_module.services.chatgpt_client import (
    ChatGPTClient,
    ChatGPTConfig,
    ChatGPTResponse,
    RateLimitInfo,
    BudgetAlert
)
from openai import RateLimitError, APITimeoutError, APIConnectionError, OpenAIError


class TestAPIResilienceProperties:
    """Property-based tests for API resilience."""
    
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
    
    # Generator strategies for test data
    @staticmethod
    @st.composite
    def api_error_scenario(draw):
        """Generate API error scenarios."""
        error_types = ['rate_limit', 'timeout', 'connection', 'generic']
        error_type = draw(st.sampled_from(error_types))
        
        # Number of consecutive failures before success
        failure_count = draw(st.integers(min_value=1, max_value=5))
        
        # Whether the request eventually succeeds
        eventually_succeeds = draw(st.booleans())
        
        return {
            'error_type': error_type,
            'failure_count': failure_count,
            'eventually_succeeds': eventually_succeeds
        }
    
    @staticmethod
    @st.composite
    def rate_limit_scenario(draw):
        """Generate rate limit scenarios."""
        # Number of requests to make
        request_count = draw(st.integers(min_value=5, max_value=20))
        
        # Rate limit (requests per minute)
        rate_limit = draw(st.integers(min_value=3, max_value=10))
        
        return {
            'request_count': request_count,
            'rate_limit': rate_limit
        }
    
    @staticmethod
    def create_mock_response(content: str = "Test response") -> Mock:
        """Create a mock OpenAI API response."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = content
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "gpt-4-turbo"
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 100
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 50
        return mock_response
    
    @staticmethod
    def create_rate_limit_error() -> RateLimitError:
        """Create a mock rate limit error."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_body = {"error": {"message": "Rate limit exceeded"}}
        return RateLimitError("Rate limit exceeded", response=mock_response, body=mock_body)
    
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow], deadline=10000)
    @given(scenario=api_error_scenario())
    def test_api_resilience_with_retries(self, scenario):
        """
        **Feature: llm-integration-module, Property 22: API resilience**
        
        For any situation where ChatGPT API is temporarily unavailable or rate-limited,
        the system should implement retry logic and eventually operate in degraded mode
        while maintaining essential functionality.
        
        **Validates: Requirements 6.1, 6.2**
        """
        client = ChatGPTClient(config=self.mock_config)
        
        error_type = scenario['error_type']
        failure_count = scenario['failure_count']
        eventually_succeeds = scenario['eventually_succeeds']
        
        # Assume reasonable failure counts for testing
        # Generic errors are not retried, so they can't eventually succeed through retries
        if error_type == 'generic':
            assume(not eventually_succeeds or failure_count == 1)
        else:
            assume(failure_count <= self.mock_config.max_retries or eventually_succeeds)
        
        # Create appropriate error based on type
        if error_type == 'rate_limit':
            error = self.create_rate_limit_error()
        elif error_type == 'timeout':
            error = APITimeoutError("Request timeout")
        elif error_type == 'connection':
            error = APIConnectionError(message="Connection error.", request=Mock())
        else:
            error = OpenAIError("Generic API error")
        
        # Set up mock to fail N times then succeed (or always fail)
        mock_response = self.create_mock_response()
        
        if eventually_succeeds and failure_count < self.mock_config.max_retries:
            # Fail N times, then succeed
            side_effects = [error] * failure_count + [mock_response]
        else:
            # Always fail - need enough failures for all retry attempts
            side_effects = [error] * (self.mock_config.max_retries + 1)
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = side_effects
            
            with patch.object(asyncio, 'sleep', new_callable=AsyncMock):
                if eventually_succeeds and failure_count < self.mock_config.max_retries:
                    # Should eventually succeed
                    response = asyncio.run(client.generate_response("Test prompt"))
                    
                    # Verify response is valid
                    assert isinstance(response, ChatGPTResponse)
                    assert response.content == "Test response"
                    assert response.tokens_used > 0
                    
                    # Verify retry logic was used
                    assert mock_request.call_count == failure_count + 1
                    
                    # Verify consecutive failures reset after success
                    assert client._consecutive_failures == 0
                    
                    # Verify last successful request was updated
                    assert client._last_successful_request is not None
                    assert (datetime.now() - client._last_successful_request).total_seconds() < 1
                    
                    # Verify client is still available
                    assert client.is_available() is True
                    
                else:
                    # Should fail after max retries
                    with pytest.raises((RateLimitError, APITimeoutError, APIConnectionError, OpenAIError)):
                        asyncio.run(client.generate_response("Test prompt"))
                    
                    # Verify all retries were attempted (for retryable errors)
                    # Generic errors are not retried, only specific API errors
                    if error_type in ['rate_limit', 'timeout', 'connection']:
                        assert mock_request.call_count == self.mock_config.max_retries
                    else:
                        # Generic OpenAIError is not retried
                        assert mock_request.call_count == 1
                    
                    # Verify consecutive failures tracked
                    assert client._consecutive_failures > 0
                    
                    # After many failures, client should report unavailable
                    if client._consecutive_failures >= 5:
                        assert client.is_available() is False
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=10000)
    @given(scenario=api_error_scenario())
    def test_exponential_backoff_behavior(self, scenario):
        """Test that exponential backoff is applied correctly during retries."""
        async def run_test():
            client = ChatGPTClient(config=self.mock_config)
            
            error_type = scenario['error_type']
            failure_count = min(scenario['failure_count'], self.mock_config.max_retries)
            
            # Only test retryable errors
            assume(error_type in ['rate_limit', 'timeout', 'connection'])
            
            # Create appropriate error
            if error_type == 'rate_limit':
                error = self.create_rate_limit_error()
            elif error_type == 'timeout':
                error = APITimeoutError("Request timeout")
            else:
                error = APIConnectionError(message="Connection error.", request=Mock())
            
            # Set up mock to always fail
            with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
                mock_request.side_effect = error
                
                sleep_times = []
                
                async def track_sleep(duration):
                    sleep_times.append(duration)
                
                with patch.object(asyncio, 'sleep', new_callable=AsyncMock) as mock_sleep:
                    mock_sleep.side_effect = track_sleep
                    
                    with pytest.raises((RateLimitError, APITimeoutError, APIConnectionError)):
                        await client.generate_response("Test prompt")
                    
                    # Verify exponential backoff was applied
                    if len(sleep_times) > 0:
                        # First wait should be base wait time (1.0s)
                        assert sleep_times[0] == pytest.approx(1.0, rel=0.1)
                        
                        # Each subsequent wait should be approximately double the previous
                        for i in range(1, len(sleep_times)):
                            expected = min(1.0 * (2 ** i), 60.0)
                            assert sleep_times[i] == pytest.approx(expected, rel=0.1)
                        
                        # Verify backoff doesn't exceed max wait time
                        assert all(t <= 60.0 for t in sleep_times)
        
        asyncio.run(run_test())
    
    @settings(max_examples=15, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    @given(scenario=rate_limit_scenario())
    def test_rate_limiting_enforcement(self, scenario):
        """Test that rate limiting is properly enforced."""
        async def run_test():
            request_count = scenario['request_count']
            rate_limit = scenario['rate_limit']
            
            # Create config with specific rate limit
            config = ChatGPTConfig(
                api_key="test-api-key",
                model="gpt-4-turbo",
                max_tokens=1000,
                temperature=0.1,
                rate_limit_rpm=rate_limit,
                timeout=30,
                max_retries=3
            )
            
            client = ChatGPTClient(config=config)
            mock_response = self.create_mock_response()
            
            with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response
                
                # Mock asyncio.sleep to avoid real delays
                with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                    start_time = datetime.now()
                    
                    # Make multiple requests
                    for i in range(request_count):
                        await client.generate_response(f"Request {i}")
                    
                    elapsed_time = (datetime.now() - start_time).total_seconds()
                    
                    # Verify all requests completed
                    assert mock_request.call_count == request_count
                    
                    # If we exceeded rate limit, sleep should have been called
                    if request_count > rate_limit:
                        # Should have been throttled
                        assert mock_sleep.call_count > 0
                        # Verify sleep was called with reasonable wait times
                        for call in mock_sleep.call_args_list:
                            wait_time = call[0][0]
                            assert 0 < wait_time <= 60  # Should wait up to 60 seconds
                    
                    # Verify rate limit info is updated
                    rate_info = client.get_rate_limit_status()
                    assert isinstance(rate_info, RateLimitInfo)
                    # remaining_requests can be negative when over limit
                    assert rate_info.remaining_requests <= rate_limit
        
        asyncio.run(run_test())
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=10000)
    @given(
        failure_count=st.integers(min_value=1, max_value=10),
        time_since_success=st.integers(min_value=0, max_value=600)
    )
    def test_availability_detection(self, failure_count, time_since_success):
        """Test that API availability is correctly detected based on failure patterns."""
        client = ChatGPTClient(config=self.mock_config)
        
        # Set consecutive failures
        client._consecutive_failures = failure_count
        
        # Set last successful request time
        if time_since_success > 0:
            client._last_successful_request = datetime.now() - timedelta(seconds=time_since_success)
        else:
            client._last_successful_request = datetime.now()
        
        # Check availability
        is_available = client.is_available()
        
        # Verify availability logic
        if failure_count >= 5:
            # Too many consecutive failures
            assert is_available is False
        elif time_since_success > 300:  # 5 minutes
            # Last success too long ago
            assert is_available is False
        else:
            # Should be available
            assert is_available is True
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=10000)
    @given(
        num_requests=st.integers(min_value=1, max_value=10),
        tokens_per_request=st.integers(min_value=100, max_value=2000)
    )
    def test_cost_tracking_and_budget_alerts(self, num_requests, tokens_per_request):
        """Test that costs are tracked and budget alerts are triggered appropriately."""
        # Set low thresholds for testing
        config = ChatGPTConfig(
            api_key="test-api-key",
            model="gpt-4-turbo",
            max_tokens=1000,
            temperature=0.1,
            rate_limit_rpm=60,
            timeout=30,
            max_retries=3,
            budget_warning_threshold=0.05,
            budget_critical_threshold=0.10
        )
        
        client = ChatGPTClient(config=config)
        
        # Track alerts
        alerts_received = []
        
        def alert_callback(alert: BudgetAlert):
            alerts_received.append(alert)
        
        client.register_alert_callback(alert_callback)
        
        # Create mock response with specific token usage
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "gpt-4-turbo"
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = tokens_per_request
        mock_response.usage.prompt_tokens = tokens_per_request // 2
        mock_response.usage.completion_tokens = tokens_per_request // 2
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            # Make requests
            for i in range(num_requests):
                asyncio.run(client.generate_response(f"Request {i}"))
            
            # Verify cost tracking
            stats = client.get_stats()
            assert stats["total_requests"] == num_requests
            assert stats["total_tokens"] == num_requests * tokens_per_request
            assert stats["total_cost"] > 0
            
            # Calculate expected cost
            expected_cost = client._estimate_cost(
                tokens_per_request // 2,
                tokens_per_request // 2
            ) * num_requests
            
            assert stats["total_cost"] == pytest.approx(expected_cost, rel=0.01)
            
            # Check if alerts were triggered based on cost
            if stats["total_cost"] >= config.budget_warning_threshold:
                assert len(alerts_received) > 0
                assert any(alert.alert_type == "warning" for alert in alerts_received)
                assert stats["warning_threshold_reached"] is True
            
            if stats["total_cost"] >= config.budget_critical_threshold:
                assert any(alert.alert_type == "critical" for alert in alerts_received)
                assert stats["critical_threshold_reached"] is True
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=10000)
    @given(
        queue_size=st.integers(min_value=1, max_value=10),
        max_queue_size=st.integers(min_value=5, max_value=20)
    )
    def test_request_queuing_under_load(self, queue_size, max_queue_size):
        """Test that request queuing works correctly under load."""
        assume(queue_size <= max_queue_size)
        
        async def run_test():
            config = ChatGPTConfig(
                api_key="test-api-key",
                model="gpt-4-turbo",
                max_tokens=1000,
                temperature=0.1,
                rate_limit_rpm=60,
                timeout=30,
                max_retries=3,
                max_queue_size=max_queue_size
            )
            
            client = ChatGPTClient(config=config)
            mock_response = self.create_mock_response()
            
            with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_response
                
                # Enqueue multiple requests
                tasks = []
                for i in range(queue_size):
                    task = asyncio.create_task(
                        client.enqueue_request(f"Request {i}", priority=i)
                    )
                    tasks.append(task)
                
                # Wait for all to complete
                responses = await asyncio.gather(*tasks)
                
                # Verify all requests completed successfully
                assert len(responses) == queue_size
                assert all(isinstance(r, ChatGPTResponse) for r in responses)
                assert all(r.content == "Test response" for r in responses)
                
                # Verify queue is empty after processing
                assert client.get_queue_size() == 0
        
        asyncio.run(run_test())
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=10000)
    @given(
        initial_failures=st.integers(min_value=1, max_value=10)
    )
    def test_recovery_after_failures(self, initial_failures):
        """Test that the system recovers properly after a series of failures."""
        client = ChatGPTClient(config=self.mock_config)
        
        # Simulate initial failures
        error = self.create_rate_limit_error()
        mock_response = self.create_mock_response()
        
        # Fail N times, then succeed
        side_effects = [error] * min(initial_failures, self.mock_config.max_retries - 1) + [mock_response]
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = side_effects
            
            with patch.object(asyncio, 'sleep', new_callable=AsyncMock):
                # First request should succeed after retries
                response = asyncio.run(client.generate_response("Test prompt"))
                
                assert isinstance(response, ChatGPTResponse)
                assert response.content == "Test response"
                
                # Verify recovery
                assert client._consecutive_failures == 0
                assert client._last_successful_request is not None
                assert client.is_available() is True
                
                # Verify stats show recovery
                stats = client.get_stats()
                assert stats["total_requests"] == 1
                assert stats["consecutive_failures"] == 0
                assert stats["is_available"] is True
    
    def test_degraded_mode_operation(self):
        """Test that essential functionality is maintained in degraded mode."""
        client = ChatGPTClient(config=self.mock_config)
        
        # Simulate degraded state (many consecutive failures)
        client._consecutive_failures = 10
        client._last_successful_request = datetime.now() - timedelta(minutes=10)
        
        # Verify client reports unavailable
        assert client.is_available() is False
        
        # Verify stats are still accessible (essential functionality)
        stats = client.get_stats()
        assert isinstance(stats, dict)
        assert "is_available" in stats
        assert stats["is_available"] is False
        
        # Verify rate limit info is still accessible
        rate_info = client.get_rate_limit_status()
        assert isinstance(rate_info, RateLimitInfo)
        
        # Verify budget tracking is still functional
        alerts = client.get_budget_alerts()
        assert isinstance(alerts, list)
        
        # Verify queue size can still be checked
        queue_size = client.get_queue_size()
        assert isinstance(queue_size, int)
        assert queue_size >= 0
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=10000)
    @given(
        error_type=st.sampled_from(['rate_limit', 'timeout', 'connection'])
    )
    def test_different_error_types_handled_consistently(self, error_type):
        """Test that different error types are handled with consistent retry logic."""
        client = ChatGPTClient(config=self.mock_config)
        
        # Create appropriate error
        if error_type == 'rate_limit':
            error = self.create_rate_limit_error()
        elif error_type == 'timeout':
            error = APITimeoutError("Request timeout")
        else:
            error = APIConnectionError(message="Connection error.", request=Mock())
        
        mock_response = self.create_mock_response()
        
        # Fail once, then succeed
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [error, mock_response]
            
            with patch.object(asyncio, 'sleep', new_callable=AsyncMock):
                response = asyncio.run(client.generate_response("Test prompt"))
                
                # All error types should be retried and eventually succeed
                assert isinstance(response, ChatGPTResponse)
                assert response.content == "Test response"
                assert mock_request.call_count == 2
                
                # Verify recovery after error
                assert client._consecutive_failures == 0
                assert client.is_available() is True
