# Claude.md

## Documentation Standards

**IMPORTANT**: All platform documentation must be stored in the `/docs` directory at the repository root.

- **Centralized location**: `/docs` is the single source of truth for all platform documentation
- **No component-specific docs**: Do not create documentation in component directories (e.g., `control-plane/docs/`, `operator/docs/`)
- **Cross-references**: Use relative paths from component READMEs to root docs (e.g., `../docs/provider-system.md`)
- **Consistency**: Keep documentation structure flat and organized by topic, not by component

When creating or updating documentation:
1. Create files in `/docs`
2. Update references in component READMEs to point to `/docs`
3. Avoid duplicating content across multiple locations

## Platform Design Principles

### Keep All Components Generic and Extensible

**CRITICAL**: All platform components (operator, control-plane, universal-adapter) must remain completely generic and server-agnostic. They process server definitions from the registry but never contain server-specific logic.

#### Core Principle: Configuration Over Code

The platform is driven by **declarative server definitions** from the registry. Server-specific behavior is configured through schemas, not hardcoded in platform components.

#### What This Means

- **No hardcoded server behavior**: Platform components never contain logic specific to individual MCP servers (e.g., postgres-mcp, tavily-mcp, finnhub, etc.)
- **Configuration via server definitions**: All server-specific behavior (startup commands, arguments, ports, environment variables, resource limits) comes from the server definition in the registry
- **Extensibility through schemas**: New server types and behaviors are supported by extending the server definition schema, not by modifying platform code
- **Registry-driven deployment**: Platform components are pure interpreters of server definitions - they read definitions and create/manage appropriate resources
- **Third-party compatibility**: External developers can add servers to the registry without any platform code changes

#### Applies To All Components

**Operator**: Deploys and manages MCP servers
- Reads server definitions and creates Kubernetes resources generically
- Never contains server-specific deployment logic

**Control Plane**: API for workspace and server management
- Routes requests and validates schemas generically
- Never contains server-specific API logic or special cases

**Universal Adapter**: Wraps stdio servers for HTTP transport
- Executes any server based on package definition
- Never contains server-specific wrapper logic

#### Correct Approach

When a server needs special startup arguments or configuration:

✅ **Add to server definition in registry**:
```json
{
  "name": "ai.nimbletools/postgres-mcp",
  "packages": [{
    "registryType": "oci",
    "identifier": "crystaldba/postgres-mcp",
    "transport": {"type": "streamable-http"},
    "runtimeArguments": [
      {"type": "named", "name": "--transport", "value": "sse"},
      {"type": "named", "name": "--sse-host", "value": "0.0.0.0"},
      {"type": "named", "name": "--sse-port", "value": "8000"}
    ],
    "environmentVariables": [
      {"name": "DATABASE_URI", "isSecret": true, "isRequired": true}
    ]
  }],
  "_meta": {
    "ai.nimbletools.mcp/v1": {
      "resources": {
        "limits": {"memory": "512Mi", "cpu": "200m"}
      }
    }
  }
}
```

✅ **Platform reads and applies generically**:
```python
# Operator - works for ANY server
args = self._extract_runtime_args(spec.get("packages", []))
env_vars = self._create_env_vars_from_packages(spec.get("packages", []))
resources = self._build_resources_config(runtime)

# Control plane - works for ANY server
mcp_server = MCPServer(**server_definition)
mcpservice_spec = _create_mcpservice_spec_from_mcp_server(mcp_server, ...)
```

#### Incorrect Approach

❌ **Never hardcode server-specific logic**:
```python
# WRONG - Don't do this in operator, control-plane, or any platform component!
if server_name == "postgres-mcp":
    args = ["--transport", "sse"]
    resources = {"memory": "512Mi"}
elif server_name == "tavily-mcp":
    args = ["--some-other-flag"]
    resources = {"memory": "256Mi"}
elif server_name == "finnhub":
    # Special finnhub logic...
```

