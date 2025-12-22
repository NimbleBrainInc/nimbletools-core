# Contributing to NimbleTools Core

Thank you for your interest in contributing to NimbleTools Core!

## Code of Conduct

This project adheres to a Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to support@nimblebrain.ai.

## Getting Started

### Development Setup

```bash
git clone https://github.com/NimbleBrainInc/nimbletools-core.git
cd nimbletools-core

# Full dev cycle: verify, build, deploy to local k3d
make dev

# Verify installation
kubectl get pods -n nimbletools-system
```

### Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes
4. Verify: `make verify`
5. Test locally: `make dev`
6. Commit and push
7. Open a Pull Request

## Code Quality

### Quick Verification

```bash
# Run all checks (lint, type-check, test)
make verify

# Or per-component
cd control-plane && make verify
cd mcp-operator && make verify
```

### Manual Commands

```bash
# Format
uv run ruff format .

# Lint
uv run ruff check .

# Type check
uv run mypy src/

# Test
uv run pytest
```

### Standards

For detailed coding standards (imports, testing, API patterns, logging), see:
- [Coding Standards](/docs/CODING_STANDARDS.md)
- [Platform Principles](/docs/PLATFORM_PRINCIPLES.md)

## Testing

### Local Testing

```bash
# Full dev cycle with smoke tests
make dev

# Quick rebuild (skip tests)
make dev-quick

# Component tests only
cd control-plane && make verify
```

### Manual Testing

```bash
# Deploy test service
kubectl apply -f examples/echo-mcp.yaml
kubectl get mcpservices

# Test API
curl http://api.nimbletools.dev/health
```

## Pull Request Process

### Requirements

- Small, focused changes (one feature or fix per PR)
- Tests pass: `make verify`
- Documentation updated if needed
- Clear commit messages

### Checklist

- [ ] `make verify` passes
- [ ] Tests added for new functionality
- [ ] Documentation updated (if applicable)
- [ ] PR description explains the changes

## Architecture Guidelines

### Key Principle

**No server-specific logic in platform code.** All server behavior comes from registry definitions. See [Platform Principles](/docs/PLATFORM_PRINCIPLES.md).

### Component Development

**Operator**: Kopf framework, generic resource handling
**Control Plane**: FastAPI, Pydantic models, async patterns
**Helm Chart**: Test in local k3d before submitting

## Issue Reporting

Include:
1. Environment (K8s version, OS, installation method)
2. Steps to reproduce
3. Expected vs actual behavior
4. Relevant logs (`kubectl logs -l app=...`)
5. Configuration used

## Release Process

See [Release Process](/docs/RELEASE_PROCESS.md) for details.

Releases are managed by maintainers:
1. `make set-version VERSION=x.y.z`
2. `make verify`
3. `make release`

## Community

- **Discussions**: GitHub Discussions
- **Issues**: GitHub Issues for bugs and feature requests

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
