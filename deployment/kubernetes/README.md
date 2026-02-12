# Kubernetes Deployment Guide

This directory contains Kubernetes manifests for deploying the LLM Integration Module.

## Prerequisites

- Kubernetes cluster (1.20+)
- kubectl configured
- Helm (optional, for monitoring stack)
- Ingress controller (nginx recommended)
- cert-manager (for TLS certificates)

## Quick Start

### 1. Create Namespace

```bash
kubectl create namespace llm-module
kubectl config set-context --current --namespace=llm-module
```

### 2. Create Secrets

```bash
# Copy and edit secrets template
cp secrets-template.yaml secrets.yaml
# Edit secrets.yaml with your actual secrets

# Apply secrets
kubectl apply -f secrets.yaml

# Delete the file (don't commit it!)
rm secrets.yaml
```

Or create secrets from command line:

```bash
kubectl create secret generic llm-secrets \
  --from-literal=openai-api-key='sk-...' \
  --from-literal=jwt-secret-key='your-secret' \
  --from-literal=admin-password='secure-password' \
  --from-literal=operator-password='secure-password' \
  --from-literal=viewer-password='secure-password'
```

### 3. Deploy Application

```bash
# Apply all manifests
kubectl apply -f deployment.yaml
kubectl apply -f hpa.yaml
kubectl apply -f ingress.yaml
```

### 4. Verify Deployment

```bash
# Check pods
kubectl get pods

# Check services
kubectl get svc

# Check ingress
kubectl get ingress

# View logs
kubectl logs -f deployment/llm-integration-module
```

## Configuration

### ConfigMap

Edit the ConfigMap in `deployment.yaml` to adjust application settings:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: llm-config
data:
  openai-model: "gpt-4o-mini"
  openai-max-tokens: "2000"
  # ... other settings
```

Apply changes:

```bash
kubectl apply -f deployment.yaml
kubectl rollout restart deployment/llm-integration-module
```

### Secrets

Update secrets:

```bash
kubectl edit secret llm-secrets
```

Or recreate:

```bash
kubectl delete secret llm-secrets
kubectl create secret generic llm-secrets --from-literal=openai-api-key='new-key'
```

## Scaling

### Manual Scaling

```bash
# Scale to 5 replicas
kubectl scale deployment llm-integration-module --replicas=5
```

### Auto-scaling

The HPA (Horizontal Pod Autoscaler) is configured to scale between 2-10 replicas based on CPU and memory usage.

View HPA status:

```bash
kubectl get hpa
kubectl describe hpa llm-integration-module-hpa
```

Adjust HPA settings in `hpa.yaml` and apply:

```bash
kubectl apply -f hpa.yaml
```

## Monitoring

### Prometheus Metrics

The application exposes Prometheus metrics on port 8000.

To scrape metrics, ensure your Prometheus is configured to discover pods with annotations:

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8000"
  prometheus.io/path: "/metrics"
```

### View Metrics

Port-forward to access metrics:

```bash
kubectl port-forward svc/llm-integration-module 8000:8000
curl http://localhost:8000/metrics
```

## Ingress and TLS

### Configure Ingress

Edit `ingress.yaml` to set your domain:

```yaml
spec:
  tls:
  - hosts:
    - your-domain.com
    secretName: llm-module-tls
  rules:
  - host: your-domain.com
```

### TLS Certificates

Using cert-manager:

```bash
# Install cert-manager (if not already installed)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create ClusterIssuer
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

## Persistent Storage

### PersistentVolumeClaims

The deployment uses PVCs for cache and output:

- `llm-cache-pvc`: 5Gi for network state cache
- `llm-output-pvc`: 10Gi for action outputs

View PVCs:

```bash
kubectl get pvc
```

### Backup Data

```bash
# Backup cache
kubectl exec deployment/llm-integration-module -- tar czf - /app/cache | tar xzf - -C ./backup/

# Backup output
kubectl exec deployment/llm-integration-module -- tar czf - /app/output | tar xzf - -C ./backup/
```

## Troubleshooting

### Pod Not Starting

```bash
# Check pod status
kubectl get pods
kubectl describe pod <pod-name>

# View logs
kubectl logs <pod-name>

# Check events
kubectl get events --sort-by='.lastTimestamp'
```

### Configuration Issues

```bash
# Verify ConfigMap
kubectl get configmap llm-config -o yaml

# Verify Secrets
kubectl get secret llm-secrets -o yaml
```

### Network Issues

```bash
# Test service connectivity
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- sh
curl http://llm-integration-module:8080/health
```

### Resource Issues

```bash
# Check resource usage
kubectl top pods
kubectl top nodes

# Describe pod for resource limits
kubectl describe pod <pod-name>
```

## Updating

### Rolling Update

```bash
# Update image
kubectl set image deployment/llm-integration-module llm-module=llm-integration-module:v2

# Or apply updated deployment.yaml
kubectl apply -f deployment.yaml

# Watch rollout
kubectl rollout status deployment/llm-integration-module
```

### Rollback

```bash
# View rollout history
kubectl rollout history deployment/llm-integration-module

# Rollback to previous version
kubectl rollout undo deployment/llm-integration-module

# Rollback to specific revision
kubectl rollout undo deployment/llm-integration-module --to-revision=2
```

## Cleanup

```bash
# Delete all resources
kubectl delete -f deployment.yaml
kubectl delete -f hpa.yaml
kubectl delete -f ingress.yaml

# Delete PVCs (warning: this deletes data!)
kubectl delete pvc llm-cache-pvc llm-output-pvc

# Delete secrets
kubectl delete secret llm-secrets

# Delete namespace
kubectl delete namespace llm-module
```

## Best Practices

1. **Use namespaces** to isolate environments
2. **Set resource limits** to prevent resource exhaustion
3. **Enable monitoring** with Prometheus and Grafana
4. **Configure alerts** for critical issues
5. **Use secrets** for sensitive data
6. **Enable TLS** for production deployments
7. **Regular backups** of persistent data
8. **Test rollback procedures** before production
9. **Monitor costs** via Prometheus metrics
10. **Use HPA** for automatic scaling