❌ **Never add server-specific configuration to platform code**:
```python
# WRONG - Don't do this!
SERVER_CONFIGS = {
    "postgres-mcp": {"transport": "sse", "port": 8000},
    "tavily-mcp": {"transport": "stdio"},
}

# WRONG - Don't do this!
if "postgres" in server_name.lower():
    # Special postgres handling...
```

❌ **Never create server-specific API endpoints**:
```python
# WRONG - Don't do this!
@router.post("/servers/postgres-mcp/special-action")
async def postgres_special_action():
    # Server-specific endpoint
```

#### Why This Matters

1. **Scalability**: Platform supports unlimited server types without code changes
2. **Maintainability**: Server-specific logic stays with server definitions in the registry where server maintainers control it
3. **Separation of concerns**:
   - Registry teams manage server definitions and metadata
   - Platform team manages deployment and orchestration logic
   - Server developers focus on their MCP implementations
4. **Third-party ecosystem**: External developers can add servers by contributing to the registry, not forking platform code
5. **Testing**: Generic code paths mean fewer test cases, edge cases, and regressions
6. **Velocity**: Adding a new server requires no platform deployment, only registry update
7. **Multi-tenancy**: All servers treated equally regardless of source

#### Adding New Features

When adding platform features, always ask:

1. **"Can this be configured via the server definition schema?"**
   - If yes, extend the schema and update generic processing logic
   - If no, reconsider if the feature is truly platform-level

2. **"Will this work for all servers, not just one specific server?"**
   - If no, it doesn't belong in the platform

3. **"Am I reading configuration from the definition, or hardcoding it?"**
   - Configuration should always come from server definitions

4. **"Does this require platform code changes for each new server?"**
   - If yes, redesign to use the server definition schema

5. **"Would a third-party developer need to modify platform code to use this?"**
   - If yes, the design is wrong

#### If You Find Yourself...

- Writing `if server_name == "..."` → **STOP** - use server definition schema
- Creating server-specific config objects → **STOP** - extend the schema
- Adding special cases for certain servers → **STOP** - make it generic
- Implementing server-specific endpoints → **STOP** - use generic patterns

**The platform is a generic MCP server orchestrator, not a collection of server-specific handlers.**

## Documentation Rules

- **No temporal references**: Don't use "New features", "Recently added", "Now supports", or dates
- **No decorative elements**: No emojis, ASCII art, or excessive formatting
- **Write in present tense**: Say "Supports X" not "Now supports X" or "Added support for X"
- **No changelog content**: Documentation describes what IS, not what WAS or what's NEW

## Code documentation:

- Use clear, concise comments
- Document the purpose, not the history
- No version numbers or dates in comments

## README updates:

- Maintain consistent structure
- Update feature lists without marking items as new
- Keep installation and usage instructions current

## Python Code Standards

### Import Organization

- **All imports at the top**: Never place imports inline or inside functions (except for circular dependency resolution)
- **Import order** (PEP 8 standard):
  1. Standard library imports
  2. Related third-party imports
  3. Local application/library specific imports
- **One import per line** for explicit imports
- **Blank lines between groups**: Separate import groups with one blank line
- **No wildcard imports**: Always import specific names
- **Sort imports**: Alphabetically within each group
- **Use absolute imports**: Always use full package paths
  - ✅ `from nimbletools_control_plane.registry_client import RegistryClient`
  - ❌ `from ..registry_client import RegistryClient`
  - ❌ `from .utils import helper_function`
- **Package imports**: Import from the package namespace, not relative paths
- **Why absolute imports**:
  - More explicit and readable
  - Avoid confusion about module location
  - Better for refactoring and moving files
  - Work consistently regardless of execution context
- **Import style consistency**:

  ```python
  # Standard library
  import os
  import sys
  from typing import Dict, List, Optional

  # Third-party
  import pytest
  from fastapi import FastAPI

  # Local application - always absolute
  from nimbletools_control_plane.models import User
  from nimbletools_control_plane.services.auth import authenticate
  ```

### Package Management

- **Always use uv, never pip**: All package commands should use `uv`, never `pip` directly
  - ❌ Never use: `pip install package`
  - ✅ Always use: `uv pip install package` or `uv add package`
