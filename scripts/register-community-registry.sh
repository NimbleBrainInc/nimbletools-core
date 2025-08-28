#!/bin/bash

# Register Community Registry Script
# Enables the NimbleTools Community MCP Registry via the Control Plane API

set -e

# Configuration
DEFAULT_CONTROL_PLANE_URL="http://api.nimbletools.local"
COMMUNITY_REGISTRY_URL="https://raw.githubusercontent.com/NimbleBrainInc/nimbletools-mcp-registry/main/registry.yaml"
DEFAULT_NAMESPACE_OVERRIDE=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo -e "${BLUE}"
    echo "═══════════════════════════════════════════════"
    echo "  NimbleTools Community Registry Registration"
    echo "═══════════════════════════════════════════════"
    echo -e "${NC}"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Register the NimbleTools Community MCP Registry with the Control Plane API.

OPTIONS:
    -u, --url URL           Control Plane API URL (default: $DEFAULT_CONTROL_PLANE_URL)
    -n, --namespace NAME    Override namespace name (optional)
    -r, --registry-url URL  Registry URL (default: community registry)
    -t, --token TOKEN       Authorization token for API (optional)
    -d, --dry-run          Show what would be registered without making changes
    -h, --help             Show this help message

EXAMPLES:
    $0
    $0 --url http://api.nimbletools.local:8080
    $0 --namespace my-custom-registry
    $0 --token "Bearer your-jwt-token"
    $0 --dry-run

EOF
}

