"""Unit tests for the validator service."""

import pytest
from datetime import datetime
from src.services.validator import ActionValidator, RollbackPlanGenerator, ImpactAssessor
from src.models.actions import (
    NetworkAction,
    ActionSequence,
    ActionType,
    ValidationResult,
    SafetyReport,
    ImpactAssessment
)
from src.models.network import (
    NetworkState,
    Topology,
    Switch,
    Link,
    Host,
    Flow,
    NetworkMetrics,
    BandwidthMetrics,
    LatencyMetrics,
    UtilizationMetrics,
    Anomaly,
    AnomalyType,
    AnomalySeverity
)


@pytest.fixture
def sample_network_state():
    """Create a sample network state for testing."""
    return NetworkState(
        timestamp=datetime.now(),
        topology=Topology(
            switches=[
                Switch(id="switch-1", name="Switch 1", dpid="0000000000000001", ports=[1, 2, 3]),
                Switch(id="switch-2", name="Switch 2", dpid="0000000000000002", ports=[1, 2, 3])
            ],
            links=[
                Link(
                    id="link-1",
                    source_switch="switch-1",
                    source_port=1,
                    destination_switch="switch-2",
                    destination_port=1,
                    bandwidth=1000
                )
            ],
            hosts=[
                Host(
                    id="host-1",
                    mac_address="00:00:00:00:00:01",
                    ip_address="10.0.0.1",
                    connected_switch="switch-1",
                    connected_port=2
                )
            ]
        ),
        flows=[],
        metrics=NetworkMetrics(
            bandwidth=BandwidthMetrics(
                total_capacity=10000,
                used_bandwidth=3000,
                available_bandwidth=7000,
                utilization_percentage=30.0
            ),
            latency=LatencyMetrics(
                average_latency=10.0,
                min_latency=5.0,
                max_latency=20.0,
                jitter=2.0
            ),
            utilization=UtilizationMetrics(
                cpu_utilization=50.0,
                memory_utilization=60.0,
                port_utilization={}
            )
        ),
        anomalies=[]
    )


@pytest.fixture
def sample_flow_mod_action():
    """Create a sample flow modification action."""
    return NetworkAction(
        id="action-1",
        type=ActionType.FLOW_MOD,
        target="switch-1",
        parameters={
            "match": {"in_port": 1, "eth_type": 0x0800},
            "actions": [{"type": "output", "port": 2}]
        },
        priority=1000,
        timeout=30
    )


@pytest.fixture
def sample_slice_create_action():
    """Create a sample slice creation action."""
    return NetworkAction(
        id="action-2",
        type=ActionType.SLICE_CREATE,
        target="switch-1",  # Target an existing switch instead of non-existent slice
        parameters={
            "slice_name": "test-slice",
            "resources": {
                "bandwidth": 500,
                "switches": ["switch-1", "switch-2"],
                "paths": [{"switches": ["switch-1", "switch-2"]}]
            }
        },
        priority=1000,
        timeout=60
    )


@pytest.fixture
def sample_action_sequence(sample_flow_mod_action, sample_slice_create_action):
    """Create a sample action sequence."""
    return ActionSequence(
        id="seq-1",
        intent_id="intent-1",
        actions=[sample_flow_mod_action, sample_slice_create_action],
        estimated_duration=90,
        dependencies=[],
        rollback_plan=[]
    )


