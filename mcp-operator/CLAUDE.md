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

## Summary

1. Keep code in `src/` with type hints.
2. Manage dependencies with `uv.lock`.
3. Use Ruff, mypy, pytest, coverage.
4. Build multi-stage, minimal Docker images.
5. Tag and publish images consistently.
6. Run as non-root in containers.
