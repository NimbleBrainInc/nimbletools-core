#!/bin/bash
set -e

BUNDLE_URL="${BUNDLE_URL:?BUNDLE_URL environment variable required}"
BUNDLE_DIR="${BUNDLE_DIR:-/tmp/bundle}"
BUNDLE_SHA256="${BUNDLE_SHA256:-}"
PORT="${PORT:-8000}"

echo "=== MCPB Python Runtime ==="
echo "Bundle URL: $BUNDLE_URL"
echo "Bundle Dir: $BUNDLE_DIR"
echo "Port: $PORT"
if [ -n "$BUNDLE_SHA256" ]; then
  echo "SHA256: ${BUNDLE_SHA256:0:16}..."
else
  echo "SHA256: (not provided, skipping verification)"
fi

# Download and extract bundle (with optional hash verification)
python3 /usr/local/bin/mcpb-loader "$BUNDLE_URL" "$BUNDLE_DIR" "$BUNDLE_SHA256"

# Read entry point from manifest
MANIFEST="$BUNDLE_DIR/manifest.json"
ENTRY_POINT=$(python3 -c "import json; print(json.load(open('$MANIFEST'))['server']['entry_point'])")

echo "Entry point: $ENTRY_POINT"

# Convert path to Python module
# server/main.py -> server.main (keeps package structure for relative imports)
MODULE=$(echo "$ENTRY_POINT" | sed 's|/|.|g' | sed 's|\.py$||')

# Add bundle dir and vendored deps to Python path
# All dependencies are pre-vendored in the bundle for portability
export PYTHONPATH="$BUNDLE_DIR:$BUNDLE_DIR/deps:$PYTHONPATH"

# Start uvicorn (using python -m since uvicorn is in vendored deps)
echo "Starting server on port $PORT..."
cd "$BUNDLE_DIR"
exec python -m uvicorn "${MODULE}:app" --host 0.0.0.0 --port "$PORT"
