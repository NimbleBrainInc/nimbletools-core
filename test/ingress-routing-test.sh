#!/bin/bash
set -e

echo "🧪 Testing MCP ingress routing configuration..."

# Configuration
TEST_WORKSPACE="test-workspace-$(date +%s)"
TEST_SERVER="test-echo"
WORKSPACE_NAMESPACE="ws-test-${TEST_WORKSPACE}"

cleanup() {
    echo "🧹 Cleaning up test resources..."
    kubectl delete namespace "$WORKSPACE_NAMESPACE" --ignore-not-found=true
    echo "✅ Cleanup completed"
}

# Set up cleanup trap
trap cleanup EXIT

echo "📦 Creating test workspace namespace: $WORKSPACE_NAMESPACE"
kubectl create namespace "$WORKSPACE_NAMESPACE" || true

echo "🚀 Deploying test MCPService..."
kubectl apply -f - <<EOF
apiVersion: mcp.nimbletools.dev/v1
kind: MCPService
metadata:
  name: $TEST_SERVER
  namespace: $WORKSPACE_NAMESPACE
  labels:
    mcp.nimbletools.dev/workspace: "true"
    mcp.nimbletools.dev/workspace_id: "$TEST_WORKSPACE"
    mcp.nimbletools.dev/service: "true"
spec:
  container:
    image: nimbletools/mcp-echo:latest
    port: 8000
  deployment:
    type: http
    healthPath: /health
  replicas: 1
  environment: {}
EOF

echo "⏳ Waiting for MCPService to be processed..."
sleep 15

echo "🔍 Testing ingress creation..."

# Test that separate ingresses are created
MCP_INGRESS="${TEST_SERVER}-ingress-mcp"
HEALTH_INGRESS="${TEST_SERVER}-ingress-health"

if ! kubectl get ingress "$MCP_INGRESS" -n "$WORKSPACE_NAMESPACE" >/dev/null 2>&1; then
    echo "❌ FAIL: MCP ingress '$MCP_INGRESS' not created"
    echo "Available ingresses:"
    kubectl get ingress -n "$WORKSPACE_NAMESPACE"
    exit 1
fi

if ! kubectl get ingress "$HEALTH_INGRESS" -n "$WORKSPACE_NAMESPACE" >/dev/null 2>&1; then
    echo "❌ FAIL: Health ingress '$HEALTH_INGRESS' not created"
    echo "Available ingresses:"
    kubectl get ingress -n "$WORKSPACE_NAMESPACE"
    exit 1
fi

echo "✅ Both MCP and health ingresses created successfully"

# Test that rewrite targets are correct
echo "🔍 Testing ingress configurations..."

MCP_REWRITE=$(kubectl get ingress "$MCP_INGRESS" -n "$WORKSPACE_NAMESPACE" -o jsonpath='{.metadata.annotations.nginx\.ingress\.kubernetes\.io/rewrite-target}' 2>/dev/null || echo "")
HEALTH_REWRITE=$(kubectl get ingress "$HEALTH_INGRESS" -n "$WORKSPACE_NAMESPACE" -o jsonpath='{.metadata.annotations.nginx\.ingress\.kubernetes\.io/rewrite-target}' 2>/dev/null || echo "")

if [[ "$MCP_REWRITE" != "/mcp" ]]; then
    echo "❌ FAIL: MCP ingress rewrite target should be '/mcp', got: '$MCP_REWRITE'"
    kubectl describe ingress "$MCP_INGRESS" -n "$WORKSPACE_NAMESPACE"
    exit 1
fi

if [[ "$HEALTH_REWRITE" != "/health" ]]; then
    echo "❌ FAIL: Health ingress rewrite target should be '/health', got: '$HEALTH_REWRITE'"
    kubectl describe ingress "$HEALTH_INGRESS" -n "$WORKSPACE_NAMESPACE"
    exit 1
fi

echo "✅ Ingress rewrite targets are correct"

# Test that paths are configured correctly
echo "🔍 Testing ingress paths..."

