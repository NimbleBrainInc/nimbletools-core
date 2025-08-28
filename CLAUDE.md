# Claude.md

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

- **Always use uv, never pip**: All package commands should use `uv pip install`
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

## General Principles

- Documentation should be a snapshot of current functionality
- Write for someone reading it for the first time
- Assume all features are established and stable
- Focus on WHAT and HOW, not WHEN
- No temporal references ("new", "recently added", "now supports")
- No decorative elements (emojis, excessive formatting)
