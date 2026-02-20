# Deployment Configuration

This directory contains all deployment configurations for the Northbound Script Generator.

## Directory Structure

```
deployment/
├── deploy.sh                    # Main deployment script
├── grafana/                     # Grafana configuration
│   ├── dashboards/
│   │   └── dashboard.yml       # Dashboard provisioning
│   └── datasources/
│       └── datasources.yml     # Data source configuration
├── kubernetes/                  # Kubernetes manifests
│   ├── namespace.yaml          # Namespace definition
│   ├── configmap.yaml          # Configuration
│   ├── secrets.yaml            # Secrets (template)
│   ├── postgres-deployment.yaml # PostgreSQL
│   ├── api-gateway-deployment.yaml # API Gateway
│   └── ingress.yaml            # Ingress rules
├── nginx/                       # Nginx configuration
│   ├── nginx.conf              # Load balancer config
│   └── ssl/                    # SSL certificates (not in repo)
└── prometheus/                  # Prometheus configuration
    └── prometheus.yml          # Metrics collection config
```

## Quick Start

### Docker Compose Deployment

```bash
# Basic deployment
./deployment/deploy.sh docker-compose development

# Production with monitoring
./deployment/deploy.sh docker-compose production

# With full monitoring stack
./deployment/deploy.sh docker-compose monitoring
```

### Kubernetes Deployment

```bash
# Deploy to Kubernetes
./deployment/deploy.sh kubernetes production

# Check status
kubectl get pods -n northbound
kubectl get services -n northbound
```

## Configuration Files

### Prometheus (`prometheus/prometheus.yml`)

Configures metrics collection:
- Scrape intervals
- Target services
- Alert rules
- Storage settings

**Customization:**
- Adjust scrape intervals for your needs
- Add additional scrape targets
- Configure alert rules

### Nginx (`nginx/nginx.conf`)

Configures load balancing and SSL:
- Upstream servers
- SSL/TLS settings
- Rate limiting
- Security headers

**Customization:**
- Update SSL certificate paths
- Adjust rate limits
- Configure upstream servers
- Add custom locations

### Grafana

**Dashboards (`grafana/dashboards/dashboard.yml`):**
- Dashboard provisioning configuration
- Auto-import settings

**Data Sources (`grafana/datasources/datasources.yml`):**
- Prometheus connection
- InfluxDB connection
- Authentication settings

**Customization:**
- Add custom dashboards
- Configure additional data sources
- Adjust refresh intervals

### Kubernetes Manifests

**Namespace (`kubernetes/namespace.yaml`):**
- Defines the `northbound` namespace
- Resource quotas (optional)

**ConfigMap (`kubernetes/configmap.yaml`):**
- Application configuration
- Environment-specific settings

**Secrets (`kubernetes/secrets.yaml`):**
- Database passwords
- API keys
- JWT secrets
- **Note:** Template only, create actual secrets separately

**Deployments:**
- PostgreSQL: Database with persistent storage
- API Gateway: Application server with health checks
- Frontend: React dashboard

**Ingress (`kubernetes/ingress.yaml`):**
- External access configuration
- SSL termination
- Path-based routing

## Deployment Script (`deploy.sh`)

### Usage

```bash
./deployment/deploy.sh [TYPE] [ENVIRONMENT]
```

**Types:**
- `docker-compose` - Docker Compose deployment
- `kubernetes` or `k8s` - Kubernetes deployment

**Environments:**
- `development` - Development settings
- `production` - Production with Nginx
- `monitoring` - With Prometheus and Grafana

### Features

- Prerequisites checking
- Docker image building
- Service deployment
- Health verification
- Rollback capability
- Log viewing

### Examples

```bash
# Development deployment
./deployment/deploy.sh docker-compose development

# Production deployment
./deployment/deploy.sh docker-compose production

# Kubernetes production
./deployment/deploy.sh kubernetes production

# View logs
./deployment/deploy.sh logs

# Rollback
./deployment/deploy.sh rollback
```

## SSL/TLS Configuration

### For Nginx (Production)

1. Obtain SSL certificates:
```bash
# Using Let's Encrypt
certbot certonly --standalone -d your-domain.com

# Or use your own certificates
```

2. Place certificates:
```bash
cp /path/to/cert.pem deployment/nginx/ssl/cert.pem
cp /path/to/key.pem deployment/nginx/ssl/key.pem
```

3. Update nginx.conf if needed:
```nginx
ssl_certificate /etc/nginx/ssl/cert.pem;
ssl_certificate_key /etc/nginx/ssl/key.pem;
```

4. Deploy with production profile:
```bash
docker-compose --profile production up -d
```

### For Kubernetes

1. Create TLS secret:
```bash
kubectl create secret tls northbound-tls \
  --cert=/path/to/cert.pem \
  --key=/path/to/key.pem \
  -n northbound
```