- Virtual environments: Create with `uv venv`
- Requirements: Use `uv pip install -r requirements.txt`
- Lockfiles: Always use `uv sync --frozen` for reproducible builds
- Never write `pip install` in documentation or code

### Development Tools & Scripts

- **All commands through uv**: Every tool must be run via `uv run`
- **Never run tools directly**:
  - ❌ `mypy src/`
  - ❌ `ruff check .`
  - ❌ `pytest tests/`
  - ✅ `uv run mypy src/`
  - ✅ `uv run ruff check .`
  - ✅ `uv run pytest tests/`
- **Common commands**:
  - Linting: `uv run ruff check .`
  - Formatting: `uv run ruff format .`
  - Type checking: `uv run mypy src/`
  - Tests: `uv run pytest`
  - Coverage: `uv run pytest --cov`
- **Scripts in pyproject.toml**: Define all commands as scripts
  ```toml
  [project.scripts]
  lint = "ruff check ."
  format = "ruff format ."
  typecheck = "mypy src/"
  test = "pytest"
  ```

### Code Style & Structure

- **Type hints required**: All functions should have type annotations
- **Docstrings**: Use Google or NumPy style for all public functions/classes
- **Max line length**: 100 characters
- **Function length**: Prefer functions under 50 lines
- **Early returns**: Use guard clauses to reduce nesting
- **No mutable default arguments**
- **Constants**: Use UPPER_SNAKE_CASE at module level

### Test-Driven Development (TDD)

- **Write tests first**: Create failing tests before implementing functionality
- **Red-Green-Refactor cycle**:
  1. Red: Write a failing test
  2. Green: Write minimal code to pass
  3. Refactor: Clean up while keeping tests green
- **Unit tests are required**: When refactoring or extracting functions, always add unit tests to prevent regression
- **Test file structure**: Mirror source structure (e.g., `src/module.py` → `tests/test_module.py`)
- **Test naming**: Use descriptive names `test_should_<expected_behavior>_when_<condition>`
- **One assertion per test**: Each test should verify one behavior
- **Use pytest**: Preferred testing framework
- **Fixtures over setup/teardown**: Use pytest fixtures for test data and mocks
- **Coverage target**: Maintain minimum 80% code coverage
- **Test categories**:
  - Unit tests: Test individual functions/methods in isolation
  - Integration tests: Test component interactions
  - End-to-end tests: Test full workflows
- **Mock external dependencies**: Use `unittest.mock` or `pytest-mock`
- **Test edge cases**: Empty inputs, None values, exceptions
- **Required test scenarios for new functions**:
  - Happy path: Normal operation with valid inputs
  - Edge cases: Boundary values, empty collections, None inputs
  - Error cases: Invalid inputs, exceptions
  - Integration: How the function interacts with dependencies
- **Arrange-Act-Assert pattern**:

  ```python
  def test_user_creation():
      # Arrange
      username = "testuser"

      # Act
      user = create_user(username)

      # Assert
      assert user.name == username
  ```

### Best Practices

- **No print() statements**: Use proper logging
- **Specific exceptions**: Never use bare `except:`
- **No commented-out code**: Delete it or use version control
- **No global mutable state**: Use dependency injection
- **Context in errors**: Include relevant information in error messages

### Code Quality & Problem Resolution

- **Always verify after changes**: Run `make verify` in the module after making code changes to ensure nothing broke
- **Never disable linters or tests**: Always fix the root cause
- **No ignoring warnings**: Don't add `--ignore`, `# noqa`, `# type: ignore`, or `|| true`
- **Examples of FORBIDDEN patterns**:
  - ❌ `uv run ruff check --ignore=ARG001,B904`
  - ❌ `# noqa: F401`
  - ❌ `# type: ignore`
  - ❌ `|| true` to bypass failures
  - ❌ `try/except: pass` to silence errors
  - ❌ Disabling tests that fail
  - ❌ Lowering coverage thresholds
