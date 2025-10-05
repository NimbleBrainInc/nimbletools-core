#!/bin/bash

# Update all version references from the VERSION file
# This ensures consistency across all components

set -euo pipefail

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Read version from VERSION file
if [[ ! -f "$ROOT_DIR/VERSION" ]]; then
    echo "ERROR: VERSION file not found at $ROOT_DIR/VERSION"
    exit 1
fi

VERSION=$(cat "$ROOT_DIR/VERSION")
echo "Updating all components to version: $VERSION"

# Update Chart.yaml appVersion
echo "Updating chart/Chart.yaml..."
if [[ -f "$ROOT_DIR/chart/Chart.yaml" ]]; then
    sed -i '' "s/^appVersion: .*/appVersion: \"$VERSION\"/" "$ROOT_DIR/chart/Chart.yaml"
fi

# Update values.yaml image tags
echo "Updating chart/values.yaml..."
if [[ -f "$ROOT_DIR/chart/values.yaml" ]]; then
    # Update all image tags in values.yaml
    sed -i '' "s/tag: \"[^\"]*\"/tag: \"$VERSION\"/g" "$ROOT_DIR/chart/values.yaml"
fi

# Update build-images.sh default version
echo "Updating scripts/build-images.sh..."
if [[ -f "$ROOT_DIR/scripts/build-images.sh" ]]; then
    sed -i '' "s/^VERSION=.*/VERSION=\"$VERSION\"/" "$ROOT_DIR/scripts/build-images.sh"
fi

# Update redeploy.sh if it exists
echo "Updating redeploy.sh..."
if [[ -f "$ROOT_DIR/redeploy.sh" ]]; then
    # Update any hardcoded versions in redeploy script
    sed -i '' "s/0\.[0-9]\.[0-9]-dev/$VERSION/g" "$ROOT_DIR/redeploy.sh"
fi

# Update Makefile if it exists
if [[ -f "$ROOT_DIR/Makefile" ]]; then
    echo "Updating Makefile..."
    sed -i '' "s/^VERSION ?= .*/VERSION ?= $VERSION/" "$ROOT_DIR/Makefile"
fi

echo ""
echo "✅ Version update complete!"
echo ""
echo "Updated files:"
echo "  - chart/Chart.yaml (appVersion)"
echo "  - chart/values.yaml (all image tags)"
echo "  - scripts/build-images.sh (VERSION variable)"
[[ -f "$ROOT_DIR/redeploy.sh" ]] && echo "  - redeploy.sh"
[[ -f "$ROOT_DIR/Makefile" ]] && echo "  - Makefile"

echo ""
echo "Next steps:"
echo "  1. Review the changes: git diff"
echo "  2. Build images: ./scripts/build-images.sh --local"
echo "  3. Deploy: ./install.sh --local"