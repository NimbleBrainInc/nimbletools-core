#!/bin/bash

# NimbleTools Core Development Setup Script
# Sets up local development environment for contributing to NimbleTools Core

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CLUSTER_NAME="nimbletools-dev"
REGISTRY_PORT="5001"
PYTHON_VERSION="3.13"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Help function
show_help() {
    cat << EOF
NimbleTools Core Development Setup

USAGE:
    ./scripts/dev-setup.sh [OPTIONS]

OPTIONS:
    --cluster-name NAME     k3d cluster name (default: nimbletools-dev)
    --registry-port PORT    Local registry port (default: 5001)
    --python-version VER    Python version (default: 3.13)
    --skip-cluster          Skip k3d cluster creation
    --skip-python           Skip Python environment setup
    --skip-docker           Skip Docker setup
    -h, --help              Show this help message

EXAMPLES:
    # Full development setup
    ./scripts/dev-setup.sh

    # Setup with custom cluster name
    ./scripts/dev-setup.sh --cluster-name my-dev-cluster

    # Skip cluster creation (use existing)
    ./scripts/dev-setup.sh --skip-cluster

REQUIREMENTS:
    - Docker Desktop running
    - k3d installed (https://k3d.io)
    - Python 3.13+ available
    - kubectl installed

EOF
}

# Parse command line arguments
parse_args() {
    SKIP_CLUSTER="false"
    SKIP_PYTHON="false"
    SKIP_DOCKER="false"
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --cluster-name)
                CLUSTER_NAME="$2"
                shift 2
                ;;
            --registry-port)
                REGISTRY_PORT="$2"
                shift 2
                ;;
            --python-version)
                PYTHON_VERSION="$2"
                shift 2
                ;;
            --skip-cluster)
                SKIP_CLUSTER="true"
                shift
                ;;
            --skip-python)
                SKIP_PYTHON="true"
                shift
                ;;
            --skip-docker)
                SKIP_DOCKER="true"
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Please install Docker Desktop."
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker daemon not running. Please start Docker Desktop."
        exit 1
    fi
    
    # Check k3d if not skipping cluster
    if [[ "$SKIP_CLUSTER" != "true" ]]; then
        if ! command -v k3d &> /dev/null; then
            log_error "k3d not found. Install with: brew install k3d"
            exit 1
        fi
    fi
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Please install kubectl."
        exit 1
    fi
    
    # Check Python if not skipping
    if [[ "$SKIP_PYTHON" != "true" ]]; then
        if ! command -v python$PYTHON_VERSION &> /dev/null; then
            log_warning "Python $PYTHON_VERSION not found. Checking for python3..."
            if ! command -v python3 &> /dev/null; then
                log_error "Python not found. Please install Python $PYTHON_VERSION+."
                exit 1
            else
                # Use available python3
                PYTHON_CMD="python3"
                log_warning "Using $(python3 --version)"
            fi
        else
            PYTHON_CMD="python$PYTHON_VERSION"
        fi
    fi
    
    log_success "Prerequisites check passed"
}

# Setup local Docker registry
setup_registry() {
    if [[ "$SKIP_DOCKER" == "true" ]]; then
        log_info "Skipping Docker registry setup"
        return 0
    fi
    
    log_info "Setting up local Docker registry..."
    
    # Check if k3d registry is already running
    if k3d registry list | grep -q "k3d-nimbletools-registry"; then
        log_info "k3d registry already running"
        return 0
    fi
    
    # Clean up any existing standalone registry
    if docker ps -a | grep -q "nimbletools-registry"; then
        log_info "Cleaning up existing standalone registry..."
        docker stop nimbletools-registry 2>/dev/null || true
        docker rm nimbletools-registry 2>/dev/null || true
    fi
    
    # Create k3d registry
    k3d registry create nimbletools-registry --port "$REGISTRY_PORT" || {
        log_warning "Registry may already exist, continuing..."
    }
    
    log_success "k3d registry running on port $REGISTRY_PORT"
}

