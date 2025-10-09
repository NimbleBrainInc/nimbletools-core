# Changelog

All notable changes to NimbleTools Core will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
