"""Mock ChatGPT API client for cost-free offline testing."""

import json
import random
import time
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from llm_integration_module.services.chatgpt_client import (
    ChatGPTResponse,
    ChatGPTConfig,
    RateLimitInfo,
    BudgetAlert
)


class MockResponseVariant(Enum):
    """Types of mock response variations."""
    SIMPLE = "simple"
    DETAILED = "detailed"
    NETWORK_CONFIG = "network_config"
    ANOMALY_DETECTION = "anomaly_detection"
    SLICE_MANAGEMENT = "slice_management"
    ERROR_RESPONSE = "error_response"
    CLARIFICATION_REQUEST = "clarification_request"


@dataclass
class MockResponseTemplate:
    """Template for generating mock responses."""
    variant: MockResponseVariant
    template: str
    variables: List[str]
    
    def generate(self, **kwargs) -> str:
        """Generate response from template with provided variables."""
        result = self.template
        for var in self.variables:
            value = kwargs.get(var, f"<{var}>")
            result = result.replace(f"{{{var}}}", str(value))
        return result


class ChatGPTResponseGenerator:
    """Generator for creating varied mock ChatGPT responses."""
    
    def __init__(self):
        """Initialize response generator with templates."""
        self.templates = self._initialize_templates()
        self.response_history: List[ChatGPTResponse] = []
    
    def _initialize_templates(self) -> Dict[MockResponseVariant, List[MockResponseTemplate]]:
        """Initialize response templates for different scenarios."""
        return {
            MockResponseVariant.SIMPLE: [
                MockResponseTemplate(
                    variant=MockResponseVariant.SIMPLE,
                    template='{"intent": "{intent}", "action": "{action}", "confidence": {confidence}}',
                    variables=["intent", "action", "confidence"]
                ),
            ],
            MockResponseVariant.NETWORK_CONFIG: [
                MockResponseTemplate(
                    variant=MockResponseVariant.NETWORK_CONFIG,
                    template='''{
                        "intent_type": "configuration",
                        "target_resources": ["{resource}"],
                        "actions": [
                            {
                                "type": "flow_mod",
                                "target": "{target}",
                                "parameters": {
                                    "priority": {priority},
                                    "match": "{match}",
                                    "actions": ["{flow_action}"]
                                }
                            }
                        ],
                        "estimated_impact": "low",
                        "rollback_plan": ["revert_flow_{target}"]
                    }''',
                    variables=["resource", "target", "priority", "match", "flow_action"]
                ),
                MockResponseTemplate(
                    variant=MockResponseVariant.NETWORK_CONFIG,
                    template='''{
                        "intent_type": "configuration",
                        "interpreted_intent": "{intent_text}",
                        "actions": [
                            {
                                "type": "config_change",
                                "target": "{switch_id}",
                                "parameters": {
                                    "setting": "{setting}",
                                    "value": "{value}"
                                }
                            }
                        ],
                        "validation": "passed",
                        "conflicts": []
                    }''',
                    variables=["intent_text", "switch_id", "setting", "value"]
                ),
            ],
            MockResponseVariant.ANOMALY_DETECTION: [
                MockResponseTemplate(
                    variant=MockResponseVariant.ANOMALY_DETECTION,
                    template='''{
                        "anomaly_detected": true,
                        "anomaly_type": "{anomaly_type}",
                        "severity": "{severity}",
                        "affected_resources": ["{resource}"],
                        "recommended_actions": [
                            {
                                "type": "flow_mod",
                                "description": "Reroute traffic to avoid congested link",
                                "priority": "high"
                            }
                        ],
                        "confidence": {confidence}
                    }''',
                    variables=["anomaly_type", "severity", "resource", "confidence"]
                ),
            ],
            MockResponseVariant.SLICE_MANAGEMENT: [
                MockResponseTemplate(
                    variant=MockResponseVariant.SLICE_MANAGEMENT,
                    template='''{
                        "intent_type": "slice_create",
                        "slice_name": "{slice_name}",
                        "resources": {
                            "bandwidth": {bandwidth},
                            "switches": ["{switches}"],
                            "priority": {priority}
                        },
                        "sla": {
                            "latency_max": {latency},
                            "availability": {availability}
                        },
                        "actions": [
                            {
                                "type": "slice_create",
                                "parameters": {
                                    "name": "{slice_name}",
                                    "bandwidth_mbps": {bandwidth}
                                }
                            }
                        ]
                    }''',
                    variables=["slice_name", "bandwidth", "switches", "priority", "latency", "availability"]
                ),
            ],
            MockResponseVariant.CLARIFICATION_REQUEST: [
                MockResponseTemplate(
                    variant=MockResponseVariant.CLARIFICATION_REQUEST,
                    template='''{
                        "requires_clarification": true,
                        "ambiguous_elements": ["{element}"],
                        "clarification_questions": [
                            "Which {resource_type} did you mean: {options}?"
                        ],
                        "partial_interpretation": "{partial}"
                    }''',
                    variables=["element", "resource_type", "options", "partial"]
                ),
            ],
            MockResponseVariant.ERROR_RESPONSE: [
                MockResponseTemplate(
                    variant=MockResponseVariant.ERROR_RESPONSE,
                    template='''{
                        "error": true,
                        "error_type": "{error_type}",
                        "message": "{message}",
                        "suggestions": ["{suggestion}"]
                    }''',
                    variables=["error_type", "message", "suggestion"]
                ),
            ],
        }
    
    def generate_response(
        self,
        variant: MockResponseVariant = MockResponseVariant.SIMPLE,
        **kwargs
    ) -> str:
        """Generate a mock response based on variant and parameters.
        
        Args:
            variant: Type of response to generate
            **kwargs: Variables to fill in the template
            
        Returns:
            Generated response string
        """
        templates = self.templates.get(variant, self.templates[MockResponseVariant.SIMPLE])
        template = random.choice(templates)
        
        # Fill in default values for missing variables
        defaults = self._get_default_values(variant)
        for var in template.variables:
            if var not in kwargs:
                kwargs[var] = defaults.get(var, f"mock_{var}")
        
        return template.generate(**kwargs)
    
    def _get_default_values(self, variant: MockResponseVariant) -> Dict[str, Any]:
        """Get default values for template variables."""
        defaults = {
            "intent": "configure network",
            "action": "apply_flow_rule",
            "confidence": "0.95",
            "resource": "switch_1",
            "target": "s1",
            "priority": "100",
            "match": "tcp",
            "flow_action": "forward",
            "intent_text": "Configure network flow",
            "switch_id": "s1",
            "setting": "max_bandwidth",
            "value": "1000",
            "anomaly_type": "high_latency",
            "severity": "medium",
            "slice_name": "slice_1",
            "bandwidth": "100",
            "switches": "s1,s2",
            "latency": "10",
            "availability": "0.99",
            "element": "switch reference",
            "resource_type": "switch",
            "options": "s1, s2, s3",
            "partial": "configure switch",
            "error_type": "validation_error",
            "message": "Invalid configuration",
            "suggestion": "Check switch ID"
        }
        return defaults
    
    def generate_network_action_response(
        self,
        intent_text: str,
        action_type: str = "flow_mod",
        num_actions: int = 1
    ) -> str:
        """Generate a response with network actions.
        
        Args:
            intent_text: The original intent text
            action_type: Type of action (flow_mod, slice_create, etc.)
            num_actions: Number of actions to generate
            
        Returns:
            JSON response string with actions
        """
        actions = []
        for i in range(num_actions):
            actions.append({
                "type": action_type,
                "target": f"target_{i}",
                "parameters": {
                    "priority": 100 + i * 10,
                    "timeout": 30
                }
            })
        
        response = {
            "intent_type": "configuration",
            "interpreted_intent": intent_text,
            "actions": actions,
            "validation": "passed",
            "estimated_duration": num_actions * 5,
            "rollback_plan": [f"revert_action_{i}" for i in range(num_actions)]
        }
        
        return json.dumps(response, indent=2)
    
    def generate_anomaly_response(
        self,
        anomaly_type: str,
        severity: str = "medium",
        auto_mitigate: bool = True
    ) -> str:
        """Generate an anomaly detection response.
        
        Args:
            anomaly_type: Type of anomaly detected
            severity: Severity level (low, medium, high, critical)
            auto_mitigate: Whether to include mitigation actions
            
        Returns:
            JSON response string with anomaly details
        """
        response = {
            "anomaly_detected": True,
            "anomaly_type": anomaly_type,
            "severity": severity,
            "affected_resources": ["switch_1", "link_1_2"],
            "timestamp": datetime.now().isoformat(),
            "confidence": 0.85
        }
        
        if auto_mitigate:
            response["recommended_actions"] = [
                {
                    "type": "flow_mod",
                    "description": f"Mitigate {anomaly_type}",
                    "priority": "high" if severity in ["high", "critical"] else "medium"
                }
            ]
        
        return json.dumps(response, indent=2)
    
    def generate_clarification_response(
        self,
        ambiguous_elements: List[str],
        questions: List[str]
    ) -> str:
        """Generate a clarification request response.
        
        Args:
            ambiguous_elements: List of ambiguous elements in the intent
            questions: List of clarification questions
            
        Returns:
            JSON response string with clarification request
        """
        response = {
            "requires_clarification": True,
            "ambiguous_elements": ambiguous_elements,
            "clarification_questions": questions,
            "partial_interpretation": "Partially understood intent",
            "confidence": 0.45
        }
        
        return json.dumps(response, indent=2)
    
    def generate_varied_responses(
        self,
        count: int,
        variant: Optional[MockResponseVariant] = None
    ) -> List[str]:
        """Generate multiple varied responses.
        
        Args:
            count: Number of responses to generate
            variant: Optional specific variant to use
            
        Returns:
            List of generated response strings
        """
        responses = []
        variants = [variant] if variant else list(MockResponseVariant)
        
        for i in range(count):
            selected_variant = random.choice(variants)
            response = self.generate_response(
                variant=selected_variant,
                index=str(i)
            )
            responses.append(response)
        
        return responses


