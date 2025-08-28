# NimbleTools Core

[![Actions status](https://github.com/nimblebrain/nimbletools-core/actions/workflows/ci.yml/badge.svg)](https://github.com/nimblebrain/nimbletools-core/actions)
[![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?logo=discord&logoColor=white)](https://www.nimbletools.ai/discord?utm_source=github&utm_medium=readme&utm_campaign=nimbletools-core&utm_content=header-badge)

**Deploy any MCP tool as an auto-scaling production service in 60 seconds**

## Why NimbleTools Core?

### For Developers & DevOps Teams

Turn command-line MCP tools into scalable HTTP services without rewriting a single line of code. Deploy once, scale automatically, pay nothing when idle.

### For Teams & Organizations

Share AI tools across teams from a central platform. No more "works on my machine" - every MCP tool becomes a reliable, discoverable service.

### For the MCP Ecosystem

The MCP ecosystem has powerful tools but inconsistent deployment patterns. NimbleTools Core provides a universal deployment layer that works with any MCP server - stdio or HTTP, Python or Go, simple or complex.

## Quick Start (60 seconds to production)

**Prerequisites:**

- **Kubernetes cluster** (we use k3d for local development)
- **Helm 3.0+** for package management
- **kubectl** configured for your cluster

**Local development setup:**

```bash
# Install k3d for local Kubernetes cluster
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

# Create local cluster
k3d cluster create nimbletools-demo --wait
```

**Installation:**

```bash
# Configure local domains for API access
echo "127.0.0.1 api.nimbletools.local mcp.nimbletools.local" | sudo tee -a /etc/hosts

# One command gets you running
curl -sSL https://raw.githubusercontent.com/nimblebrain/nimbletools-core/main/scripts/install.sh | bash
```

**What just happened?**

- ✅ Kubernetes operator deployed and running
- ✅ REST API available for service management
- ✅ Ready to deploy your first MCP service

**Verify it worked:**

```bash
kubectl get pods -n nimbletools-system
# Should show operator and API pods running
```

**Option 1: Deploy from the Community Registry**

```bash
# Add the community registry (dozens of ready-to-use services)
./scripts/register-community-registry.sh

# Browse available services via API
curl http://api.nimbletools.local/api/v1/registry/servers

# Deploy directly from the registry
# (Services come pre-configured with best practices)
```

**Option 2: Deploy your own service:**

```bash
# NOTE: remember to create workspace with CLI!
kubectl apply -f examples-everything-mcp.yaml
EOF
```

**Success!** 🎉 You now have a production MCP service that auto-scales and integrates with any MCP client.

## Choose Your Path

### 🆕 New to MCP?

**Model Context Protocol (MCP)** lets AI assistants use external tools and data sources. Think of it as "plugins for AI" - but instead of being locked to one AI system, MCP tools work with Claude, ChatGPT, local models, and more.

**What problems does MCP solve?**

- AI assistants can access real-time data (not just training data)
- Tools can be shared across different AI platforms
- Developers can create once, deploy everywhere

**Common MCP tools:** File browsers, database clients, API integrations, calculators, code analyzers, system monitors.

👉 **Next:** [Try our getting started examples](examples/README.md)

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

Instead of hunting for MCP services across GitHub repos and documentation, browse curated collections of ready-to-deploy services.

```bash
# Add the community registry
./scripts/register-community-registry.sh

# Browse ready-to-use services
curl http://api.nimbletools.local/api/v1/registry/servers | jq '.servers[].name'

# Deploy any service instantly
kubectl create -f registry-community/web-scraper.yaml
```

**What you get:**

- **Tested Services:** Every service is pre-configured and tested
- **Best Practices:** Proper security, scaling, and monitoring built-in
- **One-Click Deploy:** No YAML writing, just select and deploy
- **Community Driven:** Share your services, discover what others built

#### Create Your Own Registry

**For Teams & Organizations:** Create a private registry with your custom MCP services.

```bash
# Fork the registry template
git clone https://github.com/NimbleBrainInc/nimbletools-mcp-registry.git my-company-registry
cd my-company-registry

# Add your services to registry.yaml
# Follow the format in the community registry

# Host on GitHub Pages, S3, or any web server
git push origin main  # If using GitHub Pages

# Register with your NimbleTools Core instance
./scripts/register-community-registry.sh --registry-url https://my-company.github.io/my-company-registry/registry.yaml
```

**Use cases:**

- **Enterprise Service Catalogs:** Curated, approved services for your organization
- **Team-Specific Tools:** Department-specific MCP services and configurations
- **Compliance & Security:** Services that meet your organization's security requirements
- **Custom Business Logic:** Proprietary MCP services for internal processes

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
ntcli config set endpoint http://api.nimbletools.local

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

**Learn more:** [ntcli Documentation](https://docs.nimblebrain.ai/ntcli) | [GitHub Repository](https://github.com/NimbleBrainInc/ntcli)

## Installation Options

### Quick Install (Recommended)

Uses Helm charts to deploy the platform:

```bash
curl -sSL https://raw.githubusercontent.com/nimblebrain/nimbletools-core/main/scripts/install.sh | bash
```

### Custom Install

```bash
# Clone for customization
git clone https://github.com/nimblebrain/nimbletools-core.git
cd nimbletools-core

# Install with custom Helm values
./install.sh --namespace my-namespace --ingress-enabled --domain my-company.com
```

### Local Development

```bash
# Set up complete development environment
./scripts/dev-setup.sh
```

## Common Use Cases

### Share Team Tools

Deploy your team's internal MCP tools as services that everyone can access:

```bash
# Deploy a database query tool
kubectl apply -f examples/db-query-mcp.yaml

# Now any team member can query databases via MCP clients
```

### Serverless MCP Services

Perfect for tools that are used sporadically but need to be always available:

```yaml
spec:
  replicas: 0 # Scales to zero when not in use
  scaling:
    minReplicas: 0
    maxReplicas: 10
```

### Legacy Tool Integration

Have a valuable command-line tool that you want to make available via HTTP?

```yaml
spec:
  deployment:
    type: stdio
    executable: "/usr/local/bin/legacy-tool"
    args: ["--config", "/etc/config.json"]
```

## API Access

Once installed, access the management API:

```bash
# List workspaces
curl http://api.nimbletools.local/api/v1/workspaces

# List services
curl http://api.nimbletools.local/api/v1/workspaces/default/servers

# API documentation
open http://api.nimbletools.local/docs
```

## Examples & Templates

- **[Calculator Service](examples/calculator/)** - Simple HTTP-based MCP service
- **[File Browser](examples/file-browser/)** - stdio-based tool with universal adapter
- **[Database Query](examples/db-query/)** - Production-ready service with authentication
- **[Custom Development](examples/custom-service/)** - Build your own MCP service

## Production Deployment

### Prerequisites

- **Kubernetes 1.20+** with RBAC enabled (we recommend k3d for local development)
- **Helm 3.0+** for package management
- **Ingress Controller** (nginx, traefik, etc.) for external access

### Monitoring & Observability

```bash
# Install with monitoring enabled
./install.sh --monitoring-enabled

# View operator metrics
kubectl port-forward service/nimbletools-core-metrics 9090:9090
```

### Security & Compliance

```bash
# Install with enterprise security
./install.sh --auth-provider enterprise --network-policies --pod-security-standards
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

## Community & Support

- 📖 **[Full Documentation](https://docs.nimbletools.dev/core)**
- 🚀 **[Quick Start Guide](docs/QUICKSTART.md)**
- 🏗️ **[Architecture Guide](docs/ARCHITECTURE.md)**
- 💬 **[Discord Community](https://www.nimbletools.ai/discord?utm_source=github&utm_medium=readme&utm_campaign=nimbletools-core&utm_content=community-section)**
- 🐛 **[GitHub Issues](https://github.com/nimblebrain/nimbletools-core/issues)**
- 📋 **[Discussions](https://github.com/nimblebrain/nimbletools-core/discussions)**

## Contributing

We welcome contributions! Whether you're fixing bugs, adding features, or improving documentation:

1. **[Development Setup Guide](docs/DEVELOPMENT.md)**
2. **[Contribution Guidelines](CONTRIBUTING.md)**
3. **[Code of Conduct](CODE_OF_CONDUCT.md)**

### Quick Development Setup

```bash
git clone https://github.com/nimblebrain/nimbletools-core.git
cd nimbletools-core
./scripts/dev-setup.sh
```

## Status & Roadmap

**Current Status:** Beta - actively used in production environments with ongoing improvements

**Coming Soon:**

- Enhanced auto-scaling policies
- Built-in MCP registry integration
- Advanced monitoring and alerting
- Multi-cluster federation support

## License

Apache 2.0 - see [LICENSE](LICENSE) for details.

---

**Ready to get started?** Run the 60-second install and deploy your first MCP service:

```bash
curl -sSL https://raw.githubusercontent.com/nimblebrain/nimbletools-core/main/scripts/install.sh | bash
```
