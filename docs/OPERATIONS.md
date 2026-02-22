# Operations Guide

## Overview

Complete operational guide for the Northbound Script Generator system, including daily operations, troubleshooting, and incident response.

## Quick Commands

```bash
# Start system
python start_system.py

# Check health
curl http://localhost:8000/health

# View logs
tail -f logs/system.log

# Run tests
python scripts/run_tests.py

# Stop system
Ctrl+C  # Graceful shutdown
```

## Daily Operations

### Morning Health Check

**Run daily at start of business:**

```bash
# 1. Check system health
curl http://localhost:8000/health

# 2. Check disk space
df -h  # Ensure >20% free

# 3. Review logs
tail -100 logs/system.log | grep ERROR

# 4. Verify backups
ls -lt backups/ | head -5

# 5. Check metrics
curl http://localhost:8000/metrics | grep northbound_actions_total
```

**Alert if:**
- Health status != "healthy"
- Disk space < 20%
- Error count > 100/day
- No backup in last 2 hours
- Action success rate < 95%

### Performance Monitoring

```bash
# Response times
curl http://localhost:8000/metrics | grep http_request_duration

# Resource usage
top  # Check CPU/Memory

# Active connections
netstat -an | grep :8000 | wc -l
```

**Alert if:**
- P95 response time > 2 seconds
- CPU > 80%
- Memory > 90%
- Active connections > 1000

## Common Issues

### Service Won't Start

**Symptoms:** System fails to start, connection errors

**Solutions:**

1. Check logs:
```bash
tail -f logs/system.log
```

2. Verify dependencies:
```bash
# RYU Controller
curl http://localhost:8080/stats/switches

# ComnetsEMU
ps aux | grep comnetsemu
```

3. Check port availability:
```bash
# Linux/Mac
netstat -tuln | grep 8000

# Windows
netstat -ano | findstr :8000
```

4. Restart system:
```bash
# Stop
Ctrl+C

# Start
python start_system.py
```

### Authentication Fails

**Symptoms:** Login fails, 401 errors

**Solutions:**

1. Verify credentials:
```bash
# Default: admin/admin
```

2. Check JWT secret:
```bash
grep JWT_SECRET config/system_config.yaml
```

3. Reset user password:
```python
from src.api.auth import AuthService
auth = AuthService()
auth.reset_password("admin", "new_password")
```

4. Clear sessions:
```bash
# If using Redis
redis-cli FLUSHDB
```

### Performance Issues

**Symptoms:** Slow response times, timeouts

**Solutions:**

1. Check metrics:
```bash
curl http://localhost:8000/metrics
```

2. Review resource usage:
```bash
top
df -h
```

3. Check for bottlenecks:
```bash
# Database connections
grep "database" logs/system.log

# Network latency
ping localhost
```

4. Restart services:
```bash
python start_system.py
```

### High Memory Usage

**Symptoms:** Memory > 90%, OOM errors

**Solutions:**

1. Check memory usage:
```bash
free -h  # Linux
# or
Get-Process python | Select-Object WS  # Windows
```

2. Review logs for leaks:
```bash
grep "memory" logs/system.log
```

3. Restart system:
```bash
Ctrl+C
python start_system.py
```

4. Adjust configuration:
```yaml
# config/system_config.yaml
scalability:
  gc_mode: adaptive
  max_workers: 5  # Reduce if needed
```

### RYU Controller Connectivity

**Symptoms:** Actions fail, "RYU not available" errors

**Solutions:**

1. Check RYU status:
```bash
curl http://localhost:8080/stats/switches
```

2. Verify configuration:
```yaml
# config/system_config.yaml
northbound:
  ryu_host: localhost
  ryu_port: 8080
```

3. Test connectivity:
```bash
telnet localhost 8080
```

4. Restart RYU:
```bash
# Follow RYU documentation
ryu-manager --verbose
```

### ComnetsEMU Integration

**Symptoms:** Topology operations fail

**Solutions:**

1. Check ComnetsEMU:
```bash
ps aux | grep comnetsemu
```

2. Verify configuration:
```yaml
# config/system_config.yaml
northbound:
  comnetsemu_host: localhost
  comnetsemu_port: 6653
```

3. Test connectivity:
```bash
telnet localhost 6653
```

## Incident Response

### Severity Levels

**P0 - Critical (Immediate Response)**
- System completely down
- Data loss occurring
- Security breach

**P1 - High (15-minute Response)**
- Major functionality impaired
- Significant performance degradation
- Authentication system down

**P2 - Medium (1-hour Response)**
- Minor functionality issues
- Isolated component failures
- Non-critical errors

**P3 - Low (Next Business Day)**
- Cosmetic issues
- Documentation errors
- Enhancement requests

### P0: System Down

**Procedure:**

1. **Verify outage:**
```bash
curl http://localhost:8000/health
```

2. **Check logs:**
```bash
tail -100 logs/system.log
```

3. **Quick recovery:**
```bash
# Stop system
Ctrl+C

# Start system
python start_system.py
```

4. **If recovery fails:**
```bash
# Restore from backup
python scripts/restore_backup.py --latest
```

5. **Notify stakeholders:**
- Email: netops@example.com
- Status: "System down, recovery in progress"

6. **Post-incident:**
- Document root cause
- Update runbook
- Schedule post-mortem

