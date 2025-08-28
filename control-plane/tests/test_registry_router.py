"""Tests for registry router module."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
import yaml
from fastapi.testclient import TestClient
from kubernetes.client.rest import ApiException

from nimbletools_control_plane.auth import AuthenticatedRequest, AuthType, UserContext
from nimbletools_control_plane.routes.registry import (
    _create_mcpservice,
    _create_namespace,
    _sanitize_namespace_name,
    list_registry_servers,
)


@pytest.fixture
def sample_registry_data():
    """Sample registry data for testing."""
    return {
        "apiVersion": "registry.nimbletools.ai/v1",
        "kind": "MCPRegistry",
        "metadata": {
            "name": "community-servers",
            "version": "2.0.0",
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
                    "capabilities": {
                "tools": [{"name": "echo", "description": "Echo text back"}],
                "resources": [],
                "prompts": []
            },
                    "resources": [],
                    "prompts": []
                },
            }
        ],
    }


@pytest.fixture
def mock_k8s_namespace():
    """Mock Kubernetes namespace object."""
    mock_ns = Mock()
    mock_ns.metadata.name = "registry-community-servers"
    mock_ns.metadata.creation_timestamp = "2025-08-25T10:00:00Z"
    mock_ns.metadata.labels = {
        "mcp.nimbletools.dev/registry": "true",
        "mcp.nimbletools.dev/registry-name": "community-servers",
        "mcp.nimbletools.dev/owner": "test-user",
    }
    mock_ns.metadata.annotations = {
        "mcp.nimbletools.dev/registry-url": "https://example.com/registry.yaml"
    }
    return mock_ns


@pytest.fixture
def mock_mcpservice():
    """Mock MCPService object."""
    return {
        "metadata": {
            "name": "echo",
            "namespace": "registry-community-servers",
            "labels": {
                "mcp.nimbletools.dev/version": "1.0.0",
                "mcp.nimbletools.dev/category": "testing",
            },
            "annotations": {
                "mcp.nimbletools.dev/description": "Echo server for testing",
                "mcp.nimbletools.dev/tags": "test,echo",
            },
            "creationTimestamp": "2025-08-25T10:05:00Z",
        },
        "spec": {
            "deployment": {"type": "http"},
            "container": {"image": "echo:latest", "port": 8000},
            "capabilities": {
                "tools": [{"name": "echo", "description": "Echo text back"}],
                "resources": [],
                "prompts": []
            },
            "replicas": 1,
            "resources": {
                "requests": {"cpu": "50m", "memory": "128Mi"},
                "limits": {"cpu": "200m", "memory": "256Mi"},
            },
        },
        "status": {
            "phase": "Running",
            "replicas": 1,
            "readyReplicas": 1,
            "lastUpdated": "2025-08-25T10:10:00Z",
        },
    }


class TestRegistryServersEndpoint:
    """Test registry servers endpoint specifically - to prevent regression."""

    @pytest.mark.asyncio
    async def test_list_registry_servers_returns_actual_servers_not_empty_list(self):
        """
        Regression test: Ensure servers endpoint returns actual servers from ConfigMap,
        not an empty list with non-zero total count.
        """
        # Mock registry data with active servers
        registry_data = {
            "servers": [
                {
                    "name": "echo-server",
                    "version": "1.0.0",
                    "status": "active",
                    "meta": {"description": "Test echo server", "category": "test"},
                    "deployment": {"type": "http"},
                    "container": {"image": "echo:latest", "port": 8000},
                    "capabilities": {
                        "tools": [],
                        "resources": [],
                        "prompts": []
                    }
                }
            ]
        }

        # Mock ConfigMap with registry data
        mock_configmap = Mock()
        mock_configmap.data = {"registry.yaml": yaml.dump(registry_data)}

        # Mock authenticated user
        mock_user = UserContext(user_id="test-user", email="test@example.com", role="admin")
        mock_auth_context = AuthenticatedRequest(auth_type=AuthType.JWT, authenticated=True, user=mock_user)

        with patch("nimbletools_control_plane.routes.registry.get_user_registry_namespaces") as mock_get_namespaces:
            with patch("nimbletools_control_plane.routes.registry.client.CoreV1Api") as mock_core_api:
                # Mock registry namespace
                mock_get_namespaces.return_value = [{
                    "name": "registry-test",
                    "registry_name": "test-registry",
                    "registry_url": "https://example.com/registry.yaml"
                }]

                # Mock ConfigMap read
                mock_core_api.return_value.read_namespaced_config_map.return_value = mock_configmap

                # Create mock request
                mock_request = Mock()

                # Call the endpoint
                result = await list_registry_servers(mock_request, mock_auth_context)

                # Verify the fix: servers should contain actual server data, not be empty
                assert len(result.servers) == 1, "Should return actual servers, not empty list"
                assert result.total == 1
                assert len(result.registries) == 1

                # Verify server details
                server = result.servers[0]
                assert server.id == "echo-server"
                assert server.name == "Test echo server"
                assert server.registry == "test-registry"
                assert server.namespace == "registry-test"
                assert server.status == "available"


@pytest.mark.skip(reason="Temporarily disabled - needs K8s mocking fixes after model refactoring")
class TestRegistryRouter:
    """Test cases for registry router endpoints."""

    def test_create_registry_success(
        self,
        client: TestClient,
        mock_k8s_config,
        mock_auth_provider,
        sample_registry_data,
    ):
        """Test successful registry creation."""
        with patch(
            "nimbletools_control_plane.routes.registry.registry_client"
        ) as mock_client:
            with patch(
                "nimbletools_control_plane.routes.registry.k8s_core"
            ) as mock_k8s_core:
                with patch(
                    "nimbletools_control_plane.routes.registry.k8s_custom"
                ) as mock_k8s_custom:
                    # Mock registry client
                    mock_client.fetch_registry = AsyncMock(
                        return_value=sample_registry_data
                    )
                    mock_client.get_registry_info.return_value = {
                        "name": "community-servers",
                        "version": "2.0.0",
                        "total_servers": 1,
                        "active_servers": 1,
                    }
                    mock_client.get_active_servers.return_value = sample_registry_data[
                        "servers"
                    ]
                    mock_client.convert_to_mcpservice.return_value = {
                        "apiVersion": "mcp.nimbletools.dev/v1",
                        "kind": "MCPService",
                        "metadata": {
                            "name": "echo",
                            "namespace": "registry-community-servers",
                        },
                        "spec": {},
                    }

                    # Mock Kubernetes API calls
                    mock_k8s_core.read_namespace.side_effect = ApiException(status=404)
                    mock_k8s_core.create_namespace.return_value = None
                    mock_k8s_custom.get_namespaced_custom_object.side_effect = (
                        ApiException(status=404)
                    )
                    mock_k8s_custom.create_namespaced_custom_object.return_value = None

                    # Make request
                    response = client.post(
                        "/v1/registry",
                        json={"registry_url": "https://example.com/registry.yaml"},
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["registry_name"] == "community-servers"
                    assert data["registry_version"] == "2.0.0"
                    assert data["namespace"] == "registry-community-servers"
                    assert data["services_created"] == 1
                    assert "echo" in data["services"]

    def test_create_registry_with_namespace_override(
        self,
        client: TestClient,
        mock_k8s_config,
        mock_auth_provider,
        sample_registry_data,
    ):
        """Test registry creation with custom namespace."""
        with patch(
            "nimbletools_control_plane.routes.registry.registry_client"
        ) as mock_client:
            with patch(
                "nimbletools_control_plane.routes.registry.k8s_core"
            ) as mock_k8s_core:
                with patch(
                    "nimbletools_control_plane.routes.registry.k8s_custom"
                ) as mock_k8s_custom:
                    # Setup mocks
                    mock_client.fetch_registry = AsyncMock(
                        return_value=sample_registry_data
                    )
                    mock_client.get_registry_info.return_value = {
                        "name": "community-servers",
                        "version": "2.0.0",
                    }
                    mock_client.get_active_servers.return_value = sample_registry_data[
                        "servers"
                    ]
                    mock_client.convert_to_mcpservice.return_value = {
                        "metadata": {"name": "echo"},
                        "spec": {},
                    }

                    mock_k8s_core.read_namespace.side_effect = ApiException(status=404)
                    mock_k8s_core.create_namespace.return_value = None
                    mock_k8s_custom.get_namespaced_custom_object.side_effect = (
                        ApiException(status=404)
                    )
                    mock_k8s_custom.create_namespaced_custom_object.return_value = None

                    # Make request with namespace override
                    response = client.post(
                        "/v1/registry",
                        json={
                            "registry_url": "https://example.com/registry.yaml",
                            "namespace_override": "custom-namespace",
                        },
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["namespace"] == "custom-namespace"

    def test_create_registry_fetch_error(
        self, client: TestClient, mock_k8s_config, mock_auth_provider
    ):
        """Test registry creation with fetch error."""
        with patch(
            "nimbletools_control_plane.routes.registry.registry_client"
        ) as mock_client:
            mock_client.fetch_registry = AsyncMock(
                side_effect=Exception("Failed to fetch registry")
            )

            response = client.post(
                "/v1/registry",
                json={"registry_url": "https://invalid-url.com/registry.yaml"},
            )

            assert response.status_code == 500
            assert "Failed to fetch registry" in response.json()["detail"]

    def test_list_registries_success(
        self,
        client: TestClient,
        mock_k8s_config,
        mock_auth_provider,
        mock_k8s_namespace,
    ):
        """Test successful registry listing."""
        with patch(
            "nimbletools_control_plane.routes.registry.k8s_core"
        ) as mock_k8s_core:
            with patch(
                "nimbletools_control_plane.routes.registry.k8s_custom"
            ) as mock_k8s_custom:
                # Mock namespace list
                mock_namespaces = Mock()
                mock_namespaces.items = [mock_k8s_namespace]
                mock_k8s_core.list_namespace.return_value = mock_namespaces
                mock_k8s_core.read_namespace.return_value = mock_k8s_namespace

                # Mock MCPServices list
                mock_mcpservices = {"items": [{"metadata": {"name": "echo"}}]}
                mock_k8s_custom.list_namespaced_custom_object.return_value = (
                    mock_mcpservices
                )

                response = client.get("/v1/registry")

                assert response.status_code == 200
                data = response.json()
                assert data["total"] == 1
                assert data["total_servers"] == 1
                assert data["owner"] == "test-user"
                assert len(data["registries"]) == 1
                assert data["registries"][0]["name"] == "community-servers"
                assert (
                    data["registries"][0]["namespace"] == "registry-community-servers"
                )

    def test_list_registries_empty(
        self, client: TestClient, mock_k8s_config, mock_auth_provider
    ):
        """Test listing registries when user has none."""
        with patch(
            "nimbletools_control_plane.routes.registry.k8s_core"
        ) as mock_k8s_core:
            mock_namespaces = Mock()
            mock_namespaces.items = []
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            response = client.get("/v1/registry")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0
            assert data["total_servers"] == 0
            assert len(data["registries"]) == 0

    def test_list_registry_servers_success(
        self,
        client: TestClient,
        mock_k8s_config,
        mock_auth_provider,
        mock_k8s_namespace,
        mock_mcpservice,
    ):
        """Test successful registry servers listing."""
        with patch(
            "nimbletools_control_plane.routes.registry.k8s_core"
        ) as mock_k8s_core:
            with patch(
                "nimbletools_control_plane.routes.registry.k8s_custom"
            ) as mock_k8s_custom:
                # Mock namespace list
                mock_namespaces = Mock()
                mock_namespaces.items = [mock_k8s_namespace]
                mock_k8s_core.list_namespace.return_value = mock_namespaces

                # Mock MCPServices list
                mock_mcpservices = {"items": [mock_mcpservice]}
                mock_k8s_custom.list_namespaced_custom_object.return_value = (
                    mock_mcpservices
                )

                response = client.get("/v1/registry/servers")

                assert response.status_code == 200
                data = response.json()
                assert data["total"] == 1
                assert data["owner"] == "test-user"
                assert len(data["servers"]) == 1
                assert len(data["registries"]) == 1

                # Check server details
                server = data["servers"][0]
                assert server["id"] == "echo"
                assert server["registry"] == "community-servers"
                assert server["namespace"] == "registry-community-servers"
                assert server["status"] == "running"

    def test_get_registry_server_success(
        self,
        client: TestClient,
        mock_k8s_config,
        mock_auth_provider,
        mock_k8s_namespace,
        mock_mcpservice,
    ):
        """Test successful individual server retrieval."""
        with patch(
            "nimbletools_control_plane.routes.registry.k8s_core"
        ) as mock_k8s_core:
            with patch(
                "nimbletools_control_plane.routes.registry.k8s_custom"
            ) as mock_k8s_custom:
                # Mock namespace list
                mock_namespaces = Mock()
                mock_namespaces.items = [mock_k8s_namespace]
                mock_k8s_core.list_namespace.return_value = mock_namespaces

                # Mock MCPService get
                mock_k8s_custom.get_namespaced_custom_object.return_value = (
                    mock_mcpservice
                )

                response = client.get("/v1/registry/servers/echo")

                assert response.status_code == 200
                data = response.json()
                assert data["id"] == "echo"
                assert data["registry"] == "community-servers"
                assert data["status"] == "running"
                assert "requirements" in data
                assert "limits" in data

    def test_get_registry_server_not_found(
        self, client: TestClient, mock_k8s_config, mock_auth_provider
    ):
        """Test server retrieval when server doesn't exist."""
        with patch(
            "nimbletools_control_plane.routes.registry.k8s_core"
        ) as mock_k8s_core:
            with patch("nimbletools_control_plane.routes.registry.k8s_custom"):
                # Mock empty namespace list
                mock_namespaces = Mock()
                mock_namespaces.items = []
                mock_k8s_core.list_namespace.return_value = mock_namespaces

                response = client.get("/v1/registry/servers/nonexistent")

                assert response.status_code == 404
                assert (
                    "not found in any of your registries" in response.json()["detail"]
                )

    def test_get_registry_info_success(
        self,
        client: TestClient,
        mock_k8s_config,
        mock_auth_provider,
        sample_registry_data,
    ):
        """Test successful registry info retrieval."""
        with patch(
            "nimbletools_control_plane.routes.registry.registry_client"
        ) as mock_client:
            mock_client.fetch_registry = AsyncMock(return_value=sample_registry_data)
            mock_client.get_registry_info.return_value = {
                "name": "community-servers",
                "version": "2.0.0",
                "last_updated": "2025-08-25",
                "total_servers": 1,
                "active_servers": 1,
            }

            response = client.get(
                "/v1/registry/info?registry_url=https://example.com/registry.yaml"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "community-servers"
            assert data["version"] == "2.0.0"
            assert data["url"] == "https://example.com/registry.yaml"
            assert data["total_servers"] == 1
            assert data["active_servers"] == 1

    def test_get_registry_info_fetch_error(
        self, client: TestClient, mock_k8s_config, mock_auth_provider
    ):
        """Test registry info with fetch error."""
        with patch(
            "nimbletools_control_plane.routes.registry.registry_client"
        ) as mock_client:
            mock_client.fetch_registry = AsyncMock(
                side_effect=Exception("Fetch failed")
            )

            response = client.get(
                "/v1/registry/info?registry_url=https://invalid.com/registry.yaml"
            )

            assert response.status_code == 500
            assert "Fetch failed" in response.json()["detail"]


class TestRegistryHelperFunctions:
    """Test helper functions in registry router."""

    def test_sanitize_namespace_name(self):
        """Test namespace name sanitization."""

        # Test basic sanitization
        assert (
            _sanitize_namespace_name("Community Servers")
            == "registry-community-servers"
        )

        # Test special characters
        assert _sanitize_namespace_name("test@#$%servers") == "registry-test----servers"

        # Test length limiting
        long_name = "a" * 100
        result = _sanitize_namespace_name(long_name)
        assert len(result) <= 63
        assert result.startswith("registry-")

        # Test leading dash removal
        assert _sanitize_namespace_name("-test") == "registry-test"

    @pytest.mark.asyncio
    async def test_create_namespace_success(self):
        """Test successful namespace creation."""

        with patch(
            "nimbletools_control_plane.routes.registry.client.CoreV1Api"
        ) as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core
            mock_k8s_core.read_namespace.side_effect = ApiException(status=404)
            mock_k8s_core.create_namespace.return_value = None

            await _create_namespace(
                "test-ns", "test-registry", "https://example.com", "test-user"
            )

            mock_k8s_core.create_namespace.assert_called_once()
            call_args = mock_k8s_core.create_namespace.call_args[1]["body"]

            assert call_args["metadata"]["name"] == "test-ns"
            assert (
                call_args["metadata"]["labels"]["mcp.nimbletools.dev/owner"]
                == "test-user"
            )
            assert (
                call_args["metadata"]["labels"]["mcp.nimbletools.dev/registry-name"]
                == "test-registry"
            )
            assert (
                call_args["metadata"]["annotations"]["mcp.nimbletools.dev/registry-url"]
                == "https://example.com"
            )

    @pytest.mark.asyncio
    async def test_create_namespace_already_exists(self):
        """Test namespace creation when namespace already exists."""

        with patch(
            "nimbletools_control_plane.routes.registry.client.CoreV1Api"
        ) as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core
            mock_k8s_core.read_namespace.return_value = Mock()  # Namespace exists

            await _create_namespace(
                "existing-ns", "test-registry", "https://example.com", "test-user"
            )

            # Should not attempt to create
            mock_k8s_core.create_namespace.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_mcpservice_success(self):
        """Test successful MCPService creation."""

        mcpservice = {"metadata": {"name": "test-service"}, "spec": {}}

        with patch(
            "nimbletools_control_plane.routes.registry.client.CustomObjectsApi"
        ) as mock_k8s_custom_class:
            mock_k8s_custom = Mock()
            mock_k8s_custom_class.return_value = mock_k8s_custom
            mock_k8s_custom.get_namespaced_custom_object.side_effect = ApiException(
                status=404
            )
            mock_k8s_custom.create_namespaced_custom_object.return_value = None

            await _create_mcpservice(mcpservice, "test-ns")

            mock_k8s_custom.create_namespaced_custom_object.assert_called_once()
            call_args = mock_k8s_custom.create_namespaced_custom_object.call_args[1]
            assert call_args["namespace"] == "test-ns"
            assert call_args["body"] == mcpservice

    @pytest.mark.asyncio
    async def test_create_mcpservice_already_exists(self):
        """Test MCPService creation when service already exists."""

        mcpservice = {"metadata": {"name": "existing-service"}, "spec": {}}

        with patch(
            "nimbletools_control_plane.routes.registry.client.CustomObjectsApi"
        ) as mock_k8s_custom_class:
            mock_k8s_custom = Mock()
            mock_k8s_custom_class.return_value = mock_k8s_custom
            mock_k8s_custom.get_namespaced_custom_object.return_value = (
                Mock()
            )  # Service exists

            await _create_mcpservice(mcpservice, "test-ns")

            # Should not attempt to create
            mock_k8s_custom.create_namespaced_custom_object.assert_not_called()


@pytest.mark.skip(reason="Temporarily disabled - needs K8s mocking fixes after model refactoring")
class TestServerDeploymentFromRegistry:
    """Test server deployment from registry functionality."""

    @pytest.fixture
    def workspace_id(self):
        """Sample workspace ID."""
        return "123e4567-e89b-12d3-a456-426614174000"

    @pytest.fixture
    def registry_mcpservice(self):
        """Sample MCPService from registry namespace."""
        return {
            "metadata": {
                "name": "echo",
                "namespace": "registry-community-servers",
                "labels": {
                    "mcp.nimbletools.dev/service": "true",
                    "mcp.nimbletools.dev/version": "1.0.0",
                    "mcp.nimbletools.dev/category": "testing",
                },
                "annotations": {
                    "mcp.nimbletools.dev/description": "Echo server for testing",
                    "mcp.nimbletools.dev/tags": "test,echo",
                },
            },
            "spec": {
                "deployment": {"type": "http"},
                "container": {"image": "nimbletools/mcp-echo:latest", "port": 8000},
                "capabilities": {
                "tools": [{"name": "echo", "description": "Echo text back"}],
                "resources": [],
                "prompts": []
            },
                "replicas": 1,
                "environment": {"LOG_LEVEL": "info"},
                "resources": {
                    "requests": {"cpu": "50m", "memory": "128Mi"},
                    "limits": {"cpu": "200m", "memory": "256Mi"},
                },
            },
        }

    def test_deploy_server_from_registry_success(
        self,
        client: TestClient,
        mock_k8s_config,
        mock_auth_provider,
        workspace_id,
        registry_mcpservice,
        mock_k8s_namespace,
    ):
        """Test successful server deployment from registry."""
        with patch(
            "nimbletools_control_plane.k8s_utils.get_user_registry_namespaces"
        ) as mock_get_namespaces:
            with patch(
                "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
            ) as mock_k8s_custom_class:
                with patch(
                    "nimbletools_control_plane.routes.servers.create_workspace_access_validator"
                ):
                    # Mock registry namespaces
                    mock_get_namespaces.return_value = [
                        {
                            "name": "registry-community-servers",
                            "registry_name": "community-servers",
                        }
                    ]

                    # Mock Kubernetes API
                    mock_k8s_custom = Mock()
                    mock_k8s_custom_class.return_value = mock_k8s_custom

                    # First call finds server in registry, second call creates in workspace
                    mock_k8s_custom.get_namespaced_custom_object.side_effect = [
                        registry_mcpservice,  # Found in registry
                    ]
                    mock_k8s_custom.create_namespaced_custom_object.return_value = None

                    # Mock workspace access validation
                    with patch(
                        "nimbletools_control_plane.routes.servers.create_workspace_access_validator"
                    ) as mock_validator:
                        mock_validator.return_value = lambda: f"ws-{workspace_id}"

                        response = client.post(
                            f"/v1/workspaces/{workspace_id}/servers",
                            json={"server_id": "echo", "replicas": 2},
                        )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["server_id"] == "echo"
                    assert data["workspace_id"] == workspace_id
                    assert data["status"] == "deployed"

                    # Verify the MCPService was created with registry spec
                    create_call = (
                        mock_k8s_custom.create_namespaced_custom_object.call_args[1]
                    )
                    created_mcpservice = create_call["body"]

                    # Should use registry spec as base
                    assert (
                        created_mcpservice["spec"]["container"]["image"]
                        == "nimbletools/mcp-echo:latest"
                    )
                    assert created_mcpservice["spec"]["deployment"]["type"] == "http"
                    assert created_mcpservice["spec"]["tools"][0]["name"] == "echo"

                    # Should apply overrides
                    assert created_mcpservice["spec"]["replicas"] == 2

                    # Should merge environment variables
                    assert (
                        created_mcpservice["spec"]["environment"]["LOG_LEVEL"] == "info"
                    )

                    # Should have proper labels
                    assert (
                        created_mcpservice["metadata"]["labels"][
                            "mcp.nimbletools.dev/workspace"
                        ]
                        == workspace_id
                    )
                    assert (
                        created_mcpservice["metadata"]["labels"][
                            "mcp.nimbletools.dev/source-registry"
                        ]
                        == "community-servers"
                    )

    def test_deploy_server_not_found_in_registry(
        self, client: TestClient, mock_k8s_config, mock_auth_provider, workspace_id
    ):
        """Test server deployment when server not found in any registry."""
        with patch(
            "nimbletools_control_plane.k8s_utils.get_user_registry_namespaces"
        ) as mock_get_namespaces:
            with patch(
                "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
            ) as mock_k8s_custom_class:
                with patch(
                    "nimbletools_control_plane.routes.servers.create_workspace_access_validator"
                ):
                    # Mock registry namespaces
                    mock_get_namespaces.return_value = [
                        {
                            "name": "registry-community-servers",
                            "registry_name": "community-servers",
                        }
                    ]

                    # Mock Kubernetes API - server not found
                    mock_k8s_custom = Mock()
                    mock_k8s_custom_class.return_value = mock_k8s_custom
                    mock_k8s_custom.get_namespaced_custom_object.side_effect = (
                        ApiException(status=404)
                    )

                    with patch(
                        "nimbletools_control_plane.routes.servers.create_workspace_access_validator"
                    ) as mock_validator:
                        mock_validator.return_value = lambda: f"ws-{workspace_id}"

                        response = client.post(
                            f"/v1/workspaces/{workspace_id}/servers",
                            json={"server_id": "nonexistent"},
                        )

                    assert response.status_code == 404
                    assert (
                        "not found in any of your registries"
                        in response.json()["detail"]
                    )
                    assert "ntcli registry list-servers" in response.json()["detail"]

    def test_deploy_server_no_registries(
        self, client: TestClient, mock_k8s_config, mock_auth_provider, workspace_id
    ):
        """Test server deployment when user has no registries."""
        with patch(
            "nimbletools_control_plane.k8s_utils.get_user_registry_namespaces"
        ) as mock_get_namespaces:
            with patch(
                "nimbletools_control_plane.routes.servers.create_workspace_access_validator"
            ):
                # Mock empty registry namespaces
                mock_get_namespaces.return_value = []

                with patch(
                    "nimbletools_control_plane.routes.servers.create_workspace_access_validator"
                ) as mock_validator:
                    mock_validator.return_value = lambda: f"ws-{workspace_id}"

                    response = client.post(
                        f"/v1/workspaces/{workspace_id}/servers",
                        json={"server_id": "echo"},
                    )

                assert response.status_code == 404
                assert (
                    "not found in any of your registries" in response.json()["detail"]
                )

    def test_deploy_server_with_environment_override(
        self,
        client: TestClient,
        mock_k8s_config,
        mock_auth_provider,
        workspace_id,
        registry_mcpservice,
        mock_k8s_namespace,
    ):
        """Test server deployment with environment variable overrides."""
        with patch(
            "nimbletools_control_plane.k8s_utils.get_user_registry_namespaces"
        ) as mock_get_namespaces:
            with patch(
                "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
            ) as mock_k8s_custom_class:
                with patch(
                    "nimbletools_control_plane.routes.servers.create_workspace_access_validator"
                ):
                    mock_get_namespaces.return_value = [
                        {
                            "name": "registry-community-servers",
                            "registry_name": "community-servers",
                        }
                    ]

                    mock_k8s_custom = Mock()
                    mock_k8s_custom_class.return_value = mock_k8s_custom
                    mock_k8s_custom.get_namespaced_custom_object.return_value = (
                        registry_mcpservice
                    )
                    mock_k8s_custom.create_namespaced_custom_object.return_value = None

                    with patch(
                        "nimbletools_control_plane.routes.servers.create_workspace_access_validator"
                    ) as mock_validator:
                        mock_validator.return_value = lambda: f"ws-{workspace_id}"

                        response = client.post(
                            f"/v1/workspaces/{workspace_id}/servers",
                            json={
                                "server_id": "echo",
                                "replicas": 3,
                                "environment": {
                                    "LOG_LEVEL": "debug",  # Override existing
                                    "NEW_VAR": "value",  # Add new
                                },
                            },
                        )

                    assert response.status_code == 200

                    # Verify environment merging
                    create_call = (
                        mock_k8s_custom.create_namespaced_custom_object.call_args[1]
                    )
                    created_mcpservice = create_call["body"]
                    env = created_mcpservice["spec"]["environment"]

                    assert env["LOG_LEVEL"] == "debug"  # Overridden
                    assert env["NEW_VAR"] == "value"  # Added
                    assert created_mcpservice["spec"]["replicas"] == 3

    def test_deploy_server_kubernetes_error(
        self,
        client: TestClient,
        mock_k8s_config,
        mock_auth_provider,
        workspace_id,
        registry_mcpservice,
    ):
        """Test server deployment with Kubernetes API error."""
        with patch(
            "nimbletools_control_plane.k8s_utils.get_user_registry_namespaces"
        ) as mock_get_namespaces:
            with patch(
                "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
            ) as mock_k8s_custom_class:
                with patch(
                    "nimbletools_control_plane.routes.servers.create_workspace_access_validator"
                ):
                    mock_get_namespaces.return_value = [
                        {
                            "name": "registry-community-servers",
                            "registry_name": "community-servers",
                        }
                    ]

                    mock_k8s_custom = Mock()
                    mock_k8s_custom_class.return_value = mock_k8s_custom
                    mock_k8s_custom.get_namespaced_custom_object.return_value = (
                        registry_mcpservice
                    )
                    mock_k8s_custom.create_namespaced_custom_object.side_effect = (
                        ApiException(status=403, reason="Forbidden")
                    )

                    with patch(
                        "nimbletools_control_plane.routes.servers.create_workspace_access_validator"
                    ) as mock_validator:
                        mock_validator.return_value = lambda: f"ws-{workspace_id}"

                        response = client.post(
                            f"/v1/workspaces/{workspace_id}/servers",
                            json={"server_id": "echo"},
                        )

                    assert response.status_code == 500
                    # Should contain the Kubernetes API error
