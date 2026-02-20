# Operations Runbook - Northbound Script Generator

## Overview

This runbook provides step-by-step procedures for common operational tasks and incident response.

## Daily Operations

### Morning Health Check

**Frequency:** Daily at start of business

**Procedure:**

1. Check service status:
```bash
docker-compose ps
# All services should show "Up" and "healthy"
```

2. Verify API health:
```bash
curl http://localhost:8000/health
# Should return: {"status": "healthy"}
```

3. Check disk space:
```bash
df -h
# Ensure >20% free space on all volumes
```

4. Review overnight logs:
```bash
docker-compose logs --since 24h api-gateway | grep -i error
```

5. Verify backup completion:
```bash
ls -lt logs/backups/ | head -5
# Check latest backup timestamp
```

**Escalation:** If any check fails, follow incident response procedures.

### Log Review

**Frequency:** Daily

**Procedure:**

1. Check error rates:
```bash
docker-compose logs --since 24h api-gateway | grep -c ERROR
# Alert if >100 errors/day
```

2. Review critical errors:
```bash
docker-compose logs --since 24h api-gateway | grep CRITICAL
```

3. Check authentication failures:
```bash
docker-compose logs --since 24h api-gateway | grep "authentication failed"
# Alert if >10 failures/hour
```

4. Monitor action success rate:
```bash
curl http://localhost:8000/api/monitoring/metrics | jq '.action_success_rate'
# Alert if <95%
```

### Performance Monitoring

**Frequency:** Daily

**Procedure:**

1. Check response times:
```bash
curl http://localhost:8000/metrics | grep http_request_duration_seconds
# Alert if p95 >2s
```

2. Monitor resource usage:
```bash
docker stats --no-stream
# Alert if CPU >80% or Memory >90%
```

3. Check database performance:
```bash
docker-compose exec postgres psql -U northbound -d northbound -c \
  "SELECT * FROM pg_stat_activity WHERE state = 'active';"
# Alert if >50 active connections
```

4. Review Redis memory:
```bash
docker-compose exec redis redis-cli INFO memory | grep used_memory_human
# Alert if >80% of max memory
```

## Weekly Operations

### Backup Verification

**Frequency:** Weekly (Monday)

**Procedure:**

1. List recent backups:
```bash
ls -lh logs/backups/ | tail -10
```

2. Verify backup sizes:
```bash
# Backups should be >1MB and consistent in size
du -sh logs/backups/*.sql.gz
```

3. Test backup restoration (in test environment):
```bash
# Create test database
docker-compose exec postgres createdb -U northbound test_restore

# Restore latest backup
gunzip -c logs/backups/latest.sql.gz | \
  docker-compose exec -T postgres psql -U northbound test_restore

# Verify data
docker-compose exec postgres psql -U northbound test_restore -c \
  "SELECT COUNT(*) FROM network_actions;"

# Cleanup
docker-compose exec postgres dropdb -U northbound test_restore
```

4. Check backup retention:
```bash
# Verify old backups are cleaned up
find logs/backups/ -name "*.sql.gz" -mtime +7
# Should be empty (7-day retention)
```

### Security Audit

**Frequency:** Weekly (Tuesday)

**Procedure:**

1. Review authentication logs:
```bash
docker-compose logs --since 7d api-gateway | grep -i "auth\|login\|token"
```

2. Check for suspicious activity:
```bash
# Multiple failed login attempts
docker-compose logs --since 7d api-gateway | \
  grep "authentication failed" | \
  awk '{print $NF}' | sort | uniq -c | sort -rn
# Alert if >5 failures from same IP
```

3. Review user accounts:
```bash
curl -H "Authorization: Bearer <admin-token>" \
  http://localhost:8000/api/auth/users
# Verify all accounts are legitimate
```

4. Check for expired tokens:
```bash
docker-compose exec redis redis-cli KEYS "session:*" | wc -l
# Compare with active users
```

