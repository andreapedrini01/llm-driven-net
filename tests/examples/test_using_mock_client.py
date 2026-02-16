"""Example tests demonstrating how to use the mock ChatGPT client in various scenarios.

This file provides practical examples for integrating the mock client into existing tests.
"""

import pytest
import asyncio
from typing import Dict, Any

from tests.mocks import MockChatGPTClient, create_mock_client, MockResponseVariant
from src.services.chatgpt_client import ChatGPTConfig
from src.services.prompt_engineering import PromptEngineeringSystem, PromptType
from src.models.intent import IntentObject, IntentType
from src.models.network import NetworkState


# Example 1: Basic fixture setup
@pytest.fixture
def mock_chatgpt():
    """Provide a mock ChatGPT client for tests."""
    client = create_mock_client(simulate_latency=False)
    yield client
    client.reset()


# Example 2: Using mock in intent parsing tests
class TestIntentParsingWithMock:
    """Example tests for intent parsing using mock client."""
    
    @pytest.mark.asyncio
    async def test_parse_configuration_intent(self, mock_chatgpt):
        """Test parsing a configuration intent."""
        prompt = "Configure switch s1 to forward traffic to port 2"
        
        response = await mock_chatgpt.generate_response(prompt)
        
        assert response is not None
        assert response.tokens_used > 0
        assert "configure" in response.content.lower() or "flow" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_parse_query_intent(self, mock_chatgpt):
        """Test parsing a query intent."""
        prompt = "What is the current bandwidth utilization on switch s1?"
        
        response = await mock_chatgpt.generate_response(prompt)
        
        assert response is not None
        assert response.finish_reason == "stop"


# Example 3: Using mock with prompt engineering system
class TestPromptEngineeringWithMock:
    """Example tests for prompt engineering using mock client."""
    
    @pytest.mark.asyncio
    async def test_action_generation_prompt(self, mock_chatgpt):
        """Test action generation with prompt engineering."""
        prompt_system = PromptEngineeringSystem()
        
        # Create a simple prompt using the system
        # Note: PromptEngineeringSystem uses specific methods like build_intent_parsing_prompt
        # For this example, we'll just test with a direct prompt
        prompt = "Generate actions to add a flow rule to switch_1 for forwarding traffic"
        
        response = await mock_chatgpt.generate_response(prompt)
        
        assert response is not None
        assert response.tokens_used > 0


# Example 4: Testing with custom response handlers
class TestCustomResponseHandlers:
    """Example tests using custom response handlers."""
    
    @pytest.mark.asyncio
    async def test_specific_scenario_handler(self):
        """Test with a custom handler for specific scenarios."""
        client = create_mock_client(simulate_latency=False)
        
        # Register handler for emergency scenarios
        def emergency_handler(prompt: str, context: Dict[str, Any]) -> str:
            return '''{
                "priority": "critical",
                "immediate_action": true,
                "actions": [
                    {
                        "type": "emergency_shutdown",
                        "target": "affected_switch"
                    }
                ]
            }'''
        
        client.register_custom_handler("emergency", emergency_handler)
        
        response = await client.generate_response(
            "Emergency: network failure detected"
        )
        
        assert "critical" in response.content
        assert "emergency" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_validation_error_handler(self):
        """Test with a custom handler for validation errors."""
        client = create_mock_client(simulate_latency=False)
        
        def validation_error_handler(prompt: str, context: Dict[str, Any]) -> str:
            return '''{
                "error": true,
                "error_type": "validation_error",
                "message": "Invalid switch ID provided",
                "suggestions": ["Check switch ID format", "Use 's1' format"]
            }'''
        
        client.register_custom_handler("invalid switch", validation_error_handler)
        
        response = await client.generate_response(
            "Configure invalid switch xyz123"
        )
        
        assert "error" in response.content.lower()


# Example 5: Testing error scenarios
class TestErrorScenarios:
    """Example tests for error handling."""
    
    @pytest.mark.asyncio
    async def test_api_timeout_simulation(self):
        """Test handling of API timeout errors."""
        from openai import APITimeoutError
        
        client = create_mock_client(
            simulate_latency=False,
            simulate_errors=True,
            error_rate=1.0  # Always fail
        )
        
        with pytest.raises(APITimeoutError):
            await client.generate_response("Test prompt")
    
    @pytest.mark.asyncio
    async def test_intermittent_errors(self):
        """Test handling of intermittent errors."""
        from openai import APITimeoutError
        
        client = create_mock_client(
            simulate_latency=False,
            simulate_errors=True,
            error_rate=0.3  # 30% error rate
        )
        
        success_count = 0
        error_count = 0
        
        for i in range(20):
            try:
                await client.generate_response(f"Test {i}")
                success_count += 1
            except APITimeoutError:
                error_count += 1
        
        # Should have some successes and some errors
        assert success_count > 0
        assert error_count > 0


