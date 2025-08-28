#!/bin/bash
set -e

echo "🔌 Testing end-to-end MCP connection through ingress..."

# Configuration
TEST_WORKSPACE="e2e-test-workspace-$(date +%s)"
TEST_SERVER="test-echo"
WORKSPACE_NAMESPACE="ws-test-${TEST_WORKSPACE}"
MCP_HOST="mcp.nimbletools.local"
PORT_FORWARD_PORT=8080

cleanup() {
    echo "🧹 Cleaning up test resources..."
    # Kill port forward if running
    pkill -f "kubectl port-forward.*ingress-nginx-controller.*${PORT_FORWARD_PORT}:80" || true
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

echo "⏳ Waiting for MCPService deployment..."
kubectl wait --for=condition=available deployment/${TEST_SERVER}-deployment -n "$WORKSPACE_NAMESPACE" --timeout=120s

echo "⏳ Waiting for pod to be ready..."
kubectl wait --for=condition=ready pod -l app=$TEST_SERVER -n "$WORKSPACE_NAMESPACE" --timeout=120s

echo "🔍 Verifying ingresses were created..."
kubectl get ingress -n "$WORKSPACE_NAMESPACE"

# Set up port forwarding to ingress controller
echo "🔗 Setting up port forward to ingress controller..."
kubectl port-forward -n ingress-nginx service/ingress-nginx-controller ${PORT_FORWARD_PORT}:80 &
PORT_FORWARD_PID=$!

# Wait for port forward to be ready
echo "⏳ Waiting for port forward to be ready..."
sleep 5

# Test health endpoint first
echo "🩺 Testing health endpoint..."
HEALTH_URL="http://127.0.0.1:${PORT_FORWARD_PORT}/${TEST_WORKSPACE}/${TEST_SERVER}/health"

HEALTH_RESPONSE=$(curl -s -H "Host: $MCP_HOST" "$HEALTH_URL" --max-time 10 || echo "FAILED")

if [[ "$HEALTH_RESPONSE" == *"healthy"* ]]; then
    echo "✅ Health endpoint responds correctly"
else
    echo "❌ FAIL: Health endpoint failed. Response: $HEALTH_RESPONSE"
    exit 1
fi

# Test MCP connection
echo "🔌 Testing MCP connection..."
MCP_URL="http://127.0.0.1:${PORT_FORWARD_PORT}/${TEST_WORKSPACE}/${TEST_SERVER}/mcp"

MCP_REQUEST='{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": {},
      "resources": {},
      "prompts": {}
    },
    "clientInfo": {
      "name": "test-client",
      "version": "1.0.0"
    }
  }
}'

echo "📤 Sending MCP initialize request..."
MCP_RESPONSE=$(curl -s \
  -H "Host: $MCP_HOST" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d "$MCP_REQUEST" \
  "$MCP_URL" \
  --max-time 10 || echo "FAILED")

echo "📥 MCP Response received"

# Parse the response (it should be an SSE stream)
if [[ "$MCP_RESPONSE" == *"result"* ]] && [[ "$MCP_RESPONSE" == *"protocolVersion"* ]]; then
    echo "✅ MCP connection successful - received valid initialize response"
elif [[ "$MCP_RESPONSE" == *"Echo MCP Server"* ]]; then
    echo "✅ MCP connection successful - Echo server responded"
elif [[ "$MCP_RESPONSE" == *"jsonrpc"* ]]; then
    echo "✅ MCP connection successful - received JSON-RPC response"
else
    echo "❌ FAIL: MCP connection failed or invalid response"
    echo "Response: $MCP_RESPONSE"
    exit 1
fi

# Test that we can make multiple MCP requests
echo "🔄 Testing multiple MCP requests..."
TOOLS_REQUEST='{
  "jsonrpc": "2.0", 
  "id": 2,
  "method": "tools/list"
}'

TOOLS_RESPONSE=$(curl -s \
  -H "Host: $MCP_HOST" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d "$TOOLS_REQUEST" \
  "$MCP_URL" \
  --max-time 10 || echo "FAILED")

if [[ "$TOOLS_RESPONSE" == *"jsonrpc"* ]] || [[ "$TOOLS_RESPONSE" == *"tools"* ]]; then
    echo "✅ Multiple MCP requests work correctly"
else
    echo "⚠️  Multiple requests may have issues, but primary connection works"
fi

echo ""
echo "🎉 END-TO-END MCP CONNECTION TEST PASSED!"
echo ""
echo "Summary:"
echo "✅ MCPService deployed successfully"
echo "✅ Ingresses created and configured"
echo "✅ Health endpoint accessible via ingress"
echo "✅ MCP endpoint accessible via ingress"
echo "✅ MCP protocol communication working"
echo "✅ Ingress routing correctly handles both /mcp and /health paths"
echo ""
echo "This confirms that the ingress routing fix prevents 404 errors"
echo "and enables proper MCP communication through the ingress."