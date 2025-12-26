# MCPB Base Images

Pre-built container images for running MCPB bundles. These minimal images download and execute MCPB bundles at startup, providing fast cold-starts with vendored dependencies.

## Runtime Types

MCPB supports four runtime types, each optimized for different MCP server architectures:

| Runtime | Image | Transport | Use Case |
|---------|-------|-----------|----------|
| `python:X.Y` | `mcpb-python:X.Y` | HTTP native | Python servers with built-in HTTP (FastMCP, uvicorn) |
| `node:X` | `mcpb-node:X` | HTTP native | Node.js servers with built-in HTTP |
| `supergateway-python:X.Y` | `mcpb-supergateway-python:X.Y` | stdio → HTTP | Python servers using stdio transport (wrapped via supergateway) |
| `binary` | `mcpb-binary:latest` | HTTP native | Pre-compiled executables (Go, Rust, etc.) |

## Choosing a Runtime

```
Does your MCP server use stdio transport?
├── Yes → Use supergateway-python (wraps stdio as HTTP)
└── No (HTTP native)
    ├── Python → Use python:3.14
    ├── Node.js → Use node:24
    └── Compiled binary → Use binary
```

**Quick reference:**

| Server Type | Runtime | Example |
|-------------|---------|---------|
| FastMCP (Python) | `python:3.14` | Most Python MCP servers |
| Express/Fastify (Node) | `node:24` | Node.js HTTP servers |
| Python stdio server | `supergateway-python:3.14` | Legacy stdio-based Python tools |
| Go binary | `binary` | Compiled Go MCP servers |
| Rust binary | `binary` | Compiled Rust MCP servers |

## Supported Versions

### Python (HTTP native)

| Image | Versions | Default |
|-------|----------|---------|
| `nimbletools/mcpb-python` | 3.12, 3.13, 3.14 | 3.14 |

For Python servers that expose HTTP directly (e.g., FastMCP with uvicorn).

### Node.js (HTTP native)

| Image | Versions | Default |
|-------|----------|---------|
| `nimbletools/mcpb-node` | 20, 22, 24 | 24 |

For Node.js servers that expose HTTP directly.

### Supergateway (stdio → HTTP wrapper)

| Image | Python Versions | Node Version |
|-------|-----------------|--------------|
| `nimbletools/mcpb-supergateway-python` | 3.12, 3.13, 3.14 | 22 (fixed) |

For Python MCP servers that use **stdio transport**. Supergateway wraps the stdio interface and exposes it as HTTP with `/health` and `/mcp` endpoints.

### Binary (pre-compiled executables)

| Image | Tag |
|-------|-----|
| `nimbletools/mcpb-binary` | latest |

For pre-compiled MCP server binaries (Go, Rust, C++, etc.). Minimal Debian-based image with only curl for bundle download.

## Environment Variables

All runtimes support these environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BUNDLE_URL` | Yes | - | URL to download .mcpb bundle |
| `BUNDLE_SHA256` | No | - | SHA256 hash for integrity verification |
| `BUNDLE_DIR` | No | `/tmp/bundle` | Directory to extract bundle |
| `PORT` | No | `8000` | HTTP server port |

## Usage Examples

### Python (HTTP native)

```bash
docker run -p 8000:8000 \
  -e BUNDLE_URL=https://github.com/org/mcp-server/releases/download/v1.0.0/mcp-server-v1.0.0-linux-amd64.mcpb \
  -e BUNDLE_SHA256=abc123... \
  nimbletools/mcpb-python:3.14
```

Bundle `manifest.json` for HTTP Python servers:
```json
{
  "name": "my-server",
  "version": "1.0.0",
  "server": {
    "entry_point": "server/main.py"
  }
}
```

The entrypoint runs: `python -m uvicorn server.main:app --host 0.0.0.0 --port 8000`

### Node.js (HTTP native)

```bash
docker run -p 8000:8000 \
  -e BUNDLE_URL=https://github.com/org/mcp-server/releases/download/v1.0.0/mcp-server-v1.0.0-linux-amd64.mcpb \
  nimbletools/mcpb-node:24
```

Bundle `manifest.json` for HTTP Node servers:
```json
{
  "name": "my-server",
  "version": "1.0.0",
  "server": {
    "entry_point": "dist/index.js"
  }
}
```

The entrypoint runs: `node dist/index.js`

### Supergateway (stdio wrapper)

```bash
docker run -p 8000:8000 \
  -e BUNDLE_URL=https://github.com/org/mcp-stdio-server/releases/download/v1.0.0/mcp-stdio-v1.0.0-linux-amd64.mcpb \
  nimbletools/mcpb-supergateway-python:3.14
```

Bundle `manifest.json` for stdio servers (uses `mcp_config`):
```json
{
  "name": "my-stdio-server",
  "version": "1.0.0",
  "server": {
    "mcp_config": {
      "command": "python",
      "args": ["-m", "my_server"]
    }
  }
}
```

Supergateway wraps the stdio command and exposes:
- `/health` - Health check endpoint
- `/mcp` - MCP protocol endpoint (StreamableHTTP)

### Binary (pre-compiled)

```bash
docker run -p 8000:8000 \
  -e BUNDLE_URL=https://github.com/org/mcp-go-server/releases/download/v1.0.0/mcp-go-v1.0.0-linux-amd64.mcpb \
  nimbletools/mcpb-binary:latest
