# CLAUDE.md

## Quick Reference

| Task | Command |
|------|---------|
| Full dev cycle | `make dev` |
| Fast iteration | `make dev-quick` |
| Run tests | `make verify` or `cd <component> && make verify` |
| Set version | `make set-version VERSION=x.y.z` |
| Dev publish | `make dev-publish` (pushes -dev images) |
| Release | `make release` |

## Critical Constraints

### No Server-Specific Logic
Platform components are generic orchestrators. All server behavior comes from registry definitions.
Never write `if server_name == "..."`. See `/docs/PLATFORM_PRINCIPLES.md`.

### No Linter Bypasses
Never use `# noqa`, `# type: ignore`, `|| true`. Fix root cause.

### Schema Sync Required
When changing MCP server schema, update ALL components together:
- `mcp_server_models.py` (Pydantic)
- `crd.yaml` (Kubernetes CRD)
- `main.py` in operator

### Use uv, Not pip
All commands: `uv run pytest`, `uv run mypy`, `uv sync --frozen`

### Absolute Imports Only
`from nimbletools_control_plane.x import y` - no relative imports

### Lazy Log Formatting
`logger.info("msg: %s", val)` - never f-strings in logging

## Development Workflows

### Core Only
```bash
make dev          # verify -> build -> deploy -> smoke test
make dev-quick    # skip tests after initial verification
```

### With Enterprise
```bash
make set-version VERSION=0.3.0
make dev-publish  # Push nimbletools/*:0.3.0-dev
# Enterprise can now build
```

### Production Release
```bash
make release      # verify, git tag, push stable images + chart
```

## Architecture

### Provider System
- Duck-typed providers (no inheritance)
- Requires `PROVIDER_CONFIG` env var
- Methods: `validate_token`, `check_workspace_access`, `check_permission`

### Auth
- Centralized in control-plane `/auth` endpoint
- Swappable for enterprise

## Documentation

All docs in `/docs`, not component directories. No temporal language.

## MCPB Base Images

Four runtime types for different MCP server architectures:

| Runtime | Versions | Use Case |
|---------|----------|----------|
| `python:X.Y` | 3.12, 3.13, **3.14** | Python HTTP servers (FastMCP, uvicorn) |
| `node:X` | 20, 22, **24** | Node.js HTTP servers |
| `supergateway-python:X.Y` | 3.12, 3.13, **3.14** | stdio servers wrapped as HTTP |
| `binary` | latest | Pre-compiled binaries (Go, Rust) |

Base image format: `nimbletools/mcpb-{runtime}:{version}`

Examples:
- `nimbletools/mcpb-python:3.14` - Python HTTP server
- `nimbletools/mcpb-node:24` - Node.js HTTP server
- `nimbletools/mcpb-supergateway-python:3.14` - stdio→HTTP wrapper
- `nimbletools/mcpb-binary:latest` - Compiled binaries

### Building Base Images Locally

```bash
make base-images           # Build Python + Node (default)
make base-images-all       # Build ALL images (python, node, supergateway, binary)
make base-images-python    # Build Python 3.12, 3.13, 3.14
make base-images-node      # Build Node 20, 22, 24
make base-images-supergateway  # Build Supergateway images
make base-images-binary    # Build binary image
make base-images-import    # Import to local k3d cluster
```

Or build specific versions:
```bash
cd base-images
make python-3.13              # Build only Python 3.13
make node-22                  # Build only Node 22
make supergateway-python-3.14 # Build Supergateway with Python 3.14
make binary                   # Build binary image
```

### Releasing Base Images (Multi-arch)

Production K8s clusters may have mixed architectures. Base images must be multi-arch (amd64 + arm64).

```bash
cd base-images
make push-multiarch-python    # Python images only
make push-multiarch           # ALL base images
```

**Note**: Multi-arch builds require `--push` during build (can't load multi-arch locally). If you see `exec format error` in K8s, the image was built for wrong architecture.

## Standards References

Read these when working on relevant tasks:
- Platform architecture: `/docs/PLATFORM_PRINCIPLES.md`
- Python/testing/API standards: `/docs/CODING_STANDARDS.md`
- Version/release workflow: `/docs/RELEASE_PROCESS.md`
- MCPB base images: `/docs/MCPB_BASE_IMAGES.md`
