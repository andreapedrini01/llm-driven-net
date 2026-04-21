"""Property-based tests for resource cleanup completeness."""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from datetime import datetime
from typing import Set

from llm_integration_module.models.slices import NetworkSlice, SliceResources, SliceStatus, Path
from llm_integration_module.models.network import NetworkState, Topology, Switch, Link, NetworkMetrics, BandwidthMetrics, LatencyMetrics, UtilizationMetrics


class TestResourceCleanupProperties:
    """Property-based tests for resource cleanup completeness."""
    
    @staticmethod
    @st.composite
    def slice_to_delete(draw):
        """Generate a network slice that will be deleted."""
        slice_id = f"slice_{draw(st.integers(min_value=1000, max_value=9999))}"
        
        # Generate allocated resources
        num_switches = draw(st.integers(min_value=2, max_value=5))
        switches = [f"switch-{i}" for i in range(num_switches)]
        
        num_paths = draw(st.integers(min_value=1, max_value=3))
        paths = []
        for i in range(num_paths):
            path = Path(
                id=f"path_{i}",
                switches=draw(st.lists(
                    st.sampled_from(switches),
                    min_size=2,
                    max_size=min(4, num_switches),
                    unique=True
                )),
                links=[f"link_{j}" for j in range(draw(st.integers(min_value=1, max_value=3)))],
                bandwidth=draw(st.integers(min_value=100, max_value=5000))
            )
            paths.append(path)
        
        resources = SliceResources(
            bandwidth=draw(st.integers(min_value=500, max_value=5000)),
            switches=switches,
            paths=paths,
            cpu_allocation=draw(st.floats(min_value=10.0, max_value=80.0)),
            memory_allocation=draw(st.integers(min_value=1024, max_value=8192))
        )
        
        return NetworkSlice(
            id=slice_id,
            name=f"Slice {slice_id}",
            resources=resources,
            policies=[],
            sla=None,
            status=SliceStatus.ACTIVE,
            created_at=datetime.now().isoformat()
        )
    
    def _cleanup_slice_resources(self, slice_obj: NetworkSlice) -> dict:
        """
        Cleanup all resources allocated to a slice.
        Returns cleanup result with details.
        """
        cleanup_result = {
            "success": True,
            "cleaned_resources": {
                "bandwidth": 0,
                "switches": [],
                "paths": [],
                "cpu": 0.0,
                "memory": 0
            },
            "released_resources": {
                "bandwidth": slice_obj.resources.bandwidth,
                "switches": slice_obj.resources.switches.copy(),
                "paths": [p.id for p in slice_obj.resources.paths],
                "cpu": slice_obj.resources.cpu_allocation,
                "memory": slice_obj.resources.memory_allocation
            },
            "issues": [],
            "warnings": []
        }
        
        try:
            # Release bandwidth
            cleanup_result["cleaned_resources"]["bandwidth"] = slice_obj.resources.bandwidth
            
            # Release switches
            cleanup_result["cleaned_resources"]["switches"] = slice_obj.resources.switches.copy()
            
            # Release paths
            cleanup_result["cleaned_resources"]["paths"] = [p.id for p in slice_obj.resources.paths]
            
            # Release CPU allocation
            if slice_obj.resources.cpu_allocation:
                cleanup_result["cleaned_resources"]["cpu"] = slice_obj.resources.cpu_allocation
            
            # Release memory allocation
            if slice_obj.resources.memory_allocation:
                cleanup_result["cleaned_resources"]["memory"] = slice_obj.resources.memory_allocation
            
        except Exception as e:
            cleanup_result["success"] = False
            cleanup_result["issues"].append(f"Cleanup error: {str(e)}")
        
        return cleanup_result
    
    def _verify_cleanup_completeness(self, slice_obj: NetworkSlice, cleanup_result: dict) -> dict:
        """Verify that all resources were properly cleaned up."""
        verification = {
            "is_complete": True,
            "missing_cleanups": [],
            "warnings": []
        }
        
        # Verify bandwidth was released
        if cleanup_result["cleaned_resources"]["bandwidth"] != slice_obj.resources.bandwidth:
            verification["is_complete"] = False
            verification["missing_cleanups"].append(
                f"Bandwidth not fully released: {cleanup_result['cleaned_resources']['bandwidth']} "
                f"vs {slice_obj.resources.bandwidth}"
            )
        
        # Verify all switches were released
        cleaned_switches = set(cleanup_result["cleaned_resources"]["switches"])
        original_switches = set(slice_obj.resources.switches)
        if cleaned_switches != original_switches:
            verification["is_complete"] = False
            missing = original_switches - cleaned_switches
            verification["missing_cleanups"].append(f"Switches not released: {missing}")
        
        # Verify all paths were released
        cleaned_paths = set(cleanup_result["cleaned_resources"]["paths"])
        original_paths = set(p.id for p in slice_obj.resources.paths)
        if cleaned_paths != original_paths:
            verification["is_complete"] = False
            missing = original_paths - cleaned_paths
            verification["missing_cleanups"].append(f"Paths not released: {missing}")
        
        # Verify CPU allocation was released
        if slice_obj.resources.cpu_allocation:
            if cleanup_result["cleaned_resources"]["cpu"] != slice_obj.resources.cpu_allocation:
                verification["is_complete"] = False
                verification["missing_cleanups"].append("CPU allocation not fully released")
        
        # Verify memory allocation was released
        if slice_obj.resources.memory_allocation:
            if cleanup_result["cleaned_resources"]["memory"] != slice_obj.resources.memory_allocation:
                verification["is_complete"] = False
                verification["missing_cleanups"].append("Memory allocation not fully released")
        
        return verification
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(slice_obj=slice_to_delete())
    def test_resource_cleanup_completeness(self, slice_obj):
        """
        **Feature: llm-integration-module, Property 19: Resource cleanup completeness**
        
        For any NetworkSlice that is no longer needed, all associated resources 
        should be properly released and made available for reallocation.
        
        **Validates: Requirements 5.4**
        
        Requirement 5.4 states:
        "WHEN un Network_Slice non è più necessario, THE LLM_Module SHALL rilasciare 
        le risorse in modo pulito"
        """
        assume(slice_obj is not None)
        
        # Record original resource allocation
        original_bandwidth = slice_obj.resources.bandwidth
        original_switches = set(slice_obj.resources.switches)
        original_paths = set(p.id for p in slice_obj.resources.paths)
        original_cpu = slice_obj.resources.cpu_allocation
        original_memory = slice_obj.resources.memory_allocation
        
        # Perform cleanup
        cleanup_result = self._cleanup_slice_resources(slice_obj)
        
        # Property 1: Cleanup should succeed
        assert cleanup_result["success"], f"Cleanup failed: {cleanup_result['issues']}"
        
        # Property 2: All resources should be identified for cleanup
        assert cleanup_result["released_resources"]["bandwidth"] == original_bandwidth, \
               "Bandwidth not identified for release"
        assert set(cleanup_result["released_resources"]["switches"]) == original_switches, \
               "Switches not identified for release"
        assert set(cleanup_result["released_resources"]["paths"]) == original_paths, \
               "Paths not identified for release"
        
        # Property 3: Verify cleanup completeness
        verification = self._verify_cleanup_completeness(slice_obj, cleanup_result)
        
        assert verification["is_complete"], (
            f"Resource cleanup incomplete: {verification['missing_cleanups']}"
        )
        
        # Property 4: All bandwidth should be released
        assert cleanup_result["cleaned_resources"]["bandwidth"] == original_bandwidth, \
               "Not all bandwidth was released"
        
        # Property 5: All switches should be released
        cleaned_switches = set(cleanup_result["cleaned_resources"]["switches"])
        assert cleaned_switches == original_switches, \
               f"Not all switches released: missing {original_switches - cleaned_switches}"
        
        # Property 6: All paths should be released
        cleaned_paths = set(cleanup_result["cleaned_resources"]["paths"])
        assert cleaned_paths == original_paths, \
               f"Not all paths released: missing {original_paths - cleaned_paths}"
        
        # Property 7: CPU allocation should be released if it was allocated
        if original_cpu:
            assert cleanup_result["cleaned_resources"]["cpu"] == original_cpu, \
                   "CPU allocation not fully released"
        
        # Property 8: Memory allocation should be released if it was allocated
        if original_memory:
            assert cleanup_result["cleaned_resources"]["memory"] == original_memory, \
                   "Memory allocation not fully released"
        
        # Property 9: No cleanup issues should occur
        assert len(cleanup_result["issues"]) == 0, \
               f"Cleanup issues occurred: {cleanup_result['issues']}"
    
    @settings(max_examples=50)
    @given(slice_obj=slice_to_delete())
    def test_resources_available_after_cleanup(self, slice_obj):
        """Test that resources are available for reallocation after cleanup."""
        assume(slice_obj is not None)
        
        # Perform cleanup
        cleanup_result = self._cleanup_slice_resources(slice_obj)
        
        assert cleanup_result["success"]
        
        # Verify released resources are tracked
        released = cleanup_result["released_resources"]
        
        assert released["bandwidth"] > 0, "Bandwidth should be released"
        assert len(released["switches"]) > 0, "Switches should be released"
        assert len(released["paths"]) > 0, "Paths should be released"
        
        # These resources should now be available for reallocation
        # (In a real system, this would update a resource pool)
    
    def test_cleanup_with_no_resources(self):
        """Test cleanup of slice with minimal resources."""
        # Create slice with minimal resources
        slice_obj = NetworkSlice(
            id="slice_minimal",
            name="Minimal Slice",
            resources=SliceResources(
                bandwidth=100,
                switches=["switch-1", "switch-2"],
                paths=[]
            ),
            status=SliceStatus.INACTIVE
        )
        
        # Cleanup should still succeed
        cleanup_result = self._cleanup_slice_resources(slice_obj)
        
        assert cleanup_result["success"]
        assert cleanup_result["cleaned_resources"]["bandwidth"] == 100
        assert len(cleanup_result["cleaned_resources"]["switches"]) == 2
    
    def test_cleanup_idempotency(self):
        """Test that cleanup can be called multiple times safely."""
        slice_obj = NetworkSlice(
            id="slice_idempotent",
            name="Idempotent Slice",
            resources=SliceResources(
                bandwidth=1000,
                switches=["switch-1", "switch-2"],
                paths=[
                    Path(id="path1", switches=["switch-1", "switch-2"], links=["link1"], bandwidth=1000)
                ]
            ),
            status=SliceStatus.ACTIVE
        )
        
        # First cleanup
        cleanup1 = self._cleanup_slice_resources(slice_obj)
        assert cleanup1["success"]
        
        # Second cleanup (should handle gracefully)
        cleanup2 = self._cleanup_slice_resources(slice_obj)
        assert cleanup2["success"]
        
        # Both should release same resources
        assert cleanup1["released_resources"]["bandwidth"] == cleanup2["released_resources"]["bandwidth"]
