"""Tests for server router helper functions."""

from unittest.mock import Mock

from nimbletools_control_plane.mcp_server_models import (
    MCPServer,
    NimbleToolsRuntime,
    Package,
    Repository,
)
from nimbletools_control_plane.routes.servers import (
    _build_labels_and_annotations,
    _build_resources_config,
    _build_scaling_config,
    _extract_container_config,
)


class TestExtractContainerConfig:
    """Test _extract_container_config helper function."""

    def test_extract_container_config_no_packages(self):
        """Test extraction when no packages are available."""
        mcp_server = Mock(spec=MCPServer)
        mcp_server.packages = None
        mcp_server.nimbletools_runtime = None

        result = _extract_container_config(mcp_server)

        assert result == {
            "image": "unknown",
            "registry": "docker.io",
            "port": 8000,
        }

    def test_extract_container_config_with_oci_package(self):
        """Test extraction with OCI package."""
        package = Mock(spec=Package)
        package.registryType = "oci"
        package.identifier = "myapp:latest"
        package.registryBaseUrl = "ghcr.io"

        mcp_server = Mock(spec=MCPServer)
        mcp_server.packages = [package]
        mcp_server.nimbletools_runtime = None

        result = _extract_container_config(mcp_server)

        assert result == {
            "image": "myapp:latest",
            "registry": "ghcr.io",
            "port": 8000,
        }

    def test_extract_container_config_skip_non_oci_packages(self):
        """Test that non-OCI packages are skipped."""
        npm_package = Mock(spec=Package)
        npm_package.registryType = "npm"
        npm_package.identifier = "my-npm-package"

        oci_package = Mock(spec=Package)
        oci_package.registryType = "oci"
        oci_package.identifier = "myapp:v2"
        oci_package.registryBaseUrl = None

        mcp_server = Mock(spec=MCPServer)
        mcp_server.packages = [npm_package, oci_package]
        mcp_server.nimbletools_runtime = None

        result = _extract_container_config(mcp_server)

        # Should use the first OCI package, ignore npm
        assert result == {
            "image": "myapp:v2",
            "registry": "docker.io",
            "port": 8000,
        }

    def test_extract_container_config_with_runtime_port(self):
        """Test port override from runtime config."""
        package = Mock(spec=Package)
        package.registryType = "oci"
        package.identifier = "myapp:latest"
        package.registryBaseUrl = None

        runtime = Mock(spec=NimbleToolsRuntime)
        runtime.container = Mock()
        runtime.container.healthCheck = Mock()
        runtime.container.healthCheck.port = 3000

        mcp_server = Mock(spec=MCPServer)
        mcp_server.packages = [package]
        mcp_server.nimbletools_runtime = runtime

        result = _extract_container_config(mcp_server)

        assert result == {
            "image": "myapp:latest",
            "registry": "docker.io",
            "port": 3000,
        }


class TestBuildResourcesConfig:
    """Test _build_resources_config helper function."""

    def test_build_resources_config_no_runtime(self):
        """Test when runtime is None."""
        result = _build_resources_config(None)
        assert result == {}

    def test_build_resources_config_no_resources(self):
        """Test when runtime exists but has no resources."""
        runtime = Mock()
        runtime.resources = None

        result = _build_resources_config(runtime)
        assert result == {}

    def test_build_resources_config_with_resources(self):
        """Test with complete resource configuration."""
        runtime = Mock()
        runtime.resources = Mock()
        runtime.resources.requests = Mock()
        runtime.resources.requests.cpu = "100m"
        runtime.resources.requests.memory = "128Mi"
        runtime.resources.limits = Mock()
        runtime.resources.limits.cpu = "500m"
        runtime.resources.limits.memory = "512Mi"

        result = _build_resources_config(runtime)

        assert result == {
            "requests": {
                "cpu": "100m",
                "memory": "128Mi",
            },
            "limits": {
                "cpu": "500m",
                "memory": "512Mi",
            },
        }


