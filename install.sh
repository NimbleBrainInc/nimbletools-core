#!/bin/bash

# NimbleTools Core Installation Script
# Deploys the complete MCP service runtime to Kubernetes in under 60 seconds

set -euo pipefail

# Configuration
CHART_PATH="./chart"
CHART_REPO="oci://ghcr.io/nimblebraininc/charts"
CHART_NAME="nimbletools-core"
RELEASE_NAME="nimbletools-core"
NAMESPACE="nimbletools-system"
TIMEOUT="300s"
K3D_CLUSTER_NAME="nimbletools-quickstart"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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
NimbleTools Core Installation Script

USAGE:
    ./install.sh [OPTIONS]

OPTIONS:
    -n, --namespace NAMESPACE    Install in specific namespace (default: nimbletools-system)
    -r, --release RELEASE        Helm release name (default: nimbletools-core)
    -f, --values FILE           Additional values file
    --api-enabled               Enable API server (default: true)
    --ingress-enabled           Enable ingress (default: false)
    --monitoring-enabled        Enable monitoring (default: true)
    --domain DOMAIN             Base domain (default: nimbletools.dev)
    --local                     Build and use local images (for development with k3d)
    --k3d-cluster NAME          K3d cluster name (default: nimbletools-quickstart)
    --dry-run                   Show what would be installed without executing
    -h, --help                  Show this help message

EXAMPLES:
    # Basic installation
    ./install.sh

    # Install with custom domain and ingress
    ./install.sh --domain example.com --ingress-enabled

    # Install with custom provider configuration
    ./install.sh -f custom-values.yaml

    # Local development with k3d
    ./install.sh --local --domain nimbletools.dev

    # Dry run to see what will be installed
    ./install.sh --dry-run

REQUIREMENTS:
    - kubectl configured with cluster access OR
    - k3d installed (for automatic cluster creation)
    - Helm 3.0+ installed
    - Kubernetes cluster 1.20+ (or k3d will create one)

REMOTE INSTALLATION:
    # Install directly from GitHub (creates cluster if needed)
    curl -sSL https://raw.githubusercontent.com/NimbleBrainInc/nimbletools-core/refs/heads/main/install.sh | bash

For more information, visit: https://github.com/NimbleBrainInc/nimbletools-core
EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -n|--namespace)
                NAMESPACE="$2"
                shift 2
                ;;
            -r|--release)
                RELEASE_NAME="$2"
                shift 2
                ;;
            -f|--values)
                EXTRA_VALUES_FILE="$2"
                shift 2
                ;;
            --api-enabled)
                API_ENABLED="true"
                shift
                ;;
            --ingress-enabled)
                INGRESS_ENABLED="true"
                shift
                ;;
            --monitoring-enabled)
                MONITORING_ENABLED="true"
                shift
                ;;
            --domain)
                DOMAIN="$2"
                shift 2
                ;;
            --local)
                LOCAL_IMAGES="true"
                shift
                ;;
            --k3d-cluster)
                K3D_CLUSTER_NAME="$2"
                shift 2
                ;;
            --dry-run)
                DRY_RUN="true"
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

# Set up local k3d cluster
setup_local_cluster() {
    # Check if k3d is available
    if ! command -v k3d &> /dev/null; then
        log_error "k3d not found. Please install k3d or provide an existing Kubernetes cluster."
        log_error ""
        log_error "Install k3d:"
        log_error "  curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash"
        log_error ""
        log_error "Or connect to an existing cluster and run this script again."
        exit 1
    fi
    
    local cluster_name="${K3D_CLUSTER_NAME}"
    
    log_info "Creating local Kubernetes cluster with k3d..."
    log_info "Cluster name: $cluster_name"
    
    # Create cluster with port mapping for ingress
    if k3d cluster create "$cluster_name" \
        --port "80:80@loadbalancer" \
        --port "443:443@loadbalancer" \
        --k3s-arg "--disable=traefik@server:0" \
        --wait; then
        
        log_success "Local cluster '$cluster_name' created successfully!"
        
        # Note: We don't set LOCAL_IMAGES=true here because when installing remotely,
        # we want to use published Docker Hub images, not try to build local ones
        
        log_info ""
        log_warning "📝 For direct domain access, add to your /etc/hosts:"
        log_info "   127.0.0.1 api.nimbletools.dev mcp.nimbletools.dev"
        log_info ""
        
    else
        log_error "Failed to create local cluster"
        log_error "Please check your Docker installation and try again"
        exit 1
    fi
}

