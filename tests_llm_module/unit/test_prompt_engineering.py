"""Tests for prompt engineering system."""

import json
import pytest
from datetime import datetime

from src.services.prompt_engineering import (
    PromptEngineeringSystem,
    PromptType,
    PromptTemplate,
    ParsedResponse
)
from src.models.intent import IntentObject, IntentType, Entity, ContextualizedIntent
from src.models.network import (
    NetworkState,
    Topology,
    Switch,
    Link,
    Host,
    Flow,
    NetworkMetrics,
    BandwidthMetrics,
    LatencyMetrics,
    UtilizationMetrics,
    Anomaly,
    AnomalyType,
    AnomalySeverity
)
from src.models.actions import ActionSequence, NetworkAction, ActionType


@pytest.fixture
def prompt_system():
    """Create a prompt engineering system instance."""
    return PromptEngineeringSystem()


@pytest.fixture
def sample_intent():
    """Create a sample intent object."""
    return IntentObject(
        id="intent-001",
        raw_text="Create a high-priority flow from switch-1 to switch-2",
        timestamp=datetime.now(),
        user_id="admin",
        entities=[
            Entity(name="action", type="action", value="create", confidence=0.9),
            Entity(name="source", type="resource", value="switch-1", confidence=0.95),
            Entity(name="destination", type="resource", value="switch-2", confidence=0.95)
        ],
        intent_type=IntentType.CONFIGURATION,
        confidence=0.9,
        parameters={"priority": "high"}
    )


@pytest.fixture
def sample_network_state():
    """Create a sample network state."""
    return NetworkState(
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
                )
            ]
        ),
        flows=[
            Flow(
                id="flow-1",
                switch_id="switch-1",
                match_fields={"in_port": 2},
                actions=[{"output": 1}],
                priority=1000
            )
        ],
        metrics=NetworkMetrics(
            bandwidth=BandwidthMetrics(
                total_capacity=1000,
                used_bandwidth=300,
                available_bandwidth=700,
                utilization_percentage=30.0
            ),
            latency=LatencyMetrics(
                average_latency=2.5,
                min_latency=1.0,
                max_latency=5.0,
                jitter=0.5
            ),
            utilization=UtilizationMetrics(
                cpu_utilization=45.0,
                memory_utilization=60.0,
                port_utilization={"switch-1:1": 30.0}
            )
        ),
        anomalies=[]
    )


@pytest.fixture
def sample_anomaly():
    """Create a sample anomaly."""
    return Anomaly(
        id="anomaly-001",
        type=AnomalyType.TRAFFIC_SPIKE,
        severity=AnomalySeverity.HIGH,
        description="Unusual traffic spike detected on switch-1",
        affected_resources=["switch-1", "link-1"],
        detected_at=datetime.now(),
        metrics={"traffic_increase": "300%", "duration": "5 minutes"}
    )


@pytest.fixture
def sample_action_sequence(sample_intent):
    """Create a sample action sequence."""
    return ActionSequence(
        id="seq-001",
        intent_id=sample_intent.id,
        actions=[
            NetworkAction(
                id="action-001",
                type=ActionType.FLOW_MOD,
                target="switch-1",
                parameters={
                    "match": {"in_port": 2},
                    "actions": [{"output": 1}]
                },
                priority=2000,
                timeout=30
            )
        ],
        estimated_duration=5,
        dependencies=[],
        rollback_plan=[]
    )


