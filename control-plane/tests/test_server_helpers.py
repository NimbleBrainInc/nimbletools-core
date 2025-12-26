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
import pytest

from nimbletools_control_plane.routes.servers import (
    MCPBValidationError,
    _build_labels_and_annotations,
    _build_resources_config,
    _build_scaling_config,
    _extract_container_config,
    _extract_mcpb_filename,
    _find_mcpb_package_for_arch,
    _serialize_packages,
    _validate_mcpb_packages,
)


class TestExtractMcpbFilename:
    """Test _extract_mcpb_filename helper function."""

    def test_extract_filename_from_github_url(self):
        """Test extracting filename from GitHub release URL."""
        url = "https://github.com/NimbleBrainInc/mcp-echo/releases/download/v1.0.0/mcp-echo-v1.0.0-linux-amd64.mcpb"
        result = _extract_mcpb_filename(url)
        assert result == "mcp-echo-v1.0.0-linux-amd64.mcpb"

    def test_extract_filename_from_s3_url(self):
        """Test extracting filename from S3 URL."""
        url = "https://my-bucket.s3.amazonaws.com/servers/my-server-v2.0.0-linux-arm64.mcpb"
        result = _extract_mcpb_filename(url)
        assert result == "my-server-v2.0.0-linux-arm64.mcpb"

    def test_extract_filename_with_query_params(self):
        """Test extracting filename from URL with query parameters."""
        url = "https://example.com/server.mcpb?token=abc123"
        result = _extract_mcpb_filename(url)
        assert result == "server.mcpb"

    def test_extract_filename_invalid_extension(self):
        """Test that non-.mcpb URLs return None."""
        url = "https://example.com/server.tar.gz"
        result = _extract_mcpb_filename(url)
        assert result is None

    def test_extract_filename_empty_url(self):
        """Test that empty URL returns None."""
        result = _extract_mcpb_filename("")
        assert result is None

    def test_extract_filename_none_url(self):
        """Test that None URL returns None."""
        result = _extract_mcpb_filename(None)  # type: ignore[arg-type]
        assert result is None


class TestValidateMcpbPackages:
    """Test _validate_mcpb_packages validation function."""

    def test_validate_passes_with_matching_arch(self):
        """Test validation passes when architecture matches."""
        amd64_package = Mock(spec=Package)
        amd64_package.registryType = "mcpb"
        amd64_package.identifier = "https://example.com/mcp-echo-v1.0.0-linux-amd64.mcpb"

        arm64_package = Mock(spec=Package)
        arm64_package.registryType = "mcpb"
        arm64_package.identifier = "https://example.com/mcp-echo-v1.0.0-linux-arm64.mcpb"

        # Should not raise for either architecture
        _validate_mcpb_packages([amd64_package, arm64_package], "amd64")
        _validate_mcpb_packages([amd64_package, arm64_package], "arm64")

    def test_validate_fails_with_no_matching_arch(self):
        """Test validation fails when no architecture matches."""
        amd64_package = Mock(spec=Package)
        amd64_package.registryType = "mcpb"
        amd64_package.identifier = "https://example.com/mcp-echo-v1.0.0-linux-amd64.mcpb"

        with pytest.raises(MCPBValidationError) as exc_info:
            _validate_mcpb_packages([amd64_package], "arm64")

        assert exc_info.value.error_code == "ARCHITECTURE_MISMATCH"
        assert "arm64" in exc_info.value.message
        assert "amd64" in exc_info.value.message  # Should list available archs

    def test_validate_fails_with_invalid_url(self):
        """Test validation fails when URL doesn't end with .mcpb."""
        bad_package = Mock(spec=Package)
        bad_package.registryType = "mcpb"
        bad_package.identifier = "https://example.com/not-a-bundle"

        with pytest.raises(MCPBValidationError) as exc_info:
            _validate_mcpb_packages([bad_package], "amd64")

        assert exc_info.value.error_code == "INVALID_MCPB_URL"
        assert "not-a-bundle" in exc_info.value.message

    def test_validate_skips_non_mcpb_packages(self):
        """Test validation ignores non-MCPB packages."""
        oci_package = Mock(spec=Package)
        oci_package.registryType = "oci"
        oci_package.identifier = "myimage:latest"

        # Should not raise - no MCPB packages to validate
        _validate_mcpb_packages([oci_package], "amd64")

    def test_validate_empty_packages(self):
        """Test validation passes with empty package list."""
        _validate_mcpb_packages([], "amd64")

    def test_validate_mixed_packages(self):
        """Test validation only validates MCPB packages in mixed list."""
        oci_package = Mock(spec=Package)
        oci_package.registryType = "oci"
        oci_package.identifier = "myimage:latest"

        mcpb_package = Mock(spec=Package)
        mcpb_package.registryType = "mcpb"
        mcpb_package.identifier = "https://example.com/server-v1.0.0-linux-amd64.mcpb"

        # Should pass - MCPB package matches amd64
        _validate_mcpb_packages([oci_package, mcpb_package], "amd64")


