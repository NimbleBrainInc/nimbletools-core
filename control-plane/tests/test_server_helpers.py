"""Tests for server router helper functions."""

from unittest.mock import Mock

from nimbletools_control_plane.mcp_server_models import (
    EnvironmentVariable,
    MCPServer,
    NimbleToolsRuntime,
    Package,
    Repository,
    TransportProtocol,
)
from nimbletools_control_plane.routes.servers import (
    _build_labels_and_annotations,
    _build_resources_config,
    _build_scaling_config,
    _extract_container_config,
    _serialize_packages,
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
        package.identifier = "myapp"
        package.version = "1.0.1"
        package.registryBaseUrl = "ghcr.io"

        mcp_server = Mock(spec=MCPServer)
        mcp_server.packages = [package]
        mcp_server.nimbletools_runtime = None

        result = _extract_container_config(mcp_server)

        assert result == {
            "image": "myapp:1.0.1",
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
        oci_package.identifier = "myapp"
        oci_package.version = "v2.0.0"
        oci_package.registryBaseUrl = None

        mcp_server = Mock(spec=MCPServer)
        mcp_server.packages = [npm_package, oci_package]
        mcp_server.nimbletools_runtime = None

        result = _extract_container_config(mcp_server)

        # Should use the first OCI package, ignore npm
        assert result == {
            "image": "myapp:v2.0.0",
            "registry": "docker.io",
            "port": 8000,
        }

    def test_extract_container_config_with_mcpb_package(self):
        """Test extraction with MCPB package uses base image and bundle URL."""
        package = Mock(spec=Package)
        package.registryType = "mcpb"
        package.identifier = "mcp-echo"
        package.version = "1.0.0"
        package.registryBaseUrl = "https://github.com/NimbleBrainInc/mcp-echo/releases/download"
        package.sha256 = None  # No hash provided

        runtime = Mock(spec=NimbleToolsRuntime)
        runtime.runtime = "python:3.14"
        runtime.container = None

        mcp_server = Mock(spec=MCPServer)
        mcp_server.packages = [package]
        mcp_server.nimbletools_runtime = runtime

        result = _extract_container_config(mcp_server)

        # URL includes architecture suffix (arm64 from k3d cluster)
        assert result["image"] == "mcpb-python:3.14"
        assert result["registry"] == "docker.io/nimbletools"
        assert result["port"] == 8000
        assert "bundleUrl" in result
        # Bundle URL includes architecture detected from cluster
        assert "mcp-echo-v1.0.0-linux-" in result["bundleUrl"]

    def test_extract_container_config_mcpb_node_runtime(self):
        """Test MCPB with Node.js runtime."""
        package = Mock(spec=Package)
        package.registryType = "mcpb"
        package.identifier = "mcp-github"
        package.version = "2.0.0"
        package.registryBaseUrl = "https://github.com/NimbleBrainInc/mcp-github/releases/download"
        package.sha256 = None  # No hash provided

        runtime = Mock(spec=NimbleToolsRuntime)
        runtime.runtime = "node:24"
        runtime.container = None

        mcp_server = Mock(spec=MCPServer)
        mcp_server.packages = [package]
        mcp_server.nimbletools_runtime = runtime

        result = _extract_container_config(mcp_server)

        assert result["image"] == "mcpb-node:24"
        assert result["registry"] == "docker.io/nimbletools"
        assert result["port"] == 8000
        assert "bundleUrl" in result
        assert "mcp-github-v2.0.0-linux-" in result["bundleUrl"]

    def test_extract_container_config_mcpb_missing_runtime_defaults_to_python(self):
        """Test MCPB defaults to python:3.14 when runtime is missing."""
        package = Mock(spec=Package)
        package.registryType = "mcpb"
        package.identifier = "my-server"
        package.version = "1.0.0"
        package.registryBaseUrl = "https://example.com/releases"
        package.sha256 = None  # No hash provided

        mcp_server = Mock(spec=MCPServer)
        mcp_server.packages = [package]
        mcp_server.nimbletools_runtime = None

        result = _extract_container_config(mcp_server)

        assert result["image"] == "mcpb-python:3.14"
        assert result["registry"] == "docker.io/nimbletools"

    def test_extract_container_config_mcpb_takes_precedence_over_oci(self):
        """Test that MCPB package is processed before OCI if listed first."""
        mcpb_package = Mock(spec=Package)
        mcpb_package.registryType = "mcpb"
        mcpb_package.identifier = "mcp-echo"
        mcpb_package.version = "1.0.0"
        mcpb_package.registryBaseUrl = "https://example.com/releases"
        mcpb_package.sha256 = None  # No hash provided

        oci_package = Mock(spec=Package)
        oci_package.registryType = "oci"
        oci_package.identifier = "old-image"
        oci_package.version = "1.0.0"

        runtime = Mock(spec=NimbleToolsRuntime)
        runtime.runtime = "python:3.14"
        runtime.container = None

        mcp_server = Mock(spec=MCPServer)
        mcp_server.packages = [mcpb_package, oci_package]
        mcp_server.nimbletools_runtime = runtime

        result = _extract_container_config(mcp_server)

        # Should use MCPB, not OCI
        assert result["image"] == "mcpb-python:3.14"
        assert "bundleUrl" in result

    def test_extract_container_config_with_runtime_port(self):
        """Test port override from runtime config."""
        package = Mock(spec=Package)
        package.registryType = "oci"
        package.identifier = "myapp"
        package.version = "latest"
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


class TestSerializePackages:
    """Test _serialize_packages helper function."""

    def test_serialize_packages_preserves_default_field(self):
        """Test that environment variable default values are preserved during serialization."""
        # Create environment variables with default values
        env_var_with_default = EnvironmentVariable(
            name="TRANSPORT",
            default="http",
            isSecret=False,
            isRequired=False,
            description="Transport mode",
        )

        env_var_without_default = EnvironmentVariable(
            name="API_KEY",
            isSecret=True,
            isRequired=True,
            description="API key",
        )

        # Create a package with environment variables
        transport = TransportProtocol(type="streamable-http")
        package = Package(
            registryType="oci",
            identifier="test/image",
            version="1.0.0",
            transport=transport,
            environmentVariables=[env_var_with_default, env_var_without_default],
        )

        # Serialize the packages
        result = _serialize_packages([package])

        # Verify the result
        assert len(result) == 1
        assert "environmentVariables" in result[0]

        env_vars = result[0]["environmentVariables"]
        assert len(env_vars) == 2

        # Find the TRANSPORT env var
        transport_var = next(e for e in env_vars if e["name"] == "TRANSPORT")

        # This is the critical assertion - default value must be preserved
        assert "default" in transport_var
        assert transport_var["default"] == "http"
        assert transport_var["isSecret"] is False
        assert transport_var["isRequired"] is False

        # Verify the API_KEY env var
        api_key_var = next(e for e in env_vars if e["name"] == "API_KEY")
        assert api_key_var["isSecret"] is True
        assert api_key_var["isRequired"] is True

    def test_serialize_packages_empty_list(self):
        """Test serialization of empty package list."""
        result = _serialize_packages([])
        assert result == []

    def test_serialize_packages_none(self):
        """Test serialization when packages is None."""
        result = _serialize_packages(None)
        assert result == []

    def test_serialize_packages_multiple_packages(self):
        """Test serialization of multiple packages."""
        transport = TransportProtocol(type="stdio")

        package1 = Package(
            registryType="npm",
            identifier="package1",
            version="1.0.0",
            transport=transport,
        )

        package2 = Package(
            registryType="pypi",
            identifier="package2",
            version="2.0.0",
            transport=transport,
        )

        result = _serialize_packages([package1, package2])

        assert len(result) == 2
        assert result[0]["identifier"] == "package1"
        assert result[1]["identifier"] == "package2"
