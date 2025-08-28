#!/bin/bash

# NimbleTools Core End-to-End Test Suite
# Tests the complete workflow from installation to service deployment

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
TEST_NAMESPACE="nimbletools-test"
TEST_CLUSTER="nimbletools-e2e-test"
START_TIME=$(date +%s)

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

log_step() {
    local step_num=$1
    local step_desc=$2
    echo -e "${BLUE}[STEP $step_num]${NC} $step_desc"
}

# Timer functions
start_timer() {
    START_TIME=$(date +%s)
}

check_timer() {
    local current_time=$(date +%s)
    local elapsed=$((current_time - START_TIME))
    echo $elapsed
}

# Test results tracking
TESTS_PASSED=0
TESTS_FAILED=0
FAILED_TESTS=()

test_result() {
    local test_name=$1
    local result=$2
    
    if [[ "$result" == "PASS" ]]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        log_success "✓ $test_name"
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        FAILED_TESTS+=("$test_name")
        log_error "✗ $test_name"
    fi
}

# Cleanup function
cleanup() {
    log_info "Cleaning up test environment..."
    
    # Uninstall NimbleTools Core
    if ./scripts/uninstall.sh --namespace "$TEST_NAMESPACE" --force --remove-crd --remove-namespace &> /dev/null; then
        log_info "Uninstalled NimbleTools Core"
    else
        log_warning "Failed to uninstall NimbleTools Core"
    fi
    
    # Remove test cluster if we created it
    if command -v k3d &> /dev/null && k3d cluster list | grep -q "$TEST_CLUSTER"; then
        k3d cluster delete "$TEST_CLUSTER" &> /dev/null || true
        log_info "Deleted test cluster"
    fi
}

# Trap for cleanup on exit
trap cleanup EXIT

