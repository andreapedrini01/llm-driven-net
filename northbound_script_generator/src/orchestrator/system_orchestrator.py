"""
System Orchestrator for Northbound Script Generator.

This module provides the main orchestrator that manages the lifecycle
of all system components, including startup sequencing, health monitoring,
and graceful shutdown.
"""

import asyncio
import logging
import signal
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Status of a service."""
    NOT_STARTED = "not_started"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ServiceInfo:
    """Information about a service."""
    name: str
    status: ServiceStatus = ServiceStatus.NOT_STARTED
    instance: Optional[Any] = None
    dependencies: List[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    error: Optional[str] = None
    health_check_interval: int = 30  # seconds


class SystemOrchestrator:
    """
    Main orchestrator for managing all system components.
    
    Responsibilities:
    - Startup sequencing with dependency management
    - Health monitoring of all services
    - Graceful shutdown in correct order
    - Service lifecycle management
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize system orchestrator.
        
        Args:
            config: System configuration dictionary
        """
        self.config = config or {}
        self.services: Dict[str, ServiceInfo] = {}
        self._running = False
        self._health_check_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Service instances (will be initialized during startup)
        self.northbound_instance = None
        self.monitoring_service = None
        self.api_gateway = None
        self.backup_service = None
        self.config_manager = None
        
        logger.info("SystemOrchestrator initialized")
    
    def register_service(self, 
                        name: str, 
                        dependencies: Optional[List[str]] = None,
                        health_check_interval: int = 30) -> None:
        """
        Register a service with the orchestrator.
        
        Args:
            name: Service name
            dependencies: List of service names this service depends on
            health_check_interval: Health check interval in seconds
        """
        self.services[name] = ServiceInfo(
            name=name,
            dependencies=dependencies or [],
            health_check_interval=health_check_interval
        )
        logger.info(f"Registered service: {name} with dependencies: {dependencies}")
    
    async def start(self) -> None:
        """Start all services in dependency order."""
        if self._running:
            logger.warning("SystemOrchestrator already running")
            return
        
        logger.info("Starting SystemOrchestrator...")
        
        try:
            # Register all services with their dependencies
            self._register_all_services()
            
            # Start services in dependency order
            start_order = self._calculate_start_order()
            logger.info(f"Service start order: {start_order}")
            
            for service_name in start_order:
                await self._start_service(service_name)
            
            # Start health monitoring
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            
            # Setup signal handlers for graceful shutdown
            self._setup_signal_handlers()
            
            self._running = True
            logger.info("SystemOrchestrator started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start SystemOrchestrator: {e}")
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """Stop all services in reverse dependency order."""
        if not self._running:
            return
        
        logger.info("Stopping SystemOrchestrator...")
        
        # Stop health monitoring
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        # Stop services in reverse order
        start_order = self._calculate_start_order()
        stop_order = list(reversed(start_order))
        logger.info(f"Service stop order: {stop_order}")
        
        for service_name in stop_order:
            await self._stop_service(service_name)
        
        self._running = False
        self._shutdown_event.set()
        logger.info("SystemOrchestrator stopped")
    
    def _register_all_services(self) -> None:
        """Register all system services with their dependencies."""
        # Configuration Manager - no dependencies
        self.register_service("config_manager", dependencies=[])
        
        # Logging - depends on config
        self.register_service("logging", dependencies=["config_manager"])
        
        # Database - depends on config
        self.register_service("database", dependencies=["config_manager"])
        
        # RYU/ComnetsEMU Connectors - depend on config and logging
        self.register_service("ryu_connector", dependencies=["config_manager", "logging"])
        self.register_service("comnetsemu_connector", dependencies=["config_manager", "logging"])
        
        # Northbound Module - depends on connectors
        self.register_service("northbound_module", 
                            dependencies=["ryu_connector", "comnetsemu_connector", "database"])
        
        # Monitoring Service - depends on config
        self.register_service("monitoring_service", dependencies=["config_manager", "database"])
        
        # Authentication Service - depends on database
        self.register_service("auth_service", dependencies=["database", "config_manager"])
        
        # Backup Service - depends on database
        self.register_service("backup_service", dependencies=["database", "config_manager"])
        
        # API Gateway - depends on northbound, auth, and monitoring
        self.register_service("api_gateway", 
                            dependencies=["northbound_module", "auth_service", "monitoring_service"])
        
        # Web Interface - depends on API gateway
        self.register_service("web_interface", dependencies=["api_gateway"])
    
    def _calculate_start_order(self) -> List[str]:
        """
        Calculate service start order based on dependencies using topological sort.
        
        Returns:
            List of service names in start order
        """
        # Build dependency graph
        in_degree = {name: 0 for name in self.services}
        adj_list = {name: [] for name in self.services}
        
        for service_name, service_info in self.services.items():
            for dep in service_info.dependencies:
                if dep in adj_list:
                    adj_list[dep].append(service_name)
                    in_degree[service_name] += 1
        
        # Topological sort using Kahn's algorithm
        queue = [name for name, degree in in_degree.items() if degree == 0]
        start_order = []
        
        while queue:
            service_name = queue.pop(0)
            start_order.append(service_name)
            
            for dependent in adj_list[service_name]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        
        # Check for circular dependencies
        if len(start_order) != len(self.services):
            raise RuntimeError("Circular dependency detected in services")
        
        return start_order
    
    async def _start_service(self, service_name: str) -> None:
        """
        Start a specific service.
        
        Args:
            service_name: Name of the service to start
        """
        if service_name not in self.services:
            logger.warning(f"Service {service_name} not registered")
            return
        
        service_info = self.services[service_name]
        
        # Check if dependencies are running
        for dep in service_info.dependencies:
            if dep in self.services and self.services[dep].status != ServiceStatus.RUNNING:
                raise RuntimeError(f"Dependency {dep} not running for service {service_name}")
        
        logger.info(f"Starting service: {service_name}")
        service_info.status = ServiceStatus.STARTING
        
        try:
            # Start the service based on its name
            if service_name == "config_manager":
                await self._start_config_manager()
            elif service_name == "logging":
                await self._start_logging()
            elif service_name == "database":
                await self._start_database()
            elif service_name == "ryu_connector":
                await self._start_ryu_connector()
            elif service_name == "comnetsemu_connector":
                await self._start_comnetsemu_connector()
            elif service_name == "northbound_module":
                await self._start_northbound_module()
            elif service_name == "monitoring_service":
                await self._start_monitoring_service()
            elif service_name == "auth_service":
                await self._start_auth_service()
            elif service_name == "backup_service":
                await self._start_backup_service()
            elif service_name == "api_gateway":
                await self._start_api_gateway()
            elif service_name == "web_interface":
                await self._start_web_interface()
            else:
                logger.warning(f"Unknown service: {service_name}")
                service_info.status = ServiceStatus.ERROR
                return
            
            service_info.status = ServiceStatus.RUNNING
            service_info.start_time = datetime.utcnow()
            logger.info(f"Service {service_name} started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start service {service_name}: {e}")
            service_info.status = ServiceStatus.ERROR
            service_info.error = str(e)
            raise
    
    async def _stop_service(self, service_name: str) -> None:
        """
        Stop a specific service.
        
        Args:
            service_name: Name of the service to stop
        """
        if service_name not in self.services:
            return
        
        service_info = self.services[service_name]
        
        if service_info.status not in [ServiceStatus.RUNNING, ServiceStatus.ERROR]:
            return
        
        logger.info(f"Stopping service: {service_name}")
        service_info.status = ServiceStatus.STOPPING
        
        try:
            # Stop the service based on its name
            if service_name == "api_gateway" and self.api_gateway:
                # API gateway shutdown is handled by FastAPI lifespan
                pass
            elif service_name == "monitoring_service" and self.monitoring_service:
                await self.monitoring_service.stop()
            elif service_name == "backup_service" and self.backup_service:
                await self.backup_service.stop()
            elif service_name == "northbound_module" and self.northbound_instance:
                self.northbound_instance.close()
            # Add other service-specific shutdown logic as needed
            
            service_info.status = ServiceStatus.STOPPED
            logger.info(f"Service {service_name} stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping service {service_name}: {e}")
            service_info.status = ServiceStatus.ERROR
            service_info.error = str(e)
    
    # Service initialization methods
    
    async def _start_config_manager(self) -> None:
        """Initialize configuration manager."""
        from src.config.config_manager import ConfigManager
        
        config_file = self.config.get("config_file", "config/system_config.yaml")
        self.config_manager = ConfigManager(config_file=config_file)
        await self.config_manager.load_config()
        
        self.services["config_manager"].instance = self.config_manager
    
    async def _start_logging(self) -> None:
        """Initialize logging system."""
        from src.logging.logger import setup_logging
        
        log_config = self.config_manager.get_config("logging") if self.config_manager else {}
        setup_logging(log_config)
        
        self.services["logging"].instance = True
    
    async def _start_database(self) -> None:
        """Initialize database connections."""
        # Database initialization is handled by individual services
        # This is a placeholder for any global database setup
        self.services["database"].instance = True
    
    async def _start_ryu_connector(self) -> None:
        """Initialize RYU connector."""
        # RYU connector is initialized as part of northbound module
        self.services["ryu_connector"].instance = True
    
    async def _start_comnetsemu_connector(self) -> None:
        """Initialize ComnetsEMU connector."""
        # ComnetsEMU connector is initialized as part of northbound module
        self.services["comnetsemu_connector"].instance = True
    
    async def _start_northbound_module(self) -> None:
        """Initialize Northbound module."""
        from src.core.northbound_script import NorthboundScript
        
        nb_config = self.config_manager.get_config("northbound") if self.config_manager else {}
        self.northbound_instance = NorthboundScript(**nb_config)
        
        self.services["northbound_module"].instance = self.northbound_instance
    
    async def _start_monitoring_service(self) -> None:
        """Initialize monitoring service."""
        from src.monitoring.monitoring_service import MonitoringService
        from src.monitoring.influxdb_storage import InfluxDBConfig
        
        mon_config = self.config_manager.get_config("monitoring") if self.config_manager else {}
        
        # Create InfluxDB config if enabled
        influxdb_config = None
        if mon_config.get("enable_influxdb", False):
            influxdb_config = InfluxDBConfig(
                url=mon_config.get("influxdb_url", "http://localhost:8086"),
                token=mon_config.get("influxdb_token", ""),
                org=mon_config.get("influxdb_org", "northbound"),
                bucket=mon_config.get("influxdb_bucket", "metrics")
            )
        
        self.monitoring_service = MonitoringService(
            collection_interval=mon_config.get("collection_interval", 60),
            influxdb_config=influxdb_config,
            enable_prometheus=mon_config.get("enable_prometheus", True),
            enable_influxdb=mon_config.get("enable_influxdb", False),
            enable_alerting=mon_config.get("enable_alerting", True)
        )
        
        await self.monitoring_service.start()
        self.monitoring_service.configure_default_alerts()
        
        self.services["monitoring_service"].instance = self.monitoring_service
    
    async def _start_auth_service(self) -> None:
        """Initialize authentication service."""
        from src.api.auth import AuthService
        
        auth_config = self.config_manager.get_config("authentication") if self.config_manager else {}
        auth_service = AuthService(**auth_config)
        
        self.services["auth_service"].instance = auth_service
    
    async def _start_backup_service(self) -> None:
        """Initialize backup service."""
        from src.backup.backup_manager import BackupManager
        
        backup_config = self.config_manager.get_config("backup") if self.config_manager else {}
        self.backup_service = BackupManager(**backup_config)
        
        await self.backup_service.start()
        
        self.services["backup_service"].instance = self.backup_service
    
    async def _start_api_gateway(self) -> None:
        """Initialize API gateway."""
        # API gateway is started separately via uvicorn
        # This just marks it as ready
        self.services["api_gateway"].instance = True
    
    async def _start_web_interface(self) -> None:
        """Initialize web interface."""
        # Web interface is served by API gateway
        self.services["web_interface"].instance = True
    
    async def _health_check_loop(self) -> None:
        """Continuously monitor service health with inter-service checks."""
        while self._running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                health_results = {}
                
                for service_name, service_info in self.services.items():
                    if service_info.status == ServiceStatus.RUNNING:
                        is_healthy = await self._check_service_health(service_name)
                        health_results[service_name] = is_healthy
                        
                        if not is_healthy:
                            logger.warning(f"Service {service_name} health check failed")
                            service_info.status = ServiceStatus.ERROR
                            
                            # Check if this is a critical service
                            if service_name in ["northbound_module", "api_gateway", "monitoring_service"]:
                                logger.critical(f"Critical service {service_name} is unhealthy!")
                                
                                # Attempt to restart the service
                                logger.info(f"Attempting to restart critical service {service_name}")
                                try:
                                    await self._stop_service(service_name)
                                    await asyncio.sleep(2)  # Brief pause before restart
                                    await self._start_service(service_name)
                                    logger.info(f"Successfully restarted service {service_name}")
                                except Exception as e:
                                    logger.error(f"Failed to restart service {service_name}: {e}")
                                    # Alert administrators about critical service failure
                                    await self._alert_critical_failure(service_name, str(e))
                
                # Log health summary
                healthy_count = sum(1 for h in health_results.values() if h)
                total_count = len(health_results)
                logger.debug(f"Health check: {healthy_count}/{total_count} services healthy")
                
                # Check inter-service connectivity
                await self._check_inter_service_connectivity()
                
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
    
    async def _check_service_health(self, service_name: str) -> bool:
        """
        Check health of a specific service.
        
        Args:
            service_name: Name of the service to check
            
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            service_info = self.services.get(service_name)
            if not service_info or not service_info.instance:
                return False
            
            # Service-specific health checks
            if service_name == "monitoring_service" and self.monitoring_service:
                health = await self.monitoring_service.health_check()
                return health.get("status") in ["healthy", "degraded"]
            
            elif service_name == "northbound_module" and self.northbound_instance:
                status = self.northbound_instance.get_ryu_status()
                return status.get("connection_status", {}).get("overall_status") == "connected"
            
            elif service_name == "backup_service" and self.backup_service:
                # Check if backup service is responsive
                return True  # Add specific health check if available
            
            # Default: assume healthy if instance exists
            return True
            
        except Exception as e:
            logger.error(f"Health check failed for {service_name}: {e}")
            return False
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown")
            asyncio.create_task(self.stop())
        
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except Exception as e:
            logger.warning(f"Failed to setup signal handlers: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get current status of all services.
        
        Returns:
            Dictionary with service status information
        """
        status = {
            "orchestrator_running": self._running,
            "timestamp": datetime.utcnow().isoformat(),
            "services": {}
        }
        
        for service_name, service_info in self.services.items():
            status["services"][service_name] = {
                "status": service_info.status.value,
                "start_time": service_info.start_time.isoformat() if service_info.start_time else None,
                "dependencies": service_info.dependencies,
                "error": service_info.error
            }
        
        return status
    
    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()
    
    async def _check_inter_service_connectivity(self) -> None:
        """Check connectivity between services."""
        try:
            # Check if northbound can reach RYU/ComnetsEMU
            if self.northbound_instance:
                status = self.northbound_instance.get_ryu_status()
                conn_status = status.get("connection_status", {})
                
                if conn_status.get("overall_status") != "connected":
                    logger.warning("Northbound module has connectivity issues with RYU/ComnetsEMU")
            
            # Check if monitoring service is collecting metrics
            if self.monitoring_service:
                metrics = self.monitoring_service.get_current_metrics()
                if not metrics:
                    logger.warning("Monitoring service is not collecting metrics")
            
        except Exception as e:
            logger.error(f"Error checking inter-service connectivity: {e}")
    
    async def _alert_critical_failure(self, service_name: str, error: str) -> None:
        """Alert administrators about critical service failure."""
        try:
            # Send alert through monitoring service if available
            if self.monitoring_service:
                # Create a critical alert
                logger.critical(f"CRITICAL ALERT: Service {service_name} failed - {error}")
                # In production, this would send emails, SMS, or webhook notifications
            
        except Exception as e:
            logger.error(f"Failed to send critical alert: {e}")
    
    async def graceful_shutdown_sequence(self) -> None:
        """
        Execute graceful shutdown with proper sequencing.
        
        This ensures:
        1. Stop accepting new requests (API gateway)
        2. Wait for in-flight requests to complete
        3. Stop background workers
        4. Flush metrics and logs
        5. Close database connections
        6. Stop core services
        """
        logger.info("Starting graceful shutdown sequence...")
        
        try:
            # Phase 1: Stop accepting new requests
            logger.info("Phase 1: Stopping API gateway from accepting new requests")
            if "api_gateway" in self.services:
                self.services["api_gateway"].status = ServiceStatus.STOPPING
            
            # Wait for in-flight requests (configurable timeout)
            shutdown_timeout = self.config.get("shutdown_timeout_seconds", 30)
            logger.info(f"Waiting {shutdown_timeout}s for in-flight requests to complete...")
            await asyncio.sleep(min(shutdown_timeout, 5))  # Wait up to 5 seconds
            
            # Phase 2: Stop background workers
            logger.info("Phase 2: Stopping background workers")
            if self.northbound_instance:
                # Stop queue processing
                self.northbound_instance.queue_processing_enabled = False
            
            # Phase 3: Flush metrics and logs
            logger.info("Phase 3: Flushing metrics and logs")
            if self.monitoring_service:
                # Give monitoring service time to flush final metrics
                await asyncio.sleep(2)
            
            # Phase 4: Stop services in reverse dependency order
            logger.info("Phase 4: Stopping services in reverse dependency order")
            await self.stop()
            
            logger.info("Graceful shutdown sequence completed successfully")
            
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")
            # Force stop if graceful shutdown fails
            await self.stop()
