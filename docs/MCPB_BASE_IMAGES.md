# MCPB Base Images

Minimal container images for running MCPB bundles.

## Background

MCPB bundles running on pre-built base images significantly reduce cold-start time compared to runtime package installation:

| Step | Before (Universal Adapter) | After (MCPB) |
|------|-------------------|------------|
| Pod scheduling | 2-5s | 2-5s |
| Image pull | 3-8s | 0s (pre-cached) |
| Container startup | 1-3s | 1-3s |
| Package install | 15-30s | 0s (vendored in bundle) |
| Bundle download | N/A | 2-3s |
| Bundle extract | N/A | 1s |
| Health check delay | 30s | 15s |
| **Total** | **51-76s** | **21-27s** |

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         MCPB Runtime Architecture                           │
│                                                                             │
│                    ┌──────────────────────────────────┐                    │
│                    │     MCPB Bundles (1-10MB)        │                    │
│                    │  • App code + vendored deps      │                    │
│                    │  • Hosted on GitHub Releases     │                    │
│                    │  • Architecture-specific         │                    │
│                    └───────────────┬──────────────────┘                    │
│                                    │                                        │
│                    ┌───────────────┴───────────────┐                       │
│                    ▼                               ▼                        │
│    ┌─────────────────────────────┐  ┌─────────────────────────────┐       │
│    │     HTTP Native Servers     │  │    stdio-based Servers      │       │
│    │                             │  │                             │       │
│    │  manifest.json:             │  │  manifest.json:             │       │
│    │  { server.entry_point }     │  │  { server.mcp_config }      │       │
│    └──────────────┬──────────────┘  └──────────────┬──────────────┘       │
│                   │                                │                       │
│    ┌──────────────┴──────────────┐  ┌──────────────┴──────────────┐       │
│    ▼              ▼              ▼  ▼                             ▼       │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌───────────────────┐  ┌───────┐ │
│  │ Python  │  │ Node.js │  │ Binary  │  │ Supergateway      │  │ (future│ │
│  │ :3.14   │  │ :24     │  │ :latest │  │ Python :3.14      │  │ Node)  │ │
│  │         │  │         │  │         │  │                   │  │        │ │
│  │ uvicorn │  │ node    │  │ exec    │  │ stdio → HTTP      │  │        │ │
│  └─────────┘  └─────────┘  └─────────┘  └───────────────────┘  └───────┘ │
│                                                                             │
│  Cold-start: 20-27 seconds (base images pre-cached on nodes)               │
└────────────────────────────────────────────────────────────────────────────┘
```

## Design Principles

1. **Minimal images** - Only runtime + loader scripts, no pre-installed packages
2. **Vendored dependencies** - All deps bundled in `.mcpb` file (`deps/` or `node_modules/`)
3. **SHA256 verification** - Optional integrity check on bundle download
4. **Non-root execution** - Security hardened with unprivileged user
5. **Multi-architecture** - All images built for amd64 and arm64

## Runtime Types

MCPB supports four runtime types to handle different MCP server architectures:

### 1. Python (HTTP Native)

For Python MCP servers that expose HTTP directly using uvicorn/FastAPI/FastMCP.

| Image | Tags | Default |
|-------|------|---------|
| `nimbletools/mcpb-python` | 3.12, 3.13, 3.14 | 3.14 |

**Runtime field:** `python:3.14`

**Manifest structure:**
```json
{
  "name": "my-server",
  "version": "1.0.0",
  "server": {
    "entry_point": "server/main.py"
  }
}
```

**Execution:** `python -m uvicorn server.main:app --host 0.0.0.0 --port $PORT`

### 2. Node.js (HTTP Native)

For Node.js MCP servers that expose HTTP directly.

| Image | Tags | Default |
|-------|------|---------|
| `nimbletools/mcpb-node` | 20, 22, 24 | 24 |

**Runtime field:** `node:24`

**Manifest structure:**
```json
{
  "name": "my-server",
  "version": "1.0.0",
  "server": {
    "entry_point": "dist/index.js"
  }
}
```

**Execution:** `node dist/index.js`

### 3. Supergateway (stdio → HTTP Wrapper)

For MCP servers that use stdio transport. Supergateway wraps the stdio interface and exposes HTTP endpoints.

| Image | Python Tags | Node Version |
|-------|-------------|--------------|
| `nimbletools/mcpb-supergateway-python` | 3.12, 3.13, 3.14 | 22 (fixed) |

**Runtime field:** `supergateway-python:3.14`

**Manifest structure:**
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

**Execution:** `supergateway --stdio "python -m my_server" --outputTransport streamableHttp --port $PORT`

**Exposed endpoints:**
- `/health` - Health check
- `/mcp` - MCP protocol (StreamableHTTP transport)

### 4. Binary (Pre-compiled Executables)

For pre-compiled MCP server binaries (Go, Rust, C++, etc.).

| Image | Tag |
|-------|-----|
| `nimbletools/mcpb-binary` | latest |

**Runtime field:** `binary`

**Manifest structure:**
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

The `${__dirname}` placeholder is replaced with the bundle extraction directory at runtime.

**Execution:** Direct execution of the binary with provided args.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BUNDLE_URL` | Yes | - | URL to download .mcpb bundle |
| `BUNDLE_SHA256` | No | - | SHA256 hash for integrity verification |
| `BUNDLE_DIR` | No | `/tmp/bundle` | Directory to extract bundle |
| `PORT` | No | `8000` | HTTP server port |

