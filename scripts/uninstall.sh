#!/bin/bash

# NimbleTools Core Uninstallation Script
# Removes NimbleTools Core from Kubernetes cluster

set -euo pipefail

# Configuration
RELEASE_NAME="nimbletools-core"
NAMESPACE="nimbletools-system"

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
NimbleTools Core Uninstallation Script

USAGE:
    ./scripts/uninstall.sh [OPTIONS]

OPTIONS:
    -n, --namespace NAMESPACE    Namespace to uninstall from (default: nimbletools-system)
    -r, --release RELEASE        Helm release name (default: nimbletools-core)
    --remove-crd                 Remove MCPService CRD (WARNING: deletes all MCP services)
    --remove-namespace           Remove the namespace after uninstall
    --force                      Force removal without confirmation
    --dry-run                    Show what would be removed without executing
    -h, --help                   Show this help message

EXAMPLES:
    # Basic uninstallation
    ./scripts/uninstall.sh

    # Uninstall and remove CRD and namespace
    ./scripts/uninstall.sh --remove-crd --remove-namespace

    # Force uninstall without confirmation
    ./scripts/uninstall.sh --force

    # Dry run to see what would be removed
    ./scripts/uninstall.sh --dry-run

WARNING:
    --remove-crd will delete ALL MCPService resources across ALL namespaces!
    Use with caution in shared clusters.

EOF
}

# Parse command line arguments
parse_args() {
    REMOVE_CRD="false"
    REMOVE_NAMESPACE="false"
    FORCE="false"
    DRY_RUN="false"
    
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
            --remove-crd)
                REMOVE_CRD="true"
                shift
                ;;
            --remove-namespace)
                REMOVE_NAMESPACE="true"
                shift
                ;;
            --force)
                FORCE="true"
                shift
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
    
    # Check cluster access
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster. Please check your kubeconfig."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Confirm uninstallation
confirm_uninstall() {
    if [[ "$FORCE" == "true" ]] || [[ "$DRY_RUN" == "true" ]]; then
        return 0
    fi
    
    log_warning ""
    log_warning "This will uninstall NimbleTools Core from your cluster:"
    log_warning "  Release: $RELEASE_NAME"
    log_warning "  Namespace: $NAMESPACE"
    
    if [[ "$REMOVE_CRD" == "true" ]]; then
        log_warning "  ⚠️  Will remove MCPService CRD (deletes ALL MCP services)"
    fi
    
    if [[ "$REMOVE_NAMESPACE" == "true" ]]; then
        log_warning "  ⚠️  Will remove namespace '$NAMESPACE'"
    fi
    
    log_warning ""
    read -p "Are you sure you want to continue? [y/N]: " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Uninstallation cancelled"
        exit 0
    fi
}

# List MCP services that will be affected
list_mcp_services() {
    if [[ "$DRY_RUN" != "true" ]] && [[ "$REMOVE_CRD" == "true" ]]; then
        log_info "Checking for existing MCP services..."
        
        local mcp_services
        if mcp_services=$(kubectl get mcpservices --all-namespaces --no-headers 2>/dev/null); then
            if [[ -n "$mcp_services" ]]; then
                log_warning "Found MCP services that will be deleted:"
                echo "$mcp_services" | while read -r line; do
                    log_warning "  $line"
                done
                log_warning ""
            fi
        fi
    fi
}

# Uninstall Helm release
uninstall_helm_release() {
    log_info "Uninstalling Helm release '$RELEASE_NAME'..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would uninstall Helm release: $RELEASE_NAME"
        return 0
    fi
    
    # Check if release exists
    if ! helm status "$RELEASE_NAME" -n "$NAMESPACE" &> /dev/null; then
        log_warning "Helm release '$RELEASE_NAME' not found in namespace '$NAMESPACE'"
        return 0
    fi
    
    # Uninstall release
    if helm uninstall "$RELEASE_NAME" -n "$NAMESPACE"; then
        log_success "Uninstalled Helm release '$RELEASE_NAME'"
    else
        log_error "Failed to uninstall Helm release '$RELEASE_NAME'"
        return 1
    fi
}

