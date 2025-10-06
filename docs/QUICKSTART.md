# NimbleTools Core Quickstart

**From zero to production MCP service in 60 seconds**

Transform any MCP tool into a scalable, auto-scaling service without rewriting code. This guide gets you from installation to your first running service in under a minute.

## What You Need

**Prerequisites:**

- **Helm 3.0+** for package management
- **k3d** for local Kubernetes cluster (automatic setup)

## Installation

### Step 1: Install the Platform

```bash
# One command gets you running (creates local cluster if needed)
curl -sSL https://raw.githubusercontent.com/NimbleBrainInc/nimbletools-core/main/install.sh | bash
```

**What just happened?**

- ✅ Local Kubernetes cluster created (k3d-nimbletools-quickstart)
- ✅ NimbleTools operator deployed and running
- ✅ REST API available for service management
- ✅ Ready to deploy your first MCP service

### Step 2: Verify Installation

```bash
# Switch to the cluster context
kubectl config use-context k3d-nimbletools-quickstart

# Set namespace for convenience
kubectl config set-context --current --namespace=nimbletools-system

# Check that all pods are running
kubectl get pods

# Expected output:
# NAME                                                READY   STATUS    RESTARTS   AGE
# nimbletools-core-control-plane-64b889fbdb-xxxxx     1/1     Running   0          2m
# nimbletools-core-control-plane-64b889fbdb-xxxxx     1/1     Running   0          2m
# nimbletools-core-operator-7bf4f9f667-xxxxx          1/1     Running   0          2m
# nimbletools-core-rbac-controller-56f67c95dc-xxxxx   1/1     Running   0          2m
```

### Step 3: Install the CLI (Optional)

```bash
# Install ntcli (NimbleTools CLI)
npm install -g @nimbletools/ntcli
```

### Step 4: Create Your First Workspace

```bash
# Create a workspace
ntcli ws create myfirstworkspace

# Switch to your new workspace
ntcli ws use myfirstworkspace
```

**Output:**

```
✔ ✅ Workspace created successfully!
   Workspace: myfirstworkspace (7b545ac8-48f8-4b5f-8af8-1c3ff112d755)
   💡 Workspace saved locally for easy switching!
```

### Step 5: Deploy Your First Service

```bash
# Deploy the echo MCP server
ntcli srv deploy ai.nimbletools/echo
```

**Output:**

```
✔ 🚀 Server deployed: ai.nimbletools/echo

✅ Deployment successful!

📦 Server Details
  Name: ai.nimbletools/echo
  Version: 1.0.0
  Status: ◐ pending

Workspace: myfirstworkspace (7b545ac8-48f8-4b5f-8af8-1c3ff112d755)
```

### Step 6: Verify Your Service

```bash
# List all servers in your workspace
ntcli srv list
```

**Output:**

```
✔ 📦 Found 1 server

🏢 Workspace: myfirstworkspace

NAME           STATUS     REPLICAS  IMAGE                    CREATED
──────────────────────────────────────────────────────────────────────
ai.nimbletools/echo  🟢 Running     1         nimbletools/mcp-echo     10/4/2025

Total: 1 server in workspace myfirstworkspace
```

## Success! 🎉

**You just deployed a production-ready MCP service that:**

- Scales automatically based on demand
- Integrates with any MCP client (Claude, ChatGPT, local tools)
- Runs with enterprise-grade reliability
- Required zero code changes to your MCP tool

## What's Next?

### 🧪 Explore Your Services

```bash
# Get detailed information about a server
ntcli srv info ai.nimbletools/echo

# View server logs
ntcli srv logs ai.nimbletools/echo

# Switch between workspaces
ntcli ws list
ntcli ws use <workspace-name>
```

### 🚀 Deploy More Services

Browse available MCP servers and deploy them:

```bash
# Deploy more servers from the registry
ntcli srv deploy ai.nimbletools/finnhub
ntcli srv deploy ai.nimbletools/postgres-mcp
ntcli srv deploy ai.nimbletools/tavily-mcp

# List all deployed servers
ntcli srv list
```

### 🛠️ Manage Your Workspaces

```bash
# Create additional workspaces for different projects
ntcli ws create production
ntcli ws create development

# List all workspaces
ntcli ws list

# Delete a workspace (and all its servers)
ntcli ws delete myfirstworkspace
```

### 🛠️ Deploy Your Own Tool

**Have an existing MCP tool?** Create a server definition and deploy it:

1. **Create a `server.json` file** with your server configuration:

