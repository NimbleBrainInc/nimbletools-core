# Base Images Makefile
# Builds MCPB runtime images for Python and Node.js

REGISTRY ?= docker.io/nimbletools

# Supported versions
PYTHON_VERSIONS := 3.12 3.13 3.14
NODE_VERSIONS := 20 22 24
SUPERGATEWAY_PYTHON_VERSIONS := 3.12 3.13 3.14

# Default targets
.PHONY: all python node supergateway binary clean help

all: python node

##@ Python Images

python: $(addprefix python-,$(PYTHON_VERSIONS))

python-%:
	@echo "Building mcpb-python:$*..."
	docker build \
		--build-arg PYTHON_VERSION=$* \
		-t $(REGISTRY)/mcpb-python:$* \
		-f python/Dockerfile \
		python/

##@ Node.js Images

node: $(addprefix node-,$(NODE_VERSIONS))

node-%:
	@echo "Building mcpb-node:$*..."
	docker build \
		--build-arg NODE_VERSION=$* \
		-t $(REGISTRY)/mcpb-node:$* \
		-f node/Dockerfile \
		node/

##@ Supergateway Images (stdio-to-HTTP wrapper)

supergateway: $(addprefix supergateway-python-,$(SUPERGATEWAY_PYTHON_VERSIONS))

supergateway-python-%:
	@echo "Building mcpb-supergateway-python:$*..."
	docker build \
		--build-arg PYTHON_VERSION=$* \
		--build-arg NODE_VERSION=22 \
		-t $(REGISTRY)/mcpb-supergateway-python:$* \
		-f supergateway/Dockerfile \
		supergateway/

##@ Binary Images (for pre-compiled executables)

binary:
	@echo "Building mcpb-binary:latest..."
	docker build \
		-t $(REGISTRY)/mcpb-binary:latest \
		-f binary/Dockerfile \
		binary/

##@ Multi-arch Builds (for CI/release)

.PHONY: build-multiarch push

build-multiarch:
	@echo "Building multi-arch images..."
	@for v in $(PYTHON_VERSIONS); do \
		echo "Building mcpb-python:$$v (linux/amd64,linux/arm64)..."; \
		docker buildx build \
			--platform linux/amd64,linux/arm64 \
			--build-arg PYTHON_VERSION=$$v \
			-t $(REGISTRY)/mcpb-python:$$v \
			-f python/Dockerfile \
			python/; \
	done
	@for v in $(NODE_VERSIONS); do \
		echo "Building mcpb-node:$$v (linux/amd64,linux/arm64)..."; \
		docker buildx build \
			--platform linux/amd64,linux/arm64 \
			--build-arg NODE_VERSION=$$v \
			-t $(REGISTRY)/mcpb-node:$$v \
			-f node/Dockerfile \
			node/; \
	done
	@for v in $(SUPERGATEWAY_PYTHON_VERSIONS); do \
		echo "Building mcpb-supergateway-python:$$v (linux/amd64,linux/arm64)..."; \
		docker buildx build \
			--platform linux/amd64,linux/arm64 \
			--build-arg PYTHON_VERSION=$$v \
			--build-arg NODE_VERSION=22 \
			-t $(REGISTRY)/mcpb-supergateway-python:$$v \
			-f supergateway/Dockerfile \
			supergateway/; \
	done

push:
	@echo "Pushing all images to $(REGISTRY)..."
	@for v in $(PYTHON_VERSIONS); do \
		docker push $(REGISTRY)/mcpb-python:$$v; \
	done
	@for v in $(NODE_VERSIONS); do \
		docker push $(REGISTRY)/mcpb-node:$$v; \
	done
	@for v in $(SUPERGATEWAY_PYTHON_VERSIONS); do \
		docker push $(REGISTRY)/mcpb-supergateway-python:$$v; \
	done
	docker push $(REGISTRY)/mcpb-binary:latest

##@ k3d Import (for local development)

.PHONY: import-k3d

import-k3d:
	@echo "Importing images to k3d cluster..."
	@CLUSTER=$$(k3d cluster list -o json | jq -r '.[0].name'); \
	if [ -z "$$CLUSTER" ]; then \
		echo "No k3d cluster found"; \
		exit 1; \
	fi; \
	echo "Using cluster: $$CLUSTER"; \
	for v in $(PYTHON_VERSIONS); do \
		echo "Importing mcpb-python:$$v..."; \
		k3d image import $(REGISTRY)/mcpb-python:$$v -c $$CLUSTER; \
	done; \
	for v in $(NODE_VERSIONS); do \
		echo "Importing mcpb-node:$$v..."; \
		k3d image import $(REGISTRY)/mcpb-node:$$v -c $$CLUSTER; \
	done; \
	for v in $(SUPERGATEWAY_PYTHON_VERSIONS); do \
		echo "Importing mcpb-supergateway-python:$$v..."; \
		k3d image import $(REGISTRY)/mcpb-supergateway-python:$$v -c $$CLUSTER; \
	done; \
	echo "Importing mcpb-binary:latest..."; \
	k3d image import $(REGISTRY)/mcpb-binary:latest -c $$CLUSTER

##@ Testing

.PHONY: test test-python test-node

test: test-python test-node

test-python:
	@echo "Testing Python mcpb-loader..."
	@cd python && python3 -m pytest ../tests/test_mcpb_loader_python.py -v || true

test-node:
	@echo "Testing Node.js mcpb-loader..."
	@cd node && npm test || true

##@ Utilities

clean:
	@echo "Removing local base images..."
	@for v in $(PYTHON_VERSIONS); do \
		docker rmi $(REGISTRY)/mcpb-python:$$v 2>/dev/null || true; \
	done
	@for v in $(NODE_VERSIONS); do \
		docker rmi $(REGISTRY)/mcpb-node:$$v 2>/dev/null || true; \
	done
	@for v in $(SUPERGATEWAY_PYTHON_VERSIONS); do \
		docker rmi $(REGISTRY)/mcpb-supergateway-python:$$v 2>/dev/null || true; \
	done
	docker rmi $(REGISTRY)/mcpb-binary:latest 2>/dev/null || true

help:
	@echo "MCPB Base Images"
	@echo ""
	@echo "Supported versions:"
	@echo "  Python: $(PYTHON_VERSIONS)"
	@echo "  Node.js: $(NODE_VERSIONS)"
	@echo "  Supergateway-Python: $(SUPERGATEWAY_PYTHON_VERSIONS)"
	@echo "  Binary: latest"
	@echo ""
	@echo "Targets:"
	@echo "  all                     Build python and node images (default)"
	@echo "  python                  Build all Python images"
	@echo "  node                    Build all Node.js images"
	@echo "  supergateway            Build all Supergateway images (stdio wrapper)"
	@echo "  binary                  Build binary image (for pre-compiled executables)"
	@echo "  python-X.Y              Build specific Python version (e.g., python-3.13)"
	@echo "  node-XX                 Build specific Node version (e.g., node-22)"
	@echo "  supergateway-python-X.Y Build specific Supergateway version"
	@echo "  import-k3d              Import images to local k3d cluster"
	@echo "  test                    Run loader tests"
	@echo "  clean                   Remove local images"
	@echo ""
	@echo "Examples:"
	@echo "  make python-3.14                  # Build Python 3.14 image"
	@echo "  make node-22                      # Build Node.js 22 image"
	@echo "  make supergateway-python-3.14    # Build Supergateway with Python 3.14"
	@echo "  make binary                       # Build binary image"
	@echo "  make all supergateway import-k3d # Build all and import to k3d"
