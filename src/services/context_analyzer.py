"""Context Analyzer component for LLM Integration Module."""

import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict
import logging

from src.models.network import NetworkState, Anomaly, AnomalyType, AnomalySeverity
from src.models.intent import IntentObject, ContextualizedIntent, Entity
from src.models.actions import NetworkAction, ActionType


@dataclass
class CacheEntry:
    """Cache entry for NetworkState with metadata."""
    state: NetworkState
    cached_at: datetime
    ttl_seconds: int
    access_count: int = 0
    last_accessed: Optional[datetime] = None

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return datetime.now() > self.cached_at + timedelta(seconds=self.ttl_seconds)

    def is_fresh(self, max_age_seconds: int = 300) -> bool:
        """Check if cache entry is fresh enough for processing."""
        age = (datetime.now() - self.cached_at).total_seconds()
        return age <= max_age_seconds

    def mark_accessed(self) -> None:
        """Mark entry as accessed."""
        self.access_count += 1
        self.last_accessed = datetime.now()


class NetworkStateCache:
    """Thread-safe cache for NetworkState with TTL support."""

    def __init__(self, default_ttl: int = 300, max_entries: int = 100):
        """
        Initialize NetworkState cache.
        
        Args:
            default_ttl: Default time-to-live in seconds
            max_entries: Maximum number of cache entries
        """
        self.default_ttl = default_ttl
        self.max_entries = max_entries
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._current_state: Optional[CacheEntry] = None
        self._logger = logging.getLogger(__name__)

    def update_state(self, state: NetworkState, ttl: Optional[int] = None) -> None:
        """
        Update the current network state in cache.
        
        Args:
            state: New NetworkState to cache
            ttl: Time-to-live in seconds, uses default if None
        """
        with self._lock:
            ttl = ttl or self.default_ttl
            cache_key = f"state_{state.timestamp.isoformat()}"
            
            entry = CacheEntry(
                state=state,
                cached_at=datetime.now(),
                ttl_seconds=ttl
            )
            
            # Validate state integrity before caching
            validation = state.validate_data_integrity()
            if not validation["is_valid"]:
                self._logger.warning(f"Caching state with integrity issues: {validation['issues']}")
            
            self._cache[cache_key] = entry
            self._current_state = entry
            
            # Clean up old entries if cache is full
            self._cleanup_expired_entries()
            
            self._logger.info(f"Updated network state cache with {len(state.topology.switches)} switches, "
                            f"{len(state.topology.links)} links, {len(state.flows)} flows")

    def get_current_state(self) -> Optional[NetworkState]:
        """
        Get the current network state.
        
        Returns:
            Current NetworkState or None if not available/expired
        """
        with self._lock:
            if self._current_state is None:
                return None
            
            if self._current_state.is_expired():
                self._logger.warning("Current network state has expired")
                return None
            
            self._current_state.mark_accessed()
            return self._current_state.state

    def get_state_by_timestamp(self, timestamp: datetime) -> Optional[NetworkState]:
        """
        Get network state by timestamp.
        
        Args:
            timestamp: Timestamp to search for
            
        Returns:
            NetworkState closest to timestamp or None
        """
        with self._lock:
            closest_entry = None
            min_diff = float('inf')
            
            for entry in self._cache.values():
                if entry.is_expired():
                    continue
                
                diff = abs((entry.state.timestamp - timestamp).total_seconds())
                if diff < min_diff:
                    min_diff = diff
                    closest_entry = entry
            
            if closest_entry:
                closest_entry.mark_accessed()
                return closest_entry.state
            
            return None

    def is_state_fresh(self, max_age_seconds: int = 300) -> bool:
        """
        Check if current state is fresh enough for processing.
        
        Args:
            max_age_seconds: Maximum acceptable age in seconds
            
        Returns:
            True if state is fresh enough
        """
        with self._lock:
            if self._current_state is None:
                return False
            
            return self._current_state.is_fresh(max_age_seconds)

    def request_state_update(self) -> bool:
        """
        Request a state update from RYU controller.
        
        Returns:
            True if update request was successful
        """
        # This would typically trigger an async request to RYU
        # For now, we'll just log the request
        self._logger.info("Requesting network state update from RYU controller")
        return True

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            total_entries = len(self._cache)
            expired_entries = sum(1 for entry in self._cache.values() if entry.is_expired())
            
            return {
                "total_entries": total_entries,
                "expired_entries": expired_entries,
                "active_entries": total_entries - expired_entries,
                "current_state_available": self._current_state is not None,
                "current_state_fresh": self.is_state_fresh() if self._current_state else False,
                "cache_utilization": total_entries / self.max_entries
            }

    def _cleanup_expired_entries(self) -> None:
        """Clean up expired cache entries."""
        current_time = datetime.now()
        expired_keys = []
        
        for key, entry in self._cache.items():
            if entry.is_expired():
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
        
        # If cache is still too full, remove oldest entries
        if len(self._cache) > self.max_entries:
            sorted_entries = sorted(
                self._cache.items(),
                key=lambda x: x[1].last_accessed or x[1].cached_at
            )
            
            entries_to_remove = len(self._cache) - self.max_entries
            for i in range(entries_to_remove):
                key = sorted_entries[i][0]
                del self._cache[key]
        
        if expired_keys:
            self._logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")


