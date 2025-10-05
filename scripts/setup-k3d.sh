#!/bin/bash

# Setup k3d cluster for local development
set -euo pipefail

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

CLUSTER_NAME="${CLUSTER_NAME:-nimbletools-quickstart}"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

main() {
    log_info "Setting up k3d cluster for NimbleTools Core..."
    log_info "Cluster name: $CLUSTER_NAME"
    
    # Check if cluster exists
    if k3d cluster list | grep -q "$CLUSTER_NAME"; then
        log_warning "Cluster '$CLUSTER_NAME' already exists. Deleting..."
        k3d cluster delete "$CLUSTER_NAME"
    fi
    
    # Create cluster with port mapping and disable traefik (we use nginx-ingress instead)
    log_info "Creating k3d cluster with nginx-ingress for direct domain access..."
    
    # Create cluster with port mapping and disable traefik (we use nginx-ingress instead)
    # Add memory allocation to prevent OOMKilled issues with ingress controller
    k3d cluster create "$CLUSTER_NAME" \
        --port "80:80@loadbalancer" \
        --port "443:443@loadbalancer" \
        --k3s-arg "--disable=traefik@server:0" \
        --k3s-arg "--kubelet-arg=max-pods=110@server:*" \
        --servers 1 \
        --agents 1 \
        --servers-memory 2g \
        --agents-memory 2g \
        --wait
    
    log_success "k3d cluster '$CLUSTER_NAME' created successfully!"
    log_info ""
    log_info "Next steps:"
    log_info "1. Add to /etc/hosts:"
    log_info "   127.0.0.1 api.nimbletools.local"
    log_info "   127.0.0.1 mcp.nimbletools.local"
    log_info ""
    log_info "2. Build and install NimbleTools Core:"
    log_info "   ./scripts/build-images.sh --local && ./install.sh --local"
    log_info ""
    log_info "3. Test direct access:"
    log_info "   curl http://api.nimbletools.local/health"
}

main "$@"