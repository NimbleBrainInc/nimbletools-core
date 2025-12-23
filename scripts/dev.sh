#!/bin/bash
set -e

# dev.sh - Unified development workflow for nimbletools-core
# Designed for solo developer workflow with TDD focus
#
# Usage:
#   ./scripts/dev.sh verify      # Run all tests (format, lint, type-check, unit tests, helm tests)
#   ./scripts/dev.sh build       # Build all images for local k3d
#   ./scripts/dev.sh deploy      # Deploy to local k3d cluster
#   ./scripts/dev.sh all         # verify + build + deploy + smoke test
#   ./scripts/dev.sh smoke       # Run end-to-end smoke tests
#   ./scripts/dev.sh quick       # Build and deploy (skip tests)
#   ./scripts/dev.sh status      # Show environment status
#   ./scripts/dev.sh bump <ver>  # Bump version (e.g., ./scripts/dev.sh bump 0.3.0)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Load version
VERSION=$(cat "$CORE_ROOT/VERSION" 2>/dev/null | tr -d '\n' || echo "dev")

# Defaults (k3d adds "k3d-" prefix to kubectl context automatically)
K3D_CLUSTER="${K3D_CLUSTER:-nimbletools-quickstart}"
NAMESPACE="${NAMESPACE:-nimbletools-system}"
RELEASE="${RELEASE:-nimbletools-core}"

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "\n${BLUE}==>${NC} $1"; }

cd "$CORE_ROOT"

# Run all verification (TDD)
verify() {
    log_step "Running full verification suite"

    log_info "Running code verification for all components..."
    make verify-code

    log_info "Running Helm chart tests..."
    make verify-chart

    log_success "All verification passed"
}

# Ensure k3d cluster exists
ensure_cluster() {
    log_info "Checking k3d cluster '$K3D_CLUSTER'..."

    if k3d cluster list 2>/dev/null | grep -q "^$K3D_CLUSTER "; then
        log_success "Cluster '$K3D_CLUSTER' exists"
        return 0
    fi

    log_warn "Cluster '$K3D_CLUSTER' not found, creating..."
    k3d cluster create "$K3D_CLUSTER" \
        --port "80:80@loadbalancer" \
        --port "443:443@loadbalancer" \
        --k3s-arg "--disable=traefik@server:0" \
        --wait

    # Brief delay for k3d to fully register the cluster
    sleep 2

    log_success "Cluster '$K3D_CLUSTER' created"
}

# Build images for local k3d
build() {
    log_step "Building images for local k3d (tag: $VERSION)"

    # Ensure cluster exists first
    ensure_cluster

    # Build and import images
    ./scripts/build-images.sh --local --k3d-cluster "$K3D_CLUSTER" --tag "$VERSION"

    log_success "Images built and imported to k3d"
}

# Deploy to k3d
deploy() {
    log_step "Deploying to k3d cluster '$K3D_CLUSTER'"

    # Ensure using right context
    kubectl config use-context "k3d-$K3D_CLUSTER" 2>/dev/null || true

    # Build helm dependencies
    log_info "Building Helm dependencies..."
    helm dependency build chart/ 2>/dev/null || true

    # Deploy
    log_info "Installing/upgrading Helm release..."
    helm upgrade --install "$RELEASE" ./chart \
        --namespace "$NAMESPACE" \
        --create-namespace \
        --set global.imageRegistry="" \
        --set operator.image.pullPolicy=Never \
        --set controlPlane.image.pullPolicy=Never \
        --set rbacController.image.pullPolicy=Never \
        --set universalAdapter.image.pullPolicy=Never \
        --wait --timeout 180s

    log_success "Deployed to k3d"

    # Show pods
    log_info "Pods:"
    kubectl get pods -n "$NAMESPACE" -l "app.kubernetes.io/instance=$RELEASE" 2>/dev/null || true
}

# Run smoke tests
smoke_test() {
    log_step "Running end-to-end smoke tests"

    # Wait for pods to be ready
    log_info "Waiting for control-plane to be ready..."
    kubectl wait --for=condition=ready pod \
        -l "app.kubernetes.io/component=control-plane" \
        -n "$NAMESPACE" \
        --timeout=60s 2>/dev/null || {
            log_warn "Control plane not ready, checking status..."
            kubectl get pods -n "$NAMESPACE"
        }

    # Port forward for testing
    log_info "Setting up port-forward..."
    kubectl port-forward -n "$NAMESPACE" svc/${RELEASE}-control-plane 8080:8080 &
    PF_PID=$!
    sleep 2

    # Cleanup on exit
    cleanup() {
        kill $PF_PID 2>/dev/null || true
    }
    trap cleanup EXIT

    # Test health endpoint
    log_info "Testing health endpoint..."
    if curl -sf http://localhost:8080/health > /dev/null; then
        log_success "Health check passed"
    else
        log_error "Health check failed"
        cleanup
        exit 1
    fi

    # Test API endpoints
    log_info "Testing API endpoints..."

    # List workspaces (should return empty or list)
    if curl -sf http://localhost:8080/v1/workspaces > /dev/null; then
        log_success "GET /v1/workspaces passed"
    else
        log_warn "GET /v1/workspaces returned non-200 (may require auth)"
    fi

    # Test OpenAPI spec
    if curl -sf http://localhost:8080/openapi.json > /dev/null; then
        log_success "OpenAPI spec available"
    else
        log_warn "OpenAPI spec not available"
    fi

    # Test operator is running
    log_info "Checking operator..."
    if kubectl get pods -n "$NAMESPACE" -l "app.kubernetes.io/component=operator" --field-selector=status.phase=Running | grep -q "Running"; then
        log_success "Operator is running"
    else
        log_warn "Operator may not be running"
    fi

    # Test CRD is installed
    log_info "Checking CRD..."
    if kubectl get crd mcpservices.mcp.nimbletools.dev &>/dev/null; then
        log_success "MCPService CRD installed"
    else
        log_error "MCPService CRD not found"
    fi

    cleanup
    log_success "Smoke tests completed"
}

