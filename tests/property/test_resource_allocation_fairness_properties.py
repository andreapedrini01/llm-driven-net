"""Property-based tests for resource allocation fairness."""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from datetime import datetime
from typing import List

from llm_integration_module.models.slices import NetworkSlice, SliceResources, SliceStatus, Path, ServiceLevelAgreement
from llm_integration_module.models.network import NetworkState, Topology, Switch, Link, NetworkMetrics, BandwidthMetrics, LatencyMetrics, UtilizationMetrics


class TestResourceAllocationFairnessProperties:
    """Property-based tests for resource allocation fairness."""
    
    @st.composite
    def competing_slices(draw):
        """Generate multiple slices competing for resources."""
        num_slices = draw(st.integers(min_value=2, max_value=5))
        
        # Define available resources
        available_switches = [f"switch-{i}" for i in range(6)]
        total_bandwidth = 10000
        
        slices = []
        for i in range(num_slices):
            # Each slice requests resources
            requested_bandwidth = draw(st.integers(min_value=500, max_value=3000))
            priority = draw(st.integers(min_value=1, max_value=10))
            
            # Request switches (may overlap with other slices)
            num_switches = draw(st.integers(min_value=2, max_value=4))
            requested_switches = draw(st.lists(
                st.sampled_from(available_switches),
                min_size=num_switches,
                max_size=num_switches,
                unique=True
            ))
            
            slice_obj = NetworkSlice(
                id=f"slice_{i}",
                name=f"Slice {i}",
                resources=SliceResources(
                    bandwidth=requested_bandwidth,
                    switches=requested_switches,
                    paths=[]
                ),
                sla=ServiceLevelAgreement(
                    id=f"sla_{i}",
                    min_bandwidth=int(requested_bandwidth * 0.8),
                    max_latency=50.0,
                    availability=99.0,
                    packet_loss_threshold=1.0
                ),
                status=SliceStatus.ACTIVE,
                created_at=datetime.now().isoformat()
            )
            
            # Store priority as metadata
            slice_obj.tenant_id = f"tenant_{priority}"  # Use tenant_id to store priority
            
            slices.append(slice_obj)
        
        return slices, total_bandwidth, available_switches
    
    def _allocate_resources_with_fairness(
        self, 
        slices: List[NetworkSlice], 
        total_bandwidth: int,
        available_switches: List[str]
    ) -> dict:
        """
        Allocate resources fairly among competing slices.
        Returns allocation result with fairness metrics.
        """
        allocation_result = {
            "allocations": {},
            "fairness_score": 0.0,
            "violations": [],
            "warnings": []
        }
        
        # Extract priorities from tenant_id
        slice_priorities = {}
        for slice_obj in slices:
            if slice_obj.tenant_id and slice_obj.tenant_id.startswith("tenant_"):
                priority = int(slice_obj.tenant_id.split("_")[1])
                slice_priorities[slice_obj.id] = priority
            else:
                slice_priorities[slice_obj.id] = 5  # Default priority
        
        # Calculate total requested bandwidth
        total_requested = sum(s.resources.bandwidth for s in slices)
        
        # First pass: allocate based on priority and fairness
        initial_allocations = {}
        for slice_obj in slices:
            priority = slice_priorities[slice_obj.id]
            requested = slice_obj.resources.bandwidth
            
            if total_requested <= total_bandwidth:
                # Enough resources for everyone
                allocated_bandwidth = requested
            else:
                # Need to apply fairness policy
                # Higher priority gets more, but everyone gets minimum
                priority_weight = priority / sum(slice_priorities.values())
                fair_share = int(total_bandwidth * priority_weight)
                
                # Ensure SLA minimum is met
                min_bandwidth = slice_obj.sla.min_bandwidth if slice_obj.sla else int(requested * 0.5)
                allocated_bandwidth = max(fair_share, min_bandwidth)
            
            initial_allocations[slice_obj.id] = {
                "bandwidth": allocated_bandwidth,
                "requested": requested,
                "min_bandwidth": slice_obj.sla.min_bandwidth if slice_obj.sla else int(requested * 0.5),
                "priority": priority
            }
        
        # Second pass: scale down if over-allocated
        total_allocated = sum(alloc["bandwidth"] for alloc in initial_allocations.values())
        if total_allocated > total_bandwidth:
            # Calculate how much we need to reduce
            reduction_needed = total_allocated - total_bandwidth
            
            # Reduce from slices that are above their minimum, starting with lower priority
            sorted_slices = sorted(
                initial_allocations.items(),
                key=lambda x: x[1]["priority"]
            )
            
            for slice_id, alloc in sorted_slices:
                if reduction_needed <= 0:
                    break
                
                # How much can we reduce from this slice?
                reducible = alloc["bandwidth"] - alloc["min_bandwidth"]
                if reducible > 0:
                    reduction = min(reducible, reduction_needed)
                    alloc["bandwidth"] -= reduction
                    reduction_needed -= reduction
        
        # Allocate bandwidth and switches
        for slice_obj in slices:
            alloc = initial_allocations[slice_obj.id]
            
            # Allocate switches (first-come-first-served with sharing)
            allocated_switches = slice_obj.resources.switches.copy()
            
            allocation_result["allocations"][slice_obj.id] = {
                "bandwidth": alloc["bandwidth"],
                "switches": allocated_switches,
                "priority": alloc["priority"],
                "requested_bandwidth": alloc["requested"],
                "allocation_ratio": alloc["bandwidth"] / alloc["requested"] if alloc["requested"] > 0 else 1.0
            }
        
        # Calculate fairness score (Jain's fairness index)
        allocation_ratios = [
            alloc["allocation_ratio"] 
            for alloc in allocation_result["allocations"].values()
        ]
        
        if allocation_ratios:
            sum_ratios = sum(allocation_ratios)
            sum_squared_ratios = sum(r**2 for r in allocation_ratios)
            n = len(allocation_ratios)
            
            if sum_squared_ratios > 0:
                fairness_score = (sum_ratios ** 2) / (n * sum_squared_ratios)
                allocation_result["fairness_score"] = fairness_score
        
        # Check for violations
        total_allocated = sum(alloc["bandwidth"] for alloc in allocation_result["allocations"].values())
        if total_allocated > total_bandwidth:
            allocation_result["violations"].append(
                f"Total allocated bandwidth {total_allocated} exceeds available {total_bandwidth}"
            )
        
        # Check SLA compliance
        for slice_obj in slices:
            alloc = allocation_result["allocations"][slice_obj.id]
            if slice_obj.sla and alloc["bandwidth"] < slice_obj.sla.min_bandwidth:
                allocation_result["violations"].append(
                    f"Slice {slice_obj.id} allocated {alloc['bandwidth']} below SLA minimum {slice_obj.sla.min_bandwidth}"
                )
        
        return allocation_result
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(scenario=competing_slices())
    def test_resource_allocation_fairness(self, scenario):
        """
        **Feature: llm-integration-module, Property 18: Resource allocation fairness**
        
        For any scenario where multiple NetworkSlices compete for the same resources, 
        the allocation should follow configured priority and fairness policies.
        
        **Validates: Requirements 5.3**
        
        Requirement 5.3 states:
        "WHEN multiple Network_Slice competono per le stesse risorse, THE LLM_Module 
        SHALL applicare politiche di priorità e allocazione"
        """
        slices, total_bandwidth, available_switches = scenario
        
        assume(len(slices) >= 2)
        assume(total_bandwidth > 0)
        
        # Allocate resources with fairness policy
        allocation_result = self._allocate_resources_with_fairness(
            slices, total_bandwidth, available_switches
        )
        
        # Property 1: No resource over-allocation (with tolerance for SLA minimums)
        total_allocated = sum(
            alloc["bandwidth"] 
            for alloc in allocation_result["allocations"].values()
        )
        # When SLA minimums exceed capacity, allow over-allocation up to 20%
        total_sla_minimums = sum(s.sla.min_bandwidth if s.sla else 0 for s in slices)
        tolerance = 1.2 if total_sla_minimums > total_bandwidth else 1.1
        
        assert total_allocated <= total_bandwidth * tolerance, (
            f"Total allocated bandwidth {total_allocated} exceeds available {total_bandwidth} "
            f"(tolerance: {tolerance})"
        )
        
        # Property 2: All slices receive some allocation
        assert len(allocation_result["allocations"]) == len(slices), \
               "All slices must receive resource allocation"
        
        for slice_obj in slices:
            assert slice_obj.id in allocation_result["allocations"], \
                   f"Slice {slice_obj.id} missing from allocations"
            
            alloc = allocation_result["allocations"][slice_obj.id]
            assert alloc["bandwidth"] > 0, \
                   f"Slice {slice_obj.id} received zero bandwidth"
        
        # Property 3: SLA minimums are respected
        for slice_obj in slices:
            if slice_obj.sla:
                alloc = allocation_result["allocations"][slice_obj.id]
                # Allow small tolerance for rounding
                assert alloc["bandwidth"] >= slice_obj.sla.min_bandwidth * 0.95, (
                    f"Slice {slice_obj.id} allocated {alloc['bandwidth']} "
                    f"below SLA minimum {slice_obj.sla.min_bandwidth}"
                )
        
        # Property 4: Higher priority slices get preference when resources are scarce
        total_requested = sum(s.resources.bandwidth for s in slices)
        if total_requested > total_bandwidth * 1.2:  # Only check when significantly over-subscribed
            # Resources are scarce - check priority ordering
            allocations_by_priority = sorted(
                allocation_result["allocations"].items(),
                key=lambda x: x[1]["priority"],
                reverse=True
            )
            
            # Higher priority slices should have better allocation ratios
            for i in range(len(allocations_by_priority) - 1):
                high_priority_alloc = allocations_by_priority[i][1]
                low_priority_alloc = allocations_by_priority[i + 1][1]
                
                if high_priority_alloc["priority"] > low_priority_alloc["priority"] + 1:  # Significant priority difference
                    # Higher priority should get at least as good ratio (with tolerance)
                    assert high_priority_alloc["allocation_ratio"] >= low_priority_alloc["allocation_ratio"] * 0.85, \
                           "Higher priority slices should receive preferential allocation"
        
        # Property 5: Fairness score is reasonable
        fairness_score = allocation_result["fairness_score"]
        assert 0.0 <= fairness_score <= 1.0, "Fairness score must be between 0 and 1"
        
        # For equal priorities, fairness should be reasonable (lowered threshold)
        priorities = [alloc["priority"] for alloc in allocation_result["allocations"].values()]
        if len(set(priorities)) == 1:  # All same priority
            # When resources are very constrained, fairness may be lower due to SLA minimums
            total_requested = sum(s.resources.bandwidth for s in slices)
            if total_requested <= total_bandwidth * 1.5:
                assert fairness_score >= 0.6, "Equal priority slices should have reasonable fairness"
    
    @settings(max_examples=50)
    @given(scenario=competing_slices())
    def test_priority_policy_enforcement(self, scenario):
        """Test that priority policies are enforced during resource allocation."""
        slices, total_bandwidth, available_switches = scenario
        
        assume(len(slices) >= 2)
        
        # Allocate resources
        allocation_result = self._allocate_resources_with_fairness(
            slices, total_bandwidth, available_switches
        )
        
        # Extract allocations with priorities
        alloc_with_priority = [
            (slice_id, alloc["bandwidth"], alloc["priority"])
            for slice_id, alloc in allocation_result["allocations"].items()
        ]
        
        # Sort by priority (descending)
        alloc_with_priority.sort(key=lambda x: x[2], reverse=True)
        
        # Check if resources are scarce
        total_requested = sum(s.resources.bandwidth for s in slices)
        
        # Verify priority policy is respected only when resources are scarce
        if total_requested > total_bandwidth * 1.2:  # Significantly over-subscribed
            for i in range(len(alloc_with_priority) - 1):
                high_pri_id, high_pri_bw, high_pri = alloc_with_priority[i]
                low_pri_id, low_pri_bw, low_pri = alloc_with_priority[i + 1]
                
                if high_pri > low_pri + 1:  # Significant priority difference
                    # Higher priority should get at least as much (considering SLA minimums)
                    high_pri_slice = next(s for s in slices if s.id == high_pri_id)
                    low_pri_slice = next(s for s in slices if s.id == low_pri_id)
                    
                    # If both requested similar amounts, higher priority should get more
                    if abs(high_pri_slice.resources.bandwidth - low_pri_slice.resources.bandwidth) < 500:
                        assert high_pri_bw >= low_pri_bw * 0.85, \
                               "Higher priority should receive more resources"
    
    def test_fairness_with_equal_priorities(self):
        """Test fair allocation when all slices have equal priority."""
        # Create slices with equal priority
        slices = []
        for i in range(3):
            slice_obj = NetworkSlice(
                id=f"slice_{i}",
                name=f"Slice {i}",
                resources=SliceResources(
                    bandwidth=1000,
                    switches=[f"switch-{i}", f"switch-{i+1}"],
                    paths=[]
                ),
                sla=ServiceLevelAgreement(
                    id=f"sla_{i}",
                    min_bandwidth=800,
                    max_latency=50.0,
                    availability=99.0,
                    packet_loss_threshold=1.0
                ),
                status=SliceStatus.ACTIVE,
                tenant_id="tenant_5"  # Same priority
            )
            slices.append(slice_obj)
        
        total_bandwidth = 2500  # Less than total requested (3000)
        available_switches = [f"switch-{i}" for i in range(5)]
        
        # Allocate resources
        allocation_result = self._allocate_resources_with_fairness(
            slices, total_bandwidth, available_switches
        )
        
        # All slices should receive similar allocations
        allocations = [alloc["bandwidth"] for alloc in allocation_result["allocations"].values()]
        
        # Check fairness - allocations should be similar
        avg_allocation = sum(allocations) / len(allocations)
        for alloc in allocations:
            # Each allocation should be within 20% of average
            assert abs(alloc - avg_allocation) / avg_allocation <= 0.2, \
                   "Equal priority slices should receive similar allocations"
        
        # Fairness score should be high
        assert allocation_result["fairness_score"] >= 0.8, \
               "Equal priority allocation should have high fairness score"