# Determine chart source (local development or published chart)
get_chart_source() {
    if [[ -f "$CHART_PATH/Chart.yaml" ]]; then
        # Local development - use local chart
        echo "local"
    else
        # Production - use published chart
        echo "remote"
    fi
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Please install kubectl."
        exit 1
    fi
    
    # Check Helm
    if ! command -v helm &> /dev/null; then
        log_error "Helm not found. Please install Helm 3.0+."
        exit 1
    fi
    
    
    # Check Helm version
    HELM_VERSION=$(helm version --short | cut -d'"' -f2 | cut -d'v' -f2)
    if [[ $(echo "$HELM_VERSION 3.0.0" | tr ' ' '\n' | sort -V | head -n1) != "3.0.0" ]]; then
        log_error "Helm version 3.0+ required. Found: v$HELM_VERSION"
        exit 1
    fi
    
    # Check cluster access
    if ! kubectl cluster-info &> /dev/null; then
        log_warning "No Kubernetes cluster found. Setting up local cluster with k3d..."
        setup_local_cluster
    fi
    
    # Check chart availability
    local chart_source=$(get_chart_source)
    if [[ "$chart_source" == "local" ]]; then
        log_info "Using local chart for development"
    else
        log_info "Using published chart from registry"
    fi
    
    log_success "Prerequisites check passed"
}

# Create namespace if it doesn't exist
create_namespace() {
    log_info "Ensuring namespace '$NAMESPACE' exists..."
    
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_info "Namespace '$NAMESPACE' already exists"
    else
        if [[ "${DRY_RUN:-false}" == "true" ]]; then
            log_info "[DRY RUN] Would create namespace: $NAMESPACE"
        else
            kubectl create namespace "$NAMESPACE"
            log_success "Created namespace: $NAMESPACE"
        fi
    fi
}

# Build Helm command with dynamic values
build_helm_command() {
    local cmd="helm"
    
    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        cmd="$cmd upgrade --install --dry-run"
    else
        cmd="$cmd upgrade --install"
    fi
    
    # Determine chart source
    local chart_source=$(get_chart_source)
    if [[ "$chart_source" == "local" ]]; then
        cmd="$cmd $RELEASE_NAME $CHART_PATH"
    else
        cmd="$cmd $RELEASE_NAME $CHART_REPO/$CHART_NAME"
    fi
    cmd="$cmd --namespace $NAMESPACE"
    cmd="$cmd --create-namespace"
    cmd="$cmd --timeout $TIMEOUT"
    cmd="$cmd --wait"
    
    # Add dynamic values
    if [[ -n "${DOMAIN:-}" ]]; then
        cmd="$cmd --set global.domain=$DOMAIN"
    fi
    
    if [[ -n "${API_ENABLED:-}" ]]; then
        cmd="$cmd --set controlPlane.enabled=$API_ENABLED"
    fi
    
    if [[ -n "${INGRESS_ENABLED:-}" ]]; then
        cmd="$cmd --set ingress.enabled=$INGRESS_ENABLED"
    fi
    
    if [[ -n "${MONITORING_ENABLED:-}" ]]; then
        cmd="$cmd --set monitoring.enabled=$MONITORING_ENABLED"
    fi
    
    # Configure local images if requested
    if [[ "${LOCAL_IMAGES:-false}" == "true" ]]; then
        cmd="$cmd --set global.imageRegistry="
        cmd="$cmd --set operator.image.pullPolicy=Never"
        cmd="$cmd --set controlPlane.image.pullPolicy=Never"
        cmd="$cmd --set rbacController.image.pullPolicy=Never"
        cmd="$cmd --set workspaceAuth.image.pullPolicy=Never"
    fi
    
    # Add extra values file if specified
    if [[ -n "${EXTRA_VALUES_FILE:-}" ]]; then
        if [[ -f "$EXTRA_VALUES_FILE" ]]; then
            cmd="$cmd -f $EXTRA_VALUES_FILE"
        else
            log_error "Values file not found: $EXTRA_VALUES_FILE"
            exit 1
        fi
    fi
    
    echo "$cmd"
}

