"""Load balancer for distributing requests across multiple instances."""

import logging
import random
import threading
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import requests
from requests.exceptions import RequestException


class LoadBalancingStrategy(str, Enum):
    """Load balancing strategies."""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    RANDOM = "random"
    IP_HASH = "ip_hash"


@dataclass
class InstanceInfo:
    """Information about a backend instance."""
    instance_id: str
    host: str
    port: int
    weight: int = 1
    healthy: bool = True
    active_connections: int = 0
    total_requests: int = 0
    failed_requests: int = 0
    last_health_check: Optional[datetime] = None
    response_time_avg: float = 0.0


class LoadBalancer:
    """
    Load balancer for distributing requests across multiple instances.
    
    Features:
    - Multiple load balancing strategies
    - Health checking
    - Automatic failover
    - Connection tracking
    - Metrics collection
    """
    
    def __init__(
        self,
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN,
        health_check_interval: int = 30,
        health_check_timeout: int = 5,
        health_check_path: str = "/health"
    ):
        self.logger = logging.getLogger("LoadBalancer")
        self.strategy = strategy
        self.health_check_interval = health_check_interval
        self.health_check_timeout = health_check_timeout
        self.health_check_path = health_check_path
        
        # Backend instances
        self.instances: Dict[str, InstanceInfo] = {}
        self._instances_lock = threading.RLock()
        
        # Round robin counter
        self._round_robin_index = 0
        
        # Health check thread
        self._health_check_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Statistics
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_instances": 0,
            "healthy_instances": 0,
            "last_health_check": None
        }
        
        self.logger.info(f"LoadBalancer initialized with strategy: {strategy}")
    
    def add_instance(
        self,
        instance_id: str,
        host: str,
        port: int,
        weight: int = 1
    ):
        """Add a backend instance."""
        with self._instances_lock:
            if instance_id in self.instances:
                self.logger.warning(f"Instance {instance_id} already exists, updating")
            
            self.instances[instance_id] = InstanceInfo(
                instance_id=instance_id,
                host=host,
                port=port,
                weight=weight,
                healthy=True,
                last_health_check=datetime.now()
            )
            
            self.stats["total_instances"] = len(self.instances)
            self.stats["healthy_instances"] = sum(
                1 for inst in self.instances.values() if inst.healthy
            )
            
            self.logger.info(f"Added instance {instance_id} at {host}:{port}")
    
    def remove_instance(self, instance_id: str):
        """Remove a backend instance."""
        with self._instances_lock:
            if instance_id in self.instances:
                del self.instances[instance_id]
                
                self.stats["total_instances"] = len(self.instances)
                self.stats["healthy_instances"] = sum(
                    1 for inst in self.instances.values() if inst.healthy
                )
                
                self.logger.info(f"Removed instance {instance_id}")
            else:
                self.logger.warning(f"Instance {instance_id} not found")
    
    def get_instance(self, client_ip: Optional[str] = None) -> Optional[InstanceInfo]:
        """Get next instance based on load balancing strategy."""
        with self._instances_lock:
            # Filter healthy instances
            healthy_instances = [
                inst for inst in self.instances.values() if inst.healthy
            ]
            
            if not healthy_instances:
                self.logger.error("No healthy instances available")
                return None
            
            # Select instance based on strategy
            if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
                instance = self._round_robin_select(healthy_instances)
            
            elif self.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
                instance = self._least_connections_select(healthy_instances)
            
            elif self.strategy == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN:
                instance = self._weighted_round_robin_select(healthy_instances)
            
            elif self.strategy == LoadBalancingStrategy.RANDOM:
                instance = random.choice(healthy_instances)
            
            elif self.strategy == LoadBalancingStrategy.IP_HASH:
                instance = self._ip_hash_select(healthy_instances, client_ip)
            
            else:
                instance = healthy_instances[0]
            
            # Increment connection count
            instance.active_connections += 1
            
            return instance
    
    def _round_robin_select(self, instances: List[InstanceInfo]) -> InstanceInfo:
        """Round robin selection."""
        instance = instances[self._round_robin_index % len(instances)]
        self._round_robin_index += 1
        return instance
    
    def _least_connections_select(self, instances: List[InstanceInfo]) -> InstanceInfo:
        """Least connections selection."""
        return min(instances, key=lambda x: x.active_connections)
    
    def _weighted_round_robin_select(self, instances: List[InstanceInfo]) -> InstanceInfo:
        """Weighted round robin selection."""
        # Create weighted list
        weighted_instances = []
        for inst in instances:
            weighted_instances.extend([inst] * inst.weight)
        
        if not weighted_instances:
            return instances[0]
        
        instance = weighted_instances[self._round_robin_index % len(weighted_instances)]
        self._round_robin_index += 1
        return instance
    
    def _ip_hash_select(
        self,
        instances: List[InstanceInfo],
        client_ip: Optional[str]
    ) -> InstanceInfo:
        """IP hash selection for session affinity."""
        if not client_ip:
            return instances[0]
        
        # Hash client IP to select instance
        hash_value = hash(client_ip)
        index = hash_value % len(instances)
        return instances[index]
    
    def release_instance(self, instance_id: str, success: bool, response_time: float):
        """Release instance after request completion."""
        with self._instances_lock:
            if instance_id not in self.instances:
                return
            
            instance = self.instances[instance_id]
            instance.active_connections = max(0, instance.active_connections - 1)
            instance.total_requests += 1
            
            if success:
                self.stats["successful_requests"] += 1
                
                # Update average response time
                total_time = instance.response_time_avg * (instance.total_requests - 1)
                instance.response_time_avg = (total_time + response_time) / instance.total_requests
            else:
                instance.failed_requests += 1
                self.stats["failed_requests"] += 1
            
            self.stats["total_requests"] += 1
    
    def start_health_checks(self):
        """Start health check thread."""
        if self._running:
            self.logger.warning("Health checks already running")
            return
        
        self._running = True
        self._health_check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True,
            name="HealthChecker"
        )
        self._health_check_thread.start()
        
        self.logger.info("Started health check thread")
    
    def stop_health_checks(self):
        """Stop health check thread."""
        if not self._running:
            return
        
        self._running = False
        
        if self._health_check_thread:
            self._health_check_thread.join(timeout=10)
        
        self.logger.info("Stopped health check thread")
    
    def _health_check_loop(self):
        """Health check loop."""
        self.logger.info("Health check loop started")
        
        while self._running:
            try:
                self._perform_health_checks()
                time.sleep(self.health_check_interval)
            
            except Exception as e:
                self.logger.error(f"Error in health check loop: {e}")
                time.sleep(5)
        
        self.logger.info("Health check loop stopped")
    
    def _perform_health_checks(self):
        """Perform health checks on all instances."""
        with self._instances_lock:
            instances = list(self.instances.values())
        
        for instance in instances:
            try:
                url = f"http://{instance.host}:{instance.port}{self.health_check_path}"
                
                start_time = time.time()
                response = requests.get(url, timeout=self.health_check_timeout)
                response_time = time.time() - start_time
                
                # Check if healthy
                was_healthy = instance.healthy
                instance.healthy = response.status_code == 200
                instance.last_health_check = datetime.now()
                
                # Log status changes
                if not was_healthy and instance.healthy:
                    self.logger.info(f"Instance {instance.instance_id} is now healthy")
                elif was_healthy and not instance.healthy:
                    self.logger.warning(f"Instance {instance.instance_id} is now unhealthy")
            
            except RequestException as e:
                was_healthy = instance.healthy
                instance.healthy = False
                instance.last_health_check = datetime.now()
                
                if was_healthy:
                    self.logger.warning(
                        f"Instance {instance.instance_id} health check failed: {e}"
                    )
            
            except Exception as e:
                self.logger.error(f"Unexpected error checking {instance.instance_id}: {e}")
        
        # Update statistics
        with self._instances_lock:
            self.stats["healthy_instances"] = sum(
                1 for inst in self.instances.values() if inst.healthy
            )
            self.stats["last_health_check"] = datetime.now().isoformat()
    
    def get_instance_stats(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific instance."""
        with self._instances_lock:
            if instance_id not in self.instances:
                return None
            
            instance = self.instances[instance_id]
            
            success_rate = 0.0
            if instance.total_requests > 0:
                success_rate = (
                    (instance.total_requests - instance.failed_requests) /
                    instance.total_requests * 100
                )
            
            return {
                "instance_id": instance.instance_id,
                "host": instance.host,
                "port": instance.port,
                "healthy": instance.healthy,
                "active_connections": instance.active_connections,
                "total_requests": instance.total_requests,
                "failed_requests": instance.failed_requests,
                "success_rate": success_rate,
                "response_time_avg": instance.response_time_avg,
                "last_health_check": instance.last_health_check.isoformat() if instance.last_health_check else None
            }
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all instances."""
        with self._instances_lock:
            instance_stats = {
                inst_id: self.get_instance_stats(inst_id)
                for inst_id in self.instances.keys()
            }
            
            return {
                "load_balancer": {
                    "strategy": self.strategy.value,
                    **self.stats
                },
                "instances": instance_stats
            }
