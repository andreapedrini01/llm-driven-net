"""Intent Parser service for processing natural language intents."""

import re
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from src.models.intent import IntentObject, IntentType, Entity


class IntentParser:
    """Service for parsing natural language intents into structured objects."""
    
    def __init__(self):
        """Initialize the intent parser with basic NLP patterns."""
        # Basic patterns for entity extraction
        self.entity_patterns = {
            'resource': [
                r'\b(?:switch|router|host|link|port|interface)\s*[a-zA-Z0-9_-]*\b',
                r'\b(?:sw|rt|h)\d+\b',
                r'\b(?:eth|port)\d+\b'
            ],
            'action': [
                r'\b(?:create|delete|modify|update|configure|set|add|remove|block|allow)\b',
                r'\b(?:enable|disable|start|stop|restart)\b'
            ],
            'target': [
                r'\b(?:slice|flow|rule|policy|vlan|subnet)\s*[a-zA-Z0-9_-]*\b',
                r'\b(?:tenant|user|application)\s*[a-zA-Z0-9_-]*\b'
            ],
            'parameter': [
                r'\b(?:bandwidth|latency|priority|timeout|vlan_id)\b',
                r'\b\d+\s*(?:mbps|gbps|ms|sec|min)\b'
            ],
            'identifier': [
                r'\b(?:tenant|user|app|service)\s*[a-zA-Z0-9_-]+\b',
                r'\b[a-zA-Z0-9_-]+@[a-zA-Z0-9.-]+\b'
            ],
            'value': [
                r'\b\d+(?:\.\d+)?\b',
                r'\b(?:high|medium|low|critical|normal)\b'
            ],
            'condition': [
                r'\b(?:if|when|while|unless|until)\b.*',
                r'\b(?:greater|less|equal)\s*(?:than|to)\b'
            ]
        }
        
        # Intent type classification patterns
        self.intent_type_patterns = {
            IntentType.CONFIGURATION: [
                r'\b(?:create|configure|set|add|modify|update|delete|remove)\b',
                r'\b(?:slice|flow|rule|policy)\b'
            ],
            IntentType.QUERY: [
                r'\b(?:show|display|list|get|what|how|status|info)\b',
                r'\b(?:is|are|can|will|does)\b.*\?'
            ],
            IntentType.ANOMALY_RESPONSE: [
                r'\b(?:fix|resolve|handle|mitigate|respond)\b',
                r'\b(?:anomaly|error|problem|issue|alert)\b'
            ]
        }
    
    def parse_intent(self, text: str, user_id: str = "default_user") -> IntentObject:
        """
        Parse natural language text into a structured IntentObject.
        
        Args:
            text: Natural language intent text
            user_id: ID of the user submitting the intent
            
        Returns:
            IntentObject with extracted entities and metadata
        """
        if not text or not text.strip():
            raise ValueError("Intent text cannot be empty")
        
        text = text.strip()
        
        # Generate unique ID
        intent_id = f"intent_{uuid.uuid4().hex[:8]}"
        
        # Extract entities
        entities = self._extract_entities(text)
        
        # Classify intent type
        intent_type = self._classify_intent_type(text)
        
        # Calculate confidence score
        confidence = self._calculate_confidence(text, entities, intent_type)
        
        # Extract parameters
        parameters = self._extract_parameters(text, entities)
        
        return IntentObject(
            id=intent_id,
            raw_text=text,
            timestamp=datetime.now(),
            user_id=user_id,
            entities=entities,
            intent_type=intent_type,
            confidence=confidence,
            parameters=parameters
        )
    
    def _extract_entities(self, text: str) -> List[Entity]:
        """Extract entities from the text using pattern matching."""
        entities = []
        text_lower = text.lower()
        
        for entity_type, patterns in self.entity_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text_lower, re.IGNORECASE)
                for match in matches:
                    entity_text = match.group().strip()
                    if entity_text and len(entity_text) > 1:
                        # Generate entity name
                        entity_name = f"{entity_type}_{len(entities) + 1}"
                        
                        # Calculate confidence based on pattern specificity
                        confidence = self._calculate_entity_confidence(entity_text, entity_type)
                        
                        entity = Entity(
                            name=entity_name,
                            type=entity_type,
                            value=entity_text,
                            confidence=confidence
                        )
                        entities.append(entity)
        
        # Remove duplicates based on value
        unique_entities = []
        seen_values = set()
        for entity in entities:
            if entity.value not in seen_values:
                unique_entities.append(entity)
                seen_values.add(entity.value)
        
        return unique_entities
    
    def _classify_intent_type(self, text: str) -> IntentType:
        """Classify the intent type based on text patterns."""
        text_lower = text.lower()
        
        # Score each intent type
        type_scores = {}
        for intent_type, patterns in self.intent_type_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower, re.IGNORECASE))
                score += matches
            type_scores[intent_type] = score
        
        # Return the type with highest score, default to CONFIGURATION
        if not type_scores or max(type_scores.values()) == 0:
            return IntentType.CONFIGURATION
        
        return max(type_scores, key=type_scores.get)
    
    def _calculate_confidence(self, text: str, entities: List[Entity], intent_type: IntentType) -> float:
        """Calculate overall confidence score for the parsed intent."""
        if not text:
            return 0.0
        
        # Base confidence from text length and structure
        base_confidence = min(0.5 + len(text.split()) * 0.02, 0.8)
        
        # Boost from entities
        entity_boost = min(len(entities) * 0.05, 0.15)
        
        # Boost from clear intent type indicators
        type_boost = 0.05 if self._has_clear_intent_indicators(text, intent_type) else 0.0
        
        # Penalty for very short or very long texts
        length_penalty = 0.0
        if len(text) < 10:
            length_penalty = 0.1
        elif len(text) > 500:
            length_penalty = 0.05
        
        confidence = base_confidence + entity_boost + type_boost - length_penalty
        return max(0.1, min(1.0, confidence))
    
    def _calculate_entity_confidence(self, entity_text: str, entity_type: str) -> float:
        """Calculate confidence score for a specific entity."""
        # Base confidence
        confidence = 0.7
        
        # Boost for specific patterns
        if entity_type == 'resource' and re.match(r'\b(?:sw|rt|h)\d+\b', entity_text):
            confidence += 0.2
        elif entity_type == 'parameter' and re.match(r'\b\d+\s*(?:mbps|gbps|ms)\b', entity_text):
            confidence += 0.2
        elif entity_type == 'identifier' and '@' in entity_text:
            confidence += 0.15
        
        # Penalty for very short entities
        if len(entity_text) < 3:
            confidence -= 0.1
        
        return max(0.1, min(1.0, confidence))
    
    def _has_clear_intent_indicators(self, text: str, intent_type: IntentType) -> bool:
        """Check if text has clear indicators for the classified intent type."""
        text_lower = text.lower()
        patterns = self.intent_type_patterns.get(intent_type, [])
        
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        return False
    
    def _extract_parameters(self, text: str, entities: List[Entity]) -> Dict[str, Any]:
        """Extract parameters from text and entities."""
        parameters = {}
        
        # Extract numeric parameters
        numeric_matches = re.finditer(r'(\w+)\s*[:=]\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        for match in numeric_matches:
            param_name = match.group(1).lower()
            param_value = float(match.group(2)) if '.' in match.group(2) else int(match.group(2))
            parameters[param_name] = param_value
        
        # Extract string parameters
        string_matches = re.finditer(r'(\w+)\s*[:=]\s*["\']([^"\']+)["\']', text, re.IGNORECASE)
        for match in string_matches:
            param_name = match.group(1).lower()
            param_value = match.group(2)
            parameters[param_name] = param_value
        
        # Add entity values as parameters
        for entity in entities:
            if entity.type in ['parameter', 'value', 'identifier']:
                param_key = f"{entity.type}_{entity.name.split('_')[-1]}"
                parameters[param_key] = entity.value
        
        return parameters