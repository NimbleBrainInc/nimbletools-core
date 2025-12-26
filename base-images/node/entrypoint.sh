#!/bin/bash
set -e

BUNDLE_URL="${BUNDLE_URL:?BUNDLE_URL environment variable required}"
BUNDLE_DIR="${BUNDLE_DIR:-/tmp/bundle}"
BUNDLE_SHA256="${BUNDLE_SHA256:-}"
PORT="${PORT:-8000}"

echo "=== MCPB Node.js Runtime ==="
echo "Bundle URL: $BUNDLE_URL"
echo "Bundle Dir: $BUNDLE_DIR"
echo "Port: $PORT"
if [ -n "$BUNDLE_SHA256" ]; then
    echo "SHA256: ${BUNDLE_SHA256:0:16}..."
fi

# Download and extract bundle (with optional SHA256 verification)
node /usr/local/bin/mcpb-loader "$BUNDLE_URL" "$BUNDLE_DIR" "$BUNDLE_SHA256"

# Read entry point from manifest
MANIFEST="$BUNDLE_DIR/manifest.json"
ENTRY_POINT=$(node -e "console.log(require('$MANIFEST').server.entry_point)")

echo "Entry point: $ENTRY_POINT"

# Add vendored node_modules to NODE_PATH
# All dependencies are pre-vendored in the bundle for portability
export NODE_PATH="$BUNDLE_DIR/node_modules:$NODE_PATH"

# Export port for the server to use
export PORT

# Start server
echo "Starting server on port $PORT..."
cd "$BUNDLE_DIR"
exec node "$ENTRY_POINT"
