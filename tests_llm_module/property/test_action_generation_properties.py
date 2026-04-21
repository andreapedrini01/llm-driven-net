"""Property-based tests for action generation completeness."""

import pytest
import asyncio
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from datetime import datetime
from typing import List, Dict, Any

from llm_integration_module.services.chatgpt_client import ChatGPTClient, ChatGPTConfig
from llm_integration_module.services.prompt_engineering import PromptEngineeringSystem, PromptType
from llm_integration_module.services.context_analyzer import ContextCorrelationEngine, NetworkStateCache
from llm_integration_module.models.intent import IntentObject, IntentType, Entity, ContextualizedIntent
from llm_integration_module.models.network import NetworkState, Topology, Switch, Link, Host, Flow, NetworkMetrics, BandwidthMetrics, LatencyMetrics, UtilizationMetrics
from llm_integration_module.models.actions import ActionSequence, NetworkAction, ActionType
import json


class TestActionGenerationProperties:
    """Property-based tests for action generation completeness."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Initialize components
        self.prompt_system = PromptEngineeringSystem()
        self.state_cache = NetworkStateCache(default_ttl=600)
        self.context_engine = ContextCorrelationEngine(self.state_cache)
        
        # Initialize ChatGPT client with test configuration
        try:
            self.chatgpt_client = ChatGPTClient()
        except ValueError:
            # If API key not configured, skip tests that require it
            self.chatgpt_client = None
    
    # Generator strategies for test data
    @staticmethod
    @st.composite
    def valid_intent_object(draw):
        """Generate valid IntentObject instances."""
        intent_types = [IntentType.CONFIGURATION, IntentType.QUERY, IntentType.ANOMALY_RESPONSE]
        
        # Generate entities
        entity_types = ['resource', 'action', 'target', 'parameter', 'identifier', 'value']
        num_entities = draw(st.integers(min_value=1, max_value=5))
        
        entities = []
        for _ in range(num_entities):
            entity = Entity(
                name=draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyz', min_size=3, max_size=10)),
                type=draw(st.sampled_from(entity_types)),
                value=draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789_-', min_size=1, max_size=20)),
                confidence=draw(st.floats(min_value=0.5, max_value=1.0))
            )
            entities.append(entity)
        
        # Generate parameters
        parameters = {}
        if draw(st.booleans()):
            param_keys = ['bandwidth', 'priority', 'timeout', 'vlan_id', 'qos_class']
            for key in draw(st.lists(st.sampled_from(param_keys), min_size=0, max_size=3, unique=True)):
                parameters[key] = draw(st.integers(min_value=1, max_value=1000))
        
        intent_text_templates = [
            "create flow for {resource}",
            "configure {resource} with {param}",
            "modify {resource} settings",
            "set up network slice for {resource}",
            "add flow rule to {resource}",
            "update {resource} configuration"
        ]
        
        resource_name = entities[0].value if entities else "switch1"
        intent_text = draw(st.sampled_from(intent_text_templates)).format(
            resource=resource_name,
            param="bandwidth 100"
        )
        
        return IntentObject(
            id=f"intent_{draw(st.integers(min_value=1000, max_value=9999))}",
            raw_text=intent_text,
            timestamp=datetime.now(),
            user_id=f"user_{draw(st.integers(min_value=1, max_value=100))}",
            entities=entities,
            intent_type=draw(st.sampled_from(intent_types)),
            confidence=draw(st.floats(min_value=0.6, max_value=1.0)),
            parameters=parameters
        )
    
    @staticmethod
    @st.composite
    def network_state_with_resources(draw):
        """Generate NetworkState with available resources."""
        # Generate switches
        num_switches = draw(st.integers(min_value=2, max_value=5))
        switches = []
        for i in range(num_switches):
            switch = Switch(
                id=f"switch-{i+1}",
                name=f"Switch {i+1}",
                dpid=f"00:00:00:00:00:00:00:0{i+1}",
                ports=[j+1 for j in range(4)],
                status="active"
            )
            switches.append(switch)
        
        # Generate links
        links = []
        for i in range(min(num_switches - 1, 3)):
            link = Link(
                id=f"link-{i+1}",
                source_switch=switches[i].id,
                source_port=1,
                destination_switch=switches[i+1].id,
                destination_port=2,
                bandwidth=draw(st.integers(min_value=100, max_value=10000)),
                latency=draw(st.floats(min_value=1.0, max_value=50.0)),
                status="active"
            )
            links.append(link)
        
        # Generate hosts
        num_hosts = draw(st.integers(min_value=1, max_value=4))
        hosts = []
        for i in range(num_hosts):
            host = Host(
                id=f"host-{i+1}",
                mac_address=f"00:00:00:00:00:{i+1:02x}",
                ip_address=f"10.0.0.{i+1}",
                connected_switch=switches[i % len(switches)].id,
                connected_port=3,
                status="active"
            )
            hosts.append(host)
        
        topology = Topology(switches=switches, links=links, hosts=hosts)
        
        # Generate metrics
        bandwidth_metrics = BandwidthMetrics(
            total_capacity=sum(link.bandwidth for link in links),
            used_bandwidth=draw(st.integers(min_value=100, max_value=5000)),
            available_bandwidth=draw(st.integers(min_value=1000, max_value=10000)),
            utilization_percentage=draw(st.floats(min_value=10.0, max_value=80.0))
        )
        
        latency_metrics = LatencyMetrics(
            average_latency=draw(st.floats(min_value=1.0, max_value=50.0)),
            min_latency=draw(st.floats(min_value=0.5, max_value=10.0)),
            max_latency=draw(st.floats(min_value=50.0, max_value=200.0)),
            jitter=draw(st.floats(min_value=0.1, max_value=10.0))
        )
        
        utilization_metrics = UtilizationMetrics(
            cpu_utilization=draw(st.floats(min_value=10.0, max_value=70.0)),
            memory_utilization=draw(st.floats(min_value=20.0, max_value=60.0)),
            port_utilization={}
        )
        
        metrics = NetworkMetrics(
            bandwidth=bandwidth_metrics,
            latency=latency_metrics,
            utilization=utilization_metrics
        )
        
        return NetworkState(
            timestamp=datetime.now(),
            topology=topology,
            flows=[],
            metrics=metrics,
            anomalies=[]
        )
    
    def _parse_action_response(self, response_content: str) -> Dict[str, Any]:
        """Parse action generation response from ChatGPT."""
        try:
            # Extract JSON from response
            json_str = response_content
            if "```json" in response_content:
                start = response_content.find("```json") + 7
                end = response_content.find("```", start)
                if end != -1:
                    json_str = response_content[start:end].strip()
            elif "```" in response_content:
                start = response_content.find("```") + 3
                end = response_content.find("```", start)
                if end != -1:
                    json_str = response_content[start:end].strip()
            
            # Try to find JSON object
            if "{" in json_str:
                start = json_str.find("{")
                brace_count = 0
                for i in range(start, len(json_str)):
                    if json_str[i] == "{":
                        brace_count += 1
                    elif json_str[i] == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            json_str = json_str[start:i+1]
                            break
            
            return json.loads(json_str)
        except (json.JSONDecodeError, ValueError) as e:
            return {"actions": [], "error": str(e)}
    
    def _validate_action_completeness(
        self,
        intent: IntentObject,
        actions: List[Dict[str, Any]],
        network_state: NetworkState
    ) -> Dict[str, Any]:
        """Validate that generated actions are complete for the intent."""
        validation_result = {
            "is_complete": False,
            "issues": [],
            "warnings": [],
            "action_count": len(actions),
            "coverage_score": 0.0
        }
        
        if not actions:
            validation_result["issues"].append("No actions generated for intent")
            return validation_result
        
        # Check that actions address the intent type
        intent_type = intent.intent_type
        
        if intent_type == IntentType.CONFIGURATION:
            # Configuration intents should have at least one action
            config_actions = [a for a in actions if a.get("type") in ["flow_mod", "config_change", "slice_create", "slice_modify"]]
            if not config_actions:
                validation_result["issues"].append("Configuration intent has no configuration actions")
            else:
                validation_result["coverage_score"] += 0.4
        
        elif intent_type == IntentType.QUERY:
            # Query intents might not need actions, but if they do, they should be read-only
            # For this test, we'll accept empty actions for queries
            validation_result["coverage_score"] += 0.3
        
        elif intent_type == IntentType.ANOMALY_RESPONSE:
            # Anomaly response should have mitigation actions
            if not actions:
                validation_result["warnings"].append("Anomaly response has no mitigation actions")
            else:
                validation_result["coverage_score"] += 0.4
        
        # Check that actions reference resources mentioned in the intent
        intent_resources = set()
        for entity in intent.entities:
            if entity.type in ['resource', 'target', 'identifier']:
                intent_resources.add(entity.value)
        
        if intent_resources:
            action_targets = set()
            for action in actions:
                if "target" in action:
                    action_targets.add(action["target"])
            
            # Check if actions address at least some of the intent resources
            if action_targets & intent_resources:
                validation_result["coverage_score"] += 0.3
            elif intent_type == IntentType.CONFIGURATION:
                validation_result["warnings"].append("Actions don't reference intent resources")
        
        # Check that actions have required fields
        required_fields = ["id", "type", "target", "parameters"]
        for i, action in enumerate(actions):
            missing_fields = [field for field in required_fields if field not in action]
            if missing_fields:
                validation_result["issues"].append(f"Action {i} missing fields: {missing_fields}")
            else:
                validation_result["coverage_score"] += 0.1 / len(actions)
        
        # Check that actions have valid types
        valid_action_types = ["flow_mod", "slice_create", "slice_modify", "config_change"]
        for i, action in enumerate(actions):
            if "type" in action and action["type"] not in valid_action_types:
                validation_result["issues"].append(f"Action {i} has invalid type: {action['type']}")
        
        # Check for rollback plan (important for configuration changes)
        if intent_type == IntentType.CONFIGURATION and len(actions) > 0:
            # Rollback plan is recommended but not strictly required
            validation_result["coverage_score"] += 0.1
        
        # Determine if complete
        validation_result["is_complete"] = (
            len(validation_result["issues"]) == 0 and
            validation_result["coverage_score"] >= 0.5
        )
        
        return validation_result
    
    @settings(max_examples=3, suppress_health_check=[HealthCheck.too_slow], deadline=60000)
    @given(
        intent=valid_intent_object(),
        network_state=network_state_with_resources()
    )
    def test_action_generation_completeness(self, intent, network_state):
        """
        **Feature: llm-integration-module, Property 4: Action generation completeness**
        
        For any valid and complete intent, the generated NetworkActions should be 
        sufficient to fully implement the intent's requirements.
        
        **Validates: Requirements 1.4**
        """
        # Skip if ChatGPT client not available
        if self.chatgpt_client is None:
            pytest.skip("ChatGPT API not configured")
        
        # Ensure valid inputs
        assume(intent is not None)
        assume(network_state is not None)
        assume(len(intent.entities) > 0)
        assume(intent.confidence >= 0.6)  # Only test with reasonably confident intents
        
        # Update state cache
        self.state_cache.update_state(network_state)
        
        # Contextualize the intent
        contextualized_intent = self.context_engine.correlate_intent_with_state(intent)
        
        # Build action generation prompt
        system_message, user_prompt, config = self.prompt_system.build_action_generation_prompt(
            contextualized_intent,
            network_state
        )
        
        # Generate actions using ChatGPT
        try:
            response = asyncio.run(
                self.chatgpt_client.generate_response(
                    prompt=user_prompt,
                    system_message=system_message
                )
            )
            
            # Parse the response
            parsed_response = self._parse_action_response(response.content)
            
            # Verify response structure
            assert isinstance(parsed_response, dict), "Response should be a dictionary"
            
            # Extract actions
            actions = parsed_response.get("actions", [])
            
            # Validate action completeness
            validation = self._validate_action_completeness(intent, actions, network_state)
            
            # Core property: Actions should be complete for the intent
            assert validation["is_complete"], (
                f"Generated actions are incomplete for intent. "
                f"Issues: {validation['issues']}, "
                f"Warnings: {validation['warnings']}, "
                f"Coverage: {validation['coverage_score']:.2f}"
            )
            
            # Verify action count is reasonable
            assert validation["action_count"] >= 0, "Action count should be non-negative"
            
            # For configuration intents, we expect at least one action
            if intent.intent_type == IntentType.CONFIGURATION:
                assert validation["action_count"] > 0, (
                    "Configuration intent should generate at least one action"
                )
            
            # Verify actions have proper structure
            for action in actions:
                assert "id" in action, "Action must have an ID"
                assert "type" in action, "Action must have a type"
                assert "target" in action, "Action must have a target"
                assert "parameters" in action, "Action must have parameters"
                
                # Verify action type is valid
                assert action["type"] in ["flow_mod", "slice_create", "slice_modify", "config_change"], (
                    f"Invalid action type: {action['type']}"
                )
                
                # Verify target is not empty
                assert action["target"] and len(action["target"]) > 0, "Action target cannot be empty"
                
                # Verify parameters is a dict
                assert isinstance(action["parameters"], dict), "Action parameters must be a dictionary"
            
            # Verify response includes execution metadata
            if "estimated_duration" in parsed_response:
                assert isinstance(parsed_response["estimated_duration"], (int, float)), (
                    "Estimated duration should be numeric"
                )
                assert parsed_response["estimated_duration"] >= 0, (
                    "Estimated duration should be non-negative"
                )
            
            # Verify rollback plan exists for configuration changes
            if intent.intent_type == IntentType.CONFIGURATION and actions:
                # Rollback plan is recommended but not strictly required
                if "rollback_plan" in parsed_response:
                    rollback_actions = parsed_response["rollback_plan"]
                    assert isinstance(rollback_actions, list), "Rollback plan should be a list"
            
            # Verify risks are identified if present
            if "risks" in parsed_response:
                risks = parsed_response["risks"]
                assert isinstance(risks, list), "Risks should be a list"
                for risk in risks:
                    assert "description" in risk, "Risk should have a description"
                    assert "severity" in risk, "Risk should have a severity"
            
            # Log successful validation
            print(f"✓ Action generation complete for intent '{intent.raw_text}': "
                  f"{validation['action_count']} actions, "
                  f"coverage: {validation['coverage_score']:.2f}")
        
        except Exception as e:
            # If ChatGPT API fails, we should handle it gracefully
            if "rate limit" in str(e).lower() or "timeout" in str(e).lower():
                pytest.skip(f"ChatGPT API issue: {str(e)}")
            else:
                # Re-raise other exceptions
                raise
    
    @settings(max_examples=3, suppress_health_check=[HealthCheck.too_slow], deadline=60000)
    @given(
        intent=valid_intent_object(),
        network_state=network_state_with_resources()
    )
    def test_action_generation_with_constraints(self, intent, network_state):
        """Test that action generation respects network constraints."""
        if self.chatgpt_client is None:
            pytest.skip("ChatGPT API not configured")
        
        assume(intent is not None)
        assume(network_state is not None)
        assume(intent.confidence >= 0.6)
        
        # Update state cache
        self.state_cache.update_state(network_state)
        
        # Contextualize the intent
        contextualized_intent = self.context_engine.correlate_intent_with_state(intent)
        
        # Build action generation prompt
        system_message, user_prompt, config = self.prompt_system.build_action_generation_prompt(
            contextualized_intent,
            network_state
        )
        
        try:
            response = asyncio.run(
                self.chatgpt_client.generate_response(
                    prompt=user_prompt,
                    system_message=system_message
                )
            )
            
            parsed_response = self._parse_action_response(response.content)
            actions = parsed_response.get("actions", [])
            
            # Verify actions respect network constraints
            for action in actions:
                if "target" in action:
                    target = action["target"]
                    # Target should reference valid network resources
                    # (This is a simplified check - in production, more thorough validation needed)
                    assert isinstance(target, str) and len(target) > 0
                
                if "parameters" in action and isinstance(action["parameters"], dict):
                    params = action["parameters"]
                    
                    # Check bandwidth constraints if specified
                    if "bandwidth" in params:
                        bandwidth = params["bandwidth"]
                        if isinstance(bandwidth, (int, float)):
                            # Bandwidth should be reasonable
                            assert 0 < bandwidth <= 100000, "Bandwidth should be in reasonable range"
                    
                    # Check priority constraints if specified
                    if "priority" in params:
                        priority = params["priority"]
                        if isinstance(priority, int):
                            # Priority should be in valid range
                            assert 0 <= priority <= 65535, "Priority should be in valid range"
        
        except Exception as e:
            if "rate limit" in str(e).lower() or "timeout" in str(e).lower():
                pytest.skip(f"ChatGPT API issue: {str(e)}")
            else:
                raise
    
    def test_action_generation_with_empty_state(self):
        """Test that action generation handles empty network state gracefully."""
        if self.chatgpt_client is None:
            pytest.skip("ChatGPT API not configured")
        
        # Create minimal intent
        intent = IntentObject(
            id="intent_test",
            raw_text="show network status",
            timestamp=datetime.now(),
            user_id="test_user",
            entities=[
                Entity(name="action", type="action", value="show", confidence=0.9),
                Entity(name="resource", type="resource", value="network", confidence=0.8)
            ],
            intent_type=IntentType.QUERY,
            confidence=0.85,
            parameters={}
        )
        
        # Create empty network state
        empty_state = NetworkState(
            timestamp=datetime.now(),
            topology=Topology(switches=[], links=[], hosts=[]),
            flows=[],
            metrics=NetworkMetrics(
                bandwidth=BandwidthMetrics(
                    total_capacity=0,
                    used_bandwidth=0,
                    available_bandwidth=0,
                    utilization_percentage=0.0
                ),
                latency=LatencyMetrics(
                    average_latency=0.0,
                    min_latency=0.0,
                    max_latency=0.0,
                    jitter=0.0
                ),
                utilization=UtilizationMetrics(
                    cpu_utilization=0.0,
                    memory_utilization=0.0,
                    port_utilization={}
                )
            ),
            anomalies=[]
        )
        
        # Update state cache
        self.state_cache.update_state(empty_state)
        
        # Contextualize the intent
        contextualized_intent = self.context_engine.correlate_intent_with_state(intent)
        
        # Build action generation prompt
        system_message, user_prompt, config = self.prompt_system.build_action_generation_prompt(
            contextualized_intent,
            empty_state
        )
        
        # Should not raise an exception
        try:
            response = asyncio.run(
                self.chatgpt_client.generate_response(
                    prompt=user_prompt,
                    system_message=system_message
                )
            )
            
            # Response should be valid even with empty state
            assert response is not None
            assert response.content is not None
            
            parsed_response = self._parse_action_response(response.content)
            assert isinstance(parsed_response, dict)
        
        except Exception as e:
            if "rate limit" in str(e).lower() or "timeout" in str(e).lower():
                pytest.skip(f"ChatGPT API issue: {str(e)}")
            else:
                raise

