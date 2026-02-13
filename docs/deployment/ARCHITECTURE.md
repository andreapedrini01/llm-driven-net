# Deployment Architecture

## Overview

The LLM Integration Module is designed to support multiple deployment strategies, from simple local development to highly available production environments. This document describes the system architecture, component interactions, network design, and infrastructure requirements.

For practical deployment instructions, see the [Deployment Guide](DEPLOYMENT_GUIDE.md).

## System Architecture Overview

The LLM Integration Module follows a modular architecture with clear separation of concerns:

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

### Key Components

- **API Server**: FastAPI application serving HTTP requests on port 8080
- **Metrics Endpoint**: Prometheus metrics exposed on port 8000
- **Shared Storage**: Persistent volumes for cache and output data
- **Load Balancer**: Distributes traffic across multiple instances

## Component Architecture

### Application Layer

The application consists of several key components:

**API Layer** (`src/api/`)
- REST API endpoints for intent processing and action generation
- Request validation and sanitization
- Response formatting and error handling
- Health check endpoints

**Core Logic** (`src/core/`)
- Intent processing engine
- Action generation logic
- State management
- Business rule enforcement

**Integration Layer** (`src/integrations/`)
- ChatGPT API client
- External service integrations
- API rate limiting and retry logic

**Monitoring** (`src/monitoring/`)
- Prometheus metrics collection
- Performance tracking
- Cost monitoring
- Custom metrics

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

**Storage Types**:
- **Cache Volume**: Stores temporary state and cached responses (5GB)
- **Output Volume**: Stores generated actions and results (10GB)
- **Logs Volume**: Ephemeral storage for application logs

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

### Port Configuration

- **8080**: Main API server (HTTP/HTTPS)
- **8000**: Prometheus metrics endpoint
- **443**: External HTTPS (terminated at ingress)

### Service Mesh (Optional)

For advanced production deployments, consider implementing a service mesh (Istio/Linkerd):
- Mutual TLS (mTLS) between services
- Advanced traffic management and routing
- Distributed tracing and observability
- Circuit breaking and fault injection
- Fine-grained access control

## Data Flow

### Request Processing Flow

```
1. Client Request
   │
   ▼
2. Ingress (TLS termination, routing)
   │
   ▼
3. Service (load balancing)
   │
   ▼
4. API Server (validation, authentication)
   │
   ▼
5. Core Logic (intent processing)
   │
   ├─── Cache Check
   │    └─── Return cached result (if available)
   │
   ├─── ChatGPT API Call
   │    └─── Process with LLM
   │
   └─── Action Generation
        │
        ▼
6. Store Output
   │
   ▼
7. Return Response
   │
   ▼
8. Update Metrics
```

### Monitoring Data Flow

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

### Security Layers

**1. Network Layer**
- Firewall rules restricting inbound traffic
- DDoS protection at edge
- Network segmentation

**2. Transport Layer**
- TLS 1.3 for all external communication
- Certificate management via cert-manager
- Mutual TLS between services (optional)

**3. Application Layer**
- JWT-based authentication
- Input validation and sanitization
- Rate limiting per client
- API key management

**4. Data Layer**
- Encryption at rest for persistent volumes
- Secrets encrypted in etcd (Kubernetes)
- Secure secrets management

### Secrets Management

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

**Security Best Practices**:
- Encryption at rest: All secrets encrypted
- Encryption in transit: TLS for all communication
- Access control: RBAC for secret access
- Rotation: Regular key rotation (90 days recommended)
- Audit: All secret access logged

## Scalability Considerations

### Horizontal Scaling

The application is designed to scale horizontally by adding more instances:

**Kubernetes Horizontal Pod Autoscaler (HPA)**:
```yaml
minReplicas: 2
maxReplicas: 10
scaleUp: 100% every 30s (max 2 pods)
scaleDown: 50% every 60s (stabilization: 5min)
```

**Scaling Triggers**:
- CPU usage > 70%
- Memory usage > 80%
- Custom metrics (request rate, queue depth)

**Stateless Design**:
- No session state stored in application memory
- Shared storage for cache and output
- Any instance can handle any request

### Vertical Scaling

**Resource Requests** (guaranteed):
- CPU: 250m (0.25 cores)
- Memory: 512Mi

**Resource Limits** (maximum):
- CPU: 1000m (1 core)
- Memory: 2Gi

**When to Scale Vertically**:
- Consistent high CPU/memory usage across all pods
- Large prompt processing requirements
- Memory-intensive operations

### Performance Optimization

**Caching Strategy**:
- Cache frequently accessed state data
- Configurable TTL based on update frequency
- Cache invalidation on state changes

**Connection Pooling**:
- Reuse HTTP connections to ChatGPT API
- Connection pool sizing based on rate limits

**Async Processing**:
- Non-blocking I/O for API calls
- Concurrent request handling
- Background task processing

## High Availability

### Redundancy Strategy

