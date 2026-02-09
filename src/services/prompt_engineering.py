"""Prompt engineering system for ChatGPT API integration.

This module provides networking-specific prompt templates, context injection,
response parsing, and validation for optimal ChatGPT API usage.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
from pydantic import BaseModel, Field, validator

from src.models.intent import IntentObject, IntentType, ContextualizedIntent
from src.models.network import NetworkState, Anomaly, AnomalySeverity
from src.models.actions import ActionSequence, NetworkAction, ActionType


logger = logging.getLogger(__name__)


class PromptType(str, Enum):
    """Types of prompts for different operations."""
    INTENT_PARSING = "intent_parsing"
    ACTION_GENERATION = "action_generation"
    ANOMALY_ANALYSIS = "anomaly_analysis"
    CLARIFICATION = "clarification"
    VALIDATION = "validation"
    SLICE_ORCHESTRATION = "slice_orchestration"


class PromptTemplate(BaseModel):
    """Template for generating prompts."""
    type: PromptType
    system_message: str
    user_template: str
    response_schema: Dict[str, Any]
    max_tokens: int = 2000
    temperature: float = 0.1
    
    def format(self, **kwargs) -> str:
        """Format the user template with provided arguments."""
        try:
            return self.user_template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing required template parameter: {e}")


class ParsedResponse(BaseModel):
    """Parsed and validated response from ChatGPT."""
    raw_content: str
    parsed_data: Dict[str, Any]
    is_valid: bool
    validation_errors: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class PromptEngineeringSystem:
    """System for managing prompt templates and response processing."""
    
    def __init__(self):
        """Initialize the prompt engineering system."""
        self._templates: Dict[PromptType, PromptTemplate] = {}
        self._initialize_templates()
        logger.info("Prompt engineering system initialized")
    
    def _initialize_templates(self) -> None:
        """Initialize all prompt templates."""
        
        # Intent Parsing Template
        self._templates[PromptType.INTENT_PARSING] = PromptTemplate(
            type=PromptType.INTENT_PARSING,
            system_message=(
                "You are an expert network engineer specializing in Software-Defined Networking (SDN). "
                "Your task is to parse natural language network intents and extract structured information. "
                "Focus on identifying network resources, actions, targets, and parameters. "
                "Be precise and conservative in your confidence scores."
            ),
            user_template=(
                "Parse the following network intent and extract structured information:\n\n"
                "Intent: {intent_text}\n\n"
                "Provide a JSON response with:\n"
                "1. intent_type: 'configuration', 'query', or 'anomaly_response'\n"
                "2. entities: list of extracted entities with name, type, value, and confidence\n"
                "3. parameters: key-value pairs of extracted parameters\n"
                "4. confidence: overall confidence score (0.0-1.0)\n"
                "5. ambiguities: list of any ambiguous or unclear aspects\n\n"
                "Entity types: resource, action, target, parameter, identifier, value, condition\n\n"
                "Response format:\n{response_schema}"
            ),
            response_schema={
                "intent_type": "string",
                "entities": [
                    {
                        "name": "string",
                        "type": "string",
                        "value": "string",
                        "confidence": "float"
                    }
                ],
                "parameters": {},
                "confidence": "float",
                "ambiguities": ["string"]
            },
            max_tokens=1500,
            temperature=0.1
        )
        
        # Action Generation Template
        self._templates[PromptType.ACTION_GENERATION] = PromptTemplate(
            type=PromptType.ACTION_GENERATION,
            system_message=(
                "You are an expert SDN network engineer. Generate precise network actions "
                "to implement user intents. Consider network state, dependencies, and safety. "
                "Always provide rollback plans for configuration changes."
            ),
            user_template=(
                "Generate network actions for the following intent:\n\n"
                "Intent: {intent_text}\n"
                "Intent Type: {intent_type}\n\n"
                "Current Network State:\n"
                "- Switches: {switch_count}\n"
                "- Links: {link_count}\n"
                "- Hosts: {host_count}\n"
                "- Active Flows: {flow_count}\n"
                "- Network Slices: {slice_count}\n\n"
                "{network_details}\n\n"
                "Relevant Resources:\n{relevant_resources}\n\n"
                "Generate a JSON response with:\n"
                "1. actions: list of network actions (type, target, parameters, priority)\n"
                "2. execution_order: recommended order of execution\n"
                "3. estimated_duration: total estimated time in seconds\n"
                "4. dependencies: list of external dependencies\n"
                "5. rollback_plan: actions to revert changes if needed\n"
                "6. risks: potential risks and mitigation strategies\n\n"
                "Action types: flow_mod, slice_create, slice_modify, config_change\n\n"
                "Response format:\n{response_schema}"
            ),
            response_schema={
                "actions": [
                    {
                        "id": "string",
                        "type": "string",
                        "target": "string",
                        "parameters": {},
                        "priority": "int",
                        "timeout": "int",
                        "description": "string"
                    }
                ],
                "execution_order": ["string"],
                "estimated_duration": "int",
                "dependencies": ["string"],
                "rollback_plan": [
                    {
                        "id": "string",
                        "type": "string",
                        "target": "string",
                        "parameters": {}
                    }
                ],
                "risks": [
                    {
                        "description": "string",
                        "severity": "string",
                        "mitigation": "string"
                    }
                ]
            },
            max_tokens=2500,
            temperature=0.1
        )
        
        # Anomaly Analysis Template
        self._templates[PromptType.ANOMALY_ANALYSIS] = PromptTemplate(
            type=PromptType.ANOMALY_ANALYSIS,
            system_message=(
                "You are a network security and performance expert. Analyze network anomalies, "
                "classify their severity, and recommend mitigation actions. "
                "Consider both immediate threats and long-term network health."
            ),
            user_template=(
                "Analyze the following network anomaly:\n\n"
                "Anomaly Type: {anomaly_type}\n"
                "Severity: {anomaly_severity}\n"
                "Description: {anomaly_description}\n"
                "Affected Resources: {affected_resources}\n\n"
                "Network Context:\n{network_context}\n\n"
                "Provide a JSON response with:\n"
                "1. analysis: detailed analysis of the anomaly\n"
                "2. root_cause: likely root cause(s)\n"
                "3. impact_assessment: potential impact on network services\n"
                "4. severity_confirmation: confirm or adjust severity level\n"
                "5. mitigation_actions: recommended actions to address the anomaly\n"
                "6. monitoring_recommendations: what to monitor going forward\n\n"
                "Response format:\n{response_schema}"
            ),
            response_schema={
                "analysis": "string",
                "root_cause": ["string"],
                "impact_assessment": {
                    "affected_services": ["string"],
                    "performance_impact": "string",
                    "availability_risk": "string"
                },
                "severity_confirmation": "string",
                "mitigation_actions": [
                    {
                        "action": "string",
                        "priority": "string",
                        "estimated_time": "int"
                    }
                ],
                "monitoring_recommendations": ["string"]
            },
            max_tokens=2000,
            temperature=0.2
        )
        
        # Clarification Template
        self._templates[PromptType.CLARIFICATION] = PromptTemplate(
            type=PromptType.CLARIFICATION,
            system_message=(
                "You are a helpful network assistant. When user intents are ambiguous or incomplete, "
                "generate specific, actionable clarification questions. "
                "Help users provide the information needed to execute their intent safely."
            ),
            user_template=(
                "The following network intent is ambiguous or incomplete:\n\n"
                "Intent: {intent_text}\n"
                "Identified Ambiguities: {ambiguities}\n\n"
                "Available Network Resources:\n{available_resources}\n\n"
                "Generate specific clarification questions to resolve ambiguities. "
                "Provide a JSON response with:\n"
                "1. questions: list of clarification questions\n"
                "2. suggestions: suggested values or options for each question\n"
                "3. priority: priority level for each question (high, medium, low)\n\n"
                "Response format:\n{response_schema}"
            ),
            response_schema={
                "questions": [
                    {
                        "question": "string",
                        "context": "string",
                        "suggestions": ["string"],
                        "priority": "string"
                    }
                ]
            },
            max_tokens=1000,
            temperature=0.3
        )
        
        # Validation Template
        self._templates[PromptType.VALIDATION] = PromptTemplate(
            type=PromptType.VALIDATION,
            system_message=(
                "You are a network safety validator. Review proposed network actions "
                "for potential conflicts, safety issues, and compliance with best practices. "
                "Be thorough and conservative in your assessment."
            ),
            user_template=(
                "Validate the following network action sequence:\n\n"
                "Actions:\n{actions_json}\n\n"
                "Current Network State:\n{network_state_summary}\n\n"
                "Provide a JSON response with:\n"
                "1. is_safe: boolean indicating if actions are safe to execute\n"
                "2. conflicts: list of detected conflicts between actions\n"
                "3. risks: identified risks with severity levels\n"
                "4. recommendations: suggestions for improving safety\n"
                "5. approval_required: whether human approval is needed\n\n"
                "Response format:\n{response_schema}"
            ),
            response_schema={
                "is_safe": "boolean",
                "conflicts": [
                    {
                        "action_ids": ["string"],
                        "description": "string",
                        "severity": "string"
                    }
                ],
                "risks": [
                    {
                        "description": "string",
                        "severity": "string",
                        "affected_resources": ["string"],
                        "mitigation": "string"
                    }
                ],
                "recommendations": ["string"],
                "approval_required": "boolean"
            },
            max_tokens=1500,
            temperature=0.1
        )
        
        # Slice Orchestration Template
        self._templates[PromptType.SLICE_ORCHESTRATION] = PromptTemplate(
            type=PromptType.SLICE_ORCHESTRATION,
            system_message=(
                "You are a network slicing expert. Design and orchestrate network slices "
                "with appropriate resource allocation, QoS policies, and isolation. "
                "Ensure slices meet SLA requirements while optimizing resource utilization."
            ),
            user_template=(
                "Design a network slice based on the following requirements:\n\n"
                "Intent: {intent_text}\n"
                "Slice Requirements:\n{slice_requirements}\n\n"
                "Available Resources:\n"
                "- Total Bandwidth: {total_bandwidth}\n"
                "- Available Switches: {available_switches}\n"
                "- Current Slices: {current_slices}\n\n"
                "Provide a JSON response with:\n"
                "1. slice_configuration: complete slice configuration\n"
                "2. resource_allocation: detailed resource allocation plan\n"
                "3. qos_policies: QoS policies for the slice\n"
                "4. isolation_strategy: how to isolate this slice from others\n"
                "5. sla_guarantees: SLA parameters and guarantees\n"
                "6. monitoring_metrics: metrics to monitor for SLA compliance\n\n"
                "Response format:\n{response_schema}"
            ),
            response_schema={
                "slice_configuration": {
                    "slice_name": "string",
                    "slice_id": "string",
                    "resources": {
                        "bandwidth": "int",
                        "switches": ["string"],
                        "paths": []
                    }
                },
                "resource_allocation": {
                    "bandwidth_allocation": {},
                    "switch_allocation": {},
                    "priority_level": "string"
                },
                "qos_policies": [
                    {
                        "policy_type": "string",
                        "parameters": {}
                    }
                ],
                "isolation_strategy": "string",
                "sla_guarantees": {
                    "bandwidth_guarantee": "int",
                    "latency_guarantee": "float",
                    "availability_guarantee": "float"
                },
                "monitoring_metrics": ["string"]
            },
            max_tokens=2000,
            temperature=0.1
        )
    
    def get_template(self, prompt_type: PromptType) -> PromptTemplate:
        """Get a prompt template by type.
        
        Args:
            prompt_type: Type of prompt template to retrieve
            
        Returns:
            PromptTemplate for the specified type
            
        Raises:
            ValueError: If template type not found
        """
        if prompt_type not in self._templates:
            raise ValueError(f"Unknown prompt type: {prompt_type}")
        return self._templates[prompt_type]

    
    def build_intent_parsing_prompt(
        self,
        intent_text: str
    ) -> Tuple[str, str, Dict[str, Any]]:
        """Build prompt for intent parsing.
        
        Args:
            intent_text: Raw intent text from user
            
        Returns:
            Tuple of (system_message, user_prompt, config)
        """
        template = self.get_template(PromptType.INTENT_PARSING)
        
        user_prompt = template.format(
            intent_text=intent_text,
            response_schema=json.dumps(template.response_schema, indent=2)
        )
        
        config = {
            "max_tokens": template.max_tokens,
            "temperature": template.temperature
        }
        
        logger.debug(f"Built intent parsing prompt for: {intent_text[:50]}...")
        return template.system_message, user_prompt, config
    
    def build_action_generation_prompt(
        self,
        contextualized_intent: ContextualizedIntent,
        network_state: NetworkState
    ) -> Tuple[str, str, Dict[str, Any]]:
        """Build prompt for action generation.
        
        Args:
            contextualized_intent: Intent with network context
            network_state: Current network state
            
        Returns:
            Tuple of (system_message, user_prompt, config)
        """
        template = self.get_template(PromptType.ACTION_GENERATION)
        
        # Build network details summary
        network_details = self._format_network_state(network_state)
        
        # Format relevant resources
        relevant_resources = "\n".join(
            f"- {resource}" for resource in contextualized_intent.relevant_resources
        )
        if not relevant_resources:
            relevant_resources = "None specified"
        
        user_prompt = template.format(
            intent_text=contextualized_intent.intent.raw_text,
            intent_type=contextualized_intent.intent.intent_type.value,
            switch_count=len(network_state.topology.switches),
            link_count=len(network_state.topology.links),
            host_count=len(network_state.topology.hosts),
            flow_count=len(network_state.flows),
            slice_count=len(getattr(network_state, 'slices', [])),
            network_details=network_details,
            relevant_resources=relevant_resources,
            response_schema=json.dumps(template.response_schema, indent=2)
        )
        
        config = {
            "max_tokens": template.max_tokens,
            "temperature": template.temperature
        }
        
        logger.debug(f"Built action generation prompt for intent: {contextualized_intent.intent.id}")
        return template.system_message, user_prompt, config
    
    def build_anomaly_analysis_prompt(
        self,
        anomaly: Anomaly,
        network_state: NetworkState
    ) -> Tuple[str, str, Dict[str, Any]]:
        """Build prompt for anomaly analysis.
        
        Args:
            anomaly: Detected anomaly
            network_state: Current network state
            
        Returns:
            Tuple of (system_message, user_prompt, config)
        """
        template = self.get_template(PromptType.ANOMALY_ANALYSIS)
        
        # Build network context
        network_context = self._format_network_context_for_anomaly(network_state, anomaly)
        
        # Format affected resources
        affected_resources = ", ".join(anomaly.affected_resources) if anomaly.affected_resources else "None"
        
        user_prompt = template.format(
            anomaly_type=anomaly.type.value,
            anomaly_severity=anomaly.severity.value,
            anomaly_description=anomaly.description,
            affected_resources=affected_resources,
            network_context=network_context,
            response_schema=json.dumps(template.response_schema, indent=2)
        )
        
        config = {
            "max_tokens": template.max_tokens,
            "temperature": template.temperature
        }
        
        logger.debug(f"Built anomaly analysis prompt for: {anomaly.id}")
        return template.system_message, user_prompt, config
    
    def build_clarification_prompt(
        self,
        intent_text: str,
        ambiguities: List[str],
        network_state: NetworkState
    ) -> Tuple[str, str, Dict[str, Any]]:
        """Build prompt for clarification requests.
        
        Args:
            intent_text: Original intent text
            ambiguities: List of identified ambiguities
            network_state: Current network state
            
        Returns:
            Tuple of (system_message, user_prompt, config)
        """
        template = self.get_template(PromptType.CLARIFICATION)
        
        # Format available resources
        available_resources = self._format_available_resources(network_state)
        
        # Format ambiguities
        ambiguities_text = "\n".join(f"- {amb}" for amb in ambiguities)
        
        user_prompt = template.format(
            intent_text=intent_text,
            ambiguities=ambiguities_text,
            available_resources=available_resources,
            response_schema=json.dumps(template.response_schema, indent=2)
        )
        
        config = {
            "max_tokens": template.max_tokens,
            "temperature": template.temperature
        }
        
        logger.debug(f"Built clarification prompt with {len(ambiguities)} ambiguities")
        return template.system_message, user_prompt, config
    
    def build_validation_prompt(
        self,
        action_sequence: ActionSequence,
        network_state: NetworkState
    ) -> Tuple[str, str, Dict[str, Any]]:
        """Build prompt for action validation.
        
        Args:
            action_sequence: Sequence of actions to validate
            network_state: Current network state
            
        Returns:
            Tuple of (system_message, user_prompt, config)
        """
        template = self.get_template(PromptType.VALIDATION)
        
        # Convert actions to JSON
        actions_json = json.dumps(
            [action.dict() for action in action_sequence.actions],
            indent=2
        )
        
        # Build network state summary
        network_state_summary = self._format_network_state_summary(network_state)
        
        user_prompt = template.format(
            actions_json=actions_json,
            network_state_summary=network_state_summary,
            response_schema=json.dumps(template.response_schema, indent=2)
        )
        
        config = {
            "max_tokens": template.max_tokens,
            "temperature": template.temperature
        }
        
        logger.debug(f"Built validation prompt for sequence: {action_sequence.id}")
        return template.system_message, user_prompt, config
    
    def build_slice_orchestration_prompt(
        self,
        intent_text: str,
        slice_requirements: Dict[str, Any],
        network_state: NetworkState
    ) -> Tuple[str, str, Dict[str, Any]]:
        """Build prompt for network slice orchestration.
        
        Args:
            intent_text: Original intent text
            slice_requirements: Extracted slice requirements
            network_state: Current network state
            
        Returns:
            Tuple of (system_message, user_prompt, config)
        """
        template = self.get_template(PromptType.SLICE_ORCHESTRATION)
        
        # Calculate available resources
        total_bandwidth = sum(
            link.bandwidth or 0 for link in network_state.topology.links
        )
        
        available_switches = [
            switch.id for switch in network_state.topology.switches
            if switch.status == "active"
        ]
        
        current_slices = len(getattr(network_state, 'slices', []))
        
        user_prompt = template.format(
            intent_text=intent_text,
            slice_requirements=json.dumps(slice_requirements, indent=2),
            total_bandwidth=total_bandwidth,
            available_switches=", ".join(available_switches),
            current_slices=current_slices,
            response_schema=json.dumps(template.response_schema, indent=2)
        )
        
        config = {
            "max_tokens": template.max_tokens,
            "temperature": template.temperature
        }
        
        logger.debug(f"Built slice orchestration prompt")
        return template.system_message, user_prompt, config
    
    def parse_response(
        self,
        raw_response: str,
        expected_schema: Dict[str, Any],
        prompt_type: PromptType
    ) -> ParsedResponse:
        """Parse and validate ChatGPT response.
        
        Args:
            raw_response: Raw response text from ChatGPT
            expected_schema: Expected response schema
            prompt_type: Type of prompt that generated this response
            
        Returns:
            ParsedResponse with validation results
        """
        validation_errors = []
        parsed_data = {}
        is_valid = False
        confidence = 0.0
        
        try:
            # Try to extract JSON from response
            json_str = self._extract_json(raw_response)
            parsed_data = json.loads(json_str)
            
            # Validate against schema
            validation_errors = self._validate_against_schema(parsed_data, expected_schema)
            
            is_valid = len(validation_errors) == 0
            
            # Extract confidence if present
            if "confidence" in parsed_data:
                confidence = float(parsed_data["confidence"])
            else:
                # Estimate confidence based on response completeness
                confidence = self._estimate_confidence(parsed_data, expected_schema)
            
            if is_valid:
                logger.debug(f"Successfully parsed {prompt_type.value} response")
            else:
                logger.warning(
                    f"Validation errors in {prompt_type.value} response: {validation_errors}"
                )
        
        except json.JSONDecodeError as e:
            validation_errors.append(f"Invalid JSON: {str(e)}")
            logger.error(f"Failed to parse JSON from response: {str(e)}")
        
        except Exception as e:
            validation_errors.append(f"Parsing error: {str(e)}")
            logger.error(f"Error parsing response: {str(e)}")
        
        return ParsedResponse(
            raw_content=raw_response,
            parsed_data=parsed_data,
            is_valid=is_valid,
            validation_errors=validation_errors,
            confidence=confidence
        )
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON from text that may contain markdown or other formatting.
        
        Args:
            text: Text potentially containing JSON
            
        Returns:
            Extracted JSON string
        """
        # Remove markdown code blocks if present
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()
        
        # Try to find JSON object boundaries
        start = text.find("{")
        if start != -1:
            # Find matching closing brace
            brace_count = 0
            for i in range(start, len(text)):
                if text[i] == "{":
                    brace_count += 1
                elif text[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        return text[start:i+1]
        
        # Return as-is if no JSON structure found
        return text.strip()
    
    def _validate_against_schema(
        self,
        data: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> List[str]:
        """Validate parsed data against expected schema.
        
        Args:
            data: Parsed data dictionary
            schema: Expected schema
            
        Returns:
            List of validation error messages
        """
        errors = []
        
        # Check for required top-level keys
        for key in schema.keys():
            if key not in data:
                errors.append(f"Missing required field: {key}")
        
        # Type validation for known fields
        for key, value in data.items():
            if key in schema:
                expected_type = schema[key]
                if isinstance(expected_type, str):
                    # Simple type check
                    if expected_type == "string" and not isinstance(value, str):
                        errors.append(f"Field '{key}' should be string, got {type(value).__name__}")
                    elif expected_type == "int" and not isinstance(value, int):
                        errors.append(f"Field '{key}' should be int, got {type(value).__name__}")
                    elif expected_type == "float" and not isinstance(value, (int, float)):
                        errors.append(f"Field '{key}' should be float, got {type(value).__name__}")
                    elif expected_type == "boolean" and not isinstance(value, bool):
                        errors.append(f"Field '{key}' should be boolean, got {type(value).__name__}")
                elif isinstance(expected_type, list):
                    # List type check
                    if not isinstance(value, list):
                        errors.append(f"Field '{key}' should be list, got {type(value).__name__}")
                elif isinstance(expected_type, dict):
                    # Dict type check
                    if not isinstance(value, dict):
                        errors.append(f"Field '{key}' should be dict, got {type(value).__name__}")
        
        return errors
    
    def _estimate_confidence(
        self,
        data: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> float:
        """Estimate confidence based on response completeness.
        
        Args:
            data: Parsed data
            schema: Expected schema
            
        Returns:
            Estimated confidence score (0.0-1.0)
        """
        if not schema:
            return 0.5
        
        # Calculate completeness
        required_fields = len(schema)
        present_fields = sum(1 for key in schema.keys() if key in data)
        
        completeness = present_fields / required_fields if required_fields > 0 else 0.0
        
        # Adjust based on data quality
        quality_score = 1.0
        for value in data.values():
            if value is None or value == "" or value == []:
                quality_score *= 0.9
        
        return min(completeness * quality_score, 1.0)
    
    def _format_network_state(self, network_state: NetworkState) -> str:
        """Format network state for prompt inclusion.
        
        Args:
            network_state: Network state to format
            
        Returns:
            Formatted network state string
        """
        lines = []
        
        # Topology summary
        lines.append("Topology:")
        for switch in network_state.topology.switches[:5]:  # Limit to first 5
            lines.append(f"  - Switch {switch.id}: {len(switch.ports)} ports, {switch.status}")
        if len(network_state.topology.switches) > 5:
            lines.append(f"  ... and {len(network_state.topology.switches) - 5} more switches")
        
        # Links summary
        lines.append(f"\nLinks: {len(network_state.topology.links)} total")
        for link in network_state.topology.links[:3]:
            bw = f"{link.bandwidth}Mbps" if link.bandwidth else "unknown"
            lines.append(f"  - {link.source_switch}:{link.source_port} <-> {link.destination_switch}:{link.destination_port} ({bw})")
        
        # Metrics
        lines.append(f"\nMetrics:")
        lines.append(f"  - Bandwidth utilization: {network_state.metrics.bandwidth.utilization_percentage:.1f}%")
        lines.append(f"  - Average latency: {network_state.metrics.latency.average_latency:.2f}ms")
        lines.append(f"  - CPU utilization: {network_state.metrics.utilization.cpu_utilization:.1f}%")
        
        # Anomalies
        if network_state.anomalies:
            lines.append(f"\nActive Anomalies: {len(network_state.anomalies)}")
            for anomaly in network_state.anomalies[:3]:
                lines.append(f"  - {anomaly.type.value} ({anomaly.severity.value}): {anomaly.description}")
        
        return "\n".join(lines)
    
    def _format_network_context_for_anomaly(
        self,
        network_state: NetworkState,
        anomaly: Anomaly
    ) -> str:
        """Format network context relevant to an anomaly.
        
        Args:
            network_state: Current network state
            anomaly: The anomaly being analyzed
            
        Returns:
            Formatted context string
        """
        lines = []
        
        # Get affected resources details
        affected_switches = [
            s for s in network_state.topology.switches
            if s.id in anomaly.affected_resources
        ]
        affected_links = [
            l for l in network_state.topology.links
            if l.id in anomaly.affected_resources
        ]
        
        if affected_switches:
            lines.append("Affected Switches:")
            for switch in affected_switches:
                lines.append(f"  - {switch.id}: {switch.status}, {len(switch.ports)} ports")
        
        if affected_links:
            lines.append("Affected Links:")
            for link in affected_links:
                bw = f"{link.bandwidth}Mbps" if link.bandwidth else "unknown"
                lines.append(f"  - {link.id}: {link.status}, bandwidth: {bw}")
        
        # Add relevant metrics
        lines.append("\nCurrent Metrics:")
        lines.append(f"  - Bandwidth utilization: {network_state.metrics.bandwidth.utilization_percentage:.1f}%")
        lines.append(f"  - Average latency: {network_state.metrics.latency.average_latency:.2f}ms")
        lines.append(f"  - Max latency: {network_state.metrics.latency.max_latency:.2f}ms")
        
        # Add anomaly-specific metrics
        if anomaly.metrics:
            lines.append("\nAnomaly Metrics:")
            for key, value in anomaly.metrics.items():
                lines.append(f"  - {key}: {value}")
        
        return "\n".join(lines)
    
    def _format_available_resources(self, network_state: NetworkState) -> str:
        """Format available network resources.
        
        Args:
            network_state: Current network state
            
        Returns:
            Formatted resources string
        """
        lines = []
        
        # Active switches
        active_switches = [s for s in network_state.topology.switches if s.status == "active"]
        lines.append(f"Active Switches ({len(active_switches)}):")
        for switch in active_switches[:10]:
            lines.append(f"  - {switch.id} ({switch.name})")
        
        # Active hosts
        active_hosts = [h for h in network_state.topology.hosts if h.status == "active"]
        lines.append(f"\nActive Hosts ({len(active_hosts)}):")
        for host in active_hosts[:10]:
            ip = host.ip_address or "no IP"
            lines.append(f"  - {host.id} ({ip})")
        
        # Available bandwidth
        total_bw = sum(link.bandwidth or 0 for link in network_state.topology.links)
        used_bw = network_state.metrics.bandwidth.used_bandwidth
        available_bw = network_state.metrics.bandwidth.available_bandwidth
        lines.append(f"\nBandwidth: {available_bw}/{total_bw}Mbps available")
        
        return "\n".join(lines)
    
    def _format_network_state_summary(self, network_state: NetworkState) -> str:
        """Format network state summary for validation.
        
        Args:
            network_state: Network state to summarize
            
        Returns:
            Formatted summary string
        """
        lines = []
        
        lines.append(f"Switches: {len(network_state.topology.switches)}")
        lines.append(f"Links: {len(network_state.topology.links)}")
        lines.append(f"Hosts: {len(network_state.topology.hosts)}")
        lines.append(f"Active Flows: {len(network_state.flows)}")
        lines.append(f"Bandwidth Utilization: {network_state.metrics.bandwidth.utilization_percentage:.1f}%")
        lines.append(f"CPU Utilization: {network_state.metrics.utilization.cpu_utilization:.1f}%")
        
        if network_state.anomalies:
            lines.append(f"Active Anomalies: {len(network_state.anomalies)}")
        
        return "\n".join(lines)
    
    def optimize_prompt_for_tokens(
        self,
        prompt: str,
        max_tokens: int = 4000
    ) -> str:
        """Optimize prompt to fit within token budget.
        
        Args:
            prompt: Original prompt text
            max_tokens: Maximum token budget (approximate)
            
        Returns:
            Optimized prompt
        """
        # Rough estimate: 1 token ≈ 4 characters
        estimated_tokens = len(prompt) // 4
        
        if estimated_tokens <= max_tokens:
            return prompt
        
        # Calculate reduction needed
        target_length = max_tokens * 4
        reduction_ratio = target_length / len(prompt)
        
        logger.warning(
            f"Prompt too long ({estimated_tokens} tokens), "
            f"reducing to ~{max_tokens} tokens"
        )
        
        # Simple truncation strategy - in production, use smarter summarization
        lines = prompt.split("\n")
        optimized_lines = []
        current_length = 0
        
        for line in lines:
            if current_length + len(line) < target_length:
                optimized_lines.append(line)
                current_length += len(line) + 1
            else:
                optimized_lines.append("... (content truncated for token efficiency)")
                break
        
        return "\n".join(optimized_lines)
