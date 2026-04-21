"""Example demonstrating the prompt engineering system with ChatGPT API.

This example shows how to use the prompt engineering system to:
1. Build optimized prompts for different operations
2. Parse and validate ChatGPT responses
3. Integrate with the ChatGPT client for end-to-end processing
"""

import asyncio
import json
from datetime import datetime

from llm_integration_module.services.prompt_engineering import PromptEngineeringSystem, PromptType
from llm_integration_module.services.chatgpt_client import ChatGPTClient
from llm_integration_module.models.intent import IntentObject, IntentType, Entity, ContextualizedIntent
from llm_integration_module.models.network import (
    NetworkState,
    Topology,
    Switch,
    Link,
    Host,
    NetworkMetrics,
    BandwidthMetrics,
    LatencyMetrics,
    UtilizationMetrics
)


async def example_intent_parsing():
    """Example: Parse a natural language intent using ChatGPT."""
    print("=" * 80)
    print("Example 1: Intent Parsing")
    print("=" * 80)
    
    # Initialize systems
    prompt_system = PromptEngineeringSystem()
    chatgpt_client = ChatGPTClient()
    
    # User's natural language intent
    intent_text = "Create a high-priority flow from switch-1 port 2 to switch-2 port 1 for HTTP traffic"
    
    # Build the prompt
    system_msg, user_prompt, config = prompt_system.build_intent_parsing_prompt(intent_text)
    
    print(f"\nIntent: {intent_text}")
    print(f"\nPrompt Configuration:")
    print(f"  - Max Tokens: {config['max_tokens']}")
    print(f"  - Temperature: {config['temperature']}")
    
    # Get response from ChatGPT
    try:
        response = await chatgpt_client.generate_response(
            prompt=user_prompt,
            system_message=system_msg
        )
        
        print(f"\nChatGPT Response:")
        print(f"  - Tokens Used: {response.tokens_used}")
        print(f"  - Latency: {response.latency:.2f}s")
        print(f"  - Cost: ~${chatgpt_client._estimate_cost(response.tokens_used // 2, response.tokens_used // 2):.4f}")
        
        # Parse and validate the response
        template = prompt_system.get_template(PromptType.INTENT_PARSING)
        parsed = prompt_system.parse_response(
            response.content,
            template.response_schema,
            PromptType.INTENT_PARSING
        )
        
        print(f"\nParsed Response:")
        print(f"  - Valid: {parsed.is_valid}")
        print(f"  - Confidence: {parsed.confidence:.2f}")
        
        if parsed.is_valid:
            print(f"\nExtracted Information:")
            print(f"  - Intent Type: {parsed.parsed_data.get('intent_type')}")
            print(f"  - Entities: {len(parsed.parsed_data.get('entities', []))}")
            for entity in parsed.parsed_data.get('entities', [])[:3]:
                print(f"    * {entity['name']}: {entity['value']} ({entity['type']})")
        else:
            print(f"\nValidation Errors:")
            for error in parsed.validation_errors:
                print(f"  - {error}")
    
    except Exception as e:
        print(f"\nError: {str(e)}")


