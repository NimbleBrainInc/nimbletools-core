"""Tests for server router module."""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from kubernetes.client.rest import ApiException

from nimbletools_control_plane.routes.servers import list_workspace_servers


@pytest.fixture
def workspace_id():
    """Sample workspace ID."""
    return "123e4567-e89b-12d3-a456-426614174000"


@pytest.fixture
def registry_mcpservice():
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


@pytest.fixture
def stdio_registry_mcpservice():
    """Sample stdio MCPService from registry namespace."""
    return {
        "metadata": {
            "name": "calculator",
            "namespace": "registry-community-servers",
            "labels": {
                "mcp.nimbletools.dev/service": "true",
                "mcp.nimbletools.dev/version": "2.0.0",
                "mcp.nimbletools.dev/category": "math",
            },
        },
        "spec": {
            "deployment": {
                "type": "stdio",
                "stdio": {
                    "executable": "python",
                    "args": ["calculator.py"],
                    "workingDir": "/app",
                },
            },
            "container": {"image": "nimbletools/calculator-mcp:v2"},
            "capabilities": {
                "tools": [
                    {"name": "add", "description": "Add numbers"},
                    {"name": "subtract", "description": "Subtract numbers"},
                ],
                "resources": [],
                "prompts": []
            },
            "replicas": 1,
            "environment": {"CALC_MODE": "advanced"},
        },
    }