5. Verify SSL certificates (if applicable):
```bash
openssl x509 -in deployment/nginx/ssl/cert.pem -noout -dates
# Alert if expiring within 30 days
```

### Database Maintenance

**Frequency:** Weekly (Wednesday)

**Procedure:**

1. Analyze database:
```bash
docker-compose exec postgres psql -U northbound -d northbound -c "ANALYZE;"
```

2. Vacuum database:
```bash
docker-compose exec postgres psql -U northbound -d northbound -c "VACUUM ANALYZE;"
```

3. Check database size:
```bash
docker-compose exec postgres psql -U northbound -d northbound -c \
  "SELECT pg_size_pretty(pg_database_size('northbound'));"
```

4. Review slow queries:
```bash
docker-compose exec postgres psql -U northbound -d northbound -c \
  "SELECT query, mean_time, calls FROM pg_stat_statements \
   ORDER BY mean_time DESC LIMIT 10;"
```

5. Check for bloat:
```bash
docker-compose exec postgres psql -U northbound -d northbound -c \
  "SELECT schemaname, tablename, \
   pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size \
   FROM pg_tables ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC \
   LIMIT 10;"
```

### Log Rotation

**Frequency:** Weekly (Thursday)

**Procedure:**

1. Check log sizes:
```bash
du -sh logs/*.log
# Alert if any log >1GB
```

2. Rotate logs:
```bash
# Application logs are auto-rotated
# Verify rotation is working
ls -lh logs/northbound_*.log
```

3. Compress old logs:
```bash
find logs/ -name "*.log" -mtime +7 -exec gzip {} \;
```

4. Clean up old compressed logs:
```bash
find logs/ -name "*.log.gz" -mtime +30 -delete
```

## Monthly Operations

### System Updates

**Frequency:** Monthly (First Sunday)

**Procedure:**

1. Review available updates:
```bash
# Check Docker images
docker images | grep northbound

# Check for newer base images
docker pull python:3.11-slim
docker pull postgres:15-alpine
docker pull redis:7-alpine
```

2. Update dependencies:
```bash
# Backup current state
docker-compose exec postgres pg_dump -U northbound northbound > pre-update-backup.sql

# Pull latest code
git pull

# Update Python dependencies
pip install -r requirements.txt --upgrade

# Rebuild images
docker-compose build --no-cache
```

3. Test in staging:
```bash
# Deploy to staging environment
docker-compose -f docker-compose.staging.yml up -d

# Run tests
python scripts/run_tests.py

# Verify functionality
curl http://staging:8000/health
```

4. Deploy to production:
```bash
# Create backup
./scripts/backup.sh

# Deploy with zero downtime
docker-compose up -d --no-deps --build api-gateway

# Verify deployment
curl http://localhost:8000/health

# Monitor for issues
docker-compose logs -f api-gateway
```

5. Rollback if needed:
```bash
# Revert to previous version
docker-compose down
git checkout <previous-commit>
docker-compose up -d
```

### Performance Review

**Frequency:** Monthly (Second Monday)

**Procedure:**

1. Generate performance report:
```bash
# Export metrics from last 30 days
curl http://localhost:8000/api/monitoring/report?days=30 > performance-report.json
```

2. Analyze trends:
```bash
# Response time trends
# Action success rates
# Error rates
# Resource utilization
```

3. Identify bottlenecks:
```bash
# Slow endpoints
curl http://localhost:8000/metrics | grep http_request_duration_seconds | sort -k2 -rn

# Database slow queries
docker-compose exec postgres psql -U northbound -d northbound -c \
  "SELECT query, mean_time, calls FROM pg_stat_statements \
   WHERE mean_time > 1000 ORDER BY mean_time DESC;"
```

4. Optimize as needed:
- Add database indexes
- Adjust connection pools
- Scale services
- Optimize queries

### Capacity Planning

**Frequency:** Monthly (Third Monday)

**Procedure:**

1. Review resource trends:
```bash
# CPU usage over time
# Memory usage over time
# Disk usage growth rate
# Network bandwidth
```