```json
{
  "$schema": "https://registry.nimbletools.ai/schemas/2025-09-22/nimbletools-server.schema.json",
  "name": "your-org/your-server",
  "version": "1.0.0",
  "description": "Your MCP server description",
  "status": "active",
  "packages": [
    {
      "registryType": "oci",
      "registryBaseUrl": "https://docker.io",
      "identifier": "your-org/your-mcp-server",
      "version": "1.0.0",
      "transport": {
        "type": "streamable-http",
        "url": "https://mcp.nimbletools.ai/mcp"
      }
    }
  ],
  "_meta": {
    "ai.nimbletools.mcp/v1": {
      "container": {
        "healthCheck": {
          "path": "/health",
          "port": 8000
        }
      },
      "resources": {
        "limits": {
          "memory": "256Mi",
          "cpu": "100m"
        }
      },
      "deployment": {
        "protocol": "http",
        "port": 8000,
        "mcpPath": "/mcp"
      }
    }
  }
}
```

2. **Deploy using the server definition:**

```bash
# Deploy from local server.json file
ntcli srv deploy ./server.json
```

For more details on server definitions and configuration options, see the [Server Configuration Guide](../README.md#server-configuration).

## Advanced Deployment

### Using kubectl Directly

While `ntcli` is the recommended way to deploy servers, you can also use `kubectl` for advanced scenarios:

#### Deploy a Custom MCP Service

```bash
# For HTTP-based MCP services
kubectl apply -f - <<EOF
apiVersion: mcp.nimbletools.dev/v1
kind: MCPService
metadata:
  name: my-custom-server
  namespace: ws-myfirstworkspace-<workspace-uuid>
spec:
  container:
    image: your-org/your-mcp-server:latest
    port: 8000
  deployment:
    type: http
  resources:
    limits:
      memory: "256Mi"
      cpu: "100m"
EOF
```

For detailed kubectl-based deployment options, see the [Deployment Guide](../README.md#deployment).

### Monitoring and Operations

```bash
# Watch services in real-time
kubectl get mcpservices --watch

# Check operator health
kubectl logs -l app.kubernetes.io/component=operator -n nimbletools-system -f

# View server logs
kubectl logs -l mcp.nimbletools.dev/server=<server-name>
```

## Troubleshooting

### 🚨 Common Issues

**Server won't deploy:**

```bash
# Check server status
ntcli srv info <server-name>

# View server logs for errors
ntcli srv logs <server-name>

# Check if workspace exists
ntcli ws list
```

**CLI can't connect to control plane:**

```bash
# Verify control plane is running
kubectl get pods -n nimbletools-system

# Check control plane logs
kubectl logs -l app.kubernetes.io/component=control-plane -n nimbletools-system

# Verify API is accessible
kubectl port-forward -n nimbletools-system service/control-plane 8080:80
curl http://localhost:8080/health
```

**Server shows as "pending":**

```bash
# Check operator logs
kubectl logs -l app.kubernetes.io/component=operator -n nimbletools-system -f

# Check if images are accessible
kubectl get pods -n ws-<workspace-name> -o wide
kubectl describe pod <pod-name> -n ws-<workspace-name>
```

### 🆘 Getting Help

**Still stuck?**

- 📖 [Full Documentation](../README.md)
- 🏗️ [Architecture Guide](ARCHITECTURE.md)
- 🐛 [GitHub Issues](https://github.com/NimbleBrainInc/nimbletools-core/issues) - Report bugs
- 📋 [Discussions](https://github.com/NimbleBrainInc/nimbletools-core/discussions) - Ask questions

## Clean Up

**Delete a workspace and all its servers:**

```bash
ntcli ws delete myfirstworkspace
```

**Remove the platform completely:**

```bash
# Remove NimbleTools Core
./scripts/uninstall.sh --remove-crd --remove-namespace

# Or delete the entire cluster if using k3d
k3d cluster delete nimbletools-quickstart
```

## What You Just Built

🎉 **You just:**

- Deployed a production-ready MCP service platform
- Created a workspace for organizing your servers
- Deployed your first MCP server using the CLI
- Set up a foundation for your entire MCP ecosystem

## Next Steps

🚀 **Ready for more?**

1. **[Deploy More Servers](../README.md#available-servers)** - Browse the registry for more MCP servers
2. **[Architecture Deep-Dive](ARCHITECTURE.md)** - Understand how the platform works
3. **[Server Configuration](../README.md#server-configuration)** - Learn about server.json schema
4. **[Production Guide](../README.md#production-deployment)** - Security, monitoring, scaling

**Welcome to effortless MCP deployment!** 🚀
