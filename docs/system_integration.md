# System Integration Documentation

## Overview

The Northbound Script Generator system is a fully integrated microservices architecture that manages network operations through LLM-driven commands. This document describes the complete system integration, component wiring, and operational procedures.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     System Orchestrator                          │
│  - Lifecycle Management                                          │
│  - Dependency Resolution                                         │
│  - Health Monitoring                                             │
│  - Graceful Shutdown                                             │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐      ┌──────────────┐     ┌──────────────┐
│ Config       │      │ Monitoring   │     │ Backup       │
│ Manager      │      │ Service      │     │ Service      │
└──────────────┘      └──────────────┘     └──────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ Northbound       │
                    │ Module           │
                    │ - RYU Connector  │
                    │ - ComnetsEMU     │
                    └──────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ API Gateway      │
                    │ - REST API       │
                    │ - WebSocket      │
                    │ - Authentication │
                    └──────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ Web Interface    │
                    │ - Dashboard      │
                    │ - Controls       │
                    └──────────────────┘
```

## Component Integration

### 1. System Orchestrator

The System Orchestrator is the central component that manages the lifecycle of all services.

**Responsibilities:**
- Service registration and dependency management
- Startup sequencing based on dependencies
- Health monitoring of all services
- Graceful shutdown in reverse dependency order
- Automated service recovery

**Key Features:**
- Topological sort for dependency resolution
- Configurable health check intervals
- Automatic restart of failed critical services
- Signal handling for graceful shutdown

### 2. Service Dependencies

Services are started in the following order based on dependencies:

1. **Configuration Manager** (no dependencies)
   - Loads system configuration
   - Provides configuration to all services

2. **Logging System** (depends on: config_manager)
   - Initializes structured logging
   - Configures log levels and outputs

3. **Database** (depends on: config_manager)
   - Initializes database connections
   - Sets up connection pools

4. **RYU Connector** (depends on: config_manager, logging)
   - Connects to RYU Controller
   - Initializes connection pool

5. **ComnetsEMU Connector** (depends on: config_manager, logging)
   - Connects to ComnetsEMU
   - Initializes network interface

6. **Northbound Module** (depends on: ryu_connector, comnetsemu_connector, database)
   - Orchestrates network operations
   - Manages action queue and retry system

7. **Monitoring Service** (depends on: config_manager, database)
   - Starts metrics collection
   - Initializes Prometheus exporter
   - Configures alert thresholds

8. **Authentication Service** (depends on: database, config_manager)
   - Initializes JWT authentication
   - Loads user database

9. **Backup Service** (depends on: database, config_manager)
   - Starts backup scheduler
   - Initializes retention manager

10. **API Gateway** (depends on: northbound_module, auth_service, monitoring_service)
    - Starts FastAPI application
    - Registers all routes
    - Configures middleware

11. **Web Interface** (depends on: api_gateway)
    - Serves React frontend
    - Establishes WebSocket connections

## Health Monitoring

### Inter-Service Health Checks

The system performs continuous health monitoring with the following checks:

1. **Northbound Module Health**
   - RYU Controller connectivity
   - ComnetsEMU connectivity
   - Queue processing status
   - Retry system statistics

2. **Monitoring Service Health**
   - Metrics collection status
   - InfluxDB connectivity (if enabled)
   - Alert manager status
   - Prometheus exporter status

3. **Backup Service Health**
   - Backup scheduler status
   - Disk space availability
   - Last backup timestamp

4. **API Gateway Health**
   - Request processing status
   - Active connections count
   - Response time metrics

### Health Check Configuration

```python
# Default health check intervals
config = {
    "health_check_interval": 30,  # seconds
    "failure_threshold": 3,        # consecutive failures
    "recovery_threshold": 2,       # consecutive successes
    "timeout_seconds": 5           # health check timeout
}
```

### Automated Recovery

When a service fails health checks:

1. **Warning Phase** (1-2 failures)
   - Log warning message
   - Continue monitoring

2. **Critical Phase** (3+ failures)
   - Log critical alert
   - Attempt service restart
   - Notify administrators

3. **Recovery Phase**
   - Monitor for successful health checks
   - Log recovery message
   - Reset failure counters

## Graceful Shutdown

The system implements a multi-phase graceful shutdown:

### Phase 1: Stop Accepting Requests
- API Gateway stops accepting new requests
- Existing connections remain open

### Phase 2: Wait for In-Flight Requests
- Configurable timeout (default: 30 seconds)
- Allow current requests to complete

### Phase 3: Stop Background Workers
- Stop queue processing
- Stop scheduled tasks
- Stop health monitoring

### Phase 4: Flush Data
- Flush metrics to storage
- Flush logs to disk
- Complete pending backups

### Phase 5: Stop Services
- Stop services in reverse dependency order
- Close database connections
- Close network connections

### Phase 6: Cleanup
- Remove temporary files
- Release system resources

## Communication Channels

### HTTP/REST
- API Gateway ↔ Clients
- Northbound Module ↔ RYU Controller
- Monitoring Service ↔ Prometheus

### WebSocket
- API Gateway ↔ Web Interface (real-time updates)
- Dashboard ↔ Monitoring Service (live metrics)

### Redis Pub/Sub (if enabled)
- Inter-service event notifications
- Distributed session management
- Cache invalidation

### Database
- PostgreSQL for persistent data
- Connection pooling for performance
- Transaction management for consistency

## Configuration

### System Configuration File

```yaml
# config/system_config.yaml

