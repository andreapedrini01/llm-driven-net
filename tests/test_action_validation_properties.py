"""Property-based tests for action validation functionality."""

import pytest
from hypothesis import given, strategies as st, assume, settings
from datetime import datetime
from typing import Dict, Any, List
from src.models.actions import (
    NetworkAction, ActionType, ActionSequence,
    ValidationResult, SafetyReport, SimulationResult
)


class TestActionValidationProperties:
    """Property-based tests for action validation and formatting."""
    
    # Generator strategies for test data
    @staticmethod
    @st.composite
    def valid_action_id(draw):
        """Generate valid action IDs."""
        # Valid characters: alphanumeric, underscore, hyphen
        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-'
        length = draw(st.integers(min_value=1, max_value=50))
        return ''.join(draw(st.lists(st.sampled_from(chars), min_size=length, max_size=length)))
    
    @staticmethod
    @st.composite
    def valid_target(draw):
        """Generate valid target identifiers."""
        # Valid formats: switch-1, 192.168.1.1, switch:port, etc.
        target_types = [
            # Switch names
            lambda: f"switch-{draw(st.integers(min_value=1, max_value=100))}",
            # IP addresses (simplified)
            lambda: f"192.168.{draw(st.integers(min_value=1, max_value=255))}.{draw(st.integers(min_value=1, max_value=255))}",
            # Switch:port format
            lambda: f"sw{draw(st.integers(min_value=1, max_value=10))}:port{draw(st.integers(min_value=1, max_value=48))}",
            # Host names
            lambda: f"host_{draw(st.integers(min_value=1, max_value=100))}",
            # Router names
            lambda: f"router-{draw(st.integers(min_value=1, max_value=50))}"
        ]
        
        target_generator = draw(st.sampled_from(target_types))
        return target_generator()
    
    @staticmethod
    @st.composite
    def flow_mod_parameters(draw):
        """Generate valid flow modification parameters."""
        match_fields = {}
        actions_list = []
        
        # Generate match fields
        if draw(st.booleans()):
            match_fields['in_port'] = draw(st.integers(min_value=1, max_value=48))
        if draw(st.booleans()):
            match_fields['eth_type'] = draw(st.sampled_from([0x0800, 0x0806, 0x86dd]))  # IP, ARP, IPv6
        if draw(st.booleans()):
            match_fields['ip_src'] = f"10.0.{draw(st.integers(min_value=1, max_value=255))}.{draw(st.integers(min_value=1, max_value=255))}"
        if draw(st.booleans()):
            match_fields['tcp_dst'] = draw(st.integers(min_value=1, max_value=65535))
        
        # Generate actions
        action_types = ['output', 'drop', 'set_field', 'push_vlan']
        for _ in range(draw(st.integers(min_value=1, max_value=3))):
            action_type = draw(st.sampled_from(action_types))
            if action_type == 'output':
                actions_list.append({'output': draw(st.integers(min_value=1, max_value=48))})
            elif action_type == 'drop':
                actions_list.append({'drop': True})
            elif action_type == 'set_field':
                actions_list.append({'set_field': {'eth_dst': 'aa:bb:cc:dd:ee:ff'}})
            elif action_type == 'push_vlan':
                actions_list.append({'push_vlan': draw(st.integers(min_value=1, max_value=4094))})
        
        return {
            'match': match_fields,
            'actions': actions_list
        }
    
    @staticmethod
    @st.composite
    def slice_create_parameters(draw):
        """Generate valid slice creation parameters."""
        return {
            'slice_name': f"slice_{draw(st.integers(min_value=1, max_value=1000))}",
            'resources': {
                'bandwidth': draw(st.integers(min_value=10, max_value=10000)),
                'switches': [f"sw{i}" for i in range(1, draw(st.integers(min_value=2, max_value=5)))],
                'priority': draw(st.integers(min_value=1, max_value=10))
            },
            'sla': {
                'latency_max': draw(st.floats(min_value=1.0, max_value=100.0)),
                'availability': draw(st.floats(min_value=0.9, max_value=0.999))
            }
        }
    
    @staticmethod
    @st.composite
    def config_change_parameters(draw):
        """Generate valid configuration change parameters."""
        config_types = ['qos', 'routing', 'security', 'monitoring']
        config_type = draw(st.sampled_from(config_types))
        
        config_data = {}
        if config_type == 'qos':
            config_data = {
                'bandwidth_limit': draw(st.integers(min_value=1, max_value=10000)),
                'priority_class': draw(st.integers(min_value=1, max_value=8))
            }
        elif config_type == 'routing':
            config_data = {
                'destination': f"10.0.{draw(st.integers(min_value=1, max_value=255))}.0/24",
                'next_hop': f"10.0.0.{draw(st.integers(min_value=1, max_value=255))}"
            }
        elif config_type == 'security':
            config_data = {
                'access_control': draw(st.sampled_from(['allow', 'deny'])),
                'protocol': draw(st.sampled_from(['tcp', 'udp', 'icmp']))
            }
        elif config_type == 'monitoring':
            config_data = {
                'sampling_rate': draw(st.floats(min_value=0.01, max_value=1.0)),
                'metrics': draw(st.lists(st.sampled_from(['bandwidth', 'latency', 'packet_loss']), min_size=1, max_size=3))
            }
        
        return {
            'config_type': config_type,
            'config_data': config_data
        }
    
    @staticmethod
    @st.composite
    def network_action(draw):
        """Generate a valid NetworkAction."""
        action_type = draw(st.sampled_from(list(ActionType)))
        
        # Generate appropriate parameters based on action type
        if action_type == ActionType.FLOW_MOD:
            parameters = draw(TestActionValidationProperties.flow_mod_parameters())
        elif action_type == ActionType.SLICE_CREATE:
            parameters = draw(TestActionValidationProperties.slice_create_parameters())
        elif action_type == ActionType.SLICE_MODIFY:
            parameters = draw(TestActionValidationProperties.slice_create_parameters())
            parameters['slice_id'] = f"slice_{draw(st.integers(min_value=1, max_value=100))}"
        elif action_type == ActionType.CONFIG_CHANGE:
            parameters = draw(TestActionValidationProperties.config_change_parameters())
        else:
            parameters = {}
        
        return NetworkAction(
            id=draw(TestActionValidationProperties.valid_action_id()),
            type=action_type,
            target=draw(TestActionValidationProperties.valid_target()),
            parameters=parameters,
            priority=draw(st.integers(min_value=1, max_value=65535)),
            timeout=draw(st.integers(min_value=1, max_value=3600)),
            description=draw(st.text(min_size=0, max_size=200))
        )
    
    @staticmethod
    @st.composite
    def action_sequence(draw):
        """Generate a valid ActionSequence."""
        actions = draw(st.lists(
            TestActionValidationProperties.network_action(),
            min_size=1,
            max_size=10
        ))
        
        # Ensure unique action IDs
        used_ids = set()
        unique_actions = []
        for action in actions:
            if action.id not in used_ids:
                unique_actions.append(action)
                used_ids.add(action.id)
        
        if not unique_actions:
            # Fallback: create at least one action
            unique_actions = [draw(TestActionValidationProperties.network_action())]
        
        estimated_duration = sum(action.estimate_execution_time() for action in unique_actions)
        
        return ActionSequence(
            id=draw(TestActionValidationProperties.valid_action_id()),
            intent_id=draw(TestActionValidationProperties.valid_action_id()),
            actions=unique_actions,
            estimated_duration=estimated_duration,
            dependencies=draw(st.lists(
                TestActionValidationProperties.valid_action_id(),
                min_size=0,
                max_size=3
            ))
        )
    
    @settings(max_examples=100)
    @given(action_sequence=action_sequence())
    def test_action_validation_and_formatting(self, action_sequence):
        """
        **Feature: llm-integration-module, Property 8: Action validation and formatting**
        
        For any generated NetworkAction sequence, all actions should be syntactically 
        and semantically valid and formatted according to the Northbound_Script 
        interface specification.
        
        **Validates: Requirements 3.1, 3.3**
        """
        # Ensure we have a valid action sequence
        assume(action_sequence is not None)
        assume(len(action_sequence.actions) > 0)
        
        # Test individual action validation (Requirement 3.1)
        for action in action_sequence.actions:
            # Verify basic syntax validation
            assert action.id is not None and len(action.id) > 0
            assert isinstance(action.type, ActionType)
            assert action.target is not None and len(action.target) > 0
            assert isinstance(action.parameters, dict)
            assert 1 <= action.priority <= 65535
            assert 1 <= action.timeout <= 3600
            
            # Verify semantic validation based on action type
            validation_result = action.validate_action_parameters()
            assert isinstance(validation_result, dict)
            assert 'is_valid' in validation_result
            assert 'issues' in validation_result
            assert 'warnings' in validation_result
            assert isinstance(validation_result['issues'], list)
            assert isinstance(validation_result['warnings'], list)
            
            # For valid actions, validation should pass
            if validation_result['is_valid']:
                # Valid actions should have proper parameters for their type
                if action.type == ActionType.FLOW_MOD:
                    assert 'match' in action.parameters or 'actions' in action.parameters
                elif action.type == ActionType.SLICE_CREATE:
                    assert 'slice_name' in action.parameters
                    assert 'resources' in action.parameters
                elif action.type == ActionType.CONFIG_CHANGE:
                    assert 'config_type' in action.parameters
                    assert 'config_data' in action.parameters
            
            # Test Northbound Script formatting (Requirement 3.3)
            northbound_format = action.to_northbound_format()
            assert isinstance(northbound_format, dict)
            
            # Verify required Northbound Script fields
            required_fields = [
                'action_id', 'action_type', 'target_resource', 
                'parameters', 'execution_priority', 'timeout_seconds', 'description'
            ]
            for field in required_fields:
                assert field in northbound_format, f"Missing required field: {field}"
            
            # Verify field types and values
            assert northbound_format['action_id'] == action.id
            assert northbound_format['action_type'] == action.type.value
            assert northbound_format['target_resource'] == action.target
            assert northbound_format['parameters'] == action.parameters
            assert northbound_format['execution_priority'] == action.priority
            assert northbound_format['timeout_seconds'] == action.timeout
            assert isinstance(northbound_format['description'], str)
            
            # Verify execution time estimation is reasonable
            estimated_time = action.estimate_execution_time()
            assert isinstance(estimated_time, int)
            assert 0 < estimated_time <= action.timeout
        
        # Test sequence-level validation
        sequence_validation = action_sequence.validate_sequence_integrity()
        assert isinstance(sequence_validation, dict)
        assert 'is_valid' in sequence_validation
        assert 'issues' in sequence_validation
        assert 'warnings' in sequence_validation
        assert 'action_count' in sequence_validation
        assert 'unique_targets' in sequence_validation
        assert 'has_rollback' in sequence_validation
        
        # Verify sequence properties
        assert sequence_validation['action_count'] == len(action_sequence.actions)
        assert sequence_validation['action_count'] > 0
        
        # Test sequence Northbound formatting
        sequence_northbound = action_sequence.to_northbound_format()
        assert isinstance(sequence_northbound, dict)
        
        # Verify required sequence fields
        sequence_required_fields = [
            'sequence_id', 'source_intent', 'actions', 
            'execution_metadata', 'rollback_actions'
        ]
        for field in sequence_required_fields:
            assert field in sequence_northbound, f"Missing required sequence field: {field}"
        
        # Verify sequence field values
        assert sequence_northbound['sequence_id'] == action_sequence.id
        assert sequence_northbound['source_intent'] == action_sequence.intent_id
        assert isinstance(sequence_northbound['actions'], list)
        assert len(sequence_northbound['actions']) == len(action_sequence.actions)
        assert isinstance(sequence_northbound['execution_metadata'], dict)
        assert isinstance(sequence_northbound['rollback_actions'], list)
        
        # Verify execution metadata
        metadata = sequence_northbound['execution_metadata']
        assert 'estimated_duration_seconds' in metadata
        assert 'dependencies' in metadata
        assert 'total_actions' in metadata
        assert metadata['estimated_duration_seconds'] == action_sequence.estimated_duration
        assert metadata['dependencies'] == action_sequence.dependencies
        assert metadata['total_actions'] == len(action_sequence.actions)
        
        # Verify all actions in sequence are properly formatted
        for i, action_format in enumerate(sequence_northbound['actions']):
            original_action = action_sequence.actions[i]
            expected_format = original_action.to_northbound_format()
            assert action_format == expected_format
        
        # Test execution order generation
        execution_order = action_sequence.get_execution_order()
        assert isinstance(execution_order, list)
        assert len(execution_order) == len(action_sequence.actions)
        
        # Verify execution order is properly sorted (higher priority first)
        for i in range(len(execution_order) - 1):
            current_action = execution_order[i]
            next_action = execution_order[i + 1]
            # Higher priority should come first, or same priority with shorter execution time
            assert (current_action.priority >= next_action.priority)
    
    @settings(max_examples=50)
    @given(action=network_action())
    def test_individual_action_validation(self, action):
        """Test validation of individual NetworkActions."""
        assume(action is not None)
        
        # Test parameter validation
        validation_result = action.validate_action_parameters()
        assert isinstance(validation_result, dict)
        assert isinstance(validation_result['is_valid'], bool)
        assert isinstance(validation_result['issues'], list)
        assert isinstance(validation_result['warnings'], list)
        
        # Test Northbound formatting
        northbound_format = action.to_northbound_format()
        assert isinstance(northbound_format, dict)
        
        # Verify all required fields are present and correctly typed
        assert isinstance(northbound_format['action_id'], str)
        assert isinstance(northbound_format['action_type'], str)
        assert isinstance(northbound_format['target_resource'], str)
        assert isinstance(northbound_format['parameters'], dict)
        assert isinstance(northbound_format['execution_priority'], int)
        assert isinstance(northbound_format['timeout_seconds'], int)
        assert isinstance(northbound_format['description'], str)
        
        # Verify values match original action
        assert northbound_format['action_id'] == action.id
        assert northbound_format['action_type'] == action.type.value
        assert northbound_format['target_resource'] == action.target
        assert northbound_format['parameters'] == action.parameters
        assert northbound_format['execution_priority'] == action.priority
        assert northbound_format['timeout_seconds'] == action.timeout
    
    def test_invalid_action_handling(self):
        """Test that invalid actions are properly rejected."""
        # Test invalid action ID
        with pytest.raises(ValueError, match="Action ID must be a non-empty string"):
            NetworkAction(
                id="",
                type=ActionType.FLOW_MOD,
                target="switch-1",
                parameters={}
            )
        
        # Test invalid target
        with pytest.raises(ValueError, match="Target must be a non-empty string"):
            NetworkAction(
                id="action-1",
                type=ActionType.FLOW_MOD,
                target="",
                parameters={}
            )
        
        # Test invalid priority
        with pytest.raises(ValueError, match="Priority must be an integer between 0 and 65535"):
            NetworkAction(
                id="action-1",
                type=ActionType.FLOW_MOD,
                target="switch-1",
                parameters={},
                priority=70000
            )
        
        # Test invalid timeout
        with pytest.raises(ValueError, match="Timeout must be an integer between 1 and 3600 seconds"):
            NetworkAction(
                id="action-1",
                type=ActionType.FLOW_MOD,
                target="switch-1",
                parameters={},
                timeout=0
            )
    
    def test_action_sequence_validation_edge_cases(self):
        """Test edge cases in action sequence validation."""
        # Test empty action sequence - this should be allowed by the model
        # but validation should catch it
        empty_sequence = ActionSequence(
            id="seq-1",
            intent_id="intent-1",
            actions=[],
            estimated_duration=0
        )
        
        # The sequence validation should indicate issues with empty actions
        validation_result = empty_sequence.validate_sequence_integrity()
        assert isinstance(validation_result, dict)
        assert validation_result['action_count'] == 0
        
        # Test duplicate action IDs
        action1 = NetworkAction(
            id="duplicate-id",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={}
        )
        action2 = NetworkAction(
            id="duplicate-id",
            type=ActionType.CONFIG_CHANGE,
            target="switch-2",
            parameters={}
        )
        
        with pytest.raises(ValueError, match="Duplicate action IDs are not allowed"):
            ActionSequence(
                id="seq-1",
                intent_id="intent-1",
                actions=[action1, action2],
                estimated_duration=60
            )