"""
Health monitoring module for inter-service health checks.

This module provides comprehensive health monitoring capabilities
including service health checks, dependency verification, and
automated recovery actions.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    service_name: str
    status: HealthStatus
    timestamp: datetime
    response_time_ms: float
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class HealthCheckConfig:
    """Configuration for a health check."""
    service_name: str
    check_function: Callable
    interval_seconds: int = 30
    timeout_seconds: int = 5
    failure_threshold: int = 3  # Consecutive failures before marking unhealthy
    recovery_threshold: int = 2  # Consecutive successes before marking healthy


class HealthMonitor:
    """
    Comprehensive health monitoring for all system services.
    
    Features:
    - Periodic health checks for all services
    - Dependency verification
    - Automated recovery actions
    - Health history tracking
    - Alert generation for unhealthy services
    """
    
    def __init__(self):
        self.health_checks: Dict[str, HealthCheckConfig] = {}
        self.health_history: Dict[str, List[HealthCheckResult]] = {}
        self.failure_counts: Dict[str, int] = {}
        self.success_counts: Dict[str, int] = {}
        self._running = False
        self._check_tasks: Dict[str, asyncio.Task] = {}
        self._alert_callbacks: List[Callable] = []
    
    def register_health_check(self, config: HealthCheckConfig) -> None:
        """
        Register a health check for a service.
        
        Args:
            config: Health check configuration
        """
        self.health_checks[config.service_name] = config
        self.health_history[config.service_name] = []
        self.failure_counts[config.service_name] = 0
        self.success_counts[config.service_name] = 0
        
        logger.info(f"Registered health check for service: {config.service_name}")
    
    def register_alert_callback(self, callback: Callable) -> None:
        """
        Register a callback for health alerts.
        
        Args:
            callback: Function to call when health status changes
        """
        self._alert_callbacks.append(callback)
    
    async def start(self) -> None:
        """Start health monitoring for all registered services."""
        if self._running:
            logger.warning("HealthMonitor already running")
            return
        
        logger.info("Starting HealthMonitor...")
        self._running = True
        
        # Start health check tasks for each service
        for service_name, config in self.health_checks.items():
            task = asyncio.create_task(self._health_check_loop(config))
            self._check_tasks[service_name] = task
        
        logger.info(f"Started health monitoring for {len(self.health_checks)} services")
    
    async def stop(self) -> None:
        """Stop health monitoring."""
        if not self._running:
            return
        
        logger.info("Stopping HealthMonitor...")
        self._running = False
        
        # Cancel all health check tasks
        for service_name, task in self._check_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._check_tasks.clear()
        logger.info("HealthMonitor stopped")
    
    async def _health_check_loop(self, config: HealthCheckConfig) -> None:
        """
        Continuous health check loop for a service.
        
        Args:
            config: Health check configuration
        """
        service_name = config.service_name
        
        while self._running:
            try:
                # Perform health check
                result = await self._perform_health_check(config)
                
                # Store result in history
                self.health_history[service_name].append(result)
                
                # Keep only last 100 results
                if len(self.health_history[service_name]) > 100:
                    self.health_history[service_name] = self.health_history[service_name][-100:]
                
                # Update failure/success counts
                if result.status == HealthStatus.HEALTHY:
                    self.success_counts[service_name] += 1
                    self.failure_counts[service_name] = 0
                else:
                    self.failure_counts[service_name] += 1
                    self.success_counts[service_name] = 0
                
                # Check if we need to trigger alerts
                await self._check_alert_conditions(service_name, result, config)
                
                # Wait for next check
                await asyncio.sleep(config.interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in health check loop for {service_name}: {e}")
                await asyncio.sleep(config.interval_seconds)
    
    async def _perform_health_check(self, config: HealthCheckConfig) -> HealthCheckResult:
        """
        Perform a single health check.
        
        Args:
            config: Health check configuration
            
        Returns:
            Health check result
        """
        start_time = datetime.utcnow()
        
        try:
            # Execute health check with timeout
            result = await asyncio.wait_for(
                config.check_function(),
                timeout=config.timeout_seconds
            )
            
            end_time = datetime.utcnow()
            response_time_ms = (end_time - start_time).total_seconds() * 1000
            
            # Determine status from result
            if isinstance(result, dict):
                status_str = result.get("status", "unknown")
                status = HealthStatus(status_str) if status_str in [s.value for s in HealthStatus] else HealthStatus.UNKNOWN
                details = result
            elif isinstance(result, bool):
                status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                details = {"healthy": result}
            else:
                status = HealthStatus.UNKNOWN
                details = {"result": str(result)}
            
            return HealthCheckResult(
                service_name=config.service_name,
                status=status,
                timestamp=end_time,
                response_time_ms=response_time_ms,
                details=details
            )
            
        except asyncio.TimeoutError:
            end_time = datetime.utcnow()
            response_time_ms = (end_time - start_time).total_seconds() * 1000
            
            return HealthCheckResult(
                service_name=config.service_name,
                status=HealthStatus.UNHEALTHY,
                timestamp=end_time,
                response_time_ms=response_time_ms,
                error="Health check timeout"
            )
            
        except Exception as e:
            end_time = datetime.utcnow()
            response_time_ms = (end_time - start_time).total_seconds() * 1000
            
            return HealthCheckResult(
                service_name=config.service_name,
                status=HealthStatus.UNHEALTHY,
                timestamp=end_time,
                response_time_ms=response_time_ms,
                error=str(e)
            )
    
    async def _check_alert_conditions(self, 
                                     service_name: str, 
                                     result: HealthCheckResult,
                                     config: HealthCheckConfig) -> None:
        """
        Check if alert conditions are met and trigger alerts.
        
        Args:
            service_name: Name of the service
            result: Latest health check result
            config: Health check configuration
        """
        failure_count = self.failure_counts[service_name]
        success_count = self.success_counts[service_name]
        
        # Alert on reaching failure threshold
        if failure_count == config.failure_threshold:
            logger.warning(f"Service {service_name} reached failure threshold ({failure_count} consecutive failures)")
            await self._trigger_alert(service_name, "unhealthy", result)
        
        # Alert on recovery
        elif success_count == config.recovery_threshold and failure_count == 0:
            logger.info(f"Service {service_name} recovered ({success_count} consecutive successes)")
            await self._trigger_alert(service_name, "recovered", result)
    
    async def _trigger_alert(self, 
                           service_name: str, 
                           alert_type: str, 
                           result: HealthCheckResult) -> None:
        """
        Trigger alert callbacks.
        
        Args:
            service_name: Name of the service
            alert_type: Type of alert (unhealthy, recovered, etc.)
            result: Health check result
        """
        alert_data = {
            "service_name": service_name,
            "alert_type": alert_type,
            "status": result.status.value,
            "timestamp": result.timestamp.isoformat(),
            "error": result.error,
            "details": result.details
        }
        
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert_data)
                else:
                    callback(alert_data)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")
    
    def get_service_health(self, service_name: str) -> Optional[HealthCheckResult]:
        """
        Get latest health check result for a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Latest health check result or None
        """
        history = self.health_history.get(service_name, [])
        return history[-1] if history else None
    
    def get_all_health_status(self) -> Dict[str, Any]:
        """
        Get health status for all services.
        
        Returns:
            Dictionary with health status for all services
        """
        status = {
            "timestamp": datetime.utcnow().isoformat(),
            "services": {}
        }
        
        for service_name in self.health_checks.keys():
            latest = self.get_service_health(service_name)
            
            if latest:
                status["services"][service_name] = {
                    "status": latest.status.value,
                    "last_check": latest.timestamp.isoformat(),
                    "response_time_ms": latest.response_time_ms,
                    "consecutive_failures": self.failure_counts[service_name],
                    "consecutive_successes": self.success_counts[service_name],
                    "error": latest.error
                }
            else:
                status["services"][service_name] = {
                    "status": "unknown",
                    "error": "No health check results available"
                }
        
        return status
    
    def get_health_history(self, 
                          service_name: str, 
                          limit: int = 10) -> List[HealthCheckResult]:
        """
        Get health check history for a service.
        
        Args:
            service_name: Name of the service
            limit: Maximum number of results to return
            
        Returns:
            List of health check results
        """
        history = self.health_history.get(service_name, [])
        return history[-limit:] if history else []