class TestFindMcpbPackageForArch:
    """Test _find_mcpb_package_for_arch helper function."""

    def test_find_package_for_amd64(self):
        """Test finding amd64 package."""
        amd64_package = Mock(spec=Package)
        amd64_package.registryType = "mcpb"
        amd64_package.identifier = "https://example.com/mcp-echo-v1.0.0-linux-amd64.mcpb"

        arm64_package = Mock(spec=Package)
        arm64_package.registryType = "mcpb"
        arm64_package.identifier = "https://example.com/mcp-echo-v1.0.0-linux-arm64.mcpb"

        result = _find_mcpb_package_for_arch([amd64_package, arm64_package], "amd64")
        assert result == amd64_package

    def test_find_package_for_arm64(self):
        """Test finding arm64 package."""
        amd64_package = Mock(spec=Package)
        amd64_package.registryType = "mcpb"
        amd64_package.identifier = "https://example.com/mcp-echo-v1.0.0-linux-amd64.mcpb"

        arm64_package = Mock(spec=Package)
        arm64_package.registryType = "mcpb"
        arm64_package.identifier = "https://example.com/mcp-echo-v1.0.0-linux-arm64.mcpb"

        result = _find_mcpb_package_for_arch([amd64_package, arm64_package], "arm64")
        assert result == arm64_package

    def test_find_package_not_found(self):
        """Test when no matching architecture is found."""
        amd64_package = Mock(spec=Package)
        amd64_package.registryType = "mcpb"
        amd64_package.identifier = "https://example.com/mcp-echo-v1.0.0-linux-amd64.mcpb"

        result = _find_mcpb_package_for_arch([amd64_package], "arm64")
        assert result is None

    def test_find_package_skips_non_mcpb(self):
        """Test that non-MCPB packages are skipped."""
        oci_package = Mock(spec=Package)
        oci_package.registryType = "oci"
        oci_package.identifier = "myimage:latest"

        mcpb_package = Mock(spec=Package)
        mcpb_package.registryType = "mcpb"
        mcpb_package.identifier = "https://example.com/mcp-echo-v1.0.0-linux-amd64.mcpb"

        result = _find_mcpb_package_for_arch([oci_package, mcpb_package], "amd64")
        assert result == mcpb_package


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

    def test_extract_container_config_unknown_registry_type(self):
        """Test that unknown registry types return default config."""
        npm_package = Mock(spec=Package)
        npm_package.registryType = "npm"
        npm_package.identifier = "my-npm-package"

        mcp_server = Mock(spec=MCPServer)
        mcp_server.packages = [npm_package]
        mcp_server.nimbletools_runtime = None

        result = _extract_container_config(mcp_server)

        # Unknown registry type returns default config
        assert result == {
            "image": "unknown",
            "registry": "docker.io",
            "port": 8000,
        }

    def test_extract_container_config_with_mcpb_package(self):
        """Test extraction with MCPB package uses base image and bundle URL."""
        # New schema: separate package entries per architecture, identifier is full URL
        amd64_package = Mock(spec=Package)
        amd64_package.registryType = "mcpb"
        amd64_package.identifier = "https://github.com/NimbleBrainInc/mcp-echo/releases/download/v1.0.0/mcp-echo-v1.0.0-linux-amd64.mcpb"
        amd64_package.version = "1.0.0"
        amd64_package.fileSha256 = "abc123"

        arm64_package = Mock(spec=Package)
        arm64_package.registryType = "mcpb"
        arm64_package.identifier = "https://github.com/NimbleBrainInc/mcp-echo/releases/download/v1.0.0/mcp-echo-v1.0.0-linux-arm64.mcpb"
        arm64_package.version = "1.0.0"
        arm64_package.fileSha256 = "def456"

        runtime = Mock(spec=NimbleToolsRuntime)
        runtime.runtime = "python:3.14"
        runtime.container = None

        mcp_server = Mock(spec=MCPServer)
        mcp_server.packages = [amd64_package, arm64_package]
        mcp_server.nimbletools_runtime = runtime

        result = _extract_container_config(mcp_server)

        assert result["image"] == "mcpb-python:3.14"
        assert result["registry"] == "docker.io/nimbletools"
        assert result["port"] == 8000
        assert "bundleUrl" in result
        # Bundle URL is the identifier directly, architecture is detected from cluster
        assert "linux-" in result["bundleUrl"]
        assert result["bundleUrl"].endswith(".mcpb")
        assert "bundleSha256" in result

    def test_extract_container_config_mcpb_node_runtime(self):
        """Test MCPB with Node.js runtime."""
        # New schema: identifier is full URL with architecture
        amd64_package = Mock(spec=Package)
        amd64_package.registryType = "mcpb"
        amd64_package.identifier = "https://github.com/NimbleBrainInc/mcp-github/releases/download/v2.0.0/mcp-github-v2.0.0-linux-amd64.mcpb"
        amd64_package.version = "2.0.0"
        amd64_package.fileSha256 = None  # No hash provided

        arm64_package = Mock(spec=Package)
        arm64_package.registryType = "mcpb"
        arm64_package.identifier = "https://github.com/NimbleBrainInc/mcp-github/releases/download/v2.0.0/mcp-github-v2.0.0-linux-arm64.mcpb"
        arm64_package.version = "2.0.0"
        arm64_package.fileSha256 = None

        runtime = Mock(spec=NimbleToolsRuntime)
        runtime.runtime = "node:24"
        runtime.container = None

        mcp_server = Mock(spec=MCPServer)
        mcp_server.packages = [amd64_package, arm64_package]
        mcp_server.nimbletools_runtime = runtime

        result = _extract_container_config(mcp_server)

        assert result["image"] == "mcpb-node:24"
        assert result["registry"] == "docker.io/nimbletools"
        assert result["port"] == 8000
        assert "bundleUrl" in result
        assert "mcp-github-v2.0.0-linux-" in result["bundleUrl"]

    def test_extract_container_config_mcpb_missing_runtime_defaults_to_python(self):
        """Test MCPB defaults to python:3.14 when runtime is missing."""
        # New schema: identifier is full URL
        package = Mock(spec=Package)
        package.registryType = "mcpb"
        package.identifier = "https://example.com/releases/v1.0.0/my-server-v1.0.0-linux-amd64.mcpb"
        package.version = "1.0.0"
        package.fileSha256 = None  # No hash provided

        mcp_server = Mock(spec=MCPServer)
        mcp_server.packages = [package]
        mcp_server.nimbletools_runtime = None

        result = _extract_container_config(mcp_server)

        assert result["image"] == "mcpb-python:3.14"
        assert result["registry"] == "docker.io/nimbletools"

    def test_extract_container_config_mcpb_takes_precedence_over_oci(self):
        """Test that MCPB package is processed before OCI if listed first."""
        # New schema: identifier is full URL
        mcpb_package = Mock(spec=Package)
        mcpb_package.registryType = "mcpb"
        mcpb_package.identifier = "https://example.com/releases/v1.0.0/mcp-echo-v1.0.0-linux-amd64.mcpb"
        mcpb_package.version = "1.0.0"
        mcpb_package.fileSha256 = None  # No hash provided

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
        transport = TransportProtocol(type="streamable-http")

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