# Parse command line arguments
CONTROL_PLANE_URL="$DEFAULT_CONTROL_PLANE_URL"
REGISTRY_URL="$COMMUNITY_REGISTRY_URL"
NAMESPACE_OVERRIDE="$DEFAULT_NAMESPACE_OVERRIDE"
AUTH_TOKEN=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--url)
            CONTROL_PLANE_URL="$2"
            shift 2
            ;;
        -n|--namespace)
            NAMESPACE_OVERRIDE="$2"
            shift 2
            ;;
        -r|--registry-url)
            REGISTRY_URL="$2"
            shift 2
            ;;
        -t|--token)
            AUTH_TOKEN="$2"
            shift 2
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Function to check if required tools are available
check_dependencies() {
    local deps=("curl" "jq")
    local missing=()
    
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            missing+=("$dep")
        fi
    done
    
    if [ ${#missing[@]} -ne 0 ]; then
        print_error "Missing required dependencies: ${missing[*]}"
        print_info "Please install the missing tools and try again."
        print_info "  - On macOS: brew install curl jq"
        print_info "  - On Ubuntu/Debian: sudo apt-get install curl jq"
        print_info "  - On CentOS/RHEL: sudo yum install curl jq"
        exit 1
    fi
}

# Function to test API connectivity
test_api_connection() {
    print_info "Testing connection to Control Plane API at $CONTROL_PLANE_URL"
    
    local auth_header=""
    if [ -n "$AUTH_TOKEN" ]; then
        auth_header="-H \"Authorization: $AUTH_TOKEN\""
    fi
    
    if ! curl -s --connect-timeout 10 $auth_header "$CONTROL_PLANE_URL/health" > /dev/null 2>&1; then
        print_error "Cannot connect to Control Plane API at $CONTROL_PLANE_URL"
        print_info "Please ensure the Control Plane is running and accessible."
        print_info "You can start it with: cd control-plane && uv run python -m nimbletools_control_plane.main"
        exit 1
    fi
    
    print_success "Successfully connected to Control Plane API"
}

# Function to get registry info
get_registry_info() {
    print_info "Fetching registry information from $REGISTRY_URL"
    
    local auth_header=""
    if [ -n "$AUTH_TOKEN" ]; then
        auth_header="-H \"Authorization: $AUTH_TOKEN\""
    fi
    
    local encoded_url=$(printf '%s' "$REGISTRY_URL" | jq -sRr @uri)
    local info_response
    
    if ! info_response=$(curl -s $auth_header "$CONTROL_PLANE_URL/v1/registry/info?registry_url=$encoded_url" 2>/dev/null); then
        print_error "Failed to fetch registry information"
        exit 1
    fi
    
    # Check if response contains error
    if echo "$info_response" | jq -e '.detail' > /dev/null 2>&1; then
        local error_detail=$(echo "$info_response" | jq -r '.detail')
        print_error "API Error: $error_detail"
        exit 1
    fi
    
    # Extract registry info
    local name=$(echo "$info_response" | jq -r '.name // "unknown"')
    local version=$(echo "$info_response" | jq -r '.version // "unknown"')
    local total_servers=$(echo "$info_response" | jq -r '.total_servers // 0')
    local active_servers=$(echo "$info_response" | jq -r '.active_servers // 0')
    
    print_success "Registry Information:"
    echo "  📁 Name: $name"
    echo "  🏷️  Version: $version"
    echo "  📊 Total Servers: $total_servers"
    echo "  ✅ Active Servers: $active_servers"
    echo "  🌐 URL: $REGISTRY_URL"
}

# Function to register the registry
register_registry() {
    print_info "Registering registry with Control Plane"
    
    # Build request payload
    local payload="{\"registry_url\": \"$REGISTRY_URL\""
    if [ -n "$NAMESPACE_OVERRIDE" ]; then
        payload="$payload, \"namespace_override\": \"$NAMESPACE_OVERRIDE\""
    fi
    payload="$payload}"
    
    local auth_header=""
    if [ -n "$AUTH_TOKEN" ]; then
        auth_header="-H \"Authorization: $AUTH_TOKEN\""
    fi
    
    if [ "$DRY_RUN" = true ]; then
        print_info "DRY RUN - Would register registry with payload:"
        echo "$payload" | jq .
        return 0
    fi
    
    local response
    if ! response=$(curl -s -L -X POST \
        -H "Content-Type: application/json" \
        $auth_header \
        -d "$payload" \
        "$CONTROL_PLANE_URL/v1/registry" 2>/dev/null); then
        print_error "Failed to register registry"
        exit 1
    fi
    
    # Check if response contains error
    if echo "$response" | jq -e '.detail' > /dev/null 2>&1; then
        local error_detail=$(echo "$response" | jq -r '.detail')
        print_error "Registration failed: $error_detail"
        exit 1
    fi
    
    # Debug: Show response if it looks empty
    if [ -z "$response" ] || [ "$response" = "null" ]; then
        print_error "Empty response from API"
        exit 1
    fi
    
    # Extract registration results
    local registry_name=$(echo "$response" | jq -r '.registry_name // "unknown"')
    local registry_version=$(echo "$response" | jq -r '.registry_version // "unknown"')
    local namespace=$(echo "$response" | jq -r '.namespace // "unknown"')
    local services_created=$(echo "$response" | jq -r '.services_created // 0')
    local services=($(echo "$response" | jq -r '.services[]? // empty'))
    
    print_success "Registry successfully registered!"
    echo
    echo "📋 Registration Summary:"
    echo "  📁 Registry: $registry_name (v$registry_version)"
    echo "  📦 Namespace: $namespace"
    echo "  🚀 Services Created: $services_created"
    
    if [ ${#services[@]} -gt 0 ]; then
        echo "  📜 Services:"
        for service in "${services[@]}"; do
            echo "    • $service"
        done
    fi
    
    echo
    print_info "You can now:"
    echo "  • List all registry servers: curl $CONTROL_PLANE_URL/v1/registry/servers"
    echo "  • List your registries: curl $CONTROL_PLANE_URL/v1/registry"
    echo "  • Get server details: curl $CONTROL_PLANE_URL/v1/registry/servers/{server-name}"
}

# Function to list existing registries
list_existing_registries() {
    print_info "Checking existing registries"
    
    local auth_header=""
    if [ -n "$AUTH_TOKEN" ]; then
        auth_header="-H \"Authorization: $AUTH_TOKEN\""
    fi
    
    local registries_response
    if registries_response=$(curl -s -L $auth_header "$CONTROL_PLANE_URL/v1/registry" 2>/dev/null); then
        local total=$(echo "$registries_response" | jq -r '.total // 0')
        
        # Handle case where total might be empty or null
        if [ -n "$total" ] && [ "$total" != "null" ] && [ "$total" -gt 0 ]; then
            print_info "Found $total existing registries:"
            echo "$registries_response" | jq -r '.registries[]? | "  • \(.name) (namespace: \(.namespace))"'
            echo
        else
            print_info "No existing registries found"
        fi
    else
        print_warning "Could not fetch existing registries (this is normal for first-time setup)"
    fi
}

# Main execution
main() {
    print_header
    
    print_info "Configuration:"
    echo "  🌐 Control Plane URL: $CONTROL_PLANE_URL"
    echo "  📋 Registry URL: $REGISTRY_URL"
    if [ -n "$NAMESPACE_OVERRIDE" ]; then
        echo "  📦 Namespace Override: $NAMESPACE_OVERRIDE"
    fi
    if [ -n "$AUTH_TOKEN" ]; then
        echo "  🔐 Using Authorization Token: ✅"
    else
        echo "  🔐 Using Authorization Token: ❌ (No-auth mode)"
    fi
    if [ "$DRY_RUN" = true ]; then
        echo "  🧪 Dry Run Mode: ✅"
    fi
    echo
    
    # Check dependencies
    check_dependencies
    
    # Test API connection
    test_api_connection
    
    # List existing registries
    list_existing_registries
    
    # Get registry info
    get_registry_info
    echo
    
    # Register the registry
    register_registry
    
    print_success "Registry registration completed successfully! 🎉"
}

# Run main function
main "$@"