2. Project future needs:
```bash
# Calculate growth rate
# Estimate capacity in 3/6/12 months
# Plan for scaling
```

3. Check current capacity:
```bash
# Current limits
docker-compose exec api-gateway cat /sys/fs/cgroup/memory/memory.limit_in_bytes

# Current usage
docker stats --no-stream
```

4. Plan scaling:
- Horizontal scaling (more instances)
- Vertical scaling (more resources)
- Database sharding
- Caching improvements

## Incident Response

### Severity Levels

**P0 - Critical:** System down, data loss, security breach
- Response time: Immediate
- Escalation: Immediate to on-call engineer

**P1 - High:** Major functionality impaired, performance degraded >50%
- Response time: 15 minutes
- Escalation: 30 minutes if not resolved

**P2 - Medium:** Minor functionality impaired, workaround available
- Response time: 1 hour
- Escalation: 4 hours if not resolved

**P3 - Low:** Cosmetic issues, feature requests
- Response time: Next business day
- Escalation: Not required

### P0 - System Down

**Symptoms:**
- API returns 500 errors
- Services not responding
- Database unavailable

**Immediate Actions:**

1. Verify incident:
```bash
curl http://localhost:8000/health
docker-compose ps
```

2. Check service status:
```bash
docker-compose logs --tail=100 api-gateway
docker-compose logs --tail=100 postgres
```

3. Attempt quick recovery:
```bash
# Restart services
docker-compose restart

# If that fails, full restart
docker-compose down
docker-compose up -d
```

4. If still down, restore from backup:
```bash
# Stop services
docker-compose down

# Restore database
gunzip -c logs/backups/latest.sql.gz | \
  docker-compose exec -T postgres psql -U northbound northbound

# Start services
docker-compose up -d
```

5. Notify stakeholders:
- Send incident notification
- Update status page
- Provide ETA for resolution

6. Document incident:
- Root cause
- Actions taken
- Resolution time
- Prevention measures

### P1 - Performance Degradation

**Symptoms:**
- Response times >5 seconds
- High error rates
- Resource exhaustion

**Actions:**

1. Identify bottleneck:
```bash
# Check resource usage
docker stats

# Check slow queries
docker-compose exec postgres psql -U northbound -d northbound -c \
  "SELECT * FROM pg_stat_activity WHERE state = 'active' AND \
   query_start < NOW() - INTERVAL '5 seconds';"
```

2. Quick mitigations:
```bash
# Scale up
docker-compose up -d --scale api-gateway=3

# Clear cache
docker-compose exec redis redis-cli FLUSHDB

# Kill slow queries
docker-compose exec postgres psql -U northbound -d northbound -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity \
   WHERE state = 'active' AND query_start < NOW() - INTERVAL '30 seconds';"
```

3. Monitor improvement:
```bash
# Watch metrics
watch -n 5 'curl -s http://localhost:8000/metrics | grep http_request_duration_seconds'
```

### P1 - Data Corruption

**Symptoms:**
- Inconsistent data
- Integrity constraint violations
- Backup restoration failures

**Actions:**

1. Stop writes immediately:
```bash
# Put system in read-only mode
curl -X POST http://localhost:8000/api/admin/readonly \
  -H "Authorization: Bearer <admin-token>"
```

2. Assess damage:
```bash
# Check database integrity
docker-compose exec postgres psql -U northbound -d northbound -c \
  "SELECT * FROM pg_stat_database WHERE datname = 'northbound';"

# Look for constraint violations
docker-compose logs api-gateway | grep -i "integrity\|constraint"
```

3. Restore from last known good backup:
```bash
# Identify last good backup
ls -lt logs/backups/

# Restore
./scripts/restore_backup.sh logs/backups/backup_<timestamp>.sql.gz
```

4. Verify restoration:
```bash
# Check data consistency
docker-compose exec postgres psql -U northbound -d northbound -c \
  "SELECT COUNT(*) FROM network_actions;"

# Run integrity checks
python scripts/verify_data_integrity.py
```

