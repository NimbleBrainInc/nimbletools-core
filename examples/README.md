# NimbleTools Core Examples

This directory contains example MCPService configurations demonstrating core deployment patterns for the NimbleTools Core platform.

## Quick Start

To deploy any example to your cluster:

```bash
# Apply an example
kubectl apply -f examples/echo-mcp.yaml

# Check deployment status
kubectl get mcpservices

# View logs
kubectl logs -l app=echo-mcp
```

## Example Services

### 1. Echo MCP Service (`echo-mcp.yaml`)
**Purpose:** HTTP-based MCP service demonstrating direct container deployment.

**Features:**
- Direct HTTP service deployment
- Built-in container image (no universal adapter needed)
- Production-ready HTTP MCP server
- Health checks at `/health` endpoint

**Deployment Type:** HTTP
**Container:** `nimbletools/mcp-echo:latest`
**Port:** 8000
**Health Check:** `/health`

**Use Cases:**
- Learning MCPService basics
- Testing HTTP service deployment
- Template for containerized MCP services
- Production HTTP MCP deployments

### 2. Everything MCP Service (`everything-mcp.yaml`)
**Purpose:** STDIO-based MCP service demonstrating universal adapter deployment.

**Features:**
- Universal adapter for stdio protocol
- NPM package installation at runtime
- JSON-RPC to HTTP bridge
- Auto-discovery of server capabilities

**Deployment Type:** STDIO  
**Container:** `nimbletools/universal-adapter:latest`
**Executable:** `npx @modelcontextprotocol/server-everything`
**Health Check:** `/health` (provided by universal adapter)

**Use Cases:**
- Running npm-based MCP servers
- Testing stdio protocol adaptation
- Demonstrating universal adapter functionality
- Template for command-line MCP tools

## Deployment Patterns

### HTTP MCP Server (Echo)
```bash
# Deploy HTTP-based echo server
kubectl apply -f examples/echo-mcp.yaml

# Check status
kubectl get mcpservice echo

# Test health endpoint
kubectl port-forward service/echo-service 8080:8000
curl http://localhost:8080/health
```

### STDIO MCP Server (Everything)
```bash
# Deploy stdio-based everything server  
kubectl apply -f examples/everything-mcp.yaml

# Monitor npm package installation
kubectl logs -l app=everything -f

# Check when ready
kubectl get mcpservice everything

# Test MCP endpoint
kubectl port-forward service/everything-service 8080:8000
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{}}}'
```

### Deploy Both Examples
```bash
# Deploy both examples to see HTTP vs STDIO patterns
kubectl apply -f examples/echo-mcp.yaml
kubectl apply -f examples/everything-mcp.yaml

# Monitor deployment progress
kubectl get mcpservices --watch

# Check all pods
kubectl get pods | grep -E "(echo|everything)"
```

## Configuration Customization

### Environment Variables
Both echo and everything services can be customized with environment variables:

**Echo Service:**
```yaml
spec:
  environment:
    LOG_LEVEL: "debug"
    ECHO_PREFIX: "Echo: "
```

**Everything Service (STDIO):**
```yaml
spec:
  environment: {}  # Everything server uses default configuration
  # Universal adapter passes environment to stdio process
```

### Resource Limits
Adjust resource limits based on your cluster capacity:

```yaml
spec:
  resources:
    limits:
      cpu: "500m"
      memory: "512Mi"
    requests:
      cpu: "100m" 
      memory: "128Mi"
```

### Scaling Configuration
Control replica counts and scaling behavior:

```yaml
spec:
  replicas: 0  # Scale-to-zero when not in use
  # replicas: 2  # Fixed 2 replicas for high availability
  # replicas: 1  # Single replica for development
  
  scaling:
    minReplicas: 0
    maxReplicas: 10
    targetConcurrency: 10
    scaleDownDelay: "5m"
```

## Complete Example Files

