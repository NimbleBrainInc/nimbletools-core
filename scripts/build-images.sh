#!/bin/bash

# Unified build script for NimbleTools Core images
# Supports local k3d, local registry, and Docker Hub with multi-platform builds

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
DEFAULT_TAG=$(cat VERSION 2>/dev/null || echo "0.1.0")
TAG="${DEFAULT_TAG}"
REGISTRY=""
NAMESPACE="nimbletools"
PLATFORMS="linux/amd64,linux/arm64"
PUSH="false"
LOCAL_REGISTRY_PORT="5000"
K3D_CLUSTER=""
DRY_RUN="false"
NO_LATEST="false"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Show help
show_help() {
    cat << EOF
Unified Build Script for NimbleTools Core Images

USAGE:
    ./scripts/build-images.sh [OPTIONS]

OPTIONS:
    --tag TAG               Image tag (default: $DEFAULT_TAG from chart)
    --registry REGISTRY     Registry to push to (docker.io, localhost:5000, etc.)
    --namespace NAMESPACE   Registry namespace (default: nimbletools)
    --platforms PLATFORMS   Build platforms (default: linux/amd64,linux/arm64)
    --local                 Build for local k3d cluster (no registry, imports directly)
    --k3d-cluster NAME      K3d cluster name for local builds (default: nimbletools-dev)
    --dev                   Build for local registry (localhost:5000)
    --production            Build and push to Docker Hub (docker.io/nimbletools)
    --push                  Push to registry (implied by --production and --dev)
    --no-latest             Don't update the :latest tag (for dev builds)
    --dry-run               Show what would be built without executing
    -h, --help              Show this help

EXAMPLES:
    # Local development - build and import to k3d
    ./scripts/build-images.sh --local

    # Local development - specific k3d cluster
    ./scripts/build-images.sh --local --k3d-cluster my-cluster

    # Development registry
    ./scripts/build-images.sh --dev

    # Production - build and push to Docker Hub
    ./scripts/build-images.sh --production

    # Custom registry
    ./scripts/build-images.sh --registry my-registry.com --namespace myteam --push

    # Single platform build
    ./scripts/build-images.sh --platforms linux/amd64 --production

    # Custom tag
    ./scripts/build-images.sh --tag 2.0.0-beta --production

MODES:
    --local      : Build single-platform images and import to k3d cluster
    --dev        : Build multi-platform images and push to localhost:5000 registry  
    --production : Build multi-platform images and push to Docker Hub
    Custom       : Build with your own registry/namespace settings

REQUIREMENTS:
    - Docker with buildx support
    - For --local: k3d cluster running
    - For --dev: local registry running on port 5000
    - For --production: docker login to Docker Hub with push access

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --tag)
                TAG="$2"
                shift 2
                ;;
            --registry)
                REGISTRY="$2"
                shift 2
                ;;
            --namespace)
                NAMESPACE="$2"
                shift 2
                ;;
            --platforms)
                PLATFORMS="$2"
                shift 2
                ;;
            --local)
                REGISTRY=""
                # Use native platform for local builds (detect ARM vs x86)
                if [[ "$(uname -m)" == "arm64" || "$(uname -m)" == "aarch64" ]]; then
                    PLATFORMS="linux/arm64"
                else
                    PLATFORMS="linux/amd64"
                fi
                PUSH="false"
                shift
                ;;
            --k3d-cluster)
                K3D_CLUSTER="$2"
                shift 2
                ;;
            --dev)
                REGISTRY="localhost:$LOCAL_REGISTRY_PORT"
                PUSH="true"
                shift
                ;;
            --production)
                REGISTRY="docker.io"
                PUSH="true"
                shift
                ;;
            --push)
                PUSH="true"
                shift
                ;;
            --dry-run)
                DRY_RUN="true"
                shift
                ;;
            --no-latest)
                NO_LATEST="true"
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
    
    # Set defaults based on mode
    if [[ -z "$K3D_CLUSTER" && "$REGISTRY" == "" ]]; then
        K3D_CLUSTER="nimbletools-quickstart"
    fi
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Please install Docker."
        exit 1
    fi
    
    # Check Docker daemon
    if ! docker info &> /dev/null; then
        log_error "Docker daemon not running. Please start Docker."
        exit 1
    fi
    
    # Check buildx support
    if ! docker buildx version &> /dev/null; then
        log_error "Docker buildx not available. Please update Docker or enable buildx."
        exit 1
    fi
    
    # Mode-specific checks
    if [[ "$REGISTRY" == "" && -n "$K3D_CLUSTER" ]]; then
        # Local k3d mode
        if ! command -v k3d &> /dev/null; then
            log_error "k3d not found. Please install k3d for local builds."
            exit 1
        fi

        # Retry cluster check a few times (handles race condition after creation)
        local retries=3
        local found=false
        for i in $(seq 1 $retries); do
            # Temporarily disable errexit for grep (returns 1 when no match)
            # Using command substitution to avoid pipefail issues
            set +e
            local cluster_list
            cluster_list=$(k3d cluster list 2>/dev/null)
            echo "$cluster_list" | grep -q "^$K3D_CLUSTER "
            local grep_result=$?
            set -e

            if [[ $grep_result -eq 0 ]]; then
                found=true
                break
            fi
            if [[ $i -lt $retries ]]; then
                log_info "Waiting for cluster '$K3D_CLUSTER' to be ready... (attempt $i/$retries)"
                sleep 2
            fi
        done

        if [[ "$found" != "true" ]]; then
            log_error "k3d cluster '$K3D_CLUSTER' not found."
            log_error "Create it with: k3d cluster create $K3D_CLUSTER --wait"
            exit 1
        fi
    elif [[ "$REGISTRY" == "localhost:$LOCAL_REGISTRY_PORT" ]]; then
        # Local registry mode
        if ! curl -s "http://localhost:$LOCAL_REGISTRY_PORT/v2/" > /dev/null; then
            log_error "Local registry not running on port $LOCAL_REGISTRY_PORT"
            log_error "Start it with: docker run -d -p $LOCAL_REGISTRY_PORT:5000 --name registry registry:2"
            exit 1
        fi
    elif [[ "$REGISTRY" == "docker.io" ]]; then
        # Docker Hub mode
        if ! docker system info | grep -q "Username:"; then
            log_warning "Not logged in to Docker Hub. Run: docker login"
        fi
    fi
    
    # Check chart file exists for tag detection
    if [[ ! -f "chart/Chart.yaml" ]]; then
        log_warning "chart/Chart.yaml not found. Using default tag: $TAG"
    fi
    
    log_success "Prerequisites check passed"
}

