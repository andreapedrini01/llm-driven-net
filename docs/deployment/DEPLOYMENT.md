# Deployment Guide

This guide covers deployment and configuration management for the LLM Integration Module.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Configuration Management](#configuration-management)
- [Secrets Management](#secrets-management)
- [Docker Deployment](#docker-deployment)
- [Environment-Specific Deployment](#environment-specific-deployment)
- [Health Checks and Monitoring](#health-checks-and-monitoring)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software

- Docker 20.10+
- Docker Compose 2.0+
- Python 3.11+
- OpenAI API Key

### System Requirements

- **Development**: 2 CPU cores, 4GB RAM
- **Staging**: 4 CPU cores, 8GB RAM
- **Production**: 8 CPU cores, 16GB RAM

## Configuration Management

### Environment Files

The application supports three environments, each with its own configuration:

- `config/dev.env` - Development environment
- `config/staging.env` - Staging environment
- `config/prod.env` - Production environment

### Configuration Validation

Validate configuration before deployment:

```bash
# Linux/macOS
python scripts/config_manager.py dev

# Windows
python scripts\config_manager.py dev
```

### Key Configuration Parameters

#### API Settings
- `API_HOST`: API server host (default: 0.0.0.0)
- `API_PORT`: API server port (default: 8080)
- `METRICS_PORT`: Prometheus metrics port (default: 8000)

#### ChatGPT API
- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `OPENAI_MODEL`: Model to use (recommended: gpt-4o-mini)
- `OPENAI_MAX_TOKENS`: Maximum tokens per request
- `OPENAI_TEMPERATURE`: Response randomness (0.0-2.0)
- `OPENAI_RATE_LIMIT_RPM`: Requests per minute limit

#### Security
- `JWT_SECRET_KEY`: Secret key for JWT tokens (required)
- `ENABLE_INPUT_SANITIZATION`: Enable input validation
- `RATE_LIMIT_REQUESTS_PER_MINUTE`: API rate limiting

## Secrets Management

### Using Environment Variables

The simplest approach for development:

```bash
export OPENAI_API_KEY="sk-..."
export JWT_SECRET_KEY="your-secret-key"
```

### Using Docker Secrets

For production deployments with Docker Swarm:

```bash
# Create secrets
echo "sk-..." | docker secret create openai_api_key -
echo "your-jwt-secret" | docker secret create jwt_secret_key -

# Update docker-compose.yml to use secrets
```

### Using Encrypted Secrets File

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

## Docker Deployment

### Build Docker Image

```bash
docker build -t llm-integration-module:latest .
```

### Run with Docker Compose

```bash
# Development
docker-compose --env-file config/dev.env up -d

# Staging
docker-compose --env-file config/staging.env up -d

# Production
docker-compose --env-file config/prod.env up -d
```

### View Logs

```bash
# Follow logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f llm-module
```

### Stop Services

```bash
docker-compose down
```

## Environment-Specific Deployment

### Development Deployment

```bash
# Linux/macOS
./scripts/deploy.sh dev deploy

# Windows
scripts\deploy.bat dev deploy
```

Features:
- Debug logging enabled
- Relaxed rate limits
- Lower cache TTL for faster iteration
- Mock API support

### Staging Deployment

```bash
# Linux/macOS
./scripts/deploy.sh staging deploy

# Windows
scripts\deploy.bat staging deploy
```

Features:
- Production-like configuration
- Slack notifications enabled
- Moderate rate limits
- Full monitoring

### Production Deployment

```bash
# Linux/macOS
./scripts/deploy.sh prod deploy

# Windows
scripts\deploy.bat prod deploy
```

Features:
- Optimized logging (WARNING level)
- Strict rate limits
- Email and Slack notifications
- Full monitoring and alerting
- Budget alerts enabled

### Rollback

If deployment fails or issues are detected:

```bash
# Linux/macOS
./scripts/deploy.sh prod rollback

# Windows
scripts\deploy.bat prod rollback
```

### Check Status

```bash
# Linux/macOS
./scripts/deploy.sh prod status

# Windows
scripts\deploy.bat prod status
```

## Health Checks and Monitoring

### Manual Health Check

```bash
python scripts/health_check.py
```

### Wait for Service to be Healthy

```bash
python scripts/health_check.py --wait --max-wait 60
```

### Health Check Endpoints

- **API Health**: `GET http://localhost:8080/health`
- **Metrics**: `GET http://localhost:8000/metrics`

### Monitoring with Prometheus

The application exposes Prometheus metrics on port 8000:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'llm-integration-module'
    static_configs:
      - targets: ['localhost:8000']
```

### Key Metrics

- `http_requests_total`: Total HTTP requests
- `http_request_duration_seconds`: Request duration
- `openai_api_calls_total`: ChatGPT API calls
- `openai_api_tokens_used`: Tokens consumed
- `openai_api_cost_usd`: Estimated API costs
- `intent_processing_duration_seconds`: Intent processing time
- `action_generation_duration_seconds`: Action generation time

## Troubleshooting

### Container Won't Start

1. Check logs:
   ```bash
   docker-compose logs llm-module
   ```

2. Verify configuration:
   ```bash
   python scripts/config_manager.py prod
   ```

3. Check secrets:
   ```bash
   docker exec llm-integration-module env | grep OPENAI
   ```

### Health Check Fails

1. Check if service is running:
   ```bash
   docker-compose ps
   ```

2. Test API directly:
   ```bash
   curl http://localhost:8080/health
   ```

3. Check file system permissions:
   ```bash
   ls -la cache/ output/ logs/
   ```

### ChatGPT API Errors

1. Verify API key:
   ```bash
   python -c "import openai; openai.api_key='your-key'; print(openai.Model.list())"
   ```

2. Check rate limits in logs
3. Verify network connectivity to OpenAI

### High Memory Usage

1. Check container stats:
   ```bash
   docker stats llm-integration-module
   ```

2. Adjust cache settings in environment file:
   ```
   STATE_CACHE_TTL=60
   STATE_REFRESH_INTERVAL=30
   ```

3. Restart container:
   ```bash
   docker-compose restart
   ```

### Configuration Issues

1. Validate configuration:
   ```bash
   python scripts/config_manager.py prod
   ```

2. Check for missing required values
3. Verify secrets are properly set
4. Review environment file syntax

## Best Practices

### Security

1. **Never commit secrets** to version control
2. **Use strong JWT secrets** (32+ characters)
3. **Rotate API keys** regularly
4. **Enable input sanitization** in production
5. **Use HTTPS** in production deployments

### Performance

1. **Tune cache settings** based on network state update frequency
2. **Monitor API costs** and set budget alerts
3. **Use appropriate ChatGPT model** (gpt-4o-mini for most cases)
4. **Enable rate limiting** to prevent abuse

### Reliability

1. **Set up health checks** in orchestration platform
2. **Configure automatic restarts** for containers
3. **Monitor logs** for errors and warnings
4. **Test rollback procedures** regularly
5. **Keep backups** of configuration and state

### Cost Optimization

1. **Use gpt-4o-mini** for routine operations
2. **Set budget alerts** to avoid surprises
3. **Cache responses** when possible
4. **Optimize prompts** to reduce token usage
5. **Monitor token consumption** via metrics

## Support

For issues or questions:

1. Check logs: `docker-compose logs -f`
2. Run health checks: `python scripts/health_check.py`
3. Validate configuration: `python scripts/config_manager.py <env>`
4. Review documentation in `docs/` directory
