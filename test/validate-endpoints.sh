#!/bin/bash

# Validate dual endpoints configuration
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔍 Validating dual endpoint configuration..."

# Check if ingress is created
echo -n "Checking ingress configuration... "
if kubectl get ingress nimbletools-core-ingress -n nimbletools-system &> /dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC} Ingress not found"
    exit 1
fi

# Check ingress hosts
echo -n "Validating API endpoint host... "
API_HOST=$(kubectl get ingress nimbletools-core-ingress -n nimbletools-system -o jsonpath='{.spec.rules[0].host}')
if [[ "$API_HOST" == "api.nimbletools.local" ]]; then
    echo -e "${GREEN}✓${NC} ($API_HOST)"
else
    echo -e "${RED}✗${NC} Expected api.nimbletools.local, got $API_HOST"
    exit 1
fi

echo -n "Validating MCP endpoint host... "
MCP_HOST=$(kubectl get ingress nimbletools-core-ingress -n nimbletools-system -o jsonpath='{.spec.rules[1].host}')
if [[ "$MCP_HOST" == "mcp.nimbletools.local" ]]; then
    echo -e "${GREEN}✓${NC} ($MCP_HOST)"
else
    echo -e "${RED}✗${NC} Expected mcp.nimbletools.local, got $MCP_HOST"
    exit 1
fi

# Check services are running
echo -n "Checking API service... "
if kubectl get service nimbletools-core-control-plane -n nimbletools-system &> /dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC} API service not found"
    exit 1
fi

echo -n "Checking MCP proxy service... "
if kubectl get service nimbletools-core-mcp-proxy -n nimbletools-system &> /dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC} MCP proxy service not found"
    exit 1
fi

# Check pod readiness
echo -n "Checking API pod readiness... "
API_READY=$(kubectl get pods -l app.kubernetes.io/component=control-plane -n nimbletools-system -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "False")
if [[ "$API_READY" == "True" ]]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⏳${NC} API pod not ready yet"
fi

echo -n "Checking MCP proxy pod readiness... "
MCP_READY=$(kubectl get pods -l app.kubernetes.io/component=mcp-proxy -n nimbletools-system -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "False")
if [[ "$MCP_READY" == "True" ]]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⏳${NC} MCP proxy pod not ready yet"
fi

echo ""
echo -e "${GREEN}🎉 Dual endpoint validation completed successfully!${NC}"
echo ""
echo "Next steps:"
echo "1. Add to /etc/hosts:"
echo "   127.0.0.1 api.nimbletools.dev"
echo "   127.0.0.1 mcp.nimbletools.dev"
echo ""
echo "2. Port-forward ingress controller:"
echo "   kubectl port-forward -n ingress-nginx service/ingress-nginx-controller 80:80"
echo ""
echo "3. Test endpoints:"
echo "   curl http://api.nimbletools.dev/health"
echo "   curl http://mcp.nimbletools.dev/health"