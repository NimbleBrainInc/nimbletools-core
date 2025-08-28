# NimbleTools Core API

The NimbleTools Core API is a FastAPI-based REST API that provides management capabilities for MCP services and workspaces. It features a pluggable authentication system that supports both open-source (no-auth) and enterprise (JWT) authentication modes.

## Features

- **Workspace Management**: Create, list, get, and delete isolated workspaces
- **Server Management**: Deploy, scale, update, and monitor MCP services within workspaces
- **Registry Management**: Enable external MCP registries and deploy multiple services at once
- **Multi-tenant Isolation**: Owner-based resource isolation and access control
- **Pluggable Authentication**: Switch between no-auth (OSS) and JWT-based (enterprise) authentication
- **Kubernetes Integration**: Direct integration with Kubernetes APIs for resource management
- **OpenAPI Documentation**: Auto-generated API documentation available at `/docs`
- **Health Checks**: Built-in health endpoints for monitoring

## API Endpoints

### Core Endpoints

- `GET /`: API information and status
- `GET /health`: Health check endpoint
- `GET /docs`: Interactive API documentation (Swagger UI)
- `GET /redoc`: Alternative API documentation (ReDoc)

### Workspace Management

- `POST /v1/workspaces`: Create a new workspace
- `GET /v1/workspaces`: List all workspaces (filtered by user in enterprise mode)
- `GET /v1/workspaces/{workspace_id}`: Get workspace details
- `DELETE /v1/workspaces/{workspace_id}`: Delete workspace and all resources

### Server Management

- `GET /v1/workspaces/{workspace_id}/servers`: List servers in workspace
- `POST /v1/workspaces/{workspace_id}/servers`: Deploy new server to workspace
- `GET /v1/workspaces/{workspace_id}/servers/{server_name}`: Get server details
- `PATCH /v1/workspaces/{workspace_id}/servers/{server_name}`: Update server (scaling, etc.)
- `DELETE /v1/workspaces/{workspace_id}/servers/{server_name}`: Delete server
- `GET /v1/workspaces/{workspace_id}/servers/{server_name}/logs`: Get server logs
- `POST /v1/workspaces/{workspace_id}/servers/{server_name}/restart`: Restart server

### Registry Management

- `POST /v1/registry`: Enable registry from URL and deploy services
- `GET /v1/registry`: List all registries owned by authenticated user
- `GET /v1/registry/servers`: List all servers across user's registries
- `GET /v1/registry/servers/{server_id}`: Get detailed server information
- `GET /v1/registry/info?registry_url={url}`: Get registry information without deploying

## Authentication System

The API uses a pluggable authentication system that can be configured via environment variables.

### No-Auth Provider (OSS Default)

For open-source use, no authentication is required:

```bash
export AUTH_PROVIDER=none
```

All requests are treated as coming from an anonymous admin user with full access to all resources.

### Enterprise JWT Provider

For enterprise deployments with user authentication:

```bash
export AUTH_PROVIDER=enterprise
export JWT_SECRET=your-secret-key
export JWT_ISSUER=your-issuer
```

Requires `Authorization: Bearer <token>` header with valid JWT tokens.

JWT token should contain:

- `sub`: User ID
- `role`: User role (`admin` or `user`)
- `iss`: Token issuer (must match `JWT_ISSUER`)

## Usage Examples

### Create a Workspace

```bash
curl -X POST http://localhost:8080/v1/workspaces \
  -H "Content-Type: application/json" \
  -d '{"name": "my-workspace"}'
```

Response:

```json
{
  "workspace_id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "my-workspace",
  "namespace": "ws-123e4567-e89b-12d3-a456-426614174000",
  "owner": "anonymous",
  "status": "created"
}
```

### Deploy an MCP Service