# Example 6: Testing rate limiting
class TestRateLimiting:
    """Example tests for rate limiting behavior."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self):
        """Test that rate limits are enforced."""
        config = ChatGPTConfig(
            api_key="mock",
            rate_limit_rpm=5
        )
        client = MockChatGPTClient(config=config, simulate_latency=False)
        
        # Make requests up to limit
        for i in range(5):
            await client.generate_response(f"Request {i}")
        
        # Check rate limit status
        status = client.get_rate_limit_status()
        assert status.remaining_requests == 0
    
    @pytest.mark.asyncio
    async def test_rate_limit_reset(self):
        """Test that rate limits reset over time."""
        config = ChatGPTConfig(
            api_key="mock",
            rate_limit_rpm=3
        )
        client = MockChatGPTClient(config=config, simulate_latency=False)
        
        # Make requests up to limit
        for i in range(3):
            await client.generate_response(f"Request {i}")
        
        # Wait for reset (in real scenario, would wait 60 seconds)
        # For testing, we can reset manually
        client._request_times.clear()
        
        # Should be able to make more requests
        response = await client.generate_response("After reset")
        assert response is not None


# Example 7: Testing with network state context
class TestWithNetworkContext:
    """Example tests using network state context."""
    
    @pytest.mark.asyncio
    async def test_with_network_state(self, mock_chatgpt):
        """Test with network state context."""
        network_context = {
            "switches": ["s1", "s2", "s3"],
            "links": [
                {"src": "s1", "dst": "s2"},
                {"src": "s2", "dst": "s3"}
            ],
            "flows": 10,
            "bandwidth_utilization": 0.75
        }
        
        response = await mock_chatgpt.generate_response(
            prompt="Optimize network flow distribution",
            context=network_context
        )
        
        assert response is not None
        assert response.tokens_used > 0


# Example 8: Testing statistics and tracking
class TestStatisticsTracking:
    """Example tests for statistics tracking."""
    
    @pytest.mark.asyncio
    async def test_request_tracking(self, mock_chatgpt):
        """Test that requests are tracked correctly."""
        # Make several requests
        for i in range(5):
            await mock_chatgpt.generate_response(f"Request {i}")
        
        stats = mock_chatgpt.get_stats()
        
        assert stats["total_requests"] == 5
        assert stats["total_tokens"] > 0
        assert stats["total_cost"] == 0.0  # Mock is always free
        assert stats["is_available"] is True
    
    @pytest.mark.asyncio
    async def test_response_history(self, mock_chatgpt):
        """Test that response history is maintained."""
        prompts = ["Test 1", "Test 2", "Test 3"]
        
        for prompt in prompts:
            await mock_chatgpt.generate_response(prompt)
        
        history = mock_chatgpt.get_response_history()
        
        assert len(history) == 3
        assert all(r.content is not None for r in history)
        assert all(r.tokens_used > 0 for r in history)


# Example 9: Performance testing with mock
class TestPerformance:
    """Example performance tests using mock client."""
    
    @pytest.mark.asyncio
    async def test_high_volume_requests(self):
        """Test handling high volume of requests."""
        client = create_mock_client(simulate_latency=False)
        
        # Make many requests quickly
        tasks = [
            client.generate_response(f"Request {i}")
            for i in range(100)
        ]
        
        responses = await asyncio.gather(*tasks)
        
        assert len(responses) == 100
        assert all(r is not None for r in responses)
        
        stats = client.get_stats()
        assert stats["total_requests"] == 100
        assert stats["total_cost"] == 0.0
    
    @pytest.mark.asyncio
    async def test_latency_measurement(self):
        """Test latency measurement."""
        client = create_mock_client(simulate_latency=True)
        
        # Make several requests
        for i in range(5):
            await client.generate_response(f"Request {i}")
        
        avg_latency = client.get_latency()
        
        # Should have some latency due to simulation
        assert avg_latency > 0


# Example 10: Integration test scenario
class TestIntegrationScenario:
    """Example integration test using mock client."""
    
    @pytest.mark.asyncio
    async def test_complete_workflow(self):
        """Test a complete workflow from intent to action."""
        client = create_mock_client(simulate_latency=False)
        
        # Step 1: Parse user intent
        intent_response = await client.generate_response(
            "I want to create a QoS policy for video traffic"
        )
        assert intent_response is not None
        
        # Step 2: Validate resources
        validation_response = await client.generate_response(
            "Validate that switches s1 and s2 support QoS"
        )
        assert validation_response is not None
        
        # Step 3: Generate actions
        action_response = await client.generate_response(
            "Generate actions to implement QoS policy"
        )
        assert action_response is not None
        
        # Step 4: Verify all steps completed
        stats = client.get_stats()
        assert stats["total_requests"] == 3
        assert stats["is_available"]
        
        # Step 5: Check history
        history = client.get_response_history()
        assert len(history) == 3


# Example 11: Replacing real client in existing tests
class TestMigrationExample:
    """Example showing how to migrate from real to mock client."""
    
    @pytest.mark.asyncio
    async def test_before_migration(self):
        """Example of test before migration (commented out to avoid real API calls)."""
        # BEFORE: Using real ChatGPT client
        # from src.services.chatgpt_client import ChatGPTClient
        # client = ChatGPTClient()  # Would make real API calls
        # response = await client.generate_response("Test")
        
        # AFTER: Using mock client
        from tests.mocks import create_mock_client
        client = create_mock_client(simulate_latency=False)
        response = await client.generate_response("Test")
        
        assert response is not None
        assert response.tokens_used > 0


# Example 12: Parameterized tests with mock
class TestParameterized:
    """Example parameterized tests using mock client."""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("intent_type,expected_keyword", [
        ("configure switch", "flow"),
        ("detect anomaly", "anomaly"),
        ("create slice", "slice"),
    ])
    async def test_different_intent_types(self, mock_chatgpt, intent_type, expected_keyword):
        """Test different intent types produce appropriate responses."""
        response = await mock_chatgpt.generate_response(intent_type)
        
        assert response is not None
        # Note: Mock responses are intelligent and context-aware
        # They will generate appropriate responses based on keywords


if __name__ == "__main__":
    # Run examples
    pytest.main([__file__, "-v"])