# Remove MCPService CRD
remove_crd() {
    if [[ "$REMOVE_CRD" != "true" ]]; then
        return 0
    fi
    
    log_info "Removing MCPService CRD..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would remove CRD: mcpservices.mcp.nimbletools.dev"
        return 0
    fi
    
    # Check if CRD exists
    if ! kubectl get crd mcpservices.mcp.nimbletools.dev &> /dev/null; then
        log_warning "MCPService CRD not found"
        return 0
    fi
    
    # Remove CRD (this will also remove all MCPService resources)
    if kubectl delete crd mcpservices.mcp.nimbletools.dev; then
        log_success "Removed MCPService CRD"
    else
        log_error "Failed to remove MCPService CRD"
        return 1
    fi
}

# Remove namespace
remove_namespace() {
    if [[ "$REMOVE_NAMESPACE" != "true" ]]; then
        return 0
    fi
    
    log_info "Removing namespace '$NAMESPACE'..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would remove namespace: $NAMESPACE"
        return 0
    fi
    
    # Check if namespace exists
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_warning "Namespace '$NAMESPACE' not found"
        return 0
    fi
    
    # Remove namespace
    if kubectl delete namespace "$NAMESPACE"; then
        log_success "Removed namespace '$NAMESPACE'"
    else
        log_error "Failed to remove namespace '$NAMESPACE'"
        return 1
    fi
}

# Clean up any remaining resources
cleanup_resources() {
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would clean up remaining resources"
        return 0
    fi
    
    log_info "Cleaning up any remaining resources..."
    
    # Remove any finalizers that might prevent deletion
    local resources_to_clean=(
        "mcpservices.mcp.nimbletools.dev"
    )
    
    for resource in "${resources_to_clean[@]}"; do
        local remaining_resources
        if remaining_resources=$(kubectl get "$resource" --all-namespaces --no-headers 2>/dev/null); then
            if [[ -n "$remaining_resources" ]]; then
                log_info "Removing finalizers from $resource..."
                kubectl patch "$resource" --all-namespaces --type='merge' -p='{"metadata":{"finalizers":[]}}' 2>/dev/null || true
            fi
        fi
    done
}

# Verify uninstallation
verify_uninstall() {
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would verify uninstallation"
        return 0
    fi
    
    log_info "Verifying uninstallation..."
    
    # Check Helm release
    if helm status "$RELEASE_NAME" -n "$NAMESPACE" &> /dev/null; then
        log_warning "Helm release '$RELEASE_NAME' still exists"
    else
        log_success "Helm release '$RELEASE_NAME' removed"
    fi
    
    # Check CRD if removal was requested
    if [[ "$REMOVE_CRD" == "true" ]]; then
        if kubectl get crd mcpservices.mcp.nimbletools.dev &> /dev/null; then
            log_warning "MCPService CRD still exists"
        else
            log_success "MCPService CRD removed"
        fi
    fi
    
    # Check namespace if removal was requested
    if [[ "$REMOVE_NAMESPACE" == "true" ]]; then
        if kubectl get namespace "$NAMESPACE" &> /dev/null; then
            log_warning "Namespace '$NAMESPACE' still exists"
        else
            log_success "Namespace '$NAMESPACE' removed"
        fi
    fi
}

# Show post-uninstall information
show_post_uninstall_info() {
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info ""
        log_info "This was a dry run - no changes were made"
        return 0
    fi
    
    log_success ""
    log_success "🗑️  NimbleTools Core uninstallation complete!"
    log_success ""
    
    if [[ "$REMOVE_CRD" != "true" ]]; then
        log_info "Note: MCPService CRD was preserved"
        log_info "To remove it later: kubectl delete crd mcpservices.mcp.nimbletools.dev"
        log_info ""
    fi
    
    if [[ "$REMOVE_NAMESPACE" != "true" ]]; then
        log_info "Note: Namespace '$NAMESPACE' was preserved"
        log_info "To remove it later: kubectl delete namespace $NAMESPACE"
        log_info ""
    fi
    
    log_info "To reinstall NimbleTools Core:"
    log_info "  ./install.sh"
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
                                                       
   Core MCP Service Runtime - Uninstaller
   
EOF
    
    # Execute uninstallation steps
    check_prerequisites
    list_mcp_services
    confirm_uninstall
    uninstall_helm_release
    remove_crd
    cleanup_resources
    remove_namespace
    verify_uninstall
    show_post_uninstall_info
}

# Run main function with all arguments
main "$@"