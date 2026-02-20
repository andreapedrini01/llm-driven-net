# Operator Quick Start Guide

## Starting the System

### Prerequisites
- Python 3.8+
- RYU Controller running on localhost:8080
- ComnetsEMU running on localhost:6653
- PostgreSQL database (optional, for backup service)

### Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the system
python start_system.py
```

The system will start all components automatically and display:
```
================================================================================
System started successfully!
API Gateway: http://localhost:8000
API Documentation: http://localhost:8000/docs
Prometheus Metrics: http://localhost:8000/metrics
================================================================================
```

## Checking System Health

### Quick Health Check
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0",
  "services": {
    "northbound": "healthy",
    "api_gateway": "healthy",
    "monitoring": "healthy"
  }
}
```

### Detailed System Status
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/system/status
```

## Common Operations

### Submit a Network Action

```bash
# Login first
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'

# Submit action
curl -X POST http://localhost:8000/api/v1/actions \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "flow_rule",
    "target": "switch-1",
    "parameters": {
      "operation": "add",
      "match": {"in_port": 1},
      "actions": ["output:2"]
    }
  }'
```

### Check Action Status

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/actions/ACTION_ID
```

### View Metrics

```bash
# Prometheus format
curl http://localhost:8000/metrics

# JSON format (requires authentication)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/monitoring/metrics
```

## Stopping the System

### Graceful Shutdown
Press `Ctrl+C` or send SIGTERM:
```bash
kill -TERM $(pgrep -f start_system.py)
```

The system will:
1. Stop accepting new requests
2. Wait for in-flight requests (30s)
3. Stop background workers
4. Flush metrics and logs
5. Stop all services
6. Clean up resources

### Force Shutdown (Not Recommended)
```bash
kill -9 $(pgrep -f start_system.py)
```

## Troubleshooting

### System Won't Start

**Check logs:**
```bash
tail -f logs/system.log
```

**Common issues:**
- RYU Controller not running → Start RYU first
- ComnetsEMU not running → Start ComnetsEMU first
- Port 8000 already in use → Change port in config
- Missing dependencies → Run `pip install -r requirements.txt`

### Service Health Check Failing

**Check specific service:**
```bash
# View system status
curl http://localhost:8000/health

# Check logs for the failing service
grep "service_name" logs/system.log
```

**Common fixes:**
- Restart the system: `Ctrl+C` then `python start_system.py`
- Check network connectivity to RYU/ComnetsEMU
- Verify database is accessible (if using backup service)

### High Memory/CPU Usage

**Check metrics:**
```bash
curl http://localhost:8000/metrics | grep -E "(cpu|memory)"
```

**Actions:**
- Reduce health check frequency in config
- Disable InfluxDB if not needed
- Increase system resources

## Configuration

### Quick Configuration Changes

Edit `config/system_config.yaml`:

```yaml
# Reduce health check frequency
system:
  health_check_interval: 60  # seconds

# Disable optional services
monitoring:
  enable_influxdb: false
  enable_alerting: false

backup:
  schedule_enabled: false
```

### Environment Variables

Override configuration with environment variables:
```bash
export NORTHBOUND_RYU_HOST=192.168.1.100
export NORTHBOUND_RYU_PORT=8080
export MONITORING_ENABLE_PROMETHEUS=true
python start_system.py
```

## Monitoring

### View Logs

```bash
# System logs
tail -f logs/system.log

# Northbound logs
tail -f logs/northbound_*.log

# Filter by level
grep ERROR logs/system.log
grep WARNING logs/system.log
```

### Prometheus Integration

Add to `prometheus.yml`:
```yaml
scrape_configs:
  - job_name: 'northbound'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

### Grafana Dashboard

Import the provided dashboard:
```bash
# Dashboard JSON available at:
# docs/grafana_dashboard.json
```

## Backup and Recovery

### Manual Backup

```bash
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/backup/create
```

### List Backups

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/backup/list
```

### Restore from Backup

```bash
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/backup/restore/BACKUP_ID
```

## Security

### Change Default Credentials

1. Edit `config/system_config.yaml`:
```yaml
authentication:
  secret_key: "your-new-secret-key-here"
```

2. Restart the system

### Enable MFA

```bash
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/auth/mfa/enable
```

### View Audit Logs

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/auth/audit
```

## Performance Tuning

### For High Load

```yaml
# config/system_config.yaml
northbound:
  queue_processing_interval: 10  # Process queue more frequently
  max_retries: 5  # More retry attempts

monitoring:
  collection_interval: 30  # Collect metrics more frequently
```

### For Low Resources

```yaml
# config/system_config.yaml
system:
  health_check_interval: 60  # Check less frequently

monitoring:
  enable_influxdb: false  # Disable if not needed
  collection_interval: 120  # Collect less frequently

backup:
  schedule_enabled: false  # Disable automatic backups
```

## Getting Help

### Check Documentation
- System Integration: `docs/system_integration.md`
- API Documentation: http://localhost:8000/docs
- Troubleshooting: `docs/troubleshooting_guide.md`

### Run Diagnostics
```bash
python scripts/diagnose.py
```

### Contact Support
- Email: netops@example.com
- Logs: Attach `logs/system.log`
- Config: Attach `config/system_config.yaml` (remove secrets!)

## Quick Reference

### Important URLs
- API Gateway: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- Metrics: http://localhost:8000/metrics

### Important Files
- Main script: `start_system.py`
- Configuration: `config/system_config.yaml`
- System logs: `logs/system.log`
- Northbound logs: `logs/northbound_*.log`

### Important Commands
```bash
# Start system
python start_system.py

# Stop system
Ctrl+C

# Check health
curl http://localhost:8000/health

# View logs
tail -f logs/system.log

# Run tests
python -m pytest tests/ -v
```

## Status Indicators

### Service Status
- `running`: Service is operational
- `starting`: Service is initializing
- `stopping`: Service is shutting down
- `stopped`: Service is not running
- `error`: Service has failed

### Health Status
- `healthy`: All systems operational
- `degraded`: Some issues but functional
- `unhealthy`: Service not functioning
- `unknown`: Unable to determine status

## Emergency Procedures

### System Unresponsive

1. Check if process is running:
```bash
ps aux | grep start_system
```

2. Check system resources:
```bash
top
df -h
```

3. Force restart:
```bash
kill -9 $(pgrep -f start_system.py)
python start_system.py
```

### Data Corruption

1. Stop the system
2. Restore from latest backup
3. Verify data integrity
4. Restart the system

### Network Issues

1. Check RYU Controller:
```bash
curl http://localhost:8080/stats/switches
```

2. Check ComnetsEMU:
```bash
# Verify ComnetsEMU is running
ps aux | grep comnetsemu
```

3. Restart network services if needed

## Best Practices

1. **Always use graceful shutdown** (Ctrl+C, not kill -9)
2. **Monitor logs regularly** for warnings and errors
3. **Test backups periodically** to ensure they work
4. **Keep configuration in version control** (without secrets)
5. **Use environment variables** for sensitive data
6. **Monitor system resources** (CPU, memory, disk)
7. **Review security logs** for suspicious activity
8. **Update dependencies** regularly for security patches
