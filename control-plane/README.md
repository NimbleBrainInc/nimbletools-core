# NimbleTools Control Plane API

The NimbleTools Control Plane API is a FastAPI-based REST API that provides management capabilities for MCP services and workspaces. It features a pluggable authentication system with multi-tenant organization support.

## Features

- **Workspace Management**: Create, list, get, and delete isolated workspaces with organization-based multi-tenancy
- **Server Management**: Deploy, scale, and monitor MCP services within workspaces
- **Secret Management**: Manage workspace-specific secrets for MCP services
- **Multi-tenant Isolation**: Organization-based resource isolation and access control
- **Pluggable Authentication**: Duck-typed provider system for flexible authentication
- **Authentication**: Provides /auth endpoint for nginx-ingress validation
- **Kubernetes Integration**: Direct integration with Kubernetes APIs for resource management
- **API Versioning**: All endpoints support versioned request/response models
- **OpenAPI Documentation**: Auto-generated API documentation available at `/docs`
- **Health Checks**: Built-in health endpoints for monitoring

## Authentication

The control plane uses a pluggable provider system for authentication and authorization. All workspaces are isolated by organization with automatic filtering and access control.

**See [AUTHENTICATION.md](../docs/AUTHENTICATION.md) for complete provider configuration details.**

Quick start with community provider (no authentication):

```yaml
# community-provider.yaml
class: "nimbletools_control_plane.providers.community.CommunityProvider"
```

```bash
export PROVIDER_CONFIG=/path/to/community-provider.yaml
```

## API Endpoints

### Core Endpoints

- `GET /`: API information and status
- `GET /health`: Health check endpoint
- `GET /docs`: Interactive API documentation (Swagger UI)
- `GET /redoc`: Alternative API documentation (ReDoc)
- `GET /openapi.json`: OpenAPI specification in JSON format

### Workspace Management

- `POST /v1/workspaces`: Create a new workspace
- `GET /v1/workspaces`: List all workspaces (filtered by organization)
- `GET /v1/workspaces/{workspace_id}`: Get workspace details
- `DELETE /v1/workspaces/{workspace_id}`: Delete workspace and all resources

### Workspace Secrets

- `GET /v1/workspaces/{workspace_id}/secrets`: List workspace secrets
- `PUT /v1/workspaces/{workspace_id}/secrets/{secret_key}`: Set workspace secret
- `DELETE /v1/workspaces/{workspace_id}/secrets/{secret_key}`: Delete workspace secret

### Server Management

- `GET /v1/workspaces/{workspace_id}/servers`: List servers in workspace
- `POST /v1/workspaces/{workspace_id}/servers`: Deploy new server to workspace
- `GET /v1/workspaces/{workspace_id}/servers/{server_id}`: Get server details
- `POST /v1/workspaces/{workspace_id}/servers/{server_id}/scale`: Scale server replicas
- `DELETE /v1/workspaces/{workspace_id}/servers/{server_id}`: Delete server

## API Versioning

All request and response models include a `version` field for API compatibility:

```json
{
  "version": "v1",
  "name": "my-workspace"
}
```

## Usage Examples

### Create a Workspace

```bash
curl -X POST http://localhost:8080/v1/workspaces \
  -H "Content-Type: application/json" \
  -d '{
    "version": "v1",
    "name": "my-workspace"
  }'
```

Response:

```json
{
  "version": "v1",
  "workspace_id": "550e8400-e29b-41d4-a716-446655440000",
  "workspace_name": "my-workspace-550e8400-e29b-41d4-a716-446655440000",
  "namespace": "ws-my-workspace-550e8400-e29b-41d4-a716-446655440000",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "organization_id": "987fcdeb-51a2-43d1-9876-543210fedcba",
  "status": "active",
  "created_at": "2025-01-15T10:30:00Z"
}
```

### Deploy an MCP Service

