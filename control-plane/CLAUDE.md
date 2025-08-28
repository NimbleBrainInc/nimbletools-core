# CLAUDE.md

## Overview

This repository follows modern Python + Docker best practices.
The goal is to ensure code is:

- **Reproducible** (lockfile-driven builds)
- **Portable** (DockerHub images)
- **Maintainable** (linting, typing, tests)
- **Secure** (minimal, non-root containers)

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

## Summary

1. Keep code in `src/` with type hints.
2. Manage dependencies with `uv.lock`.
3. Use Ruff, mypy, pytest, coverage.
4. Build multi-stage, minimal Docker images.
5. Tag and publish images consistently.
6. Run as non-root in containers.
7. **Follow error handling standards** - Never silently swallow exceptions.