**Minimum Requirements**:
- At least 2 replicas in production
- Pod anti-affinity to spread across nodes
- Multiple availability zones when possible

**Failure Domains**:
- Multiple nodes in different availability zones
- Separate control plane and worker nodes
- Redundant load balancers

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

**Recovery Time Objectives**:
- Pod restart: < 1 minute
- Node failure recovery: < 5 minutes
- Full disaster recovery: < 15 minutes

## Infrastructure Requirements

### Development Environment

**Minimum Requirements**:
- 2 CPU cores
- 4GB RAM
- 20GB disk space
- Docker 20.10+

**Estimated Cost**: ~$50/month
- 1 small instance
- Minimal storage
- Development-grade monitoring

### Staging Environment

**Recommended Requirements**:
- 4 CPU cores
- 8GB RAM
- 50GB disk space
- Kubernetes cluster (2 nodes)

**Estimated Cost**: ~$200/month
- 2 medium instances
- Moderate storage
- Full monitoring stack
- Staging-grade availability

### Production Environment

**Minimum Requirements**:
- 8 CPU cores (across cluster)
- 16GB RAM (across cluster)
- 100GB disk space
- Kubernetes cluster (3+ nodes)
- Load balancer
- Monitoring infrastructure

**Estimated Cost**: ~$500-1000/month
- 2-10 instances (auto-scaled)
- High-availability storage
- Full monitoring and alerting
- Production-grade SLA
- ChatGPT API costs (variable)

### Cloud Provider Options

**AWS**:
- EKS for Kubernetes
- ELB for load balancing
- EBS for persistent storage
- CloudWatch for monitoring

**Azure**:
- AKS for Kubernetes
- Azure Load Balancer
- Azure Disk for storage
- Azure Monitor

**Google Cloud**:
- GKE for Kubernetes
- Cloud Load Balancing
- Persistent Disk
- Cloud Monitoring

## Deployment Options

### 1. Docker Compose (Development/Testing)

**Use Case**: Local development, testing, small-scale deployments

**Advantages**:
- Simple setup and configuration
- Easy to debug and iterate
- Minimal infrastructure requirements
- Quick deployment and rollback

**Deployment**:
```bash
docker-compose --env-file config/dev.env up -d
```

### 2. Kubernetes (Production)

**Use Case**: Production deployments, high availability, auto-scaling

**Advantages**:
- Horizontal auto-scaling
- Self-healing and high availability
- Rolling updates and rollbacks
- Resource management and isolation
- Service discovery and load balancing

**Deployment**:
```bash
kubectl apply -f k8s/
```

### 3. Standalone (Development Only)

**Use Case**: Local development without containers

**Deployment**:
```bash
source venv/bin/activate
python -m src.main
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
    │    - Port: 8080
    │
    ├─── Staging (config/staging.env)
    │    - Production-like
    │    - Moderate logging
    │    - Standard limits
    │    - Port: 8080
    │
    └─── Production (config/prod.env)
         - Optimized settings
         - Minimal logging
         - Strict limits
         - Port: 8080
```

### Configuration Parameters

**API Settings**:
- `API_HOST`: 0.0.0.0 (bind to all interfaces)
- `API_PORT`: 8080 (standard HTTP alternate port)
- `METRICS_PORT`: 8000 (Prometheus metrics)

**Performance Settings**:
- `STATE_CACHE_TTL`: Cache time-to-live
- `STATE_REFRESH_INTERVAL`: State refresh frequency
- `OPENAI_RATE_LIMIT_RPM`: API rate limit

## Backup and Recovery

### Data Backup Strategy

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

## Cost Optimization

### Resource Optimization

**Right-sizing**:
- Monitor actual resource usage via metrics
- Adjust requests/limits based on observed patterns
- Use HPA to scale based on demand, not fixed capacity

**Cost Monitoring**:
- Track ChatGPT API costs via Prometheus metrics
- Set budget alerts for API spending
- Optimize prompt engineering to reduce token usage
- Use gpt-4o-mini for routine operations

### Infrastructure Costs

**Development**: ~$50/month
- 1 small instance
- Minimal storage
- Basic monitoring

**Staging**: ~$200/month
- 2 medium instances
- Moderate storage
- Full monitoring stack

**Production**: ~$500-1000/month
- 2-10 instances (auto-scaled)
- High-availability storage
- Full monitoring and alerting
- ChatGPT API costs (variable, typically $100-500/month)

## Related Documentation

- [Deployment Guide](DEPLOYMENT_GUIDE.md) - Practical deployment instructions
- [API Usage](../API_USAGE.md) - API endpoints and usage
- [Dependencies](../development/DEPENDENCIES.md) - Technical requirements and dependencies
- [Troubleshooting](../TROUBLESHOOTING.md) - Common issues and solutions

## References

- [Docker Documentation](https://docs.docker.com/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Prometheus Monitoring](https://prometheus.io/docs/)
- [OpenAI API Documentation](https://platform.openai.com/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