### Echo MCP Service (echo-mcp.yaml)
```yaml
apiVersion: mcp.nimbletools.dev/v1
kind: MCPService
metadata:
  name: echo
  namespace: default  # Update with your workspace namespace
  labels:
    mcp.nimbletools.dev/service: "true"
spec:
  replicas: 1
  timeout: 300
  environment: {}
  
  container:
    image: "nimbletools/mcp-echo:latest"
    registry: "docker.io"
    port: 8000
    
  deployment:
    type: "http"
    healthPath: "/health"
    
  resources:
    requests:
      cpu: "50m"
      memory: "128Mi"
    limits:
      cpu: "200m" 
      memory: "256Mi"
      
  scaling:
    minReplicas: 0
    maxReplicas: 10
    targetConcurrency: 10
    scaleDownDelay: "5m"
    
  routing:
    path: "/services/echo"
    port: 8000
    healthPath: "/health"
    discoveryPath: "/mcp/discover"
```

### Everything MCP Service (everything-mcp.yaml)
```yaml
apiVersion: mcp.nimbletools.dev/v1
kind: MCPService
metadata:
  name: everything
  namespace: default  # Update with your workspace namespace
  labels:
    mcp.nimbletools.dev/service: "true"
spec:
  replicas: 1
  timeout: 300
  environment: {}
  
  container:
    image: "nimbletools/universal-adapter:latest"
    registry: "docker.io"
    port: 8000
    
  deployment:
    type: "stdio"
    healthPath: "/health"
    stdio:
      executable: "npx"
      args: ["-y", "@modelcontextprotocol/server-everything"]
      workingDir: "/tmp"
      
  credentials: []
  
  resources:
    requests:
      cpu: "50m"
      memory: "128Mi"
    limits:
      cpu: "200m" 
      memory: "256Mi"
      
  scaling:
    minReplicas: 0
    maxReplicas: 10
    targetConcurrency: 10
    scaleDownDelay: "5m"
    
  routing:
    path: "/services/everything"
    port: 8000
    healthPath: "/health"
    discoveryPath: "/mcp/discover"
```

## Testing Examples

### Health Check Testing
```bash
# Check if services are healthy
kubectl get pods -l example=true

# Test specific service endpoint
kubectl port-forward service/echo-mcp 8080:8000
curl http://localhost:8080/health
```

### MCP Protocol Testing
```bash
# Test MCP tools discovery
curl -X POST http://localhost:8080/mcp/tools/list

# Test specific tool
curl -X POST http://localhost:8080/mcp/tools/echo \
  -H "Content-Type: application/json" \
  -d '{"arguments": {"text": "Hello World"}}'
```

### Load Testing
```bash
# Scale up for load testing
kubectl patch mcpservice echo-mcp -p '{"spec":{"replicas": 5}}'

# Use hey or ab for load testing
hey -n 1000 -c 10 http://localhost:8080/health
```

## Server Status Examples

### Deployment Status Progression

When deploying servers, they progress through different status stages. Here are examples showing the typical deployment flow:

#### Initial Deployment - Unknown Status
After deploying a server, it initially shows as `Unknown` while the pod is being created and started:

```
ntcli server info finnhub
✔ 📦 Server details: finnhub

⚪ finnhub [Unknown]

📊 Server Information
  Server ID: finnhub
  Name: finnhub
  Status: ⚪ Unknown
  Image: nimbletools/mcp-finnhub:latest
  Namespace: ws-foobar2-079f0a5b-a5e6-4962-9780-dd7c10e3ff34
  Created: 8/27/2025, 10:49:24 PM

🚀 Deployment
  Deployment Ready: ❌ No
  Service Endpoint: /079f0a5b-a5e6-4962-9780-dd7c10e3ff34/finnhub/mcp

⚡ Scaling
  Current Replicas: 1
  Ready Replicas: Unknown
  Max Replicas: 4

Workspace: foobar2 (079f0a5b-a5e6-4962-9780-dd7c10e3ff34)
```

#### Deployment Complete - Running Status
Once the pod has successfully started and passed health checks, the status changes to `Running`:

