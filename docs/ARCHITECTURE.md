# NimbleTools Core Architecture
**How we make MCP deployment effortless**

Understand how NimbleTools Core transforms any MCP tool into a production-ready, auto-scaling service. This guide explains the components, design decisions, and patterns that make it all work seamlessly.

## Why This Architecture?

**The MCP deployment problem:** Every MCP tool has different requirements - some use stdio, others HTTP, each has unique scaling needs, and deployment patterns are inconsistent across the ecosystem.

**Our solution:** A universal deployment layer that works with any MCP server while providing enterprise-grade reliability, auto-scaling, and operational simplicity.

**Design principles:**
- **Universal compatibility:** stdio or HTTP, any language, any complexity
- **Zero-configuration scaling:** From 0 to N replicas automatically  
- **Production-ready defaults:** Security, monitoring, and reliability built-in
- **Developer-friendly:** Deploy with a single YAML file

## System Overview

```
                    Your MCP Tools → Production Services

┌─────────────────────────────────────────────────────────────────┐
│                     NimbleTools Core Platform                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  🎛️  Management Layer                 ⚙️  Automation Layer      │
│  ┌─────────────────┐                 ┌──────────────────┐      │
│  │   REST API      │                 │   MCP Operator   │      │
│  │                 │                 │                  │      │
│  │ • Service CRUD  │◄────────────────┤ • Auto-scaling   │      │
│  │ • Health Checks │                 │ • Lifecycle Mgmt │      │
│  │ • Registry Mgmt │                 │ • Self-healing   │      │
│  └─────────────────┘                 └──────────────────┘      │
│           ▲                                                     │
│           │                                                     │
│  ┌─────────────────┐          🗂️  Service Discovery            │
│  │     ntcli       │          ┌──────────────────┐             │
│  │                 │          │   MCP Registry   │             │
│  │ • CLI Commands  │◄─────────┤                  │             │
│  │ • Automation    │          │ • Service Catalog│             │
│  │ • CI/CD Ready   │          │ • Templates      │             │
│  └─────────────────┘          │ • Community Hub  │             │
│                               └──────────────────┘             │
├─────────────────────────────────────────────────────────────────┤
│                      🚀 Your MCP Services                      │
│                                                                 │
│  📊 Analytics     🗃️ Database      🌐 HTTP Service             │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐           │
│  │ stdio tool  │   │ Python CLI  │   │ Native HTTP │           │
│  │ via Adapter │   │ via Adapter │   │ Direct      │           │
│  └─────────────┘   └─────────────┘   └─────────────┘           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**The ecosystem:** Registry for service discovery, CLI for automation, platform for production deployment.

## Core Components

### 🤖 MCP Operator: The Automation Engine

**What it does:** Transforms your MCPService declarations into running, healthy services automatically.

**Key capabilities:**
- **Intelligent Scaling:** Monitors demand and adjusts replicas (including scale-to-zero)
- **Self-Healing:** Detects failures and restarts services automatically
- **Resource Optimization:** Right-sizes containers based on usage patterns
- **Health Management:** Continuous monitoring with automatic recovery

**How it works:**
```python
# You declare what you want:
apiVersion: mcp.nimbletools.dev/v1
kind: MCPService
spec:
  replicas: 0  # Start with serverless

# Operator handles everything:
# • Creates Kubernetes Deployment
# • Sets up Service endpoints
# • Configures health checks
# • Monitors and scales automatically
```

**Operator workflow:**
```
kubectl apply → Operator Watches → Resource Creation → Health Monitoring
      ↓              ↓                    ↓                 ↓
 MCPService → Deployment + Service → Running Pod → Scaling Decisions
```

### 🔌 Universal Adapter: The Compatibility Layer

**The problem:** Most MCP tools are command-line utilities using stdio, but modern infrastructure expects HTTP APIs.

**Our solution:** A transparent bridge that makes any stdio MCP tool look like a native HTTP service.

**What it enables:**
- Deploy existing command-line MCP tools without modification
- Consistent HTTP interface for all services
- Proper lifecycle management for subprocess-based tools
- Enterprise-grade error handling and timeouts

**How it works:**
```
HTTP API Request → Universal Adapter → stdin → Your MCP Tool
       ↓                ↓                         ↓
JSON Response ← HTTP Response ← stdout ← Tool Output
```

**Example transformation:**
```bash
# Your existing tool:
./my-mcp-tool --server

