# NimbleTools Core

![GitHub Release](https://img.shields.io/github/v/release/NimbleBrainInc/nimbletools-core)
![GitHub License](https://img.shields.io/github/license/NimbleBrainInc/nimbletools-core)
[![Actions status](https://github.com/NimbleBrainInc/nimbletools-core/actions/workflows/ci.yml/badge.svg)](https://github.com/NimbleBrainInc/nimbletools-core/actions)
[![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?logo=discord&logoColor=white)](https://www.nimbletools.ai/discord?utm_source=github&utm_medium=readme&utm_campaign=nimbletools-core&utm_content=header-badge)

**Deploy any MCP tool as a production service in 60 seconds**

## Why NimbleTools Core?

### For Developers & DevOps Teams

Turn command-line MCP tools into scalable HTTP services without rewriting a single line of code. Deploy once, scale automatically, pay nothing when idle.

### For Teams & Organizations

Share AI tools across teams from a central platform. No more "works on my machine" - every MCP tool becomes a reliable, discoverable service.

### For the MCP Ecosystem

The MCP ecosystem has powerful tools but inconsistent deployment patterns. NimbleTools Core provides a universal deployment layer that works with any MCP server - stdio or HTTP, Python or Go, simple or complex.

## Quick Start (60 seconds to production)

**Prerequisites:**

- **Helm 3.0+** for package management
- **k3d** for local Kubernetes cluster (automatic setup)

**Installation:**

```bash
# One command gets you running (creates local cluster if needed)
curl -sSL https://raw.githubusercontent.com/NimbleBrainInc/nimbletools-core/refs/heads/main/install.sh | bash
```

**What just happened?**

- ✅ Local Kubernetes cluster created (k3d-nimbletools-quickstart)
- ✅ NimbleTools operator deployed and running
- ✅ REST API available for service management
- ✅ Ready to deploy your first MCP service

**Verify it worked:**

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

**Deploy your first MCP service:**

```bash
# Fetch the echo server definition from the registry
curl https://registry.nimbletools.ai/v0/servers/ai.nimblebrain%2Fecho > echo-server.json

# Create a workspace
curl -X POST http://api.nimbletools.dev/v1/workspaces \
  -H "Content-Type: application/json" \
  -d '{"name": "my-workspace", "description": "My first workspace"}'

# Deploy the echo server
curl -X POST http://api.nimbletools.dev/v1/workspaces/my-workspace/servers \
  -H "Content-Type: application/json" \
  -d @echo-server.json

# Verify the service is running
kubectl get pods -n ws-my-workspace
```

**Success!** 🎉 You now have a production MCP service that scales and integrates with any MCP client.

## Choose Your Path

### 🆕 New to MCP?

**Model Context Protocol (MCP)** lets AI assistants use external tools and data sources. Think of it as "plugins for AI" - but instead of being locked to one AI system, MCP tools work with Claude, ChatGPT, local models, and more.

**What problems does MCP solve?**

- AI assistants can access real-time data (not just training data)
- Tools can be shared across different AI platforms
- Developers can create once, deploy everywhere

**Common MCP tools:** File browsers, database clients, API integrations, calculators, code analyzers, system monitors.

### ⚡ Experienced with MCP?

Skip the intro - you know MCP tools are powerful but deployment is inconsistent. Every tool has different requirements, some are stdio-only, others HTTP-only, and scaling is a manual nightmare.

**NimbleTools Core solves this by:**

- **Universal Deployment**: stdio tools run via our adapter, HTTP tools run natively
- **Auto-scaling**: Scale from 0 to N replicas automatically
- **Production Ready**: Built-in monitoring, security, and reliability

👉 **Next:** [Deploy your existing MCP tools](docs/QUICKSTART.md)

### 🔧 Kubernetes Expert?

You understand the operational complexity of running services at scale. NimbleTools Core provides Kubernetes-native primitives for MCP service lifecycle management.

**Architecture highlights:**

- Custom MCPService CRD with full lifecycle management
- Kubernetes operator pattern for automated operations
- Scale-to-zero with automatic cold-start handling
- Multi-tenant workspace isolation

👉 **Next:** [Architecture deep-dive](docs/ARCHITECTURE.md)

## Core Features

🚀 **60-Second Deployment**  
From zero to production MCP runtime in under a minute

⚡ **Zero-Waste Scaling**  
Automatically scale from 0 to N replicas based on demand - pay nothing when idle

🔧 **Works With Any MCP Tool**  
Deploy stdio command-line tools and native HTTP services with the same interface

🗂️ **Service Registry**  
Browse and deploy from curated collections of MCP services - no more hunting across repos

🖥️ **Command-Line Interface**  
Full CLI for automation, CI/CD, and developer workflows (ntcli)

🏢 **Team-Ready from Day One**  
Multi-workspace support, pluggable authentication, comprehensive observability

🔒 **Production Security**  
Kubernetes-native RBAC, network policies, signed images, vulnerability scanning

🛠️ **Developer Friendly**  
Local development with k3d, hot-reload, comprehensive examples and documentation

## Service Discovery Made Easy

### 🗂️ **MCP Registry: Your Service Marketplace**

**Turn service discovery from hunting to browsing**

Instead of hunting for MCP services across GitHub repos and documentation, browse curated collections of ready-to-deploy services from the NimbleTools Registry.

```bash
# Browse all available services
curl https://registry.nimbletools.ai/v0/servers | jq '.servers[].name'

# Get details for a specific server
curl https://registry.nimbletools.ai/v0/servers/ai.nimblebrain%2Fecho

# Deploy any service instantly
curl https://registry.nimbletools.ai/v0/servers/ai.nimbletools%2Fecho > echo-server.json
curl -X POST http://api.nimbletools.dev/v1/workspaces/my-workspace/servers \
  -H "Content-Type: application/json" \
  -d @echo-server.json
```

**Available in the registry:**

- `ai.nimbletools/echo` - Testing and debugging tool
- `ai.nimbletools/finnhub` - Financial market data API
- `ai.nimbletools/github` - GitHub integration (repos, PRs, issues)
- `ai.nimbletools/postgres-mcp` - PostgreSQL database access
- `ai.nimbletools/tavily-mcp` - Web search and extraction
- `ai.nimbletools/nationalparks-mcp` - US National Parks data
- And more...

**Registry features:**

- **Tested Services:** Every service is pre-configured and tested
- **Best Practices:** Proper security, scaling, and monitoring built-in
- **API Access:** Browse and query servers programmatically
- **Full Documentation:** Complete API docs at [registry.nimbletools.ai/docs](https://registry.nimbletools.ai/docs)

#### Publishing Your Own Servers

**For Teams & Organizations:** Publish your custom MCP services to your own registry or contribute to the community registry.

See the full documentation at [registry.nimbletools.ai/docs](https://registry.nimbletools.ai/docs) for:

- Server definition schema
- Publishing requirements
- Validation and testing
- Registry API reference

**Use cases:**

- **Enterprise Service Catalogs:** Curated, approved services for your organization
- **Team-Specific Tools:** Department-specific MCP services and configurations
- **Compliance & Security:** Services that meet your organization's security requirements
- **Custom Business Logic:** Proprietary MCP services for internal processes

**Learn more:** [NimbleTools Registry](https://registry.nimbletools.ai) | [API Documentation](https://registry.nimbletools.ai/docs) | [GitHub Repository](https://github.com/NimbleBrainInc/mcp-registry)

### 🖥️ **ntcli: Your Command-Line Companion**

**Manage your MCP platform without leaving the terminal**

Everything you can do through the web API, now available as intuitive CLI commands for automation and developer workflows.

**Installation:**

```bash
# Install ntcli
pip install ntcli
# OR
curl -sSL https://github.com/NimbleBrainInc/ntcli/releases/latest/download/install.sh | bash
```

**Usage:**

```bash
# Configure your NimbleTools Core endpoint
ntcli config set endpoint http://api.nimbletools.dev

# Workspace management
ntcli workspace create dev-team
ntcli workspace list

# Service deployment
ntcli server deploy calculator --workspace prod
ntcli server scale calculator --replicas 5

# Registry integration
ntcli registry add https://my-company.com/registry.yaml
ntcli registry search database
```

**Perfect for:**

- **CI/CD Pipelines:** Automated deployments and infrastructure-as-code
- **Developer Workflows:** Quick service management from the terminal
- **Operations Teams:** Bulk operations and scripting

**Learn more:** [GitHub Repository](https://github.com/NimbleBrainInc/ntcli)

## Installation Options

### Quick Install (Recommended)

Uses Helm charts to deploy the platform:

```bash
curl -sSL https://raw.githubusercontent.com/NimbleBrainInc/nimbletools-core/refs/heads/main/install.sh | bash
```

### Custom Install

```bash
# Clone for customization
git clone https://github.com/NimbleBrainInc/nimbletools-core.git
cd nimbletools-core

# Install with custom Helm values
./install.sh --namespace my-namespace --ingress-enabled --domain my-company.com
```

### Local Development

```bash
# Set up complete development environment
./scripts/dev-setup.sh
```

## API Access

Once installed, access the management API:

```bash
# List workspaces
curl http://api.nimbletools.dev/api/v1/workspaces

# List services
curl http://api.nimbletools.dev/api/v1/workspaces/default/servers

# API documentation
open http://api.nimbletools.dev/docs
```

## Troubleshooting

### Quick Diagnostics

```bash
# Check operator health
kubectl logs -l app.kubernetes.io/component=operator -n nimbletools-core-system

# Check service status
kubectl get mcpservices --all-namespaces

# Verify API health
curl http://api.nimbletools.ai/health
```

### Common Issues

**"Cannot connect to Kubernetes cluster"**

```bash
# Create local cluster first
k3d cluster create nimbletools-test --wait
./install.sh
```

**"MCPService not creating pods"**

```bash
# Check operator logs for detailed error messages
kubectl logs -l app.kubernetes.io/component=operator -n nimbletools-core-system -f
```

**"Service not accessible"**

```bash
# Port-forward and test directly
kubectl port-forward service/your-service 8080:8000
curl http://api.nimbletools.ai/health
```

## Documentation

📚 **[Full Documentation](docs/)** - Complete guides and references

## Community & Support

- 💬 **[Discord Community](https://www.nimblebrain.ai/discord?utm_source=github&utm_medium=readme&utm_campaign=nimbletools-core&utm_content=community-section)**
- 🐛 **[GitHub Issues](https://github.com/NimbleBrainInc/nimbletools-core/issues)**
- 📋 **[Discussions](https://github.com/NimbleBrainInc/nimbletools-core/discussions)**

## Contributing

We welcome contributions! Whether you're fixing bugs, adding features, or improving documentation:

1. **[Development Setup Guide](docs/DEVELOPMENT.md)**
2. **[Contribution Guidelines](CONTRIBUTING.md)**
3. **[Code of Conduct](CODE_OF_CONDUCT.md)**

### Quick Development Setup

```bash
git clone https://github.com/NimbleBrainInc/nimbletools-core.git
cd nimbletools-core
./redeploy.sh
```

## License

Apache 2.0 - see [LICENSE](LICENSE) for details.

---

**Ready to get started?** Run the 60-second install and deploy your first MCP service:

```bash
curl -sSL https://raw.githubusercontent.com/NimbleBrainInc/nimbletools-core/refs/heads/main/install.sh | bash
```

Join our [Discord community](https://www.nimbletools.ai/discord?utm_source=github&utm_medium=readme&utm_campaign=nimbletools-core&utm_content=bottom) to connect with other contributors and maintainers.
