"""Tests for ChatGPT API client."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from src.services.chatgpt_client import (
    ChatGPTClient,
    ChatGPTConfig,
    ChatGPTResponse,
    RateLimitInfo,
    BudgetAlert
)
from openai import RateLimitError, APITimeoutError, APIConnectionError


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    return ChatGPTConfig(
        api_key="test-api-key",
        model="gpt-4-turbo",
        max_tokens=1000,
        temperature=0.1,
        rate_limit_rpm=60,
        timeout=30,
        max_retries=3
    )


@pytest.fixture
def mock_openai_response():
    """Create a mock OpenAI API response."""
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "Test response"
    mock_response.choices[0].finish_reason = "stop"
    mock_response.model = "gpt-4-turbo"
    mock_response.usage = Mock()
    mock_response.usage.total_tokens = 100
    mock_response.usage.prompt_tokens = 50
    mock_response.usage.completion_tokens = 50
    return mock_response


@pytest.mark.asyncio
class TestChatGPTClient:
    """Test suite for ChatGPT client."""
    
    async def test_client_initialization(self, mock_config):
        """Test client initializes correctly."""
        client = ChatGPTClient(config=mock_config)
        
        assert client.config.model == "gpt-4-turbo"
        assert client.config.max_tokens == 1000
        assert client._total_requests == 0
        assert client._total_tokens == 0
        assert client._consecutive_failures == 0
    
    async def test_generate_response_success(self, mock_config, mock_openai_response):
        """Test successful response generation."""
        client = ChatGPTClient(config=mock_config)
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_openai_response
            
            response = await client.generate_response("Test prompt")
            
            assert isinstance(response, ChatGPTResponse)
            assert response.content == "Test response"
            assert response.model == "gpt-4-turbo"
            assert response.tokens_used == 100
            assert response.finish_reason == "stop"
            assert client._total_requests == 1
            assert client._total_tokens == 100
    
    async def test_generate_response_with_context(self, mock_config, mock_openai_response):
        """Test response generation with context."""
        client = ChatGPTClient(config=mock_config)
        
        context = {
            "network_state": "active",
            "topology": "mesh"
        }
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_openai_response
            
            response = await client.generate_response(
                "Test prompt",
                context=context
            )
            
            assert response.content == "Test response"
            # Verify context was included in the request
            call_args = mock_request.call_args[0][0]
            assert any("Context:" in msg["content"] for msg in call_args)
    
    async def test_generate_response_with_system_message(self, mock_config, mock_openai_response):
        """Test response generation with system message."""
        client = ChatGPTClient(config=mock_config)
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_openai_response
            
            response = await client.generate_response(
                "Test prompt",
                system_message="You are a network expert"
            )
            
            assert response.content == "Test response"
            # Verify system message was included
            call_args = mock_request.call_args[0][0]
            assert call_args[0]["role"] == "system"
            assert "network expert" in call_args[0]["content"]
    
    async def test_retry_on_rate_limit(self, mock_config, mock_openai_response):
        """Test retry logic on rate limit error."""
        client = ChatGPTClient(config=mock_config)
        
        # Create proper mock response and body for RateLimitError
        mock_response = Mock()
        mock_response.status_code = 429
        mock_body = {"error": {"message": "Rate limit exceeded"}}
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            # First call raises rate limit, second succeeds
            mock_request.side_effect = [
                RateLimitError("Rate limit exceeded", response=mock_response, body=mock_body),
                mock_openai_response
            ]
            
            with patch.object(asyncio, 'sleep', new_callable=AsyncMock):
                response = await client.generate_response("Test prompt")
            
            assert response.content == "Test response"
            assert mock_request.call_count == 2
            assert client._consecutive_failures == 0  # Reset after success
    
    async def test_retry_on_timeout(self, mock_config, mock_openai_response):
        """Test retry logic on timeout error."""
        client = ChatGPTClient(config=mock_config)
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            # First call times out, second succeeds
            mock_request.side_effect = [
                APITimeoutError("Request timeout"),
                mock_openai_response
            ]
            
            with patch.object(asyncio, 'sleep', new_callable=AsyncMock):
                response = await client.generate_response("Test prompt")
            
            assert response.content == "Test response"
            assert mock_request.call_count == 2
    
    async def test_retry_on_connection_error(self, mock_config, mock_openai_response):
        """Test retry logic on connection error."""
        client = ChatGPTClient(config=mock_config)
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            # First call fails connection, second succeeds
            # APIConnectionError takes request parameter
            mock_request.side_effect = [
                APIConnectionError(request=Mock()),
                mock_openai_response
            ]
            
            with patch.object(asyncio, 'sleep', new_callable=AsyncMock):
                response = await client.generate_response("Test prompt")
            
            assert response.content == "Test response"
            assert mock_request.call_count == 2
    
    async def test_max_retries_exhausted(self, mock_config):
        """Test behavior when max retries are exhausted."""
        client = ChatGPTClient(config=mock_config)
        
        # Create proper mock response and body for RateLimitError
        mock_response = Mock()
        mock_response.status_code = 429
        mock_body = {"error": {"message": "Rate limit exceeded"}}
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            # All attempts fail
            mock_request.side_effect = RateLimitError("Rate limit exceeded", response=mock_response, body=mock_body)
            
            with patch.object(asyncio, 'sleep', new_callable=AsyncMock):
                with pytest.raises(RateLimitError):
                    await client.generate_response("Test prompt")
            
            assert mock_request.call_count == 3  # max_retries
            assert client._consecutive_failures == 3
    
    async def test_exponential_backoff(self, mock_config):
        """Test exponential backoff calculation."""
        client = ChatGPTClient(config=mock_config)
        
        # Test backoff times
        assert client._calculate_backoff(0) == 1.0
        assert client._calculate_backoff(1) == 2.0
        assert client._calculate_backoff(2) == 4.0
        assert client._calculate_backoff(3) == 8.0
        assert client._calculate_backoff(10) == 60.0  # Max wait
    
    async def test_rate_limiting(self, mock_config, mock_openai_response):
        """Test rate limiting enforcement."""
        # Set very low rate limit for testing
        mock_config.rate_limit_rpm = 2
        client = ChatGPTClient(config=mock_config)
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_openai_response
            
            # Make requests up to the limit
            await client.generate_response("Request 1")
            await client.generate_response("Request 2")
            
            # Next request should trigger rate limiting
            rate_limit_info = client.get_rate_limit_status()
            assert rate_limit_info.remaining_requests == 0
    
    async def test_cost_estimation(self, mock_config):
        """Test cost estimation for different models."""
        client = ChatGPTClient(config=mock_config)
        
        # Test GPT-4-turbo cost
        cost = client._estimate_cost(1000, 1000)
        assert cost > 0
        assert cost == pytest.approx(0.04, rel=0.01)  # ~$0.04 for 2K tokens
        
        # Test with different token counts
        cost_small = client._estimate_cost(100, 100)
        cost_large = client._estimate_cost(10000, 10000)
        assert cost_small < cost_large
    
    def test_is_available_initial(self, mock_config):
        """Test availability check on new client."""
        client = ChatGPTClient(config=mock_config)
        assert client.is_available() is True
    
    def test_is_available_after_failures(self, mock_config):
        """Test availability check after consecutive failures."""
        client = ChatGPTClient(config=mock_config)
        
        # Simulate failures
        client._consecutive_failures = 5
        assert client.is_available() is False
        
        # Reset failures
        client._consecutive_failures = 0
        assert client.is_available() is True
    
    def test_is_available_stale_success(self, mock_config):
        """Test availability check with stale last success."""
        client = ChatGPTClient(config=mock_config)
        
        # Set last success to long ago
        client._last_successful_request = datetime.now() - timedelta(minutes=10)
        assert client.is_available() is False
        
        # Set recent success
        client._last_successful_request = datetime.now()
        assert client.is_available() is True
    
    def test_get_stats(self, mock_config):
        """Test statistics retrieval."""
        client = ChatGPTClient(config=mock_config)
        
        # Set some stats
        client._total_requests = 10
        client._total_tokens = 5000
        client._total_cost = 0.25
        
        stats = client.get_stats()
        
        assert stats["total_requests"] == 10
        assert stats["total_tokens"] == 5000
        assert stats["total_cost"] == 0.25
        assert "rate_limit_info" in stats
        assert "is_available" in stats
    
    def test_format_context(self, mock_config):
        """Test context formatting."""
        client = ChatGPTClient(config=mock_config)
        
        context = {
            "key1": "value1",
            "key2": "value2"
        }
        
        formatted = client._format_context(context)
        
        assert "Context:" in formatted
        assert "key1: value1" in formatted
        assert "key2: value2" in formatted


@pytest.mark.asyncio
class TestChatGPTClientIntegration:
    """Integration tests for ChatGPT client (requires API key)."""
    
    @pytest.mark.skip(reason="Requires valid API key and makes real API calls")
    async def test_real_api_call(self):
        """Test real API call (skipped by default)."""
        config = ChatGPTConfig(
            api_key="your-api-key-here",
            model="gpt-3.5-turbo",  # Use cheaper model for testing
            max_tokens=50
        )
        
        client = ChatGPTClient(config=config)
        response = await client.generate_response("Say 'test successful'")
        
        assert response.content
        assert response.tokens_used > 0
        assert response.latency > 0


@pytest.mark.asyncio
class TestRateLimitingAndRetry:
    """Test suite for rate limiting and retry logic (Task 6.3)."""
    
    async def test_request_queue_basic(self, mock_config, mock_openai_response):
        """Test basic request queuing functionality."""
        client = ChatGPTClient(config=mock_config)
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_openai_response
            
            # Enqueue a request
            response = await client.enqueue_request("Test prompt")
            
            assert isinstance(response, ChatGPTResponse)
            assert response.content == "Test response"
    
    async def test_request_queue_priority(self, mock_config, mock_openai_response):
        """Test priority-based request queuing."""
        client = ChatGPTClient(config=mock_config)
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_openai_response
            
            # Enqueue multiple requests with different priorities
            # Don't await immediately to test queue ordering
            task1 = asyncio.create_task(client.enqueue_request("Low priority", priority=1))
            task2 = asyncio.create_task(client.enqueue_request("High priority", priority=10))
            task3 = asyncio.create_task(client.enqueue_request("Medium priority", priority=5))
            
            # Wait for all to complete
            await asyncio.gather(task1, task2, task3)
            
            # All should succeed
            assert task1.result().content == "Test response"
            assert task2.result().content == "Test response"
            assert task3.result().content == "Test response"
    
    async def test_request_queue_full(self, mock_config):
        """Test behavior when request queue is full."""
        mock_config.max_queue_size = 2
        client = ChatGPTClient(config=mock_config)
        
        # Fill the queue by not processing it
        client._processing_queue = True  # Prevent processing
        
        with patch.object(client, '_make_request', new_callable=AsyncMock):
            # Add requests to fill queue
            task1 = asyncio.create_task(client.enqueue_request("Request 1"))
            task2 = asyncio.create_task(client.enqueue_request("Request 2"))
            
            # Give tasks time to enqueue
            await asyncio.sleep(0.1)
            
            # Next request should raise ValueError
            with pytest.raises(ValueError, match="Request queue is full"):
                await client.enqueue_request("Request 3")
    
    async def test_get_queue_size(self, mock_config):
        """Test queue size tracking."""
        client = ChatGPTClient(config=mock_config)
        
        assert client.get_queue_size() == 0
        
        # Prevent processing to test queue size
        client._processing_queue = True
        
        # Add requests
        asyncio.create_task(client.enqueue_request("Request 1"))
        await asyncio.sleep(0.1)
        
        assert client.get_queue_size() == 1
    
    async def test_budget_warning_alert(self, mock_config, mock_openai_response):
        """Test budget warning threshold alert."""
        mock_config.budget_warning_threshold = 0.05  # Very low for testing
        mock_config.budget_critical_threshold = 0.10
        client = ChatGPTClient(config=mock_config)
        
        alert_triggered = []
        
        def alert_callback(alert: BudgetAlert):
            alert_triggered.append(alert)
        
        client.register_alert_callback(alert_callback)
        
        # Create a proper mock response with token usage
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "gpt-4-turbo"
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 1000  # Large token count
        mock_response.usage.prompt_tokens = 500
        mock_response.usage.completion_tokens = 500
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            # Make enough requests to trigger warning
            for _ in range(10):
                await client.generate_response("Test prompt")
            
            # Check if warning was triggered
            assert len(alert_triggered) > 0
            assert any(alert.alert_type == "warning" for alert in alert_triggered)
    
    async def test_budget_critical_alert(self, mock_config, mock_openai_response):
        """Test budget critical threshold alert."""
        mock_config.budget_warning_threshold = 0.05
        mock_config.budget_critical_threshold = 0.10
        client = ChatGPTClient(config=mock_config)
        
        alert_triggered = []
        
        def alert_callback(alert: BudgetAlert):
            alert_triggered.append(alert)
        
        client.register_alert_callback(alert_callback)
        
        # Create a proper mock response with token usage
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "gpt-4-turbo"
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 1000  # Large token count
        mock_response.usage.prompt_tokens = 500
        mock_response.usage.completion_tokens = 500
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            # Make enough requests to trigger critical alert
            for _ in range(20):
                await client.generate_response("Test prompt")
            
            # Check if critical alert was triggered
            assert len(alert_triggered) > 0
            assert any(alert.alert_type == "critical" for alert in alert_triggered)
    
    async def test_get_budget_alerts(self, mock_config, mock_openai_response):
        """Test retrieving budget alerts."""
        mock_config.budget_warning_threshold = 0.05
        client = ChatGPTClient(config=mock_config)
        
        # Create a proper mock response with token usage
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "gpt-4-turbo"
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 1000  # Large token count
        mock_response.usage.prompt_tokens = 500
        mock_response.usage.completion_tokens = 500
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            # Initially no alerts
            assert len(client.get_budget_alerts()) == 0
            
            # Make requests to trigger alert
            for _ in range(10):
                await client.generate_response("Test prompt")
            
            # Should have alerts now
            alerts = client.get_budget_alerts()
            assert len(alerts) > 0
            assert all(isinstance(alert, BudgetAlert) for alert in alerts)
    
    async def test_reset_budget_tracking(self, mock_config, mock_openai_response):
        """Test resetting budget tracking."""
        mock_config.budget_warning_threshold = 0.05
        client = ChatGPTClient(config=mock_config)
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_openai_response
            
            # Make some requests
            for _ in range(5):
                await client.generate_response("Test prompt")
            
            # Verify cost accumulated
            assert client._total_cost > 0
            assert client._total_tokens > 0
            
            # Reset tracking
            client.reset_budget_tracking()
            
            # Verify reset
            assert client._total_cost == 0.0
            assert client._total_tokens == 0
            assert len(client.get_budget_alerts()) == 0
            assert not client._warning_threshold_reached
            assert not client._critical_threshold_reached
    
    async def test_multiple_alert_callbacks(self, mock_config, mock_openai_response):
        """Test multiple alert callbacks can be registered."""
        mock_config.budget_warning_threshold = 0.05
        client = ChatGPTClient(config=mock_config)
        
        callback1_triggered = []
        callback2_triggered = []
        
        def callback1(alert: BudgetAlert):
            callback1_triggered.append(alert)
        
        def callback2(alert: BudgetAlert):
            callback2_triggered.append(alert)
        
        client.register_alert_callback(callback1)
        client.register_alert_callback(callback2)
        
        # Create a proper mock response with token usage
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "gpt-4-turbo"
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 1000  # Large token count
        mock_response.usage.prompt_tokens = 500
        mock_response.usage.completion_tokens = 500
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            # Trigger alert
            for _ in range(10):
                await client.generate_response("Test prompt")
            
            # Both callbacks should be triggered
            assert len(callback1_triggered) > 0
            assert len(callback2_triggered) > 0
            assert len(callback1_triggered) == len(callback2_triggered)
    
    async def test_stats_include_queue_and_budget(self, mock_config):
        """Test that stats include queue size and budget information."""
        client = ChatGPTClient(config=mock_config)
        
        stats = client.get_stats()
        
        assert "queue_size" in stats
        assert "budget_alerts" in stats
        assert "warning_threshold_reached" in stats
        assert "critical_threshold_reached" in stats
        assert stats["queue_size"] == 0
        assert stats["budget_alerts"] == 0
        assert stats["warning_threshold_reached"] is False
        assert stats["critical_threshold_reached"] is False
    
    async def test_rate_limit_with_queue(self, mock_config, mock_openai_response):
        """Test that queued requests respect rate limits."""
        mock_config.rate_limit_rpm = 5
        client = ChatGPTClient(config=mock_config)
        
        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_openai_response
            
            # Enqueue multiple requests
            tasks = [
                asyncio.create_task(client.enqueue_request(f"Request {i}"))
                for i in range(3)
            ]
            
            # All should complete successfully
            responses = await asyncio.gather(*tasks)
            assert len(responses) == 3
            assert all(isinstance(r, ChatGPTResponse) for r in responses)
    
    async def test_exponential_backoff_with_jitter(self, mock_config):
        """Test exponential backoff calculation."""
        client = ChatGPTClient(config=mock_config)
        
        # Test that backoff increases exponentially
        backoff_0 = client._calculate_backoff(0)
        backoff_1 = client._calculate_backoff(1)
        backoff_2 = client._calculate_backoff(2)
        
        assert backoff_1 > backoff_0
        assert backoff_2 > backoff_1
        assert backoff_1 == backoff_0 * 2
        assert backoff_2 == backoff_0 * 4
        
        # Test max backoff cap
        backoff_large = client._calculate_backoff(100)
        assert backoff_large == 60.0  # Max wait time