## Startup Flow

### HTTP Native Runtimes (Python/Node)

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ entrypoint.sh   │────▶│ mcpb-loader     │────▶│ Start Server    │
│                 │     │                 │     │                 │
│ Parse env vars  │     │ Download bundle │     │ Read entry_point│
│ BUNDLE_URL      │     │ Verify SHA256   │     │ Set PYTHONPATH  │
│ BUNDLE_SHA256   │     │ Extract to dir  │     │ Run uvicorn/node│
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

1. Container starts, `entrypoint.sh` executes
2. `mcpb-loader` downloads bundle from `BUNDLE_URL`
3. If `BUNDLE_SHA256` provided, verifies hash (aborts on mismatch)
4. Extracts bundle to `BUNDLE_DIR`
5. Parses `manifest.json` for `server.entry_point`
6. Sets module path to include vendored deps (`deps/` or `node_modules/`)
7. Starts HTTP server on `PORT`
8. Health check passes at `/health`

### Supergateway Runtime

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ entrypoint.sh   │────▶│ mcpb-loader     │────▶│ Start Gateway   │
│                 │     │                 │     │                 │
│ Parse env vars  │     │ Download bundle │     │ Read mcp_config │
│                 │     │ Extract bundle  │     │ Build stdio cmd │
│                 │     │                 │     │ Run supergateway│
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

1. Container starts, `entrypoint.sh` executes
2. `mcpb-loader` downloads and extracts bundle
3. Parses `manifest.json` for `server.mcp_config.command` and `args`
4. Sets `PYTHONPATH` to include vendored deps
5. Starts supergateway with the stdio command
6. Supergateway exposes `/health` and `/mcp` endpoints

### Binary Runtime

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ entrypoint.sh   │────▶│ curl + tar      │────▶│ Execute Binary  │
│                 │     │                 │     │                 │
│ Parse env vars  │     │ Download bundle │     │ Read mcp_config │
│                 │     │ Verify SHA256   │     │ Replace __dirname│
│                 │     │ Extract tarball │     │ chmod +x && exec│
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

1. Container starts, `entrypoint.sh` executes
2. Downloads bundle via curl
3. Verifies SHA256 if provided
4. Extracts tarball to `BUNDLE_DIR`
5. Parses `manifest.json` for `server.mcp_config.command` and `args`
6. Replaces `${__dirname}` placeholders with bundle path
7. Makes binary executable and runs it

## Image Components

Each base image contains these files:

| File | Purpose |
|------|---------|
| `Dockerfile` | Minimal image with runtime only |
| `mcpb-loader` | Downloads, verifies, and extracts bundles |
| `entrypoint.sh` | Orchestrates startup and runs server |

### Image Sizes (approximate)

| Image | Size | Contents |
|-------|------|----------|
| mcpb-python | ~50MB | Python slim + loader |
| mcpb-node | ~50MB | Node alpine + loader |
| mcpb-supergateway-python | ~150MB | Python + Node + supergateway |
| mcpb-binary | ~30MB | Debian slim + curl |

## Bundle Structure

### HTTP Native Bundles (Python/Node)

```
my-server-v1.0.0-linux-amd64.mcpb (zip)
├── manifest.json           # Required: name, version, server.entry_point
├── server/
│   └── main.py            # Entry point
├── deps/                  # Python: vendored dependencies
│   ├── fastmcp/
│   ├── uvicorn/
│   └── ...
└── (or node_modules/)     # Node: vendored dependencies
```

### stdio/Binary Bundles

```
my-server-v1.0.0-linux-amd64.mcpb (tar.gz for binary, zip for stdio)
├── manifest.json           # Required: name, version, server.mcp_config
├── bin/
│   └── server             # Binary executable (for binary runtime)
├── server/
│   └── main.py            # Python module (for supergateway)
└── deps/                  # Vendored dependencies (for supergateway)
```

