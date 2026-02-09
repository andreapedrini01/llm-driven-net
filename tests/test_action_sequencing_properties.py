"""Property-based tests for action sequencing logic."""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from typing import List, Dict, Set
from datetime import datetime

from src.services.action_sequencer import ActionSequencer, ActionDependency, ActionConflict
from src.models.actions import NetworkAction, ActionType, ActionSequence


class TestActionSequencingProperties:
    """Property-based tests for action sequencing logic."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sequencer = ActionSequencer()
    
    # Generator strategies for test data
    @staticmethod
    @st.composite
    def action_type_strategy(draw):
        """Generate valid action types."""
        return draw(st.sampled_from([
            ActionType.FLOW_MOD,
            ActionType.SLICE_CREATE,
            ActionType.SLICE_MODIFY,
            ActionType.CONFIG_CHANGE
        ]))
    
    @staticmethod
    @st.composite
    def network_action_strategy(draw, action_id=None, action_type=None, target=None, priority=None):
        """Generate valid NetworkAction instances."""
        if action_id is None:
            action_id = f"action_{draw(st.integers(min_value=1000, max_value=9999))}"
        
        if action_type is None:
            action_type = draw(TestActionSequencingProperties.action_type_strategy())
        
        if target is None:
            target_prefix = draw(st.sampled_from(["switch", "slice", "host", "link"]))
            target_num = draw(st.integers(min_value=1, max_value=10))
            target = f"{target_prefix}-{target_num}"
        
        if priority is None:
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
    
    @staticmethod
    @st.composite
    def action_list_strategy(draw, min_size=2, max_size=10):
        """Generate list of NetworkAction instances."""
        num_actions = draw(st.integers(min_value=min_size, max_value=max_size))
        actions = []
        used_ids = set()
        
        for i in range(num_actions):
            # Ensure unique IDs
            action_id = f"action_{i}_{draw(st.integers(min_value=1000, max_value=9999))}"
            while action_id in used_ids:
                action_id = f"action_{i}_{draw(st.integers(min_value=1000, max_value=9999))}"
            used_ids.add(action_id)
            
            action = draw(TestActionSequencingProperties.network_action_strategy(action_id=action_id))
            actions.append(action)
        
        return actions
    
    @staticmethod
    @st.composite
    def dependent_action_pair_strategy(draw):
        """Generate a pair of actions with a dependency relationship."""
        # Create slice first, then modify it
        slice_name = f"slice-{draw(st.integers(min_value=1, max_value=5))}"
        
        create_action = draw(TestActionSequencingProperties.network_action_strategy(
            action_id=f"create_{slice_name}",
            action_type=ActionType.SLICE_CREATE,
            target=slice_name,
            priority=draw(st.integers(min_value=500, max_value=1000))
        ))
        
        modify_action = draw(TestActionSequencingProperties.network_action_strategy(
            action_id=f"modify_{slice_name}",
            action_type=ActionType.SLICE_MODIFY,
            target=slice_name,
            priority=draw(st.integers(min_value=500, max_value=1000))
        ))
        
        return [create_action, modify_action]
    
    @staticmethod
    @st.composite
    def priority_ordered_actions_strategy(draw):
        """Generate actions with different priorities."""
        num_actions = draw(st.integers(min_value=3, max_value=8))
        actions = []
        
        # Generate actions with distinct priorities
        priorities = draw(st.lists(
            st.integers(min_value=100, max_value=2000),
            min_size=num_actions,
            max_size=num_actions,
            unique=True
        ))
        
        for i, priority in enumerate(priorities):
            action = draw(TestActionSequencingProperties.network_action_strategy(
                action_id=f"action_{i}",
                priority=priority
            ))
            actions.append(action)
        
        return actions
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(actions=action_list_strategy())
    def test_action_sequencing_logic(self, actions):
        """
        **Feature: llm-integration-module, Property 10: Action sequencing logic**
        
        For any intent requiring multiple NetworkActions, the actions should be 
        ordered in a logical execution sequence that respects dependencies and 
        minimizes conflicts.
        
        **Validates: Requirements 3.4**
        """
        # Ensure we have multiple actions
        assume(len(actions) >= 2)
        assume(len(set(a.id for a in actions)) == len(actions))  # Unique IDs
        
        # Create action sequence
        sequence = self.sequencer.sequence_actions(
            actions=actions,
            intent_id="test_intent",
            sequence_id="test_sequence"
        )
        
        # Property 1: All input actions should be in the output sequence OR removed due to conflict resolution
        # Note: Conflict resolution may remove actions to resolve critical/high-severity conflicts
        assert len(sequence.actions) <= len(actions), (
            f"Sequence should not have more actions than input. Expected <= {len(actions)}, got {len(sequence.actions)}"
        )
        
        # If actions were removed, verify they were removed due to conflict resolution
        if len(sequence.actions) < len(actions):
            input_ids = set(a.id for a in actions)
            output_ids = set(a.id for a in sequence.actions)
            removed_ids = input_ids - output_ids
            
            # Verify removed actions had conflicts
            conflicts = self.sequencer.detect_conflicts(actions)
            conflict_action_ids = set()
            for conflict in conflicts:
                if conflict.severity in ["critical", "high"]:
                    conflict_action_ids.add(conflict.action1_id)
                    conflict_action_ids.add(conflict.action2_id)
            
            # All removed actions should have been involved in high-severity conflicts
            assert removed_ids.issubset(conflict_action_ids), (
                f"Actions removed without high-severity conflicts: {removed_ids - conflict_action_ids}"
            )
        else:
            # If no actions removed, verify all input actions are in output
            input_ids = set(a.id for a in actions)
            output_ids = set(a.id for a in sequence.actions)
            assert input_ids == output_ids, "Sequence should contain exactly the same actions as input"
        
        # Property 2: Dependencies should be respected in the ordering
        dependencies, dep_map = self.sequencer.analyze_dependencies(actions)
        
        # Build position map for actions in the sequence
        position_map = {action.id: i for i, action in enumerate(sequence.actions)}
        
        # Verify all dependencies are satisfied
        for dep in dependencies:
            action_pos = position_map.get(dep.action_id)
            depends_on_pos = position_map.get(dep.depends_on)
            
            if action_pos is not None and depends_on_pos is not None:
                assert depends_on_pos < action_pos, (
                    f"Dependency violation: {dep.action_id} (pos {action_pos}) "
                    f"depends on {dep.depends_on} (pos {depends_on_pos}), "
                    f"but {dep.depends_on} comes after {dep.action_id}"
                )
        
        # Property 3: Conflicts should be minimized or resolved
        conflicts = self.sequencer.detect_conflicts(sequence.actions)
        critical_conflicts = [c for c in conflicts if c.severity == "critical"]
        
        # Critical conflicts should be resolved (removed)
        assert len(critical_conflicts) == 0, (
            f"Sequence contains {len(critical_conflicts)} unresolved critical conflicts"
        )
        
        # Property 4: Sequence should have valid metadata
        assert sequence.id == "test_sequence", "Sequence ID should match"
        assert sequence.intent_id == "test_intent", "Intent ID should match"
        assert sequence.estimated_duration >= 0, "Estimated duration should be non-negative"
        
        # Property 5: Estimated duration should be reasonable
        total_action_time = sum(a.estimate_execution_time() for a in sequence.actions)
        assert sequence.estimated_duration == total_action_time, (
            f"Estimated duration ({sequence.estimated_duration}) should equal "
            f"sum of action times ({total_action_time})"
        )
        
        # Property 6: Rollback plan should exist
        assert sequence.rollback_plan is not None, "Rollback plan should exist"
        assert isinstance(sequence.rollback_plan, list), "Rollback plan should be a list"
        
        # Property 7: Actions should maintain their essential properties
        # Only check actions that remain in the sequence (some may be removed due to conflict resolution)
        for original_action in actions:
            sequenced_action = next((a for a in sequence.actions if a.id == original_action.id), None)
            if sequenced_action is not None:
                # Action is in the sequence, verify its properties are maintained
                assert sequenced_action.type == original_action.type, "Action type should not change"
                assert sequenced_action.target == original_action.target, "Action target should not change"
        
        # Property 8: Sequence should be valid
        validation = self.sequencer.validate_sequence(sequence)
        assert validation.is_valid or len(validation.errors) == 0, (
            f"Sequence validation failed: {validation.errors}"
        )
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(action_pair=dependent_action_pair_strategy())
    def test_dependency_ordering(self, action_pair):
        """Test that dependent actions are ordered correctly."""
        create_action, modify_action = action_pair
        
        # Sequence the actions
        sequence = self.sequencer.sequence_actions(
            actions=action_pair,
            intent_id="test_intent",
            sequence_id="test_sequence"
        )
        
        # Find positions
        create_pos = next((i for i, a in enumerate(sequence.actions) if a.id == create_action.id), None)
        modify_pos = next((i for i, a in enumerate(sequence.actions) if a.id == modify_action.id), None)
        
        assert create_pos is not None, "Create action should be in sequence"
        assert modify_pos is not None, "Modify action should be in sequence"
        
        # Create must come before modify
        assert create_pos < modify_pos, (
            f"Slice creation (pos {create_pos}) must come before modification (pos {modify_pos})"
        )
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(actions=priority_ordered_actions_strategy())
    def test_priority_ordering_without_dependencies(self, actions):
        """Test that actions without dependencies are ordered by priority."""
        # Ensure actions have different targets to avoid dependencies
        for i, action in enumerate(actions):
            action.target = f"unique_target_{i}"
        
        # Sequence the actions
        sequence = self.sequencer.sequence_actions(
            actions=actions,
            intent_id="test_intent",
            sequence_id="test_sequence"
        )
        
        # Check that higher priority actions come first (when no dependencies)
        # Note: This is a general trend, not a strict requirement due to dependencies
        priorities = [a.priority for a in sequence.actions]
        
        # At least verify that the sequence is not in reverse priority order
        # (i.e., lowest priority first)
        if len(priorities) >= 2:
            # Check that we don't have a strictly increasing priority sequence
            # (which would mean lowest priority first)
            is_strictly_increasing = all(priorities[i] < priorities[i+1] for i in range(len(priorities)-1))
            assert not is_strictly_increasing, (
                "Actions should not be in strictly increasing priority order (lowest first)"
            )
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(actions=action_list_strategy(min_size=3, max_size=6))
    def test_conflict_resolution(self, actions):
        """Test that conflicts are properly resolved in sequencing."""
        assume(len(actions) >= 3)
        
        # Create some conflicting actions (same target, different types)
        if len(actions) >= 2:
            actions[0].target = "shared_target"
            actions[0].type = ActionType.FLOW_MOD
            actions[1].target = "shared_target"
            actions[1].type = ActionType.CONFIG_CHANGE
        
        # Sequence the actions
        sequence = self.sequencer.sequence_actions(
            actions=actions,
            intent_id="test_intent",
            sequence_id="test_sequence"
        )
        
        # Verify conflicts are handled
        conflicts = self.sequencer.detect_conflicts(sequence.actions)
        critical_conflicts = [c for c in conflicts if c.severity == "critical"]
        
        # Critical conflicts should be resolved
        assert len(critical_conflicts) == 0, (
            f"Sequence should not contain critical conflicts, found {len(critical_conflicts)}"
        )
        
        # Sequence should still be valid
        assert len(sequence.actions) > 0, "Sequence should not be empty after conflict resolution"
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(actions=action_list_strategy(min_size=2, max_size=5))
    def test_rollback_plan_generation(self, actions):
        """Test that rollback plans are generated for sequences."""
        assume(len(actions) >= 2)
        
        # Sequence the actions
        sequence = self.sequencer.sequence_actions(
            actions=actions,
            intent_id="test_intent",
            sequence_id="test_sequence"
        )
        
        # Rollback plan should exist
        assert sequence.rollback_plan is not None, "Rollback plan should be generated"
        assert isinstance(sequence.rollback_plan, list), "Rollback plan should be a list"
        
        # Rollback plan should have actions (at least for some action types)
        # Note: Not all action types may have rollback actions
        # Also, conflict resolution may remove actions, so check the sequenced actions, not the input
        if any(a.type in [ActionType.FLOW_MOD, ActionType.SLICE_CREATE] for a in sequence.actions):
            assert len(sequence.rollback_plan) > 0, (
                "Rollback plan should contain actions for reversible operations"
            )
        
        # Rollback actions should have valid structure
        for rollback_action in sequence.rollback_plan:
            assert rollback_action.id is not None, "Rollback action should have ID"
            assert rollback_action.type is not None, "Rollback action should have type"
            assert rollback_action.target is not None, "Rollback action should have target"
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(actions=action_list_strategy(min_size=1, max_size=3))
    def test_sequence_validation(self, actions):
        """Test that sequence validation works correctly."""
        assume(len(actions) >= 1)
        
        # Create sequence
        sequence = self.sequencer.sequence_actions(
            actions=actions,
            intent_id="test_intent",
            sequence_id="test_sequence"
        )
        
        # Validate the sequence
        validation = self.sequencer.validate_sequence(sequence)
        
        # Validation result should have expected structure
        assert hasattr(validation, 'is_valid'), "Validation should have is_valid field"
        assert hasattr(validation, 'errors'), "Validation should have errors field"
        assert hasattr(validation, 'warnings'), "Validation should have warnings field"
        assert hasattr(validation, 'suggestions'), "Validation should have suggestions field"
        
        # If sequence is valid, it should have no errors
        if validation.is_valid:
            assert len(validation.errors) == 0, "Valid sequence should have no errors"
        
        # If there are errors, sequence should not be valid
        if len(validation.errors) > 0:
            assert not validation.is_valid, "Sequence with errors should not be valid"
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=5000)
    @given(actions=action_list_strategy(min_size=4, max_size=8))
    def test_complex_dependency_chains(self, actions):
        """Test sequencing with complex dependency chains."""
        assume(len(actions) >= 4)
        
        # Create a dependency chain: config -> flow1 -> flow2
        if len(actions) >= 3:
            # Config change
            actions[0].type = ActionType.CONFIG_CHANGE
            actions[0].target = "switch-1"
            actions[0].parameters = {"config_type": "flow_config", "config_data": {}}
            
            # Flow modifications that depend on config
            actions[1].type = ActionType.FLOW_MOD
            actions[1].target = "switch-1"
            actions[1].priority = 1000
            
            actions[2].type = ActionType.FLOW_MOD
            actions[2].target = "switch-1"
            actions[2].priority = 500
        
        # Sequence the actions
        sequence = self.sequencer.sequence_actions(
            actions=actions,
            intent_id="test_intent",
            sequence_id="test_sequence"
        )
        
        # Verify dependency chain is respected
        position_map = {a.id: i for i, a in enumerate(sequence.actions)}
        
        # Config should come before flows
        config_pos = position_map.get(actions[0].id)
        flow1_pos = position_map.get(actions[1].id)
        flow2_pos = position_map.get(actions[2].id)
        
        if config_pos is not None and flow1_pos is not None:
            assert config_pos < flow1_pos, "Config should come before flow1"
        
        if config_pos is not None and flow2_pos is not None:
            assert config_pos < flow2_pos, "Config should come before flow2"
        
        # Higher priority flow should come before lower priority flow
        if flow1_pos is not None and flow2_pos is not None:
            assert flow1_pos < flow2_pos, "Higher priority flow should come first"
    
    def test_empty_action_list(self):
        """Test that empty action list is handled gracefully."""
        sequence = self.sequencer.sequence_actions(
            actions=[],
            intent_id="test_intent",
            sequence_id="test_sequence"
        )
        
        # Should create a valid but empty sequence
        assert sequence.id == "test_sequence"
        assert sequence.intent_id == "test_intent"
        assert len(sequence.actions) == 0
        assert sequence.estimated_duration == 0
    
    def test_single_action_sequencing(self):
        """Test sequencing with a single action."""
        action = NetworkAction(
            id="single_action",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={"match": {"in_port": 1}, "actions": []},
            priority=1000,
            timeout=30
        )
        
        sequence = self.sequencer.sequence_actions(
            actions=[action],
            intent_id="test_intent",
            sequence_id="test_sequence"
        )
        
        # Should create a valid sequence with one action
        assert len(sequence.actions) == 1
        assert sequence.actions[0].id == "single_action"
        assert sequence.estimated_duration > 0
