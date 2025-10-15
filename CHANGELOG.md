# Changelog

All notable changes to NimbleTools Core will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.3] - 2025-10-14

### Fixed
- Control-plane now correctly appends version tag from package definition to Docker image references
- MCP operator now uses smart imagePullPolicy based on image tag (Always for mutable tags like :latest, IfNotPresent for semantic versions)
- Kubernetes pods now pull updated images when version tags are specified in server.json

### Changed
- Image references now include version tag from server.json packages array (e.g., "nimbletools/mcp-deepl:1.0.1")
- Operator determines pull policy automatically: mutable tags (:latest, :edge, :dev) use Always, semantic versions use IfNotPresent

## [0.2.2] - 2025-10-12

### Fixed
- Helm chart `extraEnv` now supports `valueFrom` for referencing Kubernetes secrets, ConfigMaps, and pod metadata
- All three components (control-plane, operator, rbac-controller) now support standard Kubernetes secret management patterns
- Chart.yaml now properly declares nginx-ingress as a dependency to fix helm lint warnings

### Added
- Comprehensive Helm chart testing infrastructure using helm-unittest plugin
- 18 automated tests covering extraEnv functionality across all components
- `docs/HELM_CONFIGURATION.md` - Complete guide for Helm chart configuration with extraEnv examples
- `docs/TESTING_HELM_CHARTS.md` - Guide for testing Helm charts using TDD principles
- `scripts/test-chart.sh` - Automated test runner for chart validation
- Makefile targets: `make test-chart`, `make verify-chart` for chart testing
- Integration of chart tests into main `make verify` workflow
- Chart.lock file to lock dependency versions

### Changed
- Helm chart templates now conditionally render `value` or `valueFrom` based on configuration
- Chart testing now runs as part of CI/CD verification process
- CI now runs `helm dependency build` before linting to validate subcharts

## [0.2.1] - 2025-10-08

### Fixed
- Environment variable handling in MCP operator now checks workspace-secrets for all variables, using secret references when available
- Removed deprecated internal method causing inconsistent environment variable injection

### Changed
- Centralized version management using VERSION file as single source of truth
- Chart version and appVersion now synchronized automatically via `make set-version`

## [0.2.0] - 2025-10-04

### Changed
- Standardized on MCP registry server.json schema for all server definitions
- Centralized documentation in /docs directory
- Updated control-plane, mcp-operator, and universal-adapter to use registry-based server specs

## [0.1.0] - 2025-01-28

### Added
- Initial release of NimbleTools Core MCP service runtime
- MCP Operator for Kubernetes with custom resource definitions
- Control Plane API for workspace and server management
- Universal Adapter for MCP service integration
- RBAC Controller for multi-tenant security
- Configurable domain support via global.domain setting
- Local development support with k3d clusters
- Nginx Ingress integration for HTTP routing
- Docker Hub and GHCR publishing workflows
- Comprehensive installation script with --local flag