class MockChatGPTClient:
    """Mock ChatGPT client for offline testing without API costs."""
    
    def __init__(
        self,
        config: Optional[ChatGPTConfig] = None,
        response_generator: Optional[ChatGPTResponseGenerator] = None,
        simulate_latency: bool = True,
        simulate_errors: bool = False,
        error_rate: float = 0.0
    ):
        """Initialize mock client.
        
        Args:
            config: Configuration (uses defaults if None)
            response_generator: Custom response generator
            simulate_latency: Whether to simulate API latency
            simulate_errors: Whether to simulate API errors
            error_rate: Probability of errors (0.0 to 1.0)
        """
        self.config = config or ChatGPTConfig(
            api_key="mock-api-key",
            model="gpt-4-turbo",
            max_tokens=2000,
            temperature=0.1,
            rate_limit_rpm=60,
            timeout=30,
            max_retries=3
        )
        
        self.generator = response_generator or ChatGPTResponseGenerator()
        self.simulate_latency = simulate_latency
        self.simulate_errors = simulate_errors
        self.error_rate = error_rate
        
        # Tracking
        self._request_count = 0
        self._total_tokens = 0
        self._total_cost = 0.0
        self._request_history: List[Dict[str, Any]] = []
        self._response_history: List[ChatGPTResponse] = []
        
        # Rate limiting simulation
        self._request_times: List[datetime] = []
        self._rate_limit_info = RateLimitInfo(
            remaining_requests=config.rate_limit_rpm if config else 60,
            reset_time=datetime.now() + timedelta(minutes=1),
            is_throttled=False
        )
        
        # Custom response handlers
        self._custom_handlers: Dict[str, Callable] = {}
    
    async def generate_response(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        system_message: Optional[str] = None
    ) -> ChatGPTResponse:
        """Generate a mock response.
        
        Args:
            prompt: The user prompt
            context: Optional context dictionary
            system_message: Optional system message
            
        Returns:
            ChatGPTResponse with mock data
        """
        start_time = time.time()
        
        # Simulate rate limiting
        await self._simulate_rate_limit()
        
        # Simulate errors if enabled
        if self.simulate_errors and random.random() < self.error_rate:
            from openai import APITimeoutError
            raise APITimeoutError("Mock timeout error")
        
        # Simulate latency
        if self.simulate_latency:
            latency = random.uniform(0.5, 2.0)
            await self._sleep(latency)
        
        # Check for custom handler
        response_content = None
        for pattern, handler in self._custom_handlers.items():
            if pattern.lower() in prompt.lower():
                response_content = handler(prompt, context)
                break
        
        # Generate response if no custom handler matched
        if response_content is None:
            response_content = self._generate_response_content(prompt, context)
        
        # Calculate metrics
        actual_latency = time.time() - start_time
        tokens_used = self._estimate_tokens(prompt, response_content)
        cost = self._estimate_cost(tokens_used)
        
        # Track metrics
        self._request_count += 1
        self._total_tokens += tokens_used
        self._total_cost += cost
        
        # Create response
        response = ChatGPTResponse(
            content=response_content,
            model=self.config.model,
            tokens_used=tokens_used,
            latency=actual_latency,
            finish_reason="stop",
            timestamp=datetime.now()
        )
        
        # Store history
        self._request_history.append({
            "prompt": prompt,
            "context": context,
            "system_message": system_message,
            "timestamp": datetime.now()
        })
        self._response_history.append(response)
        
        return response
    
    def _generate_response_content(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Generate response content based on prompt analysis.
        
        Args:
            prompt: The user prompt
            context: Optional context
            
        Returns:
            Generated response string
        """
        prompt_lower = prompt.lower()
        
        # Detect intent type from prompt
        if any(word in prompt_lower for word in ["anomaly", "detect", "problem", "issue"]):
            return self.generator.generate_anomaly_response(
                anomaly_type="high_latency",
                severity="medium"
            )
        
        elif any(word in prompt_lower for word in ["slice", "create slice", "network slice"]):
            return self.generator.generate_response(
                variant=MockResponseVariant.SLICE_MANAGEMENT,
                slice_name="test_slice",
                bandwidth="100"
            )
        
        elif any(word in prompt_lower for word in ["clarify", "unclear", "ambiguous"]):
            return self.generator.generate_clarification_response(
                ambiguous_elements=["switch reference"],
                questions=["Which switch did you mean?"]
            )
        
        elif any(word in prompt_lower for word in ["configure", "set", "modify", "change"]):
            return self.generator.generate_network_action_response(
                intent_text=prompt,
                action_type="flow_mod",
                num_actions=1
            )
        
        else:
            # Default simple response
            return self.generator.generate_response(
                variant=MockResponseVariant.SIMPLE,
                intent=prompt[:50],
                action="process_intent",
                confidence="0.90"
            )
    
    def register_custom_handler(
        self,
        pattern: str,
        handler: Callable[[str, Optional[Dict[str, Any]]], str]
    ) -> None:
        """Register a custom response handler for specific prompts.
        
        Args:
            pattern: String pattern to match in prompts
            handler: Function that takes (prompt, context) and returns response string
        """
        self._custom_handlers[pattern] = handler
    
    async def _simulate_rate_limit(self) -> None:
        """Simulate rate limiting behavior."""
        now = datetime.now()
        
        # Remove old requests
        self._request_times = [
            t for t in self._request_times
            if now - t < timedelta(minutes=1)
        ]
        
        # Check if at limit
        if len(self._request_times) >= self.config.rate_limit_rpm:
            oldest = min(self._request_times)
            wait_until = oldest + timedelta(minutes=1)
            wait_seconds = (wait_until - now).total_seconds()
            
            if wait_seconds > 0:
                self._rate_limit_info.is_throttled = True
                await self._sleep(wait_seconds)
                self._rate_limit_info.is_throttled = False
        
        self._request_times.append(now)
        self._rate_limit_info.remaining_requests = (
            self.config.rate_limit_rpm - len(self._request_times)
        )
    
    async def _sleep(self, seconds: float) -> None:
        """Async sleep helper."""
        import asyncio
        await asyncio.sleep(seconds)
    
    def _estimate_tokens(self, prompt: str, response: str) -> int:
        """Estimate token count."""
        # Rough estimate: ~1.3 tokens per word
        words = len(prompt.split()) + len(response.split())
        return int(words * 1.3)
    
    def _estimate_cost(self, tokens: int) -> float:
        """Estimate cost (always returns 0 for mock)."""
        return 0.0  # Mock client is cost-free
    
    def is_available(self) -> bool:
        """Check if mock client is available."""
        return True
    
    def get_latency(self) -> float:
        """Get average latency."""
        if not self._response_history:
            return 0.0
        return sum(r.latency for r in self._response_history) / len(self._response_history)
    
    def get_rate_limit_status(self) -> RateLimitInfo:
        """Get rate limit status."""
        return self._rate_limit_info
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        return {
            "total_requests": self._request_count,
            "total_tokens": self._total_tokens,
            "total_cost": self._total_cost,
            "is_available": True,
            "average_latency": self.get_latency(),
            "request_history_size": len(self._request_history),
            "response_history_size": len(self._response_history)
        }
    
    def get_request_history(self) -> List[Dict[str, Any]]:
        """Get request history."""
        return self._request_history.copy()
    
    def get_response_history(self) -> List[ChatGPTResponse]:
        """Get response history."""
        return self._response_history.copy()
    
    def reset(self) -> None:
        """Reset all tracking and history."""
        self._request_count = 0
        self._total_tokens = 0
        self._total_cost = 0.0
        self._request_history.clear()
        self._response_history.clear()
        self._request_times.clear()


# Convenience functions

def create_mock_client(
    simulate_latency: bool = False,
    simulate_errors: bool = False,
    error_rate: float = 0.0,
    **config_kwargs
) -> MockChatGPTClient:
    """Create a mock ChatGPT client with custom configuration.
    
    Args:
        simulate_latency: Whether to simulate API latency
        simulate_errors: Whether to simulate API errors
        error_rate: Probability of errors (0.0 to 1.0)
        **config_kwargs: Additional config parameters
        
    Returns:
        Configured MockChatGPTClient
    """
    config = ChatGPTConfig(
        api_key="mock-api-key",
        **config_kwargs
    ) if config_kwargs else None
    
    return MockChatGPTClient(
        config=config,
        simulate_latency=simulate_latency,
        simulate_errors=simulate_errors,
        error_rate=error_rate
    )


def create_mock_response(
    content: str = "Mock response",
    model: str = "gpt-4-turbo",
    tokens: int = 100,
    latency: float = 1.0
) -> ChatGPTResponse:
    """Create a mock ChatGPT response.
    
    Args:
        content: Response content
        model: Model name
        tokens: Token count
        latency: Simulated latency
        
    Returns:
        ChatGPTResponse object
    """
    return ChatGPTResponse(
        content=content,
        model=model,
        tokens_used=tokens,
        latency=latency,
        finish_reason="stop",
        timestamp=datetime.now()
    )