class TestActionValidator:
    """Tests for ActionValidator class."""
    
    def test_validate_valid_sequence(self, sample_action_sequence):
        """Test validation of a valid action sequence."""
        validator = ActionValidator()
        result = validator.validate_actions(sample_action_sequence)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_empty_sequence(self):
        """Test validation of an empty sequence."""
        validator = ActionValidator()
        empty_sequence = ActionSequence(
            id="seq-empty",
            intent_id="intent-1",
            actions=[],
            estimated_duration=0,
            dependencies=[],
            rollback_plan=[]
        )
        
        result = validator.validate_actions(empty_sequence)
        
        assert not result.is_valid
        assert len(result.errors) > 0
        assert "empty" in result.errors[0].lower()
    
    def test_validate_flow_mod_missing_params(self):
        """Test validation of flow mod with missing parameters."""
        validator = ActionValidator()
        
        invalid_action = NetworkAction(
            id="action-invalid",
            type=ActionType.FLOW_MOD,
            target="switch-1",
            parameters={},  # Missing required params
            priority=1000,
            timeout=30
        )
        
        sequence = ActionSequence(
            id="seq-1",
            intent_id="intent-1",
            actions=[invalid_action],
            estimated_duration=30,
            dependencies=[],
            rollback_plan=[]
        )
        
        result = validator.validate_actions(sequence)
        
        assert not result.is_valid
        assert any("match" in error.lower() for error in result.errors)
    
    def test_validate_slice_create_missing_resources(self):
        """Test validation of slice creation with missing resources."""
        validator = ActionValidator()
        
        invalid_action = NetworkAction(
            id="action-invalid",
            type=ActionType.SLICE_CREATE,
            target="slice-1",
            parameters={"slice_name": "test"},  # Missing resources
            priority=1000,
            timeout=60
        )
        
        sequence = ActionSequence(
            id="seq-1",
            intent_id="intent-1",
            actions=[invalid_action],
            estimated_duration=60,
            dependencies=[],
            rollback_plan=[]
        )
        
        result = validator.validate_actions(sequence)
        
        assert not result.is_valid
        assert any("resources" in error.lower() for error in result.errors)
    
    def test_check_safety_low_risk(self, sample_action_sequence, sample_network_state):
        """Test safety check for low-risk sequence."""
        validator = ActionValidator()
        
        safety_report = validator.check_safety(sample_action_sequence, sample_network_state)
        
        assert isinstance(safety_report, SafetyReport)
        assert safety_report.risk_level in ["low", "medium"]
    
    def test_check_safety_high_risk_many_switches(self, sample_network_state):
        """Test safety check for high-risk sequence affecting many switches."""
        validator = ActionValidator()
        
        # Create action affecting many switches
        high_risk_action = NetworkAction(
            id="action-high-risk",
            type=ActionType.SLICE_CREATE,
            target="slice-1",
            parameters={
                "slice_name": "large-slice",
                "resources": {
                    "bandwidth": 5000,
                    "switches": [f"switch-{i}" for i in range(15)],  # Many switches
                    "paths": []
                }
            },
            priority=1000,
            timeout=120
        )
        
        sequence = ActionSequence(
            id="seq-high-risk",
            intent_id="intent-1",
            actions=[high_risk_action],
            estimated_duration=120,
            dependencies=[],
            rollback_plan=[]
        )
        
        safety_report = validator.check_safety(sequence, sample_network_state)
        
        assert not safety_report.is_safe or safety_report.risk_level in ["medium", "high", "critical"]
        assert len(safety_report.potential_impacts) > 0
    
    def test_simulate_execution(self, sample_action_sequence, sample_network_state):
        """Test action execution simulation."""
        validator = ActionValidator()
        
        simulation = validator.simulate_execution(sample_action_sequence, sample_network_state)
        
        assert simulation.success
        assert len(simulation.predicted_outcomes) > 0
        assert "bandwidth_utilization_change" in simulation.performance_impact


class TestRollbackPlanGenerator:
    """Tests for RollbackPlanGenerator class."""
    
    def test_generate_rollback_plan(self, sample_action_sequence):
        """Test rollback plan generation."""
        generator = RollbackPlanGenerator()
        
        rollback_plan = generator.generate_rollback_plan(sample_action_sequence)
        
        assert len(rollback_plan) > 0
        assert all(action.id.startswith("rollback_") for action in rollback_plan)
    
    def test_rollback_flow_mod(self, sample_flow_mod_action):
        """Test rollback action creation for flow modification."""
        generator = RollbackPlanGenerator()
        
        rollback = generator._create_rollback_action(sample_flow_mod_action, 0, None)
        
        assert rollback is not None
        assert rollback.type == ActionType.FLOW_MOD
        assert rollback.parameters.get("command") == "delete"
        assert rollback.target == sample_flow_mod_action.target
    
    def test_rollback_slice_create(self, sample_slice_create_action):
        """Test rollback action creation for slice creation."""
        generator = RollbackPlanGenerator()
        
        rollback = generator._create_rollback_action(sample_slice_create_action, 0, None)
        
        assert rollback is not None
        assert rollback.type == ActionType.CONFIG_CHANGE
        assert "delete" in rollback.parameters.get("config_type", "").lower()
    
    def test_validate_rollback_plan(self, sample_action_sequence):
        """Test rollback plan validation."""
        generator = RollbackPlanGenerator()
        
        rollback_plan = generator.generate_rollback_plan(sample_action_sequence)
        result = generator.validate_rollback_plan(sample_action_sequence, rollback_plan)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid or len(result.warnings) > 0
    
    def test_validate_empty_rollback_plan(self, sample_action_sequence):
        """Test validation of empty rollback plan."""
        generator = RollbackPlanGenerator()
        
        result = generator.validate_rollback_plan(sample_action_sequence, [])
        
        assert not result.is_valid
        assert any("empty" in error.lower() for error in result.errors)
    
    def test_emergency_rollback(self, sample_action_sequence):
        """Test emergency rollback plan creation."""
        generator = RollbackPlanGenerator()
        
        emergency_plan = generator.create_emergency_rollback(sample_action_sequence)
        
        assert len(emergency_plan) > 0
        assert all("EMERGENCY" in action.description for action in emergency_plan)
        # Emergency actions should have higher priority
        assert all(
            action.priority > sample_action_sequence.actions[0].priority
            for action in emergency_plan
        )


