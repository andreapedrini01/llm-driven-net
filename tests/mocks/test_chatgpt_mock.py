"""Tests for ChatGPT API mocking system."""

import pytest
import asyncio
from datetime import datetime

from tests.mocks import (
    MockChatGPTClient,
    ChatGPTResponseGenerator,
    MockResponseVariant,
    create_mock_client,
    create_mock_response
)
from src.services.chatgpt_client import ChatGPTConfig


class TestChatGPTResponseGenerator:
    """Tests for response generator."""
    
    def test_generator_initialization(self):
        """Test that generator initializes with templates."""
        generator = ChatGPTResponseGenerator()
        
        assert generator.templates is not None
        assert len(generator.templates) > 0
        assert MockResponseVariant.SIMPLE in generator.templates
        assert MockResponseVariant.NETWORK_CONFIG in generator.templates
    
    def test_generate_simple_response(self):
        """Test generating simple responses."""
        generator = ChatGPTResponseGenerator()
        
        response = generator.generate_response(
            variant=MockResponseVariant.SIMPLE,
            intent="test intent",
            action="test_action",
            confidence="0.95"
        )
        
        assert response is not None
        assert "test intent" in response or "test_action" in response
    
    def test_generate_network_config_response(self):
        """Test generating network configuration responses."""
        generator = ChatGPTResponseGenerator()
        
        response = generator.generate_response(
            variant=MockResponseVariant.NETWORK_CONFIG,
            resource="switch_1",
            target="s1",
            priority="100"
        )
        
        assert response is not None
        assert "flow_mod" in response or "config_change" in response
    
    def test_generate_anomaly_response(self):
        """Test generating anomaly detection responses."""
        generator = ChatGPTResponseGenerator()
        
        response = generator.generate_anomaly_response(
            anomaly_type="high_latency",
            severity="critical",
            auto_mitigate=True
        )
        
        assert response is not None
        assert "anomaly_detected" in response
        assert "high_latency" in response
        assert "critical" in response
        assert "recommended_actions" in response
    
    def test_generate_clarification_response(self):
        """Test generating clarification request responses."""
        generator = ChatGPTResponseGenerator()
        
        response = generator.generate_clarification_response(
            ambiguous_elements=["switch reference", "bandwidth value"],
            questions=["Which switch?", "What bandwidth?"]
        )
        
        assert response is not None
        assert "requires_clarification" in response
        assert "switch reference" in response
        assert "Which switch?" in response
    
    def test_generate_network_action_response(self):
        """Test generating network action responses."""
        generator = ChatGPTResponseGenerator()
        
        response = generator.generate_network_action_response(
            intent_text="Configure flow on switch 1",
            action_type="flow_mod",
            num_actions=3
        )
        
        assert response is not None
        assert "actions" in response
        assert "flow_mod" in response
        assert "rollback_plan" in response
    
    def test_generate_varied_responses(self):
        """Test generating multiple varied responses."""
        generator = ChatGPTResponseGenerator()
        
        responses = generator.generate_varied_responses(count=5)
        
        assert len(responses) == 5
        assert all(isinstance(r, str) for r in responses)
        assert all(len(r) > 0 for r in responses)


