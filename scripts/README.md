# Scripts Directory

This directory contains utility scripts for NimbleTools Core development and maintenance.

## Scripts Overview

### Development Scripts

#### `dev-setup.sh`

Sets up a complete local development environment with k3d cluster, local Docker registry, and Python environment.

**Usage:**

```bash
./scripts/dev-setup.sh [OPTIONS]
```

**Features:**

- Creates k3d cluster with local registry
- Sets up Python virtual environment
- Builds and pushes development images
- Creates development values file
- Configures local DNS entries

**Understanding the Local Registry:**

The local Docker registry (`localhost:5000`) is only needed if you're **developing NimbleTools Core itself**. It stores custom-built images locally so you can test your changes.

**If you're just trying out NimbleTools Core:**

```bash
# Skip the registry - much simpler!
k3d cluster create nimbletools-test --wait
./install.sh
```

**If you get registry errors:**

```bash
# Skip Docker registry setup
./scripts/dev-setup.sh --skip-docker

# Or skip cluster creation and use existing
./scripts/dev-setup.sh --skip-cluster
```

**Options:**

- `--cluster-name NAME` - k3d cluster name (default: nimbletools-dev)
- `--registry-port PORT` - Local registry port (default: 5000)
- `--skip-cluster` - Skip k3d cluster creation
- `--skip-python` - Skip Python environment setup

#### `build-dev.sh`

Builds and pushes development images to the local registry.

**Usage:**

```bash
./scripts/build-dev.sh
```

**Environment Variables:**

- `REGISTRY_PORT` - Local registry port (default: 5000)
- `TAG` - Image tag (default: dev)

### Installation Scripts

#### `../install.sh` (in project root)

Main installation script for deploying NimbleTools Core to Kubernetes clusters.

**Usage:**

```bash
./install.sh [OPTIONS]
```

**Key Features:**

- 60-second deployment target
- Configurable authentication providers
- Support for custom domains and ingress
- Comprehensive verification checks

#### `uninstall.sh`

Safely removes NimbleTools Core from Kubernetes clusters with optional cleanup.

**Usage:**

```bash
./scripts/uninstall.sh [OPTIONS]
```

**Safety Features:**

- Confirmation prompts (bypass with `--force`)
- Dry run mode (`--dry-run`)
- Selective resource removal
- Verification of successful removal

**Options:**

- `--remove-crd` - Remove MCPService CRD (deletes all MCP services!)
- `--remove-namespace` - Remove the namespace
- `--force` - Skip confirmation prompts

## Development Workflow

### Initial Setup

1. **Set up development environment:**

   ```bash
   ./scripts/dev-setup.sh
   ```

2. **Install NimbleTools Core in development mode:**
   ```bash
   ./install.sh -f values-dev.yaml -n nimbletools-dev
   ```

### Development Cycle

1. **Make code changes** in `universal-adapter/`, `mcp-operator/`, or `control-plane/`

2. **Rebuild and push images:**

   ```bash
   ./scripts/build-dev.sh
   ```

3. **Upgrade deployment:**

   ```bash
   ./install.sh -f values-dev.yaml -n nimbletools-dev
   ```

4. **Test changes:**
   ```bash
   kubectl get pods -n nimbletools-dev
   curl http://api.nimbletools.dev:8080/health
   ```

### Testing and Validation

1. **Run unit tests:**

   ```bash
   source venv/bin/activate
   pytest
   ```

2. **Test with example MCP services:**
   ```bash
   kubectl apply -f examples/echo-mcp.yaml
   kubectl get mcpservices
   ```

### Cleanup

1. **Uninstall NimbleTools Core:**

   ```bash
   ./scripts/uninstall.sh -n nimbletools-dev
   ```

2. **Clean up development environment:**
   ```bash
   k3d cluster delete nimbletools-dev
   docker stop nimbletools-registry && docker rm nimbletools-registry
   ```

## Script Dependencies

### Required Tools

- **Docker Desktop** - For container builds and local registry
- **k3d** - For local Kubernetes cluster (`brew install k3d`)
- **kubectl** - For Kubernetes management
- **Helm 3.0+** - For chart installation
- **Python 3.13+** - For development environment
- **curl** - For health checks and API testing

### Environment Setup

Scripts automatically check for required dependencies and provide installation guidance when tools are missing.

## Configuration

### Environment Variables

- `REGISTRY_PORT` - Local Docker registry port (default: 5000)
- `CLUSTER_NAME` - k3d cluster name (default: nimbletools-dev)
- `TAG` - Docker image tag for development builds (default: dev)

### Development Values

The `dev-setup.sh` script creates a `values-dev.yaml` file with development-specific configurations:

- Local registry usage
- Debug logging
- NodePort services
- Reduced resource limits
- Local domain names

## Troubleshooting

### Common Issues

#### "Registry not running"

```bash
# Check registry status
docker ps | grep registry

# Restart registry if needed
docker start nimbletools-registry
```

#### "Cluster not accessible"

```bash
# Check cluster status
k3d cluster list

# Start cluster if stopped
k3d cluster start nimbletools-dev
```

#### "Image pull errors"

```bash
# Check if images exist in registry
curl http://localhost:5000/v2/_catalog

# Rebuild and push images
./scripts/build-dev.sh
```

#### "DNS resolution issues"

```bash
# Check /etc/hosts entry
grep nimbletools.local /etc/hosts

# Add entry if missing
echo "127.0.0.1 api.nimbletools.local" | sudo tee -a /etc/hosts
```

### Getting Help

Each script supports the `--help` or `-h` flag for detailed usage information:

```bash
./scripts/dev-setup.sh --help
./scripts/uninstall.sh --help
./install.sh --help
```

## Contributing

When adding new scripts:

1. Make them executable: `chmod +x script-name.sh`
2. Add comprehensive help text with `--help` flag
3. Include error handling with proper exit codes
4. Use consistent logging functions for colored output
5. Support dry-run mode for destructive operations
6. Update this README with usage information