MCP_PATH=$(kubectl get ingress "$MCP_INGRESS" -n "$WORKSPACE_NAMESPACE" -o jsonpath='{.spec.rules[0].http.paths[0].path}')
HEALTH_PATH=$(kubectl get ingress "$HEALTH_INGRESS" -n "$WORKSPACE_NAMESPACE" -o jsonpath='{.spec.rules[0].http.paths[0].path}')

EXPECTED_MCP_PATH="/$TEST_WORKSPACE/$TEST_SERVER/mcp"
EXPECTED_HEALTH_PATH="/$TEST_WORKSPACE/$TEST_SERVER/health"

if [[ "$MCP_PATH" != "$EXPECTED_MCP_PATH" ]]; then
    echo "❌ FAIL: MCP ingress path should be '$EXPECTED_MCP_PATH', got: '$MCP_PATH'"
    exit 1
fi

if [[ "$HEALTH_PATH" != "$EXPECTED_HEALTH_PATH" ]]; then
    echo "❌ FAIL: Health ingress path should be '$EXPECTED_HEALTH_PATH', got: '$HEALTH_PATH'"
    exit 1
fi

echo "✅ Ingress paths are correct"

# Test that both ingresses point to the correct service
echo "🔍 Testing service backends..."

MCP_SERVICE=$(kubectl get ingress "$MCP_INGRESS" -n "$WORKSPACE_NAMESPACE" -o jsonpath='{.spec.rules[0].http.paths[0].backend.service.name}')
HEALTH_SERVICE=$(kubectl get ingress "$HEALTH_INGRESS" -n "$WORKSPACE_NAMESPACE" -o jsonpath='{.spec.rules[0].http.paths[0].backend.service.name}')

EXPECTED_SERVICE="${TEST_SERVER}-service"

if [[ "$MCP_SERVICE" != "$EXPECTED_SERVICE" ]]; then
    echo "❌ FAIL: MCP ingress should point to service '$EXPECTED_SERVICE', got: '$MCP_SERVICE'"
    exit 1
fi

if [[ "$HEALTH_SERVICE" != "$EXPECTED_SERVICE" ]]; then
    echo "❌ FAIL: Health ingress should point to service '$EXPECTED_SERVICE', got: '$HEALTH_SERVICE'"
    exit 1
fi

echo "✅ Service backends are correct"

# Test that ingresses have correct labels
echo "🔍 Testing ingress labels..."

MCP_TYPE_LABEL=$(kubectl get ingress "$MCP_INGRESS" -n "$WORKSPACE_NAMESPACE" -o jsonpath='{.metadata.labels.mcp\.nimbletools\.dev/ingress-type}')
HEALTH_TYPE_LABEL=$(kubectl get ingress "$HEALTH_INGRESS" -n "$WORKSPACE_NAMESPACE" -o jsonpath='{.metadata.labels.mcp\.nimbletools\.dev/ingress-type}')

if [[ "$MCP_TYPE_LABEL" != "mcp" ]]; then
    echo "❌ FAIL: MCP ingress should have label 'mcp.nimbletools.dev/ingress-type=mcp', got: '$MCP_TYPE_LABEL'"
    exit 1
fi

if [[ "$HEALTH_TYPE_LABEL" != "health" ]]; then
    echo "❌ FAIL: Health ingress should have label 'mcp.nimbletools.dev/ingress-type=health', got: '$HEALTH_TYPE_LABEL'"
    exit 1
fi

echo "✅ Ingress labels are correct"

echo ""
echo "🎉 ALL INGRESS ROUTING TESTS PASSED!"
echo ""
echo "Summary:"
echo "✅ MCP ingress created with correct configuration"
echo "✅ Health ingress created with correct configuration" 
echo "✅ Separate rewrite targets (/mcp and /health)"
echo "✅ Correct path routing"
echo "✅ Proper service backends"
echo "✅ Appropriate labels and metadata"
echo ""
echo "This prevents the ingress routing regression that caused 404 errors."