# Create k3d cluster
create_cluster() {
    if [[ "$SKIP_CLUSTER" == "true" ]]; then
        log_info "Skipping k3d cluster creation"
        return 0
    fi
    
    log_info "Creating k3d cluster '$CLUSTER_NAME'..."
    
    # Check if cluster already exists
    if k3d cluster list | grep -q "$CLUSTER_NAME"; then
        log_info "Cluster '$CLUSTER_NAME' already exists"
        
        # Make sure it's started
        k3d cluster start "$CLUSTER_NAME" || true
    else
        # Create cluster with registry (Traefik disabled for better performance)
        k3d cluster create "$CLUSTER_NAME" \
            --api-port 6550 \
            --registry-use "k3d-nimbletools-registry:$REGISTRY_PORT" \
            --agents 2 \
            --k3s-arg "--disable=traefik@server:*" \
            --wait
    fi
    
    # Set kubeconfig context
    kubectl config use-context "k3d-$CLUSTER_NAME"
    
    log_success "k3d cluster '$CLUSTER_NAME' is ready"
}

# Install nginx ingress controller
install_nginx_ingress() {
    if [[ "$SKIP_CLUSTER" == "true" ]]; then
        log_info "Skipping nginx ingress installation"
        return 0
    fi
    
    log_info "Installing nginx ingress controller..."
    
    # Check if nginx ingress is already installed
    if kubectl get namespace ingress-nginx &> /dev/null; then
        log_info "nginx ingress controller already installed"
        return 0
    fi
    
    # Install nginx ingress controller
    kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.1/deploy/static/provider/kind/deploy.yaml
    
    # Wait for nginx ingress to be ready
    log_info "Waiting for nginx ingress controller to be ready..."
    kubectl wait --namespace ingress-nginx \
        --for=condition=ready pod \
        --selector=app.kubernetes.io/component=controller \
        --timeout=120s
    
    log_success "nginx ingress controller is ready"
}

# Setup Python development environment
setup_python_env() {
    if [[ "$SKIP_PYTHON" == "true" ]]; then
        log_info "Skipping Python environment setup"
        return 0
    fi
    
    log_info "Setting up Python development environment..."
    
    # Create virtual environment if it doesn't exist
    if [[ ! -d "venv" ]]; then
        log_info "Creating Python virtual environment..."
        $PYTHON_CMD -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install development dependencies for each component
    local components=("universal-adapter" "operator" "control-plane")
    
    for component in "${components[@]}"; do
        if [[ -f "$component/requirements.txt" ]]; then
            log_info "Installing dependencies for $component..."
            pip install -r "$component/requirements.txt"
        fi
    done
    
    # Install development tools
    log_info "Installing development tools..."
    pip install \
        pytest \
        pytest-cov \
        pytest-asyncio \
        black \
        mypy \
        ruff \
        pre-commit
    
    # Setup pre-commit hooks
    if [[ -f ".pre-commit-config.yaml" ]]; then
        log_info "Setting up pre-commit hooks..."
        pre-commit install
    fi
    
    log_success "Python development environment ready"
    log_info "To activate: source venv/bin/activate"
}

# Build development images
build_dev_images() {
    if [[ "$SKIP_DOCKER" == "true" ]]; then
        log_info "Skipping Docker image builds"
        return 0
    fi
    
    log_info "Building development images..."
    
    local registry="localhost:$REGISTRY_PORT"
    local components=("universal-adapter" "operator" "control-plane")
    
    for component in "${components[@]}"; do
        if [[ -f "$component/Dockerfile" ]]; then
            log_info "Building $component image..."
            
            local image_name="nimbletools/$component:dev"
            local registry_image="$registry/$image_name"
            
            docker build -t "$image_name" -t "$registry_image" "$component/"
            docker push "$registry_image"
            
            log_success "Built and pushed $component image"
        fi
    done
}

