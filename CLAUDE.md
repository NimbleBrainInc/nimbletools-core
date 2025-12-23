# CLAUDE.md

## Quick Reference

| Task | Command |
|------|---------|
| Full dev cycle | `make dev` |
| Fast iteration | `make dev-quick` |
| Run tests | `make verify` or `cd <component> && make verify` |
| Set version | `make set-version VERSION=x.y.z` |
| Dev publish | `make dev-publish` (pushes -dev images) |
| Release | `make release` |

## Critical Constraints

### No Server-Specific Logic
Platform components are generic orchestrators. All server behavior comes from registry definitions.
Never write `if server_name == "..."`. See `/docs/PLATFORM_PRINCIPLES.md`.

### No Linter Bypasses
Never use `# noqa`, `# type: ignore`, `|| true`. Fix root cause.

### Schema Sync Required
When changing MCP server schema, update ALL components together:
- `mcp_server_models.py` (Pydantic)
- `crd.yaml` (Kubernetes CRD)
- `main.py` in operator

### Use uv, Not pip
All commands: `uv run pytest`, `uv run mypy`, `uv sync --frozen`

### Absolute Imports Only
`from nimbletools_control_plane.x import y` - no relative imports

### Lazy Log Formatting
`logger.info("msg: %s", val)` - never f-strings in logging

## Development Workflows

### Core Only
```bash
make dev          # verify -> build -> deploy -> smoke test
make dev-quick    # skip tests after initial verification
```

### With Enterprise
```bash
make set-version VERSION=0.3.0
make dev-publish  # Push nimbletools/*:0.3.0-dev
# Enterprise can now build
```

### Production Release
```bash
make release      # verify, git tag, push stable images + chart
```

## Architecture

### Provider System
- Duck-typed providers (no inheritance)
- Requires `PROVIDER_CONFIG` env var
- Methods: `validate_token`, `check_workspace_access`, `check_permission`

### Auth
- Centralized in control-plane `/auth` endpoint
- Swappable for enterprise

## Documentation

All docs in `/docs`, not component directories. No temporal language.

## Standards References

Read these when working on relevant tasks:
- Platform architecture: `/docs/PLATFORM_PRINCIPLES.md`
- Python/testing/API standards: `/docs/CODING_STANDARDS.md`
- Version/release workflow: `/docs/RELEASE_PROCESS.md`
