#!/usr/bin/env python3
"""
System startup script with integrated orchestrator and API gateway.

This script starts the complete Northbound Script Generator system
with all components properly wired together.
"""

import asyncio
import logging
import sys
import uvicorn
from pathlib import Path
from typing import Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestrator.system_orchestrator import SystemOrchestrator
from src.api.gateway_app import create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/system.log')
    ]
)

logger = logging.getLogger(__name__)


class IntegratedSystem:
    """Integrated system that manages orchestrator and API gateway."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.orchestrator = SystemOrchestrator(config=config)
        self.action_tracker: Dict = {}
        self.app = None
        self.server = None
    
    async def start(self):
        """Start the integrated system."""
        logger.info("=" * 80)
        logger.info("Starting Northbound Script Generator Integrated System")
        logger.info("=" * 80)
        
        # Create logs directory
        Path("logs").mkdir(exist_ok=True)
        
        try:
            # Start orchestrator (this initializes all services)
            await self.orchestrator.start()
            
            # Get service instances from orchestrator
            northbound_instance = self.orchestrator.northbound_instance
            monitoring_service = self.orchestrator.monitoring_service
            
            # Create FastAPI app with integrated services
            self.app = create_app(
                northbound_instance=northbound_instance,
                monitoring_service=monitoring_service,
                action_tracker=self.action_tracker
            )
            
            # Print system status
            status = self.orchestrator.get_system_status()
            logger.info("System Status:")
            for service_name, service_status in status["services"].items():
                logger.info(f"  {service_name}: {service_status['status']}")
            
            logger.info("=" * 80)
            logger.info("System started successfully!")
            logger.info("API Gateway: http://localhost:8000")
            logger.info("API Documentation: http://localhost:8000/docs")
            logger.info("Prometheus Metrics: http://localhost:8000/metrics")
            logger.info("=" * 80)
            
            # Start uvicorn server
            config = uvicorn.Config(
                self.app,
                host="0.0.0.0",
                port=8000,
                log_level="info",
                access_log=True
            )
            self.server = uvicorn.Server(config)
            
            # Run server
            await self.server.serve()
            
        except Exception as e:
            logger.error(f"System startup error: {e}", exc_info=True)
            await self.stop()
            raise
    
    async def stop(self):
        """Stop the integrated system."""
        logger.info("Initiating graceful shutdown...")
        
        # Stop uvicorn server
        if self.server:
            self.server.should_exit = True
        
        # Stop orchestrator (this stops all services in correct order)
        await self.orchestrator.stop()
        
        logger.info("System shutdown complete")


async def main():
    """Main entry point."""
    
    # System configuration
    config = {
        "config_file": "config/system_config.yaml",
        "northbound": {
            "ryu_host": "localhost",
            "ryu_port": 8080,
            "comnetsemu_host": "localhost",
            "comnetsemu_port": 6653,
            "max_retries": 3,
            "retry_delay": 2,
            "queue_processing_enabled": True,
            "queue_processing_interval": 30
        },
        "monitoring": {
            "collection_interval": 60,
            "enable_prometheus": True,
            "enable_influxdb": False,
            "enable_alerting": True,
            "influxdb_url": "http://localhost:8086",
            "influxdb_token": "",
            "influxdb_org": "northbound",
            "influxdb_bucket": "metrics"
        },
        "authentication": {
            "secret_key": "your-secret-key-change-in-production",
            "algorithm": "HS256",
            "access_token_expire_minutes": 30
        },
        "backup": {
            "backup_dir": "./backups",
            "retention_days": 7,
            "schedule_enabled": True,
            "schedule_interval_hours": 1
        }
    }
    
    # Create and start integrated system
    system = IntegratedSystem(config)
    
    try:
        await system.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        await system.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown complete")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