# Create development values file
create_dev_values() {
    log_info "Creating development values file..."
    
    cat > values-dev.yaml << EOF
# Development values for NimbleTools Core
global:
  domain: nimbletools.local
  imageRegistry: localhost:$REGISTRY_PORT
  namespace: nimbletools-dev

# Use development images
universalAdapter:
  image:
    repository: nimbletools/universal-adapter
    tag: dev
    pullPolicy: Always

operator:
  image:
    repository: nimbletools/operator
    tag: dev
    pullPolicy: Always
  config:
    logLevel: debug

api:
  enabled: true
  image:
    repository: nimbletools/control-plane
    tag: dev
    pullPolicy: Always
  service:
    type: NodePort
  auth:
    provider: none

# Enable ingress for local development
ingress:
  enabled: true
  className: traefik
  annotations:
    traefik.ingress.kubernetes.io/router.tls: "false"
  hosts:
    - host: api.nimbletools.local
      paths:
        - path: /
          pathType: Prefix
  tls: []

# Enable monitoring
monitoring:
  enabled: true

# Development resource limits
operator:
  resources:
    requests:
      cpu: 50m
      memory: 64Mi
    limits:
      cpu: 200m
      memory: 256Mi

api:
  resources:
    requests:
      cpu: 50m
      memory: 64Mi
    limits:
      cpu: 200m
      memory: 256Mi
EOF
    
    log_success "Created values-dev.yaml"
}

# Setup /etc/hosts entries
setup_hosts() {
    log_info "Setting up local DNS entries..."
    
    local hosts_entry="127.0.0.1 api.nimbletools.local"
    
    if grep -q "api.nimbletools.local" /etc/hosts; then
        log_info "Hosts entry already exists"
    else
        log_info "Adding hosts entry (may require sudo password)..."
        echo "$hosts_entry" | sudo tee -a /etc/hosts > /dev/null
        log_success "Added hosts entry for api.nimbletools.local"
    fi
}

# Show development information
show_dev_info() {
    log_success ""
    log_success "🚀 Development environment setup complete!"
    log_success ""
    log_info "Development cluster: k3d-$CLUSTER_NAME"
    log_info "Local registry: localhost:$REGISTRY_PORT"
    log_info ""
    log_info "Quick commands:"
    log_info "  # Install NimbleTools Core in dev mode"
    log_info "  ./install.sh -f values-dev.yaml -n nimbletools-dev"
    log_info ""
    log_info "  # Build and push development images"
    log_info "  ./scripts/build-dev.sh"
    log_info ""
    log_info "  # Run tests"
    log_info "  source venv/bin/activate && pytest"
    log_info ""
    log_info "  # View cluster status"
    log_info "  kubectl get pods -n nimbletools-dev"
    log_info ""
    log_info "  # Access API (after installation)"
    log_info "  curl http://api.nimbletools.local:8080/health"
    log_info ""
    log_info "Cluster endpoints:"
    log_info "  - API: http://api.nimbletools.local:8080"
    log_info "  - Kubernetes API: https://0.0.0.0:6550"
    log_info ""
    log_info "To tear down:"
    log_info "  k3d cluster delete $CLUSTER_NAME"
    log_info "  docker stop nimbletools-registry && docker rm nimbletools-registry"
    log_info ""
}

# Main execution
main() {
    # Parse arguments
    parse_args "$@"
    
    # Show banner
    cat << 'EOF'
    _   _ _           _     _     _____           _     
   | \ | (_)_ __ ___ | |__ | | __|_   _|__   ___ | |___ 
   |  \| | | '_ ` _ \| '_ \| |/ _ \| |/ _ \ / _ \| / __|
   | |\  | | | | | | | |_) | |  __/| | (_) | (_) | \__ \
   |_| \_|_|_| |_| |_|_.__/|_|\___||_|\___/ \___/|_|___/
                                                       
   Development Environment Setup
   
EOF
    
    # Execute setup steps
    check_prerequisites
    setup_registry
    create_cluster
    setup_python_env
    build_dev_images
    create_dev_values
    setup_hosts
    show_dev_info
}

# Run main function with all arguments
main "$@"