```
ntcli server info finnhub
✔ 📦 Server details: finnhub

🟢 finnhub [Running]

📊 Server Information
  Server ID: finnhub
  Name: finnhub
  Status: 🟢 Running
  Image: nimbletools/mcp-finnhub:latest
  Namespace: ws-foobar2-079f0a5b-a5e6-4962-9780-dd7c10e3ff34
  Created: 8/27/2025, 10:49:24 PM

🚀 Deployment
  Deployment Ready: ✅ Yes
  Service Endpoint: /079f0a5b-a5e6-4962-9780-dd7c10e3ff34/finnhub/mcp

⚡ Scaling
  Current Replicas: 1
  Ready Replicas: 1
  Max Replicas: 4

Workspace: foobar2 (079f0a5b-a5e6-4962-9780-dd7c10e3ff34)
```

#### Key Status Differences

| Status | Indicator | Deployment Ready | Ready Replicas | Description |
|--------|-----------|------------------|----------------|-------------|
| Unknown | ⚪ | ❌ No | Unknown | Pod is starting, containers initializing |
| Running | 🟢 | ✅ Yes | 1 | Pod is ready, service endpoint available |

#### Common Status Transitions

1. **Unknown** → **Running**: Normal successful deployment
2. **Unknown** → **Failed**: Pod failed to start (image pull errors, resource limits, etc.)
3. **Running** → **Unknown**: Temporary status during pod restarts
4. **Running** → **Scaling**: When replicas are being modified

#### Monitoring Deployment Progress

To monitor server deployment status:

```bash
# Check specific server status
ntcli server info <server-id>

# List all servers with status
ntcli server list

# Watch for status changes (if available)
watch -n 5 'ntcli server info <server-id>'
```

## Troubleshooting

### Common Issues

#### Service Not Starting
```bash
# Check pod status
kubectl get pods -l app=your-service

# Check pod logs
kubectl logs -l app=your-service

# Describe pod for events
kubectl describe pod -l app=your-service
```

#### Image Pull Issues
```bash
# Check if image exists
docker pull your-image:tag

# Check imagePullSecrets
kubectl get secrets
kubectl describe secret your-pull-secret
```

#### Service Discovery Issues
```bash
# Check service endpoints
kubectl get endpoints your-service

# Test service connectivity
kubectl run debug --rm -it --image=curlimages/curl -- curl your-service:8000/health
```

### Debugging Tips

1. **Enable Debug Logging:**
   ```yaml
   env:
     - name: LOG_LEVEL
       value: "debug"
   ```

2. **Check Resource Usage:**
   ```bash
   kubectl top pods -l app=your-service
   ```

3. **Monitor Service Metrics:**
   ```bash
   kubectl port-forward service/your-service 8080:8000
   curl http://localhost:8080/metrics
   ```

## Creating Custom Examples

### Template for New Examples
```yaml
apiVersion: mcp.nimbletools.dev/v1
kind: MCPService
metadata:
  name: my-custom-service
  namespace: default
  labels:
    app: my-service
    category: custom
    example: "true"
spec:
  description: "Description of your custom MCP service"
  
  container:
    image: your-org/your-service:latest
    port: 8000
    env:
      - name: LOG_LEVEL
        value: "info"
      # Add your environment variables
  
  deployment:
    type: "http"  # or "stdio" with executable/args
  
  tools:
    - name: "your_tool"
      description: "Description of what your tool does"
    # Add more tools
  
  replicas: 1
```

### Best Practices for Examples
1. **Documentation:** Include clear descriptions and use cases
2. **Labels:** Use consistent labeling for easy filtering
3. **Environment Variables:** Make services configurable
4. **Security:** Follow security best practices
5. **Resource Limits:** Set appropriate resource constraints
6. **Error Handling:** Include proper error handling in services
7. **Monitoring:** Add health checks and metrics endpoints

## Contributing Examples

To contribute new examples:

1. Create a new YAML file in the `examples/` directory
2. Follow the naming convention: `service-name-mcp.yaml`
3. Include comprehensive comments explaining the configuration
4. Add the example to this README with description and use cases
5. Test the example on a real cluster
6. Submit a pull request with your example

For more information, see the main [README.md](../README.md) and [CONTRIBUTING.md](../CONTRIBUTING.md).