async def example_action_generation():
    """Example: Generate network actions from contextualized intent."""
    print("\n" + "=" * 80)
    print("Example 2: Action Generation")
    print("=" * 80)
    
    # Initialize systems
    prompt_system = PromptEngineeringSystem()
    chatgpt_client = ChatGPTClient()
    
    # Create sample network state
    network_state = NetworkState(
        timestamp=datetime.now(),
        topology=Topology(
            switches=[
                Switch(id="switch-1", name="Core Switch 1", dpid="0000000000000001", ports=[1, 2, 3, 4]),
                Switch(id="switch-2", name="Core Switch 2", dpid="0000000000000002", ports=[1, 2, 3, 4])
            ],
            links=[
                Link(
                    id="link-1",
                    source_switch="switch-1",
                    source_port=1,
                    destination_switch="switch-2",
                    destination_port=1,
                    bandwidth=1000,
                    latency=2.5
                )
            ],
            hosts=[
                Host(
                    id="host-1",
                    mac_address="00:00:00:00:00:01",
                    ip_address="192.168.1.10",
                    connected_switch="switch-1",
                    connected_port=2
                ),
                Host(
                    id="host-2",
                    mac_address="00:00:00:00:00:02",
                    ip_address="192.168.1.20",
                    connected_switch="switch-2",
                    connected_port=2
                )
            ]
        ),
        flows=[],
        metrics=NetworkMetrics(
            bandwidth=BandwidthMetrics(
                total_capacity=1000,
                used_bandwidth=200,
                available_bandwidth=800,
                utilization_percentage=20.0
            ),
            latency=LatencyMetrics(
                average_latency=2.5,
                min_latency=1.0,
                max_latency=5.0,
                jitter=0.5
            ),
            utilization=UtilizationMetrics(
                cpu_utilization=30.0,
                memory_utilization=40.0
            )
        ),
        anomalies=[]
    )
    
    # Create contextualized intent
    intent = IntentObject(
        id="intent-001",
        raw_text="Route all HTTP traffic from host-1 to host-2 with high priority",
        timestamp=datetime.now(),
        user_id="admin",
        entities=[
            Entity(name="protocol", type="parameter", value="HTTP", confidence=0.95),
            Entity(name="source", type="resource", value="host-1", confidence=0.95),
            Entity(name="destination", type="resource", value="host-2", confidence=0.95),
            Entity(name="priority", type="parameter", value="high", confidence=0.9)
        ],
        intent_type=IntentType.CONFIGURATION,
        confidence=0.92,
        parameters={"protocol": "HTTP", "priority": "high"}
    )
    
    contextualized_intent = ContextualizedIntent(
        intent=intent,
        relevant_resources=["switch-1", "switch-2", "host-1", "host-2", "link-1"],
        network_context={
            "path": ["switch-1", "link-1", "switch-2"],
            "available_bandwidth": 800
        },
        conflicts=[],
        recommendations=["Use port 80 for HTTP traffic"]
    )
    
    # Build the prompt
    system_msg, user_prompt, config = prompt_system.build_action_generation_prompt(
        contextualized_intent,
        network_state
    )
    
    print(f"\nIntent: {intent.raw_text}")
    print(f"\nNetwork Context:")
    print(f"  - Switches: {len(network_state.topology.switches)}")
    print(f"  - Available Bandwidth: {network_state.metrics.bandwidth.available_bandwidth}Mbps")
    print(f"  - Relevant Resources: {len(contextualized_intent.relevant_resources)}")
    
    # Get response from ChatGPT
    try:
        response = await chatgpt_client.generate_response(
            prompt=user_prompt,
            system_message=system_msg
        )
        
        print(f"\nChatGPT Response:")
        print(f"  - Tokens Used: {response.tokens_used}")
        print(f"  - Latency: {response.latency:.2f}s")
        
        # Parse and validate the response
        template = prompt_system.get_template(PromptType.ACTION_GENERATION)
        parsed = prompt_system.parse_response(
            response.content,
            template.response_schema,
            PromptType.ACTION_GENERATION
        )
        
        print(f"\nParsed Response:")
        print(f"  - Valid: {parsed.is_valid}")
        print(f"  - Confidence: {parsed.confidence:.2f}")
        
        if parsed.is_valid:
            actions = parsed.parsed_data.get('actions', [])
            print(f"\nGenerated Actions: {len(actions)}")
            for i, action in enumerate(actions[:3], 1):
                print(f"  {i}. {action.get('type')} on {action.get('target')}")
                print(f"     Priority: {action.get('priority')}, Timeout: {action.get('timeout')}s")
            
            if 'risks' in parsed.parsed_data:
                print(f"\nIdentified Risks: {len(parsed.parsed_data['risks'])}")
                for risk in parsed.parsed_data['risks'][:2]:
                    print(f"  - {risk.get('description')} ({risk.get('severity')})")
    
    except Exception as e:
        print(f"\nError: {str(e)}")


async def example_prompt_optimization():
    """Example: Optimize prompts for token efficiency."""
    print("\n" + "=" * 80)
    print("Example 3: Prompt Optimization")
    print("=" * 80)
    
    prompt_system = PromptEngineeringSystem()
    
    # Create a very long prompt
    long_prompt = "Network configuration details:\n" + "\n".join([
        f"Switch-{i}: {100} ports, {50}% utilization" for i in range(1000)
    ])
    
    print(f"\nOriginal Prompt Length: {len(long_prompt)} characters")
    print(f"Estimated Tokens: ~{len(long_prompt) // 4}")
    
    # Optimize for token budget
    optimized = prompt_system.optimize_prompt_for_tokens(long_prompt, max_tokens=500)
    
    print(f"\nOptimized Prompt Length: {len(optimized)} characters")
    print(f"Estimated Tokens: ~{len(optimized) // 4}")
    print(f"Reduction: {((len(long_prompt) - len(optimized)) / len(long_prompt) * 100):.1f}%")


async def example_response_parsing():
    """Example: Parse various response formats."""
    print("\n" + "=" * 80)
    print("Example 4: Response Parsing")
    print("=" * 80)
    
    prompt_system = PromptEngineeringSystem()
    
    # Test different response formats
    test_cases = [
        {
            "name": "Plain JSON",
            "response": '{"intent_type": "configuration", "confidence": 0.9}',
        },
        {
            "name": "Markdown-wrapped JSON",
            "response": '```json\n{"intent_type": "query", "confidence": 0.85}\n```',
        },
        {
            "name": "JSON with surrounding text",
            "response": 'Here is the analysis: {"intent_type": "anomaly_response", "confidence": 0.95} as requested.',
        },
        {
            "name": "Invalid JSON",
            "response": 'This is not valid JSON at all',
        }
    ]
    
    schema = {"intent_type": "string", "confidence": "float"}
    
    for test_case in test_cases:
        print(f"\n{test_case['name']}:")
        parsed = prompt_system.parse_response(
            test_case['response'],
            schema,
            PromptType.INTENT_PARSING
        )
        print(f"  - Valid: {parsed.is_valid}")
        print(f"  - Confidence: {parsed.confidence:.2f}")
        if not parsed.is_valid:
            print(f"  - Errors: {parsed.validation_errors[0]}")
        else:
            print(f"  - Intent Type: {parsed.parsed_data.get('intent_type')}")


async def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("Prompt Engineering System Examples")
    print("=" * 80)
    
    # Run examples
    await example_intent_parsing()
    await example_action_generation()
    await example_prompt_optimization()
    await example_response_parsing()
    
    print("\n" + "=" * 80)
    print("Examples Complete")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
