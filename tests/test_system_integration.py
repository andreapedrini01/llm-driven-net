"""
Integration tests for the complete system orchestration.

Tests the integration of all components including:
- System orchestrator
- Service startup sequencing
- Health monitoring
- Graceful shutdown
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.orchestrator.system_orchestrator import SystemOrchestrator, ServiceStatus
from src.orchestrator.health_monitor import HealthMonitor, HealthCheckConfig, HealthStatus


class TestSystemOrchestrator:
    """Test system orchestrator functionality."""
    
    @pytest.fixture
    def config(self):
        """Test configuration."""
        return {
            "config_file": "config/test_config.yaml",
            "northbound": {
                "ryu_host": "localhost",
                "ryu_port": 8080,
                "comnetsemu_host": "localhost",
                "comnetsemu_port": 6653
            },
            "monitoring": {
                "collection_interval": 60,
                "enable_prometheus": False,
                "enable_influxdb": False,
                "enable_alerting": False
            }
        }
    
    @pytest.fixture
    def orchestrator(self, config):
        """Create orchestrator instance."""
        return SystemOrchestrator(config=config)
    
    def test_orchestrator_initialization(self, orchestrator):
        """Test orchestrator initializes correctly."""
        assert orchestrator is not None
        assert orchestrator.config is not None
        assert orchestrator.services == {}
        assert not orchestrator._running
    
    def test_service_registration(self, orchestrator):
        """Test service registration."""
        orchestrator.register_service("test_service", dependencies=["dep1", "dep2"])
        
        assert "test_service" in orchestrator.services
        assert orchestrator.services["test_service"].name == "test_service"
        assert orchestrator.services["test_service"].dependencies == ["dep1", "dep2"]
        assert orchestrator.services["test_service"].status == ServiceStatus.NOT_STARTED
    
    def test_start_order_calculation(self, orchestrator):
        """Test dependency-based start order calculation."""
        # Register services with dependencies
        orchestrator.register_service("service_a", dependencies=[])
        orchestrator.register_service("service_b", dependencies=["service_a"])
        orchestrator.register_service("service_c", dependencies=["service_a", "service_b"])
        orchestrator.register_service("service_d", dependencies=["service_b"])
        
        start_order = orchestrator._calculate_start_order()
        
        # Verify service_a comes before service_b
        assert start_order.index("service_a") < start_order.index("service_b")
        
        # Verify service_b comes before service_c and service_d
        assert start_order.index("service_b") < start_order.index("service_c")
        assert start_order.index("service_b") < start_order.index("service_d")
        
        # Verify all services are in the order
        assert len(start_order) == 4
        assert set(start_order) == {"service_a", "service_b", "service_c", "service_d"}
    
    def test_circular_dependency_detection(self, orchestrator):
        """Test detection of circular dependencies."""
        orchestrator.register_service("service_a", dependencies=["service_b"])
        orchestrator.register_service("service_b", dependencies=["service_a"])
        
        with pytest.raises(RuntimeError, match="Circular dependency"):
            orchestrator._calculate_start_order()
    
    def test_get_system_status(self, orchestrator):
        """Test getting system status."""
        orchestrator.register_service("test_service", dependencies=[])
        
        status = orchestrator.get_system_status()
        
        assert "orchestrator_running" in status
        assert "timestamp" in status
        assert "services" in status
        assert "test_service" in status["services"]
        assert status["services"]["test_service"]["status"] == ServiceStatus.NOT_STARTED.value


class TestHealthMonitor:
    """Test health monitoring functionality."""
    
    @pytest.fixture
    def health_monitor(self):
        """Create health monitor instance."""
        return HealthMonitor()
    
    @pytest.fixture
    def mock_health_check(self):
        """Create mock health check function."""
        async def check():
            return {"status": "healthy", "details": "All good"}
        return check
    
    def test_health_monitor_initialization(self, health_monitor):
        """Test health monitor initializes correctly."""
        assert health_monitor is not None
        assert health_monitor.health_checks == {}
        assert not health_monitor._running
    
    def test_register_health_check(self, health_monitor, mock_health_check):
        """Test registering a health check."""
        config = HealthCheckConfig(
            service_name="test_service",
            check_function=mock_health_check,
            interval_seconds=30
        )
        
        health_monitor.register_health_check(config)
        
        assert "test_service" in health_monitor.health_checks
        assert health_monitor.health_checks["test_service"] == config
        assert "test_service" in health_monitor.health_history
        assert health_monitor.failure_counts["test_service"] == 0
    
    @pytest.mark.asyncio
    async def test_perform_health_check_success(self, health_monitor, mock_health_check):
        """Test performing a successful health check."""
        config = HealthCheckConfig(
            service_name="test_service",
            check_function=mock_health_check
        )
        
        result = await health_monitor._perform_health_check(config)
        
        assert result.service_name == "test_service"
        assert result.status == HealthStatus.HEALTHY
        assert result.response_time_ms > 0
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_perform_health_check_timeout(self, health_monitor):
        """Test health check timeout handling."""
        async def slow_check():
            await asyncio.sleep(10)
            return {"status": "healthy"}
        
        config = HealthCheckConfig(
            service_name="test_service",
            check_function=slow_check,
            timeout_seconds=1
        )
        
        result = await health_monitor._perform_health_check(config)
        
        assert result.service_name == "test_service"
        assert result.status == HealthStatus.UNHEALTHY
        assert result.error == "Health check timeout"
    
    @pytest.mark.asyncio
    async def test_perform_health_check_error(self, health_monitor):
        """Test health check error handling."""
        async def failing_check():
            raise Exception("Service unavailable")
        
        config = HealthCheckConfig(
            service_name="test_service",
            check_function=failing_check
        )
        
        result = await health_monitor._perform_health_check(config)
        
        assert result.service_name == "test_service"
        assert result.status == HealthStatus.UNHEALTHY
        assert "Service unavailable" in result.error
    
    def test_get_all_health_status(self, health_monitor, mock_health_check):
        """Test getting health status for all services."""
        config = HealthCheckConfig(
            service_name="test_service",
            check_function=mock_health_check
        )
        
        health_monitor.register_health_check(config)
        
        status = health_monitor.get_all_health_status()
        
        assert "timestamp" in status
        assert "services" in status
        assert "test_service" in status["services"]
    
    @pytest.mark.asyncio
    async def test_alert_on_failure_threshold(self, health_monitor):
        """Test alert triggering on failure threshold."""
        alert_triggered = False
        alert_data = None
        
        def alert_callback(data):
            nonlocal alert_triggered, alert_data
            alert_triggered = True
            alert_data = data
        
        health_monitor.register_alert_callback(alert_callback)
        
        async def failing_check():
            return {"status": "unhealthy"}
        
        config = HealthCheckConfig(
            service_name="test_service",
            check_function=failing_check,
            failure_threshold=3
        )
        
        health_monitor.register_health_check(config)
        
        # Simulate 3 consecutive failures
        for _ in range(3):
            result = await health_monitor._perform_health_check(config)
            health_monitor.failure_counts["test_service"] += 1
            await health_monitor._check_alert_conditions("test_service", result, config)
        
        assert alert_triggered
        assert alert_data["service_name"] == "test_service"
        assert alert_data["alert_type"] == "unhealthy"


class TestSystemIntegration:
    """Test complete system integration."""
    
    @pytest.mark.asyncio
    async def test_basic_startup_shutdown(self):
        """Test basic system startup and shutdown."""
        config = {
            "monitoring": {
                "enable_prometheus": False,
                "enable_influxdb": False,
                "enable_alerting": False
            }
        }
        
        orchestrator = SystemOrchestrator(config=config)
        
        # Mock service initialization to avoid actual service startup
        with patch.object(orchestrator, '_start_config_manager', new_callable=AsyncMock):
            with patch.object(orchestrator, '_start_logging', new_callable=AsyncMock):
                with patch.object(orchestrator, '_start_database', new_callable=AsyncMock):
                    # Start orchestrator
                    await orchestrator.start()
                    
                    assert orchestrator._running
                    
                    # Stop orchestrator
                    await orchestrator.stop()
                    
                    assert not orchestrator._running
    
    @pytest.mark.asyncio
    async def test_service_dependency_startup(self):
        """Test services start in correct dependency order."""
        config = {}
        orchestrator = SystemOrchestrator(config=config)
        
        start_sequence = []
        
        async def mock_start(service_name):
            start_sequence.append(service_name)
        
        # Mock all service start methods
        orchestrator._start_config_manager = lambda: mock_start("config_manager")
        orchestrator._start_logging = lambda: mock_start("logging")
        orchestrator._start_database = lambda: mock_start("database")
        orchestrator._start_ryu_connector = lambda: mock_start("ryu_connector")
        orchestrator._start_comnetsemu_connector = lambda: mock_start("comnetsemu_connector")
        orchestrator._start_northbound_module = lambda: mock_start("northbound_module")
        orchestrator._start_monitoring_service = lambda: mock_start("monitoring_service")
        orchestrator._start_auth_service = lambda: mock_start("auth_service")
        orchestrator._start_backup_service = lambda: mock_start("backup_service")
        orchestrator._start_api_gateway = lambda: mock_start("api_gateway")
        orchestrator._start_web_interface = lambda: mock_start("web_interface")
        
        # Disable health monitoring for this test
        orchestrator._health_check_task = None
        
        try:
            await orchestrator.start()
            
            # Verify config_manager starts before logging
            assert start_sequence.index("config_manager") < start_sequence.index("logging")
            
            # Verify connectors start before northbound_module
            assert start_sequence.index("ryu_connector") < start_sequence.index("northbound_module")
            assert start_sequence.index("comnetsemu_connector") < start_sequence.index("northbound_module")
            
            # Verify northbound_module starts before api_gateway
            assert start_sequence.index("northbound_module") < start_sequence.index("api_gateway")
            
        finally:
            await orchestrator.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
