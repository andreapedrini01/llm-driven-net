"""Unit tests for action sequencer service."""

import pytest
from src.services.action_sequencer import (
    ActionSequencer,
    ActionDependency,
    ActionConflict
)
from src.models.actions import NetworkAction, ActionType, ActionSequence


class TestActionSequencer:
    """Test suite for ActionSequencer."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sequencer = ActionSequencer()
    
    def test_analyze_dependencies_slice_creation_before_modification(self):
        """Test that slice modification depends on slice creation."""
        create_action = NetworkAction(
            id="create_slice_1",
            type=ActionType.SLICE_CREATE,
            target="slice-a",
            parameters={"slice_name": "slice-a", "resources": {}}
        )
        
        modify_action = NetworkAction(
            id="modify_slice_1",
            type=ActionType.SLICE_MODIFY,
            target="slice-a",
            parameters={"slice_name": "slice-a"}
        )
        
        dependencies, dep_map = self.sequencer.analyze_dependencies([create_action, modify_action])
        
        assert len(dependencies) == 1
        assert dependencies[0].action_id == "modify_slice_1"
        assert dependencies[0].depends_on == "create_slice_1"
        assert "modify_slice_1" in dep_map
        assert "create_slice_1" in dep_map["modify_slice_1"]
    
    def test_analyze_dependencies_flow_priority_ordering(self):
        """Test that lower priority flows depend on higher priority flows."""
        high_priority_flow = NetworkAction(
            id="flow_high",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            priority=1000,
            parameters={"match": {}, "actions": []}
        )
        
        low_priority_flow = NetworkAction(
            id="flow_low",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            priority=500,
            parameters={"match": {}, "actions": []}
        )
        
        dependencies, dep_map = self.sequencer.analyze_dependencies([high_priority_flow, low_priority_flow])
        
        assert len(dependencies) == 1
        assert dependencies[0].action_id == "flow_low"
        assert dependencies[0].depends_on == "flow_high"
    
    def test_analyze_dependencies_config_before_action(self):
        """Test that actions depend on relevant config changes."""
        config_action = NetworkAction(
            id="config_1",
            type=ActionType.CONFIG_CHANGE,
            target="switch-1",
            parameters={"config_type": "flow_config", "config_data": {}}
        )
        
        flow_action = NetworkAction(
            id="flow_1",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={"match": {}, "actions": []}
        )
        
        dependencies, dep_map = self.sequencer.analyze_dependencies([flow_action, config_action])
        
        assert len(dependencies) == 1
        assert dependencies[0].action_id == "flow_1"
        assert dependencies[0].depends_on == "config_1"
    
    def test_detect_conflicts_same_target_same_type(self):
        """Test conflict detection for same target and type."""
        action1 = NetworkAction(
            id="action_1",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={}
        )
        
        action2 = NetworkAction(
            id="action_2",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={}
        )
        
        conflicts = self.sequencer.detect_conflicts([action1, action2])
        
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "resource"
        assert conflicts[0].severity == "medium"
    
    def test_detect_conflicts_same_target_different_type(self):
        """Test conflict detection for same target, different types."""
        action1 = NetworkAction(
            id="action_1",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={}
        )
        
        action2 = NetworkAction(
            id="action_2",
            type=ActionType.CONFIG_CHANGE,
            target="switch-1",
            parameters={}
        )
        
        conflicts = self.sequencer.detect_conflicts([action1, action2])
        
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "resource"
        assert conflicts[0].severity == "high"
    
    def test_detect_conflicts_overlapping_flows(self):
        """Test conflict detection for overlapping flow rules."""
        action1 = NetworkAction(
            id="flow_1",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={
                "match": {"in_port": 1, "eth_type": 0x0800},
                "actions": []
            }
        )
        
        action2 = NetworkAction(
            id="flow_2",
            type=ActionType.FLOW_MOD,
            target="switch-2",
            parameters={
                "match": {"in_port": 1, "eth_type": 0x0800},
                "actions": []
            }
        )
        
        conflicts = self.sequencer.detect_conflicts([action1, action2])
        
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "logical"
        assert "overlapping" in conflicts[0].description.lower()
    
    def test_detect_conflicts_competing_slice_resources(self):
        """Test conflict detection for slices competing for resources."""
        action1 = NetworkAction(
            id="slice_1",
            type=ActionType.SLICE_CREATE,
            target="slice-a",
            parameters={
                "slice_name": "slice-a",
                "resources": {"switches": ["switch-1", "switch-2"]}
            }
        )
        
        action2 = NetworkAction(
            id="slice_2",
            type=ActionType.SLICE_CREATE,
            target="slice-b",
            parameters={
                "slice_name": "slice-b",
                "resources": {"switches": ["switch-2", "switch-3"]}
            }
        )
        
        conflicts = self.sequencer.detect_conflicts([action1, action2])
        
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "resource"
        assert conflicts[0].severity == "high"
    
    def test_resolve_conflicts_removes_lower_priority(self):
        """Test that conflict resolution removes lower priority actions."""
        action1 = NetworkAction(
            id="action_1",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            priority=1000,
            parameters={}
        )
        
        action2 = NetworkAction(
            id="action_2",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            priority=500,
            parameters={}
        )
        
        conflict = ActionConflict(
            "action_1",
            "action_2",
            "resource",
            "critical",
            "Critical conflict"
        )
        
        resolved, notes = self.sequencer.resolve_conflicts([action1, action2], [conflict])
        
        assert len(resolved) == 1
        assert resolved[0].id == "action_1"
        assert any("action_2" in note and "removed" in note.lower() for note in notes)
    
    def test_resolve_conflicts_adjusts_priority(self):
        """Test that conflict resolution adjusts priorities."""
        action1 = NetworkAction(
            id="action_1",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            priority=1000,
            parameters={}
        )
        
        action2 = NetworkAction(
            id="action_2",
            type=ActionType.CONFIG_CHANGE,
            target="switch-1",
            priority=1000,
            parameters={}
        )
        
        conflict = ActionConflict(
            "action_1",
            "action_2",
            "resource",
            "high",
            "High severity conflict"
        )
        
        resolved, notes = self.sequencer.resolve_conflicts([action1, action2], [conflict])
        
        assert len(resolved) == 2
        assert any("priority" in note.lower() for note in notes)
    
    def test_optimize_sequence_respects_dependencies(self):
        """Test that optimization respects dependencies."""
        action1 = NetworkAction(
            id="action_1",
            type=ActionType.SLICE_CREATE,
            target="slice-a",
            priority=500,
            parameters={"slice_name": "slice-a"}
        )
        
        action2 = NetworkAction(
            id="action_2",
            type=ActionType.SLICE_MODIFY,
            target="slice-a",
            priority=1000,
            parameters={"slice_name": "slice-a"}
        )
        
        dependency_map = {"action_2": ["action_1"]}
        
        optimized = self.sequencer.optimize_sequence([action1, action2], dependency_map)
        
        assert len(optimized) == 2
        assert optimized[0].id == "action_1"
        assert optimized[1].id == "action_2"
    
    def test_optimize_sequence_orders_by_priority(self):
        """Test that optimization orders by priority when no dependencies."""
        action1 = NetworkAction(
            id="action_1",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            priority=500,
            parameters={}
        )
        
        action2 = NetworkAction(
            id="action_2",
            type=ActionType.FLOW_MOD,
            target="switch-2",
            priority=1000,
            parameters={}
        )
        
        action3 = NetworkAction(
            id="action_3",
            type=ActionType.FLOW_MOD,
            target="switch-3",
            priority=750,
            parameters={}
        )
        
        optimized = self.sequencer.optimize_sequence([action1, action2, action3], {})
        
        assert len(optimized) == 3
        assert optimized[0].id == "action_2"  # Highest priority
        assert optimized[1].id == "action_3"
        assert optimized[2].id == "action_1"  # Lowest priority
    
    def test_sequence_actions_full_workflow(self):
        """Test the complete sequencing workflow."""
        actions = [
            NetworkAction(
                id="config_1",
                type=ActionType.CONFIG_CHANGE,
                target="switch-1",
                priority=1000,
                parameters={"config_type": "flow_config"}
            ),
            NetworkAction(
                id="flow_1",
                type=ActionType.FLOW_MOD,
                target="switch-1",
                priority=900,
                parameters={"match": {"in_port": 1}, "actions": []}
            ),
            NetworkAction(
                id="slice_create",
                type=ActionType.SLICE_CREATE,
                target="slice-a",
                priority=800,
                parameters={"slice_name": "slice-a", "resources": {}}
            ),
            NetworkAction(
                id="slice_modify",
                type=ActionType.SLICE_MODIFY,
                target="slice-a",
                priority=700,
                parameters={"slice_name": "slice-a"}
            )
        ]
        
        sequence = self.sequencer.sequence_actions(actions, "intent_123", "seq_123")
        
        assert sequence.id == "seq_123"
        assert sequence.intent_id == "intent_123"
        assert len(sequence.actions) == 4
        assert sequence.estimated_duration > 0
        
        # Verify ordering respects dependencies
        action_ids = [a.id for a in sequence.actions]
        assert action_ids.index("slice_create") < action_ids.index("slice_modify")
        assert action_ids.index("config_1") < action_ids.index("flow_1")
    
    def test_generate_rollback_plan(self):
        """Test rollback plan generation."""
        actions = [
            NetworkAction(
                id="flow_1",
                type=ActionType.FLOW_MOD,
                target="switch-1",
                parameters={"match": {"in_port": 1}, "actions": []}
            ),
            NetworkAction(
                id="slice_1",
                type=ActionType.SLICE_CREATE,
                target="slice-a",
                parameters={"slice_name": "slice-a"}
            )
        ]
        
        rollback = self.sequencer._generate_rollback_plan(actions)
        
        assert len(rollback) == 2
        # Rollback should be in reverse order
        assert "rollback_slice_1" in rollback[0].id
        assert "rollback_flow_1" in rollback[1].id
    
    def test_validate_sequence_empty_actions(self):
        """Test validation fails for empty sequence."""
        sequence = ActionSequence(
            id="seq_1",
            intent_id="intent_1",
            actions=[],
            estimated_duration=0
        )
        
        result = self.sequencer.validate_sequence(sequence)
        
        assert not result.is_valid
        assert any("empty" in error.lower() for error in result.errors)
    
    def test_validate_sequence_with_conflicts(self):
        """Test validation detects unresolved conflicts."""
        actions = [
            NetworkAction(
                id="action_1",
                type=ActionType.FLOW_MOD,
                target="switch-1",
                parameters={"match": {}, "actions": []}
            ),
            NetworkAction(
                id="action_2",
                type=ActionType.CONFIG_CHANGE,
                target="switch-1",
                parameters={"config_type": "test", "config_data": {}}
            )
        ]
        
        sequence = ActionSequence(
            id="seq_1",
            intent_id="intent_1",
            actions=actions,
            estimated_duration=10
        )
        
        result = self.sequencer.validate_sequence(sequence)
        
        # Should have warnings or errors about conflicts
        assert len(result.errors) > 0 or len(result.warnings) > 0
    
    def test_validate_sequence_suggests_rollback(self):
        """Test validation suggests rollback plan."""
        actions = [
            NetworkAction(
                id="action_1",
                type=ActionType.FLOW_MOD,
                target="switch-1",
                parameters={"match": {"in_port": 1}, "actions": []}
            )
        ]
        
        sequence = ActionSequence(
            id="seq_1",
            intent_id="intent_1",
            actions=actions,
            estimated_duration=5,
            rollback_plan=[]
        )
        
        result = self.sequencer.validate_sequence(sequence)
        
        assert any("rollback" in suggestion.lower() for suggestion in result.suggestions)
    
    def test_no_conflicts_for_different_targets(self):
        """Test that actions on different targets don't conflict."""
        action1 = NetworkAction(
            id="action_1",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={}
        )
        
        action2 = NetworkAction(
            id="action_2",
            type=ActionType.FLOW_MOD,
            target="switch-2",
            parameters={}
        )
        
        conflicts = self.sequencer.detect_conflicts([action1, action2])
        
        # Should have no conflicts (different targets, no overlapping flows)
        assert len(conflicts) == 0
    
    def test_optimize_handles_circular_dependencies(self):
        """Test that optimizer handles circular dependencies gracefully."""
        action1 = NetworkAction(
            id="action_1",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            priority=1000,
            parameters={}
        )
        
        action2 = NetworkAction(
            id="action_2",
            type=ActionType.FLOW_MOD,
            target="switch-2",
            priority=900,
            parameters={}
        )
        
        # Create circular dependency
        dependency_map = {
            "action_1": ["action_2"],
            "action_2": ["action_1"]
        }
        
        optimized = self.sequencer.optimize_sequence([action1, action2], dependency_map)
        
        # Should fall back to priority ordering
        assert len(optimized) == 2
        assert optimized[0].priority >= optimized[1].priority