```bash
curl -X POST http://localhost:8080/v1/workspaces/{workspace_id}/servers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "calculator",
    "spec": {
      "description": "Simple calculator MCP service",
      "container": {
        "image": "calculator-mcp:latest",
        "port": 8000
      },
      "deployment": {
        "type": "http"
      },
      "tools": [
        {"name": "add", "description": "Add two numbers"},
        {"name": "multiply", "description": "Multiply two numbers"}
      ],
      "replicas": 1
    }
  }'
```

### Scale a Service

```bash
curl -X PATCH http://localhost:8080/v1/workspaces/{workspace_id}/servers/calculator \
  -H "Content-Type: application/json" \
  -d '{"replicas": 3}'
```

### Get Server Logs

```bash
curl http://localhost:8080/v1/workspaces/{workspace_id}/servers/calculator/logs?lines=50
```

### Enable a Registry

```bash
curl -X POST http://localhost:8080/v1/registry \
  -H "Content-Type: application/json" \
  -d '{
    "registry_url": "https://raw.githubusercontent.com/NimbleBrainInc/nimbletools-mcp-registry/main/registry.yaml"
  }'
```

Response:

```json
{
  "registry_name": "community-servers",
  "registry_version": "2.0.0",
  "namespace": "registry-community-servers",
  "services_created": 6,
  "services": ["echo", "finnhub", "nationalparks-mcp", "ref-tools-mcp", "reverse-text", "tavily-mcp"],
  "timestamp": "2025-08-25T22:30:00Z"
}
```

### List Registry Servers

```bash
curl http://localhost:8080/v1/registry/servers
```

Response:

```json
{
  "servers": [
    {
      "id": "echo",
      "name": "Echo MCP Server",
      "registry": "community-servers",
      "namespace": "registry-community-servers",
      "status": "running",
      "tools": [...],
      "replicas": {"desired": 1, "current": 1, "ready": 1}
    }
  ],
  "total": 6,
  "registries": [
    {"name": "community-servers", "server_count": 6}
  ],
  "owner": "user123"
}
```

## Development

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export AUTH_PROVIDER=none
export PORT=8080

# Run the API server
python main.py
```

The API will be available at `http://localhost:8080` with documentation at `http://localhost:8080/docs`.

### Docker Development

```bash
# Build the image
docker build -t nimbletools/control-plane .

# Run with no auth
docker run -p 8080:8080 \
  -e AUTH_PROVIDER=none \
  nimbletools/control-plane

# Run with enterprise auth
docker run -p 8080:8080 \
  -e AUTH_PROVIDER=enterprise \
  -e JWT_SECRET=your-secret \
  -e JWT_ISSUER=your-issuer \
  nimbletools/control-plane
```

## Architecture Notes

### Pluggable Authentication

The authentication system is designed to be easily extensible:

1. **AuthProvider Interface**: Abstract base class defining authentication methods
2. **NoAuthProvider**: OSS implementation allowing unrestricted access
3. **EnterpriseAuthProvider**: JWT-based implementation for user authentication
4. **Factory Pattern**: `create_auth_provider()` creates the appropriate provider based on environment

### Kubernetes Integration

The API directly uses the Kubernetes Python client to:

- Create and manage namespaces for workspaces and registries
- Create, read, update, and delete MCPService custom resources
- Monitor deployment status and retrieve logs
- Handle resource cleanup on deletion
- Owner-based isolation using Kubernetes labels and selectors

### Error Handling

- **404 Not Found**: Resource doesn't exist
- **401 Unauthorized**: Authentication required (enterprise mode)
- **403 Forbidden**: User doesn't have access to workspace
- **409 Conflict**: Resource already exists
- **500 Internal Server Error**: Server-side errors with details

### Security Considerations

- **CORS**: Configured for development (allow all origins) - should be restricted in production
- **Input Validation**: FastAPI provides automatic input validation based on type hints
- **Resource Isolation**: Resources are isolated by Kubernetes namespaces and owner labels
- **Multi-tenancy**: Users can only access their own workspaces and registries
- **Least Privilege**: API only has necessary Kubernetes RBAC permissions

This API provides a clean REST interface for managing MCP services while maintaining compatibility with both open-source and enterprise deployment scenarios.