class ContextCorrelationEngine:
    """Engine for correlating intents with network state context."""

    def __init__(self, state_cache: NetworkStateCache):
        """
        Initialize context correlation engine.
        
        Args:
            state_cache: NetworkState cache instance
        """
        self.state_cache = state_cache
        self._logger = logging.getLogger(__name__)
        self._resource_similarity_threshold = 0.7
        self._context_enrichment_enabled = True

    def correlate_intent_with_state(self, intent: IntentObject) -> ContextualizedIntent:
        """
        Correlate intent with current network state.
        
        Args:
            intent: Intent to correlate
            
        Returns:
            ContextualizedIntent with network context
        """
        current_state = self.state_cache.get_current_state()
        if current_state is None:
            self._logger.warning("No current network state available for correlation")
            return ContextualizedIntent(
                intent=intent,
                conflicts=["No current network state available"]
            )

        # Identify relevant resources from intent entities
        relevant_resources = self._identify_relevant_resources(intent, current_state)
        
        # Build network context
        network_context = self._build_network_context(intent, current_state, relevant_resources)
        
        # Detect potential conflicts
        conflicts = self._detect_conflicts(intent, current_state, relevant_resources)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(intent, current_state, conflicts)

        return ContextualizedIntent(
            intent=intent,
            relevant_resources=relevant_resources,
            network_context=network_context,
            conflicts=conflicts,
            recommendations=recommendations
        )

    def _identify_relevant_resources(self, intent: IntentObject, state: NetworkState) -> List[str]:
        """Identify network resources relevant to the intent."""
        relevant_resources = []
        
        # Extract resource references from entities
        for entity in intent.entities:
            if entity.type in ['resource', 'target', 'identifier']:
                # Check if entity value matches any network resource
                if state.is_resource_available(entity.value):
                    relevant_resources.append(entity.value)
                else:
                    # Try to find similar resources
                    similar = self._find_similar_resources(entity.value, state)
                    relevant_resources.extend(similar)
        
        # Add contextually relevant resources based on intent type
        if intent.intent_type.value == "configuration":
            # For configuration intents, include related infrastructure
            relevant_resources.extend(self._get_infrastructure_context(relevant_resources, state))
        
        return list(set(relevant_resources))  # Remove duplicates

    def _find_similar_resources(self, resource_name: str, state: NetworkState) -> List[str]:
        """Find resources with similar names."""
        similar = []
        resource_name_lower = resource_name.lower()
        
        # Check switches
        for switch in state.topology.switches:
            if resource_name_lower in switch.id.lower() or resource_name_lower in switch.name.lower():
                similar.append(switch.id)
        
        # Check links
        for link in state.topology.links:
            if resource_name_lower in link.id.lower():
                similar.append(link.id)
        
        # Check hosts
        for host in state.topology.hosts:
            if (resource_name_lower in host.id.lower() or 
                resource_name_lower in (host.ip_address or "").lower()):
                similar.append(host.id)
        
        return similar

    def _get_infrastructure_context(self, resources: List[str], state: NetworkState) -> List[str]:
        """Get additional infrastructure context for resources."""
        context_resources = []
        
        for resource_id in resources:
            # For switches, add connected hosts and links
            for switch in state.topology.switches:
                if switch.id == resource_id:
                    # Add connected hosts
                    for host in state.topology.hosts:
                        if host.connected_switch == switch.id:
                            context_resources.append(host.id)
                    
                    # Add connected links
                    for link in state.topology.links:
                        if link.source_switch == switch.id or link.destination_switch == switch.id:
                            context_resources.append(link.id)
        
        return context_resources

    def _build_network_context(self, intent: IntentObject, state: NetworkState, 
                             relevant_resources: List[str]) -> Dict[str, Any]:
        """Build comprehensive network context."""
        context = {
            "state_timestamp": state.timestamp.isoformat(),
            "topology_summary": {
                "switches": len(state.topology.switches),
                "links": len(state.topology.links),
                "hosts": len(state.topology.hosts)
            },
            "resource_details": {},
            "current_flows": len(state.flows),
            "active_anomalies": len([a for a in state.anomalies if a.resolved_at is None]),
            "network_metrics": {
                "bandwidth_utilization": state.metrics.bandwidth.utilization_percentage,
                "average_latency": state.metrics.latency.average_latency,
                "cpu_utilization": state.metrics.utilization.cpu_utilization
            }
        }
        
        # Add details for relevant resources
        for resource_id in relevant_resources:
            resource_info = self._get_resource_details(resource_id, state)
            if resource_info:
                context["resource_details"][resource_id] = resource_info
        
        return context

    def _get_resource_details(self, resource_id: str, state: NetworkState) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific resource."""
        # Check switches
        for switch in state.topology.switches:
            if switch.id == resource_id:
                return {
                    "type": "switch",
                    "name": switch.name,
                    "dpid": switch.dpid,
                    "ports": switch.ports,
                    "status": switch.status,
                    "utilization": state.get_resource_utilization(resource_id)
                }
        
        # Check links
        for link in state.topology.links:
            if link.id == resource_id:
                return {
                    "type": "link",
                    "source": link.source_switch,
                    "destination": link.destination_switch,
                    "bandwidth": link.bandwidth,
                    "latency": link.latency,
                    "status": link.status
                }
        
        # Check hosts
        for host in state.topology.hosts:
            if host.id == resource_id:
                return {
                    "type": "host",
                    "mac_address": host.mac_address,
                    "ip_address": host.ip_address,
                    "connected_switch": host.connected_switch,
                    "connected_port": host.connected_port,
                    "status": host.status
                }
        
        return None

    def _detect_conflicts(self, intent: IntentObject, state: NetworkState, 
                         relevant_resources: List[str]) -> List[str]:
        """Detect potential conflicts with current network state."""
        conflicts = []
        
        # Check resource availability
        for resource_id in relevant_resources:
            if not state.is_resource_available(resource_id):
                conflicts.append(f"Resource {resource_id} is not available or inactive")
        
        # Check for high utilization that might affect operations
        for resource_id in relevant_resources:
            utilization = state.get_resource_utilization(resource_id)
            if utilization and utilization > 90:
                conflicts.append(f"Resource {resource_id} has high utilization ({utilization:.1f}%)")
        
        # Check for active anomalies affecting relevant resources
        for anomaly in state.anomalies:
            if anomaly.resolved_at is None:  # Active anomaly
                affected_relevant = set(anomaly.affected_resources) & set(relevant_resources)
                if affected_relevant:
                    conflicts.append(f"Active {anomaly.severity.value} anomaly affecting resources: {affected_relevant}")
        
        # Check for configuration intent conflicts
        if intent.intent_type.value == "configuration":
            # Check if there are existing flows that might conflict
            for entity in intent.entities:
                if entity.type == "action" and entity.value.lower() in ["block", "drop", "deny"]:
                    # This might conflict with existing flows
                    conflicts.append("Blocking action may conflict with existing traffic flows")
        
        return conflicts

    def _generate_recommendations(self, intent: IntentObject, state: NetworkState, 
                                conflicts: List[str]) -> List[str]:
        """Generate recommendations based on context analysis."""
        recommendations = []
        
        # Recommend waiting if state is stale
        if not self.state_cache.is_state_fresh():
            recommendations.append("Consider waiting for fresh network state data before proceeding")
        
        # Recommend alternatives for unavailable resources
        for entity in intent.entities:
            if entity.type in ['resource', 'target']:
                if not state.is_resource_available(entity.value):
                    similar = self._find_similar_resources(entity.value, state)
                    if similar:
                        recommendations.append(f"Resource {entity.value} unavailable, consider alternatives: {similar}")
        
        # Recommend caution for high-impact operations
        if conflicts:
            recommendations.append("Review conflicts before proceeding with intent execution")
        
        # Recommend load balancing for high utilization
        high_util_resources = []
        for resource_id in self._get_all_resource_ids(state):
            utilization = state.get_resource_utilization(resource_id)
            if utilization and utilization > 80:
                high_util_resources.append(resource_id)
        
        if high_util_resources:
            recommendations.append(f"Consider load balancing for high utilization resources: {high_util_resources}")
        
        return recommendations

    def _get_all_resource_ids(self, state: NetworkState) -> List[str]:
        """Get all resource IDs from network state."""
        resource_ids = []
        resource_ids.extend([switch.id for switch in state.topology.switches])
        resource_ids.extend([link.id for link in state.topology.links])
        resource_ids.extend([host.id for host in state.topology.hosts])
        return resource_ids

    def enrich_context_for_llm(self, contextualized_intent: ContextualizedIntent) -> Dict[str, Any]:
        """
        Enrich context specifically for LLM processing.
        
        Args:
            contextualized_intent: Intent with basic context
            
        Returns:
            Enhanced context dictionary for LLM consumption
        """
        if not self._context_enrichment_enabled:
            return contextualized_intent.network_context

        enriched_context = contextualized_intent.network_context.copy()
        
        # Add semantic descriptions for LLM understanding
        enriched_context["semantic_descriptions"] = self._generate_semantic_descriptions(
            contextualized_intent
        )
        
        # Add relationship mappings
        enriched_context["resource_relationships"] = self._map_resource_relationships(
            contextualized_intent.relevant_resources,
            self.state_cache.get_current_state()
        )
        
        # Add operational context
        enriched_context["operational_context"] = self._build_operational_context(
            contextualized_intent
        )
        
        # Add constraint information
        enriched_context["constraints"] = self._identify_constraints(
            contextualized_intent
        )
        
        return enriched_context

    def _generate_semantic_descriptions(self, contextualized_intent: ContextualizedIntent) -> Dict[str, str]:
        """Generate human-readable descriptions for network elements."""
        descriptions = {}
        current_state = self.state_cache.get_current_state()
        
        if not current_state:
            return descriptions
        
        for resource_id in contextualized_intent.relevant_resources:
            resource_details = self._get_resource_details(resource_id, current_state)
            if resource_details:
                if resource_details["type"] == "switch":
                    descriptions[resource_id] = (
                        f"Network switch '{resource_details['name']}' with "
                        f"{len(resource_details['ports'])} ports, "
                        f"currently {resource_details['status']}"
                    )
                elif resource_details["type"] == "link":
                    descriptions[resource_id] = (
                        f"Network link connecting {resource_details['source']} to "
                        f"{resource_details['destination']}, "
                        f"bandwidth: {resource_details['bandwidth']}Mbps"
                    )
                elif resource_details["type"] == "host":
                    descriptions[resource_id] = (
                        f"Host device with IP {resource_details['ip_address']}, "
                        f"connected to {resource_details['connected_switch']}"
                    )
        
        return descriptions

    def _map_resource_relationships(self, relevant_resources: List[str], 
                                  state: Optional[NetworkState]) -> Dict[str, List[str]]:
        """Map relationships between relevant resources."""
        relationships = {}
        
        if not state:
            return relationships
        
        for resource_id in relevant_resources:
            relationships[resource_id] = []
            
            # Find connected resources
            for switch in state.topology.switches:
                if switch.id == resource_id:
                    # Find connected hosts
                    for host in state.topology.hosts:
                        if host.connected_switch == switch.id:
                            relationships[resource_id].append(f"hosts:{host.id}")
                    
                    # Find connected links
                    for link in state.topology.links:
                        if link.source_switch == switch.id or link.destination_switch == switch.id:
                            relationships[resource_id].append(f"links:{link.id}")
            
            # For links, add connected switches
            for link in state.topology.links:
                if link.id == resource_id:
                    relationships[resource_id].extend([
                        f"switches:{link.source_switch}",
                        f"switches:{link.destination_switch}"
                    ])
        
        return relationships

    def _build_operational_context(self, contextualized_intent: ContextualizedIntent) -> Dict[str, Any]:
        """Build operational context for the intent."""
        current_state = self.state_cache.get_current_state()
        
        operational_context = {
            "network_health": "unknown",
            "load_status": "unknown",
            "maintenance_mode": False,
            "recent_changes": []
        }
        
        if not current_state:
            return operational_context
        
        # Assess network health
        active_anomalies = [a for a in current_state.anomalies if a.resolved_at is None]
        if not active_anomalies:
            operational_context["network_health"] = "healthy"
        elif any(a.severity == AnomalySeverity.CRITICAL for a in active_anomalies):
            operational_context["network_health"] = "critical"
        elif any(a.severity == AnomalySeverity.HIGH for a in active_anomalies):
            operational_context["network_health"] = "degraded"
        else:
            operational_context["network_health"] = "minor_issues"
        
        # Assess load status
        bandwidth_util = current_state.metrics.bandwidth.utilization_percentage
        if bandwidth_util < 50:
            operational_context["load_status"] = "low"
        elif bandwidth_util < 80:
            operational_context["load_status"] = "moderate"
        else:
            operational_context["load_status"] = "high"
        
        # Check for maintenance indicators
        inactive_resources = []
        for switch in current_state.topology.switches:
            if switch.status != "active":
                inactive_resources.append(switch.id)
        
        if inactive_resources:
            operational_context["maintenance_mode"] = True
            operational_context["maintenance_resources"] = inactive_resources
        
        return operational_context

    def _identify_constraints(self, contextualized_intent: ContextualizedIntent) -> List[Dict[str, Any]]:
        """Identify constraints that may affect intent execution."""
        constraints = []
        current_state = self.state_cache.get_current_state()
        
        if not current_state:
            constraints.append({
                "type": "data_availability",
                "description": "No current network state available",
                "severity": "high"
            })
            return constraints
        
        # Resource availability constraints
        for resource_id in contextualized_intent.relevant_resources:
            if not current_state.is_resource_available(resource_id):
                constraints.append({
                    "type": "resource_availability",
                    "resource": resource_id,
                    "description": f"Resource {resource_id} is not available",
                    "severity": "high"
                })
        
        # Capacity constraints
        if current_state.metrics.bandwidth.utilization_percentage > 90:
            constraints.append({
                "type": "bandwidth_capacity",
                "description": "Network bandwidth utilization is very high",
                "current_utilization": current_state.metrics.bandwidth.utilization_percentage,
                "severity": "medium"
            })
        
        # Performance constraints
        if current_state.metrics.latency.average_latency > 100:  # 100ms threshold
            constraints.append({
                "type": "latency_performance",
                "description": "Network latency is elevated",
                "current_latency": current_state.metrics.latency.average_latency,
                "severity": "medium"
            })
        
        # Active anomaly constraints
        active_anomalies = [a for a in current_state.anomalies if a.resolved_at is None]
        for anomaly in active_anomalies:
            if anomaly.severity in [AnomalySeverity.HIGH, AnomalySeverity.CRITICAL]:
                constraints.append({
                    "type": "active_anomaly",
                    "anomaly_id": anomaly.id,
                    "description": f"Active {anomaly.severity.value} anomaly: {anomaly.description}",
                    "severity": "high" if anomaly.severity == AnomalySeverity.CRITICAL else "medium"
                })
        
        return constraints

    def get_correlation_metrics(self) -> Dict[str, Any]:
        """Get metrics about correlation engine performance."""
        cache_stats = self.state_cache.get_cache_stats()
        
        return {
            "cache_performance": cache_stats,
            "enrichment_enabled": self._context_enrichment_enabled,
            "similarity_threshold": self._resource_similarity_threshold,
            "last_correlation_time": datetime.now().isoformat()
        }


class AnomalyDetectionSystem:
    """System for detecting and classifying network anomalies."""

    def __init__(self, state_cache: NetworkStateCache):
        """
        Initialize anomaly detection system.
        
        Args:
            state_cache: NetworkState cache instance
        """
        self.state_cache = state_cache
        self._baseline_metrics = {}
        self._anomaly_thresholds = {
            "bandwidth_spike": 1.5,  # 1.5x normal usage (more sensitive)
            "latency_increase": 1.3,  # 1.3x normal latency (more sensitive)
            "cpu_utilization": 90.0,  # 90% CPU
            "memory_utilization": 85.0  # 85% memory
        }
        self._pattern_history = defaultdict(list)
        self._false_positive_feedback = {}
        self._learning_enabled = True
        self._detection_sensitivity = 1.0  # Multiplier for thresholds
        self._logger = logging.getLogger(__name__)

    def detect_anomalies(self, state: NetworkState) -> List[Anomaly]:
        """
        Detect anomalies in network state.
        
        Args:
            state: NetworkState to analyze
            
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        # Detect bandwidth anomalies
        bandwidth_anomalies = self._detect_bandwidth_anomalies(state)
        anomalies.extend(bandwidth_anomalies)
        
        # Detect latency anomalies
        latency_anomalies = self._detect_latency_anomalies(state)
        anomalies.extend(latency_anomalies)
        
        # Detect utilization anomalies
        utilization_anomalies = self._detect_utilization_anomalies(state)
        anomalies.extend(utilization_anomalies)
        
        # Detect topology anomalies
        topology_anomalies = self._detect_topology_anomalies(state)
        anomalies.extend(topology_anomalies)
        
        # Update baseline metrics AFTER detection to avoid interference
        self._update_baseline_metrics(state)
        
        self._logger.info(f"Detected {len(anomalies)} anomalies in network state")
        return anomalies

    def classify_anomaly_severity(self, anomaly: Anomaly, state: NetworkState) -> AnomalySeverity:
        """
        Classify anomaly severity based on impact.
        
        Args:
            anomaly: Anomaly to classify
            state: Current network state
            
        Returns:
            Severity level
        """
        if anomaly.type == AnomalyType.SWITCH_FAILURE:
            # Switch failures are always critical
            return AnomalySeverity.CRITICAL
        
        if anomaly.type == AnomalyType.LINK_FAILURE:
            # Check if this is a critical link
            affected_switches = len(anomaly.affected_resources)
            if affected_switches > 2:
                return AnomalySeverity.HIGH
            else:
                return AnomalySeverity.MEDIUM
        
        if anomaly.type == AnomalyType.TRAFFIC_SPIKE:
            # Check bandwidth utilization
            if state.metrics.bandwidth.utilization_percentage > 95:
                return AnomalySeverity.HIGH
            elif state.metrics.bandwidth.utilization_percentage > 80:
                return AnomalySeverity.MEDIUM
            else:
                return AnomalySeverity.LOW
        
        if anomaly.type == AnomalyType.LATENCY_INCREASE:
            # Check latency increase magnitude
            if "latency_multiplier" in anomaly.metrics:
                multiplier = anomaly.metrics["latency_multiplier"]
                if multiplier > 3.0:
                    return AnomalySeverity.HIGH
                elif multiplier > 2.0:
                    return AnomalySeverity.MEDIUM
                else:
                    return AnomalySeverity.LOW
        
        # Default to medium severity
        return AnomalySeverity.MEDIUM

    def generate_anomaly_response(self, anomaly: Anomaly, state: NetworkState) -> List[NetworkAction]:
        """
        Generate automatic response actions for anomaly.
        
        Args:
            anomaly: Anomaly to respond to
            state: Current network state
            
        Returns:
            List of response actions
        """
        actions = []
        
        if anomaly.type == AnomalyType.TRAFFIC_SPIKE:
            # Generate load balancing actions
            actions.extend(self._generate_load_balancing_actions(anomaly, state))
        
        elif anomaly.type == AnomalyType.LINK_FAILURE:
            # Generate rerouting actions
            actions.extend(self._generate_rerouting_actions(anomaly, state))
        
        elif anomaly.type == AnomalyType.SWITCH_FAILURE:
            # Generate failover actions
            actions.extend(self._generate_failover_actions(anomaly, state))
        
        elif anomaly.type == AnomalyType.SECURITY_THREAT:
            # Generate security response actions
            actions.extend(self._generate_security_response_actions(anomaly, state))
        
        return actions

    def _update_baseline_metrics(self, state: NetworkState) -> None:
        """Update baseline metrics for anomaly detection."""
        current_metrics = {
            "bandwidth_utilization": state.metrics.bandwidth.utilization_percentage,
            "average_latency": state.metrics.latency.average_latency,
            "cpu_utilization": state.metrics.utilization.cpu_utilization,
            "memory_utilization": state.metrics.utilization.memory_utilization
        }
        
        # Simple exponential moving average for baseline
        alpha = 0.1  # Smoothing factor
        for metric, value in current_metrics.items():
            if metric in self._baseline_metrics:
                self._baseline_metrics[metric] = (alpha * value + 
                                                (1 - alpha) * self._baseline_metrics[metric])
            else:
                self._baseline_metrics[metric] = value

    def _detect_bandwidth_anomalies(self, state: NetworkState) -> List[Anomaly]:
        """Detect bandwidth-related anomalies."""
        anomalies = []
        
        current_util = state.metrics.bandwidth.utilization_percentage
        baseline_util = self._baseline_metrics.get("bandwidth_utilization", 50.0)  # Default baseline
        
        # Use absolute thresholds for extreme values
        absolute_high_threshold = 85.0
        relative_threshold = baseline_util * self._anomaly_thresholds["bandwidth_spike"]
        
        # Detect if current utilization exceeds either absolute or relative threshold
        if current_util > absolute_high_threshold or (baseline_util > 0 and current_util > relative_threshold):
            spike_multiplier = current_util / max(baseline_util, 1.0)  # Avoid division by zero
            anomaly = Anomaly(
                id=f"bandwidth_spike_{int(time.time())}",
                type=AnomalyType.TRAFFIC_SPIKE,
                severity=AnomalySeverity.MEDIUM,
                description=f"Bandwidth utilization spike: {current_util:.1f}% (baseline: {baseline_util:.1f}%)",
                detected_at=datetime.now(),
                metrics={
                    "current_utilization": current_util,
                    "baseline_utilization": baseline_util,
                    "spike_multiplier": spike_multiplier,
                    "absolute_threshold": absolute_high_threshold,
                    "relative_threshold": relative_threshold
                }
            )
            anomalies.append(anomaly)
        
        return anomalies

    def _detect_latency_anomalies(self, state: NetworkState) -> List[Anomaly]:
        """Detect latency-related anomalies."""
        anomalies = []
        
        current_latency = state.metrics.latency.average_latency
        baseline_latency = self._baseline_metrics.get("average_latency", 10.0)  # Default baseline
        
        # Use absolute thresholds for extreme values
        absolute_high_threshold = 100.0  # 100ms is considered high latency
        relative_threshold = baseline_latency * self._anomaly_thresholds["latency_increase"]
        
        # Detect if current latency exceeds either absolute or relative threshold
        if current_latency > absolute_high_threshold or (baseline_latency > 0 and current_latency > relative_threshold):
            latency_multiplier = current_latency / max(baseline_latency, 1.0)  # Avoid division by zero
            anomaly = Anomaly(
                id=f"latency_increase_{int(time.time())}",
                type=AnomalyType.LATENCY_INCREASE,
                severity=AnomalySeverity.MEDIUM,
                description=f"Latency increase: {current_latency:.2f}ms (baseline: {baseline_latency:.2f}ms)",
                detected_at=datetime.now(),
                metrics={
                    "current_latency": current_latency,
                    "baseline_latency": baseline_latency,
                    "latency_multiplier": latency_multiplier,
                    "absolute_threshold": absolute_high_threshold,
                    "relative_threshold": relative_threshold
                }
            )
            anomalies.append(anomaly)
        
        return anomalies

    def _detect_utilization_anomalies(self, state: NetworkState) -> List[Anomaly]:
        """Detect resource utilization anomalies."""
        anomalies = []
        
        # Check CPU utilization
        if state.metrics.utilization.cpu_utilization > self._anomaly_thresholds["cpu_utilization"]:
            anomaly = Anomaly(
                id=f"cpu_high_{int(time.time())}",
                type=AnomalyType.TRAFFIC_SPIKE,
                severity=AnomalySeverity.HIGH,
                description=f"High CPU utilization: {state.metrics.utilization.cpu_utilization:.1f}%",
                detected_at=datetime.now(),
                metrics={"cpu_utilization": state.metrics.utilization.cpu_utilization}
            )
            anomalies.append(anomaly)
        
        # Check memory utilization
        if state.metrics.utilization.memory_utilization > self._anomaly_thresholds["memory_utilization"]:
            anomaly = Anomaly(
                id=f"memory_high_{int(time.time())}",
                type=AnomalyType.TRAFFIC_SPIKE,
                severity=AnomalySeverity.HIGH,
                description=f"High memory utilization: {state.metrics.utilization.memory_utilization:.1f}%",
                detected_at=datetime.now(),
                metrics={"memory_utilization": state.metrics.utilization.memory_utilization}
            )
            anomalies.append(anomaly)
        
        return anomalies

    def _detect_topology_anomalies(self, state: NetworkState) -> List[Anomaly]:
        """Detect topology-related anomalies."""
        anomalies = []
        
        # Check for inactive switches
        for switch in state.topology.switches:
            if switch.status != "active":
                anomaly = Anomaly(
                    id=f"switch_failure_{switch.id}_{int(time.time())}",
                    type=AnomalyType.SWITCH_FAILURE,
                    severity=AnomalySeverity.CRITICAL,
                    description=f"Switch {switch.id} is {switch.status}",
                    affected_resources=[switch.id],
                    detected_at=datetime.now(),
                    metrics={"switch_status": switch.status}
                )
                anomalies.append(anomaly)
        
        # Check for inactive links
        for link in state.topology.links:
            if link.status != "active":
                anomaly = Anomaly(
                    id=f"link_failure_{link.id}_{int(time.time())}",
                    type=AnomalyType.LINK_FAILURE,
                    severity=AnomalySeverity.HIGH,
                    description=f"Link {link.id} is {link.status}",
                    affected_resources=[link.id, link.source_switch, link.destination_switch],
                    detected_at=datetime.now(),
                    metrics={"link_status": link.status}
                )
                anomalies.append(anomaly)
        
        return anomalies

    def _generate_load_balancing_actions(self, anomaly: Anomaly, state: NetworkState) -> List[NetworkAction]:
        """Generate load balancing actions for traffic spikes."""
        actions = []
        
        # Simple load balancing by modifying flow priorities
        action = NetworkAction(
            id=f"load_balance_{int(time.time())}",
            type=ActionType.FLOW_MOD,
            target="all_switches",
            parameters={
                "action": "modify_priorities",
                "strategy": "distribute_load",
                "anomaly_id": anomaly.id
            },
            priority=5000,
            description="Load balancing response to traffic spike"
        )
        actions.append(action)
        
        return actions

    def _generate_rerouting_actions(self, anomaly: Anomaly, state: NetworkState) -> List[NetworkAction]:
        """Generate rerouting actions for link failures."""
        actions = []
        
        for resource in anomaly.affected_resources:
            if resource.startswith("link_"):
                action = NetworkAction(
                    id=f"reroute_{resource}_{int(time.time())}",
                    type=ActionType.FLOW_MOD,
                    target="affected_switches",
                    parameters={
                        "action": "reroute_traffic",
                        "failed_link": resource,
                        "anomaly_id": anomaly.id
                    },
                    priority=8000,
                    description=f"Reroute traffic around failed link {resource}"
                )
                actions.append(action)
        
        return actions

    def _generate_failover_actions(self, anomaly: Anomaly, state: NetworkState) -> List[NetworkAction]:
        """Generate failover actions for switch failures."""
        actions = []
        
        for resource in anomaly.affected_resources:
            if resource.startswith("switch_") or any(s.id == resource for s in state.topology.switches):
                action = NetworkAction(
                    id=f"failover_{resource}_{int(time.time())}",
                    type=ActionType.CONFIG_CHANGE,
                    target="backup_switches",
                    parameters={
                        "action": "activate_backup",
                        "failed_switch": resource,
                        "anomaly_id": anomaly.id
                    },
                    priority=9000,
                    description=f"Failover for failed switch {resource}"
                )
                actions.append(action)
        
        return actions

    def _generate_security_response_actions(self, anomaly: Anomaly, state: NetworkState) -> List[NetworkAction]:
        """Generate security response actions."""
        actions = []
        
        # Block suspicious traffic
        action = NetworkAction(
            id=f"security_block_{int(time.time())}",
            type=ActionType.FLOW_MOD,
            target="all_switches",
            parameters={
                "action": "block_suspicious_traffic",
                "anomaly_id": anomaly.id,
                "affected_resources": anomaly.affected_resources
            },
            priority=9500,
            description="Block suspicious traffic in response to security threat"
        )
        actions.append(action)
        
        return actions

    def learn_from_feedback(self, anomaly_id: str, is_false_positive: bool) -> None:
        """
        Learn from user feedback about anomaly detection accuracy.
        
        Args:
            anomaly_id: ID of the anomaly
            is_false_positive: Whether the anomaly was a false positive
        """
        if not self._learning_enabled:
            return
        
        self._false_positive_feedback[anomaly_id] = is_false_positive
        
        if is_false_positive:
            # Adjust thresholds to be less sensitive for similar patterns
            self._adjust_sensitivity_for_false_positive(anomaly_id)
            self._logger.info(f"Learned from false positive: {anomaly_id}")
        else:
            # Confirmed anomaly - potentially increase sensitivity
            self._adjust_sensitivity_for_true_positive(anomaly_id)
            self._logger.info(f"Confirmed anomaly: {anomaly_id}")

    def _adjust_sensitivity_for_false_positive(self, anomaly_id: str) -> None:
        """Adjust detection sensitivity after false positive feedback."""
        # Increase thresholds slightly to reduce false positives
        adjustment_factor = 1.1
        
        for threshold_key in self._anomaly_thresholds:
            self._anomaly_thresholds[threshold_key] *= adjustment_factor
        
        # Reduce overall detection sensitivity
        self._detection_sensitivity = max(0.5, self._detection_sensitivity * 0.95)

    def _adjust_sensitivity_for_true_positive(self, anomaly_id: str) -> None:
        """Adjust detection sensitivity after confirmed anomaly."""
        # Slightly decrease thresholds to catch similar anomalies earlier
        adjustment_factor = 0.98
        
        for threshold_key in self._anomaly_thresholds:
            self._anomaly_thresholds[threshold_key] *= adjustment_factor
        
        # Increase overall detection sensitivity slightly
        self._detection_sensitivity = min(2.0, self._detection_sensitivity * 1.02)

    def detect_pattern_anomalies(self, state: NetworkState) -> List[Anomaly]:
        """
        Detect anomalies based on historical patterns.
        
        Args:
            state: NetworkState to analyze
            
        Returns:
            List of pattern-based anomalies
        """
        anomalies = []
        
        # Analyze traffic patterns
        traffic_anomalies = self._detect_traffic_pattern_anomalies(state)
        anomalies.extend(traffic_anomalies)
        
        # Analyze topology change patterns
        topology_anomalies = self._detect_topology_change_patterns(state)
        anomalies.extend(topology_anomalies)
        
        # Analyze flow distribution patterns
        flow_anomalies = self._detect_flow_distribution_anomalies(state)
        anomalies.extend(flow_anomalies)
        
        return anomalies

    def _detect_traffic_pattern_anomalies(self, state: NetworkState) -> List[Anomaly]:
        """Detect anomalies in traffic patterns."""
        anomalies = []
        
        # Store current traffic pattern
        current_pattern = {
            "bandwidth_util": state.metrics.bandwidth.utilization_percentage,
            "latency": state.metrics.latency.average_latency,
            "timestamp": state.timestamp
        }
        
        self._pattern_history["traffic"].append(current_pattern)
        
        # Keep only recent history (last 100 entries)
        if len(self._pattern_history["traffic"]) > 100:
            self._pattern_history["traffic"] = self._pattern_history["traffic"][-100:]
        
        # Analyze for unusual patterns
        if len(self._pattern_history["traffic"]) >= 10:
            recent_patterns = self._pattern_history["traffic"][-10:]
            
            # Check for sudden spikes
            bandwidth_values = [p["bandwidth_util"] for p in recent_patterns]
            if self._is_sudden_spike(bandwidth_values):
                anomaly = Anomaly(
                    id=f"traffic_pattern_spike_{int(time.time())}",
                    type=AnomalyType.TRAFFIC_SPIKE,
                    severity=AnomalySeverity.MEDIUM,
                    description="Sudden traffic pattern spike detected",
                    detected_at=datetime.now(),
                    metrics={
                        "pattern_type": "sudden_spike",
                        "recent_values": bandwidth_values[-5:]
                    }
                )
                anomalies.append(anomaly)
        
        return anomalies

    def _detect_topology_change_patterns(self, state: NetworkState) -> List[Anomaly]:
        """Detect anomalies in topology changes."""
        anomalies = []
        
        # Store current topology signature
        topology_signature = {
            "switch_count": len(state.topology.switches),
            "link_count": len(state.topology.links),
            "host_count": len(state.topology.hosts),
            "active_switches": len([s for s in state.topology.switches if s.status == "active"]),
            "timestamp": state.timestamp
        }
        
        self._pattern_history["topology"].append(topology_signature)
        
        # Keep only recent history
        if len(self._pattern_history["topology"]) > 50:
            self._pattern_history["topology"] = self._pattern_history["topology"][-50:]
        
        # Check for rapid topology changes
        if len(self._pattern_history["topology"]) >= 5:
            recent_changes = self._pattern_history["topology"][-5:]
            
            # Check for frequent switch state changes
            switch_changes = [abs(recent_changes[i]["active_switches"] - recent_changes[i-1]["active_switches"]) 
                            for i in range(1, len(recent_changes))]
            
            if sum(switch_changes) > 2:  # More than 2 switch state changes in recent history
                anomaly = Anomaly(
                    id=f"topology_instability_{int(time.time())}",
                    type=AnomalyType.SWITCH_FAILURE,
                    severity=AnomalySeverity.HIGH,
                    description="Network topology instability detected",
                    detected_at=datetime.now(),
                    metrics={
                        "pattern_type": "topology_instability",
                        "switch_changes": switch_changes
                    }
                )
                anomalies.append(anomaly)
        
        return anomalies

    def _detect_flow_distribution_anomalies(self, state: NetworkState) -> List[Anomaly]:
        """Detect anomalies in flow distribution patterns."""
        anomalies = []
        
        # Analyze flow distribution across switches
        flow_distribution = defaultdict(int)
        for flow in state.flows:
            flow_distribution[flow.switch_id] += 1
        
        # Store current distribution
        distribution_pattern = {
            "total_flows": len(state.flows),
            "switch_distribution": dict(flow_distribution),
            "max_flows_per_switch": max(flow_distribution.values()) if flow_distribution else 0,
            "timestamp": state.timestamp
        }
        
        self._pattern_history["flow_distribution"].append(distribution_pattern)
        
        # Keep only recent history
        if len(self._pattern_history["flow_distribution"]) > 20:
            self._pattern_history["flow_distribution"] = self._pattern_history["flow_distribution"][-20:]
        
        # Check for uneven distribution
        if flow_distribution:
            avg_flows = sum(flow_distribution.values()) / len(flow_distribution)
            max_flows = max(flow_distribution.values())
            
            # If one switch has significantly more flows than average
            if max_flows > avg_flows * 3 and max_flows > 10:
                overloaded_switch = max(flow_distribution, key=flow_distribution.get)
                
                anomaly = Anomaly(
                    id=f"flow_imbalance_{int(time.time())}",
                    type=AnomalyType.TRAFFIC_SPIKE,
                    severity=AnomalySeverity.MEDIUM,
                    description=f"Flow distribution imbalance detected on switch {overloaded_switch}",
                    affected_resources=[overloaded_switch],
                    detected_at=datetime.now(),
                    metrics={
                        "pattern_type": "flow_imbalance",
                        "overloaded_switch": overloaded_switch,
                        "flow_count": max_flows,
                        "average_flows": avg_flows
                    }
                )
                anomalies.append(anomaly)
        
        return anomalies

    def _is_sudden_spike(self, values: List[float]) -> bool:
        """Check if there's a sudden spike in values."""
        if len(values) < 3:
            return False
        
        # Calculate rate of change
        recent_avg = sum(values[-3:]) / 3
        previous_avg = sum(values[:-3]) / max(1, len(values) - 3)
        
        # Spike if recent average is significantly higher
        return recent_avg > previous_avg * 2.0 * self._detection_sensitivity

    def get_detection_statistics(self) -> Dict[str, Any]:
        """Get statistics about anomaly detection performance."""
        total_feedback = len(self._false_positive_feedback)
        false_positives = sum(1 for is_fp in self._false_positive_feedback.values() if is_fp)
        
        return {
            "total_anomalies_reported": total_feedback,
            "false_positive_count": false_positives,
            "accuracy_rate": (total_feedback - false_positives) / max(1, total_feedback),
            "current_sensitivity": self._detection_sensitivity,
            "learning_enabled": self._learning_enabled,
            "pattern_history_size": {
                "traffic": len(self._pattern_history["traffic"]),
                "topology": len(self._pattern_history["topology"]),
                "flow_distribution": len(self._pattern_history["flow_distribution"])
            }
        }