class TestMockChatGPTClient:
    """Tests for mock ChatGPT client."""
    
    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test that mock client initializes correctly."""
        client = MockChatGPTClient()
        
        assert client.config is not None
        assert client.generator is not None
        assert client.is_available()
    
    @pytest.mark.asyncio
    async def test_generate_response_basic(self):
        """Test basic response generation."""
        client = MockChatGPTClient(simulate_latency=False)
        
        response = await client.generate_response(
            prompt="Configure network flow",
            context={"network_state": "active"}
        )
        
        assert response is not None
        assert response.content is not None
        assert response.model == "gpt-4-turbo"
        assert response.tokens_used > 0
        assert response.finish_reason == "stop"
    
    @pytest.mark.asyncio
    async def test_generate_response_with_context(self):
        """Test response generation with context."""
        client = MockChatGPTClient(simulate_latency=False)
        
        context = {
            "switches": ["s1", "s2"],
            "current_flows": 10
        }
        
        response = await client.generate_response(
            prompt="Add new flow rule",
            context=context
        )
        
        assert response is not None
        assert response.content is not None
    
    @pytest.mark.asyncio
    async def test_anomaly_detection_response(self):
        """Test that anomaly-related prompts generate appropriate responses."""
        client = MockChatGPTClient(simulate_latency=False)
        
        response = await client.generate_response(
            prompt="Detect anomalies in network traffic"
        )
        
        assert response is not None
        assert "anomaly" in response.content.lower() or "detect" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_slice_management_response(self):
        """Test that slice-related prompts generate appropriate responses."""
        client = MockChatGPTClient(simulate_latency=False)
        
        response = await client.generate_response(
            prompt="Create a new network slice with 100Mbps bandwidth"
        )
        
        assert response is not None
        assert "slice" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_configuration_response(self):
        """Test that configuration prompts generate appropriate responses."""
        client = MockChatGPTClient(simulate_latency=False)
        
        response = await client.generate_response(
            prompt="Configure switch s1 to forward traffic"
        )
        
        assert response is not None
        content_lower = response.content.lower()
        assert any(word in content_lower for word in ["configure", "flow", "action"])
    
    @pytest.mark.asyncio
    async def test_custom_handler(self):
        """Test custom response handler."""
        client = MockChatGPTClient(simulate_latency=False)
        
        def custom_handler(prompt: str, context):
            return '{"custom": "response", "prompt": "' + prompt + '"}'
        
        client.register_custom_handler("special keyword", custom_handler)
        
        response = await client.generate_response(
            prompt="This has a special keyword in it"
        )
        
        assert response is not None
        assert "custom" in response.content
        assert "special keyword" in response.content
    
    @pytest.mark.asyncio
    async def test_request_tracking(self):
        """Test that requests are tracked."""
        client = MockChatGPTClient(simulate_latency=False)
        
        await client.generate_response("Test 1")
        await client.generate_response("Test 2")
        await client.generate_response("Test 3")
        
        stats = client.get_stats()
        assert stats["total_requests"] == 3
        assert stats["total_tokens"] > 0
        assert stats["total_cost"] == 0.0  # Mock is cost-free
        
        history = client.get_request_history()
        assert len(history) == 3
    
    @pytest.mark.asyncio
    async def test_response_history(self):
        """Test that responses are stored in history."""
        client = MockChatGPTClient(simulate_latency=False)
        
        await client.generate_response("Test prompt")
        
        history = client.get_response_history()
        assert len(history) == 1
        assert history[0].content is not None
    
    @pytest.mark.asyncio
    async def test_latency_simulation(self):
        """Test that latency can be simulated."""
        client = MockChatGPTClient(simulate_latency=True)
        
        start = datetime.now()
        response = await client.generate_response("Test")
        end = datetime.now()
        
        duration = (end - start).total_seconds()
        assert duration >= 0.5  # Should have some simulated latency
        assert response.latency > 0
    
    @pytest.mark.asyncio
    async def test_no_latency_simulation(self):
        """Test that latency simulation can be disabled."""
        client = MockChatGPTClient(simulate_latency=False)
        
        start = datetime.now()
        response = await client.generate_response("Test")
        end = datetime.now()
        
        duration = (end - start).total_seconds()
        assert duration < 0.5  # Should be fast without simulation
    
    @pytest.mark.asyncio
    async def test_error_simulation(self):
        """Test that errors can be simulated."""
        from openai import APITimeoutError
        
        client = MockChatGPTClient(
            simulate_latency=False,
            simulate_errors=True,
            error_rate=1.0  # Always error
        )
        
        with pytest.raises(APITimeoutError):
            await client.generate_response("Test")
    
    @pytest.mark.asyncio
    async def test_rate_limit_simulation(self):
        """Test that rate limiting is simulated."""
        config = ChatGPTConfig(
            api_key="mock",
            rate_limit_rpm=3  # Very low limit for testing
        )
        client = MockChatGPTClient(config=config, simulate_latency=False)
        
        # Make requests up to the limit
        for i in range(3):
            await client.generate_response(f"Test {i}")
        
        rate_limit_info = client.get_rate_limit_status()
        assert rate_limit_info.remaining_requests == 0
    
    @pytest.mark.asyncio
    async def test_client_reset(self):
        """Test that client can be reset."""
        client = MockChatGPTClient(simulate_latency=False)
        
        await client.generate_response("Test 1")
        await client.generate_response("Test 2")
        
        assert client.get_stats()["total_requests"] == 2
        
        client.reset()
        
        stats = client.get_stats()
        assert stats["total_requests"] == 0
        assert stats["total_tokens"] == 0
        assert len(client.get_request_history()) == 0
    
    @pytest.mark.asyncio
    async def test_availability(self):
        """Test that mock client is always available."""
        client = MockChatGPTClient()
        
        assert client.is_available()
        
        # Even after many requests
        for i in range(10):
            await client.generate_response(f"Test {i}")
        
        assert client.is_available()
    
    @pytest.mark.asyncio
    async def test_average_latency_calculation(self):
        """Test average latency calculation."""
        client = MockChatGPTClient(simulate_latency=False)
        
        await client.generate_response("Test 1")
        await client.generate_response("Test 2")
        
        avg_latency = client.get_latency()
        assert avg_latency >= 0


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    @pytest.mark.asyncio
    async def test_create_mock_client(self):
        """Test create_mock_client convenience function."""
        client = create_mock_client(
            simulate_latency=False,
            model="gpt-3.5-turbo"
        )
        
        assert client is not None
        assert client.config.model == "gpt-3.5-turbo"
        assert not client.simulate_latency
    
    def test_create_mock_response(self):
        """Test create_mock_response convenience function."""
        response = create_mock_response(
            content="Test content",
            model="gpt-4",
            tokens=50,
            latency=0.5
        )
        
        assert response is not None
        assert response.content == "Test content"
        assert response.model == "gpt-4"
        assert response.tokens_used == 50
        assert response.latency == 0.5


class TestMockIntegration:
    """Integration tests using mock client."""
    
    @pytest.mark.asyncio
    async def test_multiple_request_types(self):
        """Test handling multiple types of requests."""
        client = MockChatGPTClient(simulate_latency=False)
        
        # Configuration request
        config_response = await client.generate_response(
            "Configure switch s1"
        )
        assert config_response is not None
        
        # Anomaly detection request
        anomaly_response = await client.generate_response(
            "Detect network anomalies"
        )
        assert anomaly_response is not None
        
        # Slice management request
        slice_response = await client.generate_response(
            "Create network slice"
        )
        assert slice_response is not None
        
        # All should be different
        assert config_response.content != anomaly_response.content
    
    @pytest.mark.asyncio
    async def test_cost_free_operation(self):
        """Test that mock client incurs no costs."""
        client = MockChatGPTClient(simulate_latency=False)
        
        # Make many requests
        for i in range(100):
            await client.generate_response(f"Test request {i}")
        
        stats = client.get_stats()
        assert stats["total_cost"] == 0.0
        assert stats["total_requests"] == 100
    
    @pytest.mark.asyncio
    async def test_realistic_workflow(self):
        """Test a realistic workflow with mock client."""
        client = MockChatGPTClient(simulate_latency=False)
        
        # Step 1: Parse intent
        intent_response = await client.generate_response(
            "I want to configure a flow rule on switch 1"
        )
        assert intent_response is not None
        
        # Step 2: Check for anomalies
        anomaly_response = await client.generate_response(
            "Check for anomalies in the network"
        )
        assert anomaly_response is not None
        
        # Step 3: Generate actions
        action_response = await client.generate_response(
            "Generate actions to implement the flow rule"
        )
        assert action_response is not None
        
        # Verify all completed successfully
        stats = client.get_stats()
        assert stats["total_requests"] == 3
        assert stats["is_available"]