# Build and import local images for k3d development
build_local_images() {
    log_info "Building and importing local images for k3d..."
    
    # Check if k3d cluster exists, create if not
    if ! k3d cluster list | grep -q "^${K3D_CLUSTER_NAME}"; then
        log_warning "k3d cluster '${K3D_CLUSTER_NAME}' not found. Creating it..."
        setup_local_cluster
    fi
    
    # Check if build script exists
    if [[ ! -f "./scripts/build-images.sh" ]]; then
        log_error "Build script not found: ./scripts/build-images.sh"
        log_error "Please ensure you're running from the project root directory"
        exit 1
    fi
    
    # Run the build script with --local flag and cluster name
    if ./scripts/build-images.sh --local --k3d-cluster "${K3D_CLUSTER_NAME}"; then
        log_success "Local images built and imported successfully"
    else
        log_error "Failed to build local images"
        exit 1
    fi
}

# Install NimbleTools Core
install_nimbletools() {
    local start_time=$(date +%s)
    
    log_info "Installing NimbleTools Core..."
    log_info "Release: $RELEASE_NAME"
    log_info "Namespace: $NAMESPACE"
    
    # Show chart source
    local chart_source=$(get_chart_source)
    if [[ "$chart_source" == "local" ]]; then
        log_info "Chart: $CHART_PATH (local development)"
    else
        log_info "Chart: $CHART_REPO/$CHART_NAME (published)"
    fi
    
    # Build local images if requested
    if [[ "${LOCAL_IMAGES:-false}" == "true" ]]; then
        log_info "Using local images (development mode)"
        build_local_images
    fi
    
    # Build and execute Helm command
    local helm_cmd
    helm_cmd=$(build_helm_command)
    
    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        log_info "Dry run - Helm command that would be executed:"
        echo "  $helm_cmd"
        return 0
    fi
    
    log_info "Executing: $helm_cmd"
    
    if eval "$helm_cmd"; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        log_success "NimbleTools Core installed successfully in ${duration}s!"
    else
        log_error "Installation failed"
        exit 1
    fi
}

# Verify installation
verify_installation() {
    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        log_info "[DRY RUN] Would verify installation"
        return 0
    fi
    
    log_info "Verifying installation..."
    
    # Check Helm release
    if helm status "$RELEASE_NAME" -n "$NAMESPACE" &> /dev/null; then
        log_success "Helm release '$RELEASE_NAME' is deployed"
    else
        log_error "Helm release '$RELEASE_NAME' not found"
        return 1
    fi
    
    # Check operator deployment
    if kubectl get deployment "${RELEASE_NAME}-operator" -n "$NAMESPACE" &> /dev/null; then
        log_success "MCP Operator deployment found"
        
        # Wait for operator to be ready
        log_info "Waiting for operator to be ready..."
        kubectl wait --for=condition=available --timeout=120s deployment/"${RELEASE_NAME}-operator" -n "$NAMESPACE"
        log_success "MCP Operator is ready"
    else
        log_warning "MCP Operator deployment not found"
    fi
    
    # Check Control Plane deployment if enabled
    if kubectl get deployment "${RELEASE_NAME}-control-plane" -n "$NAMESPACE" &> /dev/null; then
        log_success "Control Plane deployment found"

        # Wait for Control Plane to be ready
        log_info "Waiting for Control Plane to be ready..."
        kubectl wait --for=condition=available --timeout=120s deployment/"${RELEASE_NAME}-control-plane" -n "$NAMESPACE"
        log_success "Control Plane is ready"
    else
        log_info "Control Plane not enabled or not found"
    fi

    # Check CRD
    if kubectl get crd mcpservices.mcp.nimbletools.dev &> /dev/null; then
        log_success "MCPService CRD is installed"
    else
        log_warning "MCPService CRD not found"
    fi
}

