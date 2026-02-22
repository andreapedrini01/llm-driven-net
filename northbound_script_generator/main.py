#!/usr/bin/env python3
"""
Main entry point for Northbound Script Generator system.

This script initializes and starts all system components using the
SystemOrchestrator for proper dependency management and lifecycle control.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestrator.system_orchestrator import SystemOrchestrator

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


async def main():
    """Main entry point."""
    logger.info("=" * 80)
    logger.info("Starting Northbound Script Generator System")
    logger.info("=" * 80)
    
    # Create logs directory if it doesn't exist
    Path("logs").mkdir(exist_ok=True)
    
    # Load configuration
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
            "enable_influxdb": False,  # Disable by default, enable if InfluxDB is available
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
    
    # Create orchestrator
    orchestrator = SystemOrchestrator(config=config)
    
    try:
        # Start all services
        await orchestrator.start()
        
        # Print system status
        status = orchestrator.get_system_status()
        logger.info("System Status:")
        for service_name, service_status in status["services"].items():
            logger.info(f"  {service_name}: {service_status['status']}")
        
        logger.info("=" * 80)
        logger.info("System started successfully!")
        logger.info("API Gateway available at: http://localhost:8000")
        logger.info("API Documentation: http://localhost:8000/docs")
        logger.info("Prometheus Metrics: http://localhost:8000/metrics")
        logger.info("=" * 80)
        
        # Wait for shutdown signal
        await orchestrator.wait_for_shutdown()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"System error: {e}", exc_info=True)
    finally:
        # Graceful shutdown
        logger.info("Initiating graceful shutdown...")
        await orchestrator.stop()
        logger.info("System shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown complete")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
