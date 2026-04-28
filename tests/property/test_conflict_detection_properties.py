"""Property-based tests for conflict detection accuracy.

Feature: llm-integration-module, Property 9: Conflict detection accuracy
Validates: Requirements 3.2
"""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from typing import List, Dict, Set
from datetime import datetime

from llm_integration_module.services.action_sequencer import ActionSequencer, ActionConflict
from llm_integration_module.models.actions import NetworkAction, ActionType, ActionSequence


class TestConflictDetectionProperties:
    """Property-based tests for conflict detection accuracy."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sequencer = ActionSequencer()
    
    # Generator strategies for test data
    @st.composite
    def action_type_strategy(draw):
        """Generate valid action types."""
        return draw(st.sampled_from([
            ActionType.FLOW_MOD,
            ActionType.SLICE_CREATE,
            ActionType.SLICE_MODIFY,
            ActionType.CONFIG_CHANGE
        ]))
    
    @st.composite
    def network_action_strategy(draw, action_id=None, action_type=None, target=None):
        """Generate valid NetworkAction instances."""
        if action_id is None:
            action_id = f"action_{draw(st.integers(min_value=1000, max_value=9999))}"
        
        if action_type is None:
            action_type = draw(TestConflictDetectionProperties.action_type_strategy())
        
        if target is None:
            target_prefix = draw(st.sampled_from(["switch", "slice", "host", "link"]))
            target_num = draw(st.integers(min_value=1, max_value=10))
            target = f"{target_prefix}-{target_num}"
        
        priority = draw(st.integers(min_value=100, max_value=2000))
        
        # Generate parameters based on action type
        parameters = {}
        if action_type == ActionType.FLOW_MOD:
            parameters = {
                "match": {
                    "in_port": draw(st.integers(min_value=1, max_value=8)),
                    "eth_type": draw(st.sampled_from([0x0800, 0x0806, 0x86dd]))
                },
                "actions": [
                    {"type": "output", "port": draw(st.integers(min_value=1, max_value=8))}
                ]
            }
        elif action_type in [ActionType.SLICE_CREATE, ActionType.SLICE_MODIFY]:
            num_switches = draw(st.integers(min_value=1, max_value=4))
            parameters = {
                "slice_name": target,
                "resources": {
                    "switches": [f"switch-{i+1}" for i in range(num_switches)],
                    "bandwidth": draw(st.integers(min_value=100, max_value=10000))
                }
            }
        elif action_type == ActionType.CONFIG_CHANGE:
            parameters = {
                "config_type": draw(st.sampled_from(["flow_config", "slice_config", "qos_config"])),
                "config_data": {"setting": draw(st.text(min_size=1, max_size=20))}
            }
        
        return NetworkAction(
            id=action_id,
            type=action_type,
            target=target,
            parameters=parameters,
            priority=priority,
            timeout=draw(st.integers(min_value=10, max_value=120))
        )
    
    @st.composite
    def conflicting_action_pair_strategy(draw):
        """Generate a pair of actions that should conflict."""
        conflict_type = draw(st.sampled_from([
            "same_target_same_type",
            "overlapping_flows",
            "competing_slice_resources"
        ]))
        
        if conflict_type == "same_target_same_type":
            # Two actions of same type targeting same resource
            target = f"switch-{draw(st.integers(min_value=1, max_value=5))}"
            action_type = draw(TestConflictDetectionProperties.action_type_strategy())
            
            action1 = draw(TestConflictDetectionProperties.network_action_strategy(
                action_id="action_1",
                action_type=action_type,
                target=target
            ))
            action2 = draw(TestConflictDetectionProperties.network_action_strategy(
                action_id="action_2",
                action_type=action_type,
                target=target
            ))
            
            return (action1, action2, "resource")
        
        elif conflict_type == "overlapping_flows":
            # Two flow modifications with overlapping match criteria on different targets
            # to ensure they're detected as logical conflicts, not resource conflicts
            target1 = f"switch-{draw(st.integers(min_value=1, max_value=5))}"
            target2 = f"switch-{draw(st.integers(min_value=1, max_value=5))}"
            # Ensure different targets to avoid resource conflict
            assume(target1 != target2)
            
            in_port = draw(st.integers(min_value=1, max_value=8))
            eth_type = draw(st.sampled_from([0x0800, 0x0806, 0x86dd]))
            
            action1 = NetworkAction(
                id="flow_1",
                type=ActionType.FLOW_MOD,
                target=target1,
                parameters={
                    "match": {"in_port": in_port, "eth_type": eth_type},
                    "actions": [{"type": "output", "port": 2}]
                },
                priority=1000,
                timeout=30
            )
            
            action2 = NetworkAction(
                id="flow_2",
                type=ActionType.FLOW_MOD,
                target=target2,
                parameters={
                    "match": {"in_port": in_port, "eth_type": eth_type},
                    "actions": [{"type": "output", "port": 3}]
                },
                priority=1000,
                timeout=30
            )
            
            return (action1, action2, "logical")
        
        else:  # competing_slice_resources
            # Two slices competing for same switches
            shared_switches = [f"switch-{i+1}" for i in range(draw(st.integers(min_value=1, max_value=3)))]
            
            action1 = NetworkAction(
                id="slice_1",
                type=ActionType.SLICE_CREATE,
                target="slice-1",
                parameters={
                    "slice_name": "slice-1",
                    "resources": {
                        "switches": shared_switches,
                        "bandwidth": draw(st.integers(min_value=5000, max_value=8000))
                    }
                },
                priority=1000,
                timeout=60
            )
            
            action2 = NetworkAction(
                id="slice_2",
                type=ActionType.SLICE_CREATE,
                target="slice-2",
                parameters={
                    "slice_name": "slice-2",
                    "resources": {
                        "switches": shared_switches,
                        "bandwidth": draw(st.integers(min_value=5000, max_value=8000))
                    }
                },
                priority=1000,
                timeout=60
            )
            
            return (action1, action2, "resource")
    
    @st.composite
    def non_conflicting_action_pair_strategy(draw):
        """Generate a pair of actions that should NOT conflict."""
        # Different targets, no overlapping resources
        target1 = f"switch-{draw(st.integers(min_value=1, max_value=5))}"
        target2 = f"switch-{draw(st.integers(min_value=6, max_value=10))}"
        
        # Generate action types that won't conflict
        action_type1 = draw(TestConflictDetectionProperties.action_type_strategy())
        action_type2 = draw(TestConflictDetectionProperties.action_type_strategy())
        
        action1 = draw(TestConflictDetectionProperties.network_action_strategy(
            action_id="action_1",
            action_type=action_type1,
            target=target1
        ))
        action2 = draw(TestConflictDetectionProperties.network_action_strategy(
            action_id="action_2",
            action_type=action_type2,
            target=target2
        ))
        
        # For slice actions, ensure no overlapping switches
        if action1.type in [ActionType.SLICE_CREATE, ActionType.SLICE_MODIFY]:
            resources1 = action1.parameters.get("resources", {})
            switches1 = set(resources1.get("switches", []))
            
            if action2.type in [ActionType.SLICE_CREATE, ActionType.SLICE_MODIFY]:
                resources2 = action2.parameters.get("resources", {})
                switches2 = set(resources2.get("switches", []))
                
                # Ensure no overlap in switches
                assume(len(switches1.intersection(switches2)) == 0)
        
        return (action1, action2)
    
    @st.composite
    def action_sequence_with_conflicts_strategy(draw):
        """Generate an action sequence that contains conflicts."""
        # Create a sequence with at least one conflicting pair
        num_actions = draw(st.integers(min_value=3, max_value=8))
        actions = []
        used_ids = set()
        
        # Add a conflicting pair
        conflict_pair = draw(TestConflictDetectionProperties.conflicting_action_pair_strategy())
        actions.append(conflict_pair[0])
        actions.append(conflict_pair[1])
        used_ids.add(conflict_pair[0].id)
        used_ids.add(conflict_pair[1].id)
        
        # Add additional random actions
        for i in range(num_actions - 2):
            action_id = f"action_{i+3}_{draw(st.integers(min_value=1000, max_value=9999))}"
            while action_id in used_ids:
                action_id = f"action_{i+3}_{draw(st.integers(min_value=1000, max_value=9999))}"
            used_ids.add(action_id)
            
            action = draw(TestConflictDetectionProperties.network_action_strategy(action_id=action_id))
            actions.append(action)
        
        return ActionSequence(
            id=f"seq_{draw(st.integers(min_value=1, max_value=1000))}",
            intent_id=f"intent_{draw(st.integers(min_value=1, max_value=100))}",
            actions=actions,
            estimated_duration=sum(a.timeout for a in actions),
            dependencies=[],
            rollback_plan=[]
        )
    
    # Property 9: Conflict detection accuracy
    # For any NetworkAction sequence that could cause conflicts or problems,
    # the LLM_Module should identify and report all potential risks before execution
    
    @given(conflicting_action_pair_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_9_detects_known_conflicts(self, action_pair):
        """
        Property 9.1: Known conflicting actions should be detected.
        
        When two actions have a known conflict pattern (same target, overlapping flows,
        competing resources), the conflict detection should identify them.
        """
        action1, action2, expected_conflict_type = action_pair
        
        # Detect conflicts
        conflicts = self.sequencer.detect_conflicts([action1, action2])
        
        # Should detect at least one conflict
        assert len(conflicts) > 0, (
            f"Failed to detect conflict between {action1.id} and {action2.id}. "
            f"Expected conflict type: {expected_conflict_type}"
        )
        
        # Verify conflict involves both actions
        conflict = conflicts[0]
        assert (
            (conflict.action1_id == action1.id and conflict.action2_id == action2.id) or
            (conflict.action1_id == action2.id and conflict.action2_id == action1.id)
        ), f"Conflict doesn't involve the expected actions: {conflict}"
        
        # Verify conflict type matches expected
        assert conflict.conflict_type == expected_conflict_type, (
            f"Conflict type mismatch. Expected: {expected_conflict_type}, "
            f"Got: {conflict.conflict_type}"
        )
        
        # Verify severity is appropriate
        assert conflict.severity in ["low", "medium", "high", "critical"], (
            f"Invalid severity level: {conflict.severity}"
        )
    
    @given(non_conflicting_action_pair_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_9_no_false_positives(self, action_pair):
        """
        Property 9.2: Non-conflicting actions should not be flagged as conflicts.
        
        When two actions target different resources with no overlap,
        no conflicts should be detected (avoiding false positives).
        """
        action1, action2 = action_pair
        
        # Detect conflicts
        conflicts = self.sequencer.detect_conflicts([action1, action2])
        
        # For flow modifications, overlapping match criteria is a valid conflict
        # even on different targets (logical conflict)
        if (action1.type == ActionType.FLOW_MOD and action2.type == ActionType.FLOW_MOD):
            match1 = action1.parameters.get('match', {})
            match2 = action2.parameters.get('match', {})
            
            # If matches overlap, conflict is expected
            common_fields = set(match1.keys()) & set(match2.keys())
            if common_fields and all(match1[f] == match2[f] for f in common_fields):
                # This is a valid conflict, not a false positive
                return
        
        # Should not detect conflicts for actions with different targets
        # and no resource overlap
        assert len(conflicts) == 0, (
            f"False positive: Detected conflict between non-conflicting actions. "
            f"Action1: {action1.id} (target: {action1.target}, type: {action1.type}), "
            f"Action2: {action2.id} (target: {action2.target}, type: {action2.type}). "
            f"Conflicts: {conflicts}"
        )
    
    @given(action_sequence_with_conflicts_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_9_all_conflicts_reported(self, sequence):
        """
        Property 9.3: All conflicts in a sequence should be reported.
        
        When an action sequence contains multiple conflicts,
        all of them should be identified and reported.
        """
        # Detect conflicts
        conflicts = self.sequencer.detect_conflicts(sequence.actions)
        
        # Should detect at least one conflict (we know there's at least one)
        assert len(conflicts) > 0, (
            f"Failed to detect any conflicts in sequence {sequence.id} "
            f"with {len(sequence.actions)} actions"
        )
        
        # Verify all conflicts are properly structured
        for conflict in conflicts:
            assert hasattr(conflict, 'action1_id'), "Conflict missing action1_id"
            assert hasattr(conflict, 'action2_id'), "Conflict missing action2_id"
            assert hasattr(conflict, 'conflict_type'), "Conflict missing conflict_type"
            assert hasattr(conflict, 'severity'), "Conflict missing severity"
            assert hasattr(conflict, 'description'), "Conflict missing description"
            
            # Verify actions exist in sequence
            action_ids = {a.id for a in sequence.actions}
            assert conflict.action1_id in action_ids, (
                f"Conflict references non-existent action: {conflict.action1_id}"
            )
            assert conflict.action2_id in action_ids, (
                f"Conflict references non-existent action: {conflict.action2_id}"
            )
            
            # Verify conflict type is valid
            assert conflict.conflict_type in ["resource", "timing", "logical"], (
                f"Invalid conflict type: {conflict.conflict_type}"
            )
            
            # Verify severity is valid
            assert conflict.severity in ["low", "medium", "high", "critical"], (
                f"Invalid severity: {conflict.severity}"
            )
    
    @given(st.lists(
        network_action_strategy(),
        min_size=2,
        max_size=10,
        unique_by=lambda a: a.id
    ))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_9_conflict_detection_consistency(self, actions):
        """
        Property 9.4: Conflict detection should be consistent and deterministic.
        
        Running conflict detection multiple times on the same action set
        should produce the same results.
        """
        # Run conflict detection multiple times
        conflicts1 = self.sequencer.detect_conflicts(actions)
        conflicts2 = self.sequencer.detect_conflicts(actions)
        conflicts3 = self.sequencer.detect_conflicts(actions)
        
        # Should get same number of conflicts
        assert len(conflicts1) == len(conflicts2) == len(conflicts3), (
            "Conflict detection is non-deterministic: "
            f"Run 1: {len(conflicts1)}, Run 2: {len(conflicts2)}, Run 3: {len(conflicts3)}"
        )
        
        # Convert to sets of conflict pairs for comparison
        def conflict_to_tuple(c):
            # Sort action IDs to make comparison order-independent
            ids = sorted([c.action1_id, c.action2_id])
            return (ids[0], ids[1], c.conflict_type, c.severity)
        
        conflicts1_set = {conflict_to_tuple(c) for c in conflicts1}
        conflicts2_set = {conflict_to_tuple(c) for c in conflicts2}
        conflicts3_set = {conflict_to_tuple(c) for c in conflicts3}
        
        assert conflicts1_set == conflicts2_set == conflicts3_set, (
            "Conflict detection produced different results across runs"
        )
    
    @given(st.lists(
        network_action_strategy(),
        min_size=1,
        max_size=15,
        unique_by=lambda a: a.id
    ))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_9_conflict_severity_appropriate(self, actions):
        """
        Property 9.5: Conflict severity should be appropriate for the risk level.
        
        Critical conflicts (e.g., competing for critical resources) should have
        higher severity than minor conflicts (e.g., same target with different types).
        """
        conflicts = self.sequencer.detect_conflicts(actions)
        
        for conflict in conflicts:
            # Get the conflicting actions
            action1 = next((a for a in actions if a.id == conflict.action1_id), None)
            action2 = next((a for a in actions if a.id == conflict.action2_id), None)
            
            if action1 and action2:
                # Slice resource conflicts (competing for resources) should be high severity
                if (action1.type in [ActionType.SLICE_CREATE, ActionType.SLICE_MODIFY] and
                    action2.type in [ActionType.SLICE_CREATE, ActionType.SLICE_MODIFY]):
                    # Only if they actually compete for resources (not just same target)
                    if conflict.conflict_type == "resource" and "compete" in conflict.description.lower():
                        assert conflict.severity in ["high", "critical"], (
                            f"Slice resource competition should have high/critical severity, "
                            f"got: {conflict.severity}"
                        )
                
                # Same target, same type should be at least medium severity
                if action1.target == action2.target and action1.type == action2.type:
                    assert conflict.severity in ["medium", "high", "critical"], (
                        f"Same target/type conflict should have medium+ severity, "
                        f"got: {conflict.severity}"
                    )
    
    @given(st.lists(
        network_action_strategy(),
        min_size=0,
        max_size=1,
        unique_by=lambda a: a.id
    ))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_9_no_conflicts_with_single_or_no_actions(self, actions):
        """
        Property 9.6: Single action or empty list should have no conflicts.
        
        Conflicts require at least two actions, so single action or empty
        action lists should never produce conflicts.
        """
        conflicts = self.sequencer.detect_conflicts(actions)
        
        assert len(conflicts) == 0, (
            f"Detected conflicts with {len(actions)} action(s). "
            f"Conflicts should only exist between multiple actions. "
            f"Conflicts: {conflicts}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