class TestBuildScalingConfig:
    """Test _build_scaling_config helper function."""

    def test_build_scaling_config_defaults_only(self):
        """Test with no runtime or user scaling."""
        result = _build_scaling_config(None, None)

        assert result == {
            "minReplicas": 0,
            "maxReplicas": 10,
            "targetConcurrency": 10,
            "scaleDownDelay": "5m",
        }

    def test_build_scaling_config_with_runtime_scaling(self):
        """Test with runtime scaling configuration."""
        runtime = Mock()
        runtime.scaling = Mock()
        runtime.scaling.minReplicas = 1
        runtime.scaling.maxReplicas = 5
        runtime.scaling.enabled = True

        result = _build_scaling_config(runtime, None)

        assert result == {
            "minReplicas": 1,
            "maxReplicas": 5,
            "enabled": True,
            "targetConcurrency": 10,
            "scaleDownDelay": "5m",
        }

    def test_build_scaling_config_with_user_scaling(self):
        """Test with user-provided scaling overrides."""
        runtime = Mock()
        runtime.scaling = Mock()
        runtime.scaling.minReplicas = 1
        runtime.scaling.maxReplicas = 5
        runtime.scaling.enabled = True

        user_scaling = {
            "maxReplicas": 20,
            "targetConcurrency": 50,
            "customField": "value",
        }

        result = _build_scaling_config(runtime, user_scaling)

        # User scaling should override runtime values
        assert result == {
            "minReplicas": 1,
            "maxReplicas": 20,  # Overridden by user
            "enabled": True,
            "targetConcurrency": 50,  # Overridden by user
            "scaleDownDelay": "5m",
            "customField": "value",  # Added by user
        }


class TestBuildLabelsAndAnnotations:
    """Test _build_labels_and_annotations helper function."""

    def test_build_labels_and_annotations_minimal(self):
        """Test with minimal MCP server configuration."""
        mcp_server = Mock(spec=MCPServer)
        mcp_server.name = "provider/my-server"
        mcp_server.version = "1.0.0"
        mcp_server.description = "Test server"
        mcp_server.status = "stable"
        mcp_server.repository = None

        labels, annotations = _build_labels_and_annotations(mcp_server, "workspace-123", None)

        assert labels == {
            "mcp.nimbletools.dev/workspace": "workspace-123",
            "mcp.nimbletools.dev/service": "true",
            "mcp.nimbletools.dev/server-name": "provider-my-server",
        }

        assert annotations == {
            "mcp.nimbletools.dev/version": "1.0.0",
            "mcp.nimbletools.dev/description": "Test server",
            "mcp.nimbletools.dev/status": "stable",
        }

    def test_build_labels_and_annotations_with_categories(self):
        """Test with runtime categories."""
        mcp_server = Mock(spec=MCPServer)
        mcp_server.name = "provider/my-server"
        mcp_server.version = "1.0.0"
        mcp_server.description = "Test server"
        mcp_server.status = "stable"
        mcp_server.repository = None

        runtime = Mock()
        runtime.registry = Mock()
        runtime.registry.categories = ["ai", "ml", "data", "extra"]  # 4 categories
        runtime.registry.tags = None

        labels, annotations = _build_labels_and_annotations(mcp_server, "workspace-123", runtime)

        # Should only use first 3 categories
        assert labels["mcp.nimbletools.dev/category-0"] == "ai"
        assert labels["mcp.nimbletools.dev/category-1"] == "ml"
        assert labels["mcp.nimbletools.dev/category-2"] == "data"
        assert "mcp.nimbletools.dev/category-3" not in labels

    def test_build_labels_and_annotations_with_repository(self):
        """Test with repository URL."""
        repository = Mock(spec=Repository)
        repository.url = "https://github.com/example/repo"

        mcp_server = Mock(spec=MCPServer)
        mcp_server.name = "provider/my-server"
        mcp_server.version = "1.0.0"
        mcp_server.description = "Test server"
        mcp_server.status = "stable"
        mcp_server.repository = repository

        labels, annotations = _build_labels_and_annotations(mcp_server, "workspace-123", None)

        assert annotations["mcp.nimbletools.dev/repository"] == "https://github.com/example/repo"

    def test_build_labels_and_annotations_with_tags(self):
        """Test with runtime tags."""
        mcp_server = Mock(spec=MCPServer)
        mcp_server.name = "provider/my-server"
        mcp_server.version = "1.0.0"
        mcp_server.description = "Test server"
        mcp_server.status = "stable"
        mcp_server.repository = None

        runtime = Mock()
        runtime.registry = Mock()
        runtime.registry.categories = None
        runtime.registry.tags = ["production", "stable", "v2"]

        labels, annotations = _build_labels_and_annotations(mcp_server, "workspace-123", runtime)

        assert annotations["mcp.nimbletools.dev/tags"] == "production,stable,v2"

    def test_build_labels_and_annotations_server_name_with_slashes(self):
        """Test that slashes in server names are replaced."""
        mcp_server = Mock(spec=MCPServer)
        mcp_server.name = "provider/category/my-server"
        mcp_server.version = "1.0.0"
        mcp_server.description = "Test server"
        mcp_server.status = "stable"
        mcp_server.repository = None

        labels, annotations = _build_labels_and_annotations(mcp_server, "workspace-123", None)

        # Slashes should be replaced with dashes
        assert labels["mcp.nimbletools.dev/server-name"] == "provider-category-my-server"