# Becomes this HTTP service:
curl http://service/mcp -d '{"method": "tools/list"}'
```

### 🎛️ Management API: Your Control Center

**What it provides:** A clean, RESTful interface for managing your entire MCP service ecosystem.

**Key capabilities:**
- **Service Lifecycle:** Deploy, scale, update, and monitor services
- **Workspace Management:** Organize services by team, project, or environment
- **Health Monitoring:** Real-time status and performance metrics
- **Interactive Documentation:** Built-in API explorer

**Authentication flexibility:**
```
Open Source → No authentication (development/internal use)
  ↓
Enterprise → JWT-based authentication with RBAC
```

**Essential endpoints:**
- `GET /api/v1/workspaces` - List all workspaces
- `POST /api/v1/workspaces/{id}/servers` - Deploy new service
- `GET /api/v1/workspaces/{id}/servers` - List services
- `GET /health` - System health check
- `GET /docs` - Interactive API documentation

### 📋 MCPService Resource: Your Service Declaration

**What it is:** A Kubernetes-native way to declare "I want this MCP tool running as a service."

**Why it matters:** Declarative configuration means you describe the outcome, and the system figures out how to achieve it.

**Basic structure:**
```yaml
apiVersion: mcp.nimbletools.dev/v1
kind: MCPService
metadata:
  name: my-service
spec:
  # What to run
  container:
    image: your-org/mcp-tool:latest
    port: 8000
  
  # How to run it
  deployment:
    type: http  # or "stdio" for command-line tools
  
  # Scaling behavior  
  replicas: 0  # Serverless: scale from 0 based on demand
  
  # Tool metadata
  tools:
    - name: "analyze"
      description: "Analyze data patterns"
```

**Automatic status tracking:**
```yaml
status:
  phase: Running        # Pending → Running → Scaling
  readyReplicas: 3      # How many are actually working
  conditions:
    - type: Ready
      status: "True"
      lastTransitionTime: "2024-01-15T10:30:00Z"
```

**What you get:** Real-time visibility into service health without manual monitoring.

### 🗂️ MCP Registry: Service Discovery Layer

**The problem:** MCP services are scattered across repositories, blog posts, and documentation. Finding and deploying the right service is time-consuming and error-prone.

**Our solution:** Centralized service registries with tested, documented, ready-to-deploy MCP services.

**Registry Architecture:**
```yaml
# registry.yaml format
name: "community-registry"
version: "1.0.0"
servers:
  - name: "web-scraper"
    status: "active"
    meta:
      description: "Extract content from web pages"
      category: "data-extraction"
      tags: ["web", "scraping", "content"]
    container:
      image: "nimbletools/web-scraper:v1.2.0"
      port: 8000
    deployment:
      type: "http"
    tools:
      - name: "scrape_url"
        description: "Extract content from a URL"
```

**How it works:**
1. **Registry Creation:** Fork the [registry template](https://github.com/NimbleBrainInc/nimbletools-mcp-registry)
2. **Service Addition:** Add your services following the schema
3. **Distribution:** Host on GitHub Pages, S3, or any web server
4. **Registration:** `register-community-registry.sh --registry-url YOUR_URL`
5. **Discovery:** Services appear in API and can be deployed instantly

**Registry benefits:**
- **Quality Assurance:** All services tested and documented
- **Consistent Configuration:** Standardized security and scaling settings
- **Version Management:** Semantic versioning for service updates
- **Team Collaboration:** Shared service catalogs for organizations

### 🖥️ ntcli: Developer Experience Layer

**The vision:** Every operation available through the REST API should be accessible via an intuitive command-line interface.

**Architecture:**
```
ntcli command → HTTP Request → NimbleTools Core API → Kubernetes Action
     ↓              ↓                    ↓                    ↓
User Intent → Structured Data → Service Logic → Infrastructure Change
```

**Core capabilities:**
- **Configuration Management:** `ntcli config set endpoint https://api.company.com`
- **Workspace Operations:** `ntcli workspace create/list/delete`
- **Service Lifecycle:** `ntcli server deploy/scale/restart/delete`
- **Registry Management:** `ntcli registry add/list/search`
- **Status Monitoring:** `ntcli status workspace production`

**Developer workflows:**
```bash
# Development workflow
ntcli workspace create feature-branch-123
ntcli server deploy my-service --workspace feature-branch-123 --replicas 1
# Test, iterate
ntcli workspace delete feature-branch-123

# Production deployment
ntcli registry search data-processing
ntcli server deploy analytics-engine --workspace production --replicas 5
ntcli server status analytics-engine --workspace production
```

