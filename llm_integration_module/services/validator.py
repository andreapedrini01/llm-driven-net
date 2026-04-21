"""Action validation and safety checking service."""

from typing import Dict, List, Optional, Set, Any
from datetime import datetime
import logging
import copy

from llm_integration_module.models.actions import (
    NetworkAction,
    ActionSequence,
    ActionType,
    ValidationResult,
    SafetyReport,
    SimulationResult,
    ImpactAssessment
)
from llm_integration_module.models.network import NetworkState, AnomalySeverity


logger = logging.getLogger(__name__)


class ActionValidator:
    """Service for validating network actions and assessing safety."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._validation_rules = self._initialize_validation_rules()
        self._safety_thresholds = self._initialize_safety_thresholds()
    
    def _initialize_validation_rules(self) -> Dict[ActionType, Dict[str, Any]]:
        """Initialize validation rules for each action type."""
        return {
            ActionType.FLOW_MOD: {
                "required_params": ["match", "actions"],
                "optional_params": ["priority", "idle_timeout", "hard_timeout"],
                "valid_match_fields": [
                    "in_port", "eth_src", "eth_dst", "eth_type",
                    "ip_src", "ip_dst", "ip_proto",
                    "tcp_src", "tcp_dst", "udp_src", "udp_dst"
                ],
                "valid_action_types": [
                    "output", "drop", "set_field", "push_vlan", "pop_vlan"
                ]
            },
            ActionType.SLICE_CREATE: {
                "required_params": ["slice_name", "resources"],
                "optional_params": ["policies", "sla"],
                "resource_fields": ["bandwidth", "switches", "paths"]
            },
            ActionType.SLICE_MODIFY: {
                "required_params": [],
                "optional_params": ["slice_name", "resources", "policies", "sla", "bandwidth", "config_data"],
                "resource_fields": ["bandwidth", "switches", "paths"]
            },
            ActionType.SLICE_DELETE: {
                "required_params": [],
                "optional_params": ["slice_name", "config_data"],
            },
            ActionType.LOAD_BALANCE: {
                "required_params": [],
                "optional_params": ["backends", "virtual_ip", "config_data"],
            },
            ActionType.CONFIG_CHANGE: {
                "required_params": ["config_type", "config_data"],
                "optional_params": ["backup", "validate_before_apply"],
                "valid_config_types": [
                    "switch_config", "port_config", "qos_config",
                    "slice_config", "flow_table_config"
                ]
            }
        }
    
    def _initialize_safety_thresholds(self) -> Dict[str, Any]:
        """Initialize safety thresholds for risk assessment."""
        return {
            "max_affected_switches": 10,
            "max_affected_hosts": 50,
            "max_bandwidth_change_percent": 50,
            "max_flow_modifications": 100,
            "critical_resource_utilization": 90.0,
            "high_risk_utilization": 75.0,
            "medium_risk_utilization": 50.0
        }
    
    def validate_actions(self, sequence: ActionSequence) -> ValidationResult:
        """
        Validate an action sequence for syntax and semantic correctness.
        
        Args:
            sequence: The action sequence to validate
            
        Returns:
            ValidationResult with errors, warnings, and suggestions
        """
        self.logger.info(f"Validating action sequence {sequence.id}")
        
        errors = []
        warnings = []
        suggestions = []
        
        # Validate sequence structure
        if not sequence.actions:
            errors.append("Action sequence is empty")
            return ValidationResult(is_valid=False, errors=errors)
        
        # Validate each action
        for action in sequence.actions:
            action_validation = self._validate_single_action(action)
            errors.extend(action_validation["errors"])
            warnings.extend(action_validation["warnings"])
            suggestions.extend(action_validation["suggestions"])
        
        # Validate action sequence integrity
        integrity_validation = self._validate_sequence_integrity(sequence)
        errors.extend(integrity_validation["errors"])
        warnings.extend(integrity_validation["warnings"])
        suggestions.extend(integrity_validation["suggestions"])
        
        # Check for duplicate action IDs
        action_ids = [action.id for action in sequence.actions]
        if len(action_ids) != len(set(action_ids)):
            errors.append("Duplicate action IDs found in sequence")
        
        # Validate dependencies
        dependency_validation = self._validate_dependencies(sequence)
        errors.extend(dependency_validation["errors"])
        warnings.extend(dependency_validation["warnings"])
        
        is_valid = len(errors) == 0
        
        self.logger.info(
            f"Validation complete: valid={is_valid}, "
            f"errors={len(errors)}, warnings={len(warnings)}"
        )
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )
    
    def _validate_single_action(self, action: NetworkAction) -> Dict[str, List[str]]:
        """Validate a single network action."""
        errors = []
        warnings = []
        suggestions = []
        
        # Get validation rules for action type
        rules = self._validation_rules.get(action.type)
        if not rules:
            errors.append(f"Unknown action type: {action.type}")
            return {"errors": errors, "warnings": warnings, "suggestions": suggestions}
        
        # Check required parameters
        for param in rules.get("required_params", []):
            if param not in action.parameters:
                errors.append(f"Action {action.id}: Missing required parameter '{param}'")
        
        # Validate action-specific parameters
        if action.type == ActionType.FLOW_MOD:
            flow_validation = self._validate_flow_mod(action, rules)
            errors.extend(flow_validation["errors"])
            warnings.extend(flow_validation["warnings"])
            suggestions.extend(flow_validation["suggestions"])
        
        elif action.type == ActionType.SLICE_CREATE:
            slice_validation = self._validate_slice_create(action, rules)
            errors.extend(slice_validation["errors"])
            warnings.extend(slice_validation["warnings"])
            suggestions.extend(slice_validation["suggestions"])
        
        elif action.type == ActionType.SLICE_MODIFY:
            slice_validation = self._validate_slice_modify(action, rules)
            errors.extend(slice_validation["errors"])
            warnings.extend(slice_validation["warnings"])
            suggestions.extend(slice_validation["suggestions"])
        
        elif action.type in (ActionType.SLICE_DELETE, ActionType.LOAD_BALANCE):
            # Basic validation only — no special rules needed
            pass
        
        elif action.type == ActionType.CONFIG_CHANGE:
            config_validation = self._validate_config_change(action, rules)
            errors.extend(config_validation["errors"])
            warnings.extend(config_validation["warnings"])
            suggestions.extend(config_validation["suggestions"])
        
        # Validate priority and timeout
        if action.priority < 0 or action.priority > 65535:
            errors.append(f"Action {action.id}: Invalid priority {action.priority}")
        
        if action.timeout < 1 or action.timeout > 3600:
            errors.append(f"Action {action.id}: Invalid timeout {action.timeout}")
        
        return {"errors": errors, "warnings": warnings, "suggestions": suggestions}
    
    def _validate_flow_mod(
        self,
        action: NetworkAction,
        rules: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """Validate flow modification action."""
        errors = []
        warnings = []
        suggestions = []
        
        match_fields = action.parameters.get("match", {})
        flow_actions = action.parameters.get("actions", [])
        
        # Validate match fields
        valid_match_fields = rules.get("valid_match_fields", [])
        for field in match_fields:
            if field not in valid_match_fields:
                warnings.append(
                    f"Action {action.id}: Unknown match field '{field}'"
                )
        
        # Check for empty match (matches all traffic)
        if not match_fields:
            warnings.append(
                f"Action {action.id}: Empty match criteria will affect all traffic"
            )
            suggestions.append(
                f"Action {action.id}: Consider adding specific match criteria"
            )
        
        # Validate flow actions
        valid_action_types = rules.get("valid_action_types", [])
        for flow_action in flow_actions:
            if isinstance(flow_action, dict):
                action_type = flow_action.get("type")
                if action_type and action_type not in valid_action_types:
                    warnings.append(
                        f"Action {action.id}: Unknown flow action type '{action_type}'"
                    )
        
        # Check for drop action without specific match
        if any(a.get("type") == "drop" for a in flow_actions if isinstance(a, dict)):
            if not match_fields or len(match_fields) < 2:
                warnings.append(
                    f"Action {action.id}: Drop action with broad match criteria"
                )
        
        return {"errors": errors, "warnings": warnings, "suggestions": suggestions}
    
    def _validate_slice_create(
        self,
        action: NetworkAction,
        rules: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """Validate slice creation action."""
        errors = []
        warnings = []
        suggestions = []
        
        slice_name = action.parameters.get("slice_name")
        resources = action.parameters.get("resources", {})
        
        # Validate slice name
        if not slice_name or not isinstance(slice_name, str):
            errors.append(f"Action {action.id}: Invalid slice name")
        elif len(slice_name) < 3:
            warnings.append(f"Action {action.id}: Slice name is very short")
        
        # Validate resources
        resource_fields = rules.get("resource_fields", [])
        if not resources:
            errors.append(f"Action {action.id}: No resources specified for slice")
        elif isinstance(resources, list):
            # Resources provided as a list of switch names — valid format
            if len(resources) > self._safety_thresholds["max_affected_switches"]:
                warnings.append(
                    f"Action {action.id}: Slice affects many switches ({len(resources)})"
                )
        else:
            # Check bandwidth
            bandwidth = resources.get("bandwidth")
            if bandwidth is not None:
                if not isinstance(bandwidth, (int, float)) or bandwidth <= 0:
                    errors.append(f"Action {action.id}: Invalid bandwidth value")
                elif bandwidth > 10000:  # 10 Gbps
                    warnings.append(
                        f"Action {action.id}: Very high bandwidth requested ({bandwidth} Mbps)"
                    )
            
            # Check switches
            switches = resources.get("switches", [])
            if not switches:
                warnings.append(f"Action {action.id}: No switches specified for slice")
            elif len(switches) > self._safety_thresholds["max_affected_switches"]:
                warnings.append(
                    f"Action {action.id}: Slice affects many switches ({len(switches)})"
                )
            
            # Check paths
            paths = resources.get("paths", [])
            if paths:
                for i, path in enumerate(paths):
                    if not isinstance(path, dict):
                        errors.append(
                            f"Action {action.id}: Invalid path format at index {i}"
                        )
                    elif "switches" not in path:
                        errors.append(
                            f"Action {action.id}: Path {i} missing switches"
                        )
        
        # Check SLA if provided
        sla = action.parameters.get("sla")
        if sla:
            if not isinstance(sla, dict):
                errors.append(f"Action {action.id}: Invalid SLA format")
            else:
                # Validate SLA parameters
                if "latency" in sla and sla["latency"] < 0:
                    errors.append(f"Action {action.id}: Negative latency in SLA")
                if "availability" in sla:
                    avail = sla["availability"]
                    if not (0 <= avail <= 100):
                        errors.append(
                            f"Action {action.id}: Invalid availability percentage"
                        )
        
        return {"errors": errors, "warnings": warnings, "suggestions": suggestions}
    
    def _validate_slice_modify(
        self,
        action: NetworkAction,
        rules: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """Validate slice modification action."""
        errors = []
        warnings = []
        suggestions = []
        
        slice_name = action.parameters.get("slice_name")
        
        # Validate slice name (optional — slice can be identified by hosts)
        if slice_name and not isinstance(slice_name, str):
            errors.append(f"Action {action.id}: Invalid slice name")
        
        # Check that at least one modification is specified
        has_modification = any(
            key in action.parameters
            for key in ["resources", "policies", "sla", "bandwidth", "config_data"]
        )
        
        if not has_modification:
            warnings.append(
                f"Action {action.id}: No modifications specified for slice"
            )
            suggestions.append(
                f"Action {action.id}: Specify resources, policies, or SLA to modify"
            )
        
        # Validate resources if provided (similar to slice_create)
        resources = action.parameters.get("resources")
        if resources and isinstance(resources, dict):
            bandwidth = resources.get("bandwidth")
            if bandwidth is not None and bandwidth <= 0:
                errors.append(f"Action {action.id}: Invalid bandwidth value")
        
        # Also check bandwidth at top level
        bandwidth = action.parameters.get("bandwidth")
        if bandwidth is not None and isinstance(bandwidth, (int, float)) and bandwidth <= 0:
            errors.append(f"Action {action.id}: Invalid bandwidth value")
        
        return {"errors": errors, "warnings": warnings, "suggestions": suggestions}
    
    def _validate_config_change(
        self,
        action: NetworkAction,
        rules: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """Validate configuration change action."""
        errors = []
        warnings = []
        suggestions = []
        
        config_type = action.parameters.get("config_type")
        config_data = action.parameters.get("config_data")
        
        # Validate config type
        valid_config_types = rules.get("valid_config_types", [])
        if config_type not in valid_config_types:
            warnings.append(
                f"Action {action.id}: Unknown config type '{config_type}'"
            )
        
        # Validate config data
        if not config_data:
            errors.append(f"Action {action.id}: Empty configuration data")
        elif not isinstance(config_data, dict):
            errors.append(f"Action {action.id}: Configuration data must be a dictionary")
        
        # Suggest backup for critical config changes
        if not action.parameters.get("backup"):
            suggestions.append(
                f"Action {action.id}: Consider enabling backup before config change"
            )
        
        # Suggest validation for config changes
        if not action.parameters.get("validate_before_apply"):
            suggestions.append(
                f"Action {action.id}: Consider enabling pre-validation"
            )
        
        return {"errors": errors, "warnings": warnings, "suggestions": suggestions}
    
    def _validate_sequence_integrity(
        self,
        sequence: ActionSequence
    ) -> Dict[str, List[str]]:
        """Validate action sequence integrity."""
        errors = []
        warnings = []
        suggestions = []
        
        # Check estimated duration
        actual_duration = sum(
            action.estimate_execution_time() for action in sequence.actions
        )
        
        if sequence.estimated_duration <= 0:
            errors.append("Estimated duration must be positive")
        elif abs(sequence.estimated_duration - actual_duration) > actual_duration * 0.5:
            warnings.append(
                f"Estimated duration ({sequence.estimated_duration}s) differs "
                f"significantly from sum of action times ({actual_duration}s)"
            )
        
        # Check rollback plan
        if not sequence.rollback_plan:
            suggestions.append("Consider adding a rollback plan for safer execution")
        else:
            # Validate rollback covers all actions
            action_targets = {action.target for action in sequence.actions}
            rollback_targets = {action.target for action in sequence.rollback_plan}
            
            uncovered = action_targets - rollback_targets
            if uncovered:
                warnings.append(
                    f"Rollback plan doesn't cover targets: {uncovered}"
                )
        
        # Check for very long sequences
        if len(sequence.actions) > 50:
            warnings.append(
                f"Very long action sequence ({len(sequence.actions)} actions)"
            )
            suggestions.append("Consider breaking into smaller sequences")
        
        if sequence.estimated_duration > 600:  # 10 minutes
            warnings.append(
                f"Long execution time ({sequence.estimated_duration}s)"
            )
            suggestions.append("Consider breaking into smaller sequences")
        
        return {"errors": errors, "warnings": warnings, "suggestions": suggestions}
    
    def _validate_dependencies(
        self,
        sequence: ActionSequence
    ) -> Dict[str, List[str]]:
        """Validate action dependencies."""
        errors = []
        warnings = []
        
        action_ids = {action.id for action in sequence.actions}
        
        # Check that dependencies reference valid actions
        for dep in sequence.dependencies:
            if dep not in action_ids:
                # Dependency might be external (from another sequence)
                warnings.append(
                    f"Dependency '{dep}' not found in current sequence (may be external)"
                )
        
        # Check for circular dependencies (simplified check)
        # A full check would require building a dependency graph
        if len(sequence.dependencies) > len(sequence.actions):
            warnings.append("More dependencies than actions - possible circular dependency")
        
        return {"errors": errors, "warnings": warnings}
    
    def check_safety(
        self,
        sequence: ActionSequence,
        network_state: Optional[NetworkState] = None
    ) -> SafetyReport:
        """
        Perform safety checks on an action sequence.
        
        Args:
            sequence: The action sequence to check
            network_state: Current network state for context
            
        Returns:
            SafetyReport with risk assessment
        """
        self.logger.info(f"Performing safety check on sequence {sequence.id}")
        
        potential_impacts = []
        mitigation_strategies = []
        
        # Analyze affected resources
        affected_switches = set()
        affected_hosts = set()
        total_bandwidth_change = 0
        flow_mod_count = 0
        
        for action in sequence.actions:
            if action.type == ActionType.FLOW_MOD:
                flow_mod_count += 1
                affected_switches.add(action.target)
            
            elif action.type in [ActionType.SLICE_CREATE, ActionType.SLICE_MODIFY]:
                resources = action.parameters.get("resources", {})
                switches = resources.get("switches", [])
                affected_switches.update(switches)
                
                bandwidth = resources.get("bandwidth", 0)
                total_bandwidth_change += bandwidth
            
            elif action.type == ActionType.CONFIG_CHANGE:
                affected_switches.add(action.target)
        
        # Assess risk level
        risk_factors = []
        
        # Check number of affected switches
        if len(affected_switches) > self._safety_thresholds["max_affected_switches"]:
            risk_factors.append("high_switch_count")
            potential_impacts.append(
                f"Affects {len(affected_switches)} switches (threshold: "
                f"{self._safety_thresholds['max_affected_switches']})"
            )
            mitigation_strategies.append(
                "Consider breaking into smaller sequences affecting fewer switches"
            )
        
        # Check flow modification count
        if flow_mod_count > self._safety_thresholds["max_flow_modifications"]:
            risk_factors.append("high_flow_mod_count")
            potential_impacts.append(
                f"Modifies {flow_mod_count} flows (threshold: "
                f"{self._safety_thresholds['max_flow_modifications']})"
            )
            mitigation_strategies.append(
                "Consider batching flow modifications or using more specific rules"
            )
        
        # Check bandwidth changes
        if network_state:
            total_capacity = network_state.metrics.bandwidth.total_capacity
            if total_capacity > 0:
                bandwidth_change_percent = (total_bandwidth_change / total_capacity) * 100
                
                if bandwidth_change_percent > self._safety_thresholds["max_bandwidth_change_percent"]:
                    risk_factors.append("high_bandwidth_change")
                    potential_impacts.append(
                        f"Changes {bandwidth_change_percent:.1f}% of total bandwidth"
                    )
                    mitigation_strategies.append(
                        "Ensure sufficient bandwidth is available before execution"
                    )
            
            # Check resource utilization
            for switch_id in affected_switches:
                utilization = network_state.get_resource_utilization(switch_id)
                if utilization and utilization > self._safety_thresholds["critical_resource_utilization"]:
                    risk_factors.append("critical_utilization")
                    potential_impacts.append(
                        f"Switch {switch_id} at critical utilization ({utilization:.1f}%)"
                    )
                    mitigation_strategies.append(
                        f"Consider load balancing or reducing load on {switch_id}"
                    )
            
            # Check for active anomalies
            if network_state.anomalies:
                critical_anomalies = [
                    a for a in network_state.anomalies
                    if a.severity == AnomalySeverity.CRITICAL and not a.resolved_at
                ]
                if critical_anomalies:
                    risk_factors.append("active_anomalies")
                    potential_impacts.append(
                        f"{len(critical_anomalies)} critical anomalies active"
                    )
                    mitigation_strategies.append(
                        "Resolve critical anomalies before executing actions"
                    )
        
        # Check for actions without rollback
        if not sequence.rollback_plan:
            risk_factors.append("no_rollback")
            potential_impacts.append("No rollback plan available")
            mitigation_strategies.append("Create rollback plan before execution")
        
        # Determine overall risk level
        risk_level = self._calculate_risk_level(risk_factors, sequence, network_state)
        is_safe = risk_level in ["low", "medium"]
        
        self.logger.info(
            f"Safety check complete: risk_level={risk_level}, "
            f"is_safe={is_safe}, impacts={len(potential_impacts)}"
        )
        
        return SafetyReport(
            is_safe=is_safe,
            risk_level=risk_level,
            potential_impacts=potential_impacts,
            mitigation_strategies=mitigation_strategies
        )
    
    def _calculate_risk_level(
        self,
        risk_factors: List[str],
        sequence: ActionSequence,
        network_state: Optional[NetworkState]
    ) -> str:
        """Calculate overall risk level based on risk factors."""
        
        # Critical risk factors
        critical_factors = ["critical_utilization", "active_anomalies"]
        if any(factor in risk_factors for factor in critical_factors):
            return "critical"
        
        # High risk factors
        high_factors = ["high_switch_count", "high_flow_mod_count", "high_bandwidth_change"]
        high_risk_count = sum(1 for factor in high_factors if factor in risk_factors)
        
        if high_risk_count >= 2:
            return "high"
        elif high_risk_count == 1:
            return "medium"
        
        # Check for no rollback with many actions
        if "no_rollback" in risk_factors and len(sequence.actions) > 10:
            return "medium"
        
        # Default to low risk
        return "low"
    
    def simulate_execution(
        self,
        sequence: ActionSequence,
        network_state: NetworkState
    ) -> SimulationResult:
        """
        Simulate action execution to predict outcomes.
        
        Args:
            sequence: The action sequence to simulate
            network_state: Current network state
            
        Returns:
            SimulationResult with predicted outcomes
        """
        self.logger.info(f"Simulating execution of sequence {sequence.id}")
        
        # Create a copy of network state for simulation
        simulated_state = copy.deepcopy(network_state)
        
        predicted_outcomes = {}
        performance_impact = {}
        resource_changes = {}
        
        success = True
        
        try:
            # Simulate each action
            for action in sequence.actions:
                action_result = self._simulate_single_action(action, simulated_state)
                
                if not action_result["success"]:
                    success = False
                    predicted_outcomes[action.id] = action_result
                    break
                
                predicted_outcomes[action.id] = action_result
                
                # Update simulated state based on action
                self._apply_action_to_state(action, simulated_state)
            
            # Calculate performance impact
            performance_impact = self._calculate_performance_impact(
                network_state,
                simulated_state
            )
            
            # Calculate resource changes
            resource_changes = self._calculate_resource_changes(
                network_state,
                simulated_state
            )
            
        except Exception as e:
            self.logger.error(f"Simulation failed: {e}")
            success = False
            predicted_outcomes["error"] = str(e)
        
        self.logger.info(f"Simulation complete: success={success}")
        
        return SimulationResult(
            success=success,
            predicted_outcomes=predicted_outcomes,
            performance_impact=performance_impact,
            resource_changes=resource_changes
        )
    
    def _simulate_single_action(
        self,
        action: NetworkAction,
        state: NetworkState
    ) -> Dict[str, Any]:
        """Simulate a single action execution."""
        
        result = {
            "success": True,
            "action_id": action.id,
            "action_type": action.type.value,
            "effects": []
        }
        
        # Check if target exists
        if not state.is_resource_available(action.target):
            result["success"] = False
            result["error"] = f"Target resource {action.target} not available"
            return result
        
        # Simulate based on action type
        if action.type == ActionType.FLOW_MOD:
            result["effects"].append(f"Flow modified on {action.target}")
            result["estimated_time"] = action.estimate_execution_time()
        
        elif action.type == ActionType.SLICE_CREATE:
            slice_name = action.parameters.get("slice_name")
            resources = action.parameters.get("resources", {})
            bandwidth = resources.get("bandwidth", 0)
            
            result["effects"].append(f"Slice '{slice_name}' created")
            result["effects"].append(f"Bandwidth allocated: {bandwidth} Mbps")
            result["estimated_time"] = action.estimate_execution_time()
        
        elif action.type == ActionType.SLICE_MODIFY:
            slice_name = action.parameters.get("slice_name")
            result["effects"].append(f"Slice '{slice_name}' modified")
            result["estimated_time"] = action.estimate_execution_time()
        
        elif action.type == ActionType.CONFIG_CHANGE:
            config_type = action.parameters.get("config_type")
            result["effects"].append(f"Configuration changed: {config_type}")
            result["estimated_time"] = action.estimate_execution_time()
        
        return result
    
    def _apply_action_to_state(self, action: NetworkAction, state: NetworkState) -> None:
        """Apply action effects to simulated state."""
        
        # This is a simplified simulation
        # In a real implementation, this would modify the state based on action type
        
        if action.type == ActionType.FLOW_MOD:
            # Would add/modify flows in state
            pass
        
        elif action.type == ActionType.SLICE_CREATE:
            # Would add slice to state
            pass
        
        elif action.type == ActionType.SLICE_MODIFY:
            # Would modify existing slice
            pass
        
        elif action.type == ActionType.CONFIG_CHANGE:
            # Would apply configuration changes
            pass
    
    def _calculate_performance_impact(
        self,
        original_state: NetworkState,
        simulated_state: NetworkState
    ) -> Dict[str, float]:
        """Calculate performance impact of actions."""
        
        impact = {}
        
        # Calculate bandwidth impact
        original_bandwidth = original_state.metrics.bandwidth.utilization_percentage
        simulated_bandwidth = simulated_state.metrics.bandwidth.utilization_percentage
        impact["bandwidth_utilization_change"] = simulated_bandwidth - original_bandwidth
        
        # Calculate latency impact (simplified)
        original_latency = original_state.metrics.latency.average_latency
        simulated_latency = simulated_state.metrics.latency.average_latency
        impact["latency_change_ms"] = simulated_latency - original_latency
        
        # Calculate CPU impact
        original_cpu = original_state.metrics.utilization.cpu_utilization
        simulated_cpu = simulated_state.metrics.utilization.cpu_utilization
        impact["cpu_utilization_change"] = simulated_cpu - original_cpu
        
        return impact
    
    def _calculate_resource_changes(
        self,
        original_state: NetworkState,
        simulated_state: NetworkState
    ) -> Dict[str, Any]:
        """Calculate resource changes from actions."""
        
        changes = {}
        
        # Calculate flow count change
        original_flows = len(original_state.flows)
        simulated_flows = len(simulated_state.flows)
        changes["flow_count_change"] = simulated_flows - original_flows
        
        # Calculate bandwidth allocation change
        original_used = original_state.metrics.bandwidth.used_bandwidth
        simulated_used = simulated_state.metrics.bandwidth.used_bandwidth
        changes["bandwidth_allocation_change"] = simulated_used - original_used
        
        # Calculate available bandwidth change
        original_available = original_state.metrics.bandwidth.available_bandwidth
        simulated_available = simulated_state.metrics.bandwidth.available_bandwidth
        changes["available_bandwidth_change"] = simulated_available - original_available
        
        return changes



class RollbackPlanGenerator:
    """Service for generating and validating rollback plans."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_rollback_plan(
        self,
        sequence: ActionSequence,
        network_state: Optional[NetworkState] = None
    ) -> List[NetworkAction]:
        """
        Generate automatic rollback plan for an action sequence.
        
        Args:
            sequence: The action sequence to create rollback for
            network_state: Current network state for context
            
        Returns:
            List of rollback actions in reverse order
        """
        self.logger.info(f"Generating rollback plan for sequence {sequence.id}")
        
        rollback_actions = []
        
        # Process actions in reverse order
        for i, action in enumerate(reversed(sequence.actions)):
            rollback_action = self._create_rollback_action(
                action,
                len(sequence.actions) - i - 1,
                network_state
            )
            
            if rollback_action:
                rollback_actions.append(rollback_action)
            else:
                self.logger.warning(
                    f"Could not create rollback for action {action.id}"
                )
        
        self.logger.info(
            f"Generated {len(rollback_actions)} rollback actions "
            f"for {len(sequence.actions)} original actions"
        )
        
        return rollback_actions
    
    def _create_rollback_action(
        self,
        action: NetworkAction,
        index: int,
        network_state: Optional[NetworkState] = None
    ) -> Optional[NetworkAction]:
        """Create a rollback action for a given action."""
        
        if action.type == ActionType.FLOW_MOD:
            return self._create_flow_mod_rollback(action, index)
        
        elif action.type == ActionType.SLICE_CREATE:
            return self._create_slice_create_rollback(action, index)
        
        elif action.type == ActionType.SLICE_MODIFY:
            return self._create_slice_modify_rollback(action, index, network_state)
        
        elif action.type == ActionType.CONFIG_CHANGE:
            return self._create_config_change_rollback(action, index, network_state)
        
        return None
    
    def _create_flow_mod_rollback(
        self,
        action: NetworkAction,
        index: int
    ) -> NetworkAction:
        """Create rollback action for flow modification."""
        
        # Rollback by deleting the flow
        rollback_params = {
            "command": "delete",
            "match": action.parameters.get("match", {})
        }
        
        # If the original action had a specific flow ID, use it
        if "flow_id" in action.parameters:
            rollback_params["flow_id"] = action.parameters["flow_id"]
        
        return NetworkAction(
            id=f"rollback_{action.id}_{index}",
            type=ActionType.FLOW_MOD,
            target=action.target,
            parameters=rollback_params,
            priority=action.priority,
            timeout=action.timeout,
            description=f"Rollback flow modification for {action.id}"
        )
    
    def _create_slice_create_rollback(
        self,
        action: NetworkAction,
        index: int
    ) -> NetworkAction:
        """Create rollback action for slice creation."""
        
        slice_name = action.parameters.get("slice_name")
        
        # Rollback by deleting the slice
        rollback_params = {
            "config_type": "slice_delete",
            "slice_name": slice_name,
            "config_data": {
                "slice_name": slice_name,
                "force_delete": True
            }
        }
        
        return NetworkAction(
            id=f"rollback_{action.id}_{index}",
            type=ActionType.CONFIG_CHANGE,
            target=action.target,
            parameters=rollback_params,
            priority=action.priority,
            timeout=action.timeout * 2,  # Deletion might take longer
            description=f"Rollback slice creation for {action.id}"
        )
    
    def _create_slice_modify_rollback(
        self,
        action: NetworkAction,
        index: int,
        network_state: Optional[NetworkState] = None
    ) -> Optional[NetworkAction]:
        """Create rollback action for slice modification."""
        
        slice_name = action.parameters.get("slice_name")
        
        # Ideally, we would restore the original slice configuration
        # For now, we'll create a generic rollback that reverts changes
        
        rollback_params = {
            "slice_name": slice_name,
            "restore_previous": True
        }
        
        # If we have network state, we could capture the original config
        if network_state:
            # In a real implementation, we would look up the original slice config
            # from network_state and include it in the rollback
            pass
        
        return NetworkAction(
            id=f"rollback_{action.id}_{index}",
            type=ActionType.SLICE_MODIFY,
            target=action.target,
            parameters=rollback_params,
            priority=action.priority,
            timeout=action.timeout,
            description=f"Rollback slice modification for {action.id}"
        )
    
    def _create_config_change_rollback(
        self,
        action: NetworkAction,
        index: int,
        network_state: Optional[NetworkState] = None
    ) -> Optional[NetworkAction]:
        """Create rollback action for configuration change."""
        
        config_type = action.parameters.get("config_type")
        
        # Check if backup was enabled
        if action.parameters.get("backup"):
            # Rollback by restoring from backup
            rollback_params = {
                "config_type": f"{config_type}_restore",
                "config_data": {
                    "restore_from_backup": True,
                    "backup_id": f"{action.id}_backup"
                }
            }
            
            return NetworkAction(
                id=f"rollback_{action.id}_{index}",
                type=ActionType.CONFIG_CHANGE,
                target=action.target,
                parameters=rollback_params,
                priority=action.priority,
                timeout=action.timeout,
                description=f"Rollback config change for {action.id}"
            )
        
        # If no backup, we can't safely rollback
        self.logger.warning(
            f"Cannot create rollback for config change {action.id} without backup"
        )
        return None
    
    def validate_rollback_plan(
        self,
        original_sequence: ActionSequence,
        rollback_plan: List[NetworkAction]
    ) -> ValidationResult:
        """
        Validate a rollback plan for completeness and correctness.
        
        Args:
            original_sequence: The original action sequence
            rollback_plan: The proposed rollback plan
            
        Returns:
            ValidationResult with errors, warnings, and suggestions
        """
        self.logger.info(
            f"Validating rollback plan for sequence {original_sequence.id}"
        )
        
        errors = []
        warnings = []
        suggestions = []
        
        # Check if rollback plan is empty
        if not rollback_plan:
            errors.append("Rollback plan is empty")
            return ValidationResult(is_valid=False, errors=errors)
        
        # Check coverage: rollback should cover all original actions
        original_targets = {action.target for action in original_sequence.actions}
        rollback_targets = {action.target for action in rollback_plan}
        
        uncovered_targets = original_targets - rollback_targets
        if uncovered_targets:
            warnings.append(
                f"Rollback plan doesn't cover targets: {uncovered_targets}"
            )
            suggestions.append(
                "Add rollback actions for all affected targets"
            )
        
        # Check that rollback actions are in reverse order
        # (This is a heuristic check)
        if len(rollback_plan) != len(original_sequence.actions):
            warnings.append(
                f"Rollback plan has {len(rollback_plan)} actions, "
                f"original has {len(original_sequence.actions)}"
            )
        
        # Validate each rollback action
        for action in rollback_plan:
            # Check that rollback action IDs follow naming convention
            if not action.id.startswith("rollback_"):
                warnings.append(
                    f"Rollback action {action.id} doesn't follow naming convention"
                )
            
            # Check that rollback actions have reasonable timeouts
            if action.timeout < 1:
                errors.append(
                    f"Rollback action {action.id} has invalid timeout"
                )
        
        # Check for potential issues in rollback execution
        rollback_conflicts = self._check_rollback_conflicts(rollback_plan)
        if rollback_conflicts:
            warnings.extend(rollback_conflicts)
        
        is_valid = len(errors) == 0
        
        self.logger.info(
            f"Rollback validation complete: valid={is_valid}, "
            f"errors={len(errors)}, warnings={len(warnings)}"
        )
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )
    
    def _check_rollback_conflicts(self, rollback_plan: List[NetworkAction]) -> List[str]:
        """Check for potential conflicts in rollback execution."""
        
        conflicts = []
        
        # Check for duplicate targets
        target_counts = {}
        for action in rollback_plan:
            target_counts[action.target] = target_counts.get(action.target, 0) + 1
        
        for target, count in target_counts.items():
            if count > 1:
                conflicts.append(
                    f"Multiple rollback actions target {target} ({count} actions)"
                )
        
        return conflicts
    
    def test_rollback_plan(
        self,
        rollback_plan: List[NetworkAction],
        network_state: NetworkState
    ) -> Dict[str, Any]:
        """
        Test a rollback plan by simulating its execution.
        
        Args:
            rollback_plan: The rollback plan to test
            network_state: Current network state
            
        Returns:
            Dictionary with test results
        """
        self.logger.info("Testing rollback plan execution")
        
        results = {
            "success": True,
            "actions_tested": len(rollback_plan),
            "actions_passed": 0,
            "actions_failed": 0,
            "failures": []
        }
        
        # Simulate each rollback action
        for action in rollback_plan:
            # Check if target exists
            if not network_state.is_resource_available(action.target):
                results["success"] = False
                results["actions_failed"] += 1
                results["failures"].append({
                    "action_id": action.id,
                    "reason": f"Target {action.target} not available"
                })
                continue
            
            # Validate action parameters
            validation = action.validate_action_parameters()
            if not validation["is_valid"]:
                results["success"] = False
                results["actions_failed"] += 1
                results["failures"].append({
                    "action_id": action.id,
                    "reason": f"Invalid parameters: {validation['issues']}"
                })
                continue
            
            results["actions_passed"] += 1
        
        self.logger.info(
            f"Rollback test complete: success={results['success']}, "
            f"passed={results['actions_passed']}, failed={results['actions_failed']}"
        )
        
        return results
    
    def create_emergency_rollback(
        self,
        sequence: ActionSequence,
        failure_point: Optional[str] = None
    ) -> List[NetworkAction]:
        """
        Create an emergency rollback plan for immediate execution.
        
        This creates a minimal rollback that focuses on critical actions
        up to the failure point.
        
        Args:
            sequence: The action sequence that needs emergency rollback
            failure_point: Action ID where failure occurred (if known)
            
        Returns:
            List of emergency rollback actions
        """
        self.logger.warning(
            f"Creating emergency rollback for sequence {sequence.id}"
        )
        
        emergency_actions = []
        
        # Determine which actions need rollback
        actions_to_rollback = []
        
        if failure_point:
            # Rollback only actions up to failure point
            for action in sequence.actions:
                actions_to_rollback.append(action)
                if action.id == failure_point:
                    break
        else:
            # Rollback all actions
            actions_to_rollback = sequence.actions
        
        # Create emergency rollback actions (simplified, high priority)
        for i, action in enumerate(reversed(actions_to_rollback)):
            emergency_action = self._create_emergency_rollback_action(action, i)
            if emergency_action:
                emergency_actions.append(emergency_action)
        
        self.logger.warning(
            f"Created {len(emergency_actions)} emergency rollback actions"
        )
        
        return emergency_actions
    
    def _create_emergency_rollback_action(
        self,
        action: NetworkAction,
        index: int
    ) -> Optional[NetworkAction]:
        """Create an emergency rollback action with high priority."""
        
        # Create basic rollback action
        rollback = self._create_rollback_action(action, index, None)
        
        if rollback:
            # Increase priority for emergency execution
            rollback.priority = min(65535, action.priority + 1000)
            
            # Reduce timeout for faster execution
            rollback.timeout = max(10, action.timeout // 2)
            
            # Mark as emergency
            rollback.description = f"EMERGENCY: {rollback.description}"
        
        return rollback



class ImpactAssessor:
    """Service for assessing the impact of network actions."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._impact_weights = self._initialize_impact_weights()
    
    def _initialize_impact_weights(self) -> Dict[str, float]:
        """Initialize weights for different impact factors."""
        return {
            "bandwidth_change": 0.3,
            "latency_change": 0.2,
            "affected_resources": 0.25,
            "service_disruption": 0.15,
            "recovery_complexity": 0.1
        }
    
    def assess_impact(
        self,
        sequence: ActionSequence,
        network_state: NetworkState
    ) -> ImpactAssessment:
        """
        Assess the impact of an action sequence on the network.
        
        Args:
            sequence: The action sequence to assess
            network_state: Current network state
            
        Returns:
            ImpactAssessment with detailed impact analysis
        """
        self.logger.info(f"Assessing impact of sequence {sequence.id}")
        
        # Identify affected resources
        affected_resources = self._identify_affected_resources(sequence, network_state)
        
        # Predict performance impact
        performance_impact = self._predict_performance_impact(sequence, network_state)
        
        # Assess service disruption risk
        disruption_risk = self._assess_service_disruption(
            sequence,
            network_state,
            affected_resources
        )
        
        # Estimate recovery time
        recovery_time = self._estimate_recovery_time(sequence, disruption_risk)
        
        self.logger.info(
            f"Impact assessment complete: "
            f"affected_resources={len(affected_resources)}, "
            f"disruption_risk={disruption_risk}, "
            f"recovery_time={recovery_time}s"
        )
        
        return ImpactAssessment(
            affected_resources=affected_resources,
            performance_impact=performance_impact,
            service_disruption_risk=disruption_risk,
            estimated_recovery_time=recovery_time
        )
    
    def _identify_affected_resources(
        self,
        sequence: ActionSequence,
        network_state: NetworkState
    ) -> List[str]:
        """Identify all resources affected by the action sequence."""
        
        affected = set()
        
        for action in sequence.actions:
            # Add direct target
            affected.add(action.target)
            
            # Add resources from parameters
            if action.type in [ActionType.SLICE_CREATE, ActionType.SLICE_MODIFY]:
                resources = action.parameters.get("resources", {})
                
                # Add switches
                switches = resources.get("switches", [])
                affected.update(switches)
                
                # Add paths
                paths = resources.get("paths", [])
                for path in paths:
                    if isinstance(path, dict):
                        path_switches = path.get("switches", [])
                        affected.update(path_switches)
            
            # For flow modifications, check which hosts might be affected
            if action.type == ActionType.FLOW_MOD:
                # Find hosts connected to the target switch
                for host in network_state.topology.hosts:
                    if host.connected_switch == action.target:
                        affected.add(host.id)
                
                # Find links connected to the target switch
                for link in network_state.topology.links:
                    if (link.source_switch == action.target or
                        link.destination_switch == action.target):
                        affected.add(link.id)
        
        return sorted(list(affected))
    
    def _predict_performance_impact(
        self,
        sequence: ActionSequence,
        network_state: NetworkState
    ) -> Dict[str, float]:
        """Predict performance impact of actions."""
        
        impact = {
            "bandwidth_utilization_change": 0.0,
            "latency_change_ms": 0.0,
            "throughput_change_percent": 0.0,
            "packet_loss_risk": 0.0
        }
        
        total_bandwidth_change = 0
        flow_mod_count = 0
        slice_operations = 0
        
        for action in sequence.actions:
            if action.type == ActionType.FLOW_MOD:
                flow_mod_count += 1
                
                # Flow modifications can cause temporary packet loss
                impact["packet_loss_risk"] += 0.5
                
                # May increase latency during installation
                impact["latency_change_ms"] += 2.0
            
            elif action.type in [ActionType.SLICE_CREATE, ActionType.SLICE_MODIFY]:
                slice_operations += 1
                resources = action.parameters.get("resources", {})
                bandwidth = resources.get("bandwidth", 0)
                total_bandwidth_change += bandwidth
                
                # Slice operations can cause temporary disruption
                impact["latency_change_ms"] += 5.0
                impact["packet_loss_risk"] += 1.0
            
            elif action.type == ActionType.CONFIG_CHANGE:
                # Config changes can have significant impact
                impact["latency_change_ms"] += 10.0
                impact["packet_loss_risk"] += 2.0
        
        # Calculate bandwidth utilization change
        if network_state.metrics.bandwidth.total_capacity > 0:
            bandwidth_change_percent = (
                total_bandwidth_change / network_state.metrics.bandwidth.total_capacity
            ) * 100
            impact["bandwidth_utilization_change"] = bandwidth_change_percent
        
        # Estimate throughput change based on flow modifications
        if flow_mod_count > 0:
            # More flow mods = more potential throughput impact
            impact["throughput_change_percent"] = min(
                flow_mod_count * 0.5,
                20.0  # Cap at 20%
            )
        
        # Normalize packet loss risk (0-100 scale)
        impact["packet_loss_risk"] = min(impact["packet_loss_risk"] * 10, 100.0)
        
        return impact
    
    def _assess_service_disruption(
        self,
        sequence: ActionSequence,
        network_state: NetworkState,
        affected_resources: List[str]
    ) -> str:
        """Assess the risk of service disruption."""
        
        disruption_score = 0
        
        # Factor 1: Number of affected resources
        resource_count = len(affected_resources)
        if resource_count > 20:
            disruption_score += 3
        elif resource_count > 10:
            disruption_score += 2
        elif resource_count > 5:
            disruption_score += 1
        
        # Factor 2: Type of actions
        has_config_change = any(
            action.type == ActionType.CONFIG_CHANGE
            for action in sequence.actions
        )
        has_slice_create = any(
            action.type == ActionType.SLICE_CREATE
            for action in sequence.actions
        )
        
        if has_config_change:
            disruption_score += 2
        if has_slice_create:
            disruption_score += 1
        
        # Factor 3: Current network state
        if network_state.anomalies:
            active_anomalies = [
                a for a in network_state.anomalies
                if not a.resolved_at
            ]
            if active_anomalies:
                disruption_score += 2
        
        # Factor 4: Resource utilization
        high_utilization_count = 0
        for resource_id in affected_resources:
            utilization = network_state.get_resource_utilization(resource_id)
            if utilization and utilization > 80:
                high_utilization_count += 1
        
        if high_utilization_count > len(affected_resources) * 0.5:
            disruption_score += 2
        elif high_utilization_count > 0:
            disruption_score += 1
        
        # Factor 5: Rollback availability
        if not sequence.rollback_plan:
            disruption_score += 1
        
        # Map score to risk level
        if disruption_score >= 7:
            return "high"
        elif disruption_score >= 4:
            return "moderate"
        elif disruption_score >= 2:
            return "minimal"
        else:
            return "none"
    
    def _estimate_recovery_time(
        self,
        sequence: ActionSequence,
        disruption_risk: str
    ) -> int:
        """Estimate recovery time in seconds if something goes wrong."""
        
        # Base recovery time on sequence duration
        base_time = sequence.estimated_duration
        
        # Adjust based on disruption risk
        risk_multipliers = {
            "none": 1.0,
            "minimal": 1.5,
            "moderate": 2.0,
            "high": 3.0
        }
        
        multiplier = risk_multipliers.get(disruption_risk, 2.0)
        
        # Add time for rollback if available
        if sequence.rollback_plan:
            rollback_time = sum(
                action.estimate_execution_time()
                for action in sequence.rollback_plan
            )
            recovery_time = int((base_time + rollback_time) * multiplier)
        else:
            # Without rollback, recovery takes longer (manual intervention)
            recovery_time = int(base_time * multiplier * 2)
        
        # Add buffer for investigation and verification
        recovery_time += 60  # 1 minute buffer
        
        return recovery_time
    
    def calculate_risk_score(
        self,
        sequence: ActionSequence,
        network_state: NetworkState
    ) -> Dict[str, Any]:
        """
        Calculate a comprehensive risk score for the action sequence.
        
        Returns:
            Dictionary with risk score and breakdown
        """
        self.logger.info(f"Calculating risk score for sequence {sequence.id}")
        
        # Get impact assessment
        impact = self.assess_impact(sequence, network_state)
        
        # Calculate individual risk components
        bandwidth_risk = self._calculate_bandwidth_risk(
            impact.performance_impact.get("bandwidth_utilization_change", 0)
        )
        
        latency_risk = self._calculate_latency_risk(
            impact.performance_impact.get("latency_change_ms", 0)
        )
        
        resource_risk = self._calculate_resource_risk(
            len(impact.affected_resources),
            network_state
        )
        
        disruption_risk_score = self._disruption_risk_to_score(
            impact.service_disruption_risk
        )
        
        recovery_risk = self._calculate_recovery_risk(
            impact.estimated_recovery_time
        )
        
        # Calculate weighted overall risk score (0-100)
        weights = self._impact_weights
        overall_risk = (
            bandwidth_risk * weights["bandwidth_change"] +
            latency_risk * weights["latency_change"] +
            resource_risk * weights["affected_resources"] +
            disruption_risk_score * weights["service_disruption"] +
            recovery_risk * weights["recovery_complexity"]
        )
        
        # Determine risk level
        if overall_risk >= 75:
            risk_level = "critical"
        elif overall_risk >= 50:
            risk_level = "high"
        elif overall_risk >= 25:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        result = {
            "overall_risk_score": round(overall_risk, 2),
            "risk_level": risk_level,
            "risk_breakdown": {
                "bandwidth_risk": round(bandwidth_risk, 2),
                "latency_risk": round(latency_risk, 2),
                "resource_risk": round(resource_risk, 2),
                "disruption_risk": round(disruption_risk_score, 2),
                "recovery_risk": round(recovery_risk, 2)
            },
            "requires_approval": overall_risk >= 50
        }
        
        self.logger.info(
            f"Risk score calculated: {overall_risk:.2f} ({risk_level})"
        )
        
        return result
    
    def _calculate_bandwidth_risk(self, bandwidth_change: float) -> float:
        """Calculate risk score based on bandwidth change (0-100)."""
        abs_change = abs(bandwidth_change)
        
        if abs_change >= 50:
            return 100.0
        elif abs_change >= 30:
            return 75.0
        elif abs_change >= 15:
            return 50.0
        elif abs_change >= 5:
            return 25.0
        else:
            return 10.0
    
    def _calculate_latency_risk(self, latency_change: float) -> float:
        """Calculate risk score based on latency change (0-100)."""
        abs_change = abs(latency_change)
        
        if abs_change >= 100:  # 100ms+
            return 100.0
        elif abs_change >= 50:
            return 75.0
        elif abs_change >= 20:
            return 50.0
        elif abs_change >= 10:
            return 25.0
        else:
            return 10.0
    
    def _calculate_resource_risk(
        self,
        affected_count: int,
        network_state: NetworkState
    ) -> float:
        """Calculate risk score based on affected resources (0-100)."""
        total_resources = (
            len(network_state.topology.switches) +
            len(network_state.topology.links) +
            len(network_state.topology.hosts)
        )
        
        if total_resources == 0:
            return 0.0
        
        affected_percent = (affected_count / total_resources) * 100
        
        if affected_percent >= 50:
            return 100.0
        elif affected_percent >= 30:
            return 75.0
        elif affected_percent >= 15:
            return 50.0
        elif affected_percent >= 5:
            return 25.0
        else:
            return 10.0
    
    def _disruption_risk_to_score(self, disruption_risk: str) -> float:
        """Convert disruption risk level to score (0-100)."""
        risk_scores = {
            "none": 0.0,
            "minimal": 25.0,
            "moderate": 60.0,
            "high": 100.0
        }
        return risk_scores.get(disruption_risk, 50.0)
    
    def _calculate_recovery_risk(self, recovery_time: int) -> float:
        """Calculate risk score based on recovery time (0-100)."""
        if recovery_time >= 1800:  # 30 minutes+
            return 100.0
        elif recovery_time >= 900:  # 15 minutes+
            return 75.0
        elif recovery_time >= 300:  # 5 minutes+
            return 50.0
        elif recovery_time >= 120:  # 2 minutes+
            return 25.0
        else:
            return 10.0
    
    def generate_approval_workflow(
        self,
        sequence: ActionSequence,
        risk_score: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate an approval workflow based on risk assessment.
        
        Args:
            sequence: The action sequence
            risk_score: Risk score from calculate_risk_score()
            
        Returns:
            Dictionary with approval workflow details
        """
        self.logger.info(
            f"Generating approval workflow for sequence {sequence.id}"
        )
        
        workflow = {
            "requires_approval": risk_score["requires_approval"],
            "approval_level": None,
            "approvers": [],
            "review_items": [],
            "estimated_review_time": 0
        }
        
        risk_level = risk_score["risk_level"]
        
        if risk_level == "critical":
            workflow["approval_level"] = "senior_management"
            workflow["approvers"] = ["network_architect", "operations_manager", "cto"]
            workflow["estimated_review_time"] = 3600  # 1 hour
            workflow["review_items"] = [
                "Complete impact assessment",
                "Rollback plan verification",
                "Business continuity plan",
                "Stakeholder notification plan"
            ]
        
        elif risk_level == "high":
            workflow["approval_level"] = "management"
            workflow["approvers"] = ["network_manager", "operations_lead"]
            workflow["estimated_review_time"] = 1800  # 30 minutes
            workflow["review_items"] = [
                "Impact assessment",
                "Rollback plan",
                "Affected services list"
            ]
        
        elif risk_level == "medium":
            workflow["approval_level"] = "team_lead"
            workflow["approvers"] = ["network_team_lead"]
            workflow["estimated_review_time"] = 600  # 10 minutes
            workflow["review_items"] = [
                "Quick impact review",
                "Rollback availability check"
            ]
        
        else:  # low risk
            workflow["requires_approval"] = False
            workflow["approval_level"] = "automatic"
            workflow["estimated_review_time"] = 0
        
        return workflow



# Alias for API compatibility
Validator = ActionValidator