- **Fix the actual issues**:
  - Unused arguments: Use `_` prefix or remove if truly unused
  - Import errors: Fix import structure, don't move imports inside functions
  - Type errors: Add proper type annotations, don't ignore
  - Test failures: Fix the code or update the test, don't skip
- **If a linter rule seems wrong**: Discuss whether to disable it project-wide in `pyproject.toml`, never inline
- **Quality gates are non-negotiable**: CI/CD should fail on any quality issue
- **Example fixes**:

  ```python
  # ❌ WRONG: Ignoring unused argument
  def endpoint(request: Request, dep: Depends(auth)):  # noqa: ARG001
      pass

  # ✅ RIGHT: Prefix with underscore
  def endpoint(request: Request, _dep: Depends(auth)):
      pass

  # ✅ RIGHT: Actually use it
  def endpoint(request: Request, auth: Depends(auth)):
      user = auth.user
  ```

### API Standards

- **Always use Pydantic models**: Never accept raw Request objects or untyped parameters
- **Explicit request/response models**: Create dedicated Pydantic models for every endpoint
- **Model versioning**: All models must include a version field
- **Model naming convention**:
  - Requests: `<Resource><Action>Request` (e.g., `WorkspaceCreateRequest`)
  - Responses: `<Resource><Action>Response` (e.g., `WorkspaceCreateResponse`)
- **Required model structure**:

  ```python
  class WorkspaceCreateRequest(BaseModel):
      """Workspace creation request"""
      version: str = Field(default="v1", description="API version")
      name: str = Field(..., description="Workspace name", pattern=r"^[a-z0-9-]+$")
      description: str | None = Field(default=None, description="Workspace description")

  class WorkspaceCreateResponse(BaseModel):
      """Workspace creation response"""
      version: str = Field(default="v1", description="API version")
      id: str = Field(..., description="Workspace ID")
      name: str = Field(..., description="Workspace name")
      created_at: datetime = Field(..., description="Creation timestamp")
  ```

- **Endpoint structure**:
  ```python
  @router.post("", response_model=WorkspaceCreateResponse)
  async def create_workspace(
      request: WorkspaceCreateRequest,
      auth_context: AuthenticatedRequest = Depends(get_auth_context),
  ) -> WorkspaceCreateResponse:
      # Implementation
      return WorkspaceCreateResponse(...)
  ```
- **Field validation**: Use Pydantic Field() for all model attributes with descriptions
- **Response models**: Always specify `response_model` in route decorators
- **Error responses**: Use consistent error response models across all endpoints
- **No dict returns**: Always return Pydantic model instances, not dictionaries

### Logging Standards

- **Use lazy % formatting**: Always use `logger.info("Message: %s", value)` not f-strings
- **Never use f-strings in logging**: Violates Pylint W1203 (logging-fstring-interpolation)
- **Never use .format() in logging**: Same performance issue as f-strings
- **Examples**:
  - ✅ `logger.info("User %s logged in", username)`
  - ✅ `logger.debug("Processing %d items", count)`
  - ❌ `logger.info(f"User {username} logged in")`
  - ❌ `logger.error("Failed: {}".format(error))`
- **Complex formatting**: Use dict formatting: `logger.info("Server: %(host)s:%(port)d", {'host': host, 'port': port})`

### Documentation

- Use clear, concise comments (above the code, not inline)
- Document the purpose, not the history
- No version numbers or dates in comments
- Write self-documenting code where possible

## Version Management

### Single Source of Truth
- **VERSION file**: All version numbers are managed from a single `VERSION` file at the repository root
- **Automatic synchronization**: Use `make update-version` to sync all components
- **Consistent versioning**: Docker images, Helm chart version, and Helm chart appVersion all use the same version
- **Chart and images in sync**: The Helm chart `version` and `appVersion` are always kept identical to simplify release management

### Version Update Workflow
1. **Update version number**:
   ```bash
   # Recommended: Use make command
   make set-version VERSION=0.3.0

   # Alternative: Edit VERSION file directly, then sync
   echo "0.3.0" > VERSION
   make update-version
   ```

