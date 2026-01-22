# MCPB Python Runtime

Base image for running Python MCP servers from `.mcpb` bundles.

## How It Works

1. Downloads the bundle from `BUNDLE_URL`
2. Optionally verifies SHA256 hash
3. Extracts bundle to `/tmp/bundle`
4. Sets `PYTHONPATH` to include bundle deps
5. Starts uvicorn with the server module

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BUNDLE_URL` | Yes | URL to download the `.mcpb` bundle |
| `BUNDLE_SHA256` | No | SHA256 hash for integrity verification |
| `PORT` | No | Server port (default: 8000) |

## Resource Requirements

Python servers with large dependency bundles need adequate CPU for fast startup. Importing dependencies is CPU-bound, and low CPU limits cause slow startup that triggers health probe failures.

### Recommended

```yaml
resources:
  requests:
    cpu: 250m
    memory: 256Mi
  limits:
    cpu: 1000m     # burst for imports
    memory: 512Mi
```

### Why These Values?

- **CPU requests (250m)**: Scheduler reservation. Low because servers are idle after startup.
- **CPU limits (1000m)**: Burst capacity for Python imports. Used for ~5-10 seconds during startup, then released.
- **Memory (256-512Mi)**: Typical for Python + FastMCP + dependencies.

### Common Issue: Startup Failures

If servers crash with `CrashLoopBackOff` or `asyncio.CancelledError`:

1. Check CPU limits - anything below 500m may cause startup timeouts
2. Check health probe `initialDelaySeconds` vs actual startup time
3. Increase CPU limits or probe delays

## Bundle Structure

Bundles are extracted to `/tmp/bundle` with this structure:

```
/tmp/bundle/
├── deps/           # Vendored Python dependencies
├── src/            # Source code (for reference)
├── manifest.json   # Bundle metadata
└── ...
```

The `PYTHONPATH` is set to `/tmp/bundle:/tmp/bundle/deps` so imports resolve from the vendored dependencies.

## Building

```bash
# Build all Python versions
make build-multiarch

# Push to Docker Hub
make push

# Build specific version
make build-multiarch PYTHON_VERSION=3.13
```

## Tags

| Tag | Python Version |
|-----|----------------|
| `3.12` | Python 3.12 |
| `3.13` | Python 3.13 |
| `3.14` | Python 3.14 |
| `latest` | Python 3.14 |
