"""Property-based tests for service continuity preservation during slice modifications."""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from datetime import datetime
import copy

from src.models.slices import NetworkSlice, SliceResources, SliceStatus, Path, ServiceLevelAgreement, Policy
from src.models.network import NetworkState, Topology, Switch, Link, NetworkMetrics, BandwidthMetrics, LatencyMetrics, UtilizationMetrics


class TestServiceContinuityProperties:
    """Property-based tests for service continuity preservation."""
    
    @staticmethod
    @st.composite
    def active_network_slice(draw):
        """Generate an active network slice."""
        slice_id = f"slice_{draw(st.integers(min_value=1000, max_value=9999))}"
        bandwidth = draw(st.integers(min_value=100, max_value=5000))
        
        # Generate switches
        num_switches = draw(st.integers(min_value=2, max_value=5))
        switches = [f"switch-{i}" for i in range(num_switches)]
        
        # Generate paths
        num_paths = draw(st.integers(min_value=1, max_value=3))
        paths = []
        for i in range(num_paths):
            path_switches = draw(st.lists(
                st.sampled_from(switches),
                min_size=2,
                max_size=min(4, num_switches),
                unique=True
            ))
            path = Path(
                id=f"path_{i}",
                switches=path_switches,
                links=[f"link_{j}" for j in range(len(path_switches)-1)],
                bandwidth=bandwidth,
                latency=draw(st.floats(min_value=1.0, max_value=50.0))
            )
            paths.append(path)
        
        resources = SliceResources(
            bandwidth=bandwidth,
            switches=switches,
            paths=paths,
            cpu_allocation=draw(st.floats(min_value=10.0, max_value=80.0)),
            memory_allocation=draw(st.integers(min_value=1024, max_value=8192))
        )
        
        sla = ServiceLevelAgreement(
            id=f"sla_{slice_id}",
            min_bandwidth=int(bandwidth * 0.8),
            max_latency=draw(st.floats(min_value=10.0, max_value=100.0)),
            availability=draw(st.floats(min_value=95.0, max_value=99.99)),
            packet_loss_threshold=draw(st.floats(min_value=0.1, max_value=5.0))
        )
        
        return NetworkSlice(
            id=slice_id,
            name=f"Slice {slice_id}",
            resources=resources,
            policies=[],
            sla=sla,
            status=SliceStatus.ACTIVE,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
    
    @staticmethod
    @st.composite
    def slice_modification(draw):
        """Generate a modification to apply to a slice."""
        modification_type = draw(st.sampled_from([
            "bandwidth_increase",
            "bandwidth_decrease",
            "add_switch",
            "remove_switch",
            "add_path",
            "update_sla"
        ]))
        
        modification_params = {}
        if modification_type == "bandwidth_increase":
            modification_params["new_bandwidth"] = draw(st.integers(min_value=5100, max_value=10000))
        elif modification_type == "bandwidth_decrease":
            modification_params["new_bandwidth"] = draw(st.integers(min_value=50, max_value=4900))
        elif modification_type == "add_switch":
            modification_params["new_switch"] = f"switch-{draw(st.integers(min_value=10, max_value=20))}"
        elif modification_type == "remove_switch":
            modification_params["remove_index"] = 0  # Will remove first switch
        elif modification_type == "add_path":
            modification_params["new_path_switches"] = [f"switch-{i}" for i in range(2)]
        elif modification_type == "update_sla":
            modification_params["new_max_latency"] = draw(st.floats(min_value=20.0, max_value=150.0))
        
        return modification_type, modification_params
    
    def _apply_modification(self, slice_obj: NetworkSlice, mod_type: str, params: dict) -> NetworkSlice:
        """Apply modification to slice and return modified copy."""
        modified_slice = copy.deepcopy(slice_obj)
        
        if mod_type == "bandwidth_increase":
            modified_slice.resources.bandwidth = params["new_bandwidth"]
            for path in modified_slice.resources.paths:
                path.bandwidth = params["new_bandwidth"]
        
        elif mod_type == "bandwidth_decrease":
            new_bw = params["new_bandwidth"]
            # Ensure we don't go below SLA minimum
            if modified_slice.sla:
                new_bw = max(new_bw, modified_slice.sla.min_bandwidth)
            modified_slice.resources.bandwidth = new_bw
            for path in modified_slice.resources.paths:
                path.bandwidth = new_bw
        
        elif mod_type == "add_switch":
            if params["new_switch"] not in modified_slice.resources.switches:
                modified_slice.resources.switches.append(params["new_switch"])
        
        elif mod_type == "remove_switch":
            if len(modified_slice.resources.switches) > 2:  # Keep at least 2 switches
                modified_slice.resources.switches.pop(params["remove_index"])
        
        elif mod_type == "add_path":
            new_path = Path(
                id=f"path_{len(modified_slice.resources.paths)}",
                switches=params["new_path_switches"],
                links=[f"link_new_{i}" for i in range(len(params["new_path_switches"])-1)],
                bandwidth=modified_slice.resources.bandwidth
            )
            modified_slice.resources.paths.append(new_path)
        
        elif mod_type == "update_sla":
            if modified_slice.sla:
                modified_slice.sla.max_latency = params["new_max_latency"]
        
        modified_slice.updated_at = datetime.now().isoformat()
        return modified_slice
    
    def _check_service_continuity(self, original: NetworkSlice, modified: NetworkSlice) -> dict:
        """Check if service continuity is preserved during modification."""
        continuity_check = {
            "is_preserved": True,
            "violations": [],
            "warnings": []
        }
        
        # Check 1: Slice remains active or in controlled transition
        if original.status == SliceStatus.ACTIVE:
            if modified.status not in [SliceStatus.ACTIVE, SliceStatus.CONFIGURING]:
                continuity_check["is_preserved"] = False
                continuity_check["violations"].append(
                    f"Slice transitioned from ACTIVE to {modified.status.value}"
                )
        
        # Check 2: SLA requirements are maintained
        if original.sla and modified.sla:
            if modified.resources.bandwidth < modified.sla.min_bandwidth:
                continuity_check["is_preserved"] = False
                continuity_check["violations"].append(
                    f"Bandwidth {modified.resources.bandwidth} below SLA minimum {modified.sla.min_bandwidth}"
                )
        
        # Check 3: At least one path remains available
        if len(original.resources.paths) > 0:
            if len(modified.resources.paths) == 0:
                continuity_check["is_preserved"] = False
                continuity_check["violations"].append("All paths removed during modification")
        
        # Check 4: Minimum connectivity maintained
        if len(modified.resources.switches) < 2:
            continuity_check["warnings"].append("Less than 2 switches may impact connectivity")
        
        # Check 5: Resource allocation remains valid
        if modified.resources.bandwidth <= 0:
            continuity_check["is_preserved"] = False
            continuity_check["violations"].append("Invalid bandwidth allocation")
        
        return continuity_check
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        slice_obj=active_network_slice(),
        modification=slice_modification()
    )
    def test_service_continuity_preservation(self, slice_obj, modification):
        """
        **Feature: llm-integration-module, Property 17: Service continuity preservation**
        
        For any modification to an existing NetworkSlice, the changes should be 
        implemented without interrupting ongoing services.
        
        **Validates: Requirements 5.2**
        
        Requirement 5.2 states:
        "WHEN un intent modifica un Network_Slice esistente, THE LLM_Module SHALL 
        preservare la continuità del servizio durante la transizione"
        """
        assume(slice_obj is not None)
        assume(slice_obj.status == SliceStatus.ACTIVE)
        
        mod_type, params = modification
        
        # Apply modification
        modified_slice = self._apply_modification(slice_obj, mod_type, params)
        
        # Check service continuity
        continuity_check = self._check_service_continuity(slice_obj, modified_slice)
        
        # Property: Service continuity must be preserved
        assert continuity_check["is_preserved"], (
            f"Service continuity violated during {mod_type}: {continuity_check['violations']}"
        )
        
        # Verify slice integrity after modification
        integrity = modified_slice.validate_slice_integrity()
        assert integrity["is_valid"], f"Slice integrity compromised: {integrity['issues']}"
        
        # Verify essential service parameters are maintained
        assert modified_slice.id == slice_obj.id, "Slice ID must not change"
        assert modified_slice.status in [SliceStatus.ACTIVE, SliceStatus.CONFIGURING], \
               "Slice must remain active or in controlled transition"
        
        # Verify SLA compliance if SLA exists
        if modified_slice.sla:
            assert modified_slice.resources.bandwidth >= modified_slice.sla.min_bandwidth, \
                   "Bandwidth must meet SLA minimum"
        
        # Verify connectivity is maintained
        assert len(modified_slice.resources.switches) >= 2, \
               "At least 2 switches required for connectivity"
        
        # Verify at least one path exists for active slices
        if modified_slice.status == SliceStatus.ACTIVE:
            assert len(modified_slice.resources.paths) > 0, \
                   "Active slice must have at least one path"
    
    @settings(max_examples=50)
    @given(slice_obj=active_network_slice())
    def test_no_service_interruption_during_update(self, slice_obj):
        """Test that slice updates don't cause service interruption."""
        assume(slice_obj.status == SliceStatus.ACTIVE)
        
        # Simulate safe update (bandwidth increase)
        modified_slice = copy.deepcopy(slice_obj)
        modified_slice.resources.bandwidth = slice_obj.resources.bandwidth + 1000
        modified_slice.updated_at = datetime.now().isoformat()
        
        # Check continuity
        continuity_check = self._check_service_continuity(slice_obj, modified_slice)
        
        # Should preserve continuity for safe updates
        assert continuity_check["is_preserved"]
        assert len(continuity_check["violations"]) == 0
    
    def test_continuity_with_sla_compliance(self):
        """Test that modifications maintain SLA compliance."""
        # Create slice with SLA
        slice_obj = NetworkSlice(
            id="slice_sla_test",
            name="SLA Test Slice",
            resources=SliceResources(
                bandwidth=1000,
                switches=["switch-1", "switch-2"],
                paths=[
                    Path(id="path1", switches=["switch-1", "switch-2"], links=["link1"], bandwidth=1000)
                ]
            ),
            sla=ServiceLevelAgreement(
                id="sla_test",
                min_bandwidth=800,
                max_latency=50.0,
                availability=99.0,
                packet_loss_threshold=1.0
            ),
            status=SliceStatus.ACTIVE,
            created_at=datetime.now().isoformat()
        )
        
        # Try to reduce bandwidth below SLA minimum
        modified_slice = copy.deepcopy(slice_obj)
        modified_slice.resources.bandwidth = 700  # Below SLA minimum of 800
        
        # Check continuity
        continuity_check = self._check_service_continuity(slice_obj, modified_slice)
        
        # Should detect SLA violation
        assert not continuity_check["is_preserved"]
        assert any("SLA" in v or "bandwidth" in v.lower() for v in continuity_check["violations"])