2. **Files automatically updated**:
   - `chart/Chart.yaml` - Both `version` and `appVersion` (kept in sync)
   - `chart/values.yaml` - All Docker image tags
   - `scripts/build-images.sh` - VERSION variable
   - `redeploy.sh` - Any version references
   - `Makefile` - VERSION variable

3. **Build and test locally**:
   ```bash
   # Build all images with new version
   ./scripts/build-images.sh --local

   # Deploy with new version
   ./install.sh --local
   ```

4. **Publish (when ready)**:
   ```bash
   # Full release: verify, tag, build, and publish
   make release
   ```

### Version Commands
- `make version` - Show current version
- `make set-version VERSION=x.y.z` - Set new version and sync all files
- `make update-version` - Sync all files from VERSION file (if manually edited)
- `make tag` - Create and push git tag for current version
- `make publish` - Publish images and chart (prompts for confirmation)
- `make release` - Full release workflow (verify, tag, publish)

### Version Format
- Development: `x.y.z-dev` (e.g., `0.2.0-dev`)
- Release candidates: `x.y.z-rc.n` (e.g., `0.2.0-rc.1`)
- Production: `x.y.z` (e.g., `0.2.0`)
- Follow semantic versioning (semver.org)

### Publishing Workflow
1. **Set version**: `make set-version VERSION=x.y.z`
2. **Verify quality**: `make verify` (runs in all modules)
3. **Test locally**: Build and deploy to local k3d cluster
4. **Release**: `make release` (creates tag, publishes images and chart)
5. **Create GitHub release**: `make github-release` (requires gh CLI)

### Important Notes
- **Always use make set-version** - Never manually edit version files
- **Chart and image versions are synced** - Simplifies version management and tracking
- **Run make verify before release** - Ensures code quality
- **CI/CD integration**: VERSION file is the source for automated builds
- **One version for everything**: Chart version, appVersion, and all image tags use the same version

## Architecture Decisions

### Authentication Service Pattern

- **Centralized auth in control-plane**: All authentication is handled by the control-plane service via the /auth endpoint
- **Control-plane handles both orchestration and auth**: The control-plane service manages Kubernetes resources and provides authentication endpoints
- **Swappable auth implementation**: Enterprise editions can override the /auth endpoint without modifying core functionality
- **Clear separation of concerns**:
  - Control-plane: Kubernetes resource management, server deployment, workspace lifecycle, and authentication
  - Enterprise overrides: Can replace /auth endpoint implementation for custom authentication
- **Extensibility pattern**: Core provides base functionality that can be extended in enterprise editions

### Provider System Architecture

- **Duck-typed providers**: Providers implement expected methods without inheritance, allowing complete replacement without importing OSS code
- **Explicit configuration required**: System requires `PROVIDER_CONFIG` environment variable - no silent defaults to prevent accidental unsecured deployments
- **Provider protocol methods**:
  - `validate_token`: User authentication
  - `check_workspace_access`: Workspace-level access control
  - `check_permission`: Resource-level permission checks
  - `initialize/shutdown`: Lifecycle management

## General Principles

- Documentation should be a snapshot of current functionality
- Write for someone reading it for the first time
- Assume all features are established and stable
- Focus on WHAT and HOW, not WHEN
- No temporal references ("new", "recently added", "now supports")
- No decorative elements (emojis, excessive formatting)

## Component Synchronization

### Critical: Keep All Components in Sync

When adding new fields to the MCP server schema, ALL of the following components must be updated together:

1. **Schema Definition** - The base MCP server.json schema that defines valid fields
2. **CRD (Custom Resource Definition)** - `chart/templates/crd.yaml` must include all schema fields
3. **Control Plane Models** - `control-plane/src/nimbletools_control_plane/mcp_server_models.py` must handle all fields
4. **MCP Operator** - `mcp-operator/src/nimbletools_core_operator/main.py` must process all fields
5. **Universal Adapter** - Must understand and use any runtime-related fields

**Important**: If these components are out of sync, deployments will fail silently with fields being stripped or ignored. Always update all components when changing the schema.
