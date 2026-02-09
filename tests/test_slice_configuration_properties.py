"""Property-based tests for network slice configuration completeness."""

import pytest
import asyncio
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from datetime import datetime
from typing import List, Dict, Any

from src.services.chatgpt_client import ChatGPTClient
from src.services.prompt_engineering import PromptEngineeringSystem
from src.services.context_analyzer import ContextCorrelationEngine, NetworkStateCache
from src.models.intent import IntentObject, IntentType, Entity
from src.models.network import (
    NetworkState, Topology, Switch, Link, Host, NetworkMetrics,
    BandwidthMetrics, LatencyMetrics, UtilizationMetrics
)
from src.models.slices import (
    NetworkSlice, SliceResources, Path, Policy, ServiceLevelAgreement, SliceStatus
)
from src.models.actions import NetworkAction, ActionType
import json


class TestSliceConfigurationProperties:
    """Property-based tests for slice configuration completeness."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.prompt_system = PromptEngineeringSystem()
        self.state_cache = NetworkStateCache(default_ttl=600)
        self.context_engine = ContextCorrelationEngine(self.state_cache)
        
        try:
            self.chatgpt_client = ChatGPTClient()
        except ValueError:
            self.chatgpt_client = None
    
    @staticmethod
    @st.composite
    def slice_creation_intent(draw):
        """Generate intent for network slice creation."""
        slice_name = f"slice_{draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyz', min_size=3, max_size=10))}"
        bandwidth = draw(st.integers(min_value=100, max_value=10000))
        latency = draw(st.floats(min_value=1.0, max_value=100.0))
        
        # Generate entities for slice creation
        entities = [
            Entity(
                name="action",
                type="action",
                value=draw(st.sampled_from(["create", "setup", "configure", "provision"])),
                confidence=0.9
            ),
            Entity(
                name="resource_type",
                type="resource",
                value="slice",
                confidence=0.95
            ),
            Entity(
                name="slice_name",
                type="identifier",
                value=slice_name,
                confidence=0.85
            ),
            Entity(
                name="bandwidth",
                type="parameter",
                value=str(bandwidth),
                confidence=0.8
            )
        ]
        
        # Add optional latency requirement
        if draw(st.booleans()):
            entities.append(
                Entity(
                    name="latency",
                    type="parameter",
                    value=str(latency),
                    confidence=0.75
                )
            )
        
        # Generate intent text
        intent_templates = [
            f"create network slice {slice_name} with {bandwidth} Mbps bandwidth",
            f"set up slice {slice_name} with bandwidth {bandwidth} Mbps and latency {latency} ms",
            f"provision network slice {slice_name} requiring {bandwidth} Mbps",
            f"configure slice {slice_name} with {bandwidth} Mbps bandwidth and max latency {latency} ms"
        ]
        
        intent_text = draw(st.sampled_from(intent_templates))
        
        # Generate parameters
        parameters = {
            "slice_name": slice_name,
            "bandwidth": bandwidth,
            "latency_max": latency
        }
        
        # Add optional parameters
        if draw(st.booleans()):
            parameters["priority"] = draw(st.integers(min_value=1, max_value=10))
        
        if draw(st.booleans()):
            parameters["availability"] = draw(st.floats(min_value=0.9, max_value=0.999))
        
        if draw(st.booleans()):
            num_switches = draw(st.integers(min_value=2, max_value=5))
            parameters["switches"] = [f"switch-{i}" for i in range(1, num_switches + 1)]
        
        return IntentObject(
            id=f"intent_{draw(st.integers(min_value=1000, max_value=9999))}",
            raw_text=intent_text,
            timestamp=datetime.now(),
            user_id=f"user_{draw(st.integers(min_value=1, max_value=100))}",
            entities=entities,
            intent_type=IntentType.CONFIGURATION,
            confidence=draw(st.floats(min_value=0.7, max_value=1.0)),
            parameters=parameters
        )
    
    @staticmethod
    @st.composite
    def network_state_with_available_resources(draw):
        """Generate NetworkState with sufficient resources for slice creation."""
        # Generate switches with good capacity
        num_switches = draw(st.integers(min_value=4, max_value=8))
        switches = []
        for i in range(num_switches):
            switch = Switch(
                id=f"switch-{i+1}",
                name=f"Switch {i+1}",
                dpid=f"00:00:00:00:00:00:00:{i+1:02x}",
                ports=[j+1 for j in range(8)],
                status="active"
            )
            switches.append(switch)
        
        # Generate links with high bandwidth
        links = []
        for i in range(num_switches - 1):
            link = Link(
                id=f"link-{i+1}",
                source_switch=switches[i].id,
                source_port=1,
                destination_switch=switches[i+1].id,
                destination_port=2,
                bandwidth=draw(st.integers(min_value=1000, max_value=10000)),
                latency=draw(st.floats(min_value=0.5, max_value=10.0)),
                status="active"
            )
            links.append(link)
        
        # Add some cross-links for redundancy
        if num_switches >= 4:
            for i in range(0, num_switches - 2, 2):
                link = Link(
                    id=f"link-cross-{i}",
                    source_switch=switches[i].id,
                    source_port=3,
                    destination_switch=switches[i+2].id,
                    destination_port=3,
                    bandwidth=draw(st.integers(min_value=1000, max_value=10000)),
                    latency=draw(st.floats(min_value=1.0, max_value=15.0)),
                    status="active"
                )
                links.append(link)
        
        # Generate hosts
        num_hosts = draw(st.integers(min_value=2, max_value=6))
        hosts = []
        for i in range(num_hosts):
            host = Host(
                id=f"host-{i+1}",
                mac_address=f"00:00:00:00:00:{i+1:02x}",
                ip_address=f"10.0.0.{i+1}",
                connected_switch=switches[i % len(switches)].id,
                connected_port=4,
                status="active"
            )
            hosts.append(host)
        
        topology = Topology(switches=switches, links=links, hosts=hosts)
        
        # Generate metrics showing available capacity
        total_bandwidth = sum(link.bandwidth for link in links)
        used_bandwidth = draw(st.integers(min_value=100, max_value=int(total_bandwidth * 0.3)))
        
        bandwidth_metrics = BandwidthMetrics(
            total_capacity=total_bandwidth,
            used_bandwidth=used_bandwidth,
            available_bandwidth=total_bandwidth - used_bandwidth,
            utilization_percentage=draw(st.floats(min_value=10.0, max_value=50.0))
        )
        
        latency_metrics = LatencyMetrics(
            average_latency=draw(st.floats(min_value=1.0, max_value=20.0)),
            min_latency=draw(st.floats(min_value=0.5, max_value=5.0)),
            max_latency=draw(st.floats(min_value=20.0, max_value=100.0)),
            jitter=draw(st.floats(min_value=0.1, max_value=5.0))
        )
        
        utilization_metrics = UtilizationMetrics(
            cpu_utilization=draw(st.floats(min_value=10.0, max_value=50.0)),
            memory_utilization=draw(st.floats(min_value=20.0, max_value=50.0)),
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
    
    def _parse_slice_configuration_response(self, response_content: str) -> Dict[str, Any]:
        """Parse slice configuration response from ChatGPT."""
        try:
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
    
    def _validate_slice_configuration_completeness(
        self,
        intent: IntentObject,
        actions: List[Dict[str, Any]],
        network_state: NetworkState
    ) -> Dict[str, Any]:
        """
        Validate that generated slice configuration is complete.
        
        According to Requirement 5.1:
        "WHEN an intent requests NetworkSlice creation, THE LLM_Module SHALL 
        generate the configurations appropriate for all components involved"
        """
        validation_result = {
            "is_complete": False,
            "issues": [],
            "warnings": [],
            "component_coverage": {},
            "completeness_score": 0.0
        }
        
        if not actions:
            validation_result["issues"].append("No actions generated for slice creation intent")
            return validation_result
        
        # Check for slice creation action
        slice_create_actions = [a for a in actions if a.get("type") == "slice_create"]
        if not slice_create_actions:
            validation_result["issues"].append("No slice_create action found")
            return validation_result
        
        validation_result["component_coverage"]["slice_create_action"] = True
        validation_result["completeness_score"] += 0.2
        
        # Analyze the primary slice creation action
        primary_action = slice_create_actions[0]
        parameters = primary_action.get("parameters", {})
        
        # Component 1: Slice identification (name/id)
        if "slice_name" in parameters or "slice_id" in parameters:
            validation_result["component_coverage"]["slice_identification"] = True
            validation_result["completeness_score"] += 0.15
        else:
            validation_result["issues"].append("Slice name/ID not specified")
        
        # Component 2: Resource allocation
        if "resources" in parameters:
            resources = parameters["resources"]
            validation_result["component_coverage"]["resource_allocation"] = True
            validation_result["completeness_score"] += 0.15
            
            # Check bandwidth allocation
            if "bandwidth" in resources:
                validation_result["component_coverage"]["bandwidth_allocation"] = True
                validation_result["completeness_score"] += 0.1
                
                # Verify bandwidth is reasonable
                bandwidth = resources["bandwidth"]
                if isinstance(bandwidth, (int, float)):
                    available = network_state.metrics.bandwidth.available_bandwidth
                    if bandwidth > available:
                        validation_result["warnings"].append(
                            f"Requested bandwidth {bandwidth} exceeds available {available}"
                        )
            else:
                validation_result["warnings"].append("Bandwidth not specified in resources")
            
            # Check switch allocation
            if "switches" in resources and resources["switches"]:
                validation_result["component_coverage"]["switch_allocation"] = True
                validation_result["completeness_score"] += 0.1
                
                # Verify switches exist in network state
                available_switches = {s.id for s in network_state.topology.switches}
                requested_switches = set(resources["switches"])
                invalid_switches = requested_switches - available_switches
                if invalid_switches:
                    validation_result["warnings"].append(
                        f"Requested switches not in topology: {invalid_switches}"
                    )
            else:
                validation_result["warnings"].append("No switches allocated to slice")
            
            # Check path allocation
            if "paths" in resources and resources["paths"]:
                validation_result["component_coverage"]["path_allocation"] = True
                validation_result["completeness_score"] += 0.1
            else:
                validation_result["warnings"].append("No paths defined for slice")
        else:
            validation_result["issues"].append("Resource allocation not specified")
        
        # Component 3: SLA configuration
        if "sla" in parameters:
            sla = parameters["sla"]
            validation_result["component_coverage"]["sla_configuration"] = True
            validation_result["completeness_score"] += 0.1
            
            # Check SLA components
            sla_components = ["min_bandwidth", "max_latency", "availability"]
            for component in sla_components:
                if component in sla:
                    validation_result["component_coverage"][f"sla_{component}"] = True
                    validation_result["completeness_score"] += 0.02
        else:
            validation_result["warnings"].append("SLA not specified")
        
        # Component 4: Policies
        if "policies" in parameters and parameters["policies"]:
            validation_result["component_coverage"]["policies"] = True
            validation_result["completeness_score"] += 0.08
            
            # Check policy types
            policy_types = [p.get("type") for p in parameters["policies"] if isinstance(p, dict)]
            if policy_types:
                validation_result["component_coverage"]["policy_types"] = policy_types
        else:
            validation_result["warnings"].append("No policies defined for slice")
        
        # Component 5: Supporting configuration actions
        # Check for related configuration actions (QoS, routing, etc.)
        config_actions = [a for a in actions if a.get("type") == "config_change"]
        if config_actions:
            validation_result["component_coverage"]["supporting_config"] = True
            validation_result["completeness_score"] += 0.05
            validation_result["component_coverage"]["config_action_count"] = len(config_actions)
        
        # Component 6: Flow rules for slice
        flow_actions = [a for a in actions if a.get("type") == "flow_mod"]
        if flow_actions:
            validation_result["component_coverage"]["flow_rules"] = True
            validation_result["completeness_score"] += 0.05
            validation_result["component_coverage"]["flow_action_count"] = len(flow_actions)
        
        # Determine overall completeness
        # A slice configuration is complete if:
        # 1. Has slice_create action
        # 2. Has slice identification
        # 3. Has resource allocation with at least bandwidth
        # 4. Completeness score >= 0.6
        validation_result["is_complete"] = (
            len(validation_result["issues"]) == 0 and
            validation_result["completeness_score"] >= 0.6 and
            validation_result["component_coverage"].get("slice_create_action", False) and
            validation_result["component_coverage"].get("slice_identification", False) and
            validation_result["component_coverage"].get("resource_allocation", False)
        )
        
        return validation_result
    
    @settings(max_examples=3, suppress_health_check=[HealthCheck.too_slow], deadline=60000)
    @given(
        intent=slice_creation_intent(),
        network_state=network_state_with_available_resources()
    )
    def test_slice_configuration_completeness(self, intent, network_state):
        """
        **Feature: llm-integration-module, Property 16: Slice configuration completeness**
        
        For any intent requesting NetworkSlice creation, all necessary component 
        configurations should be generated to fully implement the slice requirements.
        
        **Validates: Requirements 5.1**
        
        Requirement 5.1 states:
        "WHEN an intent richiede la creazione di un Network_Slice, THE LLM_Module 
        SHALL generare le configurazioni appropriate per tutti i componenti coinvolti"
        
        This test verifies that slice creation intents result in complete configurations
        including: slice identification, resource allocation (bandwidth, switches, paths),
        SLA requirements, policies, and supporting network configurations.
        """
        if self.chatgpt_client is None:
            pytest.skip("ChatGPT API not configured")
        
        assume(intent is not None)
        assume(network_state is not None)
        assume(len(intent.entities) > 0)
        assume(intent.confidence >= 0.7)
        assume(intent.intent_type == IntentType.CONFIGURATION)
        
        # Verify intent is about slice creation
        slice_related = any(
            e.value in ["slice", "create", "setup", "provision", "configure"]
            for e in intent.entities
        )
        assume(slice_related)
        
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
            # Generate actions using ChatGPT
            response = asyncio.run(
                self.chatgpt_client.generate_response(
                    prompt=user_prompt,
                    system_message=system_message
                )
            )
            
            # Parse the response
            parsed_response = self._parse_slice_configuration_response(response.content)
            
            assert isinstance(parsed_response, dict), "Response should be a dictionary"
            
            # Extract actions
            actions = parsed_response.get("actions", [])
            
            # Validate slice configuration completeness
            validation = self._validate_slice_configuration_completeness(
                intent, actions, network_state
            )
            
            # Core property: Slice configuration should be complete
            assert validation["is_complete"], (
                f"Slice configuration is incomplete. "
                f"Issues: {validation['issues']}, "
                f"Warnings: {validation['warnings']}, "
                f"Completeness score: {validation['completeness_score']:.2f}, "
                f"Component coverage: {validation['component_coverage']}"
            )
            
            # Verify essential components are present
            assert validation["component_coverage"].get("slice_create_action"), (
                "Slice creation action must be present"
            )
            
            assert validation["component_coverage"].get("slice_identification"), (
                "Slice must have identification (name or ID)"
            )
            
            assert validation["component_coverage"].get("resource_allocation"), (
                "Slice must have resource allocation"
            )
            
            # Verify completeness score is reasonable
            assert validation["completeness_score"] >= 0.6, (
                f"Completeness score {validation['completeness_score']:.2f} is too low"
            )
            
            # Verify slice_create action has proper structure
            slice_actions = [a for a in actions if a.get("type") == "slice_create"]
            assert len(slice_actions) > 0, "At least one slice_create action required"
            
            primary_slice_action = slice_actions[0]
            assert "id" in primary_slice_action, "Slice action must have ID"
            assert "type" in primary_slice_action, "Slice action must have type"
            assert "target" in primary_slice_action, "Slice action must have target"
            assert "parameters" in primary_slice_action, "Slice action must have parameters"
            
            # Verify parameters contain essential slice configuration
            params = primary_slice_action["parameters"]
            assert isinstance(params, dict), "Parameters must be a dictionary"
            
            # Check for slice name
            assert "slice_name" in params or "slice_id" in params, (
                "Slice must have name or ID in parameters"
            )
            
            # Check for resources
            assert "resources" in params, "Slice must have resources defined"
            resources = params["resources"]
            assert isinstance(resources, dict), "Resources must be a dictionary"
            
            # Verify bandwidth is specified
            assert "bandwidth" in resources, "Resources must include bandwidth allocation"
            bandwidth = resources["bandwidth"]
            assert isinstance(bandwidth, (int, float)), "Bandwidth must be numeric"
            assert bandwidth > 0, "Bandwidth must be positive"
            
            # Verify switches are specified (at least for complete configuration)
            if validation["completeness_score"] >= 0.7:
                assert "switches" in resources, (
                    "High-quality slice configuration should include switch allocation"
                )
                if "switches" in resources:
                    switches = resources["switches"]
                    assert isinstance(switches, list), "Switches must be a list"
                    assert len(switches) >= 2, (
                        "Slice should have at least 2 switches for meaningful topology"
                    )
            
            # Log successful validation
            print(f"✓ Slice configuration complete for intent '{intent.raw_text}': "
                  f"completeness score: {validation['completeness_score']:.2f}, "
                  f"components: {list(validation['component_coverage'].keys())}")
        
        except Exception as e:
            if "rate limit" in str(e).lower() or "timeout" in str(e).lower():
                pytest.skip(f"ChatGPT API issue: {str(e)}")
            else:
                raise
    
    def test_slice_configuration_with_minimal_intent(self):
        """Test slice configuration with minimal intent information."""
        if self.chatgpt_client is None:
            pytest.skip("ChatGPT API not configured")
        
        # Create minimal slice creation intent
        intent = IntentObject(
            id="intent_minimal",
            raw_text="create network slice for tenant A",
            timestamp=datetime.now(),
            user_id="test_user",
            entities=[
                Entity(name="action", type="action", value="create", confidence=0.9),
                Entity(name="resource", type="resource", value="slice", confidence=0.9),
                Entity(name="tenant", type="identifier", value="tenant_a", confidence=0.8)
            ],
            intent_type=IntentType.CONFIGURATION,
            confidence=0.85,
            parameters={"tenant": "tenant_a"}
        )
        
        # Create network state with resources
        switches = [
            Switch(id=f"switch-{i}", name=f"Switch {i}", dpid=f"00:00:00:00:00:00:00:0{i}", 
                   ports=[1, 2, 3, 4], status="active")
            for i in range(1, 5)
        ]
        
        links = [
            Link(id=f"link-{i}", source_switch=f"switch-{i}", source_port=1,
                 destination_switch=f"switch-{i+1}", destination_port=2,
                 bandwidth=1000, latency=5.0, status="active")
            for i in range(1, 4)
        ]
        
        topology = Topology(switches=switches, links=links, hosts=[])
        
        network_state = NetworkState(
            timestamp=datetime.now(),
            topology=topology,
            flows=[],
            metrics=NetworkMetrics(
                bandwidth=BandwidthMetrics(
                    total_capacity=3000,
                    used_bandwidth=500,
                    available_bandwidth=2500,
                    utilization_percentage=16.7
                ),
                latency=LatencyMetrics(
                    average_latency=5.0,
                    min_latency=2.0,
                    max_latency=10.0,
                    jitter=1.0
                ),
                utilization=UtilizationMetrics(
                    cpu_utilization=30.0,
                    memory_utilization=40.0,
                    port_utilization={}
                )
            ),
            anomalies=[]
        )
        
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
            # Generate actions
            response = asyncio.run(
                self.chatgpt_client.generate_response(
                    prompt=user_prompt,
                    system_message=system_message
                )
            )
            
            # Parse response
            parsed_response = self._parse_slice_configuration_response(response.content)
            actions = parsed_response.get("actions", [])
            
            # Even with minimal intent, system should generate reasonable slice configuration
            validation = self._validate_slice_configuration_completeness(
                intent, actions, network_state
            )
            
            # Should have at least basic components
            assert validation["component_coverage"].get("slice_create_action"), (
                "Should generate slice_create action even with minimal intent"
            )
            
            # May not be fully complete, but should have some configuration
            assert validation["completeness_score"] > 0.3, (
                "Should generate some slice configuration even with minimal intent"
            )
        
        except Exception as e:
            if "rate limit" in str(e).lower() or "timeout" in str(e).lower():
                pytest.skip(f"ChatGPT API issue: {str(e)}")
            else:
                raise