5. Resume operations:
```bash
# Disable read-only mode
curl -X POST http://localhost:8000/api/admin/readonly/disable \
  -H "Authorization: Bearer <admin-token>"
```

### Security Incident

**Symptoms:**
- Unauthorized access
- Suspicious activity
- Data breach

**Immediate Actions:**

1. Isolate system:
```bash
# Block external access
docker-compose down

# Or block at firewall level
sudo iptables -A INPUT -p tcp --dport 8000 -j DROP
```

2. Preserve evidence:
```bash
# Collect logs
docker-compose logs > incident-logs-$(date +%Y%m%d-%H%M%S).txt

# Backup current state
docker-compose exec postgres pg_dump -U northbound northbound > \
  incident-backup-$(date +%Y%m%d-%H%M%S).sql
```

3. Assess impact:
```bash
# Check for unauthorized access
docker-compose logs api-gateway | grep -i "authentication\|authorization"

# Review recent actions
docker-compose exec postgres psql -U northbound -d northbound -c \
  "SELECT * FROM network_actions WHERE created_at > NOW() - INTERVAL '24 hours' \
   ORDER BY created_at DESC;"
```

4. Contain breach:
```bash
# Revoke all tokens
docker-compose exec redis redis-cli FLUSHDB

# Reset passwords
# Disable compromised accounts
```

5. Notify:
- Security team
- Management
- Affected users (if applicable)
- Regulatory bodies (if required)

6. Investigate and remediate:
- Identify attack vector
- Patch vulnerabilities
- Implement additional controls
- Document incident

## Maintenance Windows

### Planned Maintenance

**Procedure:**

1. Schedule maintenance window:
- Notify users 7 days in advance
- Choose low-traffic time
- Estimate duration

2. Pre-maintenance checklist:
```bash
# Create backup
./scripts/backup.sh

# Verify backup
gunzip -t logs/backups/latest.sql.gz

# Document current state
docker-compose ps > pre-maintenance-state.txt
docker stats --no-stream >> pre-maintenance-state.txt
```

3. During maintenance:
```bash
# Put system in maintenance mode
curl -X POST http://localhost:8000/api/admin/maintenance \
  -H "Authorization: Bearer <admin-token>"

# Perform maintenance tasks
# ...

# Verify changes
python scripts/run_tests.py
```

4. Post-maintenance checklist:
```bash
# Disable maintenance mode
curl -X POST http://localhost:8000/api/admin/maintenance/disable \
  -H "Authorization: Bearer <admin-token>"

# Verify all services
curl http://localhost:8000/health

# Monitor for issues
docker-compose logs -f api-gateway
```

5. Notify users of completion

## Contacts

### Escalation Path

1. On-call Engineer: <phone>
2. Team Lead: <phone>
3. Engineering Manager: <phone>
4. CTO: <phone>

### External Contacts

- RYU Controller Support: <contact>
- ComnetsEMU Support: <contact>
- Cloud Provider Support: <contact>
- Security Team: <contact>

## Useful Commands Reference

### Docker Commands
```bash
# View logs
docker-compose logs -f [service]

# Restart service
docker-compose restart [service]

# Scale service
docker-compose up -d --scale api-gateway=3

# Execute command in container
docker-compose exec [service] [command]

# View resource usage
docker stats

# Clean up
docker system prune -a
```

### Database Commands
```bash
# Connect to database
docker-compose exec postgres psql -U northbound -d northbound

# Backup
docker-compose exec postgres pg_dump -U northbound northbound > backup.sql

# Restore
docker-compose exec -T postgres psql -U northbound northbound < backup.sql

# Check connections
docker-compose exec postgres psql -U northbound -d northbound -c \
  "SELECT * FROM pg_stat_activity;"
```

### Monitoring Commands
```bash
# Check health
curl http://localhost:8000/health

# View metrics
curl http://localhost:8000/metrics

# Test endpoint
curl -X POST http://localhost:8000/api/actions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"action":"test"}'
```