**CI/CD Integration:**
```yaml
# GitHub Actions example
- name: Deploy MCP Service
  run: |
    ntcli config set endpoint ${{ secrets.NIMBLETOOLS_ENDPOINT }}
    ntcli config set auth-token ${{ secrets.NIMBLETOOLS_TOKEN }}
    ntcli server deploy ${{ matrix.service }} --workspace production
```

**Implementation:** [ntcli GitHub Repository](https://github.com/NimbleBrainInc/ntcli) | [Documentation](https://docs.nimblebrain.ai/ntcli)

## Deployment Patterns

### 🌐 HTTP-Native Services
**For services built with HTTP APIs from the start**

```yaml
# Your service already speaks HTTP
spec:
  deployment:
    type: http
  container:
    image: your-org/web-scraper-mcp:latest
    port: 8000
```

**What happens:**
- Direct deployment of your container
- Kubernetes Service routes traffic to your port
- Built-in health checks and load balancing

### 💻 Command-Line Tools
**For existing stdio-based MCP tools**

```yaml
# Your existing CLI tool
spec:
  deployment:
    type: stdio
    executable: "/usr/local/bin/data-analyzer"
    args: ["--server", "--config=/etc/config.json"]
```

**What happens:**
- Universal Adapter wraps your CLI tool
- stdio communication converted to HTTP API
- Your tool runs as a managed subprocess
- Full lifecycle management and health monitoring

## Organization Patterns

### 🏠 Simple Setup (Open Source)
**Perfect for individuals and small teams**

- Core components in `nimbletools-system` namespace
- Services deployed anywhere you want
- Cluster-wide permissions for simplicity
- Single management interface

### 🏢 Enterprise Setup
**Designed for organizations with multiple teams**

- Each team gets their own workspace (namespace)
- User-based access controls and resource quotas
- Audit logging and compliance features
- Centralized management with team isolation

## Scaling Intelligence

### ⚡ Serverless Mode (Scale-to-Zero)
**Pay nothing when not in use, instant scaling when needed**

```yaml
spec:
  replicas: 0  # Start with zero instances
```

**How it works:**
1. **Idle state:** Zero pods running, zero cost
2. **Request arrives:** Operator detects demand, spins up pod
3. **Cold start:** ~10-30 seconds to first response (cached images)
4. **Auto scale-down:** Returns to zero after idle period

### 📈 Performance Optimization

**Smart defaults that just work:**
- CPU and memory limits based on container requirements
- Health checks ensure traffic only goes to ready pods
- Kubernetes-native load balancing distributes requests
- Built-in metrics help you understand usage patterns

## Security by Design

### 🔒 Defense in Depth
**Security isn't an afterthought - it's built into every layer**

**Container Security:**
- Non-root containers by default
- Read-only filesystems prevent tampering
- Minimal capabilities (no privileged access)
- Signed images with vulnerability scanning

**Network Security:**
- Services isolated by default
- Optional network policies for strict traffic control
- TLS termination at ingress
- Service mesh encryption (optional)

**Access Control:**
- Kubernetes RBAC with least-privilege principles
- Pluggable authentication (no-auth → JWT → enterprise SSO)
- Workspace-level isolation
- Audit logging for compliance

**Example security configuration:**
```yaml
# Automatic security defaults
securityContext:
  runAsNonRoot: true          # Never run as root
  readOnlyRootFilesystem: true # Prevent file tampering
  capabilities:
    drop: ["ALL"]             # Remove all privileges
```

## Built-in Observability

### 📊 What You Can Monitor
**Comprehensive visibility without complex setup**

**Service Health:**
- Request rates and response times per MCP service
- Success/error rates and typical failure patterns
- Scaling events (when and why services scale up/down)
- Resource usage (CPU, memory, network)

**Platform Health:**
- Operator performance (how quickly changes are applied)
- API server metrics (authentication, request patterns)
- Cluster resource utilization
- Error rates and recovery times

**Business Insights:**
- Most popular MCP tools in your organization
- Peak usage times and scaling patterns
- Cost optimization opportunities
- User adoption metrics

### 🔍 Troubleshooting Made Easy

**Structured logging with correlation:**
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "service": "calculator",
  "request_id": "req-abc123",
  "message": "Tool execution completed",
  "duration_ms": 245
}
```

**Integration-ready:**
- Works with Prometheus, Grafana, ELK stack
- OpenTelemetry compatible for distributed tracing
- Standard Kubernetes metrics and health checks

## Extensibility

### 🔧 Customization Points
**Built for extension without modification**

**Custom Authentication:**
```python
class CustomAuthProvider:
    def authenticate(self, request):
        # Your authentication logic
        return UserContext(user_id="...", permissions=[...])
