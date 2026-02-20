# Quick Reference - Northbound Script Generator

## Essential Commands

### Deployment

```bash
# Start system
./deployment/deploy.sh docker-compose development

# Stop system
docker-compose down

# Restart service
docker-compose restart api-gateway

# View logs
docker-compose logs -f api-gateway
```

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Service status
docker-compose ps

# Database
docker-compose exec postgres pg_isready -U northbound

# Redis
docker-compose exec redis redis-cli ping
```

### Backup & Recovery

```bash
# Manual backup
docker-compose exec postgres pg_dump -U northbound northbound > backup.sql

# Restore
docker-compose exec -T postgres psql -U northbound northbound < backup.sql

# List backups
ls -lt logs/backups/
```

### Monitoring

```bash
# View metrics
curl http://localhost:8000/metrics

# Check resource usage
docker stats

# Database connections
docker-compose exec postgres psql -U northbound -d northbound -c \
  "SELECT count(*) FROM pg_stat_activity;"
```

### Troubleshooting

```bash
# Check logs for errors
docker-compose logs api-gateway | grep -i error

# Restart all services
docker-compose restart

# Clear Redis cache
docker-compose exec redis redis-cli FLUSHDB

# Database maintenance
docker-compose exec postgres psql -U northbound -d northbound -c "VACUUM ANALYZE;"
```

## Service URLs

- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Dashboard: http://localhost:3000
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001
- InfluxDB: http://localhost:8086

## Default Credentials

**API Admin:**
- Username: admin
- Password: (set in .env)

**Grafana:**
- Username: admin
- Password: admin (change on first login)

**InfluxDB:**
- Username: admin
- Password: (set in .env)

## Common Issues

### Service Won't Start
```bash
# Check logs
docker-compose logs [service-name]

# Verify dependencies
docker-compose ps

# Restart
docker-compose restart [service-name]
```

### Database Connection Error
```bash
# Check PostgreSQL
docker-compose ps postgres

# Test connection
docker-compose exec postgres psql -U northbound -d northbound

# Reset database
docker-compose down -v
docker-compose up -d
```

### High Memory Usage
```bash
# Check usage
docker stats

# Clear cache
docker-compose exec redis redis-cli FLUSHDB

# Restart services
docker-compose restart
```

### Slow Performance
```bash
# Check slow queries
docker-compose exec postgres psql -U northbound -d northbound -c \
  "SELECT query, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 5;"

# Scale up
docker-compose up -d --scale api-gateway=3

# Check resources
docker stats
```

## Emergency Procedures

### System Down
1. Check service status: `docker-compose ps`
2. View logs: `docker-compose logs --tail=100`
3. Restart: `docker-compose restart`
4. If still down: `docker-compose down && docker-compose up -d`

### Data Corruption
1. Stop writes: Put system in read-only mode
2. Identify last good backup: `ls -lt logs/backups/`
3. Restore: `./scripts/restore_backup.sh logs/backups/backup_<timestamp>.sql.gz`
4. Verify: Run integrity checks
5. Resume: Disable read-only mode

### Security Incident
1. Isolate: `docker-compose down`
2. Preserve evidence: Collect logs
3. Assess impact: Review recent actions
4. Contain: Revoke tokens, reset passwords
5. Notify: Security team and management

## Configuration Files

- `.env` - Environment variables
- `config/system_config.yaml` - System configuration
- `config/backup_config.yaml` - Backup settings
- `docker-compose.yml` - Service orchestration

## Log Locations

- Application: `logs/northbound_*.log`
- Actions: `logs/actions.jsonl`
- Database: `logs/network_changes.db`
- Retry Queue: `logs/retry_queue.db`

## Maintenance Schedule

**Daily:**
- Health checks
- Log review
- Backup verification

**Weekly:**
- Security audit
- Database maintenance
- Log rotation

**Monthly:**
- System updates
- Performance review
- Capacity planning

## Support Contacts

- On-call Engineer: [phone]
- Team Lead: [phone]
- Engineering Manager: [phone]

## Documentation

- Deployment Guide: `docs/deployment_guide.md`
- Troubleshooting: `docs/troubleshooting_guide.md`
- Operations Runbook: `docs/operations_runbook.md`
- API Documentation: http://localhost:8000/docs

## Useful Aliases

Add to your shell profile:

```bash
# Northbound aliases
alias nb-start='docker-compose up -d'
alias nb-stop='docker-compose down'
alias nb-logs='docker-compose logs -f api-gateway'
alias nb-health='curl http://localhost:8000/health'
alias nb-restart='docker-compose restart api-gateway'
alias nb-backup='docker-compose exec postgres pg_dump -U northbound northbound > backup-$(date +%Y%m%d-%H%M%S).sql'
```
