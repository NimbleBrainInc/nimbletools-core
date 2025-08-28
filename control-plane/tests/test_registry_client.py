"""Tests for registry client module."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from nimbletools_control_plane.registry_client import RegistryClient


@pytest.fixture
def registry_client():
    """Create a registry client for testing."""
    return RegistryClient()


@pytest.fixture
def sample_registry_data():
    """Sample registry data for testing."""
    return {
        "apiVersion": "registry.nimbletools.ai/v1",
        "kind": "MCPRegistry",
        "metadata": {
            "name": "test-registry",
            "version": "1.0.0",
            "lastUpdated": "2025-08-25",
        },
        "servers": [
            {
                "name": "echo",
                "version": "1.0.0",
                "status": "active",
                "meta": {
                    "description": "Echo server for testing",
                    "category": "testing",
                    "tags": ["test", "echo"],
                },
                "deployment": {"type": "http"},
                "container": {"image": "echo:latest", "port": 8000},
                "capabilities": {
                    "tools": [{"name": "echo", "description": "Echo text back"}],
                    "resources": [],
                    "prompts": []
                },
                "resources": {
                    "requests": {"cpu": "50m", "memory": "128Mi"},
                    "limits": {"cpu": "200m", "memory": "256Mi"},
                },
            },
            {
                "name": "calculator",
                "version": "1.0.0",
                "status": "deprecated",
                "meta": {"description": "Calculator server", "category": "math"},
                "deployment": {
                    "type": "stdio",
                    "stdio": {
                        "executable": "python",
                        "args": ["calc.py"],
                        "workingDir": "/app",
                    },
                },
                "container": {"image": "calc:latest"},
            },
        ],
    }


class TestRegistryClient:
    """Test cases for RegistryClient."""

    @pytest.mark.asyncio
    async def test_fetch_registry_success(self, registry_client, sample_registry_data):
        """Test successful registry fetching."""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.text = AsyncMock(
            return_value="apiVersion: registry.nimbletools.ai/v1\nkind: MCPRegistry"
        )

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = Mock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session

            # Mock the get method to return a context manager
            mock_get = Mock()
            mock_get.__aenter__ = AsyncMock(return_value=mock_response)
            mock_get.__aexit__ = AsyncMock(return_value=None)
            mock_session.get.return_value = mock_get

            with patch("yaml.safe_load", return_value=sample_registry_data):
                result = await registry_client.fetch_registry(
                    "http://example.com/registry.yaml"
                )

                assert result == sample_registry_data
                # Verify the call was made - the timeout is wrapped in ClientTimeout object
                mock_session.get.assert_called_once()
                call_args = mock_session.get.call_args
                assert call_args[0][0] == "http://example.com/registry.yaml"
                assert hasattr(call_args[1]["timeout"], "total")
                assert call_args[1]["timeout"].total == 30

    @pytest.mark.asyncio
    async def test_fetch_registry_http_error(self, registry_client):
        """Test registry fetch with HTTP error."""
        mock_response = Mock()
        mock_response.status = 404

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = Mock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session

            mock_get = Mock()
            mock_get.__aenter__ = AsyncMock(return_value=mock_response)
            mock_get.__aexit__ = AsyncMock(return_value=None)
            mock_session.get.return_value = mock_get

            with pytest.raises(Exception, match="Failed to fetch registry: HTTP 404"):
                await registry_client.fetch_registry("http://example.com/registry.yaml")

    @pytest.mark.asyncio
    async def test_fetch_registry_timeout(self, registry_client):
        """Test registry fetch timeout."""
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = Mock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session

            mock_session.get.side_effect = TimeoutError()

            with pytest.raises(Exception, match="Timeout fetching registry"):
                await registry_client.fetch_registry("http://example.com/registry.yaml")

    def test_validate_registry_success(self, registry_client, sample_registry_data):
        """Test successful registry validation."""
        # Should not raise an exception
        registry_client._validate_registry(sample_registry_data)

    def test_validate_registry_invalid_api_version(
        self, registry_client, sample_registry_data
    ):
        """Test registry validation with invalid API version."""
        sample_registry_data["apiVersion"] = "invalid/v1"

        with pytest.raises(Exception, match="Invalid or missing apiVersion"):
            registry_client._validate_registry(sample_registry_data)

    def test_validate_registry_invalid_kind(
        self, registry_client, sample_registry_data
    ):
        """Test registry validation with invalid kind."""
        sample_registry_data["kind"] = "InvalidKind"

        with pytest.raises(Exception, match="Invalid or missing kind"):
            registry_client._validate_registry(sample_registry_data)

    def test_validate_registry_missing_name(
        self, registry_client, sample_registry_data
    ):
        """Test registry validation with missing name."""
        del sample_registry_data["metadata"]["name"]

        with pytest.raises(Exception, match="Registry metadata missing name"):
            registry_client._validate_registry(sample_registry_data)

    def test_validate_registry_invalid_servers(
        self, registry_client, sample_registry_data
    ):
        """Test registry validation with invalid servers."""
        sample_registry_data["servers"] = "not-a-list"

        with pytest.raises(Exception, match="Registry servers must be a list"):
            registry_client._validate_registry(sample_registry_data)

    def test_get_registry_info(self, registry_client, sample_registry_data):
        """Test extracting registry information."""
        info = registry_client.get_registry_info(sample_registry_data)

        assert info["name"] == "test-registry"
        assert info["version"] == "1.0.0"
        assert info["last_updated"] == "2025-08-25"
        assert info["total_servers"] == 2
        assert info["active_servers"] == 1

    def test_get_active_servers(self, registry_client, sample_registry_data):
        """Test getting active servers."""
        active_servers = registry_client.get_active_servers(sample_registry_data)

        assert len(active_servers) == 1
        assert active_servers[0]["name"] == "echo"
        assert active_servers[0]["status"] == "active"

    def test_convert_to_mcpservice_http(self, registry_client, sample_registry_data):
        """Test converting HTTP server to MCPService."""
        server = sample_registry_data["servers"][0]  # echo server
        mcpservice = registry_client.convert_to_mcpservice(server, "test-namespace")

        assert mcpservice["apiVersion"] == "mcp.nimbletools.dev/v1"
        assert mcpservice["kind"] == "MCPService"
        assert mcpservice["metadata"]["name"] == "echo"
        assert mcpservice["metadata"]["namespace"] == "test-namespace"
        assert mcpservice["metadata"]["labels"]["mcp.nimbletools.dev/service"] == "true"
        assert (
            mcpservice["metadata"]["labels"]["mcp.nimbletools.dev/category"]
            == "testing"
        )
        assert (
            mcpservice["metadata"]["annotations"]["mcp.nimbletools.dev/tags"]
            == "test,echo"
        )

        # Check spec
        spec = mcpservice["spec"]
        assert spec["deployment"]["type"] == "http"
        assert spec["container"]["image"] == "echo:latest"
        assert spec["container"]["port"] == 8000
        assert spec["tools"][0]["name"] == "echo"
        assert spec["resources"]["requests"]["cpu"] == "50m"

    def test_convert_to_mcpservice_stdio(self, registry_client, sample_registry_data):
        """Test converting stdio server to MCPService."""
        server = sample_registry_data["servers"][1]  # calculator server
        mcpservice = registry_client.convert_to_mcpservice(server, "test-namespace")

        assert mcpservice["metadata"]["name"] == "calculator"

        # Check stdio deployment
        spec = mcpservice["spec"]
        assert spec["deployment"]["type"] == "stdio"
        assert spec["deployment"]["stdio"]["executable"] == "python"
        assert spec["deployment"]["stdio"]["args"] == ["calc.py"]
        assert spec["deployment"]["stdio"]["workingDir"] == "/app"
        assert spec["container"]["image"] == "calc:latest"

    def test_process_deployment_config_http(self, registry_client):
        """Test processing HTTP deployment config."""
        deployment_config = {"type": "http", "http": {"port": 9000, "path": "/custom"}}

        result = registry_client._process_deployment_config(deployment_config)

        assert result["type"] == "http"
        assert result["http"]["port"] == 9000
        assert result["http"]["path"] == "/custom"

    def test_process_deployment_config_stdio(self, registry_client):
        """Test processing stdio deployment config."""
        deployment_config = {
            "type": "stdio",
            "stdio": {
                "executable": "node",
                "args": ["server.js"],
                "workingDir": "/usr/app",
            },
        }

        result = registry_client._process_deployment_config(deployment_config)

        assert result["type"] == "stdio"
        assert result["stdio"]["executable"] == "node"
        assert result["stdio"]["args"] == ["server.js"]
        assert result["stdio"]["workingDir"] == "/usr/app"

    def test_process_container_config(self, registry_client):
        """Test processing container config."""
        container_config = {"image": "my-app:v2.0", "port": 3000, "tag": "latest"}

        result = registry_client._process_container_config(container_config)

        assert result["image"] == "my-app:v2.0"
        assert result["port"] == 3000
        assert result["tag"] == "latest"

    def test_process_resources_config(self, registry_client):
        """Test processing resources config."""
        resources_config = {
            "requests": {"cpu": "100m", "memory": "256Mi"},
            "limits": {"cpu": "500m", "memory": "512Mi"},
        }

        result = registry_client._process_resources_config(resources_config)

        assert result["requests"]["cpu"] == "100m"
        assert result["requests"]["memory"] == "256Mi"
        assert result["limits"]["cpu"] == "500m"
        assert result["limits"]["memory"] == "512Mi"