```

Bundle `manifest.json` for binary servers:
```json
{
  "name": "my-go-server",
  "version": "1.0.0",
  "server": {
    "mcp_config": {
      "command": "${__dirname}/bin/server",
      "args": ["--port", "8000"]
    }
  }
}
```

The `${__dirname}` placeholder is replaced with the bundle directory at runtime.

## Local Development

### Build with Makefile

```bash
# From repo root
make base-images           # Build python and node (default)
make base-images-python    # Build Python 3.12, 3.13, 3.14
make base-images-node      # Build Node 20, 22, 24
make base-images-supergateway  # Build Supergateway images
make base-images-binary    # Build binary image
make base-images-import    # Import all to local k3d cluster

# From base-images directory
cd base-images
make python-3.13              # Build specific Python version
make node-22                  # Build specific Node version
make supergateway-python-3.14 # Build specific Supergateway version
make binary                   # Build binary image
make all supergateway binary import-k3d  # Build all and import
```

### Build manually

```bash
# Python
cd base-images/python
docker build --build-arg PYTHON_VERSION=3.14 -t mcpb-python:3.14 .

# Node.js
cd base-images/node
docker build --build-arg NODE_VERSION=24 -t mcpb-node:24 .

# Supergateway
cd base-images/supergateway
docker build --build-arg PYTHON_VERSION=3.14 -t mcpb-supergateway-python:3.14 .

# Binary
cd base-images/binary
docker build -t mcpb-binary:latest .
```

### Verify health

```bash
curl http://localhost:8000/health
```

### Test MCP endpoint

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## Startup Flow

### HTTP Native (Python/Node)

1. Container starts, `entrypoint.sh` runs
2. `mcpb-loader` downloads bundle from `BUNDLE_URL`
3. If `BUNDLE_SHA256` provided, verifies hash
4. Extracts bundle to `BUNDLE_DIR`
5. Reads `manifest.json` for `server.entry_point`
6. Sets module path (`PYTHONPATH` or `NODE_PATH`) to include vendored deps
7. Starts HTTP server on `PORT`
8. Health check passes at `/health`

### Supergateway (stdio wrapper)

1. Container starts, `entrypoint.sh` runs
2. `mcpb-loader` downloads and extracts bundle
3. Reads `manifest.json` for `server.mcp_config.command` and `args`
4. Sets `PYTHONPATH` for vendored deps
5. Starts supergateway with the stdio command
6. Supergateway exposes `/health` and `/mcp` endpoints on `PORT`

### Binary

1. Container starts, `entrypoint.sh` runs
2. Downloads bundle via curl
3. Verifies SHA256 if provided
4. Extracts tarball to `BUNDLE_DIR`
5. Reads `manifest.json` for `server.mcp_config.command` and `args`
6. Replaces `${__dirname}` placeholders with bundle path
7. Makes binary executable and runs it

## Image Contents

These are **minimal images** containing only:

| Image Type | Contents |
|------------|----------|
| Python | Python runtime, `mcpb-loader.py`, `entrypoint.sh` |
| Node | Node.js runtime, `mcpb-loader.js`, `entrypoint.sh` |
| Supergateway | Python + Node.js, supergateway npm package, `mcpb-loader.py` |
| Binary | Debian slim, curl, `entrypoint.sh` |

**All application dependencies are vendored inside the MCPB bundle** in the `deps/` (Python) or `node_modules/` (Node) directory.

## Multi-Architecture Support

All images are built for both `linux/amd64` and `linux/arm64`. The GitHub Actions workflow handles multi-arch builds automatically.

For local multi-arch builds:

```bash
# Create builder (one time)
docker buildx create --name multiarch --use

# Build and push
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --build-arg PYTHON_VERSION=3.14 \
  --tag nimbletools/mcpb-python:3.14 \
  --push \
  ./python
```

## Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `HTTP 404` on download | Wrong bundle URL | Verify GitHub Release exists and URL is correct |
| `SHA256 mismatch` | Wrong hash or corruption | Ensure hash matches the architecture-specific bundle |
| `ModuleNotFoundError` | Missing vendored deps | Include all deps in `deps/` (Python) or `node_modules/` (Node) |
| `connection refused` on health | Server not listening | Check PORT matches, verify /health endpoint exists |
| `supergateway: command not found` | Wrong image | Use `mcpb-supergateway-python`, not `mcpb-python` |
| Binary not executable | Permission issue | Bundle should include executable with proper permissions |

## See Also

- [MCPB Base Images Spec](../docs/MCPB_BASE_IMAGES.md) - Detailed architecture
- [Architecture Guide](../docs/ARCHITECTURE.md) - Overall platform architecture
- [MCPB Specification](https://github.com/modelcontextprotocol/mcpb) - Official spec
