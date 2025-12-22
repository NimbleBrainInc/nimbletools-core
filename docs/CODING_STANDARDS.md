# Coding Standards

## Python Standards

### Imports

- All imports at top of file (except circular dependency resolution)
- Order: stdlib, third-party, local (blank line between groups)
- **Absolute imports only**: `from nimbletools_control_plane.x import y`
- No relative imports: `from ..x` or `from .x`
- No wildcard imports

Example:
```python
# Standard library
import os
from typing import Dict, List

# Third-party
from fastapi import FastAPI

# Local - always absolute
from nimbletools_control_plane.models import User
```

### Package Management

- **Always use uv, never pip**
- Run tools via uv: `uv run pytest`, `uv run mypy src/`
- Lockfiles: `uv sync --frozen`

### Code Style

- Type hints required on all functions
- Docstrings: Google or NumPy style
- Max line length: 100 characters
- Functions under 50 lines preferred
- Use guard clauses for early returns
- No mutable default arguments
- Constants: UPPER_SNAKE_CASE

## Testing

### TDD Approach

1. Red: Write failing test
2. Green: Minimal code to pass
3. Refactor: Clean up, keep tests green

### Test Structure

- Mirror source: `src/module.py` -> `tests/test_module.py`
- Naming: `test_should_<behavior>_when_<condition>`
- One assertion per test
- Use pytest fixtures over setup/teardown
- Coverage target: 80%

### Required Test Scenarios

- Happy path
- Edge cases (empty, None, boundaries)
- Error cases
- Integration with dependencies

### Arrange-Act-Assert

```python
def test_user_creation():
    # Arrange
    username = "testuser"

    # Act
    user = create_user(username)

    # Assert
    assert user.name == username
```

## API Standards

### Pydantic Models

- Always use Pydantic models, never raw Request or dicts
- Naming: `<Resource><Action>Request/Response`
- Include version field in all models
- Use Field() with descriptions

```python
class WorkspaceCreateRequest(BaseModel):
    version: str = Field(default="v1")
    name: str = Field(..., pattern=r"^[a-z0-9-]+$")

class WorkspaceCreateResponse(BaseModel):
    version: str = Field(default="v1")
    id: str
    created_at: datetime
```

### Endpoints

```python
@router.post("", response_model=WorkspaceCreateResponse)
async def create_workspace(
    request: WorkspaceCreateRequest,
    auth: AuthenticatedRequest = Depends(get_auth_context),
) -> WorkspaceCreateResponse:
    return WorkspaceCreateResponse(...)
```

## Logging

- Lazy % formatting: `logger.info("User %s", username)`
- Never f-strings: `logger.info(f"User {username}")` - WRONG
- Never .format(): `logger.info("User {}".format(x))` - WRONG

## Code Quality

### Forbidden Patterns

- `# noqa` or `# type: ignore`
- `|| true` to bypass failures
- `try/except: pass`
- `--ignore` flags on linters
- Disabling or skipping tests
- Lowering coverage thresholds

### Fixing Issues

- Unused arguments: prefix with `_` or remove
- Import errors: fix structure, don't inline imports
- Type errors: add annotations, don't ignore
- Test failures: fix code or update test, don't skip

### Verification

Run `make verify` after changes. Quality gates are non-negotiable.

## Documentation

- Comments above code, not inline
- Document purpose, not history
- No version numbers or dates in comments
- No temporal language ("new", "added", "now supports")