class TestDeployServerValidation:
    """Test MCPB validation in the deploy_server_to_workspace endpoint."""

    @pytest.fixture
    def valid_mcpb_server_data(self):
        """Valid server data with proper MCPB packages."""
        return {
            "server": {
                "name": "ai.nimbletools/echo",
                "version": "1.0.0",
                "description": "Echo server for testing",
                "packages": [
                    {
                        "registryType": "mcpb",
                        "identifier": "https://github.com/example/releases/v1.0.0/echo-v1.0.0-linux-amd64.mcpb",
                        "version": "1.0.0",
                        "fileSha256": "abc123",
                        "transport": {"type": "streamable-http"},
                    },
                    {
                        "registryType": "mcpb",
                        "identifier": "https://github.com/example/releases/v1.0.0/echo-v1.0.0-linux-arm64.mcpb",
                        "version": "1.0.0",
                        "fileSha256": "def456",
                        "transport": {"type": "streamable-http"},
                    },
                ],
                "_meta": {
                    "ai.nimbletools.mcp/v1": {
                        "status": "active",
                        "runtime": "python:3.14",
                    }
                },
            }
        }

    @pytest.fixture
    def invalid_url_server_data(self):
        """Server data with invalid MCPB URL (missing .mcpb extension)."""
        return {
            "server": {
                "name": "ai.nimbletools/bad-server",
                "version": "1.0.0",
                "description": "Server with bad URL",
                "packages": [
                    {
                        "registryType": "mcpb",
                        "identifier": "https://example.com/not-a-valid-bundle",
                        "version": "1.0.0",
                        "transport": {"type": "streamable-http"},
                    },
                ],
                "_meta": {
                    "ai.nimbletools.mcp/v1": {
                        "status": "active",
                        "runtime": "python:3.14",
                    }
                },
            }
        }

    @pytest.fixture
    def wrong_arch_server_data(self):
        """Server data with MCPB package for wrong architecture."""
        return {
            "server": {
                "name": "ai.nimbletools/wrong-arch",
                "version": "1.0.0",
                "description": "Server with wrong architecture",
                "packages": [
                    {
                        "registryType": "mcpb",
                        "identifier": "https://github.com/example/releases/v1.0.0/server-v1.0.0-linux-arm64.mcpb",
                        "version": "1.0.0",
                        "fileSha256": "abc123",
                        "transport": {"type": "streamable-http"},
                    },
                ],
                "_meta": {
                    "ai.nimbletools.mcp/v1": {
                        "status": "active",
                        "runtime": "python:3.14",
                    }
                },
            }
        }

    @pytest.mark.asyncio
    async def test_deploy_rejects_invalid_mcpb_url(self, invalid_url_server_data):
        """Test that deploy endpoint returns 422 for invalid MCPB URL."""
        from unittest.mock import AsyncMock, patch

        from fastapi import HTTPException

        from nimbletools_control_plane.routes.servers import deploy_server_to_workspace

        mock_request = Mock()

        with patch(
            "nimbletools_control_plane.routes.servers._get_cluster_architecture",
            return_value="amd64",
        ):
            with pytest.raises(HTTPException) as exc_info:
                await deploy_server_to_workspace(
                    workspace_id="test-workspace-123",
                    server_request=invalid_url_server_data,
                    request=mock_request,
                    namespace_name="ws-test-workspace",
                )

            assert exc_info.value.status_code == 422
            assert exc_info.value.detail["error_code"] == "INVALID_MCPB_URL"
            assert "not-a-valid-bundle" in exc_info.value.detail["message"]

    @pytest.mark.asyncio
    async def test_deploy_rejects_wrong_architecture(self, wrong_arch_server_data):
        """Test that deploy endpoint returns 422 when no matching architecture."""
        from unittest.mock import patch

        from fastapi import HTTPException

        from nimbletools_control_plane.routes.servers import deploy_server_to_workspace

        mock_request = Mock()

        # Cluster is amd64, but package only has arm64
        with patch(
            "nimbletools_control_plane.routes.servers._get_cluster_architecture",
            return_value="amd64",
        ):
            with pytest.raises(HTTPException) as exc_info:
                await deploy_server_to_workspace(
                    workspace_id="test-workspace-123",
                    server_request=wrong_arch_server_data,
                    request=mock_request,
                    namespace_name="ws-test-workspace",
                )

            assert exc_info.value.status_code == 422
            assert exc_info.value.detail["error_code"] == "ARCHITECTURE_MISMATCH"
            assert "amd64" in exc_info.value.detail["message"]
            assert exc_info.value.detail["cluster_architecture"] == "amd64"

    @pytest.mark.asyncio
    async def test_deploy_accepts_valid_mcpb_packages(self, valid_mcpb_server_data):
        """Test that deploy endpoint proceeds with valid MCPB packages."""
        from unittest.mock import MagicMock, patch

        from nimbletools_control_plane.routes.servers import deploy_server_to_workspace

        mock_request = Mock()
        mock_k8s_custom = MagicMock()

        # Mock the 404 response to trigger create path
        from kubernetes.client.rest import ApiException

        mock_k8s_custom.get_namespaced_custom_object.side_effect = ApiException(
            status=404, reason="Not Found"
        )
        mock_k8s_custom.create_namespaced_custom_object.return_value = {}

        with patch(
            "nimbletools_control_plane.routes.servers._get_cluster_architecture",
            return_value="amd64",
        ):
            with patch(
                "nimbletools_control_plane.routes.servers.client.CustomObjectsApi",
                return_value=mock_k8s_custom,
            ):
                result = await deploy_server_to_workspace(
                    workspace_id="550e8400-e29b-41d4-a716-446655440000",
                    server_request=valid_mcpb_server_data,
                    request=mock_request,
                    namespace_name="ws-test-workspace",
                )

                # Should succeed and return a deploy response
                assert result.server_id == "echo"
                assert result.status == "pending"
                assert "deployed successfully" in result.message