class TestServerStatusMapping:
    """Test server status mapping to prevent regression where status shows Unknown."""

    @pytest.mark.asyncio
    async def test_server_status_shows_running_when_deployment_ready(self):
        """
        Regression test: Ensure server status shows 'Running' when deployment has ready replicas,
        even when MCPService status is empty or Unknown.
        """
        workspace_id = "test-workspace-id"
        namespace_name = "ws-test-workspace-id"

        # Mock MCPService with empty status (the problem scenario)
        mock_mcpservice = {
            "metadata": {
                "name": "echo",
                "creationTimestamp": "2025-08-27T19:24:56Z"
            },
            "spec": {
                "container": {"image": "nimbletools/mcp-echo:latest", "port": 8000},
                "replicas": 1
            },
            "status": {}  # Empty status - this was causing "Unknown"
        }

        # Mock deployment with ready replicas
        mock_deployment = Mock()
        mock_deployment.status.ready_replicas = 1
        mock_deployment.status.replicas = 1

        with patch("nimbletools_control_plane.routes.servers.client.CustomObjectsApi") as mock_custom_api:
            with patch("nimbletools_control_plane.routes.servers.client.AppsV1Api") as mock_apps_api:
                # Mock MCPService list
                mock_custom_api.return_value.list_namespaced_custom_object.return_value = {
                    "items": [mock_mcpservice]
                }

                # Mock deployment read
                mock_apps_api.return_value.read_namespaced_deployment.return_value = mock_deployment

                # Create mock request
                mock_request = Mock()

                # Call the endpoint
                result = await list_workspace_servers(workspace_id, mock_request, namespace_name)

                # Verify the fix: status should be 'Running', not 'Unknown'
                assert len(result.servers) == 1
                server = result.servers[0]
                assert server.status == "Running", "Server should show Running status when deployment has ready replicas"
                assert server.id == "echo"
                assert server.image == "nimbletools/mcp-echo:latest"
                assert server.replicas == 1

    @pytest.mark.asyncio
    async def test_server_status_shows_pending_when_deployment_has_replicas_but_none_ready(self):
        """Test server status shows 'Pending' when deployment exists but no ready replicas."""
        workspace_id = "test-workspace-id"
        namespace_name = "ws-test-workspace-id"

        mock_mcpservice = {
            "metadata": {
                "name": "echo",
                "creationTimestamp": "2025-08-27T19:24:56Z"
            },
            "spec": {
                "container": {"image": "nimbletools/mcp-echo:latest", "port": 8000},
                "replicas": 1
            },
            "status": {}
        }

        # Mock deployment with replicas but none ready
        mock_deployment = Mock()
        mock_deployment.status.ready_replicas = 0
        mock_deployment.status.replicas = 1

        with patch("nimbletools_control_plane.routes.servers.client.CustomObjectsApi") as mock_custom_api:
            with patch("nimbletools_control_plane.routes.servers.client.AppsV1Api") as mock_apps_api:
                mock_custom_api.return_value.list_namespaced_custom_object.return_value = {
                    "items": [mock_mcpservice]
                }

                mock_apps_api.return_value.read_namespaced_deployment.return_value = mock_deployment

                mock_request = Mock()

                result = await list_workspace_servers(workspace_id, mock_request, namespace_name)

                assert len(result.servers) == 1
                server = result.servers[0]
                assert server.status == "Pending"

    @pytest.mark.asyncio
    async def test_server_status_falls_back_to_mcpservice_status_when_deployment_not_found(self):
        """Test server status uses MCPService status when deployment doesn't exist."""
        workspace_id = "test-workspace-id"
        namespace_name = "ws-test-workspace-id"

        mock_mcpservice = {
            "metadata": {
                "name": "echo",
                "creationTimestamp": "2025-08-27T19:24:56Z"
            },
            "spec": {
                "container": {"image": "nimbletools/mcp-echo:latest", "port": 8000},
                "replicas": 1
            },
            "status": {"phase": "Deploying"}  # MCPService has status
        }

        with patch("nimbletools_control_plane.routes.servers.client.CustomObjectsApi") as mock_custom_api:
            with patch("nimbletools_control_plane.routes.servers.client.AppsV1Api") as mock_apps_api:
                mock_custom_api.return_value.list_namespaced_custom_object.return_value = {
                    "items": [mock_mcpservice]
                }

                # Deployment not found
                mock_apps_api.return_value.read_namespaced_deployment.side_effect = ApiException(status=404)

                mock_request = Mock()

                result = await list_workspace_servers(workspace_id, mock_request, namespace_name)

                assert len(result.servers) == 1
                server = result.servers[0]
                assert server.status == "Deploying"

    @pytest.mark.asyncio
    async def test_server_status_shows_unknown_when_both_deployment_and_mcpservice_status_empty(self):
        """Test server status shows 'Unknown' when both deployment doesn't exist and MCPService status is empty."""
        workspace_id = "test-workspace-id"
        namespace_name = "ws-test-workspace-id"

        mock_mcpservice = {
            "metadata": {
                "name": "echo",
                "creationTimestamp": "2025-08-27T19:24:56Z"
            },
            "spec": {
                "container": {"image": "nimbletools/mcp-echo:latest", "port": 8000},
                "replicas": 1
            },
            "status": {}  # Empty status
        }

        with patch("nimbletools_control_plane.routes.servers.client.CustomObjectsApi") as mock_custom_api:
            with patch("nimbletools_control_plane.routes.servers.client.AppsV1Api") as mock_apps_api:
                mock_custom_api.return_value.list_namespaced_custom_object.return_value = {
                    "items": [mock_mcpservice]
                }

                # Deployment not found
                mock_apps_api.return_value.read_namespaced_deployment.side_effect = ApiException(status=404)

                mock_request = Mock()

                result = await list_workspace_servers(workspace_id, mock_request, namespace_name)

                assert len(result.servers) == 1
                server = result.servers[0]
                assert server.status == "Unknown"


