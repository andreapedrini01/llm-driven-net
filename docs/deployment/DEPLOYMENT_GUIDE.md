# Deployment Guide

This guide provides practical instructions for deploying the LLM Integration Module to various environments. For architecture details and design decisions, see [Architecture](ARCHITECTURE.md).

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Local Deployment](#local-deployment)
- [Docker Deployment](#docker-deployment)
- [Cloud Deployment](#cloud-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Configuration](#configuration)
- [Secrets Management](#secrets-management)
- [Monitoring and Maintenance](#monitoring-and-maintenance)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)
- [Related Documentation](#related-documentation)

## Overview

The LLM Integration Module supports multiple deployment strategies:

- **Local Deployment**: Development and testing on your local machine
- **Docker Compose**: Containerized deployment for development and small-scale production
- **Kubernetes**: Production deployment with auto-scaling and high availability
- **Cloud Platforms**: Deployment to AWS, Azure, or GCP

Choose the deployment method that best fits your requirements. For most production deployments, we recommend Kubernetes.

## Prerequisites

### Required Software

- **Python 3.11+**: Application runtime
- **Docker 20.10+**: Container runtime (for Docker/Kubernetes deployments)
- **Docker Compose 2.0+**: Container orchestration (for Docker deployments)
- **kubectl**: Kubernetes CLI (for Kubernetes deployments)
- **OpenAI API Key**: Required for ChatGPT integration

For installation instructions, see the [Installation Guide](../INSTALLATION.md).

### System Requirements

**Development Environment**:
- 2 CPU cores
- 4GB RAM
- 10GB disk space

**Staging Environment**:
- 4 CPU cores
- 8GB RAM
- 20GB disk space

**Production Environment**:
- 8 CPU cores
- 16GB RAM
- 50GB disk space

## Local Deployment

Local deployment is ideal for development and testing without containers.

### Setup Steps

1. **Activate Virtual Environment**:

```bash
# Linux/macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

2. **Install Dependencies**:

```bash
pip install -r requirements.txt
```

For detailed dependency information, see [Dependencies](../development/DEPENDENCIES.md).

3. **Configure Environment**:

Create a `.env` file in the project root:

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8080
METRICS_PORT=8000

# OpenAI Configuration
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=2000
OPENAI_TEMPERATURE=0.7

# Security
JWT_SECRET_KEY=your-secret-key-here
ENABLE_INPUT_SANITIZATION=true

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=60
OPENAI_RATE_LIMIT_RPM=500
```

4. **Run the Application**:

```bash
python -m src.main
```

The API will be available at `http://localhost:8080`.

### Verification

Test the deployment:

```bash
# Check health endpoint
curl http://localhost:8080/health

# Check metrics endpoint
curl http://localhost:8000/metrics
```

## Docker Deployment

Docker deployment provides containerized execution with consistent environments.

### Build Docker Image

```bash
docker build -t llm-integration-module:latest .
```

### Run with Docker Compose

The application supports three environments, each with its own configuration file.

#### Development Deployment

```bash
docker-compose --env-file config/dev.env up -d
```

Features:
- Debug logging enabled
- Relaxed rate limits
- Lower cache TTL for faster iteration
- Mock API support

#### Staging Deployment

```bash
docker-compose --env-file config/staging.env up -d
```

Features:
- Production-like configuration
- Slack notifications enabled
- Moderate rate limits
- Full monitoring

#### Production Deployment

```bash
docker-compose --env-file config/prod.env up -d
```

Features:
- Optimized logging (WARNING level)
- Strict rate limits
- Email and Slack notifications
- Full monitoring and alerting
- Budget alerts enabled

### Docker Management Commands

**View Logs**:
```bash
# Follow all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f llm-module
```

**Check Status**:
```bash
docker-compose ps
```

**Stop Services**:
```bash
docker-compose down
```

**Restart Services**:
```bash
docker-compose restart
```

## Cloud Deployment

### AWS Deployment

#### Using ECS (Elastic Container Service)

1. **Push Image to ECR**:

```bash
# Authenticate to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Tag and push image
docker tag llm-integration-module:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/llm-integration-module:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/llm-integration-module:latest
```

2. **Create ECS Task Definition**:

```json
{
  "family": "llm-integration-module",
  "containerDefinitions": [
    {
      "name": "llm-module",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/llm-integration-module:latest",
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        },
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "API_PORT",
          "value": "8080"
        },
        {
          "name": "METRICS_PORT",
          "value": "8000"
        }
      ],
      "secrets": [
        {
          "name": "OPENAI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:<account-id>:secret:openai-api-key"
        },
        {
          "name": "JWT_SECRET_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:<account-id>:secret:jwt-secret"
        }
      ]
    }
  ]
}
```

3. **Create ECS Service**:

```bash
aws ecs create-service \
  --cluster llm-cluster \
  --service-name llm-integration-module \
  --task-definition llm-integration-module \
  --desired-count 2 \
  --launch-type FARGATE
```

### Azure Deployment

#### Using Azure Container Instances

```bash
az container create \
  --resource-group llm-rg \
  --name llm-integration-module \
  --image llm-integration-module:latest \
  --ports 8080 8000 \
  --environment-variables \
    API_PORT=8080 \
    METRICS_PORT=8000 \
  --secure-environment-variables \
    OPENAI_API_KEY=<your-key> \
    JWT_SECRET_KEY=<your-secret>
```

### GCP Deployment

#### Using Cloud Run

```bash
# Build and push to GCR
gcloud builds submit --tag gcr.io/<project-id>/llm-integration-module

# Deploy to Cloud Run
gcloud run deploy llm-integration-module \
  --image gcr.io/<project-id>/llm-integration-module \
  --port 8080 \
  --set-env-vars API_PORT=8080,METRICS_PORT=8000 \
  --set-secrets OPENAI_API_KEY=openai-api-key:latest,JWT_SECRET_KEY=jwt-secret:latest
```

## Kubernetes Deployment

Kubernetes provides production-grade orchestration with auto-scaling and high availability.

### Prerequisites

- Kubernetes cluster (1.20+)
- kubectl configured
- Helm (optional, for easier management)

### Deployment Steps

1. **Create Namespace**:

```bash
kubectl create namespace llm-integration
```

2. **Create Secrets**:

```bash
# Create OpenAI API key secret
kubectl create secret generic openai-api-key \
  --from-literal=key=sk-your-api-key-here \
  -n llm-integration

# Create JWT secret
kubectl create secret generic jwt-secret \
  --from-literal=key=your-jwt-secret-here \
  -n llm-integration
```

3. **Deploy Application**:

```bash
kubectl apply -f k8s/ -n llm-integration
```

This deploys:
- Deployment with 2 replicas
- Service (ClusterIP)
- ConfigMap for configuration
- PersistentVolumeClaims for storage
- HorizontalPodAutoscaler
- Ingress (optional)

4. **Verify Deployment**:

```bash
# Check pods
kubectl get pods -n llm-integration

# Check service
kubectl get svc -n llm-integration

# Check logs
kubectl logs -f deployment/llm-integration-module -n llm-integration
```

### Accessing the Application

**Port Forward (Development)**:
```bash
kubectl port-forward svc/llm-integration-module 8080:8080 -n llm-integration
```

**Ingress (Production)**:
Configure ingress in `k8s/ingress.yaml` with your domain and TLS certificate.

### Scaling

**Manual Scaling**:
```bash
kubectl scale deployment llm-integration-module --replicas=5 -n llm-integration
```

**Auto-Scaling**:
The HorizontalPodAutoscaler automatically scales based on:
- CPU usage > 70%
- Memory usage > 80%
- Scale range: 2-10 replicas

### Updates and Rollbacks

**Rolling Update**:
```bash
kubectl set image deployment/llm-integration-module \
  llm-module=llm-integration-module:v2.0 \
  -n llm-integration
```

**Rollback**:
```bash
kubectl rollout undo deployment/llm-integration-module -n llm-integration
```

**Check Rollout Status**:
```bash
kubectl rollout status deployment/llm-integration-module -n llm-integration
```

## Configuration

### Environment Files

The application uses environment-specific configuration files:

- `config/dev.env` - Development environment
- `config/staging.env` - Staging environment
- `config/prod.env` - Production environment

### Key Configuration Parameters

#### API Settings

```bash
API_HOST=0.0.0.0          # API server host
API_PORT=8080             # API server port (standardized)
METRICS_PORT=8000         # Prometheus metrics port
```

#### ChatGPT API

```bash
OPENAI_API_KEY=sk-...                # Your OpenAI API key (required)
OPENAI_MODEL=gpt-4o-mini             # Model to use (recommended)
OPENAI_MAX_TOKENS=2000               # Maximum tokens per request
OPENAI_TEMPERATURE=0.7               # Response randomness (0.0-2.0)
OPENAI_RATE_LIMIT_RPM=500            # Requests per minute limit
```

#### Security

```bash
JWT_SECRET_KEY=your-secret-key       # Secret key for JWT tokens (required)
ENABLE_INPUT_SANITIZATION=true       # Enable input validation
RATE_LIMIT_REQUESTS_PER_MINUTE=60    # API rate limiting
```

#### Caching

```bash
STATE_CACHE_TTL=300                  # Cache time-to-live (seconds)
STATE_REFRESH_INTERVAL=60            # State refresh interval (seconds)
```

### Configuration Validation

Validate configuration before deployment:

```bash
# Linux/macOS
python scripts/config_manager.py dev

# Windows
python scripts\config_manager.py dev
```

This checks:
- Required values are set
- Values are in valid ranges
- Secrets are properly configured
- File paths are accessible

## Secrets Management

### Environment Variables (Development)

The simplest approach for local development:

```bash
export OPENAI_API_KEY="sk-..."
export JWT_SECRET_KEY="your-secret-key"
```

### Docker Secrets (Docker Swarm)

For production Docker deployments:

```bash
# Create secrets
echo "sk-..." | docker secret create openai_api_key -
echo "your-jwt-secret" | docker secret create jwt_secret_key -
```

Update `docker-compose.yml` to use secrets:

```yaml
secrets:
  openai_api_key:
    external: true
  jwt_secret_key:
    external: true
```

### Kubernetes Secrets

For Kubernetes deployments:

```bash
# Create from literal
kubectl create secret generic openai-api-key \
  --from-literal=key=sk-your-api-key-here

# Create from file
kubectl create secret generic jwt-secret \
  --from-file=key=./jwt-secret.txt
```

### Encrypted Secrets File (Local)

For secure local storage:

```bash
# Create encrypted secrets file
python scripts/secrets_manager.py create

# Set encryption key
export SECRETS_ENCRYPTION_KEY="your-encryption-key"
```

### Generate Secure Keys

```bash
# Generate JWT secret
python scripts/secrets_manager.py generate-jwt
```

### Best Practices

1. **Never commit secrets** to version control
2. **Use strong JWT secrets** (32+ characters, random)
3. **Rotate API keys** regularly (every 90 days)
4. **Use different secrets** for each environment
5. **Encrypt secrets at rest** in production

## Monitoring and Maintenance

### Health Checks

#### Manual Health Check

```bash
python scripts/health_check.py
```

This verifies:
- API is responding
- Metrics endpoint is accessible
- File system is writable
- Configuration is valid

#### Wait for Service

```bash
python scripts/health_check.py --wait --max-wait 60
```

Useful in deployment scripts to wait for the service to be ready.

#### Health Endpoints

- **API Health**: `GET http://localhost:8080/health`
- **Metrics**: `GET http://localhost:8000/metrics`

### Monitoring with Prometheus

The application exposes Prometheus metrics on port 8000.

**Prometheus Configuration** (`prometheus.yml`):

```yaml
scrape_configs:
  - job_name: 'llm-integration-module'
    static_configs:
      - targets: ['localhost:8000']
```

**Key Metrics**:

- `http_requests_total`: Total HTTP requests
- `http_request_duration_seconds`: Request duration
- `openai_api_calls_total`: ChatGPT API calls
- `openai_api_tokens_used`: Tokens consumed
- `openai_api_cost_usd`: Estimated API costs
- `intent_processing_duration_seconds`: Intent processing time
- `action_generation_duration_seconds`: Action generation time

### Alerting

Configure alerts in `monitoring/alerts.yml`:

- Service availability
- High error rates
- API cost thresholds
- Resource usage
- Rate limit violations

### Log Management

**View Logs**:

```bash
# Docker
docker-compose logs -f

# Kubernetes
kubectl logs -f deployment/llm-integration-module -n llm-integration

# Local
tail -f logs/app.log
```

**Log Levels by Environment**:

- Development: DEBUG
- Staging: INFO
- Production: WARNING

### Maintenance Tasks

#### Update Dependencies

```bash
pip install --upgrade -r requirements.txt
```

See [Dependencies](../development/DEPENDENCIES.md) for details.

#### Rotate Secrets

```bash
# Generate new JWT secret
python scripts/secrets_manager.py generate-jwt

# Update in deployment
kubectl create secret generic jwt-secret \
  --from-literal=key=<new-secret> \
  --dry-run=client -o yaml | kubectl apply -f -

# Restart pods to pick up new secret
kubectl rollout restart deployment/llm-integration-module
```

#### Clear Cache

```bash
# Docker
docker-compose exec llm-module rm -rf /app/cache/*

# Kubernetes
kubectl exec deployment/llm-integration-module -- rm -rf /app/cache/*

# Local
rm -rf cache/*
```

## Troubleshooting

For general troubleshooting, see the [Troubleshooting Guide](../TROUBLESHOOTING.md).

### Container Won't Start

**Symptoms**: Container exits immediately or enters CrashLoopBackOff

**Solutions**:

1. Check logs:
   ```bash
   docker-compose logs llm-module
   # or
   kubectl logs <pod-name>
   ```

2. Verify configuration:
   ```bash
   python scripts/config_manager.py prod
   ```

3. Check secrets are set:
   ```bash
   docker exec llm-integration-module env | grep OPENAI
   # or
   kubectl exec <pod-name> -- env | grep OPENAI
   ```

4. Verify file permissions:
   ```bash
   ls -la cache/ output/ logs/
   ```

### Health Check Fails

**Symptoms**: Health endpoint returns errors or timeouts

**Solutions**:

1. Check if service is running:
   ```bash
   docker-compose ps
   # or
   kubectl get pods
   ```

2. Test API directly:
   ```bash
   curl http://localhost:8080/health
   ```

3. Check port configuration:
   ```bash
   # Verify API_PORT is set to 8080
   grep API_PORT config/prod.env
   ```

4. Review logs for errors:
   ```bash
   docker-compose logs -f llm-module
   ```

### ChatGPT API Errors

**Symptoms**: API calls fail or return errors

**Solutions**:

1. Verify API key:
   ```bash
   python -c "import openai; openai.api_key='your-key'; print(openai.Model.list())"
   ```

2. Check rate limits in logs

3. Verify network connectivity:
   ```bash
   curl https://api.openai.com/v1/models
   ```

4. Review OpenAI status page: https://status.openai.com/

### High Memory Usage

**Symptoms**: Container using excessive memory or being OOM killed

**Solutions**:

1. Check container stats:
   ```bash
   docker stats llm-integration-module
   # or
   kubectl top pod <pod-name>
   ```

2. Adjust cache settings in environment file:
   ```bash
   STATE_CACHE_TTL=60
   STATE_REFRESH_INTERVAL=30
   ```

3. Increase memory limits:
   ```yaml
   # docker-compose.yml
   mem_limit: 2g
   
   # k8s/deployment.yaml
   resources:
     limits:
       memory: 2Gi
   ```

4. Restart container:
   ```bash
   docker-compose restart
   # or
   kubectl rollout restart deployment/llm-integration-module
   ```

### Port Conflicts

**Symptoms**: Cannot bind to port 8080 or 8000

**Solutions**:

1. Check what's using the port:
   ```bash
   # Linux/macOS
   lsof -i :8080
   
   # Windows
   netstat -ano | findstr :8080
   ```

2. Stop conflicting service or change port in configuration

3. Use different port in `.env`:
   ```bash
   API_PORT=8081
   ```

### Deployment Script Fails

**Symptoms**: `deploy.sh` or `deploy.bat` exits with errors

**Solutions**:

1. Check prerequisites:
   ```bash
   docker --version
   docker-compose --version
   python --version
   ```

2. Validate configuration:
   ```bash
   python scripts/config_manager.py <env>
   ```

3. Check Docker daemon is running:
   ```bash
   docker ps
   ```

4. Review script output for specific errors

### Kubernetes Pod Issues

**Symptoms**: Pods not starting or failing readiness checks

**Solutions**:

1. Describe pod for events:
   ```bash
   kubectl describe pod <pod-name> -n llm-integration
   ```

2. Check pod logs:
   ```bash
   kubectl logs <pod-name> -n llm-integration
   ```

3. Verify secrets exist:
   ```bash
   kubectl get secrets -n llm-integration
   ```

4. Check resource availability:
   ```bash
   kubectl describe nodes
   ```

5. Verify PVC is bound:
   ```bash
   kubectl get pvc -n llm-integration
   ```

## Best Practices

### Security

1. **Never commit secrets** to version control
   - Use `.gitignore` for `.env` files
   - Use secret management systems

2. **Use strong JWT secrets**
   - Minimum 32 characters
   - Random, cryptographically secure
   - Different for each environment

3. **Rotate API keys regularly**
   - Every 90 days minimum
   - Immediately if compromised

4. **Enable input sanitization** in production
   ```bash
   ENABLE_INPUT_SANITIZATION=true
   ```

5. **Use HTTPS** in production
   - Configure TLS in ingress
   - Use valid certificates (Let's Encrypt)

6. **Implement rate limiting**
   ```bash
   RATE_LIMIT_REQUESTS_PER_MINUTE=60
   ```

7. **Run containers as non-root**
   - Already configured in Dockerfile
   - Verify with `docker exec <container> whoami`

### Performance

1. **Tune cache settings** based on state update frequency
   ```bash
   STATE_CACHE_TTL=300
   STATE_REFRESH_INTERVAL=60
   ```

2. **Monitor API costs** and set budget alerts
   - Track via Prometheus metrics
   - Set up alerts in monitoring/alerts.yml

3. **Use appropriate ChatGPT model**
   - `gpt-4o-mini` for most cases (cost-effective)
   - `gpt-4` only when necessary

4. **Enable rate limiting** to prevent abuse
   ```bash
   OPENAI_RATE_LIMIT_RPM=500
   ```

5. **Optimize resource allocation**
   - Monitor actual usage
   - Adjust requests/limits accordingly

### Reliability

1. **Set up health checks** in orchestration
   - Liveness probe: restart unhealthy pods
   - Readiness probe: remove from service

2. **Configure automatic restarts**
   ```yaml
   restart: unless-stopped  # Docker Compose
   ```

3. **Monitor logs** for errors and warnings
   - Centralized logging (ELK, Splunk)
   - Alert on error patterns

4. **Test rollback procedures** regularly
   ```bash
   kubectl rollout undo deployment/llm-integration-module
   ```

5. **Keep backups** of configuration and state
   - Version control for configs
   - Regular PVC snapshots

6. **Use multiple replicas** in production
   ```bash
   kubectl scale deployment/llm-integration-module --replicas=3
   ```

### Cost Optimization

1. **Use gpt-4o-mini** for routine operations
   - 10x cheaper than gpt-4
   - Sufficient for most use cases

2. **Set budget alerts** to avoid surprises
   ```bash
   BUDGET_ALERT_THRESHOLD_USD=100
   ```

3. **Cache responses** when possible
   - Reduces redundant API calls
   - Faster response times

4. **Optimize prompts** to reduce token usage
   - Clear, concise instructions
   - Avoid unnecessary context

5. **Monitor token consumption** via metrics
   ```bash
   curl http://localhost:8000/metrics | grep openai_api_tokens
   ```

6. **Right-size resources**
   - Don't over-provision
   - Use auto-scaling

### Deployment

1. **Deploy to staging first**
   - Test in production-like environment
   - Validate before production

2. **Use gradual rollouts**
   - Canary deployments
   - Blue-green deployments

3. **Automate deployments**
   - CI/CD pipelines
   - Infrastructure as Code

4. **Document deployment procedures**
   - Runbooks for common tasks
   - Incident response plans

5. **Monitor during deployment**
   - Watch metrics and logs
   - Be ready to rollback

## Related Documentation

- **[Architecture](ARCHITECTURE.md)**: Deployment architecture and design details
- **[Installation Guide](../INSTALLATION.md)**: Local installation instructions
- **[Dependencies](../development/DEPENDENCIES.md)**: Dependency requirements and management
- **[Troubleshooting](../TROUBLESHOOTING.md)**: General troubleshooting guide
- **[API Usage](../API_USAGE.md)**: API reference and usage examples

## Support

For deployment issues:

1. Check logs: `docker-compose logs -f` or `kubectl logs -f <pod>`
2. Run health checks: `python scripts/health_check.py`
3. Validate configuration: `python scripts/config_manager.py <env>`
4. Review this guide and [Troubleshooting](../TROUBLESHOOTING.md)
5. Check monitoring dashboards for metrics and alerts
