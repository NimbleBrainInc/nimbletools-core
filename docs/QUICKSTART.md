# NimbleTools Core Quickstart

**From zero to production MCP service in 60 seconds**

Transform any MCP tool into a scalable, auto-scaling service without rewriting code. This guide gets you from installation to your first running service in under a minute.

## What You Need (2-minute setup)

**Prerequisites:**

- **Kubernetes cluster** (we recommend k3d for local development)
- **Helm 3.0+** for package management
- **kubectl** configured for your cluster

**Already have Kubernetes and Helm?** Skip to [60-Second Installation](#60-second-installation)

**Need a local cluster?** Set up k3d:

```bash
# Install k3d for local Kubernetes cluster
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

# Create local cluster
k3d cluster create nimbletools-local --wait
```

**Verify you're ready:**

```bash
kubectl cluster-info  # Should show cluster info
helm version         # Should show Helm 3.0+
```

**Configure local domains:**

```bash
# Add local domains to hosts file for API access
echo "127.0.0.1 api.nimbletools.local mcp.nimbletools.local" | sudo tee -a /etc/hosts
```

This configuration routes local API calls to your cluster (the default local cluster uses these domains for easier URL management).

## 60-Second Installation

### One Command Install (30 seconds)

```bash
curl -sSL https://raw.githubusercontent.com/nimblebrain/nimbletools-core/main/scripts/install.sh | bash
```

**What just happened?**

- ✅ MCP Operator deployed and managing services
- ✅ REST API ready for service management
- ✅ Custom Resource Definition installed
- ✅ Everything verified and working

### Deploy Your First Service (15 seconds)

```bash
kubectl apply -f - <<EOF
apiVersion: mcp.nimbletools.dev/v1
kind: MCPService
metadata:
  name: calculator
spec:
  container:
    image: nimbletools/calculator-mcp:latest
    port: 8000
  deployment:
    type: http
  tools:
    - name: add
      description: "Add two numbers"
EOF
```

### Verify Success (15 seconds)

```bash
# Check your service is running
kubectl get mcpservices
# Should show: calculator   Running   1/1

# View the pod
kubectl get pods -l app=calculator
# Should show: calculator-xxx   Running
```

## Success! 🎉

**You just deployed a production-ready MCP service that:**

- Scales automatically based on demand
- Integrates with any MCP client (Claude, ChatGPT, local tools)
- Runs with enterprise-grade reliability
- Required zero code changes to your MCP tool

## What's Next?

### 🧪 Test Your Service

#### Using the CLI (Recommended)

```bash
# Set up local domain for CLI access
ntcli domain set nimbletools.local --insecure

# View your services
ntcli server list

# Check service status
ntcli server info calculator
```

#### Using the API Directly

```bash
# Access the management API
kubectl port-forward -n nimbletools-system service/nimbletools-core-api 8080:80

# View your services
curl http://localhost:8080/api/v1/workspaces/default/servers

# API documentation
open http://localhost:8080/docs
```

### 🚀 Deploy More Services

```bash
# File browser tool
kubectl apply -f examples/file-browser.yaml

# Database query tool
kubectl apply -f examples/db-query.yaml

# List all your MCP services
kubectl get mcpservices --all-namespaces
```

### 🛠️ Deploy Your Own Tool

**Have an existing MCP tool?** Deploy it in 30 seconds:

```bash
# For HTTP-based MCP services
kubectl apply -f - <<EOF
apiVersion: mcp.nimbletools.dev/v1
kind: MCPService
metadata:
  name: my-tool
spec:
  container:
    image: your-org/your-mcp-tool:latest
    port: 8000
  deployment:
    type: http
EOF
```

```bash
# For command-line MCP tools (stdio)
kubectl apply -f - <<EOF
apiVersion: mcp.nimbletools.dev/v1
kind: MCPService
metadata:
  name: my-cli-tool
spec:
  container:
    image: nimbletools/universal-adapter:latest
    port: 8000
  deployment:
    type: stdio
    stdio:
      executable: "npx"
      args: ["-y", "@modelcontextprotocol/server-filesystem"]
      workingDir: "/tmp"
  resources:
    requests:
      cpu: "50m"
      memory: "128Mi"
    limits:
      cpu: "200m"
      memory: "256Mi"
EOF
```

## Deploying STDIO MCP Servers

**Many MCP servers are built as command-line tools** that communicate via stdio (standard input/output). NimbleTools Core can run these servers using the Universal Adapter, which converts stdio communication to HTTP.

### How STDIO Deployment Works

1. **Universal Adapter**: Wraps your stdio MCP server in an HTTP interface
2. **NPM Package Installation**: Automatically installs MCP servers from npm during startup
3. **JSON-RPC Bridge**: Converts HTTP requests to stdio JSON-RPC calls
4. **Auto-scaling**: Same scaling and reliability as HTTP services

### Complete STDIO Example

Here's a working example that deploys the `@modelcontextprotocol/server-everything` stdio MCP server:

```yaml
apiVersion: mcp.nimbletools.dev/v1
kind: MCPService
metadata:
  name: everything
  namespace: ws-your-workspace-uuid
  labels:
    mcp.nimbletools.dev/service: "true"
    mcp.nimbletools.dev/workspace: "your-workspace-uuid"
  annotations:
    mcp.nimbletools.dev/description: "Everything MCP test server"
    mcp.nimbletools.dev/version: "1.0.0"
spec:
  # Basic configuration
  replicas: 1
  timeout: 300
  environment: {}

  # Container - ALWAYS use universal-adapter for stdio servers
  container:
    image: "nimbletools/universal-adapter:latest"
    registry: "docker.io"
    port: 8000

  # Deployment configuration - specify stdio details
  deployment:
    type: "stdio"
    healthPath: "/health"
    stdio:
      executable: "npx" # Command to run
      args: ["-y", "@modelcontextprotocol/server-everything"] # Package to install and run
      workingDir: "/tmp" # Working directory

  # Resource limits
  resources:
    requests:
      cpu: "50m"
      memory: "128Mi"
    limits:
      cpu: "200m"
      memory: "256Mi"

  # Auto-scaling configuration
  scaling:
    minReplicas: 0
    maxReplicas: 10
    targetConcurrency: 10
    scaleDownDelay: "5m"

  # Routing configuration
  routing:
    path: "/services/everything"
    port: 8000
    healthPath: "/health"
    discoveryPath: "/mcp/discover"
```

### Deployment Steps

1. **Create the manifest file:**

```bash
# Save the above YAML as everything-mcp.yaml
kubectl apply -f everything-mcp.yaml
```

2. **Verify deployment:**

```bash
# Check service is running
kubectl get mcpservices
# Should show: everything   Running   1/1

# Check the pod
kubectl get pods | grep everything
# Should show: everything-deployment-xxx   1/1   Running
```

3. **Test the service:**

```bash
# Check logs to see MCP server startup
kubectl logs -l app=everything

# Port-forward to test locally
kubectl port-forward service/everything-service 8080:8000

# Test MCP endpoint
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{}}}'
```

### Common STDIO MCP Servers

Here are examples for popular stdio-based MCP servers:

**Filesystem Server:**

```yaml
spec:
  deployment:
    type: stdio
    stdio:
      executable: "npx"
      args: ["-y", "@modelcontextprotocol/server-filesystem"]
      workingDir: "/tmp"
```

**SQLite Server:**

```yaml
spec:
  deployment:
    type: stdio
    stdio:
      executable: "npx"
      args:
        [
          "-y",
          "@modelcontextprotocol/server-sqlite",
          "/path/to/database.sqlite",
        ]
      workingDir: "/tmp"
```

**Custom Python Server:**

```yaml
spec:
  deployment:
    type: stdio
    stdio:
      executable: "python"
      args: ["-m", "your_mcp_package"]
      workingDir: "/app"
  # You'd need a custom container image with your Python package installed
  container:
    image: "your-org/your-mcp-server:latest"
```

### Troubleshooting STDIO Servers

**Common Issues:**

1. **Package Not Found (404):**

   - Verify npm package name: `npm info @modelcontextprotocol/server-everything`
   - Use correct package name in `args`

2. **Server Won't Start:**

   - Check logs: `kubectl logs -l app=your-service-name`
   - Verify executable and args are correct
   - Ensure workingDir exists in container

3. **Health Check Failures:**
   - STDIO servers use universal adapter's HTTP interface
   - Health endpoint is always `/health` (provided by universal adapter)
   - MCP endpoint is at `/mcp`

**Debugging Commands:**

```bash
# See what's happening during startup
kubectl logs -l app=your-service-name -f

# Check if MCP server is responsive
kubectl exec -it deployment/your-service-name -- curl localhost:8000/health

# View full deployment configuration
kubectl get mcpservice your-service-name -o yaml
```

## Advanced Installation

### Custom Configuration

```bash
# Clone for full control
git clone https://github.com/nimblebrain/nimbletools-core.git
cd nimbletools-core

# Custom namespace
./install.sh --namespace my-company

# With ingress and custom domain
./install.sh --ingress-enabled --domain mcp.mycompany.com

# Enterprise security
./install.sh --auth-provider enterprise --rbac-enabled
```

### Management API

Access your MCP service platform:

- **Health Check:** `http://localhost:8080/health`
- **Interactive API Docs:** `http://localhost:8080/docs`
- **Service Management:** `http://localhost:8080/api/v1/workspaces/default/servers`
- **Workspace Management:** `http://localhost:8080/api/v1/workspaces`

## Development Environment

**Building your own MCP services?** Set up the full development environment:

```bash
# Complete development setup
git clone https://github.com/nimblebrain/nimbletools-core.git
cd nimbletools-core
./scripts/dev-setup.sh
```

**What you get:**

- Local k3d cluster with hot-reload
- Python development environment
- Local Docker registry for testing
- Example services and templates
- Development-specific configurations

### Local Registry (Optional)

**Just trying NimbleTools Core?** Skip this - use the simple install above.

**Building custom images?** The local Docker registry lets you:

- Test custom operator/adapter images
- Work offline during development
- Avoid pushing to public registries

**Registry troubleshooting:**

```bash
# Skip registry if you get errors
./scripts/dev-setup.sh --skip-registry

# Or create simple cluster
k3d cluster create test --wait && ./install.sh
```

## Production Operations

### 📊 Monitor Your Services

```bash
# Watch services in real-time
kubectl get mcpservices --watch

# Check operator health
kubectl logs -l app.kubernetes.io/component=operator -n nimbletools-system -f

# Resource usage
kubectl top pods -n nimbletools-system
```

### ⚡ Scale Services

```bash
# Scale up for high demand
kubectl patch mcpservice calculator -p '{"spec":{"replicas": 5}}'

# Enable serverless mode (scale to zero when idle)
kubectl patch mcpservice calculator -p '{"spec":{"replicas": 0}}'
```

### ⚙️ Custom Configuration

```bash
# Extract configuration template
helm show values ./chart > production-values.yaml

# Edit with your production settings
vim production-values.yaml

# Apply custom configuration
./install.sh -f production-values.yaml
```

## Troubleshooting

### 🚨 Installation Issues

**"Permission denied" errors:**

```bash
# Check your cluster permissions
kubectl auth can-i create deployments
kubectl auth can-i create customresourcedefinitions
# Both should return "yes"
```

**Pods stuck in "Pending":**

```bash
# Check cluster resources
kubectl get nodes
kubectl describe pod -n nimbletools-system
# Look for resource constraints or scheduling issues
```

### 🔧 Service Issues

**MCPService not starting:**

```bash
# Check what the operator is doing
kubectl logs -l app.kubernetes.io/component=operator -n nimbletools-system -f

# Get detailed service status
kubectl describe mcpservice your-service-name
```

**Can't reach your service:**

```bash
# Test directly
kubectl port-forward service/your-service 8080:8000
curl http://localhost:8080/health
```

### 🆘 Getting Help

**Quick diagnostics:**

```bash
# All-in-one health check
kubectl logs -l app.kubernetes.io/instance=nimbletools-core -n nimbletools-system
kubectl get mcpservices --all-namespaces
kubectl get pods --all-namespaces | grep -E "(Error|CrashLoop|Pending)"
```

**Still stuck?**

- 📖 [Full Documentation](../README.md)
- 🏗️ [Architecture Guide](ARCHITECTURE.md)
- 💬 [Discord Community](https://discord.gg/nimbletools) - Get help from other users
- 🐛 [GitHub Issues](https://github.com/nimblebrain/nimbletools-core/issues) - Report bugs
- 📋 [Discussions](https://github.com/nimblebrain/nimbletools-core/discussions) - Ask questions

## Clean Up

**Remove NimbleTools Core but keep your services:**

```bash
./scripts/uninstall.sh
```

**Complete removal (⚠️ deletes all MCP services):**

```bash
./scripts/uninstall.sh --remove-crd --remove-namespace
```

**Just testing? Remove everything:**

```bash
k3d cluster delete nimbletools-demo
```

## What You Just Built

🎉 **In 60 seconds, you:**

- Deployed a production-ready MCP service platform
- Transformed an MCP tool into a scalable HTTP service
- Set up automatic scaling and enterprise-grade reliability
- Created a foundation for your entire MCP ecosystem

## Your Next Adventure

🚀 **Ready for more?**

1. **[Deploy More Services](../examples/README.md)** - File browsers, databases, custom tools
2. **[Architecture Deep-Dive](ARCHITECTURE.md)** - Understand how it all works
3. **[Production Guide](../README.md#production-deployment)** - Security, monitoring, compliance
4. **[Build Your Own](../examples/custom-service/)** - Create custom MCP services
5. **[Join the Community](https://discord.gg/nimbletools)** - Share your creations!

**Welcome to effortless MCP deployment!** 🚀
