# Troubleshooting Guide - Northbound Script Generator

## Common Issues and Solutions

### Service Startup Issues

#### API Gateway Won't Start

**Symptoms:**
- Container exits immediately
- Health check fails
- Connection refused errors

**Solutions:**

1. Check logs:
```bash
docker-compose logs api-gateway
```

2. Verify database connection:
```bash
# Test PostgreSQL connection
docker-compose exec postgres pg_isready -U northbound

# Check DATABASE_URL in .env
cat .env | grep DATABASE_URL
```

3. Verify dependencies are healthy:
```bash
docker-compose ps
# All services should show "healthy" status
```

4. Check port conflicts:
```bash
# On Linux/Mac
netstat -tuln | grep 8000

# On Windows
netstat -ano | findstr :8000
```

#### Database Connection Errors

**Error:** `could not connect to server: Connection refused`

**Solutions:**

1. Ensure PostgreSQL is running:
```bash
docker-compose ps postgres
docker-compose logs postgres
```

2. Check network connectivity:
```bash
docker-compose exec api-gateway ping postgres
```

3. Verify credentials:
```bash
# Check .env file
cat .env | grep POSTGRES

# Test connection manually
docker-compose exec postgres psql -U northbound -d northbound
```

4. Reset database:
```bash
docker-compose down -v
docker-compose up -d postgres
# Wait for postgres to be healthy
docker-compose up -d
```

#### Redis Connection Issues

**Error:** `Error connecting to Redis`

**Solutions:**

1. Check Redis status:
```bash
docker-compose ps redis
docker-compose logs redis
```

2. Test Redis connection:
```bash
docker-compose exec redis redis-cli ping
# Should return: PONG
```

3. Verify password:
```bash
# With password
docker-compose exec redis redis-cli -a <password> ping
```

### Network Action Failures

#### RYU Controller Unreachable

**Symptoms:**
- Actions fail with connection timeout
- "Controller not available" errors

**Solutions:**

1. Verify RYU Controller is running:
```bash
# Check if RYU is accessible
curl http://<RYU_HOST>:<RYU_PORT>/stats/switches
```

2. Check network connectivity:
```bash
docker-compose exec api-gateway ping <RYU_HOST>
```

3. Verify configuration:
```bash
cat .env | grep RYU_CONTROLLER
```

4. Check retry queue:
```bash
# View queued actions
sqlite3 logs/ryu_retry_queue.db "SELECT * FROM retry_queue;"
```

5. Restart connector:
```bash
docker-compose restart api-gateway
```

#### ComnetsEMU Integration Issues

**Symptoms:**
- Topology operations fail
- Network state verification errors

**Solutions:**

1. Verify ComnetsEMU is accessible:
```bash
# Check connectivity
docker-compose exec api-gateway telnet <COMNETSEMU_HOST> <COMNETSEMU_PORT>
```

2. Check logs for specific errors:
```bash
docker-compose logs api-gateway | grep -i comnetsemu
```

3. Verify network configuration:
```bash
cat network_configs/simple_topology.py
```

4. Test with demo script:
```bash
python demos/demo_comnetsemu_integration.py
```

### Authentication Issues

#### JWT Token Errors

**Error:** `Invalid token` or `Token expired`

**Solutions:**

1. Check token expiration:
```bash
# Tokens expire after JWT_ACCESS_TOKEN_EXPIRE_MINUTES
cat .env | grep JWT_ACCESS_TOKEN_EXPIRE_MINUTES
```

2. Verify JWT secret:
```bash
cat .env | grep JWT_SECRET_KEY
# Ensure it's set and not the default
```

3. Clear session and re-authenticate:
```bash
# Clear Redis sessions
docker-compose exec redis redis-cli FLUSHDB
```

4. Generate new token:
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password"}'
```

#### MFA Issues

**Error:** `Invalid TOTP code`

**Solutions:**

1. Check time synchronization:
```bash
# Ensure system time is correct
date
# TOTP requires accurate time (±30 seconds)
```

2. Regenerate MFA secret:
```bash
# Use admin panel to reset MFA
curl -X POST http://localhost:8000/api/auth/reset-mfa \
  -H "Authorization: Bearer <admin-token>"
