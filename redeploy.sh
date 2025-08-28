#!/bin/sh
# Helper script to delete/rebuild locally

k3d cluster delete nimbletools-dev

# 2. Create new k3d cluster
./scripts/setup-k3d.sh

# 3. Build and import all images with your latest code
make build-local

# 4. Install the system
./install.sh

