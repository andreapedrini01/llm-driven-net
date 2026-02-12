# Deployment Architecture

## Overview

The LLM Integration Module supports multiple deployment strategies to accommodate different environments and requirements.

## Deployment Options

### 1. Docker Compose (Recommended for Development/Testing)

**Use Case**: Local development, testing, small-scale deployments

**Advantages**:
- Simple setup and configuration
- Easy to debug and iterate
- Minimal infrastructure requirements
- Quick deployment and rollback

**Files**:
- `Dockerfile` - Container image definition
- `docker-compose.yml` - Service orchestration
- `.dockerignore` - Build optimization

**Deployment**:
```bash
docker-compose --env-file config/dev.env up -d
```

### 2. Kubernetes (Recommended for Production)

**Use Case**: Production deployments, high availability, auto-scaling

**Advantages**:
- Horizontal auto-scaling
- Self-healing and high availability
- Rolling updates and rollbacks
- Resource management and isolation
- Service discovery and load balancing

**Files**:
- `k8s/deployment.yaml` - Deployment, Service, ConfigMap, PVC
- `k8s/hpa.yaml` - Horizontal Pod Autoscaler
- `k8s/ingress.yaml` - Ingress configuration
- `k8s/secrets-template.yaml` - Secrets template

**Deployment**:
```bash
kubectl apply -f k8s/
```

### 3. Standalone (Development Only)

**Use Case**: Local development without containers

**Deployment**:
```bash
source venv/bin/activate
python -m uvicorn src.main:app --host 0.0.0.0 --port 8080
```

## Architecture Components

### Application Layer

```
┌─────────────────────────────────────────┐
│         Load Balancer / Ingress         │
└─────────────────┬───────────────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
┌───────▼────────┐  ┌──────▼─────────┐
│   Instance 1   │  │   Instance 2   │
│                │  │                │
│  API (8080)    │  │  API (8080)    │
│  Metrics(8000) │  │  Metrics(8000) │
└───────┬────────┘  └──────┬─────────┘
        │                   │
        └─────────┬─────────┘
                  │
        ┌─────────▼─────────┐
        │  Shared Storage   │
        │  - Cache          │
        │  - Output         │
        └───────────────────┘
```

### Storage Architecture

```
┌──────────────────────────────────────────┐
│           Application Pod                │
│                                          │
│  ┌────────────┐  ┌──────────────────┐  │
│  │   Cache    │  │     Output       │  │
│  │  (5GB PVC) │  │    (10GB PVC)    │  │
│  └────────────┘  └──────────────────┘  │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │         Logs (EmptyDir)            │ │
│  └────────────────────────────────────┘ │
└──────────────────────────────────────────┘
```

### Monitoring Architecture

```
┌─────────────────────────────────────────┐
│         Application Instances           │
│         (Expose /metrics on :8000)      │
└─────────────────┬───────────────────────┘
                  │
        ┌─────────▼─────────┐
        │    Prometheus     │
        │  (Scrape metrics) │
        └─────────┬─────────┘
                  │
        ┌─────────▼─────────┐
        │     Grafana       │
        │  (Visualization)  │
        └───────────────────┘
                  │
        ┌─────────▼─────────┐
        │   Alertmanager    │
        │  (Notifications)  │
        └───────────────────┘
```

## Configuration Management

### Environment Hierarchy

```
Base Configuration (.env.example)
    │
    ├─── Development (config/dev.env)
    │    - Debug enabled
    │    - Verbose logging
    │    - Relaxed limits
    │
    ├─── Staging (config/staging.env)
    │    - Production-like
    │    - Moderate logging
    │    - Standard limits
    │
    └─── Production (config/prod.env)
         - Optimized settings
         - Minimal logging
         - Strict limits
```

### Secrets Management Flow

```
┌──────────────────────────────────────────┐
│         Secrets Sources                  │
│                                          │
│  1. Environment Variables (Dev)          │
│  2. Docker Secrets (Docker Swarm)        │
│  3. Kubernetes Secrets (K8s)             │
│  4. Encrypted File (Local)               │
└─────────────────┬────────────────────────┘
                  │
        ┌─────────▼─────────┐
        │  Secrets Manager  │
        │  (Priority Order) │
        └─────────┬─────────┘
                  │
        ┌─────────▼─────────┐
        │   Application     │
        └───────────────────┘
```

## Scaling Strategy

### Horizontal Scaling (Kubernetes)

**Triggers**:
- CPU usage > 70%
- Memory usage > 80%
- Custom metrics (request rate, queue depth)

**Configuration**:
```yaml
minReplicas: 2
maxReplicas: 10
scaleUp: 100% every 30s (max 2 pods)
scaleDown: 50% every 60s (stabilization: 5min)
```

### Vertical Scaling

**Resource Requests**:
- CPU: 250m (0.25 cores)
- Memory: 512Mi

**Resource Limits**:
- CPU: 1000m (1 core)
- Memory: 2Gi

## High Availability

### Redundancy

- **Minimum 2 replicas** in production
- **Pod anti-affinity** to spread across nodes
- **Multiple availability zones** when possible

### Health Checks

**Liveness Probe**:
- Endpoint: `/health`
- Initial delay: 30s
- Period: 10s
- Timeout: 5s
- Failure threshold: 3