## server.json Configuration

In the MCP server registry, specify the runtime in `_meta` and provide separate packages per architecture:

```json
{
  "name": "ai.nimbletools/my-server",
  "version": "1.0.0",
  "packages": [
    {
      "registryType": "mcpb",
      "identifier": "https://github.com/org/my-server/releases/download/v1.0.0/my-server-v1.0.0-linux-amd64.mcpb",
      "version": "1.0.0",
      "fileSha256": "abc123...",
      "transport": { "type": "streamable-http" }
    },
    {
      "registryType": "mcpb",
      "identifier": "https://github.com/org/my-server/releases/download/v1.0.0/my-server-v1.0.0-linux-arm64.mcpb",
      "version": "1.0.0",
      "fileSha256": "def456...",
      "transport": { "type": "streamable-http" }
    }
  ],
  "_meta": {
    "ai.nimbletools.mcp/v1": {
      "runtime": "python:3.14"
    }
  }
}
```

### Package URL Requirements

MCPB package URLs (the `identifier` field) must follow these requirements:

1. **Must end with `.mcpb`**: The URL must end with a valid `.mcpb` filename
2. **Must contain architecture**: The filename must include the target architecture (e.g., `linux-amd64.mcpb` or `linux-arm64.mcpb`)
3. **One package per architecture**: Create separate package entries for each supported architecture

The control-plane validates these requirements at deploy time and returns a `422 Unprocessable Entity` error if:
- The URL doesn't end with a `.mcpb` filename (`INVALID_MCPB_URL`)
- No package matches the cluster's architecture (`ARCHITECTURE_MISMATCH`)

### Runtime Values

| Value | Base Image | Use Case |
|-------|------------|----------|
| `python:3.12` | mcpb-python:3.12 | Python HTTP servers (older) |
| `python:3.13` | mcpb-python:3.13 | Python HTTP servers |
| `python:3.14` | mcpb-python:3.14 | Python HTTP servers (default) |
| `node:20` | mcpb-node:20 | Node.js HTTP servers (LTS) |
| `node:22` | mcpb-node:22 | Node.js HTTP servers (LTS) |
| `node:24` | mcpb-node:24 | Node.js HTTP servers (default) |
| `supergateway-python:3.14` | mcpb-supergateway-python:3.14 | Python stdio servers |
| `binary` | mcpb-binary:latest | Pre-compiled binaries |

## Local Development

```bash
# Build all versions
make base-images

# Build specific runtime
make base-images-python       # Python 3.12, 3.13, 3.14
make base-images-node         # Node 20, 22, 24
make base-images-supergateway # Supergateway images
make base-images-binary       # Binary image

# Import to local k3d cluster
make base-images-import
```

Or build specific versions directly:

```bash
cd base-images
make python-3.13
make node-22
make supergateway-python-3.14
make binary
```

## Testing

```bash
# Determine your architecture
ARCH=$(uname -m | sed 's/x86_64/amd64/' | sed 's/aarch64/arm64/')

# Run with a bundle
docker run -p 8000:8000 \
  -e BUNDLE_URL=https://github.com/NimbleBrainInc/mcp-echo/releases/download/v1.0.0/mcp-echo-v1.0.0-linux-${ARCH}.mcpb \
  nimbletools/mcpb-python:3.14

# Verify
curl http://localhost:8000/health
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## Security

All images follow security best practices:

- **Non-root user**: Containers run as unprivileged user (UID 1000)
- **Minimal attack surface**: Only essential packages installed
- **SHA256 verification**: Optional integrity check prevents tampering
- **Read-only friendly**: Designed to work with read-only root filesystems

## Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `HTTP 404` on download | Wrong bundle URL | Check GitHub Release exists and URL is correct |
| `SHA256 mismatch` | Wrong hash or corruption | Verify hash matches architecture-specific bundle |
| `ModuleNotFoundError` | Missing vendored deps | Ensure all deps in `deps/` (Python) or `node_modules/` (Node) |
| `connection refused` on health | Server not listening | Check PORT matches, verify /health endpoint exists |
| `supergateway: command not found` | Using wrong image | Use `mcpb-supergateway-python`, not `mcpb-python` |
| Binary won't execute | Permissions or arch mismatch | Ensure binary is executable and matches container arch |

## See Also

- [`base-images/README.md`](../base-images/README.md) - Build commands and quick start
- [Architecture Guide](./ARCHITECTURE.md) - Overall platform architecture
- [MCPB Specification](https://github.com/modelcontextprotocol/mcpb) - Official spec
