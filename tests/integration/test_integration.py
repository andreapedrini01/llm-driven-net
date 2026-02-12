"""Integration tests for the LLM integration module components."""

import pytest
from datetime import datetime
from src.models.intent import IntentObject, IntentType, Entity
from src.models.actions import NetworkAction, ActionType, ActionSequence
from src.models.network import NetworkState, Topology, NetworkMetrics, BandwidthMetrics, LatencyMetrics, UtilizationMetrics
from src.models.slices import NetworkSlice, SliceStatus, ServiceLevelAgreement, SliceResources
from src.services.intent_parser import IntentParser


class TestSystemIntegration:
    """Integration tests for the complete system workflow."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = IntentParser()
    
    def test_complete_intent_to_action_workflow(self):
        """Test the complete workflow from intent parsing to action generation."""
        
        # 1. Parse a natural language intent
        intent_text = "Create a new network slice for tenant A with high priority and 1000 Mbps bandwidth"
        parsed_intent = self.parser.parse_intent(intent_text)
        
        # Verify intent parsing worked
        assert isinstance(parsed_intent, IntentObject)
        assert parsed_intent.raw_text == intent_text
        assert parsed_intent.intent_type == IntentType.CONFIGURATION
        assert parsed_intent.confidence > 0.5
        
        # Verify entities were extracted
        assert len(parsed_intent.entities) > 0
        entity_types = [entity.type for entity in parsed_intent.entities]
        assert 'action' in entity_types  # "create"
        # Note: entity types may vary based on parsing implementation
        
        # 2. Create a network state for context
        topology = Topology()
        
        bandwidth_metrics = BandwidthMetrics(
            total_capacity=10000,
            used_bandwidth=3000,
            available_bandwidth=7000,
            utilization_percentage=30.0
        )
        
        latency_metrics = LatencyMetrics(
            average_latency=5.2,
            min_latency=1.0,
            max_latency=15.0,
            jitter=2.1
        )
        
        utilization_metrics = UtilizationMetrics(
            cpu_utilization=45.0,
            memory_utilization=60.0
        )
        
        network_metrics = NetworkMetrics(
            bandwidth=bandwidth_metrics,
            latency=latency_metrics,
            utilization=utilization_metrics
        )
        
        network_state = NetworkState(
            timestamp=datetime.now(),
            topology=topology,
            metrics=network_metrics
        )
        
        # Verify network state is valid
        assert network_state.metrics.bandwidth.available_bandwidth == 7000
        assert network_state.metrics.utilization.cpu_utilization == 45.0
        
        # 3. Generate actions based on the intent
        # Simulate action generation (this would normally be done by the Action Generator component)
        slice_action = NetworkAction(
            id="slice-create-001",
            type=ActionType.SLICE_CREATE,
            target="network-controller",
            parameters={
                'slice_name': 'tenant_a_slice',
                'resources': {
                    'bandwidth': 1000,
                    'switches': ['sw1', 'sw2', 'sw3'],
                    'priority': 'high'
                },
                'sla': {
                    'latency_max': 10.0,
                    'availability': 0.99
                }
            },
            priority=8000,  # High priority
            timeout=120,
            description="Create network slice for tenant A with high priority"
        )
        
        # 4. Validate the generated action
        validation_result = slice_action.validate_action_parameters()
        assert validation_result['is_valid'] == True
        assert len(validation_result['issues']) == 0
        
        # Verify action parameters are correct for slice creation
        assert 'slice_name' in slice_action.parameters
        assert 'resources' in slice_action.parameters
        assert slice_action.parameters['resources']['bandwidth'] == 1000
        assert slice_action.parameters['resources']['priority'] == 'high'
        
        # 5. Create an action sequence
        action_sequence = ActionSequence(
            id="seq-tenant-a-slice",
            intent_id=parsed_intent.id,
            actions=[slice_action],
            estimated_duration=slice_action.estimate_execution_time(),
            dependencies=[]
        )
        
        # Verify sequence integrity
        sequence_validation = action_sequence.validate_sequence_integrity()
        assert sequence_validation['is_valid'] == True
        assert sequence_validation['action_count'] == 1
        assert sequence_validation['unique_targets'] == 1
        
        # 6. Format for Northbound Script
        northbound_format = action_sequence.to_northbound_format()
        
        # Verify Northbound formatting
        assert northbound_format['sequence_id'] == action_sequence.id
        assert northbound_format['source_intent'] == parsed_intent.id
        assert len(northbound_format['actions']) == 1
        
        action_format = northbound_format['actions'][0]
        assert action_format['action_type'] == 'slice_create'
        assert action_format['target_resource'] == 'network-controller'
        assert action_format['parameters']['slice_name'] == 'tenant_a_slice'
        
        # 7. Verify the complete workflow maintains data integrity
        assert action_sequence.intent_id == parsed_intent.id
        assert action_format['action_id'] == slice_action.id
        
        print("✅ Complete workflow test passed!")
        print(f"   Intent: {parsed_intent.raw_text}")
        print(f"   Confidence: {parsed_intent.confidence:.2f}")
        print(f"   Entities: {len(parsed_intent.entities)}")
        print(f"   Action: {slice_action.type.value}")
        print(f"   Target: {slice_action.target}")
        print(f"   Validation: {'✅ Valid' if validation_result['is_valid'] else '❌ Invalid'}")
    
    def test_multiple_actions_workflow(self):
        """Test workflow with multiple related actions."""
        
        # Parse intent for multiple actions
        intent_text = "Configure QoS policies and create monitoring rules for the web service slice"
        parsed_intent = self.parser.parse_intent(intent_text)
        
        assert isinstance(parsed_intent, IntentObject)
        assert parsed_intent.confidence > 0.3
        
        # Create multiple related actions
        qos_action = NetworkAction(
            id="qos-config-001",
            type=ActionType.CONFIG_CHANGE,
            target="switch-1",
            parameters={
                'config_type': 'qos',
                'config_data': {
                    'bandwidth_limit': 5000,
                    'priority_class': 3
                }
            },
            priority=7000,
            timeout=60
        )
        
        monitoring_action = NetworkAction(
            id="monitor-config-001",
            type=ActionType.CONFIG_CHANGE,
            target="monitoring-server",
            parameters={
                'config_type': 'monitoring',
                'config_data': {
                    'sampling_rate': 0.1,
                    'metrics': ['bandwidth', 'latency', 'packet_loss']
                }
            },
            priority=6000,
            timeout=30
        )
        
        # Validate both actions
        qos_validation = qos_action.validate_action_parameters()
        monitor_validation = monitoring_action.validate_action_parameters()
        
        assert qos_validation['is_valid'] == True
        assert monitor_validation['is_valid'] == True
        
        # Create sequence with dependencies
        action_sequence = ActionSequence(
            id="seq-web-service-config",
            intent_id=parsed_intent.id,
            actions=[qos_action, monitoring_action],
            estimated_duration=qos_action.estimate_execution_time() + monitoring_action.estimate_execution_time(),
            dependencies=[]
        )
        
        # Verify sequence
        sequence_validation = action_sequence.validate_sequence_integrity()
        assert sequence_validation['is_valid'] == True
        assert sequence_validation['action_count'] == 2
        assert sequence_validation['unique_targets'] == 2
        
        # Test execution order
        execution_order = action_sequence.get_execution_order()
        assert len(execution_order) == 2
        # QoS should come first (higher priority)
        assert execution_order[0].priority >= execution_order[1].priority
        
        print("✅ Multiple actions workflow test passed!")
        print(f"   Actions: {len(action_sequence.actions)}")
        print(f"   Execution order: {[action.id for action in execution_order]}")
    
    def test_error_handling_workflow(self):
        """Test error handling in the workflow."""
        
        # Test with invalid action parameters
        invalid_action = NetworkAction(
            id="invalid-action",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={
                # Missing required 'match' and 'actions' for flow_mod
                'invalid_param': 'test'
            }
        )
        
        # Validation should catch the issues
        validation_result = invalid_action.validate_action_parameters()
        assert validation_result['is_valid'] == False
        assert len(validation_result['issues']) > 0
        assert "Flow modification requires 'match' parameters" in validation_result['issues']
        assert "Flow modification requires 'actions' parameters" in validation_result['issues']
        
        # Test with invalid sequence (duplicate IDs)
        action1 = NetworkAction(
            id="duplicate-id",
            type=ActionType.CONFIG_CHANGE,
            target="switch-1",
            parameters={'config_type': 'qos', 'config_data': {}}
        )
        
        action2 = NetworkAction(
            id="duplicate-id",  # Same ID
            type=ActionType.CONFIG_CHANGE,
            target="switch-2",
            parameters={'config_type': 'security', 'config_data': {}}
        )
        
        # Should raise error for duplicate IDs
        with pytest.raises(ValueError, match="Duplicate action IDs are not allowed"):
            ActionSequence(
                id="invalid-seq",
                intent_id="test-intent",
                actions=[action1, action2],
                estimated_duration=60
            )
        
        print("✅ Error handling workflow test passed!")
    
    def test_network_slice_integration(self):
        """Test integration with network slice components."""
        
        # Create a network slice
        sla = ServiceLevelAgreement(
            id="sla-001",
            min_bandwidth=1000,
            max_latency=10.0,
            availability=99.0,  # percentage
            packet_loss_threshold=1.0  # required field
        )
        
        resources = SliceResources(
            bandwidth=1500,
            cpu_allocation=50.0,
            memory_allocation=30.0
        )
        
        network_slice = NetworkSlice(
            id="slice-001",
            name="tenant_a_slice",
            tenant_id="tenant_a",
            status=SliceStatus.ACTIVE,
            sla=sla,
            resources=resources
        )
        
        # Verify slice is valid
        assert network_slice.id == "slice-001"
        assert network_slice.status == SliceStatus.ACTIVE
        assert network_slice.sla.min_bandwidth == 1000
        assert network_slice.resources.bandwidth == 1500
        
        # Create action to modify the slice
        modify_action = NetworkAction(
            id="slice-modify-001",
            type=ActionType.SLICE_MODIFY,
            target="network-controller",
            parameters={
                'slice_id': network_slice.id,
                'slice_name': network_slice.name,
                'resources': {
                    'bandwidth': 2000,  # Increase bandwidth
                    'switches': network_slice.resources.switches,
                    'priority': 'high'
                }
            }
        )
        
        # Validate the modification action
        validation_result = modify_action.validate_action_parameters()
        assert validation_result['is_valid'] == True
        
        # Verify Northbound formatting includes slice information
        northbound_format = modify_action.to_northbound_format()
        assert northbound_format['parameters']['slice_id'] == network_slice.id
        assert northbound_format['parameters']['resources']['bandwidth'] == 2000
        
        print("✅ Network slice integration test passed!")
        print(f"   Slice: {network_slice.name}")
        print(f"   Status: {network_slice.status.value}")
        print(f"   Bandwidth: {network_slice.resources.bandwidth} -> {northbound_format['parameters']['resources']['bandwidth']}")


if __name__ == "__main__":
    # Run integration tests
    test_suite = TestSystemIntegration()
    test_suite.setup_method()
    
    try:
        test_suite.test_complete_intent_to_action_workflow()
        test_suite.test_multiple_actions_workflow()
        test_suite.test_error_handling_workflow()
        test_suite.test_network_slice_integration()
        print("\n🎉 All integration tests passed successfully!")
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        raise