```

3. Verify TOTP app configuration:
- Ensure time-based (not counter-based)
- Check for correct secret key

### Performance Issues

#### Slow API Response Times

**Symptoms:**
- Requests take >5 seconds
- Timeout errors
- High CPU/memory usage

**Solutions:**

1. Check system resources:
```bash
# Docker stats
docker stats

# System resources
top
htop
```

2. Analyze slow queries:
```bash
# PostgreSQL slow queries
docker-compose exec postgres psql -U northbound -d northbound -c \
  "SELECT query, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"
```

3. Check Redis performance:
```bash
docker-compose exec redis redis-cli INFO stats
docker-compose exec redis redis-cli SLOWLOG GET 10
```

4. Review application logs:
```bash
docker-compose logs api-gateway | grep -i "slow\|timeout"
```

5. Scale services:
```bash
# Increase workers
# Edit .env: WORKERS=8
docker-compose up -d

# Or scale containers
docker-compose up -d --scale api-gateway=3
```

#### High Memory Usage

**Solutions:**

1. Check memory usage:
```bash
docker stats --no-stream
```

2. Optimize garbage collection:
```python
# Already implemented in src/scalability/gc_optimizer.py
# Verify it's enabled in config
```

3. Adjust connection pools:
```bash
# Edit config/system_config.yaml
# Reduce pool sizes if memory constrained
```

4. Clear caches:
```bash
# Clear Redis cache
docker-compose exec redis redis-cli FLUSHDB

# Restart services
docker-compose restart
```

### Monitoring Issues

#### Metrics Not Appearing

**Symptoms:**
- Prometheus shows no data
- Grafana dashboards empty

**Solutions:**

1. Verify Prometheus is scraping:
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets
```

2. Check metrics endpoint:
```bash
curl http://localhost:8000/metrics
```

3. Verify InfluxDB connection:
```bash
docker-compose exec influxdb influx ping
```

4. Check datasource configuration:
```bash
# Grafana datasources
cat deployment/grafana/datasources/datasources.yml
```

#### Alerts Not Firing

**Solutions:**

1. Check alert configuration:
```bash
# View alert rules
curl http://localhost:8000/api/monitoring/alerts
```

2. Verify notification channels:
```bash
# Check email/webhook configuration
cat config/system_config.yaml | grep -A 10 notifications
```

3. Test alert manually:
```bash
curl -X POST http://localhost:8000/api/monitoring/test-alert
```

4. Check alert manager logs:
```bash
docker-compose logs api-gateway | grep -i alert
```

### Backup and Recovery Issues

#### Backup Failures

**Error:** `Backup failed` or `Insufficient disk space`

**Solutions:**

1. Check disk space:
```bash
df -h
du -sh logs/backups/
```

2. Verify backup configuration:
```bash
cat config/backup_config.yaml
```

3. Check backup logs:
```bash
docker-compose logs api-gateway | grep -i backup
```

4. Manual backup:
```bash
docker-compose exec postgres pg_dump -U northbound northbound > manual_backup.sql
```

5. Clean old backups:
```bash
# Remove backups older than 7 days
find logs/backups/ -name "*.sql.gz" -mtime +7 -delete
```

#### Recovery Failures

**Error:** `Recovery failed` or `Corrupted backup`

**Solutions:**

1. Verify backup integrity:
```bash
# Test backup file
gunzip -t backup.sql.gz
```

2. Check backup size:
```bash
ls -lh logs/backups/
# Ensure backup is not 0 bytes
```

3. Try older backup:
```bash
# List available backups
ls -lt logs/backups/

# Restore from specific backup
./scripts/restore_backup.sh logs/backups/backup_20260220.sql.gz
```

4. Manual recovery:
```bash
# Stop services
docker-compose down

# Start only database
docker-compose up -d postgres

# Restore manually
gunzip -c backup.sql.gz | docker-compose exec -T postgres psql -U northbound northbound

# Start all services
docker-compose up -d
```

