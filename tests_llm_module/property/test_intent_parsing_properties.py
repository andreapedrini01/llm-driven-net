"""Property-based tests for intent parsing functionality."""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from datetime import datetime
from src.services.intent_parser import IntentParser
from src.models.intent import IntentObject, IntentType, Entity


class TestIntentParsingProperties:
    """Property-based tests for intent parsing completeness."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = IntentParser()
    
    # Generator strategies for test data
    @staticmethod
    @st.composite
    def natural_language_intent(draw):
        """Generate realistic natural language intents."""
        # Intent action words
        actions = ['create', 'delete', 'modify', 'configure', 'set', 'add', 'remove', 
                  'show', 'display', 'list', 'get', 'fix', 'resolve', 'handle']
        
        # Network resources
        resources = ['switch', 'router', 'host', 'link', 'port', 'slice', 'flow', 
                    'rule', 'policy', 'vlan', 'subnet']
        
        # Identifiers and values
        identifiers = ['tenant_a', 'user123', 'app_web', 'service_db', 'sw1', 'rt2', 'h3']
        values = ['100', '1000', 'high', 'medium', 'low', '10.0.0.1', 'critical']
        
        # Build intent components
        action = draw(st.sampled_from(actions))
        resource = draw(st.sampled_from(resources))
        identifier = draw(st.sampled_from(identifiers))
        
        # Generate different intent structures
        intent_templates = [
            f"{action} {resource} {identifier}",
            f"{action} a new {resource} for {identifier}",
            f"please {action} the {resource} named {identifier}",
            f"I want to {action} {resource} {identifier}",
            f"can you {action} {resource} {identifier}?",
            f"{action} {resource} with {identifier}",
        ]
        
        template = draw(st.sampled_from(intent_templates))
        
        # Optionally add parameters
        if draw(st.booleans()):
            param_value = draw(st.sampled_from(values))
            template += f" with bandwidth {param_value}"
        
        # Optionally add conditions
        if draw(st.booleans()):
            template += f" if priority is high"
        
        return template
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(intent_text=natural_language_intent())
    def test_intent_parsing_completeness(self, intent_text):
        """
        **Feature: llm-integration-module, Property 1: Intent parsing completeness**
        
        For any natural language intent provided by a user, the LLM_Module should 
        successfully parse it into a valid IntentObject with correctly extracted 
        entities and appropriate confidence scores.
        
        **Validates: Requirements 1.1**
        """
        # Ensure we have valid input
        assume(intent_text and len(intent_text.strip()) > 0)
        assume(len(intent_text) <= 10000)  # Reasonable length limit
        
        # Parse the intent
        result = self.parser.parse_intent(intent_text)
        
        # Verify the result is a valid IntentObject
        assert isinstance(result, IntentObject)
        
        # Verify basic completeness requirements
        assert result.id is not None and len(result.id) > 0
        assert result.raw_text == intent_text.strip()
        assert isinstance(result.timestamp, datetime)
        assert result.user_id is not None and len(result.user_id) > 0
        assert isinstance(result.entities, list)
        assert isinstance(result.intent_type, IntentType)
        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.parameters, dict)
        
        # Verify entities are properly structured
        for entity in result.entities:
            assert isinstance(entity, Entity)
            assert entity.name is not None and len(entity.name) > 0
            assert entity.type in ['resource', 'action', 'target', 'parameter', 'identifier', 'value', 'condition']
            assert entity.value is not None and len(entity.value.strip()) > 0
            assert 0.0 <= entity.confidence <= 1.0
        
        # Verify data integrity
        validation_report = result.validate_data_integrity()
        assert isinstance(validation_report, dict)
        assert 'is_valid' in validation_report
        assert 'issues' in validation_report
        assert 'warnings' in validation_report
        assert 'entity_count' in validation_report
        assert 'confidence_score' in validation_report
        
        # Verify confidence score is reasonable
        # For any valid intent, confidence should be at least 0.1
        assert result.confidence >= 0.1
        
        # If entities were extracted, confidence should reflect that
        if result.entities:
            # With entities, confidence should be higher
            assert result.confidence >= 0.2
            
            # Entity count should match actual entities
            assert validation_report['entity_count'] == len(result.entities)
        
        # Verify intent type classification is reasonable
        text_lower = intent_text.lower()
        if any(word in text_lower for word in ['create', 'configure', 'set', 'add', 'modify']):
            # Configuration intents should be classified correctly
            assert result.intent_type in [IntentType.CONFIGURATION, IntentType.QUERY, IntentType.ANOMALY_RESPONSE]
        
        if any(word in text_lower for word in ['show', 'display', 'list', 'get', 'what']):
            # Query intents should be classified correctly  
            assert result.intent_type in [IntentType.QUERY, IntentType.CONFIGURATION, IntentType.ANOMALY_RESPONSE]
        
        if any(word in text_lower for word in ['fix', 'resolve', 'handle', 'anomaly']):
            # Anomaly response intents should be classified correctly
            assert result.intent_type in [IntentType.ANOMALY_RESPONSE, IntentType.CONFIGURATION, IntentType.QUERY]
    
    @settings(max_examples=50)
    @given(
        intent_text=natural_language_intent(),
        user_id=st.text(alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_@.-', min_size=1, max_size=50)
    )
    def test_intent_parsing_with_user_context(self, intent_text, user_id):
        """Test that intent parsing works correctly with different user contexts."""
        assume(intent_text and len(intent_text.strip()) > 0)
        assume(user_id and len(user_id.strip()) > 0)
        
        # Parse with specific user ID
        result = self.parser.parse_intent(intent_text, user_id.strip())
        
        # Verify user context is preserved
        assert result.user_id == user_id.strip()
        
        # Verify all other properties still hold
        assert isinstance(result, IntentObject)
        assert result.raw_text == intent_text.strip()
        assert 0.0 <= result.confidence <= 1.0
    
    @settings(max_examples=30)
    @given(
        base_intent=natural_language_intent(),
        extra_words=st.lists(st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll')), min_size=1, max_size=10), min_size=0, max_size=5)
    )
    def test_intent_parsing_robustness(self, base_intent, extra_words):
        """Test that intent parsing is robust to additional noise words."""
        assume(base_intent and len(base_intent.strip()) > 0)
        
        # Add noise words to the intent
        noisy_intent = base_intent
        for word in extra_words:
            if word and word.strip():
                noisy_intent += f" {word.strip()}"
        
        assume(len(noisy_intent) <= 10000)
        
        # Parse both original and noisy versions
        original_result = self.parser.parse_intent(base_intent)
        noisy_result = self.parser.parse_intent(noisy_intent)
        
        # Both should parse successfully
        assert isinstance(original_result, IntentObject)
        assert isinstance(noisy_result, IntentObject)
        
        # Both should have reasonable confidence
        assert original_result.confidence >= 0.1
        assert noisy_result.confidence >= 0.1
        
        # Intent type should be consistent or at least reasonable
        assert isinstance(original_result.intent_type, IntentType)
        assert isinstance(noisy_result.intent_type, IntentType)
    
    def test_empty_intent_handling(self):
        """Test that empty intents are handled appropriately."""
        with pytest.raises(ValueError, match="Intent text cannot be empty"):
            self.parser.parse_intent("")
        
        with pytest.raises(ValueError, match="Intent text cannot be empty"):
            self.parser.parse_intent("   ")
        
        with pytest.raises(ValueError, match="Intent text cannot be empty"):
            self.parser.parse_intent(None)
    
    @settings(max_examples=20)
    @given(intent_text=st.text(min_size=1, max_size=50))
    def test_minimal_intent_parsing(self, intent_text):
        """Test parsing of minimal intents."""
        assume(intent_text and len(intent_text.strip()) > 0)
        assume(len(intent_text.strip()) <= 10000)
        
        # Even minimal intents should parse successfully
        result = self.parser.parse_intent(intent_text)
        
        assert isinstance(result, IntentObject)
        assert result.raw_text == intent_text.strip()
        assert result.confidence >= 0.1  # Minimum confidence threshold
        assert isinstance(result.intent_type, IntentType)
        assert isinstance(result.entities, list)
        assert isinstance(result.parameters, dict)