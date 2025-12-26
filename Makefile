# NimbleTools Core - Root Makefile
.PHONY: help install verify clean dev dev-verify dev-build dev-deploy dev-smoke dev-quick dev-status dev-bump publish release base-images

# Version from VERSION file
VERSION := $(shell cat VERSION 2>/dev/null || echo "0.1.0")
CHART_NAME := nimbletools-core
REGISTRY := ghcr.io/nimblebraininc
DOCKER_REGISTRY := docker.io

# Default target
help: ## Show this help message
	@echo "NimbleTools Core - Development Commands"
	@echo "========================================"
	@echo ""
	@echo "Development Workflow:"
	@grep -E '^dev[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Testing & Quality:"
	@grep -E '^(verify|install|clean)[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Base Images (MCPB):"
	@grep -E '^base-images[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Publishing & Release:"
	@grep -E '^(publish|release|tag|version)[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# =============================================================================
# Development Workflow (primary interface)
# =============================================================================

dev: ## Full development cycle: verify -> build -> deploy -> smoke test
	@./scripts/dev.sh all

dev-verify: ## Run all tests (unit, lint, type-check, helm)
	@./scripts/dev.sh verify

dev-build: ## Build images for local k3d
	@./scripts/dev.sh build

dev-deploy: ## Deploy to local k3d cluster
	@./scripts/dev.sh deploy

dev-smoke: ## Run end-to-end smoke tests
	@./scripts/dev.sh smoke

dev-quick: ## Quick rebuild and deploy (skip tests)
	@./scripts/dev.sh quick

dev-status: ## Show development environment status
	@./scripts/dev.sh status

dev-bump: ## Bump version (usage: make dev-bump VERSION=0.3.0)
	@./scripts/dev.sh bump $(VERSION)

# =============================================================================
# Testing & Quality
# =============================================================================

install: ## Install all component dependencies
	@echo "Installing dependencies for all components..."
	@cd control-plane && uv sync --dev
	@cd mcp-operator && uv sync --dev
	@cd rbac-controller && uv sync --dev
	@echo "All dependencies installed"

verify: verify-code verify-chart ## Run all verification (code + chart tests)
	@echo ""
	@echo "All modules verified successfully!"

verify-code: ## Run verification for all Python modules
	@echo "Running verification suite for all modules..."
	@cd control-plane && $(MAKE) verify
	@cd mcp-operator && $(MAKE) verify
	@cd rbac-controller && $(MAKE) verify

verify-chart: ## Run Helm chart unit tests
	@echo "Running Helm chart tests..."
	@./scripts/test-chart.sh

clean: ## Clean all generated files
	@echo "Cleaning all components..."
	@cd control-plane && $(MAKE) clean
	@cd mcp-operator && $(MAKE) clean
	@cd rbac-controller && $(MAKE) clean
	@rm -rf dist/
	@echo "Cleanup completed"

# =============================================================================
# Version Management
# =============================================================================

version: ## Show current version
	@echo "Current version: $(VERSION)"

set-version: ## Set a new version (usage: make set-version VERSION=0.3.0)
	@echo "Setting version to $(VERSION)..."
	@echo "$(VERSION)" > VERSION
	@./scripts/update-versions.sh
	@echo "Version updated to $(VERSION)"

# =============================================================================
# Publishing & Release (production)
# =============================================================================

dev-publish: ## Push development images to Docker Hub (appends -dev suffix)
	@echo "Publishing development images to $(DOCKER_REGISTRY)..."
	@echo "Version: $(VERSION)-dev"
	@echo ""
	@echo "This will push development images to Docker Hub."
	@echo "The 'latest' tag will NOT be updated."
	@read -p "Continue? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	@./scripts/build-images.sh --production --tag $(VERSION)-dev --no-latest

publish-images: ## Build and push stable Docker images to Docker Hub
	@echo "Publishing Docker images to $(DOCKER_REGISTRY)..."
	@echo "Version: $(VERSION)"
	@echo ""
	@echo "This will push images to Docker Hub!"
	@read -p "Continue? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	@./scripts/build-images.sh --production

publish-chart: ## Package and push Helm chart to GHCR
	@mkdir -p dist
	@echo "Publishing Helm chart to $(REGISTRY)..."
	@echo "Version: $(VERSION)"
	@echo ""
	@echo "This will push the chart to GitHub Container Registry!"
	@read -p "Continue? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	@helm package chart/ --destination ./dist/
	@helm push dist/$(CHART_NAME)-$(VERSION).tgz oci://$(REGISTRY)/charts
	@echo "Chart published: oci://$(REGISTRY)/charts/$(CHART_NAME):$(VERSION)"

publish: publish-images publish-chart ## Publish both images and chart

tag: ## Create and push git tag for current version
	@echo "Creating git tag v$(VERSION)..."
	@if git tag | grep -q "v$(VERSION)"; then \
		echo "Tag v$(VERSION) already exists"; \
		exit 1; \
	fi
	@git tag -a v$(VERSION) -m "Release v$(VERSION)"
	@git push origin v$(VERSION)
	@echo "Git tag v$(VERSION) created and pushed"

github-release: ## Create GitHub release for current version
	@echo "Creating GitHub release v$(VERSION)..."
	@gh release create v$(VERSION) --title "v$(VERSION)" --generate-notes
	@echo "GitHub release v$(VERSION) created"

release: verify tag publish github-release ## Complete release workflow (verify, tag, publish, github release)
	@echo ""
	@echo "Release $(VERSION) complete!"
	@echo ""
	@echo "Published:"
	@echo "  Git tag: v$(VERSION)"
	@echo "  GitHub release: https://github.com/NimbleBrainInc/nimbletools-core/releases/tag/v$(VERSION)"
	@echo "  Docker images: $(DOCKER_REGISTRY)/nimbletools/*:$(VERSION)"
	@echo "  Helm chart: oci://$(REGISTRY)/charts/$(CHART_NAME):$(VERSION)"

# =============================================================================
# Base Images (MCPB runtime)
# =============================================================================

base-images: ## Build default MCPB base images (Python + Node)
	@cd base-images && $(MAKE) all

base-images-python: ## Build Python base images (3.12, 3.13, 3.14)
	@cd base-images && $(MAKE) python

base-images-node: ## Build Node.js base images (20, 22, 24)
	@cd base-images && $(MAKE) node

base-images-supergateway: ## Build Supergateway images (stdio→HTTP wrapper)
	@cd base-images && $(MAKE) supergateway

base-images-binary: ## Build binary image (for Go, Rust executables)
	@cd base-images && $(MAKE) binary

base-images-all: ## Build ALL base images (python, node, supergateway, binary)
	@cd base-images && $(MAKE) all supergateway binary

base-images-import: ## Import base images to local k3d cluster
	@cd base-images && $(MAKE) import-k3d

base-images-clean: ## Remove local base images
	@cd base-images && $(MAKE) clean
