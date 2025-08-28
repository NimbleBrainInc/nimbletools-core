# Publishing Guide

This guide covers how to publish NimbleTools Core for production use. The publishing process involves building and pushing Docker images to Docker Hub and publishing the Helm chart to GitHub Container Registry (GHCR).

## Quick Start

```bash
# Check prerequisites
make check-publish

# Login to registries (see Prerequisites section below)
docker login
echo $GITHUB_TOKEN | helm registry login ghcr.io -u YOUR_USERNAME --password-stdin

# Publish everything
make publish
```

## Prerequisites

### Required Tools

- **Docker**: For building and pushing images
- **Helm 3.0+**: For packaging and publishing charts
- **Make**: For running build commands

### Registry Access

#### Docker Hub

```bash
# Login to Docker Hub
docker login

# Verify login
docker system info | grep Username
```

#### GitHub Container Registry (GHCR)

```bash
# Create GitHub Personal Access Token with packages:write scope
# https://github.com/settings/tokens

# Login to GHCR
echo $GITHUB_TOKEN | helm registry login ghcr.io -u YOUR_USERNAME --password-stdin

# Verify login
helm registry login ghcr.io --dry-run
```

### Check Prerequisites

```bash
make check-publish
```

This command will show you:

- Docker Hub login status
- GHCR login status
- Current version from chart
- Chart availability

## Publishing Commands

### Individual Components

```bash
# Publish only Docker images
make publish-images

# Publish only Helm chart
make publish-chart
```

### Complete Publishing

```bash
# Publish both images and chart
make publish

# Complete release workflow (includes checks)
make release
```

## What Gets Published

### Docker Images → Docker Hub

All images are built for multiple platforms (`linux/amd64,linux/arm64`):

- `docker.io/nimbletools/universal-adapter:VERSION`
- `docker.io/nimbletools/universal-adapter:latest`
- `docker.io/nimbletools/mcp-operator:VERSION`
- `docker.io/nimbletools/mcp-operator:latest`
- `docker.io/nimbletools/control-plane:VERSION`
- `docker.io/nimbletools/control-plane:latest`
- `docker.io/nimbletools/rbac-controller:VERSION`
- `docker.io/nimbletools/rbac-controller:latest`

### Helm Chart → GitHub Container Registry

- `oci://ghcr.io/nimblebrain/charts/nimbletools-core:VERSION`

The version is automatically read from `chart/Chart.yaml`.

## Release Process

### 1. Pre-Release Checks

```bash
# Run all quality checks
make check

# Check publishing prerequisites
make check-publish

# View current version
make version
```

### 2. Update Version (if needed)

Edit `chart/Chart.yaml`:

```yaml
version: "1.1.0" # Chart version
appVersion: "1.1.0" # Application version
```

### 3. Build and Test Locally

```bash
# Build local images
make build-local

# Install locally for testing
make install-k8s-local

# Test the installation
kubectl get pods -n nimbletools-system
curl http://api.nimbletools.local/health
```

### 4. Publish

```bash
# Complete release workflow
make release
```

This will:

1. Run quality checks
2. Clean build artifacts
3. Check publishing prerequisites
4. Create and push Git tag
5. Publish Docker images
6. Publish Helm chart
7. Show verification steps

### 5. Verify Release

After publishing, verify the release:

#### Check Docker Hub

- Visit: https://hub.docker.com/r/nimbletools
- Verify all 4 images are published with correct tags

#### Check GitHub Container Registry

- Visit: https://github.com/nimblebrain/nimbletools-core/pkgs/container/charts%2Fnimbletools-core
- Verify chart package is available

#### Test Remote Installation

```bash
# Test installation from published artifacts
curl -sSL https://raw.githubusercontent.com/nimblebrain/nimbletools-core/main/install.sh | bash
```

## Troubleshooting

### Docker Hub Issues

**Problem**: `unauthorized: authentication required`

```bash
# Solution: Login to Docker Hub
docker login
```

**Problem**: `denied: requested access to the resource is denied`

```bash
# Solution: Verify you have push access to nimbletools organization
# Or update DOCKER_REGISTRY in Makefile to use your namespace
```

### GHCR Issues

**Problem**: `Error: failed to authorize: failed to fetch oauth token`

```bash
# Solution: Login to GHCR with proper token (use your PAT)
docker login ghcr.io
```

**Problem**: `Error: failed to push: insufficient_scope: authorization failed`

```bash
# Solution: Ensure GitHub token has packages:write scope
# Recreate token at: https://github.com/settings/tokens
```

### Build Issues

**Problem**: `buildx: command not found`

```bash
# Solution: Enable Docker buildx
docker buildx create --use
```

**Problem**: Build fails for ARM64 platform

```bash
# Solution: Build for single platform temporarily
make build-production PLATFORMS=linux/amd64
```

## Configuration

### Registry Settings

Edit `Makefile` to customize registry settings:

```makefile
# Docker image registry
DOCKER_REGISTRY := docker.io

# Helm chart registry
REGISTRY := ghcr.io/nimblebrain

# Chart name
CHART_NAME := nimbletools-core
```

### Custom Namespace

To publish under your own namespace:

```makefile
DOCKER_REGISTRY := docker.io/mycompany
REGISTRY := ghcr.io/mycompany
```

## Automation

### GitHub Actions

For automated publishing, create `.github/workflows/release.yml`:

```yaml
name: Release
on:
  push:
    tags: ["v*"]
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - name: Setup
        run: |
          docker login -u ${{ secrets.DOCKER_USERNAME }} -p ${{ secrets.DOCKER_PASSWORD }}
          echo ${{ secrets.GITHUB_TOKEN }} | helm registry login ghcr.io -u ${{ github.actor }} --password-stdin
      - name: Release
        run: make release
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Manual Release Tags

The `make release` command automatically creates Git tags, but you can also create them manually:

```bash
# Create tag manually
make tag

# Or using Git directly
git tag v1.0.0
git push origin v1.0.0

# Create GitHub release (optional, requires gh CLI)
make github-release

# Or create via GitHub UI
# https://github.com/nimblebrain/nimbletools-core/releases/new
```

## Security Considerations

### Image Signing

Consider signing your images for enhanced security:

```bash
# Install cosign
# https://docs.sigstore.dev/cosign/installation/

# Sign images after publishing
cosign sign docker.io/nimbletools/control-plane:1.0.0
```

### Vulnerability Scanning

Scan images before publishing:

```bash
# Using Docker Scout
docker scout quickview nimbletools/control-plane:1.0.0

# Using trivy
trivy image nimbletools/control-plane:1.0.0
```

## Support

For publishing issues:

1. Check this guide first
2. Review [GitHub Issues](https://github.com/nimblebrain/nimbletools-core/issues)
3. Create a new issue with:
   - Output of `make check-publish`
   - Error messages
   - Steps to reproduce