# Show post-installation information
show_post_install_info() {
    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        return 0
    fi
    
    log_success ""
    log_success "🎉 NimbleTools Core installation complete!"
    log_success ""
    log_info "Dual endpoints are now configured:"
    log_success "  📊 API Management: http://api.nimbletools.dev"
    log_success "  🔗 MCP Runtime:    http://mcp.nimbletools.dev"
    log_info ""
    log_warning "⚠️  IMPORTANT: Authentication Configuration"
    log_info "   The control-plane uses the community provider by default (no authentication)."
    log_info "   For production, configure authentication via PROVIDER_CONFIG environment variable."
    log_info ""
    log_warning "⚠️  Add these entries to your /etc/hosts for direct domain access:"
    log_info "   127.0.0.1 api.nimbletools.dev"
    log_info "   127.0.0.1 mcp.nimbletools.dev"
    log_info ""
    log_info "Next steps:"
    log_info "1. Verify the installation:"
    log_info "   kubectl get pods -n $NAMESPACE"
    log_info ""
    log_info "2. Test the API endpoint (direct domain access):"
    log_info "   curl http://api.nimbletools.dev/health"
    log_info ""
    log_info "3. Test the MCP endpoint:"
    log_info "   curl http://mcp.nimbletools.dev/health"
    log_info ""
    log_info "4. Create your first workspace:"
    log_info "   curl -X POST http://api.nimbletools.dev/v1/workspaces -H 'Content-Type: application/json' -d '{\"name\":\"test\"}'"
    log_info ""
    log_info "5. Deploy an MCP service:"
    log_info "   kubectl apply -f examples/echo-mcp.yaml"
    log_info ""
    log_info "6. View logs:"
    log_info "   kubectl logs -l app.kubernetes.io/component=operator -n $NAMESPACE"
    log_info ""
    log_info "For documentation and examples:"
    log_info "   https://github.com/NimbleBrainInc/nimbletools-core"
    log_info ""
}

# Main execution
main() {
    # Set default values for dual endpoint setup
    API_ENABLED="true"
    INGRESS_ENABLED="true"  # Enable ingress by default for dual endpoints
    MONITORING_ENABLED="true"
    DOMAIN="nimbletools.dev"  # Use local domain for development
    DRY_RUN="false"
    
    # Parse arguments
    parse_args "$@"
    
    # Show banner
    cat << 'EOF'
    _   _ _           _     _     _____           _     
   | \ | (_)_ __ ___ | |__ | | __|_   _|__   ___ | |___ 
   |  \| | | '_ ` _ \| '_ \| |/ _ \| |/ _ \ / _ \| / __|
   | |\  | | | | | | | |_) | |  __/| | (_) | (_) | \__ \
   |_| \_|_|_| |_| |_|_.__/|_|\___||_|\___/ \___/|_|___/
                                                       
   Core MCP Service Runtime for Kubernetes
   
EOF
    
    # Execute installation steps
    check_prerequisites
    create_namespace
    install_nimbletools
    verify_installation
    show_post_install_info
}

# Run main function with all arguments
main "$@"