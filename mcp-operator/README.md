# NimbleTools Core Operator

The NimbleTools Core Operator is a Kubernetes controller that manages the lifecycle of MCPService custom resources. It provides a simplified, open-source alternative to enterprise MCP platforms.

## Features

- **MCPService Management**: Creates and manages Kubernetes deployments, services, and configs for MCP services
- **HTTP and stdio Support**: Handles both direct HTTP MCP services and stdio-based services via universal adapter
- **Reactive Architecture**: Responds to MCPService resources created by the control plane
- **Auto-scaling**: Manual scaling support via replica count updates
- **Security**: Runs with least-privilege security contexts

## Architecture

The operator watches for MCPService custom resources created by the control plane and creates the corresponding Kubernetes resources:

```
Control Plane → MCPService CR → Operator → Deployment + Service + ConfigMap
```

### Deployment Types

1. **HTTP Services** (`deployment.type: http`):

   - Direct container deployment
   - Service must provide `/health` and `/mcp` endpoints

2. **stdio Services** (`deployment.type: stdio`):
   - Uses Universal Adapter as a bridge
   - Adapter spawns the stdio process and provides HTTP interface

## Configuration

The operator is configured via environment variables:

- `OPERATOR_NAMESPACE`: Namespace where operator runs (default: `nimbletools-core-system`)
- `UNIVERSAL_ADAPTER_IMAGE`: Universal adapter container image

## Example MCPService

### HTTP Service

```yaml
apiVersion: mcp.nimbletools.dev/v1
kind: MCPService
metadata:
  name: calculator
  namespace: my-workspace
spec:
  description: "Simple calculator MCP service"
  container:
    image: calculator-mcp:latest
    port: 8000
  deployment:
    type: http
  tools:
    - name: add
      description: "Add two numbers"
    - name: multiply
      description: "Multiply two numbers"
  replicas: 1
```

### stdio Service

```yaml
apiVersion: mcp.nimbletools.dev/v1
kind: MCPService
metadata:
  name: echo-mcp
  namespace: my-workspace
spec:
  description: "Echo MCP service using stdio"
  container:
    image: ghcr.io/nimblebrain/nimbletools-core-universal-adapter:latest
    port: 8000
  deployment:
    type: stdio
    stdio:
      executable: npx
      args: ["@modelcontextprotocol/server-echo"]
      workingDir: /tmp
  tools:
    - name: echo
      description: "Echo back input"
  replicas: 1
```

## Security

The operator follows security best practices:

- **Non-root containers**: All containers run as non-root user (UID 1000)
- **Read-only filesystem**: Containers use read-only root filesystems
- **Dropped capabilities**: All Linux capabilities are dropped
- **Security contexts**: Restrictive pod and container security contexts
- **Namespace isolation**: Only operates in allowed namespaces


## Development

Build the operator:

```bash
docker build -t nimbletools-core-operator .
```

Test locally:

```bash
# Apply CRDs
kubectl apply -f ../crd/mcpservice.yaml

# Install operator
kubectl apply -f operator-deployment.yaml

# Create test service
kubectl apply -f test-mcpservice.yaml
```

## Differences from Enterprise Version

This OSS version has simplified functionality compared to enterprise versions:

**Removed Features**:

- Complex workspace validation and RBAC
- KEDA auto-scaling (uses manual scaling)
- Multi-registry namespaces
- Enterprise credential injection
- Advanced ingress management

**Simplified Features**:

- Basic namespace validation (no system namespaces)
- Reactive architecture (no registry polling)
- Environment-based configuration
- Manual scaling only
- Basic security contexts

## API Reference

### MCPService Spec

| Field              | Type   | Description                     |
| ------------------ | ------ | ------------------------------- |
| `description`      | string | Human-readable description      |
| `container.image`  | string | Container image to run          |
| `container.port`   | int    | Container port (default: 8000)  |
| `deployment.type`  | string | "http" or "stdio"               |
| `deployment.stdio` | object | stdio configuration             |
| `tools`            | array  | List of available tools         |
| `resources`        | array  | List of available resources     |
| `prompts`          | array  | List of available prompts       |
| `environment`      | object | Environment variables           |
| `replicas`         | int    | Number of replicas (default: 1) |

### Status Fields

| Field                            | Type   | Description                              |
| -------------------------------- | ------ | ---------------------------------------- |
| `phase`                          | string | Current phase (Pending, Running, Failed) |
| `conditions`                     | array  | Detailed status conditions               |
| `deploymentStatus.ready`         | bool   | Whether deployment is ready              |
| `deploymentStatus.replicas`      | int    | Total replica count                      |
| `deploymentStatus.readyReplicas` | int    | Ready replica count                      |

This operator provides a solid foundation for running MCP services on Kubernetes with a focus on simplicity, security, and reliability.
