#!/usr/bin/env python3
"""
Demo script for the monitoring system.

This script demonstrates how to use the comprehensive monitoring system
including metrics collection, Prometheus export, alerting, and InfluxDB storage.
"""

import asyncio
import time
import random
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import monitoring components
from src.monitoring import (
    MonitoringService,
    InfluxDBConfig,
    AlertThreshold,
    AlertSeverity,
    NotificationChannel
)


async def demo_monitoring_system():
    """Demonstrate the monitoring system capabilities."""
    logger.info("Starting monitoring system demo...")
    
    # Configure InfluxDB (optional - will work without it)
    influxdb_config = InfluxDBConfig(
        url="http://localhost:8086",
        token="your-influxdb-token",  # Replace with actual token
        org="northbound-org",
        bucket="northbound-metrics"
    )
    
    # Initialize monitoring service
    monitoring = MonitoringService(
        collection_interval=10,  # Collect metrics every 10 seconds for demo
        influxdb_config=influxdb_config,
        enable_prometheus=True,
        enable_influxdb=False,  # Disable for demo (requires InfluxDB setup)
        enable_alerting=True
    )
    
    try:
        # Start monitoring
        await monitoring.start()
        
        # Configure default alerts
        monitoring.configure_default_alerts()
        
        # Add custom alert thresholds
        custom_threshold = AlertThreshold(
            metric_name="business.actions_per_minute",
            operator="<",
            value=5.0,
            severity=AlertSeverity.WARNING,
            duration_seconds=30,
            description="Low action throughput detected"
        )
        monitoring.add_alert_threshold(custom_threshold)
        
        # Add email notification channel (example configuration)
        email_channel = NotificationChannel(
            name="admin_email",
            type="email",
            config={
                "smtp_host": "smtp.gmail.com",
                "smtp_port": 587,
                "use_tls": True,
                "from_email": "alerts@yourcompany.com",
                "to_emails": ["admin@yourcompany.com"],
                "username": "your-email@gmail.com",
                "password": "your-app-password"
            },
            enabled=False,  # Disabled for demo
            severity_filter=[AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]
        )
        monitoring.add_notification_channel(email_channel)
        
        # Add webhook notification channel (example)
        webhook_channel = NotificationChannel(
            name="slack_webhook",
            type="webhook",
            config={
                "url": "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
                "timeout": 30,
                "headers": {
                    "Content-Type": "application/json"
                }
            },
            enabled=False,  # Disabled for demo
            severity_filter=[AlertSeverity.WARNING, AlertSeverity.CRITICAL]
        )
        monitoring.add_notification_channel(webhook_channel)
        
        logger.info("Monitoring system started successfully")
        logger.info("Prometheus metrics available at: http://localhost:8000/metrics")
        
        # Simulate application activity
        await simulate_application_activity(monitoring)
        
    except Exception as e:
        logger.error(f"Error in monitoring demo: {e}")
    finally:
        # Stop monitoring
        await monitoring.stop()
        logger.info("Monitoring system stopped")


async def simulate_application_activity(monitoring: MonitoringService):
    """Simulate application activity to generate metrics."""
    logger.info("Simulating application activity...")
    
    users = ["user1", "user2", "user3", "user4", "user5"]
    endpoints = ["/api/actions", "/api/status", "/api/health", "/api/metrics"]
    
    for i in range(60):  # Run for 60 iterations (10 minutes with 10s intervals)
        # Simulate HTTP requests
        for _ in range(random.randint(5, 20)):
            method = random.choice(["GET", "POST", "PUT", "DELETE"])
            endpoint = random.choice(endpoints)
            status_code = random.choices([200, 201, 400, 404, 500], weights=[70, 10, 10, 5, 5])[0]
            duration_ms = random.uniform(10, 500)
            
            monitoring.record_http_request(method, endpoint, status_code, duration_ms)
        
        # Simulate network actions
        for _ in range(random.randint(0, 15)):
            success = random.random() > 0.1  # 90% success rate
            response_time = random.uniform(50, 300)
            
            if success:
                monitoring.record_action_success(response_time)
            else:
                monitoring.record_action_error(response_time)
        
        # Simulate user activity
        active_user = random.choice(users)
        monitoring.record_user_activity(active_user)
        
        # Update queue sizes
        monitoring.update_queue_size("action_queue", random.randint(0, 50))
        monitoring.update_queue_size("retry_queue", random.randint(0, 10))
        
        # Display current metrics every 30 seconds
        if i % 3 == 0:
            await display_current_metrics(monitoring)
        
        # Check for alerts
        active_alerts = monitoring.get_active_alerts()
        if active_alerts:
            logger.warning(f"Active alerts: {len(active_alerts)}")
            for alert in active_alerts[:3]:  # Show first 3 alerts
                logger.warning(f"  - {alert.message}")
        
        # Wait for next iteration
        await asyncio.sleep(10)


async def display_current_metrics(monitoring: MonitoringService):
    """Display current metrics."""
    try:
        metrics = monitoring.get_current_metrics()
        
        logger.info("=== Current Metrics ===")
        
        # System metrics
        if metrics.get('system'):
            sys_metrics = metrics['system']
            logger.info(f"CPU: {sys_metrics.cpu_usage_percent:.1f}%")
            logger.info(f"Memory: {sys_metrics.memory_usage_percent:.1f}%")
            logger.info(f"Connections: {sys_metrics.active_connections}")
        
        # Business metrics
        if metrics.get('business'):
            biz_metrics = metrics['business']
            logger.info(f"Actions/min: {biz_metrics.actions_per_minute}")
            logger.info(f"Success rate: {biz_metrics.success_rate_percent:.1f}%")
            logger.info(f"Avg response time: {biz_metrics.response_time_avg_ms:.1f}ms")
            logger.info(f"Active users: {biz_metrics.active_users}")
        
        # Application metrics
        if metrics.get('application'):
            app_metrics = metrics['application']
            logger.info(f"HTTP requests: {app_metrics.http_requests_total}")
            logger.info(f"Cache hit rate: {app_metrics.cache_hit_rate_percent:.1f}%")
        
        logger.info("=====================")
        
    except Exception as e:
        logger.error(f"Error displaying metrics: {e}")


async def demo_health_check(monitoring: MonitoringService):
    """Demonstrate health check functionality."""
    logger.info("Performing health check...")
    
    health = await monitoring.health_check()
    
    logger.info(f"Overall status: {health['status']}")
    logger.info("Component status:")
    
    for component, status in health['components'].items():
        logger.info(f"  {component}: {status.get('status', 'unknown')}")


if __name__ == "__main__":
    try:
        asyncio.run(demo_monitoring_system())
    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise