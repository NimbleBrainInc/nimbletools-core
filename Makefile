# NimbleTools Core - Root Makefile
.PHONY: help install verify check clean docker-build update-version

# Version from VERSION file
VERSION ?= 0.2.1

# Default target
help: ## Show this help message
	@echo "NimbleTools Core - Root Development Commands"
	@echo "==========================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Installation
install: install-control-plane install-operator install-universal-adapter install-rbac-controller ## Install all dependencies
	@echo "✅ All dependencies installed"

install-control-plane: ## Install control plane dependencies
	@echo "📦 Installing control plane dependencies..."
	@cd control-plane && uv sync --dev

install-operator: ## Install operator dependencies
	@echo "📦 Installing operator dependencies..."
	@cd mcp-operator && uv sync --dev

install-universal-adapter: ## Install universal adapter dependencies
	@echo "📦 Installing universal adapter dependencies..."
	@cd universal-adapter && uv sync --dev

install-rbac-controller: ## Install rbac controller dependencies
	@echo "📦 Installing rbac controller dependencies..."
	@cd rbac-controller && uv sync --dev

# Verification - single command for all quality checks
verify: verify-code verify-chart ## Run all verification steps (code + chart tests)
	@echo ""
	@echo "✅ All modules verified successfully!"

verify-code: ## Run verification for all Python modules
	@echo "🔍 Running full verification suite for all modules..."
	@echo "================================================"
	@cd control-plane && $(MAKE) verify
	@cd mcp-operator && $(MAKE) verify
	@cd universal-adapter && $(MAKE) verify
	@cd rbac-controller && $(MAKE) verify



# Helm Chart Testing
verify-chart: ## Run Helm chart unit tests
	@echo "🧪 Running Helm chart tests..."
	@./scripts/test-chart.sh

test-chart: verify-chart ## Alias for verify-chart

test-chart-verbose: ## Run Helm chart tests with verbose output
	@echo "🧪 Running Helm chart tests (verbose)..."
	@./scripts/test-chart.sh -v

lint-chart: ## Lint Helm chart
	@echo "🔍 Linting Helm chart..."
	@helm lint chart/

# Backwards compatibility alias
check: verify ## Alias for verify (backwards compatibility)

# Docker
docker-build: docker-build-control-plane docker-build-operator docker-build-universal-adapter docker-build-rbac-controller ## Build all Docker images
	@echo "✅ All Docker images built"

docker-build-control-plane: ## Build control plane Docker image
	@echo "🐳 Building control plane Docker image..."
	@cd control-plane && docker build -t nimbletools-control-plane .

docker-build-operator: ## Build operator Docker image
	@echo "🐳 Building operator Docker image..."
	@cd mcp-operator && docker build -t nimbletools-operator .

docker-build-universal-adapter: ## Build universal adapter Docker image
	@echo "🐳 Building universal adapter Docker image..."
	@cd universal-adapter && docker build -t nimbletools-universal-adapter .

docker-build-rbac-controller: ## Build rbac controller Docker image
	@echo "🐳 Building rbac controller Docker image..."
	@cd rbac-controller && docker build -t nimbletools-rbac-controller .

docker-dev: docker-dev-control-plane docker-dev-operator docker-dev-universal-adapter docker-dev-rbac-controller ## Build and push all Docker images with dev tag
	@echo "✅ All Docker images built and pushed with dev tag"

docker-dev-control-plane: ## Build and push control plane Docker image with dev tag
	@echo "🐳 Building and pushing control plane Docker image with dev tag..."
	@cd control-plane && docker buildx build --platform linux/amd64,linux/arm64 -t nimbletools/control-plane:dev --push .

docker-dev-operator: ## Build and push operator Docker image with dev tag
	@echo "🐳 Building and pushing operator Docker image with dev tag..."
	@cd mcp-operator && docker buildx build --platform linux/amd64,linux/arm64 -t nimbletools/mcp-operator:dev --push .

docker-dev-universal-adapter: ## Build and push universal adapter Docker image with dev tag
	@echo "🐳 Building and pushing universal adapter Docker image with dev tag..."
	@cd universal-adapter && docker buildx build --platform linux/amd64,linux/arm64 -t nimbletools/universal-adapter:dev --push .

docker-dev-rbac-controller: ## Build and push rbac controller Docker image with dev tag
	@echo "🐳 Building and pushing rbac controller Docker image with dev tag..."
	@cd rbac-controller && docker buildx build --platform linux/amd64,linux/arm64 -t nimbletools/rbac-controller:dev --push .

# Cleanup
clean: clean-control-plane clean-operator clean-universal-adapter clean-rbac-controller ## Clean all generated files
	@echo "✅ All cleanup completed"

clean-control-plane: ## Clean control plane generated files
	@echo "🧹 Cleaning control plane..."
	@cd control-plane && $(MAKE) clean

clean-operator: ## Clean operator generated files
	@echo "🧹 Cleaning operator..."
	@cd mcp-operator && $(MAKE) clean

clean-universal-adapter: ## Clean universal adapter generated files
	@echo "🧹 Cleaning universal adapter..."
	@cd universal-adapter && $(MAKE) clean

clean-rbac-controller: ## Clean rbac controller generated files
	@echo "🧹 Cleaning rbac controller..."
	@cd rbac-controller && $(MAKE) clean

# Development shortcuts
dev-setup: install ## Set up development environment
	@echo "🚀 Development environment ready!"
	@echo "Available commands:"
	@echo "  make verify     - Run all quality checks"
	@echo "  make install    - Install all dependencies"
	@echo "  make build-local - Build Docker images locally"

# Get version from VERSION file
VERSION := $(shell cat VERSION 2>/dev/null || echo "0.1.0")
CHART_NAME := nimbletools-core
REGISTRY := ghcr.io/nimblebraininc
DOCKER_REGISTRY := docker.io

# Build and deployment
build-local: ## Build images for local k3d cluster
	@echo "🔨 Building images for local development..."
	./scripts/build-images.sh --local

build-production: ## Build multi-platform images (does not push)
	@echo "🔨 Building production images..."
	./scripts/build-images.sh --platforms linux/amd64,linux/arm64

install-k8s: ## Install NimbleTools Core to Kubernetes
	@echo "🚀 Installing NimbleTools Core..."
	./install.sh

install-k8s-local: ## Install with local images
	@echo "🚀 Installing with local images..."
	./install.sh --local

uninstall-k8s: ## Uninstall NimbleTools Core
	@echo "🗑️  Uninstalling NimbleTools Core..."
	./scripts/uninstall.sh

# Publishing commands
publish-images: ## Build and push Docker images to Docker Hub
	@echo "🚀 Publishing Docker images to $(DOCKER_REGISTRY)..."
	@echo "Version: $(VERSION)"
	@echo
	@echo "🚨 This will push images to Docker Hub!"
	@read -p "Continue? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	@echo
	./scripts/build-images.sh --production

publish-chart: dist ## Package and push Helm chart to GHCR
	@echo "📦 Publishing Helm chart to $(REGISTRY)..."
	@echo "Chart: $(CHART_NAME)"
	@echo "Version: $(VERSION)"
	@echo
	@echo "🚨 This will push the chart to GitHub Container Registry!"
	@read -p "Continue? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	@echo
	@echo "📦 Packaging Helm chart..."
	helm package chart/ --destination ./dist/
	@echo
	@echo "🚀 Pushing chart to registry..."
	helm push dist/$(CHART_NAME)-$(VERSION).tgz oci://$(REGISTRY)/charts
	@echo
	@echo "✅ Chart published successfully!"
	@echo "   Registry: oci://$(REGISTRY)/charts/$(CHART_NAME):$(VERSION)"

publish: publish-images publish-chart ## Publish both images and chart
	@echo
	@echo "🎉 Everything published successfully!"
	@echo
	@echo "📋 Published:"
	@echo "   Docker images: $(DOCKER_REGISTRY)/nimbletools/*:$(VERSION)"
	@echo "   Helm chart: oci://$(REGISTRY)/charts/$(CHART_NAME):$(VERSION)"
	@echo
	@echo "Next steps:"
	@echo "1. Test remote installation:"
	@echo "   curl -sSL https://raw.githubusercontent.com/nimblebrain/nimbletools-core/main/install.sh | bash"
	@echo
	@echo "2. Update documentation with new version: $(VERSION)"