**Readiness Probe**:
- Endpoint: `/health`
- Initial delay: 10s
- Period: 5s
- Timeout: 3s
- Failure threshold: 3

### Failure Recovery

```
Pod Failure
    │
    ├─── Liveness probe fails
    │    └─── Kubernetes restarts pod
    │
    ├─── Readiness probe fails
    │    └─── Pod removed from service
    │         (traffic redirected)
    │
    └─── Node failure
         └─── Pods rescheduled to
              healthy nodes
```

## Network Architecture

### Ingress Configuration

```
Internet
    │
    ▼
┌─────────────────┐
│  Ingress (TLS)  │
│  - SSL Termination
│  - Rate Limiting
│  - Path Routing
└────────┬────────┘
         │
    ┌────▼────┐
    │ Service │
    │ (ClusterIP)
    └────┬────┘
         │
    ┌────▼────────────┐
    │  Pod Endpoints  │
    │  - 10.0.1.5:8080
    │  - 10.0.1.6:8080
    └─────────────────┘
```

### Service Mesh (Optional)

For advanced deployments, consider service mesh (Istio/Linkerd):
- mTLS between services
- Advanced traffic management
- Observability and tracing
- Circuit breaking

## Backup and Recovery

### Data Backup

**Automated Backups**:
```bash
# Daily backup of persistent volumes
kubectl exec deployment/llm-integration-module -- \
  tar czf - /app/cache /app/output | \
  aws s3 cp - s3://backups/$(date +%Y%m%d).tar.gz
```

**Backup Schedule**:
- Cache: Daily (7-day retention)
- Output: Daily (30-day retention)
- Configuration: On change (version controlled)

### Disaster Recovery

**Recovery Time Objective (RTO)**: < 15 minutes
**Recovery Point Objective (RPO)**: < 1 hour

**Recovery Steps**:
1. Deploy from version-controlled manifests
2. Restore secrets from secure storage
3. Restore persistent volume data from backups
4. Verify health checks pass
5. Gradually restore traffic

## Security Architecture

### Network Security

```
┌─────────────────────────────────────────┐
│         External Network                │
└─────────────────┬───────────────────────┘
                  │
        ┌─────────▼─────────┐
        │   Firewall/WAF    │
        │  - DDoS Protection
        │  - Rate Limiting
        └─────────┬─────────┘
                  │
        ┌─────────▼─────────┐
        │  Ingress (TLS)    │
        │  - SSL/TLS 1.3
        │  - Certificate Mgmt
        └─────────┬─────────┘
                  │
        ┌─────────▼─────────┐
        │  Service Mesh     │
        │  - mTLS
        │  - AuthN/AuthZ
        └─────────┬─────────┘
                  │
        ┌─────────▼─────────┐
        │   Application     │
        │  - Input Validation
        │  - JWT Auth
        └───────────────────┘
```

### Secrets Security

- **Encryption at rest**: All secrets encrypted
- **Encryption in transit**: TLS for all communication
- **Access control**: RBAC for secret access
- **Rotation**: Regular key rotation (90 days)
- **Audit**: All secret access logged

## Cost Optimization

### Resource Optimization

**Right-sizing**:
- Monitor actual resource usage
- Adjust requests/limits based on metrics
- Use HPA to scale based on demand

**Cost Monitoring**:
- Track ChatGPT API costs via Prometheus
- Set budget alerts
- Optimize prompt engineering to reduce tokens

### Infrastructure Costs

**Development**: ~$50/month
- 1 small instance
- Minimal storage

**Staging**: ~$200/month
- 2 medium instances
- Moderate storage
- Monitoring stack

**Production**: ~$500-1000/month
- 2-10 instances (auto-scaled)
- High-availability storage
- Full monitoring and alerting
- ChatGPT API costs (variable)

## Deployment Checklist

### Pre-Deployment

- [ ] Configuration validated
- [ ] Secrets created and tested
- [ ] Docker image built and scanned
- [ ] Health checks verified
- [ ] Monitoring configured
- [ ] Backup strategy in place
- [ ] Rollback plan documented

### Deployment

- [ ] Deploy to staging first
- [ ] Run integration tests
- [ ] Verify health checks
- [ ] Check metrics and logs
- [ ] Gradual traffic migration
- [ ] Monitor for errors

### Post-Deployment

- [ ] Verify all services healthy
- [ ] Check monitoring dashboards
- [ ] Review logs for errors
- [ ] Validate API functionality
- [ ] Document any issues
- [ ] Update runbooks

## Troubleshooting Guide

### Common Issues

**Pod CrashLoopBackOff**:
- Check logs: `kubectl logs <pod>`
- Verify secrets are set
- Check resource limits
- Validate configuration

**High Memory Usage**:
- Review cache settings
- Check for memory leaks
- Adjust resource limits
- Consider vertical scaling

**Slow Response Times**:
- Check ChatGPT API latency
- Review database queries
- Analyze request patterns
- Consider caching strategies

**API Rate Limiting**:
- Monitor rate limit metrics
- Adjust OpenAI rate limits
- Implement request queuing
- Consider multiple API keys

## References

- [Docker Documentation](https://docs.docker.com/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Prometheus Monitoring](https://prometheus.io/docs/)
- [OpenAI API Documentation](https://platform.openai.com/docs/)