### Frontend Issues

#### Dashboard Not Loading

**Symptoms:**
- Blank page
- 404 errors
- Connection refused

**Solutions:**

1. Check frontend service:
```bash
docker-compose ps frontend
docker-compose logs frontend
```

2. Verify API connection:
```bash
# Check REACT_APP_API_URL
docker-compose exec frontend env | grep REACT_APP
```

3. Check browser console:
- Open browser DevTools (F12)
- Look for errors in Console tab
- Check Network tab for failed requests

4. Rebuild frontend:
```bash
docker-compose build frontend
docker-compose up -d frontend
```

#### WebSocket Connection Failures

**Error:** `WebSocket connection failed`

**Solutions:**

1. Check WebSocket endpoint:
```bash
# Test WebSocket
wscat -c ws://localhost:8000/ws
```

2. Verify proxy configuration:
```bash
# If using nginx
cat deployment/nginx/nginx.conf | grep -A 10 "location /ws"
```

3. Check firewall rules:
```bash
# Ensure WebSocket port is open
# Default: 8000
```

### Deployment Issues

#### Docker Compose Fails

**Error:** `Service 'X' failed to build`

**Solutions:**

1. Check Docker version:
```bash
docker --version
docker-compose --version
```

2. Clean Docker cache:
```bash
docker system prune -a
docker volume prune
```

3. Rebuild from scratch:
```bash
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

4. Check for port conflicts:
```bash
# Stop conflicting services
docker ps -a
docker stop <conflicting-container>
```

#### Kubernetes Deployment Fails

**Error:** `Pod in CrashLoopBackOff`

**Solutions:**

1. Check pod logs:
```bash
kubectl logs -f <pod-name> -n northbound
kubectl describe pod <pod-name> -n northbound
```

2. Verify secrets and configmaps:
```bash
kubectl get secrets -n northbound
kubectl get configmaps -n northbound
```

3. Check resource limits:
```bash
kubectl describe node
# Ensure sufficient CPU/memory
```

4. Verify image pull:
```bash
kubectl get events -n northbound
# Look for ImagePullBackOff errors
```

## Getting Help

### Log Collection

Collect logs for support:

```bash
# All logs
docker-compose logs > all-logs.txt

# Specific service
docker-compose logs api-gateway > api-logs.txt

# With timestamps
docker-compose logs -t > logs-with-time.txt
```

### System Information

Collect system info:

```bash
# Docker info
docker info > docker-info.txt
docker-compose version >> docker-info.txt

# System resources
df -h > system-info.txt
free -h >> system-info.txt
top -bn1 >> system-info.txt
```

### Debug Mode

Enable debug logging:

```bash
# Edit .env
LOG_LEVEL=DEBUG

# Restart services
docker-compose restart api-gateway
```

### Contact Support

When reporting issues, include:
1. Error messages and logs
2. System information
3. Steps to reproduce
4. Configuration files (redact secrets)
5. Docker/Kubernetes version

## Preventive Maintenance

### Regular Checks

Daily:
- Monitor disk space
- Check service health
- Review error logs

Weekly:
- Verify backups
- Check performance metrics
- Update dependencies

Monthly:
- Security updates
- Database optimization
- Log cleanup

### Health Monitoring Script

```bash
#!/bin/bash
# health-check.sh

echo "=== Service Health ==="
docker-compose ps

echo -e "\n=== API Health ==="
curl -s http://localhost:8000/health | jq

echo -e "\n=== Disk Space ==="
df -h | grep -E "/$|/var"

echo -e "\n=== Recent Errors ==="
docker-compose logs --tail=50 api-gateway | grep -i error

echo -e "\n=== Database Size ==="
docker-compose exec postgres psql -U northbound -d northbound -c \
  "SELECT pg_size_pretty(pg_database_size('northbound'));"
```

Run regularly:
```bash
chmod +x health-check.sh
./health-check.sh
```