# Build and handle image
build_image() {
    local component=$1
    local dockerfile_path=$2
    
    log_info "Building $component..."
    
    local image_name="$NAMESPACE/$component"
    local base_tag="$image_name:$TAG"
    
    # Determine full image name
    local full_image_name
    if [[ -n "$REGISTRY" ]]; then
        full_image_name="$REGISTRY/$base_tag"
    else
        full_image_name="$base_tag"
    fi
    
    # Build command
    local build_cmd="docker buildx build"
    build_cmd="$build_cmd --platform $PLATFORMS"
    build_cmd="$build_cmd -t $full_image_name"
    
    # Add latest tag for production (skip if --no-latest flag is set)
    if [[ "$REGISTRY" == "docker.io" && "$TAG" != "latest" && "$NO_LATEST" != "true" ]]; then
        if [[ -n "$REGISTRY" ]]; then
            build_cmd="$build_cmd -t $REGISTRY/$NAMESPACE/$component:latest"
        else
            build_cmd="$build_cmd -t $NAMESPACE/$component:latest"
        fi
    fi
    
    # Add push flag if needed
    if [[ "$PUSH" == "true" ]]; then
        build_cmd="$build_cmd --push"
    elif [[ "$REGISTRY" == "" ]]; then
        # Local mode - load into local Docker
        build_cmd="$build_cmd --load"
    fi
    
    build_cmd="$build_cmd $dockerfile_path"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would execute: $build_cmd"
        return 0
    fi
    
    # Execute build
    if eval "$build_cmd"; then
        log_success "Built $component image: $full_image_name"
    else
        log_error "Failed to build $component image"
        return 1
    fi
    
    # Import to k3d if local mode
    if [[ "$REGISTRY" == "" && -n "$K3D_CLUSTER" ]]; then
        log_info "Importing $full_image_name into k3d cluster '$K3D_CLUSTER'..."
        if k3d image import "$full_image_name" -c "$K3D_CLUSTER"; then
            log_success "Imported $component into k3d cluster"
        else
            log_error "Failed to import $component image"
            return 1
        fi
    fi
}

