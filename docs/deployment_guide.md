# Deployment Guide - Northbound Script Generator

## Overview

This guide covers deployment options for the Northbound Script Generator system in various environments.

## Prerequisites

### Required Software
- Docker 20.10+
- Docker Compose 2.0+ (for Docker Compose deployment)
- kubectl 1.24+ (for Kubernetes deployment)
- Python 3.11+ (for local development)

### System Requirements
- CPU: 4+ cores recommended
- RAM: 8GB minimum, 16GB recommended
- Disk: 50GB minimum for logs and backups
- Network: Stable connection to RYU Controller and ComnetsEMU

## Quick Start

### 1. Clone and Configure

```bash
# Clone repository
git clone <repository-url>
cd northbound-script-generator

# Create environment file
cp .env.example .env

# Edit .env with your configuration
nano .env
```

### 2. Deploy with Docker Compose

```bash
# Basic deployment
./deployment/deploy.sh docker-compose development

# Production deployment with monitoring
./deployment/deploy.sh docker-compose production

# With monitoring stack (Prometheus + Grafana)
./deployment/deploy.sh docker-compose monitoring
```

### 3. Verify Deployment

```bash
# Check service health
curl http://localhost:8000/health

# View logs
docker-compose logs -f api-gateway

# Access services
# - API: http://localhost:8000
# - Docs: http://localhost:8000/docs
# - Dashboard: http://localhost:3000
# - Prometheus: http://localhost:9090 (if monitoring profile)
# - Grafana: http://localhost:3001 (if monitoring profile)
```

## Deployment Options

### Docker Compose Deployment

Best for: Development, testing, small production deployments

```bash
# Start all services
docker-compose up -d

# Start with specific profile
docker-compose --profile production up -d
docker-compose --profile monitoring up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f [service-name]

# Restart specific service
docker-compose restart api-gateway
```

### Kubernetes Deployment

Best for: Production, high availability, scalability

```bash
# Deploy to Kubernetes
./deployment/deploy.sh kubernetes production

# Check deployment status
kubectl get pods -n northbound
kubectl get services -n northbound

# View logs
kubectl logs -f deployment/api-gateway -n northbound

# Scale deployment
kubectl scale deployment/api-gateway --replicas=3 -n northbound
```

### Manual Deployment

For development or custom setups:

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://user:pass@localhost/northbound"
export REDIS_URL="redis://localhost:6379/0"

# Run API Gateway
uvicorn src.api.gateway:app --host 0.0.0.0 --port 8000

# Run in development mode with auto-reload
uvicorn src.api.gateway:app --reload
```

## Configuration

### Environment Variables

Key configuration variables in `.env`:

```bash
# Database
DATABASE_URL=postgresql://northbound:password@postgres:5432/northbound
POSTGRES_PASSWORD=changeme

# Redis
REDIS_URL=redis://:password@redis:6379/0
REDIS_PASSWORD=changeme

# InfluxDB
INFLUXDB_URL=http://influxdb:8086
INFLUXDB_TOKEN=my-super-secret-token
INFLUXDB_ORG=northbound
INFLUXDB_BUCKET=metrics

# RYU Controller
RYU_CONTROLLER_HOST=ryu-controller
RYU_CONTROLLER_PORT=8080

# ComnetsEMU
COMNETSEMU_HOST=comnetsemu
COMNETSEMU_PORT=6653

# Security
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# Application
LOG_LEVEL=INFO
WORKERS=4
```

### Configuration Files

System configuration: `config/system_config.example.yaml`
Backup configuration: `config/backup_config.example.yaml`

Copy example files and customize:

```bash
cp config/system_config.example.yaml config/system_config.yaml
cp config/backup_config.example.yaml config/backup_config.yaml
```

## Health Checks

### API Health Endpoint

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "database": "connected",
    "redis": "connected",
    "influxdb": "connected"
  }
}
```

### Service-Specific Checks