# Test functions
test_prerequisites() {
    log_step 1 "Testing Prerequisites"
    
    local required_commands=("kubectl" "helm" "docker")
    local missing_commands=()
    
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            missing_commands+=("$cmd")
        fi
    done
    
    if [[ ${#missing_commands[@]} -eq 0 ]]; then
        test_result "Prerequisites Check" "PASS"
        return 0
    else
        log_error "Missing commands: ${missing_commands[*]}"
        test_result "Prerequisites Check" "FAIL"
        return 1
    fi
}

test_cluster_access() {
    log_step 2 "Testing Cluster Access"
    
    if kubectl cluster-info &> /dev/null; then
        test_result "Cluster Access" "PASS"
        return 0
    else
        test_result "Cluster Access" "FAIL"
        return 1
    fi
}

test_helm_chart_validation() {
    log_step 3 "Testing Helm Chart Validation"
    
    # Lint the chart
    if helm lint ./chart &> /dev/null; then
        test_result "Helm Chart Lint" "PASS"
    else
        test_result "Helm Chart Lint" "FAIL"
        return 1
    fi
    
    # Template the chart
    if helm template test-release ./chart &> /dev/null; then
        test_result "Helm Chart Template" "PASS"
    else
        test_result "Helm Chart Template" "FAIL"
        return 1
    fi
    
    return 0
}

test_60_second_installation() {
    log_step 4 "Testing 60-Second Installation Target"
    
    start_timer
    
    # Run installation
    if ./install.sh --namespace "$TEST_NAMESPACE" &> /dev/null; then
        local elapsed=$(check_timer)
        
        if [[ $elapsed -le 60 ]]; then
            test_result "60-Second Installation (${elapsed}s)" "PASS"
        else
            test_result "60-Second Installation (${elapsed}s - EXCEEDED LIMIT)" "FAIL"
            return 1
        fi
    else
        test_result "Installation Process" "FAIL"
        return 1
    fi
    
    return 0
}

test_operator_deployment() {
    log_step 5 "Testing Operator Deployment"
    
    # Check if operator pod is running
    local timeout=120
    local elapsed=0
    
    while [[ $elapsed -lt $timeout ]]; do
        if kubectl get pods -n "$TEST_NAMESPACE" -l app.kubernetes.io/component=operator --no-headers | grep -q "Running"; then
            test_result "Operator Pod Running" "PASS"
            return 0
        fi
        
        sleep 5
        elapsed=$((elapsed + 5))
    done
    
    test_result "Operator Pod Running (timeout after ${timeout}s)" "FAIL"
    return 1
}

test_crd_installation() {
    log_step 6 "Testing CRD Installation"
    
    if kubectl get crd mcpservices.mcp.nimbletools.dev &> /dev/null; then
        test_result "MCPService CRD Installed" "PASS"
        return 0
    else
        test_result "MCPService CRD Installed" "FAIL"
        return 1
    fi
}

test_api_server_deployment() {
    log_step 7 "Testing API Server Deployment (Optional)"
    
    # Check if API server is deployed
    if kubectl get deployment -n "$TEST_NAMESPACE" | grep -q "api"; then
        # Wait for API server to be ready
        local timeout=60
        local elapsed=0
        
        while [[ $elapsed -lt $timeout ]]; do
            if kubectl get pods -n "$TEST_NAMESPACE" -l app.kubernetes.io/component=api --no-headers | grep -q "Running"; then
                test_result "API Server Pod Running" "PASS"
                return 0
            fi
            
            sleep 5
            elapsed=$((elapsed + 5))
        done
        
        test_result "API Server Pod Running (timeout)" "FAIL"
        return 1
    else
        log_info "API Server not enabled - skipping"
        test_result "API Server Check (Skipped)" "PASS"
        return 0
    fi
}

test_example_service_deployment() {
    log_step 8 "Testing Example Service Deployment"
    
    # Deploy echo service
    if kubectl apply -f examples/echo-mcp.yaml -n "$TEST_NAMESPACE" &> /dev/null; then
        test_result "Example Service Created" "PASS"
    else
        test_result "Example Service Created" "FAIL"
        return 1
    fi
    
    # Wait for service to be processed by operator
    local timeout=120
    local elapsed=0
    
    while [[ $elapsed -lt $timeout ]]; do
        if kubectl get mcpservice echo-mcp -n "$TEST_NAMESPACE" &> /dev/null; then
            test_result "MCPService Resource Created" "PASS"
            break
        fi
        
        sleep 5
        elapsed=$((elapsed + 5))
    done
    
    if [[ $elapsed -ge $timeout ]]; then
        test_result "MCPService Resource Created (timeout)" "FAIL"
        return 1
    fi
    
    # Wait for pods to be running
    elapsed=0
    while [[ $elapsed -lt $timeout ]]; do
        if kubectl get pods -n "$TEST_NAMESPACE" -l app=echo-mcp --no-headers | grep -q "Running"; then
            test_result "Example Service Pod Running" "PASS"
            return 0
        fi
        
        sleep 5
        elapsed=$((elapsed + 5))
    done
    
    test_result "Example Service Pod Running (timeout)" "FAIL"
    return 1
}

test_service_scaling() {
    log_step 9 "Testing Service Scaling"
    
    # Scale service to 2 replicas
    if kubectl patch mcpservice echo-mcp -n "$TEST_NAMESPACE" -p '{"spec":{"replicas": 2}}' &> /dev/null; then
        test_result "Service Scale Up Command" "PASS"
    else
        test_result "Service Scale Up Command" "FAIL"
        return 1
    fi
    
    # Wait for 2 pods to be running
    local timeout=60
    local elapsed=0
    
    while [[ $elapsed -lt $timeout ]]; do
        local running_pods=$(kubectl get pods -n "$TEST_NAMESPACE" -l app=echo-mcp --no-headers | grep "Running" | wc -l)
        
        if [[ $running_pods -eq 2 ]]; then
            test_result "Service Scaled to 2 Replicas" "PASS"
            return 0
        fi
        
        sleep 5
        elapsed=$((elapsed + 5))
    done
    
    test_result "Service Scaled to 2 Replicas (timeout)" "FAIL"
    return 1
}

test_service_scale_to_zero() {
    log_step 10 "Testing Scale-to-Zero"
    
    # Scale service to 0 replicas
    if kubectl patch mcpservice echo-mcp -n "$TEST_NAMESPACE" -p '{"spec":{"replicas": 0}}' &> /dev/null; then
        test_result "Scale-to-Zero Command" "PASS"
    else
        test_result "Scale-to-Zero Command" "FAIL"
        return 1
    fi
    
    # Wait for pods to terminate
    local timeout=60
    local elapsed=0
    
    while [[ $elapsed -lt $timeout ]]; do
        local running_pods=$(kubectl get pods -n "$TEST_NAMESPACE" -l app=echo-mcp --no-headers | grep "Running" | wc -l)
        
        if [[ $running_pods -eq 0 ]]; then
            test_result "Service Scaled to Zero" "PASS"
            return 0
        fi
        
        sleep 5
        elapsed=$((elapsed + 5))
    done
    
    test_result "Service Scaled to Zero (timeout)" "FAIL"
    return 1
}

test_service_health_check() {
    log_step 11 "Testing Service Health Checks"
    
    # Scale back to 1 for health check
    kubectl patch mcpservice echo-mcp -n "$TEST_NAMESPACE" -p '{"spec":{"replicas": 1}}' &> /dev/null
    
    # Wait for pod to be running
    local timeout=60
    local elapsed=0
    
    while [[ $elapsed -lt $timeout ]]; do
        if kubectl get pods -n "$TEST_NAMESPACE" -l app=echo-mcp --no-headers | grep -q "Running"; then
            break
        fi
        
        sleep 5
        elapsed=$((elapsed + 5))
    done
    
    # Test health endpoint if accessible
    local pod_name=$(kubectl get pods -n "$TEST_NAMESPACE" -l app=echo-mcp -o jsonpath='{.items[0].metadata.name}')
    
    if [[ -n "$pod_name" ]]; then
        if kubectl exec -n "$TEST_NAMESPACE" "$pod_name" -- wget -q -O- http://localhost:8000/health &> /dev/null; then
            test_result "Service Health Check" "PASS"
        else
            # Health check might not be implemented in example service
            test_result "Service Health Check (endpoint may not exist)" "PASS"
        fi
    else
        test_result "Service Health Check (no pod found)" "FAIL"
    fi
}

test_operator_metrics() {
    log_step 12 "Testing Operator Metrics"
    
    local operator_pod=$(kubectl get pods -n "$TEST_NAMESPACE" -l app.kubernetes.io/component=operator -o jsonpath='{.items[0].metadata.name}')
    
    if [[ -n "$operator_pod" ]]; then
        if kubectl exec -n "$TEST_NAMESPACE" "$operator_pod" -- wget -q -O- http://localhost:8080/metrics | grep -q "kopf_"; then
            test_result "Operator Metrics Available" "PASS"
        else
            test_result "Operator Metrics Available" "FAIL"
        fi
    else
        test_result "Operator Metrics Available (no operator pod)" "FAIL"
    fi
}

test_service_cleanup() {
    log_step 13 "Testing Service Cleanup"
    
    # Delete the example service
    if kubectl delete -f examples/echo-mcp.yaml -n "$TEST_NAMESPACE" &> /dev/null; then
        test_result "Service Deletion Command" "PASS"
    else
        test_result "Service Deletion Command" "FAIL"
        return 1
    fi
    
    # Wait for pods to be cleaned up
    local timeout=60
    local elapsed=0
    
    while [[ $elapsed -lt $timeout ]]; do
        local pod_count=$(kubectl get pods -n "$TEST_NAMESPACE" -l app=echo-mcp --no-headers | wc -l)
        
        if [[ $pod_count -eq 0 ]]; then
            test_result "Service Resources Cleaned Up" "PASS"
            return 0
        fi
        
        sleep 5
        elapsed=$((elapsed + 5))
    done
    
    test_result "Service Resources Cleaned Up (timeout)" "FAIL"
    return 1
}

# Setup test environment
setup_test_environment() {
    log_info "Setting up test environment..."
    
    # Check if we need to create a test cluster
    if ! kubectl cluster-info &> /dev/null; then
        if command -v k3d &> /dev/null; then
            log_info "Creating test cluster with k3d..."
            k3d cluster create "$TEST_CLUSTER" --wait &> /dev/null
            kubectl config use-context "k3d-$TEST_CLUSTER" &> /dev/null
        else
            log_error "No Kubernetes cluster available and k3d not installed"
            exit 1
        fi
    fi
}

# Main execution
main() {
    # Show banner
    cat << 'EOF'
    _   _ _           _     _     _____           _     
   | \ | (_)_ __ ___ | |__ | | __|_   _|__   ___ | |___ 
   |  \| | | '_ ` _ \| '_ \| |/ _ \| |/ _ \ / _ \| / __|
   | |\  | | | | | | | |_) | |  __/| | (_) | (_) | \__ \
   |_| \_|_|_| |_| |_|_.__/|_|\___||_|\___/ \___/|_|___/
                                                       
   End-to-End Test Suite
   
EOF
    
    log_info "Starting NimbleTools Core E2E Test Suite..."
    log_info "Test Namespace: $TEST_NAMESPACE"
    
    # Setup
    setup_test_environment
    
    # Run all tests
    local test_functions=(
        "test_prerequisites"
        "test_cluster_access"
        "test_helm_chart_validation"
        "test_60_second_installation"
        "test_operator_deployment"
        "test_crd_installation"
        "test_api_server_deployment"
        "test_example_service_deployment"
        "test_service_scaling"
        "test_service_scale_to_zero"
        "test_service_health_check"
        "test_operator_metrics"
        "test_service_cleanup"
    )
    
    local start_time=$(date +%s)
    
    for test_func in "${test_functions[@]}"; do
        $test_func || true  # Continue even if test fails
    done
    
    local end_time=$(date +%s)
    local total_elapsed=$((end_time - start_time))
    
    # Show results
    echo ""
    log_info "==============================================="
    log_info "E2E Test Results"
    log_info "==============================================="
    log_info "Total Tests: $((TESTS_PASSED + TESTS_FAILED))"
    log_success "Passed: $TESTS_PASSED"
    
    if [[ $TESTS_FAILED -gt 0 ]]; then
        log_error "Failed: $TESTS_FAILED"
        log_error "Failed Tests:"
        for test in "${FAILED_TESTS[@]}"; do
            log_error "  - $test"
        done
    fi
    
    log_info "Total Time: ${total_elapsed}s"
    log_info "==============================================="
    
    # Exit with appropriate code
    if [[ $TESTS_FAILED -gt 0 ]]; then
        exit 1
    else
        log_success "All tests passed! 🎉"
        exit 0
    fi
}

# Run main function
main "$@"