# Full development cycle
dev_cycle() {
    log_step "Full development cycle: verify -> build -> deploy -> smoke test"

    local start_time=$(date +%s)

    verify
    build
    deploy
    smoke_test

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    echo ""
    log_success "Development cycle complete in ${duration}s"
    echo ""
    log_info "Version: $VERSION"
    log_info "Cluster: k3d-$K3D_CLUSTER"
    log_info "Namespace: $NAMESPACE"
}

# Quick rebuild (skip tests)
quick() {
    log_step "Quick rebuild (skipping tests)"
    build
    deploy
    log_success "Quick deploy complete"
}

# Show status
status() {
    log_step "Development environment status"

    echo ""
    log_info "Version: $VERSION"
    echo ""

    log_info "Docker images:"
    docker images | grep nimbletools | head -10 || echo "  No nimbletools images found"

    echo ""
    log_info "K3d clusters:"
    k3d cluster list 2>/dev/null || echo "  k3d not available"

    if k3d cluster list 2>/dev/null | grep -q "$K3D_CLUSTER"; then
        echo ""
        log_info "Pods in $NAMESPACE:"
        kubectl config use-context "k3d-$K3D_CLUSTER" 2>/dev/null || true
        kubectl get pods -n "$NAMESPACE" 2>/dev/null || echo "  Unable to get pods"

        echo ""
        log_info "Services:"
        kubectl get svc -n "$NAMESPACE" 2>/dev/null || echo "  Unable to get services"
    fi
}

# Bump version
bump_version() {
    local new_version="$1"
    if [ -z "$new_version" ]; then
        log_error "Version required. Usage: ./scripts/dev.sh bump 0.3.0"
        exit 1
    fi

    log_step "Bumping version to $new_version"

    # Update VERSION file
    echo "$new_version" > "$CORE_ROOT/VERSION"

    # Run update script to sync all files
    make update-version

    log_success "Version bumped to $new_version"
    log_info "Files updated:"
    log_info "  - VERSION"
    log_info "  - chart/Chart.yaml"
    log_info "  - chart/values.yaml"
    log_info "  - scripts/build-images.sh"
    log_info "  - Makefile"
    echo ""
    log_info "Next steps:"
    log_info "  1. Run: ./scripts/dev.sh all  (verify everything works)"
    log_info "  2. Commit the changes"
    log_info "  3. In enterprise: make dev-sync && make dev"
}

# Show help
show_help() {
    echo "NimbleTools Core Development Workflow"
    echo "======================================"
    echo ""
    echo "Usage: $0 <command> [args]"
    echo ""
    echo "Commands:"
    echo "  verify       Run all tests (TDD first)"
    echo "  build        Build images for local k3d"
    echo "  deploy       Deploy to local k3d cluster"
    echo "  all          Full cycle: verify -> build -> deploy -> smoke"
    echo "  smoke        Run end-to-end smoke tests"
    echo "  quick        Quick rebuild (skip tests)"
    echo "  status       Show development environment status"
    echo "  bump <ver>   Bump version (e.g., bump 0.3.0)"
    echo ""
    echo "Environment variables:"
    echo "  K3D_CLUSTER  K3d cluster name (default: nimbletools-quickstart)"
    echo "  NAMESPACE    Kubernetes namespace (default: nimbletools-system)"
    echo "  RELEASE      Helm release name (default: nimbletools-core)"
    echo ""
    echo "Examples:"
    echo "  $0 all              # Full development cycle"
    echo "  $0 quick            # Fast iteration"
    echo "  $0 bump 0.3.0       # Bump to new version"
    echo "  $0 verify && $0 build  # Test then build"
}

# Main
case "${1:-help}" in
    verify|test)
        verify
        ;;
    build)
        build
        ;;
    deploy)
        deploy
        ;;
    all|cycle)
        dev_cycle
        ;;
    smoke)
        smoke_test
        ;;
    quick)
        quick
        ;;
    status)
        status
        ;;
    bump)
        bump_version "$2"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
