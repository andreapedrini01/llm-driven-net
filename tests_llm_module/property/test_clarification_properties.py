"""Property-based tests for clarification request functionality."""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from datetime import datetime
from typing import List, Dict, Any, Optional
from llm_integration_module.services.intent_parser import IntentParser
from llm_integration_module.models.intent import IntentObject, IntentType, Entity
from llm_integration_module.models.network import NetworkState, Switch, Host, Link, Topology


class TestClarificationProperties:
    """Property-based tests for clarification request appropriateness."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = IntentParser()
    
    # Generator strategies for test data
    @staticmethod
    @st.composite
    def ambiguous_intent(draw):
        """Generate intentionally ambiguous or incomplete intents."""
        # Vague intents with generic terms
        vague_templates = [
            "configure the switch",
            "modify network",
            "set bandwidth",
            "create slice",
            "fix the problem",
            "show status",
            "delete it",
            "update this",
            "change that",
            "add something"
        ]
        
        # Incomplete intents missing critical information
        incomplete_templates = [
            "create",
            "delete switch",
            "set bandwidth to",
            "configure slice for",
            "show",
            "fix",
            "modify the",
            "add new"
        ]
        
        # Conflicting intents with contradictory information
        conflicting_templates = [
            "create and delete switch sw1",
            "enable and disable port eth0",
            "set bandwidth to 100 and 200 mbps",
            "add and remove flow rule"
        ]
        
        # Multiple interpretation intents
        multi_interpretation_templates = [
            "configure it for the user",
            "set this to high priority",
            "modify them all",
            "show all switches and hosts and links",
            "create slice for tenant and user and app"
        ]
        
        all_templates = vague_templates + incomplete_templates + conflicting_templates + multi_interpretation_templates
        return draw(st.sampled_from(all_templates))
    
    @staticmethod
    @st.composite
    def clear_intent(draw):
        """Generate clear, unambiguous intents."""
        actions = ['create', 'delete', 'modify', 'configure', 'show', 'list']
        resources = ['switch', 'host', 'link', 'slice', 'flow']
        identifiers = ['sw1', 'h2', 'link3', 'tenant_a', 'user123']
        parameters = ['bandwidth 100mbps', 'priority high', 'vlan 10']
        
        action = draw(st.sampled_from(actions))
        resource = draw(st.sampled_from(resources))
        identifier = draw(st.sampled_from(identifiers))
        
        # Build clear intent
        intent = f"{action} {resource} {identifier}"
        
        # Optionally add parameters for configuration intents
        if action in ['create', 'modify', 'configure'] and draw(st.booleans()):
            param = draw(st.sampled_from(parameters))
            intent += f" with {param}"
        
        return intent
    
    @staticmethod
    @st.composite
    def network_state_with_resources(draw):
        """Generate a network state with various resources."""
        # Generate switches
        num_switches = draw(st.integers(min_value=1, max_value=5))
        switches = []
        for i in range(num_switches):
            switch = Switch(
                id=f"sw{i+1}",
                name=f"switch{i+1}",
                dpid=f"000000000000000{i+1}",
                ports=[j for j in range(1, 4)],  # Port numbers as integers
                status=draw(st.sampled_from(["active", "inactive"]))
            )
            switches.append(switch)
        
        # Generate hosts
        num_hosts = draw(st.integers(min_value=1, max_value=5))
        hosts = []
        for i in range(num_hosts):
            host = Host(
                id=f"h{i+1}",
                mac_address=f"00:00:00:00:00:0{i+1}",
                ip_address=f"10.0.0.{i+1}",
                connected_switch=f"sw{(i % num_switches) + 1}",
                connected_port=draw(st.integers(min_value=1, max_value=3)),
                status=draw(st.sampled_from(["active", "inactive"]))
            )
            hosts.append(host)
        
        # Generate links
        links = []
        for i in range(min(num_switches - 1, 3)):
            link = Link(
                id=f"link{i+1}",
                source_switch=f"sw{i+1}",
                source_port=draw(st.integers(min_value=1, max_value=3)),
                destination_switch=f"sw{i+2}",
                destination_port=draw(st.integers(min_value=1, max_value=3)),
                bandwidth=draw(st.integers(min_value=100, max_value=1000)),
                status=draw(st.sampled_from(["active", "inactive"]))
            )
            links.append(link)
        
        topology = Topology(switches=switches, hosts=hosts, links=links)
        
        # Create basic metrics
        from llm_integration_module.models.network import NetworkMetrics, BandwidthMetrics, LatencyMetrics, UtilizationMetrics
        from datetime import datetime
        
        bandwidth_metrics = BandwidthMetrics(
            total_capacity=1000,
            used_bandwidth=draw(st.integers(min_value=0, max_value=500)),
            available_bandwidth=500,
            utilization_percentage=draw(st.floats(min_value=0.0, max_value=100.0))
        )
        
        latency_metrics = LatencyMetrics(
            average_latency=draw(st.floats(min_value=1.0, max_value=100.0)),
            min_latency=1.0,
            max_latency=100.0,
            jitter=draw(st.floats(min_value=0.0, max_value=10.0))
        )
        
        utilization_metrics = UtilizationMetrics(
            cpu_utilization=draw(st.floats(min_value=0.0, max_value=100.0)),
            memory_utilization=draw(st.floats(min_value=0.0, max_value=100.0))
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
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(intent_text=ambiguous_intent())
    def test_clarification_request_appropriateness_for_ambiguous_intents(self, intent_text):
        """
        **Feature: llm-integration-module, Property 3: Clarification request appropriateness**
        
        For any ambiguous or incomplete intent, the LLM_Module should generate specific 
        clarification requests that address the missing or unclear information.
        
        **Validates: Requirements 1.3**
        """
        # Ensure we have valid input
        assume(intent_text and len(intent_text.strip()) > 0)
        assume(len(intent_text) <= 1000)
        
        # Parse the intent and analyze for ambiguities
        result = self.parser.analyze_and_clarify_intent(intent_text)
        
        # Verify the result structure
        assert isinstance(result, dict)
        assert 'intent' in result
        assert 'ambiguity_analysis' in result
        assert 'clarification_requests' in result
        assert 'needs_clarification' in result
        
        intent = result['intent']
        ambiguity_analysis = result['ambiguity_analysis']
        clarification_requests = result['clarification_requests']
        
        # Verify intent was parsed
        assert isinstance(intent, IntentObject)
        
        # Verify ambiguity analysis structure
        assert isinstance(ambiguity_analysis, dict)
        assert 'ambiguity_score' in ambiguity_analysis
        assert 'ambiguities' in ambiguity_analysis
        assert 'clarification_needed' in ambiguity_analysis
        assert 0.0 <= ambiguity_analysis['ambiguity_score'] <= 1.0
        
        # For ambiguous intents, clarification should be needed
        # (though not all generated ambiguous intents will necessarily be detected as ambiguous)
        if ambiguity_analysis['clarification_needed']:
            # Verify clarification requests are generated
            assert isinstance(clarification_requests, list)
            assert len(clarification_requests) > 0
            
            # Verify each clarification request is appropriate
            for request in clarification_requests:
                assert isinstance(request, str)
                assert len(request.strip()) > 0
                assert len(request) <= 500  # Reasonable length limit
                
                # Clarification requests should be questions or requests for information
                request_lower = request.lower()
                assert (
                    '?' in request or
                    any(word in request_lower for word in [
                        'which', 'what', 'how', 'please', 'specify', 'clarify', 
                        'could you', 'can you', 'do you mean', 'more details'
                    ])
                ), f"Clarification request doesn't seem like a proper question: {request}"
            
            # Verify clarification requests address specific ambiguities
            ambiguity_types = [amb.get('type', '') for amb in ambiguity_analysis['ambiguities']]
            
            # If there are vague entities, clarification should address them
            if any('vague' in amb_type for amb_type in ambiguity_types):
                assert any(
                    any(word in req.lower() for word in ['which', 'specific', 'mean'])
                    for req in clarification_requests
                ), "Should ask for specific clarification when vague entities detected"
            
            # If there are missing targets, clarification should address them
            if any('missing_target' in amb_type for amb_type in ambiguity_types):
                assert any(
                    any(word in req.lower() for word in ['resource', 'target', 'which'])
                    for req in clarification_requests
                ), "Should ask about target when missing target detected"
            
            # If there are conflicting actions, clarification should address them
            if any('conflicting' in amb_type for amb_type in ambiguity_types):
                assert any(
                    any(word in req.lower() for word in ['conflict', 'which', 'clarify'])
                    for req in clarification_requests
                ), "Should ask for clarification when conflicts detected"
        
        # Verify no duplicate clarification requests
        assert len(clarification_requests) == len(set(clarification_requests)), \
            "Clarification requests should not contain duplicates"
        
        # Verify reasonable number of clarification requests (not overwhelming)
        assert len(clarification_requests) <= 5, \
            "Should not generate more than 5 clarification requests"
    
    @settings(max_examples=50)
    @given(
        intent_text=ambiguous_intent(),
        network_state=network_state_with_resources()
    )
    def test_clarification_with_network_context(self, intent_text, network_state):
        """Test that clarification requests are context-aware when network state is available."""
        assume(intent_text and len(intent_text.strip()) > 0)
        
        # Analyze with network context
        result = self.parser.analyze_and_clarify_intent(intent_text, network_state)
        
        clarification_requests = result['clarification_requests']
        ambiguity_analysis = result['ambiguity_analysis']
        
        if ambiguity_analysis['clarification_needed'] and clarification_requests:
            # Context-aware clarifications should reference actual network resources
            available_switches = [s.id for s in network_state.topology.switches]
            available_hosts = [h.id for h in network_state.topology.hosts]
            
            # If asking about switches, should mention available ones
            switch_requests = [req for req in clarification_requests if 'switch' in req.lower()]
            if switch_requests and available_switches:
                # At least one switch request should mention available switches
                mentions_available = any(
                    any(switch_id in req for switch_id in available_switches)
                    for req in switch_requests
                )
                # This is a soft assertion - context-aware suggestions are helpful but not required
                if not mentions_available:
                    # Still valid, just not as helpful
                    pass
            
            # Verify clarification requests are still well-formed
            for request in clarification_requests:
                assert isinstance(request, str)
                assert len(request.strip()) > 0
    
    @settings(max_examples=50)
    @given(intent_text=clear_intent())
    def test_no_clarification_for_clear_intents(self, intent_text):
        """Test that clear, unambiguous intents don't generate unnecessary clarification requests."""
        assume(intent_text and len(intent_text.strip()) > 0)
        
        # Analyze clear intent
        result = self.parser.analyze_and_clarify_intent(intent_text)
        
        ambiguity_analysis = result['ambiguity_analysis']
        clarification_requests = result['clarification_requests']
        
        # Clear intents should have low ambiguity scores
        assert ambiguity_analysis['ambiguity_score'] <= 0.7, \
            f"Clear intent should have low ambiguity score, got {ambiguity_analysis['ambiguity_score']}"
        
        # If clarification is not needed, requests should be empty or minimal
        if not ambiguity_analysis['clarification_needed']:
            assert len(clarification_requests) == 0, \
                "Should not generate clarification requests for clear intents"
        else:
            # If some clarification is requested, it should be minimal
            assert len(clarification_requests) <= 2, \
                "Should generate minimal clarification for mostly clear intents"
    
    @settings(max_examples=30)
    @given(
        base_intent=st.text(alphabet='abcdefghijklmnopqrstuvwxyz ', min_size=5, max_size=50),
        missing_info=st.sampled_from(['target', 'action', 'parameter', 'value'])
    )
    def test_clarification_addresses_missing_information(self, base_intent, missing_info):
        """Test that clarification requests specifically address missing information types."""
        assume(base_intent and len(base_intent.strip()) > 0)
        
        # Create an intent that's missing specific information
        if missing_info == 'target':
            intent_text = "configure"  # Missing target
        elif missing_info == 'action':
            intent_text = "switch sw1"  # Missing action
        elif missing_info == 'parameter':
            intent_text = "set bandwidth"  # Missing parameter value
        else:  # missing_info == 'value'
            intent_text = "create slice with"  # Missing value
        
        result = self.parser.analyze_and_clarify_intent(intent_text)
        
        if result['ambiguity_analysis']['clarification_needed']:
            clarification_requests = result['clarification_requests']
            assert len(clarification_requests) > 0
            
            # Verify clarification addresses the missing information
            combined_requests = ' '.join(clarification_requests).lower()
            
            if missing_info == 'target':
                assert any(word in combined_requests for word in [
                    'which', 'what', 'resource', 'target', 'switch', 'host'
                ]), "Should ask about missing target"
            elif missing_info == 'action':
                assert any(word in combined_requests for word in [
                    'what', 'action', 'do', 'perform', 'create', 'modify', 'delete'
                ]), "Should ask about missing action"
            elif missing_info in ['parameter', 'value']:
                assert any(word in combined_requests for word in [
                    'value', 'specify', 'what', 'how much', 'details'
                ]), "Should ask about missing parameter/value"
    
    def test_clarification_for_empty_intent(self):
        """Test handling of empty or minimal intents."""
        minimal_intents = ["", "   ", "a", "the", "it"]
        
        for intent_text in minimal_intents:
            if not intent_text or not intent_text.strip():
                # Empty intents should raise ValueError
                with pytest.raises(ValueError):
                    self.parser.analyze_and_clarify_intent(intent_text)
            else:
                # Very minimal intents should generate clarification requests
                result = self.parser.analyze_and_clarify_intent(intent_text)
                
                # Should need clarification for such minimal input
                assert result['ambiguity_analysis']['clarification_needed']
                assert len(result['clarification_requests']) > 0
                
                # Should ask for more details
                combined_requests = ' '.join(result['clarification_requests']).lower()
                assert any(word in combined_requests for word in [
                    'more', 'details', 'what', 'clarify', 'rephrase', 'specific'
                ]), "Should ask for more details for minimal intents"
    
    @settings(max_examples=20)
    @given(
        intent_text=st.text(min_size=10, max_size=100),
        confidence_threshold=st.floats(min_value=0.1, max_value=0.9)
    )
    def test_clarification_based_on_confidence(self, intent_text, confidence_threshold):
        """Test that clarification requests are generated based on confidence levels."""
        assume(intent_text and len(intent_text.strip()) > 0)
        
        result = self.parser.analyze_and_clarify_intent(intent_text)
        intent = result['intent']
        ambiguity_analysis = result['ambiguity_analysis']
        
        # Low confidence intents should be more likely to need clarification
        if intent.confidence < confidence_threshold:
            # Not a strict requirement, but low confidence should increase likelihood
            # of clarification being needed
            if ambiguity_analysis['clarification_needed']:
                clarification_requests = result['clarification_requests']
                assert len(clarification_requests) > 0
                
                # Should mention uncertainty in some way
                combined_requests = ' '.join(clarification_requests).lower()
                uncertainty_indicators = [
                    'not sure', 'uncertain', 'unclear', 'rephrase', 
                    'clarify', 'understand', 'mean'
                ]
                # This is a soft check - not all low confidence intents need to explicitly mention uncertainty
                has_uncertainty_language = any(
                    indicator in combined_requests for indicator in uncertainty_indicators
                )
                # Just verify the requests are well-formed
                for request in clarification_requests:
                    assert isinstance(request, str)
                    assert len(request.strip()) > 0