#!/bin/bash
set -e

# MCPB Binary Runtime Entrypoint
# Downloads and runs a pre-compiled MCP server binary

BUNDLE_URL="${BUNDLE_URL:?BUNDLE_URL environment variable required}"
BUNDLE_DIR="${BUNDLE_DIR:-/tmp/bundle}"
BUNDLE_SHA256="${BUNDLE_SHA256:-}"
PORT="${PORT:-8000}"

echo "=== MCPB Binary Runtime ==="
echo "Bundle URL: $BUNDLE_URL"
echo "Bundle Dir: $BUNDLE_DIR"
echo "Port: $PORT"
echo "SHA256: ${BUNDLE_SHA256:-(not provided, skipping verification)}"

# Download bundle
echo "Downloading bundle from $BUNDLE_URL..."
BUNDLE_FILE="/tmp/bundle.mcpb"
curl -fsSL "$BUNDLE_URL" -o "$BUNDLE_FILE"
echo "Downloaded $(du -h "$BUNDLE_FILE" | cut -f1)"

# Verify SHA256 if provided
if [ -n "$BUNDLE_SHA256" ]; then
    echo "Verifying SHA256..."
    ACTUAL_SHA256=$(sha256sum "$BUNDLE_FILE" | cut -d' ' -f1)
    if [ "$ACTUAL_SHA256" != "$BUNDLE_SHA256" ]; then
        echo "Error: SHA256 mismatch!"
        echo "Expected: $BUNDLE_SHA256"
        echo "Actual: $ACTUAL_SHA256"
        exit 1
    fi
    echo "SHA256 verified"
else
    echo "Warning: No SHA256 hash provided, skipping integrity verification"
fi

# Extract bundle
echo "Extracting to $BUNDLE_DIR..."
mkdir -p "$BUNDLE_DIR"
tar -xzf "$BUNDLE_FILE" -C "$BUNDLE_DIR"

# Read manifest and extract command
MANIFEST="$BUNDLE_DIR/manifest.json"
if [ ! -f "$MANIFEST" ]; then
    echo "Error: manifest.json not found in bundle"
    exit 1
fi

# Extract name and version
NAME=$(cat "$MANIFEST" | grep -o '"name"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | cut -d'"' -f4)
VERSION=$(cat "$MANIFEST" | grep -o '"version"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | cut -d'"' -f4)
echo "Loaded: $NAME v$VERSION"

# Extract command and args from mcp_config
# Parse JSON using basic shell commands (no jq dependency)
COMMAND=$(cat "$MANIFEST" | grep -o '"command"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | cut -d'"' -f4)
ARGS_JSON=$(cat "$MANIFEST" | grep -o '"args"[[:space:]]*:[[:space:]]*\[[^]]*\]' | head -1)

# Replace ${__dirname} with bundle directory
COMMAND="${COMMAND/\$\{__dirname\}/$BUNDLE_DIR}"

# Build args array (simple parsing for common cases)
ARGS=""
if [ -n "$ARGS_JSON" ]; then
    # Extract the array contents (between [ and ])
    ARRAY_CONTENTS=$(echo "$ARGS_JSON" | sed 's/.*\[\(.*\)\].*/\1/')
    # Extract strings from the array, skip "args" key
    ARGS=$(echo "$ARRAY_CONTENTS" | grep -o '"[^"]*"' | while read -r arg; do
        arg="${arg//\"/}"
        arg="${arg/\$\{__dirname\}/$BUNDLE_DIR}"
        echo -n "$arg "
    done)
fi

# Ensure binary is executable
if [ -f "$COMMAND" ]; then
    chmod +x "$COMMAND"
fi

echo "Command: $COMMAND $ARGS"
echo "Starting server on port $PORT..."

# Export PORT for the binary to use
export PORT

# Execute the binary
cd "$BUNDLE_DIR"
exec $COMMAND $ARGS