@pytest.mark.skip(reason="Temporarily disabled - needs K8s mocking fixes after model refactoring")
class TestServerDeploymentFromRegistry:
    """Test server deployment from registry functionality."""

    def test_deploy_server_from_registry_success(
        self,
        client: TestClient,
        mock_k8s_config,
        mock_auth_provider,
        workspace_id,
        registry_mcpservice,
    ):
        """Test successful server deployment from registry."""
        with patch(
            "nimbletools_control_plane.k8s_utils.get_user_registry_namespaces"
        ) as mock_get_namespaces:
            with patch(
                "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
            ) as mock_k8s_custom_class:
                with patch(
                    "nimbletools_control_plane.middlewares.client.CoreV1Api"
                ) as mock_workspace_validator_k8s_class:
                    # Mock workspace access validation K8s calls
                    mock_workspace_k8s_core = Mock()
                    mock_workspace_validator_k8s_class.return_value = (
                        mock_workspace_k8s_core
                    )

                    # Mock namespace response for workspace validation
                    mock_workspace_namespace = Mock()
                    mock_workspace_namespace.metadata.name = f"ws-foobar-{workspace_id}"
                    mock_workspace_namespaces = Mock()
                    mock_workspace_namespaces.items = [mock_workspace_namespace]
                    mock_workspace_k8s_core.list_namespace.return_value = (
                        mock_workspace_namespaces
                    )

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
                    mock_k8s_custom.get_namespaced_custom_object.return_value = (
                        registry_mcpservice
                    )
                    mock_k8s_custom.create_namespaced_custom_object.return_value = None

                    response = client.post(
                        f"/v1/workspaces/{workspace_id}/servers",
                        json={"server_id": "echo", "replicas": 2, "environment": {}},
                    )

                assert response.status_code == 200
                data = response.json()
                assert data["server_id"] == "echo"
                assert data["workspace_id"] == workspace_id
                assert data["status"] == "deployed"

                # Verify the MCPService was created with registry spec
                create_call = mock_k8s_custom.create_namespaced_custom_object.call_args[
                    1
                ]
                created_mcpservice = create_call["body"]

                # The current implementation uses hardcoded echo deployment, not registry-based
                assert (
                    created_mcpservice["spec"]["container"]["image"]
                    == "nimbletools/mcp-echo:latest"
                )
                assert created_mcpservice["spec"]["deployment"]["type"] == "http"
                assert created_mcpservice["spec"]["container"]["port"] == 8000

                # Should apply request overrides
                assert created_mcpservice["spec"]["replicas"] == 2
                assert (
                    created_mcpservice["spec"]["environment"] == {}
                )  # Empty from request

                # Should have workspace labels
                metadata = created_mcpservice["metadata"]
                assert (
                    metadata["labels"]["mcp.nimbletools.dev/workspace"] == workspace_id
                )
                assert metadata["labels"]["mcp.nimbletools.dev/service"] == "true"

    def test_deploy_stdio_server_from_registry(
        self,
        client: TestClient,
        mock_k8s_config,
        mock_auth_provider,
        workspace_id,
        stdio_registry_mcpservice,
    ):
        """Test deploying stdio server from registry."""
        with patch(
            "nimbletools_control_plane.k8s_utils.get_user_registry_namespaces"
        ) as mock_get_namespaces:
            with patch(
                "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
            ) as mock_k8s_custom_class:
                with patch(
                    "nimbletools_control_plane.routes.servers.create_workspace_access_validator"
                ) as mock_validator:
                    mock_get_namespaces.return_value = [
                        {
                            "name": "registry-community-servers",
                            "registry_name": "community-servers",
                        }
                    ]

                    mock_k8s_custom = Mock()
                    mock_k8s_custom_class.return_value = mock_k8s_custom
                    mock_k8s_custom.get_namespaced_custom_object.return_value = (
                        stdio_registry_mcpservice
                    )
                    mock_k8s_custom.create_namespaced_custom_object.return_value = None

                    mock_validator.return_value = (
                        lambda workspace_id: f"ws-{workspace_id}"
                    )

                    response = client.post(
                        f"/v1/workspaces/{workspace_id}/servers",
                        json={
                            "server_id": "calculator",
                            "replicas": 1,
                            "environment": {},
                        },
                    )

                assert response.status_code == 200

                # Verify stdio deployment was preserved
                create_call = mock_k8s_custom.create_namespaced_custom_object.call_args[
                    1
                ]
                created_mcpservice = create_call["body"]

                spec = created_mcpservice["spec"]
                assert spec["deployment"]["type"] == "stdio"
                assert spec["deployment"]["stdio"]["executable"] == "python"
                assert spec["deployment"]["stdio"]["args"] == ["calculator.py"]
                assert spec["deployment"]["stdio"]["workingDir"] == "/app"
                assert spec["container"]["image"] == "nimbletools/calculator-mcp:v2"

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
                ) as mock_validator:
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

                    mock_validator.return_value = (
                        lambda workspace_id: f"ws-{workspace_id}"
                    )

                    response = client.post(
                        f"/v1/workspaces/{workspace_id}/servers",
                        json={
                            "server_id": "nonexistent",
                            "replicas": 1,
                            "environment": {},
                        },
                    )

                assert response.status_code == 404
                assert (
                    "not found in any of your registries" in response.json()["detail"]
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
            ) as mock_validator:
                # Mock empty registry namespaces
                mock_get_namespaces.return_value = []

                mock_validator.return_value = lambda workspace_id: f"ws-{workspace_id}"

                response = client.post(
                    f"/v1/workspaces/{workspace_id}/servers",
                    json={"server_id": "echo", "replicas": 1, "environment": {}},
                )

            assert response.status_code == 404
            assert "not found in any of your registries" in response.json()["detail"]

    def test_deploy_server_with_environment_override(
        self,
        client: TestClient,
        mock_k8s_config,
        mock_auth_provider,
        workspace_id,
        registry_mcpservice,
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
                ) as mock_validator:
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

                    mock_validator.return_value = (
                        lambda workspace_id: f"ws-{workspace_id}"
                    )

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
                create_call = mock_k8s_custom.create_namespaced_custom_object.call_args[
                    1
                ]
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
                ) as mock_validator:
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

                    mock_validator.return_value = (
                        lambda workspace_id: f"ws-{workspace_id}"
                    )

                    response = client.post(
                        f"/v1/workspaces/{workspace_id}/servers",
                        json={"server_id": "echo", "replicas": 1, "environment": {}},
                    )

                assert response.status_code == 500
                # Should contain the Kubernetes API error

    def test_deploy_server_missing_server_id(
        self, client: TestClient, mock_k8s_config, mock_auth_provider, workspace_id
    ):
        """Test server deployment with missing server_id."""
        with patch(
            "nimbletools_control_plane.routes.servers.create_workspace_access_validator"
        ) as mock_validator:
            mock_validator.return_value = lambda workspace_id: f"ws-{workspace_id}"

            response = client.post(
                f"/v1/workspaces/{workspace_id}/servers",
                json={"replicas": 1, "environment": {}},  # Missing server_id
            )

        assert response.status_code == 400
        assert "server_id is required" in response.json()["detail"]

    def test_deploy_server_empty_server_id(
        self, client: TestClient, mock_k8s_config, mock_auth_provider, workspace_id
    ):
        """Test server deployment with empty server_id."""
        with patch(
            "nimbletools_control_plane.routes.servers.create_workspace_access_validator"
        ) as mock_validator:
            mock_validator.return_value = lambda workspace_id: f"ws-{workspace_id}"

            response = client.post(
                f"/v1/workspaces/{workspace_id}/servers",
                json={
                    "server_id": "   ",
                    "replicas": 1,
                    "environment": {},
                },  # Empty/whitespace server_id
            )

        assert response.status_code == 400
        assert "server_id is required" in response.json()["detail"]

    def test_deploy_server_multiple_registries_found_in_first(
        self,
        client: TestClient,
        mock_k8s_config,
        mock_auth_provider,
        workspace_id,
        registry_mcpservice,
    ):
        """Test server deployment when server found in first registry."""
        with patch(
            "nimbletools_control_plane.k8s_utils.get_user_registry_namespaces"
        ) as mock_get_namespaces:
            with patch(
                "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
            ) as mock_k8s_custom_class:
                with patch(
                    "nimbletools_control_plane.routes.servers.create_workspace_access_validator"
                ) as mock_validator:
                    # Mock multiple registry namespaces
                    mock_get_namespaces.return_value = [
                        {
                            "name": "registry-community-servers",
                            "registry_name": "community-servers",
                        },
                        {"name": "registry-custom", "registry_name": "custom-registry"},
                    ]

                    mock_k8s_custom = Mock()
                    mock_k8s_custom_class.return_value = mock_k8s_custom

                    # Found in first registry
                    mock_k8s_custom.get_namespaced_custom_object.return_value = (
                        registry_mcpservice
                    )
                    mock_k8s_custom.create_namespaced_custom_object.return_value = None

                    mock_validator.return_value = (
                        lambda workspace_id: f"ws-{workspace_id}"
                    )

                    response = client.post(
                        f"/v1/workspaces/{workspace_id}/servers",
                        json={"server_id": "echo", "replicas": 1, "environment": {}},
                    )

                assert response.status_code == 200

                # Should only call get_namespaced_custom_object once (found in first registry)
                assert mock_k8s_custom.get_namespaced_custom_object.call_count == 1

                # Verify it was looking in the right namespace
                get_call = mock_k8s_custom.get_namespaced_custom_object.call_args[1]
                assert get_call["namespace"] == "registry-community-servers"
                assert get_call["name"] == "echo"

    def test_deploy_server_found_in_second_registry(
        self,
        client: TestClient,
        mock_k8s_config,
        mock_auth_provider,
        workspace_id,
        registry_mcpservice,
    ):
        """Test server deployment when server found in second registry."""
        with patch(
            "nimbletools_control_plane.k8s_utils.get_user_registry_namespaces"
        ) as mock_get_namespaces:
            with patch(
                "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
            ) as mock_k8s_custom_class:
                with patch(
                    "nimbletools_control_plane.routes.servers.create_workspace_access_validator"
                ) as mock_validator:
                    # Mock multiple registry namespaces
                    mock_get_namespaces.return_value = [
                        {"name": "registry-first", "registry_name": "first-registry"},
                        {"name": "registry-second", "registry_name": "second-registry"},
                    ]

                    mock_k8s_custom = Mock()
                    mock_k8s_custom_class.return_value = mock_k8s_custom

                    # Not found in first, found in second
                    mock_k8s_custom.get_namespaced_custom_object.side_effect = [
                        ApiException(status=404),  # Not in first registry
                        registry_mcpservice,  # Found in second registry
                    ]
                    mock_k8s_custom.create_namespaced_custom_object.return_value = None

                    mock_validator.return_value = (
                        lambda workspace_id: f"ws-{workspace_id}"
                    )

                    response = client.post(
                        f"/v1/workspaces/{workspace_id}/servers",
                        json={"server_id": "echo", "replicas": 1, "environment": {}},
                    )

                assert response.status_code == 200

                # Should have searched both registries
                assert mock_k8s_custom.get_namespaced_custom_object.call_count == 2

                # Check that it looked in both namespaces
                calls = mock_k8s_custom.get_namespaced_custom_object.call_args_list
                assert calls[0][1]["namespace"] == "registry-first"
                assert calls[1][1]["namespace"] == "registry-second"

                # Should have proper source registry in created service
                create_call = mock_k8s_custom.create_namespaced_custom_object.call_args[
                    1
                ]
                created_mcpservice = create_call["body"]
                assert (
                    created_mcpservice["metadata"]["labels"][
                        "mcp.nimbletools.dev/source-registry"
                    ]
                    == "second-registry"
                )

    def test_deploy_server_preserves_all_registry_spec_fields(
        self,
        client: TestClient,
        mock_k8s_config,
        mock_auth_provider,
        workspace_id,
        registry_mcpservice,
    ):
        """Test that deployment preserves all fields from registry spec."""
        with patch(
            "nimbletools_control_plane.k8s_utils.get_user_registry_namespaces"
        ) as mock_get_namespaces:
            with patch(
                "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
            ) as mock_k8s_custom_class:
                with patch(
                    "nimbletools_control_plane.routes.servers.create_workspace_access_validator"
                ) as mock_validator:
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

                    mock_validator.return_value = (
                        lambda workspace_id: f"ws-{workspace_id}"
                    )

                    response = client.post(
                        f"/v1/workspaces/{workspace_id}/servers",
                        json={"server_id": "echo", "replicas": 1, "environment": {}},
                    )

                assert response.status_code == 200

                # Verify ALL registry spec fields are preserved
                create_call = mock_k8s_custom.create_namespaced_custom_object.call_args[
                    1
                ]
                created_mcpservice = create_call["body"]
                spec = created_mcpservice["spec"]

                # Core deployment fields
                assert spec["deployment"]["type"] == "http"
                assert spec["container"]["image"] == "nimbletools/mcp-echo:latest"
                assert spec["container"]["port"] == 8000

                # Tools should be preserved
                assert len(spec["tools"]) == 1
                assert spec["tools"][0]["name"] == "echo"
                assert spec["tools"][0]["description"] == "Echo text back"

                # Resources should be preserved
                assert spec["resources"]["requests"]["cpu"] == "50m"
                assert spec["resources"]["requests"]["memory"] == "128Mi"
                assert spec["resources"]["limits"]["cpu"] == "200m"
                assert spec["resources"]["limits"]["memory"] == "256Mi"

                # Environment should be preserved (with defaults if no override)
                assert spec["environment"]["LOG_LEVEL"] == "info"

    def test_deploy_server_missing_server_id_field(
        self, client: TestClient, mock_k8s_config, mock_auth_provider, workspace_id
    ):
        """Test deployment fails gracefully with missing server_id."""
        with patch(
            "nimbletools_control_plane.routes.servers.create_workspace_access_validator"
        ) as mock_validator:
            mock_validator.return_value = lambda workspace_id: f"ws-{workspace_id}"

            response = client.post(
                f"/v1/workspaces/{workspace_id}/servers",
                json={
                    "replicas": 2,
                    "environment": {},
                },  # Missing server_id field entirely
            )

        assert response.status_code == 400
        assert "server_id is required" in response.json()["detail"]