# Confirm production push
confirm_production_push() {
    if [[ "$REGISTRY" != "docker.io" || "$DRY_RUN" == "true" ]]; then
        return 0
    fi
    
    log_warning ""
    log_warning "🚨 PRODUCTION BUILD & PUSH 🚨"
    log_warning ""
    log_warning "This will build and push images to Docker Hub:"
    log_warning "  Registry: $REGISTRY"
    log_warning "  Namespace: $NAMESPACE"
    log_warning "  Tag: $TAG"
    log_warning "  Platforms: $PLATFORMS"
    log_warning ""
    
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Cancelled by user"
        exit 0
    fi
}

# Show build summary
show_build_summary() {
    local mode="Custom"
    if [[ "$REGISTRY" == "" ]]; then
        mode="Local k3d ($K3D_CLUSTER)"
    elif [[ "$REGISTRY" == "localhost:$LOCAL_REGISTRY_PORT" ]]; then
        mode="Development (local registry)"
    elif [[ "$REGISTRY" == "docker.io" ]]; then
        mode="Production (Docker Hub)"
    fi
    
    log_info ""
    log_info "NimbleTools Core - Image Build"
    log_info "============================="
    log_info ""
    log_info "Mode: $mode"
    log_info "Tag: $TAG"
    log_info "Namespace: $NAMESPACE"
    log_info "Platforms: $PLATFORMS"
    if [[ -n "$REGISTRY" ]]; then
        log_info "Registry: $REGISTRY"
        log_info "Push: $PUSH"
    fi
    if [[ -n "$K3D_CLUSTER" ]]; then
        log_info "K3d cluster: $K3D_CLUSTER"
    fi
    log_info ""
}

# Main execution
main() {
    # Parse arguments
    parse_args "$@"
    
    show_build_summary
    check_prerequisites
    confirm_production_push
    
    # Component definitions
    local components=(
        "mcp-operator:mcp-operator"
        "control-plane:control-plane"
        "rbac-controller:rbac-controller"
    )
    
    local start_time=$(date +%s)
    
    # Build all components
    for component_info in "${components[@]}"; do
        IFS=':' read -r image_name directory <<< "$component_info"
        
        if [[ -d "$directory" && -f "$directory/Dockerfile" ]]; then
            build_image "$image_name" "$directory"
        else
            log_error "Component directory or Dockerfile not found: $directory"
            exit 1
        fi
    done
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    # Success message
    log_success ""
    log_success "🎉 All images built successfully in ${duration}s!"
    log_success ""
    
    # Show what was built
    log_info "Images built:"
    for component_info in "${components[@]}"; do
        IFS=':' read -r image_name directory <<< "$component_info"
        if [[ -n "$REGISTRY" ]]; then
            log_info "  $REGISTRY/$NAMESPACE/$image_name:$TAG"
            if [[ "$REGISTRY" == "docker.io" && "$TAG" != "latest" ]]; then
                log_info "  $REGISTRY/$NAMESPACE/$image_name:latest"
            fi
        else
            log_info "  $NAMESPACE/$image_name:$TAG"
        fi
    done
    
    # Next steps
    log_info ""
    log_info "Next steps:"
    if [[ "$REGISTRY" == "" ]]; then
        log_info "1. Install with local images:"
        log_info "   ./install.sh --local"
    elif [[ "$REGISTRY" == "localhost:$LOCAL_REGISTRY_PORT" ]]; then
        log_info "1. Install with development registry:"
        log_info "   ./install.sh --registry localhost:$LOCAL_REGISTRY_PORT"
    elif [[ "$REGISTRY" == "docker.io" ]]; then
        log_info "1. Test remote installation:"
        log_info "   ./install.sh  # (uses Docker Hub images)"
        log_info ""
        log_info "2. Test on fresh cluster:"
        log_info "   k3d cluster create test-remote --wait"
        log_info "   ./install.sh"
    fi
    log_info ""
}

# Run main function with all arguments
main "$@"