```

**Custom Scaling Policies:**
```yaml
spec:
  scaling:
    policy: custom
    triggers:
      - type: queue-depth
        threshold: 10
      - type: response-time
        threshold: 500ms
```

**Webhook Integration:**
```yaml
# Validate services before deployment
webhook:
  validation:
    url: https://your-validator.com/validate
    rules:
      - operations: ["CREATE", "UPDATE"]
        resources: ["mcpservices"]
```

**Why this matters:** Adapt the platform to your organization's needs without forking the codebase.

## How Everything Works Together

### 🚀 Service Deployment Journey
**From `kubectl apply` to running service**

```
1. You: kubectl apply -f my-service.yaml
2. Kubernetes: Validates and stores MCPService
3. Operator: Detects new service, creates Deployment + Service
4. Kubernetes: Schedules pod, pulls image, starts container
5. Service: Health checks pass, ready to receive traffic
6. You: Service available at http://service-name:8000
```

### ⚡ Request Processing Flow
**What happens when someone uses your MCP service**

```
MCP Client Request → Kubernetes Service → Load Balancer → Healthy Pod
        ↓                    ↓               ↓              ↓
   JSON-RPC Call → HTTP Route → Container → MCP Tool Execution
        ↓                    ↓               ↓              ↓
    Tool Response ← HTTP Response ← stdout ← Tool Completes
```

### 🔄 Serverless Scaling
**The magic of scale-to-zero**

```
No requests for 5 minutes → Operator scales to 0 → Pod terminates
         ↓                         ↓                    ↓
    Zero cost                Pod resources freed    Ready for next request

New request arrives → Operator scales to 1 → Pod starts → Service ready
       ↓                     ↓                ↓            ↓ 
  ~30s cold start        Image cached      Health check   Handle request
```

## Configuration Management

### 🎯 Environment-Specific Configuration
**One codebase, many environments**

```bash
# Development
./install.sh -f values-dev.yaml

# Staging  
./install.sh -f values-staging.yaml

# Production
./install.sh -f values-prod.yaml --auth-provider enterprise
```

**What changes between environments:**
- Resource limits (dev: small, prod: large)
- Authentication (dev: none, prod: enterprise)
- Scaling policies (dev: fixed, prod: auto)
- Monitoring level (dev: basic, prod: comprehensive)

### 🔐 Secrets Management
**Keep sensitive data secure**

```yaml
# Database credentials via Kubernetes Secret
spec:
  container:
    env:
      - name: DB_PASSWORD
        valueFrom:
          secretKeyRef:
            name: db-credentials
            key: password
```

## Production Reliability

### 🏗️ High Availability by Default
**Built for uptime, not complexity**

**Core components:**
- **MCP Operator:** Single instance with leader election (only one active)
- **API Server:** Multiple replicas behind load balancer
- **Your Services:** You choose replica count (1 for dev, 3+ for prod)

**Data resilience:**
- All state stored in Kubernetes etcd (automatically backed up)
- Service configurations are declarative (reproducible)
- No single points of failure in request path

### 🔄 Disaster Recovery
**Simple backup and restore**

```bash
# Backup: Export all your service definitions
kubectl get mcpservices -A -o yaml > my-services-backup.yaml

# Restore: Apply to new cluster
kubectl apply -f my-services-backup.yaml
```

## Performance at Scale

### 📈 Resource Optimization
**Efficient by design**

**Smart resource management:**
- **Right-sizing:** Containers start small, grow based on actual usage
- **Bin packing:** Kubernetes efficiently schedules pods across nodes
- **Resource pooling:** Shared operator and API server across all services
- **Automatic cleanup:** Unused resources garbage collected

**Scaling strategies:**
```yaml
# Development: Fixed small resources
resources:
  requests: {cpu: 100m, memory: 128Mi}
  limits: {cpu: 200m, memory: 256Mi}

# Production: Auto-scaling based on usage
horizontalPodAutoscaler:
  minReplicas: 2
  maxReplicas: 50
  targetCPUUtilizationPercentage: 70
```

### 🚀 Network Performance
**Fast by default, faster with tuning**

**Built-in optimizations:**
- Kubernetes-native service discovery (no external dependencies)
- HTTP/2 and connection pooling in Universal Adapter
- Request compression and response caching
- Health check optimizations

**Optional enhancements:**
- Service mesh (Istio) for advanced traffic management
- CDN integration for static responses
- Custom load balancing algorithms

---

**This architecture transforms the complex world of MCP deployment into a simple, reliable platform that scales from your laptop to enterprise production environments.**