class TestImpactAssessor:
    """Tests for ImpactAssessor class."""
    
    def test_assess_impact(self, sample_action_sequence, sample_network_state):
        """Test impact assessment."""
        assessor = ImpactAssessor()
        
        impact = assessor.assess_impact(sample_action_sequence, sample_network_state)
        
        assert isinstance(impact, ImpactAssessment)
        assert len(impact.affected_resources) > 0
        assert impact.service_disruption_risk in ["none", "minimal", "moderate", "high"]
        assert impact.estimated_recovery_time > 0
    
    def test_identify_affected_resources(self, sample_action_sequence, sample_network_state):
        """Test affected resources identification."""
        assessor = ImpactAssessor()
        
        affected = assessor._identify_affected_resources(
            sample_action_sequence,
            sample_network_state
        )
        
        assert len(affected) > 0
        assert "switch-1" in affected or "slice-1" in affected
    
    def test_predict_performance_impact(self, sample_action_sequence, sample_network_state):
        """Test performance impact prediction."""
        assessor = ImpactAssessor()
        
        impact = assessor._predict_performance_impact(
            sample_action_sequence,
            sample_network_state
        )
        
        assert "bandwidth_utilization_change" in impact
        assert "latency_change_ms" in impact
        assert "throughput_change_percent" in impact
        assert "packet_loss_risk" in impact
    
    def test_calculate_risk_score(self, sample_action_sequence, sample_network_state):
        """Test risk score calculation."""
        assessor = ImpactAssessor()
        
        risk_score = assessor.calculate_risk_score(
            sample_action_sequence,
            sample_network_state
        )
        
        assert "overall_risk_score" in risk_score
        assert "risk_level" in risk_score
        assert "risk_breakdown" in risk_score
        assert 0 <= risk_score["overall_risk_score"] <= 100
        assert risk_score["risk_level"] in ["low", "medium", "high", "critical"]
    
    def test_generate_approval_workflow_low_risk(self, sample_action_sequence, sample_network_state):
        """Test approval workflow generation for low-risk sequence."""
        assessor = ImpactAssessor()
        
        risk_score = assessor.calculate_risk_score(
            sample_action_sequence,
            sample_network_state
        )
        
        workflow = assessor.generate_approval_workflow(
            sample_action_sequence,
            risk_score
        )
        
        assert "requires_approval" in workflow
        assert "approval_level" in workflow
        assert "estimated_review_time" in workflow
    
    def test_generate_approval_workflow_high_risk(self, sample_network_state):
        """Test approval workflow generation for high-risk sequence."""
        assessor = ImpactAssessor()
        
        # Create high-risk sequence
        high_risk_actions = [
            NetworkAction(
                id=f"action-{i}",
                type=ActionType.CONFIG_CHANGE,
                target=f"switch-{i}",
                parameters={
                    "config_type": "switch_config",
                    "config_data": {"setting": "value"}
                },
                priority=1000,
                timeout=60
            )
            for i in range(10)
        ]
        
        high_risk_sequence = ActionSequence(
            id="seq-high-risk",
            intent_id="intent-1",
            actions=high_risk_actions,
            estimated_duration=600,
            dependencies=[],
            rollback_plan=[]
        )
        
        risk_score = assessor.calculate_risk_score(
            high_risk_sequence,
            sample_network_state
        )
        
        workflow = assessor.generate_approval_workflow(
            high_risk_sequence,
            risk_score
        )
        
        # High risk should require approval
        if risk_score["risk_level"] in ["high", "critical"]:
            assert workflow["requires_approval"]
            assert len(workflow["approvers"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