2. Update ingress.yaml:
```yaml
spec:
  tls:
  - hosts:
    - your-domain.com
    secretName: northbound-tls
```

## Environment Variables

Required environment variables in `.env`:

```bash
# Database
POSTGRES_PASSWORD=changeme
DATABASE_URL=postgresql://northbound:password@postgres:5432/northbound

# Redis
REDIS_PASSWORD=changeme
REDIS_URL=redis://:password@redis:6379/0

# InfluxDB
INFLUXDB_TOKEN=my-super-secret-token
INFLUXDB_URL=http://influxdb:8086

# Security
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256

# RYU Controller
RYU_CONTROLLER_HOST=ryu-controller
RYU_CONTROLLER_PORT=8080

# ComnetsEMU
COMNETSEMU_HOST=comnetsemu
COMNETSEMU_PORT=6653

# Application
LOG_LEVEL=INFO
WORKERS=4
```

## Profiles

### Docker Compose Profiles

**Default (no profile):**
- API Gateway
- PostgreSQL
- Redis
- InfluxDB
- Frontend

**Production (`--profile production`):**
- All default services
- Nginx load balancer
- SSL termination

**Monitoring (`--profile monitoring`):**
- All default services
- Prometheus
- Grafana

### Usage

```bash
# Start with production profile
docker-compose --profile production up -d

# Start with monitoring profile
docker-compose --profile monitoring up -d

# Start with multiple profiles
docker-compose --profile production --profile monitoring up -d
```

## Health Checks

All services include health checks:

**API Gateway:**
```bash
curl http://localhost:8000/health
```

**PostgreSQL:**
```bash
docker-compose exec postgres pg_isready -U northbound
```

**Redis:**
```bash
docker-compose exec redis redis-cli ping
```

**InfluxDB:**
```bash
docker-compose exec influxdb influx ping
```

## Scaling

### Docker Compose

```bash
# Scale API Gateway
docker-compose up -d --scale api-gateway=3

# With load balancer
docker-compose --profile production up -d --scale api-gateway=3
```

### Kubernetes

```bash
# Manual scaling
kubectl scale deployment/api-gateway --replicas=5 -n northbound

# Auto-scaling
kubectl autoscale deployment/api-gateway \
  --min=2 --max=10 --cpu-percent=70 -n northbound
```

## Troubleshooting

### Deployment Fails

1. Check prerequisites:
```bash
docker --version
docker-compose --version
kubectl version  # for Kubernetes
```

2. Verify .env file exists:
```bash
ls -la .env
```

3. Check logs:
```bash
./deployment/deploy.sh logs
```

### Service Won't Start

1. Check service status:
```bash
docker-compose ps
# or
kubectl get pods -n northbound
```

2. View logs:
```bash
docker-compose logs [service-name]
# or
kubectl logs [pod-name] -n northbound
```

3. Verify dependencies:
```bash
# Ensure database is healthy before API starts
docker-compose ps postgres
```

### Port Conflicts

1. Check for conflicts:
```bash
# Linux/Mac
netstat -tuln | grep 8000

# Windows
netstat -ano | findstr :8000
```

2. Stop conflicting services or change ports in docker-compose.yml

## Maintenance

### Update Deployment

```bash
# Pull latest changes
git pull

# Rebuild images
docker-compose build --no-cache

# Restart services
docker-compose up -d
```

### Backup Before Deployment

```bash
# Backup database
docker-compose exec postgres pg_dump -U northbound northbound > \
  pre-deployment-backup-$(date +%Y%m%d-%H%M%S).sql
```

### Rollback

```bash
# Docker Compose
./deployment/deploy.sh rollback

# Kubernetes
kubectl rollout undo deployment/api-gateway -n northbound
```

## Security Best Practices

1. **Never commit secrets:**
   - Use `.env` file (in .gitignore)
   - Use Kubernetes secrets
   - Use external secret managers

2. **Use strong passwords:**
   - Generate random passwords
   - Rotate regularly
   - Use different passwords for each service

3. **Enable SSL/TLS:**
   - Use valid certificates
   - Enforce HTTPS
   - Configure security headers

4. **Limit access:**
   - Use firewall rules
   - Configure network policies
   - Implement rate limiting

5. **Keep updated:**
   - Update base images regularly
   - Apply security patches
   - Monitor CVE databases

## Additional Resources

- [Deployment Guide](../docs/deployment_guide.md)
- [Troubleshooting Guide](../docs/troubleshooting_guide.md)
- [Operations Runbook](../docs/operations_runbook.md)
- [Quick Reference](../docs/quick_reference.md)

## Support

For issues or questions:
1. Check the troubleshooting guide
2. Review logs
3. Contact the on-call engineer
4. Create an issue in the repository
