"""Intent Parser service for processing natural language intents."""

import re
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set
from src.models.intent import IntentObject, IntentType, Entity, ContextualizedIntent
from src.models.network import NetworkState


class IntentParser:
    """Service for parsing natural language intents into structured objects."""
    
    def __init__(self):
        """Initialize the intent parser with enhanced NLP patterns and preprocessing."""
        # Stopwords for filtering (common words that don't add meaning)
        self.stopwords = {
            'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should',
            'could', 'may', 'might', 'must', 'can', 'to', 'of', 'in', 'on', 'at',
            'by', 'for', 'with', 'from', 'as', 'into', 'through', 'during', 'before',
            'after', 'above', 'below', 'between', 'under', 'again', 'further', 'then',
            'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'both',
            'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor',
            'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just'
        }
        
        # Enhanced patterns for entity extraction
        self.entity_patterns = {
            'resource': [
                r'\b(?:sw|rt|h|link)\d+\b',  # Match sw1, rt1, h1, link1 etc.
                r'\b(?:switch|router|host|link|port|interface)[-_]?[a-zA-Z0-9_-]*\b',
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
        
        # Enhanced intent type classification patterns with weights
        self.intent_type_patterns = {
            IntentType.CONFIGURATION: {
                'primary': [
                    r'\b(?:create|configure|set|add|modify|update|delete|remove|establish|deploy|install)\b',
                    r'\b(?:slice|flow|rule|policy|vlan|subnet|route|firewall)\b'
                ],
                'secondary': [
                    r'\b(?:new|change|adjust|setup|build|make)\b',
                    r'\b(?:network|connection|bandwidth|priority)\b'
                ],
                'weight': 1.0
            },
            IntentType.QUERY: {
                'primary': [
                    r'\b(?:show|display|list|get|what|how|status|info|check|view|see)\b',
                    r'\b(?:is|are|can|will|does|tell|explain)\b.*\?'
                ],
                'secondary': [
                    r'\b(?:current|existing|available|active)\b',
                    r'\?$'  # Ends with question mark
                ],
                'weight': 1.0
            },
            IntentType.ANOMALY_RESPONSE: {
                'primary': [
                    r'\b(?:fix|resolve|handle|mitigate|respond|repair|troubleshoot)\b',
                    r'\b(?:anomaly|error|problem|issue|alert|failure|outage|down)\b'
                ],
                'secondary': [
                    r'\b(?:urgent|critical|emergency|broken|failed)\b',
                    r'\b(?:restore|recover|diagnose|investigate)\b'
                ],
                'weight': 1.2  # Higher weight for anomaly responses
            }
        }
        
        # Tokenization patterns
        self.token_patterns = {
            'word': r'\b[a-zA-Z][a-zA-Z0-9_-]*\b',
            'number': r'\b\d+(?:\.\d+)?\b',
            'identifier': r'\b[a-zA-Z0-9_-]+@[a-zA-Z0-9.-]+\b|\b[a-zA-Z][a-zA-Z0-9_-]*\d+\b',
            'ip_address': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
            'mac_address': r'\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b',
            'unit': r'\b\d+\s*(?:mbps|gbps|kbps|ms|sec|min|hour|kb|mb|gb|tb)\b'
        }
    
    def tokenize(self, text: str) -> List[Dict[str, Any]]:
        """
        Enhanced tokenization with type classification.
        
        Args:
            text: Input text to tokenize
            
        Returns:
            List of token dictionaries with type and position information
        """
        tokens = []
        text_lower = text.lower()
        
        # Find all token types
        for token_type, pattern in self.token_patterns.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                token = {
                    'text': match.group(),
                    'type': token_type,
                    'start': match.start(),
                    'end': match.end(),
                    'is_stopword': match.group().lower() in self.stopwords
                }
                tokens.append(token)
        
        # Sort by position and remove overlaps (prefer longer matches)
        tokens.sort(key=lambda x: (x['start'], -(x['end'] - x['start'])))
        
        # Remove overlapping tokens
        filtered_tokens = []
        last_end = -1
        for token in tokens:
            if token['start'] >= last_end:
                filtered_tokens.append(token)
                last_end = token['end']
        
        return filtered_tokens
    
    def preprocess_text(self, text: str) -> str:
        """
        Preprocess text for better parsing.
        
        Args:
            text: Raw input text
            
        Returns:
            Preprocessed text
        """
        if not text:
            return ""
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Expand common contractions
        contractions = {
            "can't": "cannot",
            "won't": "will not",
            "n't": " not",
            "'re": " are",
            "'ve": " have",
            "'ll": " will",
            "'d": " would",
            "'m": " am"
        }
        
        for contraction, expansion in contractions.items():
            text = re.sub(contraction, expansion, text, flags=re.IGNORECASE)
        
        # Normalize punctuation spacing
        text = re.sub(r'\s*([.!?])\s*', r' \1 ', text)
        text = re.sub(r'\s*([,;:])\s*', r'\1 ', text)
        
        # Remove extra whitespace again
        text = re.sub(r'\s+', ' ', text.strip())
        
        return text
    
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
        
        # Store original text and preprocess
        original_text = text.strip()
        preprocessed_text = self.preprocess_text(original_text)
        
        # Generate unique ID
        intent_id = f"intent_{uuid.uuid4().hex[:8]}"
        
        # Tokenize for enhanced processing
        tokens = self.tokenize(preprocessed_text)
        
        # Extract entities using both original and preprocessed text
        entities = self._extract_entities(preprocessed_text, tokens)
        
        # Classify intent type with enhanced scoring
        intent_type, type_confidence = self._classify_intent_type_enhanced(preprocessed_text, tokens)
        
        # Calculate confidence score with multiple factors
        confidence = self._calculate_confidence_enhanced(
            original_text, preprocessed_text, entities, intent_type, type_confidence, tokens
        )
        
        # Extract parameters with token awareness
        parameters = self._extract_parameters_enhanced(preprocessed_text, entities, tokens)
        
        return IntentObject(
            id=intent_id,
            raw_text=original_text,
            timestamp=datetime.now(),
            user_id=user_id,
            entities=entities,
            intent_type=intent_type,
            confidence=confidence,
            parameters=parameters
        )
    
    def _extract_entities(self, text: str, tokens: List[Dict[str, Any]]) -> List[Entity]:
        """Extract entities from the text using enhanced pattern matching and token analysis."""
        entities = []
        text_lower = text.lower()
        
        # Extract entities using pattern matching
        for entity_type, patterns in self.entity_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text_lower, re.IGNORECASE)
                for match in matches:
                    entity_text = match.group().strip()
                    if entity_text and len(entity_text) > 1:
                        # For compound phrases like "switch sw1", extract just the identifier
                        if entity_type == 'resource' and ' ' in entity_text:
                            # Look for the actual resource identifier
                            parts = entity_text.split()
                            for part in parts:
                                if re.match(r'^(?:sw|rt|h|link)\d+$', part):
                                    entity_text = part
                                    break
                        
                        # Generate entity name
                        entity_name = f"{entity_type}_{len(entities) + 1}"
                        
                        # Calculate confidence based on pattern specificity and context
                        confidence = self._calculate_entity_confidence_enhanced(
                            entity_text, entity_type, match.start(), match.end(), tokens
                        )
                        
                        entity = Entity(
                            name=entity_name,
                            type=entity_type,
                            value=entity_text,
                            confidence=confidence
                        )
                        entities.append(entity)
        
        # Extract entities from special token types
        for token in tokens:
            if token['type'] in ['identifier', 'ip_address', 'mac_address', 'unit'] and not token['is_stopword']:
                # Check if this token is already covered by pattern matching
                token_text = token['text']
                if not any(entity.value.lower() == token_text.lower() for entity in entities):
                    entity_type = self._map_token_type_to_entity_type(token['type'])
                    entity_name = f"{entity_type}_{len(entities) + 1}"
                    
                    confidence = self._calculate_token_entity_confidence(token)
                    
                    entity = Entity(
                        name=entity_name,
                        type=entity_type,
                        value=token_text,
                        confidence=confidence
                    )
                    entities.append(entity)
        
        # Remove duplicates based on value and merge similar entities
        unique_entities = self._deduplicate_entities(entities)
        
        return unique_entities
    
    def _map_token_type_to_entity_type(self, token_type: str) -> str:
        """Map token types to entity types."""
        mapping = {
            'identifier': 'identifier',
            'ip_address': 'parameter',
            'mac_address': 'parameter',
            'unit': 'parameter',
            'number': 'value'
        }
        return mapping.get(token_type, 'value')
    
    def _calculate_token_entity_confidence(self, token: Dict[str, Any]) -> float:
        """Calculate confidence for entities extracted from tokens."""
        base_confidence = 0.8
        
        # Boost for specific token types
        if token['type'] == 'ip_address':
            base_confidence += 0.15
        elif token['type'] == 'mac_address':
            base_confidence += 0.15
        elif token['type'] == 'identifier':
            base_confidence += 0.1
        elif token['type'] == 'unit':
            base_confidence += 0.1
        
        # Penalty for very short tokens
        if len(token['text']) < 3:
            base_confidence -= 0.1
        
        return max(0.1, min(1.0, base_confidence))
    
    def _deduplicate_entities(self, entities: List[Entity]) -> List[Entity]:
        """Remove duplicate entities and merge similar ones."""
        unique_entities = []
        seen_values = set()
        
        for entity in entities:
            entity_value_lower = entity.value.lower()
            
            # Check for exact duplicates
            if entity_value_lower not in seen_values:
                unique_entities.append(entity)
                seen_values.add(entity_value_lower)
            else:
                # Find existing entity and potentially merge
                for existing_entity in unique_entities:
                    if existing_entity.value.lower() == entity_value_lower:
                        # Keep the entity with higher confidence
                        if entity.confidence > existing_entity.confidence:
                            existing_entity.confidence = entity.confidence
                            existing_entity.type = entity.type
                        break
        
        return unique_entities
    
    def _classify_intent_type_enhanced(self, text: str, tokens: List[Dict[str, Any]]) -> Tuple[IntentType, float]:
        """Classify the intent type using enhanced scoring with confidence."""
        text_lower = text.lower()
        
        # Score each intent type with weighted patterns
        type_scores = {}
        for intent_type, pattern_config in self.intent_type_patterns.items():
            score = 0.0
            
            # Primary patterns (higher weight)
            for pattern in pattern_config['primary']:
                matches = len(re.findall(pattern, text_lower, re.IGNORECASE))
                score += matches * 2.0
            
            # Secondary patterns (lower weight)
            for pattern in pattern_config['secondary']:
                matches = len(re.findall(pattern, text_lower, re.IGNORECASE))
                score += matches * 1.0
            
            # Apply intent type weight
            score *= pattern_config['weight']
            
            # Boost based on token analysis
            score += self._calculate_token_intent_boost(tokens, intent_type)
            
            type_scores[intent_type] = score
        
        # Find the best match
        if not type_scores or max(type_scores.values()) == 0:
            return IntentType.CONFIGURATION, 0.5  # Default with medium confidence
        
        best_type = max(type_scores, key=type_scores.get)
        best_score = type_scores[best_type]
        
        # Calculate confidence based on score distribution
        total_score = sum(type_scores.values())
        if total_score > 0:
            confidence = min(0.95, best_score / total_score)
        else:
            confidence = 0.5
        
        # Boost confidence if score is significantly higher than others
        other_scores = [score for t, score in type_scores.items() if t != best_type]
        if other_scores and best_score > max(other_scores) * 2:
            confidence = min(0.95, confidence + 0.1)
        
        return best_type, max(0.1, confidence)
    
    def _calculate_token_intent_boost(self, tokens: List[Dict[str, Any]], intent_type: IntentType) -> float:
        """Calculate intent type boost based on token analysis."""
        boost = 0.0
        
        # Count relevant tokens for each intent type
        if intent_type == IntentType.CONFIGURATION:
            config_tokens = ['create', 'configure', 'set', 'add', 'modify', 'update', 'delete', 'remove']
            boost += sum(0.1 for token in tokens if token['text'].lower() in config_tokens)
        
        elif intent_type == IntentType.QUERY:
            query_tokens = ['show', 'display', 'list', 'get', 'what', 'how', 'status', 'info']
            boost += sum(0.1 for token in tokens if token['text'].lower() in query_tokens)
            # Extra boost for question marks
            boost += sum(0.2 for token in tokens if '?' in token['text'])
        
        elif intent_type == IntentType.ANOMALY_RESPONSE:
            anomaly_tokens = ['fix', 'resolve', 'handle', 'mitigate', 'error', 'problem', 'issue', 'alert']
            boost += sum(0.15 for token in tokens if token['text'].lower() in anomaly_tokens)
        
        return boost
    
    def _calculate_confidence_enhanced(self, original_text: str, preprocessed_text: str, 
                                     entities: List[Entity], intent_type: IntentType, 
                                     type_confidence: float, tokens: List[Dict[str, Any]]) -> float:
        """Calculate enhanced confidence score considering multiple factors."""
        if not original_text:
            return 0.0
        
        # Base confidence from text structure and length
        word_count = len(preprocessed_text.split())
        base_confidence = min(0.4 + word_count * 0.02, 0.7)
        
        # Entity confidence contribution
        if entities:
            avg_entity_confidence = sum(e.confidence for e in entities) / len(entities)
            entity_boost = min(len(entities) * 0.03 + avg_entity_confidence * 0.1, 0.2)
        else:
            entity_boost = 0.0
        
        # Intent type confidence contribution
        type_boost = type_confidence * 0.15
        
        # Token quality boost
        meaningful_tokens = [t for t in tokens if not t['is_stopword'] and t['type'] != 'word']
        token_boost = min(len(meaningful_tokens) * 0.02, 0.1)
        
        # Text quality factors
        quality_boost = 0.0
        
        # Boost for proper sentence structure
        if re.search(r'^[A-Z].*[.!?]$', original_text.strip()):
            quality_boost += 0.05
        
        # Boost for technical terms
        tech_terms = ['network', 'switch', 'router', 'flow', 'slice', 'vlan', 'bandwidth', 'latency']
        tech_count = sum(1 for term in tech_terms if term in preprocessed_text.lower())
        quality_boost += min(tech_count * 0.02, 0.08)
        
        # Boost for short but precise commands (action + resource/target pattern)
        # Short texts with clear entities and strong type classification are direct commands
        has_action_entity = any(e.type == 'action' for e in entities)
        has_resource_entity = any(e.type == 'resource' for e in entities)
        has_target_entity = any(e.type == 'target' for e in entities)
        if word_count <= 6 and has_action_entity and (has_resource_entity or has_target_entity):
            quality_boost += 0.15  # direct command pattern boost
        
        # Penalties
        penalties = 0.0
        
        # Penalty for very short texts — only if no clear entities found
        if len(original_text.strip()) < 5 and not entities:
            penalties += 0.2
        elif len(original_text.strip()) < 15 and not (has_action_entity and (has_resource_entity or has_target_entity)):
            penalties += 0.1
        
        # Penalty for very long texts
        if len(original_text) > 1000:
            penalties += 0.1
        elif len(original_text) > 500:
            penalties += 0.05
        
        # Penalty for excessive punctuation or special characters
        special_char_ratio = len(re.findall(r'[^a-zA-Z0-9\s]', original_text)) / len(original_text)
        if special_char_ratio > 0.2:
            penalties += 0.1
        
        # Calculate final confidence
        confidence = base_confidence + entity_boost + type_boost + token_boost + quality_boost - penalties
        
        return max(0.1, min(1.0, confidence))
    
    def _calculate_entity_confidence_enhanced(self, entity_text: str, entity_type: str, 
                                           start_pos: int, end_pos: int, 
                                           tokens: List[Dict[str, Any]]) -> float:
        """Calculate enhanced confidence score for a specific entity."""
        # Base confidence
        confidence = 0.7
        
        # Boost for specific patterns
        if entity_type == 'resource':
            if re.match(r'\b(?:sw|rt|h)\d+\b', entity_text, re.IGNORECASE):
                confidence += 0.25
            elif re.match(r'\b(?:switch|router|host|link|port)\d*\b', entity_text, re.IGNORECASE):
                confidence += 0.2
        
        elif entity_type == 'parameter':
            if re.match(r'\b\d+\s*(?:mbps|gbps|kbps|ms|sec|min)\b', entity_text, re.IGNORECASE):
                confidence += 0.25
            elif re.match(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', entity_text):  # IP address
                confidence += 0.3
        
        elif entity_type == 'identifier':
            if '@' in entity_text:
                confidence += 0.2
            elif re.match(r'\b[a-zA-Z][a-zA-Z0-9_-]*\d+\b', entity_text):
                confidence += 0.15
        
        elif entity_type == 'action':
            action_words = ['create', 'delete', 'modify', 'configure', 'set', 'add', 'remove']
            if entity_text.lower() in action_words:
                confidence += 0.2
        
        # Context-based adjustments
        # Check if entity is surrounded by relevant tokens
        relevant_tokens = [t for t in tokens if abs(t['start'] - start_pos) < 50 or abs(t['end'] - end_pos) < 50]
        context_boost = min(len(relevant_tokens) * 0.01, 0.05)
        confidence += context_boost
        
        # Length-based adjustments
        if len(entity_text) < 2:
            confidence -= 0.2
        elif len(entity_text) < 3:
            confidence -= 0.1
        elif len(entity_text) > 20:
            confidence -= 0.05
        
        # Boost for entities that match token boundaries
        matching_tokens = [t for t in tokens if t['text'].lower() == entity_text.lower()]
        if matching_tokens:
            confidence += 0.1
        
        return max(0.1, min(1.0, confidence))
    
    def _has_clear_intent_indicators(self, text: str, intent_type: IntentType) -> bool:
        """Check if text has clear indicators for the classified intent type."""
        text_lower = text.lower()
        pattern_config = self.intent_type_patterns.get(intent_type, {})
        
        # Check primary patterns (stronger indicators)
        primary_patterns = pattern_config.get('primary', [])
        for pattern in primary_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        
        # Check secondary patterns (weaker indicators)
        secondary_patterns = pattern_config.get('secondary', [])
        secondary_matches = 0
        for pattern in secondary_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                secondary_matches += 1
        
        # Consider it clear if we have multiple secondary indicators
        return secondary_matches >= 2
    
    def _extract_parameters_enhanced(self, text: str, entities: List[Entity], 
                                   tokens: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract parameters from text, entities, and tokens with enhanced patterns."""
        parameters = {}
        
        # Extract explicit key-value parameters
        # Pattern: key = value, key: value, key is value
        kv_patterns = [
            r'(\w+)\s*[:=]\s*(\d+(?:\.\d+)?(?:\s*(?:mbps|gbps|kbps|ms|sec|min|kb|mb|gb|tb))?)',
            r'(\w+)\s*[:=]\s*["\']([^"\']+)["\']',
            r'(\w+)\s+(?:is|equals?)\s+(\w+)',
            r'(?:set|with|using)\s+(\w+)\s+(?:to|as)\s+(\w+)'
        ]
        
        for pattern in kv_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                param_name = match.group(1).lower()
                param_value = match.group(2)
                
                # Try to convert to appropriate type
                if re.match(r'^\d+$', param_value):
                    param_value = int(param_value)
                elif re.match(r'^\d+\.\d+$', param_value):
                    param_value = float(param_value)
                elif param_value.lower() in ['true', 'false']:
                    param_value = param_value.lower() == 'true'
                
                parameters[param_name] = param_value
        
        # Extract parameters from entities
        for entity in entities:
            if entity.type in ['parameter', 'value', 'identifier']:
                # Use entity type and a simplified name
                param_key = f"{entity.type}_{len(parameters) + 1}"
                
                # Avoid duplicates
                while param_key in parameters:
                    param_key = f"{entity.type}_{len(parameters) + 1}"
                
                parameters[param_key] = entity.value
        
        # Extract parameters from special tokens
        for token in tokens:
            if token['type'] in ['number', 'unit', 'ip_address', 'mac_address']:
                param_key = f"token_{token['type']}_{len(parameters) + 1}"
                
                # Avoid duplicates
                while param_key in parameters:
                    param_key = f"token_{token['type']}_{len(parameters) + 1}"
                
                # Convert numbers
                if token['type'] == 'number':
                    try:
                        value = int(token['text']) if '.' not in token['text'] else float(token['text'])
                        parameters[param_key] = value
                    except ValueError:
                        parameters[param_key] = token['text']
                else:
                    parameters[param_key] = token['text']
        
        # Extract common networking parameters with context
        networking_params = {
            'bandwidth': r'\b(\d+(?:\.\d+)?)\s*(?:mbps|gbps|kbps)\b',
            'latency': r'\b(\d+(?:\.\d+)?)\s*(?:ms|milliseconds?)\b',
            'priority': r'\bpriority\s+(\d+|high|medium|low|critical)\b',
            'vlan_id': r'\bvlan\s+(\d+)\b',
            'port': r'\bport\s+(\d+)\b',
            'timeout': r'\btimeout\s+(\d+(?:\.\d+)?)\s*(?:sec|seconds?|min|minutes?)?\b'
        }
        
        for param_name, pattern in networking_params.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                value = match.group(1)
                # Convert to appropriate type
                if value.isdigit():
                    value = int(value)
                elif re.match(r'^\d+\.\d+$', value):
                    value = float(value)
                
                parameters[param_name] = value
        
        return parameters
    
    def validate_entities_against_network_state(self, intent: IntentObject, 
                                               network_state: NetworkState) -> ContextualizedIntent:
        """
        Validate extracted entities against current network state and create contextualized intent.
        
        Args:
            intent: Parsed intent object
            network_state: Current network state
            
        Returns:
            ContextualizedIntent with validation results and suggestions
        """
        relevant_resources = []
        conflicts = []
        recommendations = []
        network_context = {}
        
        # Validate each entity against network state
        for entity in intent.entities:
            if entity.type == 'resource':
                validation_result = self._validate_resource_entity(entity, network_state)
                
                if validation_result['exists']:
                    relevant_resources.append(entity.value)
                    if validation_result['available']:
                        network_context[entity.value] = validation_result['details']
                    else:
                        conflicts.append(f"Resource '{entity.value}' exists but is not available (status: {validation_result['status']})")
                else:
                    # Generate suggestions for invalid resource references
                    suggestions = self._generate_resource_suggestions(entity.value, network_state)
                    if suggestions:
                        recommendations.append(f"Resource '{entity.value}' not found. Did you mean: {', '.join(suggestions[:3])}?")
                    else:
                        recommendations.append(f"Resource '{entity.value}' not found in current network topology")
            
            elif entity.type == 'identifier':
                # Validate identifiers (could be switch names, host names, etc.)
                validation_result = self._validate_identifier_entity(entity, network_state)
                if validation_result['matches']:
                    relevant_resources.extend(validation_result['matched_resources'])
                    network_context.update(validation_result['context'])
        
        # Check for resource conflicts and dependencies
        conflicts.extend(self._check_resource_conflicts(relevant_resources, network_state))
        
        # Add network context information
        network_context.update(self._gather_network_context(relevant_resources, network_state))
        
        # Generate recommendations based on current network state
        recommendations.extend(self._generate_context_recommendations(intent, network_state))
        
        return ContextualizedIntent(
            intent=intent,
            relevant_resources=relevant_resources,
            network_context=network_context,
            conflicts=conflicts,
            recommendations=recommendations
        )
    
    def _validate_resource_entity(self, entity: Entity, network_state: NetworkState) -> Dict[str, Any]:
        """Validate a resource entity against network state."""
        resource_id = entity.value.lower()
        
        # Check switches
        for switch in network_state.topology.switches:
            if switch.id.lower() == resource_id or switch.name.lower() == resource_id:
                return {
                    'exists': True,
                    'available': switch.status == "active",
                    'status': switch.status,
                    'type': 'switch',
                    'details': {
                        'id': switch.id,
                        'name': switch.name,
                        'dpid': switch.dpid,
                        'ports': switch.ports,
                        'status': switch.status
                    }
                }
        
        # Check links
        for link in network_state.topology.links:
            if link.id.lower() == resource_id:
                return {
                    'exists': True,
                    'available': link.status == "active",
                    'status': link.status,
                    'type': 'link',
                    'details': {
                        'id': link.id,
                        'source_switch': link.source_switch,
                        'destination_switch': link.destination_switch,
                        'bandwidth': link.bandwidth,
                        'status': link.status
                    }
                }
        
        # Check hosts
        for host in network_state.topology.hosts:
            if (host.id.lower() == resource_id or 
                host.mac_address.lower() == resource_id or
                (host.ip_address and host.ip_address.lower() == resource_id)):
                return {
                    'exists': True,
                    'available': host.status == "active",
                    'status': host.status,
                    'type': 'host',
                    'details': {
                        'id': host.id,
                        'mac_address': host.mac_address,
                        'ip_address': host.ip_address,
                        'connected_switch': host.connected_switch,
                        'status': host.status
                    }
                }
        
        return {
            'exists': False,
            'available': False,
            'status': 'not_found',
            'type': 'unknown',
            'details': {}
        }
    
    def _validate_identifier_entity(self, entity: Entity, network_state: NetworkState) -> Dict[str, Any]:
        """Validate an identifier entity and find matching resources."""
        identifier = entity.value.lower()
        matched_resources = []
        context = {}
        
        # Check if identifier matches any resource patterns
        # Pattern: sw1, switch1, etc.
        if re.match(r'^sw\d+$', identifier) or re.match(r'^switch\d+$', identifier):
            for switch in network_state.topology.switches:
                if (switch.id.lower() == identifier or 
                    switch.name.lower() == identifier or
                    switch.id.lower().startswith(identifier[:2])):
                    matched_resources.append(switch.id)
                    context[switch.id] = {'type': 'switch', 'name': switch.name, 'status': switch.status}
        
        # Pattern: h1, host1, etc.
        elif re.match(r'^h\d+$', identifier) or re.match(r'^host\d+$', identifier):
            for host in network_state.topology.hosts:
                if (host.id.lower() == identifier or 
                    host.id.lower().startswith(identifier[:1])):
                    matched_resources.append(host.id)
                    context[host.id] = {'type': 'host', 'ip': host.ip_address, 'status': host.status}
        
        # Pattern: link identifiers
        elif 'link' in identifier or re.match(r'^l\d+$', identifier):
            for link in network_state.topology.links:
                if link.id.lower() == identifier:
                    matched_resources.append(link.id)
                    context[link.id] = {'type': 'link', 'status': link.status}
        
        return {
            'matches': len(matched_resources) > 0,
            'matched_resources': matched_resources,
            'context': context
        }
    
    def _generate_resource_suggestions(self, invalid_resource: str, network_state: NetworkState) -> List[str]:
        """Generate suggestions for invalid resource references using fuzzy matching."""
        suggestions = []
        invalid_lower = invalid_resource.lower()
        
        # Collect all resource identifiers
        all_resources = []
        
        # Add switches
        for switch in network_state.topology.switches:
            all_resources.extend([switch.id, switch.name])
        
        # Add links
        for link in network_state.topology.links:
            all_resources.append(link.id)
        
        # Add hosts
        for host in network_state.topology.hosts:
            all_resources.extend([host.id, host.mac_address])
            if host.ip_address:
                all_resources.append(host.ip_address)
        
        # Find similar resources using simple string matching
        for resource in all_resources:
            resource_lower = resource.lower()
            
            # Exact substring match
            if invalid_lower in resource_lower or resource_lower in invalid_lower:
                suggestions.append(resource)
            # Similar length and some character overlap
            elif (abs(len(invalid_lower) - len(resource_lower)) <= 2 and
                  len(set(invalid_lower) & set(resource_lower)) >= min(3, len(invalid_lower) // 2)):
                suggestions.append(resource)
        
        # Remove duplicates and limit suggestions
        return list(dict.fromkeys(suggestions))[:5]
    
    def _check_resource_conflicts(self, resources: List[str], network_state: NetworkState) -> List[str]:
        """Check for conflicts between requested resources."""
        conflicts = []
        
        # Check if resources are already heavily utilized
        for resource_id in resources:
            utilization = network_state.get_resource_utilization(resource_id)
            if utilization and utilization > 90:
                conflicts.append(f"Resource '{resource_id}' is heavily utilized ({utilization:.1f}%)")
        
        # Check for anomalies affecting requested resources
        for anomaly in network_state.anomalies:
            if anomaly.severity in ['high', 'critical']:
                affected_requested = set(anomaly.affected_resources) & set(resources)
                if affected_requested:
                    conflicts.append(f"Critical anomaly '{anomaly.type}' affects requested resources: {', '.join(affected_requested)}")
        
        return conflicts
    
    def _gather_network_context(self, resources: List[str], network_state: NetworkState) -> Dict[str, Any]:
        """Gather relevant network context for the requested resources."""
        context = {
            'network_summary': {
                'total_switches': len(network_state.topology.switches),
                'total_links': len(network_state.topology.links),
                'total_hosts': len(network_state.topology.hosts),
                'active_flows': len(network_state.flows),
                'active_anomalies': len([a for a in network_state.anomalies if a.resolved_at is None])
            },
            'metrics_summary': {
                'bandwidth_utilization': network_state.metrics.bandwidth.utilization_percentage,
                'average_latency': network_state.metrics.latency.average_latency,
                'cpu_utilization': network_state.metrics.utilization.cpu_utilization
            }
        }
        
        # Add specific context for requested resources
        if resources:
            context['requested_resources'] = {}
            for resource_id in resources:
                utilization = network_state.get_resource_utilization(resource_id)
                if utilization is not None:
                    context['requested_resources'][resource_id] = {
                        'utilization': utilization,
                        'available': network_state.is_resource_available(resource_id)
                    }
        
        return context
    
    def _generate_context_recommendations(self, intent: IntentObject, network_state: NetworkState) -> List[str]:
        """Generate recommendations based on intent type and network context."""
        recommendations = []
        
        # Check network health
        if network_state.metrics.bandwidth.utilization_percentage > 80:
            recommendations.append("Network bandwidth utilization is high (>80%). Consider load balancing or capacity planning.")
        
        if network_state.metrics.latency.average_latency > 100:  # ms
            recommendations.append("Network latency is elevated. Check for congestion or routing issues.")
        
        # Intent-specific recommendations
        if intent.intent_type == IntentType.CONFIGURATION:
            if len(network_state.anomalies) > 0:
                active_anomalies = [a for a in network_state.anomalies if a.resolved_at is None]
                if active_anomalies:
                    recommendations.append(f"Consider resolving {len(active_anomalies)} active anomalies before making configuration changes.")
        
        elif intent.intent_type == IntentType.ANOMALY_RESPONSE:
            critical_anomalies = [a for a in network_state.anomalies 
                                if a.severity == 'critical' and a.resolved_at is None]
            if critical_anomalies:
                recommendations.append(f"Priority should be given to {len(critical_anomalies)} critical anomalies.")
        
        return recommendations
    
    def detect_ambiguity(self, intent: IntentObject, network_state: Optional[NetworkState] = None) -> Dict[str, Any]:
        """
        Detect ambiguities in the parsed intent and calculate ambiguity score.
        
        Args:
            intent: Parsed intent object
            network_state: Optional network state for context-aware ambiguity detection
            
        Returns:
            Dictionary with ambiguity analysis results
        """
        ambiguities = []
        ambiguity_score = 0.0
        clarification_needed = False
        
        # Check for vague or incomplete entities
        vague_entities = self._detect_vague_entities(intent)
        if vague_entities:
            ambiguities.extend(vague_entities)
            ambiguity_score += len(vague_entities) * 0.2
        
        # Check for missing critical information
        missing_info = self._detect_missing_information(intent)
        if missing_info:
            ambiguities.extend(missing_info)
            ambiguity_score += len(missing_info) * 0.3
        
        # Check for conflicting or contradictory information
        conflicts = self._detect_internal_conflicts(intent)
        if conflicts:
            ambiguities.extend(conflicts)
            ambiguity_score += len(conflicts) * 0.4
        
        # Check for multiple possible interpretations
        interpretations = self._detect_multiple_interpretations(intent)
        if interpretations:
            ambiguities.extend(interpretations)
            ambiguity_score += len(interpretations) * 0.25
        
        # Context-aware ambiguity detection if network state is available
        if network_state:
            context_ambiguities = self._detect_context_ambiguities(intent, network_state)
            if context_ambiguities:
                ambiguities.extend(context_ambiguities)
                ambiguity_score += len(context_ambiguities) * 0.15
        
        # Normalize ambiguity score
        ambiguity_score = min(1.0, ambiguity_score)
        
        # Determine if clarification is needed
        clarification_needed = ambiguity_score > 0.3 or len(ambiguities) > 2
        
        return {
            'ambiguity_score': ambiguity_score,
            'ambiguities': ambiguities,
            'clarification_needed': clarification_needed,
            'confidence_impact': max(0.0, intent.confidence - ambiguity_score * 0.5)
        }
    
    def generate_clarification_requests(self, intent: IntentObject, 
                                      ambiguity_analysis: Dict[str, Any],
                                      network_state: Optional[NetworkState] = None) -> List[str]:
        """
        Generate specific clarification requests based on detected ambiguities.
        
        Args:
            intent: Parsed intent object
            ambiguity_analysis: Results from ambiguity detection
            network_state: Optional network state for context-aware suggestions
            
        Returns:
            List of clarification request strings
        """
        clarification_requests = []
        
        for ambiguity in ambiguity_analysis['ambiguities']:
            request = self._generate_specific_clarification(ambiguity, intent, network_state)
            if request:
                clarification_requests.append(request)
        
        # Add general clarification requests based on intent type
        general_requests = self._generate_general_clarifications(intent, network_state)
        clarification_requests.extend(general_requests)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_requests = []
        for request in clarification_requests:
            if request not in seen:
                unique_requests.append(request)
                seen.add(request)
        
        return unique_requests[:5]  # Limit to 5 most important clarifications
    
    def _detect_vague_entities(self, intent: IntentObject) -> List[Dict[str, Any]]:
        """Detect vague or incomplete entity references."""
        vague_entities = []
        
        for entity in intent.entities:
            # Check for very generic terms
            if entity.value.lower() in ['switch', 'router', 'host', 'link', 'network', 'device']:
                vague_entities.append({
                    'type': 'vague_entity',
                    'entity': entity.value,
                    'description': f"'{entity.value}' is too generic - which specific {entity.value}?",
                    'severity': 'medium'
                })
            
            # Check for incomplete identifiers
            elif entity.type == 'identifier' and len(entity.value) < 2:
                vague_entities.append({
                    'type': 'incomplete_identifier',
                    'entity': entity.value,
                    'description': f"Identifier '{entity.value}' seems incomplete",
                    'severity': 'high'
                })
            
            # Check for low confidence entities
            elif entity.confidence < 0.4:
                vague_entities.append({
                    'type': 'low_confidence_entity',
                    'entity': entity.value,
                    'description': f"Uncertain about entity '{entity.value}' (confidence: {entity.confidence:.2f})",
                    'severity': 'low'
                })
        
        return vague_entities
    
    def _detect_missing_information(self, intent: IntentObject) -> List[Dict[str, Any]]:
        """Detect missing critical information based on intent type."""
        missing_info = []
        
        if intent.intent_type == IntentType.CONFIGURATION:
            # Check for missing target resources
            resource_entities = [e for e in intent.entities if e.type in ['resource', 'identifier']]
            if not resource_entities:
                missing_info.append({
                    'type': 'missing_target',
                    'description': "Configuration intent is missing target resource specification",
                    'severity': 'high'
                })
            
            # Check for missing action specification
            action_entities = [e for e in intent.entities if e.type == 'action']
            if not action_entities:
                # Look for action words in the text
                action_words = ['create', 'delete', 'modify', 'configure', 'set', 'add', 'remove']
                if not any(word in intent.raw_text.lower() for word in action_words):
                    missing_info.append({
                        'type': 'missing_action',
                        'description': "Configuration intent is missing clear action specification",
                        'severity': 'high'
                    })
            
            # Check for missing parameters for specific actions
            if 'bandwidth' in intent.raw_text.lower() and not any('bandwidth' in p for p in intent.parameters.keys()):
                missing_info.append({
                    'type': 'missing_parameter_value',
                    'description': "Bandwidth mentioned but no specific value provided",
                    'severity': 'medium'
                })
        
        elif intent.intent_type == IntentType.QUERY:
            # Check for overly broad queries
            if len(intent.entities) == 0 and len(intent.raw_text.split()) < 4:
                missing_info.append({
                    'type': 'overly_broad_query',
                    'description': "Query is too broad - what specific information do you need?",
                    'severity': 'medium'
                })
        
        return missing_info
    
    def _detect_internal_conflicts(self, intent: IntentObject) -> List[Dict[str, Any]]:
        """Detect conflicting or contradictory information within the intent."""
        conflicts = []
        
        # Check for conflicting actions
        action_entities = [e for e in intent.entities if e.type == 'action']
        if len(action_entities) > 1:
            action_values = [e.value.lower() for e in action_entities]
            conflicting_pairs = [
                ('create', 'delete'),
                ('add', 'remove'),
                ('enable', 'disable'),
                ('start', 'stop')
            ]
            
            for pair in conflicting_pairs:
                if pair[0] in action_values and pair[1] in action_values:
                    conflicts.append({
                        'type': 'conflicting_actions',
                        'description': f"Conflicting actions detected: '{pair[0]}' and '{pair[1]}'",
                        'severity': 'high'
                    })
        
        # Check for conflicting parameters
        bandwidth_params = [p for p in intent.parameters.keys() if 'bandwidth' in p.lower()]
        if len(bandwidth_params) > 1:
            values = [intent.parameters[p] for p in bandwidth_params]
            if len(set(str(v) for v in values)) > 1:
                conflicts.append({
                    'type': 'conflicting_parameters',
                    'description': f"Multiple different bandwidth values specified: {values}",
                    'severity': 'medium'
                })
        
        return conflicts
    
    def _detect_multiple_interpretations(self, intent: IntentObject) -> List[Dict[str, Any]]:
        """Detect cases where the intent could have multiple valid interpretations."""
        interpretations = []
        
        # Check for ambiguous pronouns or references
        ambiguous_words = ['it', 'this', 'that', 'them', 'they']
        for word in ambiguous_words:
            if word in intent.raw_text.lower().split():
                interpretations.append({
                    'type': 'ambiguous_reference',
                    'description': f"Ambiguous reference '{word}' - what does it refer to?",
                    'severity': 'medium'
                })
        
        # Check for multiple possible targets
        resource_entities = [e for e in intent.entities if e.type in ['resource', 'identifier']]
        if len(resource_entities) > 3:
            interpretations.append({
                'type': 'multiple_targets',
                'description': f"Multiple resources mentioned ({len(resource_entities)}) - which one is the primary target?",
                'severity': 'medium'
            })
        
        # Check for ambiguous scope
        scope_indicators = ['all', 'every', 'each', 'some', 'any']
        if any(word in intent.raw_text.lower() for word in scope_indicators):
            if not resource_entities:
                interpretations.append({
                    'type': 'ambiguous_scope',
                    'description': "Scope indicator used but target resources not clearly specified",
                    'severity': 'medium'
                })
        
        return interpretations
    
    def _detect_context_ambiguities(self, intent: IntentObject, network_state: NetworkState) -> List[Dict[str, Any]]:
        """Detect ambiguities that require network context to resolve."""
        context_ambiguities = []
        
        # Check for resources that could match multiple network elements
        for entity in intent.entities:
            if entity.type in ['resource', 'identifier']:
                matches = self._find_matching_resources(entity.value, network_state)
                if len(matches) > 1:
                    context_ambiguities.append({
                        'type': 'multiple_resource_matches',
                        'entity': entity.value,
                        'matches': matches,
                        'description': f"'{entity.value}' could refer to multiple resources: {', '.join(matches)}",
                        'severity': 'high'
                    })
        
        # Check for operations that might affect multiple resources
        if intent.intent_type == IntentType.CONFIGURATION:
            action_entities = [e for e in intent.entities if e.type == 'action']
            if action_entities and 'all' in intent.raw_text.lower():
                total_resources = (len(network_state.topology.switches) + 
                                 len(network_state.topology.hosts) + 
                                 len(network_state.topology.links))
                if total_resources > 5:
                    context_ambiguities.append({
                        'type': 'broad_scope_operation',
                        'description': f"Operation might affect {total_resources} resources - please confirm scope",
                        'severity': 'medium'
                    })
        
        return context_ambiguities
    
    def _find_matching_resources(self, entity_value: str, network_state: NetworkState) -> List[str]:
        """Find all resources that could match the given entity value."""
        matches = []
        entity_lower = entity_value.lower()
        
        # Check switches
        for switch in network_state.topology.switches:
            if (entity_lower in switch.id.lower() or 
                entity_lower in switch.name.lower() or
                switch.id.lower() in entity_lower or
                switch.name.lower() in entity_lower):
                matches.append(switch.id)
        
        # Check hosts
        for host in network_state.topology.hosts:
            if (entity_lower in host.id.lower() or
                (host.ip_address and entity_lower in host.ip_address.lower())):
                matches.append(host.id)
        
        # Check links
        for link in network_state.topology.links:
            if entity_lower in link.id.lower():
                matches.append(link.id)
        
        return matches
    
    def _generate_specific_clarification(self, ambiguity: Dict[str, Any], 
                                       intent: IntentObject, 
                                       network_state: Optional[NetworkState]) -> Optional[str]:
        """Generate a specific clarification request for an ambiguity."""
        ambiguity_type = ambiguity['type']
        
        if ambiguity_type == 'vague_entity':
            if network_state:
                # Provide specific options
                if ambiguity['entity'].lower() == 'switch':
                    switches = [s.id for s in network_state.topology.switches if s.status == "active"]
                    if switches:
                        return f"Which switch do you mean? Available options: {', '.join(switches[:5])}"
                elif ambiguity['entity'].lower() == 'host':
                    hosts = [h.id for h in network_state.topology.hosts if h.status == "active"]
                    if hosts:
                        return f"Which host do you mean? Available options: {', '.join(hosts[:5])}"
            return f"Please specify which {ambiguity['entity']} you're referring to."
        
        elif ambiguity_type == 'multiple_resource_matches':
            matches = ambiguity['matches']
            return f"'{ambiguity['entity']}' could refer to: {', '.join(matches)}. Which one do you mean?"
        
        elif ambiguity_type == 'missing_target':
            if network_state:
                available_resources = []
                available_resources.extend([s.id for s in network_state.topology.switches[:3]])
                available_resources.extend([h.id for h in network_state.topology.hosts[:3]])
                if available_resources:
                    return f"Which resource should be configured? For example: {', '.join(available_resources)}"
            return "Which network resource should be configured?"
        
        elif ambiguity_type == 'missing_action':
            return "What action should be performed? (e.g., create, modify, delete, configure)"
        
        elif ambiguity_type == 'missing_parameter_value':
            return ambiguity['description'] + " Please specify the exact value."
        
        elif ambiguity_type == 'conflicting_actions':
            return ambiguity['description'] + " Please clarify which action you want to perform."
        
        elif ambiguity_type == 'ambiguous_reference':
            return ambiguity['description']
        
        elif ambiguity_type == 'broad_scope_operation':
            return ambiguity['description']
        
        return None
    
    def _generate_general_clarifications(self, intent: IntentObject, 
                                       network_state: Optional[NetworkState]) -> List[str]:
        """Generate general clarification requests based on intent analysis."""
        clarifications = []
        
        # Low confidence intent
        if intent.confidence < 0.5:
            clarifications.append("I'm not entirely sure I understood your request correctly. Could you rephrase it?")
        
        # Very short intent
        if len(intent.raw_text.split()) < 3:
            clarifications.append("Could you provide more details about what you want to do?")
        
        # Configuration intent without clear parameters
        if (intent.intent_type == IntentType.CONFIGURATION and 
            len(intent.parameters) == 0 and 
            len(intent.entities) < 2):
            clarifications.append("What specific configuration changes do you want to make?")
        
        return clarifications
    
    def analyze_and_clarify_intent(self, text: str, network_state: Optional[NetworkState] = None,
                                 user_id: str = "default_user") -> Dict[str, Any]:
        """
        Main interface for parsing intent, detecting ambiguities, and generating clarifications.
        
        Args:
            text: Natural language intent text
            network_state: Optional network state for context-aware analysis
            user_id: ID of the user submitting the intent
            
        Returns:
            Dictionary with parsed intent, ambiguity analysis, and clarification requests
        """
        # Parse the intent
        intent = self.parse_intent(text, user_id)
        
        # Detect ambiguities
        ambiguity_analysis = self.detect_ambiguity(intent, network_state)
        
        # Generate clarification requests if needed
        clarification_requests = []
        if ambiguity_analysis['clarification_needed']:
            clarification_requests = self.generate_clarification_requests(
                intent, ambiguity_analysis, network_state
            )
        
        # Create contextualized intent if network state is available
        contextualized_intent = None
        if network_state:
            contextualized_intent = self.validate_entities_against_network_state(intent, network_state)
        
        return {
            'intent': intent,
            'contextualized_intent': contextualized_intent,
            'ambiguity_analysis': ambiguity_analysis,
            'clarification_requests': clarification_requests,
            'needs_clarification': len(clarification_requests) > 0,
            'confidence_adjusted': ambiguity_analysis['confidence_impact']
        }
    
    def handle_clarification_response(self, original_intent: IntentObject, 
                                    clarification_response: str,
                                    network_state: Optional[NetworkState] = None) -> Dict[str, Any]:
        """
        Handle user's response to clarification requests and update the intent.
        
        Args:
            original_intent: The original parsed intent
            clarification_response: User's response to clarification
            network_state: Optional network state for validation
            
        Returns:
            Updated analysis with refined intent
        """
        # Combine original intent with clarification response
        combined_text = f"{original_intent.raw_text} {clarification_response}"
        
        # Re-analyze with the additional information
        updated_analysis = self.analyze_and_clarify_intent(
            combined_text, network_state, original_intent.user_id
        )
        
        # Check if clarification resolved ambiguities
        original_ambiguity_score = self.detect_ambiguity(original_intent, network_state)['ambiguity_score']
        new_ambiguity_score = updated_analysis['ambiguity_analysis']['ambiguity_score']
        
        improvement = original_ambiguity_score - new_ambiguity_score
        
        updated_analysis['clarification_improvement'] = {
            'original_ambiguity_score': original_ambiguity_score,
            'new_ambiguity_score': new_ambiguity_score,
            'improvement': improvement,
            'resolved': improvement > 0.2
        }
        
        return updated_analysis
    
    def extract_and_validate_entities(self, text: str, network_state: NetworkState, 
                                    user_id: str = "default_user") -> ContextualizedIntent:
        """
        Main interface for extracting entities and validating against network state.
        
        Args:
            text: Natural language intent text
            network_state: Current network state for validation
            user_id: ID of the user submitting the intent
            
        Returns:
            ContextualizedIntent with validated entities and context
        """
        # First parse the intent normally
        intent = self.parse_intent(text, user_id)
        
        # Then validate entities against network state and add context
        contextualized_intent = self.validate_entities_against_network_state(intent, network_state)
        
        return contextualized_intent
    
    def suggest_entity_corrections(self, entity: Entity, network_state: NetworkState) -> List[str]:
        """
        Provide suggestions for correcting invalid entity references.
        
        Args:
            entity: Entity that failed validation
            network_state: Current network state
            
        Returns:
            List of suggested corrections
        """
        if entity.type == 'resource':
            return self._generate_resource_suggestions(entity.value, network_state)
        elif entity.type == 'identifier':
            # For identifiers, suggest based on pattern matching
            suggestions = []
            identifier = entity.value.lower()
            
            # Suggest switch patterns
            if re.match(r'^sw?\d*$', identifier):
                switch_ids = [s.id for s in network_state.topology.switches if s.status == "active"]
                suggestions.extend(switch_ids[:3])
            
            # Suggest host patterns  
            elif re.match(r'^h(ost)?\d*$', identifier):
                host_ids = [h.id for h in network_state.topology.hosts if h.status == "active"]
                suggestions.extend(host_ids[:3])
            
            return suggestions
        
        return []
    
    def get_network_resource_summary(self, network_state: NetworkState) -> Dict[str, Any]:
        """
        Get a summary of available network resources for user reference.
        
        Args:
            network_state: Current network state
            
        Returns:
            Dictionary with resource summaries
        """
        return {
            'switches': [
                {
                    'id': switch.id,
                    'name': switch.name,
                    'status': switch.status,
                    'ports': len(switch.ports)
                }
                for switch in network_state.topology.switches
            ],
            'hosts': [
                {
                    'id': host.id,
                    'ip_address': host.ip_address,
                    'connected_switch': host.connected_switch,
                    'status': host.status
                }
                for host in network_state.topology.hosts
            ],
            'links': [
                {
                    'id': link.id,
                    'source': link.source_switch,
                    'destination': link.destination_switch,
                    'status': link.status
                }
                for link in network_state.topology.links
            ],
            'summary': {
                'total_switches': len(network_state.topology.switches),
                'active_switches': len([s for s in network_state.topology.switches if s.status == "active"]),
                'total_hosts': len(network_state.topology.hosts),
                'active_hosts': len([h for h in network_state.topology.hosts if h.status == "active"]),
                'total_links': len(network_state.topology.links),
                'active_links': len([l for l in network_state.topology.links if l.status == "active"])
            }
        }

    def generate_clarification_questions(self, intent: IntentObject) -> List[str]:
        """
        Generate clarification questions for an ambiguous intent (API compatibility wrapper).
        
        Args:
            intent: The intent object to analyze
            
        Returns:
            List of clarification questions
        """
        clarification_result = self.generate_clarification_requests(intent)
        return clarification_result.get("clarification_questions", [])