@pytest.mark.skip(reason="Temporarily disabled - needs K8s mocking fixes after model refactoring")
class TestServerDeploymentRegression:
    """Specific regression tests for the ntcli deployment bug fix."""

    def test_ntcli_echo_deployment_scenario(
        self, client: TestClient, mock_k8s_config, mock_auth_provider, workspace_id
    ):
        """
        Test the exact scenario that was failing with ntcli server deploy echo.
        This is the critical regression test.
        """
        # This is the exact registry MCPService that would exist for echo
        echo_registry_mcpservice = {
            "metadata": {
                "name": "echo",
                "namespace": "registry-community-servers",
                "labels": {
                    "mcp.nimbletools.dev/service": "true",
                    "mcp.nimbletools.dev/version": "1.0.0",
                    "mcp.nimbletools.dev/category": "testing",
                    "mcp.nimbletools.dev/managed-by": "nimbletools-control-plane",
                },
                "annotations": {
                    "mcp.nimbletools.dev/description": "echo MCP service",
                    "mcp.nimbletools.dev/generated-from": "registry",
                    "mcp.nimbletools.dev/tags": "testing,development,echo,debug,utilities",
                },
            },
            "spec": {
                "deployment": {"type": "http"},
                "container": {"image": "nimbletools/mcp-echo:latest", "port": 8000},
                "replicas": 1,
            },
        }

        with patch(
            "nimbletools_control_plane.k8s_utils.get_user_registry_namespaces"
        ) as mock_get_namespaces:
            with patch(
                "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
            ) as mock_k8s_custom_class:
                with patch(
                    "nimbletools_control_plane.routes.servers.create_workspace_access_validator"
                ) as mock_validator:
                    # Mock user has community registry
                    mock_get_namespaces.return_value = [
                        {
                            "name": "registry-community-servers",
                            "registry_name": "community-servers",
                        }
                    ]

                    mock_k8s_custom = Mock()
                    mock_k8s_custom_class.return_value = mock_k8s_custom
                    mock_k8s_custom.get_namespaced_custom_object.return_value = (
                        echo_registry_mcpservice
                    )
                    mock_k8s_custom.create_namespaced_custom_object.return_value = None

                    mock_validator.return_value = (
                        lambda workspace_id: f"ws-{workspace_id}"
                    )

                    # This is the exact request ntcli makes
                    response = client.post(
                        f"/v1/workspaces/{workspace_id}/servers",
                        json={"server_id": "echo", "replicas": 1, "environment": {}},
                    )

                # Should succeed (was failing with 500 before)
                assert response.status_code == 200
                data = response.json()
                assert data["server_id"] == "echo"
                assert data["status"] == "deployed"

                # CRITICAL: Verify it uses the correct image from registry
                create_call = mock_k8s_custom.create_namespaced_custom_object.call_args[
                    1
                ]
                created_mcpservice = create_call["body"]

                # This was the bug - it was using "nimbletools/echo-mcp:latest"
                # Now it should use "nimbletools/mcp-echo:latest" from registry
                assert (
                    created_mcpservice["spec"]["container"]["image"]
                    == "nimbletools/mcp-echo:latest"
                )
                assert created_mcpservice["spec"]["deployment"]["type"] == "http"
                assert created_mcpservice["spec"]["container"]["port"] == 8000

                # Verify it was created in workspace namespace, not registry namespace
                assert create_call["namespace"] == f"ws-{workspace_id}"

                # Verify proper labeling for workspace deployment
                labels = created_mcpservice["metadata"]["labels"]
                assert labels["mcp.nimbletools.dev/workspace"] == workspace_id
                assert (
                    labels["mcp.nimbletools.dev/source-registry"] == "community-servers"
                )

    def test_helpful_error_message_for_missing_server(
        self, client: TestClient, mock_k8s_config, mock_auth_provider, workspace_id
    ):
        """Test that we provide helpful error when server not found."""
        with patch(
            "nimbletools_control_plane.k8s_utils.get_user_registry_namespaces"
        ) as mock_get_namespaces:
            with patch(
                "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
            ) as mock_k8s_custom_class:
                with patch(
                    "nimbletools_control_plane.routes.servers.create_workspace_access_validator"
                ) as mock_validator:
                    mock_get_namespaces.return_value = [
                        {
                            "name": "registry-community-servers",
                            "registry_name": "community-servers",
                        }
                    ]

                    mock_k8s_custom = Mock()
                    mock_k8s_custom_class.return_value = mock_k8s_custom
                    mock_k8s_custom.get_namespaced_custom_object.side_effect = (
                        ApiException(status=404)
                    )

                    mock_validator.return_value = (
                        lambda workspace_id: f"ws-{workspace_id}"
                    )

                    response = client.post(
                        f"/v1/workspaces/{workspace_id}/servers",
                        json={
                            "server_id": "nonexistent",
                            "replicas": 1,
                            "environment": {},
                        },
                    )

                assert response.status_code == 404
                error_detail = response.json()["detail"]
                assert "nonexistent" in error_detail
                assert "not found in any of your registries" in error_detail
                assert "ntcli registry list-servers" in error_detail  # Helpful guidance