### P1: Performance Degradation

**Procedure:**

1. **Identify bottleneck:**
```bash
curl http://localhost:8000/metrics
top
```

2. **Quick fixes:**
```bash
# Restart system
Ctrl+C
python start_system.py

# Or scale up
# Increase workers in config
```

3. **Monitor recovery:**
```bash
watch -n 5 'curl -s http://localhost:8000/metrics | grep response_time'
```

4. **Document issue:**
- Capture metrics
- Save logs
- Note resolution

## Maintenance

### Weekly Tasks

**Every Monday:**

1. Review backup status:
```bash
ls -lh backups/
python scripts/verify_backups.py
```

2. Check security logs:
```bash
grep "authentication failed" logs/system.log | wc -l
```

3. Database maintenance:
```bash
# If using PostgreSQL
psql -U northbound -d northbound -c "VACUUM ANALYZE;"
```

4. Log rotation:
```bash
# Logs rotate automatically
# Verify rotation working
ls -lh logs/
```

### Monthly Tasks

**First of each month:**

1. System updates:
```bash
pip install --upgrade -r requirements.txt
```

2. Performance review:
```bash
python scripts/benchmark.py
# Compare with baseline
```

3. Capacity planning:
```bash
# Review metrics
curl http://localhost:8000/api/v1/monitoring/capacity
```

4. Security audit:
```bash
# Check for vulnerabilities
pip-audit
bandit -r src/
```

### Backup Procedures

**Automated (Hourly):**
- Backups run automatically
- Retention: 7 days
- Location: `backups/`

**Manual Backup:**
```bash
python scripts/create_backup.py --description "Pre-upgrade backup"
```

**Restore from Backup:**
```bash
# List backups
python scripts/list_backups.py

# Restore specific backup
python scripts/restore_backup.py --backup-id <id>

# Restore latest
python scripts/restore_backup.py --latest
```

**Verify Backup:**
```bash
python scripts/verify_backup.py --backup-id <id>
```

## Configuration

### Hot-Reload Configuration

```bash
# Edit configuration
nano config/system_config.yaml

# Configuration reloads automatically
# No restart needed for most changes
```

### Environment Variables

```bash
# Edit .env file
nano .env

# Restart required for .env changes
Ctrl+C
python start_system.py
```

### Common Configuration Changes

**Adjust timeouts:**
```yaml
# config/system_config.yaml
northbound:
  max_retries: 5  # Increase retries
  retry_delay: 5  # Increase delay
```

**Enable/disable features:**
```yaml
monitoring:
  enable_prometheus: true
  enable_influxdb: false  # Disable if not needed
  enable_alerting: true

backup:
  schedule_enabled: true
  schedule_interval_hours: 1
```

**Adjust resources:**
```yaml
scalability:
  max_workers: 10  # Parallel processing
  connection_pool_size: 20  # Database connections
```

## Monitoring

### Key Metrics

**System Health:**
- `northbound_health_status` - Overall health (0=unhealthy, 1=healthy)
- `northbound_uptime_seconds` - System uptime

**Actions:**
- `northbound_actions_total` - Total actions processed
- `northbound_actions_success_rate` - Success rate (0-1)
- `northbound_actions_duration_seconds` - Action execution time

**Resources:**
- `process_cpu_percent` - CPU usage
- `process_memory_bytes` - Memory usage
- `process_open_fds` - Open file descriptors

### Prometheus Queries

```promql
# Error rate
rate(northbound_actions_failed_total[5m])

# P95 response time
histogram_quantile(0.95, northbound_actions_duration_seconds_bucket)

# Success rate
northbound_actions_success_total / northbound_actions_total
```

### Grafana Dashboards

Import dashboard from:
```
deployment/grafana/dashboards/dashboard.yml
```

## Security

### Access Control

**User Management:**
```bash
# Create user
curl -X POST http://localhost:8000/api/v1/auth/users \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"username": "newuser", "password": "password", "roles": ["operator"]}'

# List users
curl http://localhost:8000/api/v1/auth/users \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Disable user
curl -X DELETE http://localhost:8000/api/v1/auth/users/username \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**API Keys:**
```bash
# Create API key
curl -X POST http://localhost:8000/api/v1/auth/api-keys \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"name": "LLM Integration", "permissions": ["actions:write"]}'

# Revoke API key
curl -X DELETE http://localhost:8000/api/v1/auth/api-keys/key-id \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Audit Logs

```bash
# View audit logs
tail -f logs/audit.log

# Search for specific user
grep "user:admin" logs/audit.log

# Search for failed auth
grep "authentication failed" logs/audit.log
```

## Support

### Log Collection

```bash
# Collect all logs
tar -czf logs-$(date +%Y%m%d).tar.gz logs/

# Collect system info
python scripts/diagnose.py > system-info.txt
```

### Diagnostic Commands

```bash
# System diagnostics
python scripts/diagnose.py

# Validate configuration
python scripts/validate_config.py

# Test connectivity
python scripts/test_connectivity.py

# Benchmark performance
python scripts/benchmark.py
```

### Contact Information

- **Email:** netops@example.com
- **Documentation:** docs/
- **API Docs:** http://localhost:8000/docs
- **GitHub Issues:** [repository]/issues

---

**Version:** 1.0 | **Last Updated:** January 2025 | **Status:** Production Ready ✅
