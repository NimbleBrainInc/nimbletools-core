# Release Process

## Quick Start

```bash
make check-publish    # Check prerequisites
make set-version VERSION=x.y.z
make release          # Full release: verify, tag, publish
```

## Version Management

### Single Source of Truth

The `VERSION` file at repository root controls all version numbers:
- Docker image tags
- Helm chart version and appVersion

### Version Format

- Development: `x.y.z-dev`
- Release candidates: `x.y.z-rc.n`
- Production: `x.y.z`

### Commands

| Command | Description |
|---------|-------------|
| `make version` | Show current version |
| `make set-version VERSION=x.y.z` | Set version and sync all files |
| `make check-publish` | Check registry login status |
| `make publish-images` | Push Docker images only |
| `make publish-chart` | Push Helm chart only |
| `make publish` | Push images and chart |
| `make release` | Full release (verify, tag, publish) |
| `make github-release` | Create GitHub release (requires gh CLI) |

## Prerequisites

### Registry Access

```bash
# Docker Hub
docker login

# GitHub Container Registry (for Helm chart)
echo $GITHUB_TOKEN | helm registry login ghcr.io -u YOUR_USERNAME --password-stdin
```

GitHub token needs `packages:write` scope: https://github.com/settings/tokens

## What Gets Published

### Docker Images (Docker Hub)

All images built for `linux/amd64,linux/arm64`:

- `docker.io/nimbletools/universal-adapter:VERSION`
- `docker.io/nimbletools/mcp-operator:VERSION`
- `docker.io/nimbletools/control-plane:VERSION`
- `docker.io/nimbletools/rbac-controller:VERSION`

Each also tagged `:latest`.

### Helm Chart (GHCR)

- `oci://ghcr.io/nimblebraininc/charts/nimbletools-core:VERSION`

## Release Workflow

### Development (Core Only)

```bash
make dev              # verify -> build -> deploy -> smoke test
make dev-quick        # skip tests
```

### Development (With Enterprise)

```bash
make set-version VERSION=0.3.0
make dev-publish      # Push nimbletools/*:0.3.0-dev
```

### Production Release

```bash
make set-version VERSION=1.0.0
make verify
make release          # Creates tag, publishes images + chart
make github-release   # Optional: create GitHub release
```

## Troubleshooting

### Docker Hub

**`unauthorized: authentication required`**
```bash
docker login
```

**`denied: requested access to the resource is denied`**
- Verify push access to nimbletools organization

### GHCR

**`failed to authorize: failed to fetch oauth token`**
```bash
docker login ghcr.io
```

**`insufficient_scope: authorization failed`**
- Ensure GitHub token has `packages:write` scope

### Build

**`buildx: command not found`**
```bash
docker buildx create --use
```

**ARM64 build fails**
```bash
make build-production PLATFORMS=linux/amd64
```

## Configuration

### Custom Registry

Edit `Makefile`:

```makefile
DOCKER_REGISTRY := docker.io/mycompany
REGISTRY := ghcr.io/mycompany
```

## GitHub Actions

For automated releases on tag push:

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
```

## Security

### Image Signing (Optional)

```bash
cosign sign docker.io/nimbletools/control-plane:1.0.0
```

### Vulnerability Scanning

```bash
docker scout quickview nimbletools/control-plane:1.0.0
# or
trivy image nimbletools/control-plane:1.0.0
```