# Prerequisites check
check-publish: ## Check prerequisites for publishing
	@echo "📋 Checking prerequisites for publishing..."
	@echo
	@echo "🐳 Docker Hub login status:"
	@if cat ~/.docker/config.json 2>/dev/null | jq -r '.auths | keys[]' 2>/dev/null | grep -q "https://index.docker.io/v1/"; then echo "✅ Logged in to Docker Hub"; else echo "❌ Not logged in to Docker Hub. Run: docker login"; fi
	@echo
	@echo "📦 GitHub Container Registry login status:"
	@if cat ~/.docker/config.json 2>/dev/null | jq -r '.auths | keys[]' 2>/dev/null | grep -q "ghcr.io"; then echo "✅ Logged in to GHCR"; else echo "❌ Not logged in to GHCR. Run: docker login ghcr.io"; fi
	@echo
	@echo "📋 Version info:"
	@echo "   Current version: $(VERSION)"
	@echo "   Chart path: chart/Chart.yaml"
	@test -f chart/Chart.yaml && echo "✅ Chart found" || echo "❌ Chart not found"
	@echo

# Version management
version: ## Show current version
	@echo "Current version: $(VERSION)"

# Utility targets
dist:
	mkdir -p dist

# Cleanup - extend existing clean
clean-dist: ## Clean build artifacts
	@echo "🧹 Cleaning build artifacts..."
	rm -rf dist/
	
clean-docker: ## Clean up Docker images
	@echo "🧹 Cleaning up Docker images..."
	docker images | grep nimbletools | awk '{print $$3}' | xargs docker rmi -f || true

# Git tagging
tag: ## Create and push git tag for current version
	@echo "🏷️  Creating git tag v$(VERSION)..."
	@if git tag | grep -q "v$(VERSION)"; then \
		echo "❌ Tag v$(VERSION) already exists"; \
		exit 1; \
	fi
	@git tag -a v$(VERSION) -m "Release v$(VERSION)"
	@git push origin v$(VERSION)
	@echo "✅ Git tag v$(VERSION) created and pushed"

github-release: ## Create GitHub release (requires gh CLI)
	@echo "📝 Creating GitHub release v$(VERSION)..."
	@if ! command -v gh >/dev/null 2>&1; then \
		echo "❌ GitHub CLI (gh) not found. Install: https://cli.github.com/"; \
		exit 1; \
	fi
	@gh release create v$(VERSION) \
		--title "v$(VERSION)" \
		--notes "Release v$(VERSION) - See [CHANGELOG.md](CHANGELOG.md) for details." \
		--verify-tag
	@echo "✅ GitHub release v$(VERSION) created"

# Release workflow
release: check clean-dist check-publish tag publish ## Complete release workflow
	@echo
	@echo "🎉 Release $(VERSION) complete!"
	@echo
	@echo "📋 What was released:"
	@echo "   Git tag: v$(VERSION)"
	@echo "   Docker images: $(DOCKER_REGISTRY)/nimbletools/*:$(VERSION)"
	@echo "   Helm chart: oci://$(REGISTRY)/charts/$(CHART_NAME):$(VERSION)"
	@echo
	@echo "🔍 Verification steps:"
	@echo "1. Check GitHub releases: https://github.com/NimbleBrainInc/nimbletools-core/releases"
	@echo "2. Check Docker Hub: https://hub.docker.com/r/nimbletools"
	@echo "3. Check GHCR: https://github.com/NimbleBrainInc/nimbletools-core/pkgs/container/charts%2F$(CHART_NAME)"
	@echo "4. Test installation: curl -sSL https://raw.githubusercontent.com/NimbleBrainInc/nimbletools-core/refs/heads/main/install.sh | bash"

# Version Management
update-version: ## Update all version references from VERSION file
	@echo "📝 Updating all versions from VERSION file..."
	@./scripts/update-versions.sh
	@echo "✅ Version update complete"

set-version: ## Set a new version (usage: make set-version VERSION=0.3.0)
	@echo "Setting version to $(VERSION)..."
	@echo "$(VERSION)" > VERSION
	@$(MAKE) update-version