system:
  shutdown_timeout_seconds: 30
  health_check_interval: 30

northbound:
  ryu_host: localhost
  ryu_port: 8080
  comnetsemu_host: localhost
  comnetsemu_port: 6653
  max_retries: 3
  retry_delay: 2
  queue_processing_enabled: true
  queue_processing_interval: 30

monitoring:
  collection_interval: 60
  enable_prometheus: true
  enable_influxdb: false
  enable_alerting: true
  influxdb_url: http://localhost:8086
  influxdb_token: ""
  influxdb_org: northbound
  influxdb_bucket: metrics

authentication:
  secret_key: your-secret-key-change-in-production
  algorithm: HS256
  access_token_expire_minutes: 30
  enable_mfa: true

backup:
  backup_dir: ./backups
  retention_days: 7
  schedule_enabled: true
  schedule_interval_hours: 1
  compression_enabled: true
  encryption_enabled: false

logging:
  level: INFO
  format: json
  output: both  # console, file, or both
  rotation: daily
  retention_days: 30
```

## Starting the System

### Method 1: Integrated Startup Script

```bash
python start_system.py
```

This starts all components with the orchestrator managing the lifecycle.

### Method 2: Manual Startup

```bash
# Start individual components (not recommended for production)
python main.py
```

### Method 3: Docker Compose

```bash
docker-compose up -d
```

## Monitoring the System

### Health Check Endpoint

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0",
  "services": {
    "northbound": "healthy",
    "api_gateway": "healthy",
    "monitoring": "healthy",
    "database": "healthy"
  }
}
```

### System Status

```bash
curl http://localhost:8000/api/v1/system/status
```

### Prometheus Metrics

```bash
curl http://localhost:8000/metrics
```

## Troubleshooting

### Service Won't Start

1. Check dependencies are running:
   ```bash
   curl http://localhost:8000/api/v1/system/status
   ```

2. Check logs:
   ```bash
   tail -f logs/system.log
   ```

3. Verify configuration:
   ```bash
   python scripts/validate_config.py
   ```

### Service Health Check Failing

1. Check service-specific logs
2. Verify network connectivity
3. Check resource availability (CPU, memory, disk)
4. Review recent configuration changes

### Graceful Shutdown Not Working

1. Check for stuck background tasks
2. Verify database connections are closing
3. Check for deadlocks in shutdown sequence
4. Review shutdown timeout configuration

## Best Practices

### Production Deployment

1. **Use Environment Variables** for sensitive configuration
2. **Enable All Monitoring** (Prometheus, InfluxDB, Alerting)
3. **Configure Backup Retention** appropriately
4. **Set Up Log Aggregation** for distributed deployments
5. **Use Load Balancer** for API Gateway
6. **Enable SSL/TLS** for all external connections
7. **Configure Firewall Rules** appropriately

### Development

1. **Disable InfluxDB** if not needed
2. **Reduce Health Check Intervals** for faster feedback
3. **Enable Debug Logging** for troubleshooting
4. **Use Mock Services** for testing

### Testing

1. **Run Integration Tests** before deployment
2. **Test Graceful Shutdown** scenarios
3. **Verify Health Monitoring** works correctly
4. **Test Service Recovery** mechanisms

## Performance Tuning

### Connection Pooling

```python
# Adjust pool sizes based on load
database_pool_size = 20
ryu_connection_pool_size = 10
```

### Health Check Intervals

```python
# Balance between responsiveness and overhead
health_check_interval = 30  # seconds
```

### Shutdown Timeout

```python
# Allow enough time for graceful shutdown
shutdown_timeout_seconds = 60  # seconds
```

## Security Considerations

1. **Change Default Secret Keys** in production
2. **Enable MFA** for administrative users
3. **Use Strong Passwords** for database
4. **Restrict Network Access** to internal services
5. **Enable Audit Logging** for all privileged operations
6. **Regular Security Updates** for dependencies
7. **Encrypt Sensitive Data** at rest and in transit

## Maintenance

### Regular Tasks

- **Daily**: Review logs for errors
- **Weekly**: Check disk space and backup status
- **Monthly**: Review and update dependencies
- **Quarterly**: Performance tuning and optimization

### Backup and Recovery

- Automated backups run hourly
- Retention: 7 days by default
- Test recovery procedures regularly
- Document recovery procedures

## Support

For issues or questions:
- Check logs: `logs/system.log`
- Review documentation: `docs/`
- Run diagnostics: `python scripts/diagnose.py`
- Contact: netops@example.com
