#!/bin/bash

# Comprehensive deployment test for NimbleTools Core
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

CLUSTER_NAME="nimbletools-dev"
START_TIME=$(date +%s)

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

# Test deployment speed (from fresh cluster to running services)
test_deployment_speed() {
    log_info "🚀 Testing 60-second deployment goal..."
    
    # Delete and recreate cluster
    log_info "Creating fresh k3d cluster..."
    k3d cluster delete $CLUSTER_NAME >/dev/null 2>&1 || true
    k3d cluster create $CLUSTER_NAME --wait >/dev/null 2>&1
    
    local cluster_start=$(date +%s)
    
    # Build and import images
    log_info "Building and importing images..."
    ./scripts/build-local.sh >/dev/null 2>&1
    
    # Install NimbleTools Core
    log_info "Installing NimbleTools Core..."
    ./install.sh >/dev/null 2>&1
    
    local cluster_end=$(date +%s)
    local cluster_duration=$((cluster_end - cluster_start))
    
    if [[ $cluster_duration -le 60 ]]; then
        log_success "✅ Deployment completed in ${cluster_duration}s (under 60s goal!)"
    else
        log_warning "⚠️  Deployment took ${cluster_duration}s (over 60s goal)"
    fi
    
    return $cluster_duration
}

# Test dual endpoints
test_endpoints() {
    log_info "🔍 Testing dual endpoint configuration..."
    
    # Check ingress exists
    if kubectl get ingress nimbletools-core-ingress -n nimbletools-system >/dev/null 2>&1; then
        log_success "✅ Ingress configuration found"
    else
        log_error "❌ Ingress not found"
        return 1
    fi
    
    # Validate hosts
    local api_host=$(kubectl get ingress nimbletools-core-ingress -n nimbletools-system -o jsonpath='{.spec.rules[0].host}')
    local mcp_host=$(kubectl get ingress nimbletools-core-ingress -n nimbletools-system -o jsonpath='{.spec.rules[1].host}')
    
    if [[ "$api_host" == "api.nimbletools.local" ]] && [[ "$mcp_host" == "mcp.nimbletools.local" ]]; then
        log_success "✅ Dual endpoints configured correctly"
    else
        log_error "❌ Incorrect endpoint configuration"
        return 1
    fi
    
    # Check services
    if kubectl get svc nimbletools-core-control-plane nimbletools-core-mcp-proxy -n nimbletools-system >/dev/null 2>&1; then
        log_success "✅ Both API and MCP proxy services running"
    else
        log_error "❌ Services not found"
        return 1
    fi
    
    return 0
}

# Test pod health
test_pod_health() {
    log_info "🏥 Testing pod health..."
    
    # Wait for pods to be ready
    log_info "Waiting for all pods to be ready..."
    kubectl wait --for=condition=ready pod --all -n nimbletools-system --timeout=60s >/dev/null 2>&1
    
    local total_pods=$(kubectl get pods -n nimbletools-system --no-headers | wc -l)
    local ready_pods=$(kubectl get pods -n nimbletools-system --no-headers | grep "1/1.*Running" | wc -l)
    
    if [[ $ready_pods -eq $total_pods ]]; then
        log_success "✅ All $total_pods pods are healthy and ready"
    else
        log_error "❌ Only $ready_pods/$total_pods pods are ready"
        return 1
    fi
    
    return 0
}

# Test API functionality
test_api_functionality() {
    log_info "🔧 Testing API functionality..."
    
    # Port forward to test API
    kubectl port-forward -n nimbletools-system service/nimbletools-core-control-plane 18080:8080 >/dev/null 2>&1 &
    local pf_pid=$!
    sleep 2
    
    # Test health endpoint
    if curl -s http://localhost:18080/health | grep -q "healthy"; then
        log_success "✅ API health endpoint working"
    else
        log_error "❌ API health endpoint failed"
        kill $pf_pid 2>/dev/null || true
        return 1
    fi
    
    # Test root endpoint
    if curl -s http://localhost:18080/ | grep -q "NimbleTools Management API"; then
        log_success "✅ API root endpoint working"
    else
        log_error "❌ API root endpoint failed"
        kill $pf_pid 2>/dev/null || true
        return 1
    fi
    
    # Test workspaces endpoint
    if curl -s http://localhost:18080/v1/workspaces | grep -q "workspaces"; then
        log_success "✅ Workspaces API working"
    else
        log_error "❌ Workspaces API failed"
        kill $pf_pid 2>/dev/null || true
        return 1
    fi
    
    kill $pf_pid 2>/dev/null || true
    return 0
}

# Main test execution
main() {
    log_info "🧪 Starting comprehensive NimbleTools Core deployment test"
    log_info ""
    
    local tests_passed=0
    local total_tests=4
    
    # Test 1: Deployment Speed
    if test_deployment_speed; then
        ((tests_passed++))
    fi
    
    # Test 2: Dual Endpoints
    if test_endpoints; then
        ((tests_passed++))
    fi
    
    # Test 3: Pod Health
    if test_pod_health; then
        ((tests_passed++))
    fi
    
    # Test 4: API Functionality
    if test_api_functionality; then
        ((tests_passed++))
    fi
    
    log_info ""
    log_info "📊 Test Summary:"
    log_info "   Tests passed: $tests_passed/$total_tests"
    
    local end_time=$(date +%s)
    local total_duration=$((end_time - START_TIME))
    log_info "   Total test time: ${total_duration}s"
    
    if [[ $tests_passed -eq $total_tests ]]; then
        log_success ""
        log_success "🎉 All tests passed! NimbleTools Core is ready for use."
        log_success ""
        log_info "Next steps:"
        log_info "1. Add to /etc/hosts: 127.0.0.1 api.nimbletools.local mcp.nimbletools.local"
        log_info "2. Test endpoints with traefik LoadBalancer:"
        log_info "   curl -H 'Host: api.nimbletools.local' http://$(kubectl get svc traefik -n kube-system -o jsonpath='{.status.loadBalancer.ingress[0].ip}')/health"
        return 0
    else
        log_error ""
        log_error "❌ Some tests failed. Check logs above for details."
        return 1
    fi
}

main "$@"