```bash
# PostgreSQL
docker-compose exec postgres pg_isready -U northbound

# Redis
docker-compose exec redis redis-cli ping

# InfluxDB
docker-compose exec influxdb influx ping
```

## Scaling

### Horizontal Scaling (Docker Compose)

```bash
# Scale API Gateway
docker-compose up -d --scale api-gateway=3

# With load balancer
docker-compose --profile production up -d
```

### Horizontal Scaling (Kubernetes)

```bash
# Scale deployment
kubectl scale deployment/api-gateway --replicas=5 -n northbound

# Auto-scaling
kubectl autoscale deployment/api-gateway \
  --min=2 --max=10 --cpu-percent=70 -n northbound
```

## Backup and Recovery

### Automated Backups

Backups run automatically every hour. Configuration in `config/backup_config.yaml`.

### Manual Backup

```bash
# Backup database
docker-compose exec postgres pg_dump -U northbound northbound > backup.sql

# Backup with compression
docker-compose exec postgres pg_dump -U northbound northbound | gzip > backup.sql.gz
```

### Restore from Backup

```bash
# Restore database
docker-compose exec -T postgres psql -U northbound northbound < backup.sql

# Restore from compressed backup
gunzip -c backup.sql.gz | docker-compose exec -T postgres psql -U northbound northbound
```

## Monitoring

### Prometheus Metrics

Access Prometheus: `http://localhost:9090`

Key metrics:
- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request latency
- `network_actions_total` - Network actions executed
- `network_action_errors_total` - Failed actions

### Grafana Dashboards

Access Grafana: `http://localhost:3001`
Default credentials: admin/admin

Pre-configured dashboards:
- System Overview
- API Performance
- Network Actions
- Error Rates

### InfluxDB Metrics

Access InfluxDB UI: `http://localhost:8086`

Query metrics using Flux:

```flux
from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "network_actions")
```

## Troubleshooting

See [Troubleshooting Guide](./troubleshooting_guide.md) for common issues and solutions.

## Security

### SSL/TLS Configuration

For production, configure SSL certificates:

```bash
# Place certificates
cp your-cert.pem deployment/nginx/ssl/cert.pem
cp your-key.pem deployment/nginx/ssl/key.pem

# Deploy with production profile
docker-compose --profile production up -d
```

### Secrets Management

Never commit secrets to version control. Use:
- Environment variables
- Docker secrets
- Kubernetes secrets
- External secret managers (AWS Secrets Manager, HashiCorp Vault)

## Maintenance

### Update Deployment

```bash
# Pull latest changes
git pull

# Rebuild images
docker-compose build

# Restart services
docker-compose up -d
```

### Database Migrations

```bash
# Run migrations
docker-compose exec api-gateway alembic upgrade head

# Rollback migration
docker-compose exec api-gateway alembic downgrade -1
```

### Log Rotation

Logs are automatically rotated. Manual cleanup:

```bash
# Clean old logs (older than 7 days)
find logs/ -name "*.log" -mtime +7 -delete
```

## Performance Tuning

### Database Optimization

```sql
-- Analyze tables
ANALYZE;

-- Vacuum database
VACUUM ANALYZE;

-- Check slow queries
SELECT * FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;
```

### Redis Optimization

```bash
# Check memory usage
docker-compose exec redis redis-cli INFO memory

# Clear cache if needed
docker-compose exec redis redis-cli FLUSHDB
```

### Application Tuning

Adjust workers in `.env`:

```bash
# For CPU-bound workloads
WORKERS=<number_of_cpu_cores>

# For I/O-bound workloads
WORKERS=<2 * number_of_cpu_cores + 1>
```

## Next Steps

- Review [API Documentation](./api_documentation.md)
- Read [Integration Guide](./integration_guide.md)
- Check [Troubleshooting Guide](./troubleshooting_guide.md)
- Review [Operations Runbook](./operations_runbook.md)