class TestPromptEngineeringSystem:
    """Test suite for PromptEngineeringSystem."""
    
    def test_initialization(self, prompt_system):
        """Test system initialization."""
        assert prompt_system is not None
        # Verify all template types are initialized
        for prompt_type in PromptType:
            template = prompt_system.get_template(prompt_type)
            assert template is not None
            assert template.system_message
            assert template.user_template
            assert template.response_schema
    
    def test_get_template_valid(self, prompt_system):
        """Test getting a valid template."""
        template = prompt_system.get_template(PromptType.INTENT_PARSING)
        assert isinstance(template, PromptTemplate)
        assert template.type == PromptType.INTENT_PARSING
        assert "network" in template.system_message.lower()
    
    def test_get_template_invalid(self, prompt_system):
        """Test getting an invalid template raises error."""
        with pytest.raises(ValueError, match="Unknown prompt type"):
            prompt_system.get_template("invalid_type")
    
    def test_build_intent_parsing_prompt(self, prompt_system):
        """Test building intent parsing prompt."""
        intent_text = "Create a flow from host-1 to host-2"
        
        system_msg, user_prompt, config = prompt_system.build_intent_parsing_prompt(intent_text)
        
        assert system_msg
        assert "network" in system_msg.lower()
        assert intent_text in user_prompt
        assert "JSON" in user_prompt
        assert config["max_tokens"] > 0
        assert 0 <= config["temperature"] <= 1
    
    def test_build_action_generation_prompt(
        self,
        prompt_system,
        sample_intent,
        sample_network_state
    ):
        """Test building action generation prompt."""
        contextualized_intent = ContextualizedIntent(
            intent=sample_intent,
            relevant_resources=["switch-1", "switch-2"],
            network_context={"topology": "simple"},
            conflicts=[],
            recommendations=[]
        )
        
        system_msg, user_prompt, config = prompt_system.build_action_generation_prompt(
            contextualized_intent,
            sample_network_state
        )
        
        assert system_msg
        assert sample_intent.raw_text in user_prompt
        assert "switch-1" in user_prompt
        assert "switch-2" in user_prompt
        assert str(len(sample_network_state.topology.switches)) in user_prompt
        assert config["max_tokens"] > 0
    
    def test_build_anomaly_analysis_prompt(
        self,
        prompt_system,
        sample_anomaly,
        sample_network_state
    ):
        """Test building anomaly analysis prompt."""
        system_msg, user_prompt, config = prompt_system.build_anomaly_analysis_prompt(
            sample_anomaly,
            sample_network_state
        )
        
        assert system_msg
        assert sample_anomaly.type.value in user_prompt
        assert sample_anomaly.severity.value in user_prompt
        assert sample_anomaly.description in user_prompt
        assert config["max_tokens"] > 0
    
    def test_build_clarification_prompt(
        self,
        prompt_system,
        sample_network_state
    ):
        """Test building clarification prompt."""
        intent_text = "Configure the network"
        ambiguities = ["Which network component?", "What configuration?"]
        
        system_msg, user_prompt, config = prompt_system.build_clarification_prompt(
            intent_text,
            ambiguities,
            sample_network_state
        )
        
        assert system_msg
        assert intent_text in user_prompt
        assert ambiguities[0] in user_prompt
        assert ambiguities[1] in user_prompt
        assert config["max_tokens"] > 0
    
    def test_build_validation_prompt(
        self,
        prompt_system,
        sample_action_sequence,
        sample_network_state
    ):
        """Test building validation prompt."""
        system_msg, user_prompt, config = prompt_system.build_validation_prompt(
            sample_action_sequence,
            sample_network_state
        )
        
        assert system_msg
        assert "action-001" in user_prompt
        assert "switch-1" in user_prompt
        assert config["max_tokens"] > 0
    
    def test_build_slice_orchestration_prompt(
        self,
        prompt_system,
        sample_network_state
    ):
        """Test building slice orchestration prompt."""
        intent_text = "Create a network slice for IoT devices"
        slice_requirements = {
            "bandwidth": 100,
            "latency": 10,
            "isolation": "high"
        }
        
        system_msg, user_prompt, config = prompt_system.build_slice_orchestration_prompt(
            intent_text,
            slice_requirements,
            sample_network_state
        )
        
        assert system_msg
        assert intent_text in user_prompt
        assert "100" in user_prompt  # bandwidth requirement
        assert config["max_tokens"] > 0
    
    def test_parse_response_valid_json(self, prompt_system):
        """Test parsing valid JSON response."""
        raw_response = json.dumps({
            "intent_type": "configuration",
            "entities": [
                {"name": "action", "type": "action", "value": "create", "confidence": 0.9}
            ],
            "parameters": {},
            "confidence": 0.85,
            "ambiguities": []
        })
        
        schema = {
            "intent_type": "string",
            "entities": [],
            "parameters": {},
            "confidence": "float",
            "ambiguities": []
        }
        
        result = prompt_system.parse_response(
            raw_response,
            schema,
            PromptType.INTENT_PARSING
        )
        
        assert result.is_valid
        assert result.parsed_data["intent_type"] == "configuration"
        assert result.confidence == 0.85
        assert len(result.validation_errors) == 0
    
    def test_parse_response_with_markdown(self, prompt_system):
        """Test parsing JSON wrapped in markdown."""
        raw_response = """```json
{
    "intent_type": "configuration",
    "confidence": 0.9
}
```"""
        
        schema = {"intent_type": "string", "confidence": "float"}
        
        result = prompt_system.parse_response(
            raw_response,
            schema,
            PromptType.INTENT_PARSING
        )
        
        assert result.is_valid
        assert result.parsed_data["intent_type"] == "configuration"
    
    def test_parse_response_invalid_json(self, prompt_system):
        """Test parsing invalid JSON."""
        raw_response = "This is not JSON"
        schema = {"intent_type": "string"}
        
        result = prompt_system.parse_response(
            raw_response,
            schema,
            PromptType.INTENT_PARSING
        )
        
        assert not result.is_valid
        assert len(result.validation_errors) > 0
        assert "JSON" in result.validation_errors[0]
    
    def test_parse_response_missing_fields(self, prompt_system):
        """Test parsing response with missing required fields."""
        raw_response = json.dumps({
            "intent_type": "configuration"
            # Missing other required fields
        })
        
        schema = {
            "intent_type": "string",
            "entities": [],
            "confidence": "float"
        }
        
        result = prompt_system.parse_response(
            raw_response,
            schema,
            PromptType.INTENT_PARSING
        )
        
        assert not result.is_valid
        assert any("Missing required field" in err for err in result.validation_errors)
    
    def test_parse_response_wrong_types(self, prompt_system):
        """Test parsing response with wrong field types."""
        raw_response = json.dumps({
            "intent_type": 123,  # Should be string
            "confidence": "high"  # Should be float
        })
        
        schema = {
            "intent_type": "string",
            "confidence": "float"
        }
        
        result = prompt_system.parse_response(
            raw_response,
            schema,
            PromptType.INTENT_PARSING
        )
        
        assert not result.is_valid
        assert len(result.validation_errors) > 0
    
    def test_optimize_prompt_for_tokens_no_reduction(self, prompt_system):
        """Test prompt optimization when no reduction needed."""
        short_prompt = "This is a short prompt"
        optimized = prompt_system.optimize_prompt_for_tokens(short_prompt, max_tokens=1000)
        
        assert optimized == short_prompt
    
    def test_optimize_prompt_for_tokens_with_reduction(self, prompt_system):
        """Test prompt optimization with reduction."""
        long_prompt = "A" * 20000  # Very long prompt
        optimized = prompt_system.optimize_prompt_for_tokens(long_prompt, max_tokens=1000)
        
        assert len(optimized) < len(long_prompt)
        assert "truncated" in optimized.lower()
    
    def test_extract_json_plain(self, prompt_system):
        """Test extracting plain JSON."""
        text = '{"key": "value"}'
        result = prompt_system._extract_json(text)
        assert result == text
    
    def test_extract_json_with_markdown(self, prompt_system):
        """Test extracting JSON from markdown code block."""
        text = '```json\n{"key": "value"}\n```'
        result = prompt_system._extract_json(text)
        assert result == '{"key": "value"}'
    
    def test_extract_json_with_text_around(self, prompt_system):
        """Test extracting JSON with surrounding text."""
        text = 'Here is the result: {"key": "value"} and some more text'
        result = prompt_system._extract_json(text)
        assert '{"key": "value"}' in result
    
    def test_format_network_state(self, prompt_system, sample_network_state):
        """Test formatting network state."""
        formatted = prompt_system._format_network_state(sample_network_state)
        
        assert "switch-1" in formatted.lower()
        assert "switch-2" in formatted.lower()
        assert "30.0%" in formatted  # Bandwidth utilization
        assert "2.5" in formatted  # Latency
    
    def test_format_network_state_with_anomalies(
        self,
        prompt_system,
        sample_network_state,
        sample_anomaly
    ):
        """Test formatting network state with anomalies."""
        sample_network_state.anomalies = [sample_anomaly]
        formatted = prompt_system._format_network_state(sample_network_state)
        
        assert "anomal" in formatted.lower()
        assert sample_anomaly.type.value in formatted
    
    def test_format_available_resources(self, prompt_system, sample_network_state):
        """Test formatting available resources."""
        formatted = prompt_system._format_available_resources(sample_network_state)
        
        assert "switch-1" in formatted
        assert "switch-2" in formatted
        assert "host-1" in formatted
        assert "192.168.1.10" in formatted
    
    def test_estimate_confidence_complete(self, prompt_system):
        """Test confidence estimation with complete data."""
        data = {
            "field1": "value1",
            "field2": "value2",
            "field3": "value3"
        }
        schema = {
            "field1": "string",
            "field2": "string",
            "field3": "string"
        }
        
        confidence = prompt_system._estimate_confidence(data, schema)
        assert confidence > 0.9
    
    def test_estimate_confidence_incomplete(self, prompt_system):
        """Test confidence estimation with incomplete data."""
        data = {
            "field1": "value1"
        }
        schema = {
            "field1": "string",
            "field2": "string",
            "field3": "string"
        }
        
        confidence = prompt_system._estimate_confidence(data, schema)
        assert confidence < 0.5
    
    def test_estimate_confidence_empty_values(self, prompt_system):
        """Test confidence estimation with empty values."""
        data = {
            "field1": "",
            "field2": None,
            "field3": []
        }
        schema = {
            "field1": "string",
            "field2": "string",
            "field3": "list"
        }
        
        confidence = prompt_system._estimate_confidence(data, schema)
        assert confidence < 0.8


