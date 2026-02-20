#!/bin/bash

# Northbound Script Generator Deployment Script
# This script automates the deployment process for different environments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local missing_deps=()
    
    if ! command_exists docker; then
        missing_deps+=("docker")
    fi
    
    if [ "$DEPLOYMENT_TYPE" = "docker-compose" ] && ! command_exists docker-compose; then
        missing_deps+=("docker-compose")
    fi
    
    if [ "$DEPLOYMENT_TYPE" = "kubernetes" ] && ! command_exists kubectl; then
        missing_deps+=("kubectl")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        log_error "Missing required dependencies: ${missing_deps[*]}"
        log_error "Please install them and try again."
        exit 1
    fi
    
    log_info "All prerequisites satisfied ✓"
}

# Build Docker images
build_images() {
    log_info "Building Docker images..."
    
    # Build API Gateway
    log_info "Building API Gateway image..."
    docker build -t northbound-api:latest -f Dockerfile .
    
    # Build Frontend
    if [ -d "frontend" ]; then
        log_info "Building Frontend image..."
        docker build -t northbound-frontend:latest -f frontend/Dockerfile frontend/
    fi
    
    log_info "Docker images built successfully ✓"
}

# Deploy with Docker Compose
deploy_docker_compose() {
    log_info "Deploying with Docker Compose..."
    
    # Check if .env file exists
    if [ ! -f ".env" ]; then
        log_warn ".env file not found. Creating from .env.example..."
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_warn "Please update .env file with your configuration before running again."
            exit 1
        else
            log_error ".env.example not found. Please create .env file manually."
            exit 1
        fi
    fi
    
    # Stop existing containers
    log_info "Stopping existing containers..."
    docker-compose down
    
    # Start services
    log_info "Starting services..."
    if [ "$ENVIRONMENT" = "production" ]; then
        docker-compose --profile production up -d
    elif [ "$ENVIRONMENT" = "monitoring" ]; then
        docker-compose --profile monitoring up -d
    else
        docker-compose up -d
    fi
    
    # Wait for services to be healthy
    log_info "Waiting for services to be healthy..."
    sleep 10
    
    # Check health
    check_health_docker_compose
    
    log_info "Deployment completed successfully ✓"
    log_info "API Gateway: http://localhost:8000"
    log_info "Frontend Dashboard: http://localhost:3000"
    log_info "API Documentation: http://localhost:8000/docs"
}

# Deploy to Kubernetes
deploy_kubernetes() {
    log_info "Deploying to Kubernetes..."
    
    # Create namespace
    log_info "Creating namespace..."
    kubectl apply -f deployment/kubernetes/namespace.yaml
    
    # Apply ConfigMap and Secrets
    log_info "Applying ConfigMap and Secrets..."
    kubectl apply -f deployment/kubernetes/configmap.yaml
    kubectl apply -f deployment/kubernetes/secrets.yaml
    
    # Deploy PostgreSQL
    log_info "Deploying PostgreSQL..."
    kubectl apply -f deployment/kubernetes/postgres-deployment.yaml
    
    # Deploy Redis
    log_info "Deploying Redis..."
    kubectl apply -f deployment/kubernetes/redis-deployment.yaml
    
    # Deploy InfluxDB
    log_info "Deploying InfluxDB..."
    kubectl apply -f deployment/kubernetes/influxdb-deployment.yaml
    
    # Wait for databases to be ready
    log_info "Waiting for databases to be ready..."
    kubectl wait --for=condition=ready pod -l app=postgres -n northbound --timeout=300s
    kubectl wait --for=condition=ready pod -l app=redis -n northbound --timeout=300s
    kubectl wait --for=condition=ready pod -l app=influxdb -n northbound --timeout=300s
    
    # Deploy API Gateway
    log_info "Deploying API Gateway..."
    kubectl apply -f deployment/kubernetes/api-gateway-deployment.yaml
    
    # Deploy Frontend
    log_info "Deploying Frontend..."
    kubectl apply -f deployment/kubernetes/frontend-deployment.yaml
    
    # Apply Ingress
    log_info "Applying Ingress..."
    kubectl apply -f deployment/kubernetes/ingress.yaml
    
    # Wait for deployments
    log_info "Waiting for deployments to be ready..."
    kubectl wait --for=condition=available deployment/api-gateway -n northbound --timeout=300s
    kubectl wait --for=condition=available deployment/frontend -n northbound --timeout=300s
    
    log_info "Deployment completed successfully ✓"
    
    # Get ingress info
    log_info "Getting ingress information..."
    kubectl get ingress -n northbound
}

# Check health for Docker Compose
check_health_docker_compose() {
    log_info "Checking service health..."
    
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -f http://localhost:8000/health >/dev/null 2>&1; then
            log_info "API Gateway is healthy ✓"
            return 0
        fi
        
        attempt=$((attempt + 1))
        log_info "Waiting for API Gateway to be healthy... ($attempt/$max_attempts)"
        sleep 2
    done
    
    log_error "API Gateway failed to become healthy"
    return 1
}

# Rollback deployment
rollback() {
    log_warn "Rolling back deployment..."
    
    if [ "$DEPLOYMENT_TYPE" = "docker-compose" ]; then
        docker-compose down
        log_info "Docker Compose deployment rolled back"
    elif [ "$DEPLOYMENT_TYPE" = "kubernetes" ]; then
        kubectl rollout undo deployment/api-gateway -n northbound
        kubectl rollout undo deployment/frontend -n northbound
        log_info "Kubernetes deployment rolled back"
    fi
}

# Show logs
show_logs() {
    if [ "$DEPLOYMENT_TYPE" = "docker-compose" ]; then
        docker-compose logs -f
    elif [ "$DEPLOYMENT_TYPE" = "kubernetes" ]; then
        kubectl logs -f -l app=api-gateway -n northbound
    fi
}

# Main script
main() {
    log_info "Northbound Script Generator Deployment"
    log_info "======================================="
    
    # Parse arguments
    DEPLOYMENT_TYPE="${1:-docker-compose}"
    ENVIRONMENT="${2:-development}"
    
    log_info "Deployment Type: $DEPLOYMENT_TYPE"
    log_info "Environment: $ENVIRONMENT"
    
    # Check prerequisites
    check_prerequisites
    
    # Build images
    build_images
    
    # Deploy based on type
    case "$DEPLOYMENT_TYPE" in
        docker-compose)
            deploy_docker_compose
            ;;
        kubernetes|k8s)
            deploy_kubernetes
            ;;
        *)
            log_error "Unknown deployment type: $DEPLOYMENT_TYPE"
            log_error "Supported types: docker-compose, kubernetes"
            exit 1
            ;;
    esac
    
    log_info ""
    log_info "Deployment completed successfully! 🎉"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Access the API documentation: http://localhost:8000/docs"
    log_info "  2. Access the dashboard: http://localhost:3000"
    log_info "  3. Check logs: ./deployment/deploy.sh logs"
    log_info "  4. Monitor health: curl http://localhost:8000/health"
}

# Handle script arguments
case "${1:-}" in
    logs)
        show_logs
        ;;
    rollback)
        rollback
        ;;
    *)
        main "$@"
        ;;
esac
