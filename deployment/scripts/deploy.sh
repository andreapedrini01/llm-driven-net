#!/bin/bash
# Deployment script for LLM Integration Module

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Functions
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_header() {
    echo ""
    echo "=========================================="
    echo "  $1"
    echo "=========================================="
    echo ""
}

# Parse arguments
ENVIRONMENT=${1:-dev}
ACTION=${2:-deploy}

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    print_error "Invalid environment: $ENVIRONMENT"
    echo "Usage: $0 <dev|staging|prod> [deploy|rollback|status]"
    exit 1
fi

# Validate action
if [[ ! "$ACTION" =~ ^(deploy|rollback|status)$ ]]; then
    print_error "Invalid action: $ACTION"
    echo "Usage: $0 <dev|staging|prod> [deploy|rollback|status]"
    exit 1
fi

print_header "LLM Integration Module - Deployment"
print_info "Environment: $ENVIRONMENT"
print_info "Action: $ACTION"

# Load environment configuration
ENV_FILE="config/${ENVIRONMENT}.env"
if [ ! -f "$ENV_FILE" ]; then
    print_error "Environment file not found: $ENV_FILE"
    exit 1
fi

print_success "Environment file loaded: $ENV_FILE"

# Function to deploy
deploy() {
    print_header "Deploying to $ENVIRONMENT"
    
    # 1. Pre-deployment checks
    print_info "Running pre-deployment checks..."
    
    if [ ! -f "Dockerfile" ]; then
        print_error "Dockerfile not found"
        exit 1
    fi
    
    if [ ! -f "docker-compose.yml" ]; then
        print_error "docker-compose.yml not found"
        exit 1
    fi
    
    print_success "Pre-deployment checks passed"
    
    # 2. Build Docker image
    print_info "Building Docker image..."
    
    IMAGE_TAG="llm-integration-module:${ENVIRONMENT}-$(date +%Y%m%d-%H%M%S)"
    docker build -t "$IMAGE_TAG" .
    docker tag "$IMAGE_TAG" "llm-integration-module:${ENVIRONMENT}-latest"
    
    print_success "Docker image built: $IMAGE_TAG"
    
    # 3. Stop existing containers
    print_info "Stopping existing containers..."
    
    docker-compose --env-file "$ENV_FILE" down || true
    
    print_success "Existing containers stopped"
    
    # 4. Start new containers
    print_info "Starting new containers..."
    
    docker-compose --env-file "$ENV_FILE" up -d
    
    print_success "New containers started"
    
    # 5. Wait for health check
    print_info "Waiting for service to become healthy..."
    
    python scripts/health_check.py --wait --max-wait 60
    
    if [ $? -eq 0 ]; then
        print_success "Deployment successful!"
    else
        print_error "Health check failed"
        print_warning "Rolling back..."
        rollback
        exit 1
    fi
    
    # 6. Run post-deployment tests
    if [ "$ENVIRONMENT" != "prod" ]; then
        print_info "Running post-deployment tests..."
        python scripts/health_check.py
    fi
    
    print_header "Deployment Complete"
    print_success "Service is running at http://localhost:8080"
    print_info "View logs: docker-compose logs -f"
    print_info "Check status: $0 $ENVIRONMENT status"
}

# Function to rollback
rollback() {
    print_header "Rolling back $ENVIRONMENT"
    
    print_info "Stopping current containers..."
    docker-compose --env-file "$ENV_FILE" down
    
    print_info "Starting previous version..."
    PREVIOUS_TAG="llm-integration-module:${ENVIRONMENT}-previous"
    
    if docker images | grep -q "$PREVIOUS_TAG"; then
        docker tag "$PREVIOUS_TAG" "llm-integration-module:${ENVIRONMENT}-latest"
        docker-compose --env-file "$ENV_FILE" up -d
        print_success "Rollback complete"
    else
        print_error "No previous version found"
        exit 1
    fi
}

# Function to check status
status() {
    print_header "Status Check - $ENVIRONMENT"
    
    print_info "Container status:"
    docker-compose --env-file "$ENV_FILE" ps
    
    echo ""
    print_info "Running health checks:"
    python scripts/health_check.py
    
    echo ""
    print_info "Recent logs:"
    docker-compose --env-file "$ENV_FILE" logs --tail=20
}

# Execute action
case $ACTION in
    deploy)
        deploy
        ;;
    rollback)
        rollback
        ;;
    status)
        status
        ;;
esac
