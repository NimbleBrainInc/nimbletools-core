# Contributing to NimbleTools Core

Thank you for your interest in contributing to NimbleTools Core! This document provides guidelines and information for contributors.

## Code of Conduct

This project adheres to a Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to support@nimblebrain.ai.

## Getting Started

### Development Setup

1. Clone the repository:

```bash
git clone https://github.com/nimblebrain/nimbletools-core.git
cd nimbletools-core
```

2. Set up local development environment:

```bash
./scripts/dev-setup.sh
```

3. Verify installation:

```bash
kubectl get pods -n nimbletools-core-system
```

### Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes
4. Test your changes locally
5. Commit your changes: `git commit -m "Description of your changes"`
6. Push to your fork: `git push origin feature/your-feature-name`
7. Open a Pull Request

## Development Guidelines

### Code Quality Standards

- **Type Annotations**: All Python functions must have complete type annotations
- **Linting**: Code must pass `ruff check` and `black` formatting
- **Testing**: New features must include appropriate tests
- **Documentation**: Update documentation for user-facing changes

### Python Code Standards

```bash
# Format code
black .

# Check linting
ruff check --fix .

# Type checking
mypy --ignore-missing-imports .
```

### Kubernetes Manifests

- Use consistent naming conventions (kebab-case for resources)
- Include proper labels and annotations
- Test manifests in local k3d cluster before submitting

### Docker Images

- Multi-stage builds for minimal image size
- Non-root user for security
- Proper health checks
- Clear documentation of build process

## Testing

### Local Testing

```bash
# Build and install locally
./scripts/dev-setup.sh

# Test basic functionality (Update workspace!)
kubectl apply -f examples/everything.yaml
kubectl get mcpservices

# Test API endpoints
curl http://nimbletools.dev/health
```

### Integration Tests

```bash
# Run full installation test
time ./scripts/install.sh

# Verify all components are working
./scripts/test-installation.sh
```

## Pull Request Process

1. **Small, Focused Changes**: Keep PRs focused on a single feature or fix
2. **Clear Description**: Describe what your PR does and why
3. **Tests**: Include tests for new functionality
4. **Documentation**: Update documentation if needed
5. **Review Process**: Address reviewer feedback promptly

### PR Checklist

- [ ] Code follows project style guidelines
- [ ] Tests pass locally
- [ ] Documentation updated (if applicable)
- [ ] PR description clearly explains the changes
- [ ] Commits have clear, descriptive messages

## Architecture Guidelines

### Operator Development

- Follow the existing pattern using Kopf framework
- Keep operator logic simple and focused
- Use proper error handling and logging
- Test operator behavior with various MCPService configurations

### API Development

- Use FastAPI with proper async patterns
- Implement proper error handling and status codes
- Follow RESTful API conventions
- Include OpenAPI documentation

### Helm Chart Updates

- Test chart changes in local k3d cluster
- Follow Helm best practices
- Update default values appropriately
- Include proper RBAC permissions

## Issue Reporting

When reporting issues, please include:

1. **Environment**: Kubernetes version, OS, installation method
2. **Steps to Reproduce**: Clear steps to reproduce the issue
3. **Expected Behavior**: What you expected to happen
4. **Actual Behavior**: What actually happened
5. **Logs**: Relevant logs from pods/services
6. **Configuration**: Any custom configuration used

## Documentation

- Keep README.md up to date with significant changes
- Update examples if API changes
- Include inline code documentation
- Consider adding tutorials for complex features

## Release Process

Releases are managed by maintainers. The process includes:

1. Version bump in appropriate files
2. Update CHANGELOG.md
3. Create GitHub release with release notes
4. Build and push Docker images
5. Update Helm chart repository

## Community

- **Discussions**: Use GitHub Discussions for questions and ideas
- **Discord**: Join our Discord server for real-time chat
- **Issues**: Use GitHub Issues for bugs and feature requests

## License

By contributing to NimbleTools Core, you agree that your contributions will be licensed under the Apache 2.0 License.