```bash
curl -X POST http://localhost:8080/v1/workspaces/{workspace_id}/servers \
  -H "Content-Type: application/json" \
  -d '{
    "version": "v1",
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
curl -X POST http://localhost:8080/v1/workspaces/{workspace_id}/servers/{server_id}/scale \
  -H "Content-Type: application/json" \
  -d '{
    "version": "v1",
    "replicas": 3
  }'
```

### Manage Workspace Secrets

```bash
# List secrets
curl http://localhost:8080/v1/workspaces/{workspace_id}/secrets

# Set a secret
curl -X PUT http://localhost:8080/v1/workspaces/{workspace_id}/secrets/API_KEY \
  -H "Content-Type: application/json" \
  -d '{
    "version": "v1",
    "value": "secret-value-123"
  }'

# Delete a secret
curl -X DELETE http://localhost:8080/v1/workspaces/{workspace_id}/secrets/API_KEY
```

## Development

### Prerequisites

- Python 3.13+
- uv (for package management)
- Kubernetes cluster or Docker Desktop with Kubernetes enabled

### Local Development

```bash
# Clone the repository
git clone https://github.com/nimbletools/nimbletools-core
cd nimbletools-core/control-plane

# Install dependencies using uv
uv sync

# Create provider configuration
cat > community-provider.yaml <<EOF
class: "nimbletools_control_plane.providers.community.CommunityProvider"
EOF

# Set environment variables
export PROVIDER_CONFIG=./community-provider.yaml
export PORT=8080

# Run the API server
uv run python -m nimbletools_control_plane.main
```

The API will be available at `http://localhost:8080` with documentation at `http://localhost:8080/docs`.

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov

# Run linting
uv run ruff check .

# Run type checking
uv run mypy src/
```

### Docker Development

```bash
# Build the image
docker build -t nimbletools/control-plane .

# Run with community provider (no auth)
docker run -p 8080:8080 \
  -v ./community-provider.yaml:/app/provider-config.yaml \
  -e PROVIDER_CONFIG=/app/provider-config.yaml \
  nimbletools/control-plane
```

## Architecture Notes

### Kubernetes Integration

The API directly uses the Kubernetes Python client to:

- Create and manage namespaces for workspaces (format: `ws-{name}-{uuid}`)
- Create, read, update, and delete MCPService custom resources
- Monitor deployment status
- Handle resource cleanup on deletion
- Organization-based isolation using Kubernetes labels

Required Kubernetes labels on workspace namespaces:

- `mcp.nimbletools.dev/workspace_id`: Workspace UUID
- `mcp.nimbletools.dev/workspace_name`: Full workspace name
- `mcp.nimbletools.dev/user_id`: Owner's UUID
- `mcp.nimbletools.dev/organization_id`: Organization UUID

### Error Handling

- **401 Unauthorized**: Missing or invalid authentication
- **403 Forbidden**: User doesn't have access to resource
- **404 Not Found**: Resource doesn't exist
- **409 Conflict**: Resource already exists
- **422 Unprocessable Entity**: Invalid request data
- **500 Internal Server Error**: Server-side errors with details

### Security Considerations

- **CORS**: Configured for development (allow all origins) - should be restricted in production
- **Input Validation**: FastAPI provides automatic input validation via Pydantic models
- **Resource Isolation**: Resources isolated by Kubernetes namespaces and organization labels
- **Multi-tenancy**: Automatic organization-based filtering for all operations
- **UUID Requirements**: All entity IDs must be valid UUIDs (not strings)
- **Least Privilege**: API only has necessary Kubernetes RBAC permissions
- **No Silent Defaults**: Provider configuration is required - fails explicitly if missing

## Documentation

- **[Provider System](../docs/AUTHENTICATION.md)**: Authentication and authorization configuration
- **[Server Logs](../docs/server-logs.md)**: Accessing and streaming MCP server logs

## Related Services

- **mcp-runtime**: Handles MCP protocol connections and routing to workspace servers
- **nginx-ingress**: Routes requests based on workspace and server IDs
