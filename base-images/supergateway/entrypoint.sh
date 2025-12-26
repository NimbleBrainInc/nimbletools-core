#!/bin/bash
set -e

BUNDLE_URL="${BUNDLE_URL:?BUNDLE_URL environment variable required}"
BUNDLE_DIR="${BUNDLE_DIR:-/tmp/bundle}"
BUNDLE_SHA256="${BUNDLE_SHA256:-}"
PORT="${PORT:-8000}"

echo "=== MCPB Supergateway Runtime ==="
echo "Bundle URL: $BUNDLE_URL"
echo "Bundle Dir: $BUNDLE_DIR"
echo "Port: $PORT"
if [ -n "$BUNDLE_SHA256" ]; then
  echo "SHA256: ${BUNDLE_SHA256:0:16}..."
else
  echo "SHA256: (not provided, skipping verification)"
fi

# Download and extract bundle
python3 /usr/local/bin/mcpb-loader "$BUNDLE_URL" "$BUNDLE_DIR" "$BUNDLE_SHA256"

# Read stdio command from manifest.json
# Uses mcp_config.command and mcp_config.args from manifest
MANIFEST="$BUNDLE_DIR/manifest.json"

# Extract command and args, build full stdio command
STDIO_CMD=$(python3 -c "
import json
import shlex

manifest = json.load(open('$MANIFEST'))
mcp_config = manifest['server']['mcp_config']
command = mcp_config['command']
args = mcp_config.get('args', [])

# Replace \${__dirname} placeholder with bundle dir
args = [a.replace('\${__dirname}', '$BUNDLE_DIR') for a in args]

# Build full command
parts = [command] + args
print(' '.join(shlex.quote(p) for p in parts))
")

echo "Stdio command: $STDIO_CMD"

# Set up Python environment for vendored deps
export PYTHONPATH="$BUNDLE_DIR:$BUNDLE_DIR/deps:$PYTHONPATH"

# Change to bundle directory
cd "$BUNDLE_DIR"

# Run via supergateway
# - Wraps stdio MCP server and exposes as StreamableHTTP
# - /health endpoint for Kubernetes probes
# - /mcp endpoint for MCP protocol
echo "Starting supergateway on port $PORT..."
exec supergateway \
  --stdio "$STDIO_CMD" \
  --outputTransport streamableHttp \
  --port "$PORT" \
  --healthEndpoint /health
