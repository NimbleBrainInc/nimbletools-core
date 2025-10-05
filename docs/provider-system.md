# Provider System Documentation

## Overview

The NimbleTools Control Plane uses a **duck-typed provider pattern** for authentication and authorization. This allows enterprise deployments to add custom authentication without modifying the control plane code.

## How It Works

### 1. Duck Typing - No Inheritance Required

Providers don't inherit from a base class. They simply implement the expected methods:

```python
class MyProvider:
    async def validate_token(self, token: str) -> dict | None
    async def check_workspace_access(self, user: dict, workspace_id: str) -> bool
    async def check_permission(self, user: dict, resource: str, action: str) -> bool
    async def initialize(self) -> None
    async def shutdown(self) -> None
```

### 2. Configuration via YAML

Providers are configured using a YAML file specified by `PROVIDER_CONFIG` environment variable:

```yaml
# provider.yaml
class: "my_company.auth.MyProvider"
kwargs:
  database_url: "postgresql://..."
  auth_service: "https://auth.company.com"
```

### 3. Dynamic Loading

The control plane dynamically imports and instantiates the provider:

```python
# This happens automatically on first use
module = importlib.import_module("my_company.auth")
provider = module.MyProvider(**kwargs)
```

## Provider Methods

### `validate_token(token: str) -> dict | None`
Validates an authentication token and returns user information.

**Required fields:**
- `user_id`: User identifier (must be convertible to UUID)
- `organization_id`: Organization identifier (must be convertible to UUID)

**Returns:**
- Dict with user information if valid
- None if token is invalid

### `check_workspace_access(user: dict, workspace_id: str) -> bool`
Checks if a user can access a specific workspace

### `check_permission(user: dict, resource: str, action: str) -> bool`
Checks if a user can perform an action on a resource

### `initialize() -> None`
Called on startup to initialize resources (database connections, etc.)

### `shutdown() -> None`
Called on shutdown to cleanup resources

## Community Provider

The default provider (`CommunityProvider`) allows open access:
- All tokens return a fixed community user with `user_id` and `organization_id`
- All workspace access is allowed
- All permissions are granted

## Enterprise Provider Example

Enterprise providers can implement custom authentication logic including:
- JWT validation with JWKS
- Database-backed workspace membership
- RBAC permission system
- Custom authorization rules

## Docker Composition

Enterprise deployments add their provider via Docker:

```dockerfile
FROM nimbletools/control-plane:latest

# Add your provider package
COPY my_provider/ /app/my_provider/

# Install dependencies
RUN uv pip install my-auth-deps

# Configure provider
COPY provider.yaml /app/config/
ENV PROVIDER_CONFIG=/app/config/provider.yaml
```

## Extension Points

The provider system provides extension points throughout the control plane:

1. **API Authentication** - Who can access the control plane API?
2. **Workspace Access** - Who can access which workspaces?
3. **Resource Permissions** - Who can create/delete/modify resources?

## Benefits

- **No Code Coupling** - Enterprise providers don't import from control-plane
- **Simple Contract** - Just implement the methods, no base classes
- **Flexible Implementation** - Use any auth system (JWT, OAuth, SAML, etc.)
- **Docker Composable** - Add providers as layers in Docker
- **Environment Agnostic** - Configure via environment variables

## Testing Your Provider

```python
# Test your provider standalone
provider = MyProvider(config="...")
await provider.initialize()

# Test token validation
user = await provider.validate_token("test-token")
assert user["user_id"] == "expected-id"

# Test workspace access
allowed = await provider.check_workspace_access(user, "workspace-123")
assert allowed

await provider.shutdown()
```