class TestPromptTemplates:
    """Test suite for prompt templates."""
    
    def test_template_format_valid(self):
        """Test template formatting with valid parameters."""
        template = PromptTemplate(
            type=PromptType.INTENT_PARSING,
            system_message="System message",
            user_template="Hello {name}, your age is {age}",
            response_schema={}
        )
        
        result = template.format(name="Alice", age=30)
        assert result == "Hello Alice, your age is 30"
    
    def test_template_format_missing_param(self):
        """Test template formatting with missing parameter."""
        template = PromptTemplate(
            type=PromptType.INTENT_PARSING,
            system_message="System message",
            user_template="Hello {name}",
            response_schema={}
        )
        
        with pytest.raises(ValueError, match="Missing required template parameter"):
            template.format()
    
    def test_all_templates_have_required_fields(self, prompt_system):
        """Test that all templates have required fields."""
        for prompt_type in PromptType:
            template = prompt_system.get_template(prompt_type)
            
            assert template.system_message
            assert template.user_template
            assert template.response_schema
            assert template.max_tokens > 0
            assert 0 <= template.temperature <= 1
            
            # Check that system message is relevant
            assert len(template.system_message) > 20
            assert any(word in template.system_message.lower() 
                      for word in ["network", "sdn", "expert"])


class TestResponseParsing:
    """Test suite for response parsing."""
    
    def test_parsed_response_creation(self):
        """Test creating a ParsedResponse."""
        response = ParsedResponse(
            raw_content='{"key": "value"}',
            parsed_data={"key": "value"},
            is_valid=True,
            validation_errors=[],
            confidence=0.95
        )
        
        assert response.is_valid
        assert response.confidence == 0.95
        assert len(response.validation_errors) == 0
    
    def test_parsed_response_with_errors(self):
        """Test ParsedResponse with validation errors."""
        response = ParsedResponse(
            raw_content="invalid",
            parsed_data={},
            is_valid=False,
            validation_errors=["Error 1", "Error 2"],
            confidence=0.0
        )
        
        assert not response.is_valid
        assert len(response.validation_errors) == 2
        assert response.confidence == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
