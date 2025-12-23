# CLAUDE.md

## Overview

This repository follows modern Python + Docker best practices.
The goal is to ensure code is:

- **Reproducible** (lockfile-driven builds)
- **Portable** (DockerHub images)
- **Maintainable** (linting, typing, tests)
- **Secure** (minimal, non-root containers)

## Documentation Standards

- **Centralized documentation**: All platform documentation should be stored in `/docs` at the repository root, not in component-specific directories
- **Single source of truth**: Avoid duplicating documentation across components
- **Cross-references**: Use relative paths to link between documents (e.g., `../docs/AUTHENTICATION.md`)

---

## Project Layout

```
api/
├─ src/yourpkg/          # importable package
│  ├─ __init__.py
│  ├─ _version.py
│  └─ py.typed
├─ tests/                # unit tests
├─ pyproject.toml        # tooling + deps
├─ uv.lock               # committed lockfile
├─ Dockerfile            # multi-stage build
├─ .dockerignore
└─ README.md
```

**Why `src/`?** Prevents accidental local imports and mirrors how the package is used in production.

---

## Dependency Management

- Use [`uv`](https://docs.astral.sh/uv/) for environments and locking.
- Commit `uv.lock`.
- Install with:

  ```bash
  uv sync --frozen
  ```

This guarantees reproducible builds in Docker and CI.

---

## Tooling

- **Linting & Formatting**: [`ruff`](https://docs.astral.sh/ruff/)
- **Typing**: [`mypy`](http://mypy-lang.org/)
- **Testing**: [`pytest`](https://docs.pytest.org/)
- **Coverage**: [`coverage`](https://coverage.readthedocs.io/)

All are configured in `pyproject.toml`.

---

## Docker Best Practices

- **Multi-stage builds**: builder + runtime
- **Lockfile installs**: `uv sync --frozen`
- **Non-root user**: drop privileges in final image
- **Slim base images**: reduce surface area
- **.dockerignore**: keep context lean

Minimal runtime image includes only:

- Installed virtualenv
- Application source

---

## CI/CD

- Run lint, type-check, and tests in CI.
- Build and push Docker images with:

  - Immutable `:sha-xxxxxxx` tags
  - Rolling `:edge` for main
  - Semantic `:vX.Y.Z` + `:latest` on releases

---

## Versioning

- Version is injected at build (from git tag or env).
- `src/yourpkg/_version.py` stores the active version.

---

## Security

- Use slim Python images.
- Non-root `app` user in runtime container.
- (Optional) run image scans (e.g., Trivy) in CI.

---

## Error Handling Standards

### General Principles

- **Never silently swallow exceptions** - All exceptions must be logged with appropriate context
- **Use structured logging** - Include operation, resource type, and resource identifier in log messages
- **Fail fast with clear messages** - Provide actionable error messages to users and operators
- **Distinguish between expected and unexpected errors** - Handle 404s differently from 500s

### Implementation Guidelines

#### 1. Use Error Handling Decorators

For Kubernetes operations, use the decorators from `nimbletools_control_plane.exceptions`:

```python
from nimbletools_control_plane.exceptions import (
    handle_kubernetes_errors,
    handle_optional_kubernetes_resource,
)

@handle_kubernetes_errors("reading", "deployment")
async def get_deployment(name: str, namespace: str):
    return k8s_apps.read_namespaced_deployment(name=name, namespace=namespace)

@handle_optional_kubernetes_resource("reading", "service", default_value=None)
async def get_service_if_exists(name: str, namespace: str):
    return k8s_core.read_namespaced_service(name=name, namespace=namespace)
```

#### 2. Exception Handling Patterns

**Required Pattern for API Operations:**
```python
try:
    result = await kubernetes_operation()
    log_operation_success("reading", "deployment", deployment_name)
    return result
except KubernetesOperationError as e:
    raise convert_to_http_exception(e)
except Exception as e:
    logger.error(f"Unexpected error in operation: {e}", exc_info=True)
    raise HTTPException(status_code=500, detail="Internal server error")
```

**Forbidden Patterns:**
```python
# NEVER DO THIS - Silent exception swallowing
try:
    k8s_operation()
except ApiException:
    pass

# NEVER DO THIS - Generic error handling without logging
except Exception:
    return None
```

#### 3. Logging Standards

- **INFO level**: Normal operations, successful completions
- **WARNING level**: Client errors (400-403), recoverable issues  
- **ERROR level**: Server errors (500+), unexpected exceptions
- **DEBUG level**: Optional resource not found (404 for optional resources)

#### 4. Error Message Structure

Error messages should follow this format:
- **Log message**: `"Kubernetes API error while {operation} {resource_type} '{resource_id}': {specific_error}"`
- **User message**: `"Failed to {operation} {resource_type} '{resource_id}': {user_friendly_reason}"`

#### 5. HTTP Status Code Mapping

- **404**: Resource not found (Kubernetes 404)
- **400/401/403**: Client errors (pass through from Kubernetes)
- **500**: Server errors, unexpected exceptions, Kubernetes server errors

### Testing Error Handling

Always include tests for error conditions:
- Network failures
- Kubernetes API errors (404, 403, 500)
- Invalid input validation
- Resource conflicts

---

## Architecture Decisions

### Multi-Tenant Workspace Isolation

- **Organization-based filtering**: All workspace operations are scoped to the user's organization
- **Required tenant context**: Every workspace must belong to an organization (no orphaned workspaces)
- **Authentication requirements**: `validate_token` must return both `user_id` and `organization_id`
- **Kubernetes label strategy**:
  - Query label: `mcp.nimbletools.dev/organization_id` for filtering
  - Owner label: `mcp.nimbletools.dev/user_id` for workspace ownership
  - No fallback to legacy fields - fail explicitly if data missing

### Data Model Standards

- **UUID-only IDs**: All entity IDs (`workspace_id`, `user_id`, `organization_id`) must be UUIDs
- **No string IDs**: Never accept or return string identifiers for core entities
- **Required fields philosophy**: Make fields required at creation rather than optional with defaults
- **Field naming conventions**:
  - `user_id`: The user who owns/created a resource
  - `organization_id`: The organization that owns a resource
  - `created_at`: Timestamp of creation (datetime type)
  - Never use: `owner`, `created_by`, `created` (string)

### API Design Principles

- **Explicit over implicit**: Require all necessary data upfront (no magic defaults)
- **Fail fast**: Return 401/403 immediately if auth context incomplete
- **Consistent responses**: All list endpoints filter by organization automatically
- **No cross-tenant data**: Never allow viewing resources from other organizations

### Workspace Identity Management

- **Workspace Naming Convention**:
  - Format: `{base_name}-{uuid}` (e.g., `my-workspace-550e8400-e29b-41d4-a716-446655440000`)
  - Namespace format: `ws-{workspace_name}`
  - Always use `workspace_utils.generate_workspace_identifiers()` for consistency
  - Workspace names are immutable after creation
- **Dual Identification**: Workspaces have both a UUID (`workspace_id`) and human-readable name (`workspace_name`)
- **No String Parsing**: Never extract metadata from namespace names or other string manipulation

### Kubernetes Labels as Source of Truth

- **Required Labels**: Every workspace namespace MUST have:
  - `mcp.nimbletools.dev/workspace_id` - The workspace UUID
  - `mcp.nimbletools.dev/workspace_name` - The full workspace name including UUID
  - `mcp.nimbletools.dev/user_id` - The owner's UUID
  - `mcp.nimbletools.dev/organization_id` - The organization's UUID
- **No Fallbacks**: Missing required labels = invalid configuration
  - Log and skip invalid workspaces during listing
  - Return HTTP 500 for invalid workspaces during detail retrieval
  - Never use zero UUIDs, "unknown" values, or None as fallbacks
- **Label Authority**: Labels are the single source of truth for workspace metadata

---

## Summary

1. Keep code in `src/` with type hints.
2. Manage dependencies with `uv.lock`.
3. Use Ruff, mypy, pytest, coverage.
4. Build multi-stage, minimal Docker images.
5. Tag and publish images consistently.
6. Run as non-root in containers.
7. **Follow error handling standards** - Never silently swallow exceptions.
