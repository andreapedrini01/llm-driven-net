"""Action sequencing and optimization service."""

from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict, deque
import logging

from src.models.actions import (
    NetworkAction,
    ActionSequence,
    ActionType,
    ValidationResult
)

logger = logging.getLogger(__name__)


class ActionDependency:
    """Represents a dependency between two actions."""
    
    def __init__(self, action_id: str, depends_on: str, reason: str = ""):
        self.action_id = action_id
        self.depends_on = depends_on
        self.reason = reason
    
    def __repr__(self) -> str:
        return f"ActionDependency({self.action_id} -> {self.depends_on}: {self.reason})"


class ActionConflict:
    """Represents a conflict between two actions."""
    
    def __init__(
        self,
        action1_id: str,
        action2_id: str,
        conflict_type: str,
        severity: str,
        description: str
    ):
        self.action1_id = action1_id
        self.action2_id = action2_id
        self.conflict_type = conflict_type  # "resource", "timing", "logical"
        self.severity = severity  # "low", "medium", "high", "critical"
        self.description = description
    
    def __repr__(self) -> str:
        return f"ActionConflict({self.action1_id} <-> {self.action2_id}: {self.conflict_type}/{self.severity})"


class ActionSequencer:
    """Service for analyzing dependencies and optimizing action sequences."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_dependencies(
        self,
        actions: List[NetworkAction]
    ) -> Tuple[List[ActionDependency], Dict[str, List[str]]]:
        """
        Analyze dependencies between actions.
        
        Returns:
            Tuple of (dependency list, dependency map)
        """
        dependencies = []
        dependency_map = defaultdict(list)
        
        # Build action lookup
        action_map = {action.id: action for action in actions}
        
        # Analyze each pair of actions for dependencies
        for i, action1 in enumerate(actions):
            for action2 in actions[i+1:]:
                dep = self._check_dependency(action1, action2)
                if dep:
                    dependencies.append(dep)
                    dependency_map[dep.action_id].append(dep.depends_on)
                
                # Check reverse dependency
                dep_reverse = self._check_dependency(action2, action1)
                if dep_reverse:
                    dependencies.append(dep_reverse)
                    dependency_map[dep_reverse.action_id].append(dep_reverse.depends_on)
        
        self.logger.info(f"Found {len(dependencies)} dependencies among {len(actions)} actions")
        return dependencies, dict(dependency_map)
    
    def _check_dependency(
        self,
        action1: NetworkAction,
        action2: NetworkAction
    ) -> Optional[ActionDependency]:
        """Check if action1 depends on action2."""
        
        # Slice creation must happen before slice modification
        if (action1.type == ActionType.SLICE_MODIFY and 
            action2.type == ActionType.SLICE_CREATE):
            if self._targets_same_slice(action1, action2):
                return ActionDependency(
                    action1.id,
                    action2.id,
                    "Slice must be created before modification"
                )
        
        # Flow modifications on a slice depend on slice creation
        if (action1.type == ActionType.FLOW_MOD and 
            action2.type == ActionType.SLICE_CREATE):
            if action1.target == action2.target:
                return ActionDependency(
                    action1.id,
                    action2.id,
                    "Flow modification depends on slice creation"
                )
        
        # Flow modifications on same target should be ordered
        if (action1.type == ActionType.FLOW_MOD and 
            action2.type == ActionType.FLOW_MOD):
            if action1.target == action2.target:
                # Higher priority action should come first
                if action1.priority < action2.priority:
                    return ActionDependency(
                        action1.id,
                        action2.id,
                        "Lower priority flow depends on higher priority"
                    )
        
        # Config changes should happen before actions that use the config
        if (action1.type in [ActionType.FLOW_MOD, ActionType.SLICE_CREATE] and
            action2.type == ActionType.CONFIG_CHANGE):
            if self._config_affects_action(action2, action1):
                return ActionDependency(
                    action1.id,
                    action2.id,
                    "Action depends on configuration change"
                )
        
        # Any action on a target depends on CONFIG_CHANGE on the same target
        if (action1.type != ActionType.CONFIG_CHANGE and 
            action2.type == ActionType.CONFIG_CHANGE):
            if action1.target == action2.target:
                return ActionDependency(
                    action1.id,
                    action2.id,
                    "Action depends on configuration of same target"
                )
        
        return None
    
    def _targets_same_slice(self, action1: NetworkAction, action2: NetworkAction) -> bool:
        """Check if two actions target the same slice."""
        slice_name1 = action1.parameters.get('slice_name') or action1.target
        slice_name2 = action2.parameters.get('slice_name') or action2.target
        return slice_name1 == slice_name2
    
    def _config_affects_action(self, config_action: NetworkAction, target_action: NetworkAction) -> bool:
        """Check if a config change affects another action."""
        config_type = config_action.parameters.get('config_type', '')
        
        # Check if config affects the target
        if config_action.target == target_action.target:
            return True
        
        # Check if config type is relevant to action type
        if target_action.type == ActionType.FLOW_MOD and 'flow' in config_type.lower():
            return True
        if target_action.type in [ActionType.SLICE_CREATE, ActionType.SLICE_MODIFY] and 'slice' in config_type.lower():
            return True
        
        return False
    
    def detect_conflicts(self, actions: List[NetworkAction]) -> List[ActionConflict]:
        """
        Detect conflicts between actions.
        
        Returns:
            List of detected conflicts
        """
        conflicts = []
        
        # Check each pair of actions
        for i, action1 in enumerate(actions):
            for action2 in actions[i+1:]:
                conflict = self._check_conflict(action1, action2)
                if conflict:
                    conflicts.append(conflict)
        
        self.logger.info(f"Found {len(conflicts)} conflicts among {len(actions)} actions")
        return conflicts
    
    def _check_conflict(
        self,
        action1: NetworkAction,
        action2: NetworkAction
    ) -> Optional[ActionConflict]:
        """Check if two actions conflict."""
        
        # Same target resource conflict
        if action1.target == action2.target:
            # Special case: SLICE_CREATE followed by SLICE_MODIFY is a dependency, not a conflict
            if ((action1.type == ActionType.SLICE_CREATE and action2.type == ActionType.SLICE_MODIFY) or
                (action1.type == ActionType.SLICE_MODIFY and action2.type == ActionType.SLICE_CREATE)):
                # This is a dependency relationship, not a conflict
                return None
            
            # Multiple modifications on same target
            if action1.type == action2.type:
                return ActionConflict(
                    action1.id,
                    action2.id,
                    "resource",
                    "medium",
                    f"Both actions modify the same target: {action1.target}"
                )
            
            # Different action types on same target
            # Most cases can be resolved through dependency ordering, so treat as medium severity
            # unless it's a known dependency relationship
            if action1.type != action2.type:
                # Check if this is a known dependency relationship
                dependency_pairs = [
                    (ActionType.CONFIG_CHANGE, ActionType.FLOW_MOD),
                    (ActionType.CONFIG_CHANGE, ActionType.SLICE_CREATE),
                    (ActionType.CONFIG_CHANGE, ActionType.SLICE_MODIFY),
                    (ActionType.SLICE_CREATE, ActionType.FLOW_MOD),
                    (ActionType.SLICE_CREATE, ActionType.SLICE_MODIFY),
                ]
                
                # Check if this pair is a dependency (in either order)
                is_dependency = False
                for dep_type1, dep_type2 in dependency_pairs:
                    if ((action1.type == dep_type1 and action2.type == dep_type2) or
                        (action1.type == dep_type2 and action2.type == dep_type1)):
                        is_dependency = True
                        break
                
                if is_dependency:
                    # This is a dependency, not a conflict
                    return None
                
                # Other combinations: treat as medium severity (can be resolved by ordering)
                return ActionConflict(
                    action1.id,
                    action2.id,
                    "resource",
                    "medium",
                    f"Different action types on same target: {action1.target}"
                )
        
        # Flow modification conflicts
        if action1.type == ActionType.FLOW_MOD and action2.type == ActionType.FLOW_MOD:
            if self._flows_overlap(action1, action2):
                return ActionConflict(
                    action1.id,
                    action2.id,
                    "logical",
                    "medium",
                    "Flow rules have overlapping match criteria"
                )
        
        # Slice resource conflicts
        if (action1.type in [ActionType.SLICE_CREATE, ActionType.SLICE_MODIFY] and
            action2.type in [ActionType.SLICE_CREATE, ActionType.SLICE_MODIFY]):
            if self._slices_compete_for_resources(action1, action2):
                return ActionConflict(
                    action1.id,
                    action2.id,
                    "resource",
                    "high",
                    "Slices compete for the same network resources"
                )
        
        return None
    
    def _flows_overlap(self, action1: NetworkAction, action2: NetworkAction) -> bool:
        """Check if two flow modifications have overlapping match criteria."""
        match1 = action1.parameters.get('match', {})
        match2 = action2.parameters.get('match', {})
        
        if not match1 or not match2:
            return False
        
        # Check for overlapping match fields
        common_fields = set(match1.keys()) & set(match2.keys())
        if not common_fields:
            return False
        
        # If all common fields match, flows overlap
        for field in common_fields:
            if match1[field] != match2[field]:
                return False
        
        return True
    
    def _slices_compete_for_resources(self, action1: NetworkAction, action2: NetworkAction) -> bool:
        """Check if two slice actions compete for resources."""
        resources1 = action1.parameters.get('resources', {})
        resources2 = action2.parameters.get('resources', {})
        
        if not resources1 or not resources2:
            return False
        
        # Check for overlapping switches
        switches1 = set(resources1.get('switches', []))
        switches2 = set(resources2.get('switches', []))
        
        if switches1 & switches2:
            return True
        
        # Check for overlapping paths
        paths1 = resources1.get('paths', [])
        paths2 = resources2.get('paths', [])
        
        for path1 in paths1:
            for path2 in paths2:
                if self._paths_overlap(path1, path2):
                    return True
        
        return False
    
    def _paths_overlap(self, path1: Dict, path2: Dict) -> bool:
        """Check if two paths overlap."""
        switches1 = set(path1.get('switches', []))
        switches2 = set(path2.get('switches', []))
        return bool(switches1 & switches2)
    
    def resolve_conflicts(
        self,
        actions: List[NetworkAction],
        conflicts: List[ActionConflict]
    ) -> Tuple[List[NetworkAction], List[str]]:
        """
        Resolve conflicts by modifying or removing actions.
        
        Returns:
            Tuple of (resolved actions, resolution notes)
        """
        resolved_actions = actions.copy()
        resolution_notes = []
        actions_to_remove = set()
        
        # Sort conflicts by severity
        sorted_conflicts = sorted(
            conflicts,
            key=lambda c: {"critical": 4, "high": 3, "medium": 2, "low": 1}[c.severity],
            reverse=True
        )
        
        for conflict in sorted_conflicts:
            if conflict.action1_id in actions_to_remove or conflict.action2_id in actions_to_remove:
                continue
            
            resolution = self._resolve_single_conflict(conflict, resolved_actions)
            if resolution:
                resolution_notes.append(resolution)
                
                # If resolution suggests removal, mark for removal
                if "removed" in resolution.lower():
                    if conflict.action1_id in resolution:
                        actions_to_remove.add(conflict.action1_id)
                    if conflict.action2_id in resolution:
                        actions_to_remove.add(conflict.action2_id)
        
        # Remove conflicting actions
        if actions_to_remove:
            resolved_actions = [a for a in resolved_actions if a.id not in actions_to_remove]
            self.logger.info(f"Removed {len(actions_to_remove)} conflicting actions")
        
        return resolved_actions, resolution_notes
    
    def _resolve_single_conflict(
        self,
        conflict: ActionConflict,
        actions: List[NetworkAction]
    ) -> Optional[str]:
        """Resolve a single conflict."""
        
        action1 = next((a for a in actions if a.id == conflict.action1_id), None)
        action2 = next((a for a in actions if a.id == conflict.action2_id), None)
        
        if not action1 or not action2:
            return None
        
        # For critical conflicts, remove lower priority action
        if conflict.severity == "critical":
            if action1.priority < action2.priority:
                return f"Removed action {action1.id} due to critical conflict (lower priority)"
            else:
                return f"Removed action {action2.id} due to critical conflict (lower priority)"
        
        # For high severity resource conflicts, handle based on action types
        if conflict.severity == "high" and conflict.conflict_type == "resource":
            # For slices competing for resources, remove lower priority
            if action1.type in [ActionType.SLICE_CREATE, ActionType.SLICE_MODIFY]:
                if action1.priority < action2.priority:
                    return f"Removed action {action1.id} due to resource competition (lower priority)"
                elif action2.priority < action1.priority:
                    return f"Removed action {action2.id} due to resource competition (lower priority)"
                else:
                    # Equal priority - remove the second one
                    return f"Removed action {action2.id} due to resource competition (equal priority)"
            else:
                # For other high-severity conflicts, adjust priorities to ensure ordering
                if action1.priority == action2.priority:
                    action2.priority = action1.priority - 1
                    return f"Adjusted priority of {action2.id} to resolve resource conflict"
        
        # For medium severity, log warning
        if conflict.severity == "medium":
            return f"Warning: {conflict.description} between {action1.id} and {action2.id}"
        
        return None
    
    def optimize_sequence(
        self,
        actions: List[NetworkAction],
        dependency_map: Dict[str, List[str]]
    ) -> List[NetworkAction]:
        """
        Optimize action sequence based on dependencies and priorities.
        
        Uses topological sort with priority ordering.
        """
        if not actions:
            return []
        
        # Build action lookup
        action_map = {action.id: action for action in actions}
        
        # Build adjacency list for topological sort
        graph = defaultdict(list)
        in_degree = defaultdict(int)
        
        # Initialize all actions with 0 in-degree
        for action in actions:
            in_degree[action.id] = 0
        
        # Build graph from dependencies
        for action_id, deps in dependency_map.items():
            if action_id in action_map:
                for dep in deps:
                    if dep in action_map:
                        graph[dep].append(action_id)
                        in_degree[action_id] += 1
        
        # Topological sort with priority queue
        queue = deque()
        
        # Start with actions that have no dependencies
        for action in actions:
            if in_degree[action.id] == 0:
                queue.append(action.id)
        
        # Sort initial queue by priority
        queue = deque(sorted(queue, key=lambda aid: -action_map[aid].priority))
        
        optimized = []
        
        while queue:
            # Get highest priority action from queue
            current_id = queue.popleft()
            current_action = action_map[current_id]
            optimized.append(current_action)
            
            # Process dependent actions
            for dependent_id in graph[current_id]:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    queue.append(dependent_id)
            
            # Re-sort queue by priority
            queue = deque(sorted(queue, key=lambda aid: -action_map[aid].priority))
        
        # Check for cycles
        if len(optimized) != len(actions):
            self.logger.warning("Circular dependencies detected, using priority-based ordering")
            # Fall back to simple priority sorting
            optimized = sorted(actions, key=lambda a: (-a.priority, a.estimate_execution_time()))
        
        self.logger.info(f"Optimized sequence of {len(optimized)} actions")
        return optimized
    
    def sequence_actions(
        self,
        actions: List[NetworkAction],
        intent_id: str,
        sequence_id: str
    ) -> ActionSequence:
        """
        Create an optimized action sequence with conflict resolution.
        
        This is the main entry point that combines all sequencing operations.
        """
        self.logger.info(f"Sequencing {len(actions)} actions for intent {intent_id}")
        
        # Step 1: Detect conflicts
        conflicts = self.detect_conflicts(actions)
        
        # Step 2: Resolve conflicts
        resolved_actions, resolution_notes = self.resolve_conflicts(actions, conflicts)
        
        if resolution_notes:
            for note in resolution_notes:
                self.logger.info(f"Conflict resolution: {note}")
        
        # Step 3: Analyze dependencies
        dependencies, dependency_map = self.analyze_dependencies(resolved_actions)
        
        # Step 4: Optimize sequence
        optimized_actions = self.optimize_sequence(resolved_actions, dependency_map)
        
        # Step 5: Calculate estimated duration
        estimated_duration = sum(action.estimate_execution_time() for action in optimized_actions)
        
        # Step 6: Generate rollback plan
        rollback_plan = self._generate_rollback_plan(optimized_actions)
        
        # Step 7: Create action sequence
        sequence = ActionSequence(
            id=sequence_id,
            intent_id=intent_id,
            actions=optimized_actions,
            estimated_duration=estimated_duration,
            dependencies=[dep for deps in dependency_map.values() for dep in deps],
            rollback_plan=rollback_plan
        )
        
        self.logger.info(
            f"Created sequence {sequence_id} with {len(optimized_actions)} actions, "
            f"estimated duration: {estimated_duration}s"
        )
        
        return sequence
    
    def _generate_rollback_plan(self, actions: List[NetworkAction]) -> List[NetworkAction]:
        """Generate rollback actions for a sequence."""
        rollback_actions = []
        
        # Reverse the action order for rollback
        for i, action in enumerate(reversed(actions)):
            rollback_action = self._create_rollback_action(action, i)
            if rollback_action:
                rollback_actions.append(rollback_action)
        
        return rollback_actions
    
    def _create_rollback_action(self, action: NetworkAction, index: int) -> Optional[NetworkAction]:
        """Create a rollback action for a given action."""
        
        # Flow modifications can be rolled back by deleting the flow
        if action.type == ActionType.FLOW_MOD:
            return NetworkAction(
                id=f"rollback_{action.id}_{index}",
                type=ActionType.FLOW_MOD,
                target=action.target,
                parameters={
                    "command": "delete",
                    "match": action.parameters.get("match", {})
                },
                priority=action.priority,
                timeout=action.timeout,
                description=f"Rollback for {action.id}"
            )
        
        # Slice creation can be rolled back by deletion
        if action.type == ActionType.SLICE_CREATE:
            return NetworkAction(
                id=f"rollback_{action.id}_{index}",
                type=ActionType.CONFIG_CHANGE,
                target=action.target,
                parameters={
                    "config_type": "slice_delete",
                    "slice_name": action.parameters.get("slice_name")
                },
                priority=action.priority,
                timeout=action.timeout,
                description=f"Rollback for {action.id}"
            )
        
        # Config changes need original config stored (not implemented here)
        # Would require state tracking
        
        return None
    
    def validate_sequence(self, sequence: ActionSequence) -> ValidationResult:
        """Validate an action sequence for correctness."""
        errors = []
        warnings = []
        suggestions = []
        
        # Check for empty sequence
        if not sequence.actions:
            errors.append("Action sequence is empty")
            return ValidationResult(is_valid=False, errors=errors)
        
        # Validate each action
        for action in sequence.actions:
            validation = action.validate_action_parameters()
            if not validation["is_valid"]:
                errors.extend([f"Action {action.id}: {issue}" for issue in validation["issues"]])
            warnings.extend([f"Action {action.id}: {warning}" for warning in validation["warnings"]])
        
        # Check for remaining conflicts
        conflicts = self.detect_conflicts(sequence.actions)
        critical_conflicts = [c for c in conflicts if c.severity in ["critical", "high"]]
        
        if critical_conflicts:
            errors.extend([f"Unresolved conflict: {c.description}" for c in critical_conflicts])
        
        # Check sequence integrity
        integrity = sequence.validate_sequence_integrity()
        if not integrity["is_valid"]:
            errors.extend(integrity["issues"])
        warnings.extend(integrity["warnings"])
        
        # Suggestions
        if not sequence.rollback_plan:
            suggestions.append("Consider adding a rollback plan for safer execution")
        
        if sequence.estimated_duration > 300:  # 5 minutes
            suggestions.append("Long execution time - consider breaking into smaller sequences")
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )

    def parse_actions_from_response(self, response_content: str) -> List[NetworkAction]:
        """
        Parse network actions from ChatGPT response content.
        
        Args:
            response_content: The response content from ChatGPT
            
        Returns:
            List of NetworkAction objects
        """
        import json
        import re
        
        actions = []
        
        try:
            # Try to parse as JSON first
            if response_content.strip().startswith('{') or response_content.strip().startswith('['):
                data = json.loads(response_content)
                
                # Handle different response formats
                if isinstance(data, dict):
                    actions_data = data.get('actions', [])
                elif isinstance(data, list):
                    actions_data = data
                else:
                    actions_data = []
                
                # Convert to NetworkAction objects
                for action_data in actions_data:
                    action = NetworkAction.from_dict(action_data)
                    actions.append(action)
            
            else:
                # Try to extract JSON from markdown code blocks
                json_match = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', response_content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    data = json.loads(json_str)
                    
                    if isinstance(data, dict):
                        actions_data = data.get('actions', [])
                    elif isinstance(data, list):
                        actions_data = data
                    else:
                        actions_data = []
                    
                    for action_data in actions_data:
                        action = NetworkAction.from_dict(action_data)
                        actions.append(action)
        
        except Exception as e:
            self.logger.error(f"Failed to parse actions from response: {e}")
            # Return empty list on parse failure
            return []
        
        return actions
