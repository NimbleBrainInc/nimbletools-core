#!/bin/bash
set -euo pipefail

# Helm Chart Testing Script
# Tests Helm chart templates using helm-unittest plugin

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CHART_DIR="${REPO_ROOT}/chart"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if helm is installed
if ! command -v helm &> /dev/null; then
    echo -e "${RED}Error: helm is not installed${NC}"
    echo "Install helm: https://helm.sh/docs/intro/install/"
    exit 1
fi

# Check if helm-unittest plugin is installed
if ! helm plugin list | grep -q unittest; then
    echo -e "${YELLOW}Warning: helm-unittest plugin is not installed${NC}"
    echo "Installing helm-unittest plugin..."
    helm plugin install https://github.com/helm-unittest/helm-unittest
fi

echo "========================================="
echo "Running Helm Chart Unit Tests"
echo "========================================="

# Run helm lint first (optional, warnings don't fail)
echo -e "\n${YELLOW}1. Running helm lint...${NC}"
if helm lint "${CHART_DIR}" 2>&1 | grep -q "ERROR"; then
    echo -e "${YELLOW}⚠ Helm lint found issues (non-blocking for unit tests)${NC}"
else
    echo -e "${GREEN}✓ Helm lint passed${NC}"
fi

# Run helm unittest
echo -e "\n${YELLOW}2. Running helm unit tests...${NC}"
if helm unittest "${CHART_DIR}" "$@"; then
    echo -e "\n${GREEN}✓ All tests passed${NC}"
else
    echo -e "\n${RED}✗ Tests failed${NC}"
    exit 1
fi

# Validate templates can be rendered
echo -e "\n${YELLOW}3. Validating template rendering...${NC}"
if helm template test-release "${CHART_DIR}" > /dev/null; then
    echo -e "${GREEN}✓ Templates render successfully${NC}"
else
    echo -e "${RED}✗ Template rendering failed${NC}"
    exit 1
fi

echo -e "\n========================================="
echo -e "${GREEN}All chart tests passed!${NC}"
echo -e "========================================="
