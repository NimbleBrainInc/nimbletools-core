#!/bin/sh
# Helper script to delete/rebuild locally

k3d cluster delete nimbletools-quickstart

# 2. Create new k3d cluster
./scripts/setup-k3d.sh

# 3. Wait for cluster to be fully ready
echo "Waiting for cluster to be fully registered..."
sleep 2

# 4. Install the system locally
./install.sh --local --domain nt.dev

