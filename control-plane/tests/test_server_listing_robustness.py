"""Tests for server listing robustness when servers are in various states."""

from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException
from kubernetes.client.rest import ApiException

from nimbletools_control_plane.exceptions import KubernetesOperationError
from nimbletools_control_plane.routes.servers import list_workspace_servers


class TestServerListingRobustness:
    """Test server listing handles edge cases and doesn't crash the API."""

    @pytest.fixture
    def mock_workspace_id(self):
        """Mock workspace ID."""
        return "f33ae45a-f171-46da-b78e-2b4feca6dded"

    @pytest.fixture
    def mock_namespace_name(self):
        """Mock namespace name."""
        return "ws-test-workspace-f33ae45a-f171-46da-b78e-2b4feca6dded"

    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI request object."""
        return Mock()

    def create_mock_mcpservice(self, server_name: str, status_phase: str = "Unknown"):
        """Create a mock MCPService object."""
        return {
            "metadata": {
                "name": server_name,
                "creationTimestamp": "2024-01-01T00:00:00Z",
            },
            "spec": {
                "container": {"image": "test/server:latest"},
                "replicas": 1,
            },
            "status": {"phase": status_phase},
        }

    def create_mock_deployment(self, ready_replicas=None, total_replicas=None):
        """Create a mock Kubernetes deployment with configurable status."""
        deployment = Mock()
        deployment.status = Mock()
        deployment.status.ready_replicas = ready_replicas
        deployment.status.replicas = total_replicas
        return deployment

    @pytest.mark.asyncio
    async def test_list_servers_with_pending_server_no_deployment(
        self, mock_workspace_id, mock_namespace_name, mock_request
    ):
        """Test listing servers when deployment doesn't exist yet (server is starting)."""
        # Mock MCPService exists but deployment doesn't exist yet
        mock_mcpservices = {
            "items": [
                self.create_mock_mcpservice("echo-server", "Pending"),
            ]
        }

        with patch(
            "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
        ) as mock_custom_api:
            mock_custom_api.return_value.list_namespaced_custom_object.return_value = (
                mock_mcpservices
            )

            # Mock get_deployment_if_exists to return None (deployment doesn't exist yet)
            with patch(
                "nimbletools_control_plane.routes.servers.get_deployment_if_exists"
            ) as mock_get_deployment:
                mock_get_deployment.return_value = None

                # This should not crash and should return the server with status from MCPService
                result = await list_workspace_servers(
                    workspace_id=mock_workspace_id,
                    request=mock_request,
                    namespace_name=mock_namespace_name,
                )

                # Verify the result
                assert result.total == 1
                assert len(result.servers) == 1
                server = result.servers[0]
                assert server.id == "echo-server"
                assert server.status == "Pending"  # Should fall back to MCPService status
                assert server.workspace_id == UUID(mock_workspace_id)

    @pytest.mark.asyncio
    async def test_list_servers_with_deployment_no_ready_replicas(
        self, mock_workspace_id, mock_namespace_name, mock_request
    ):
        """Test listing servers when deployment exists but no replicas are ready (pending state)."""
        mock_mcpservices = {
            "items": [
                self.create_mock_mcpservice("echo-server", "Running"),
            ]
        }

        # Create deployment with total replicas but no ready replicas (pending state)
        mock_deployment = self.create_mock_deployment(ready_replicas=0, total_replicas=1)

        with patch(
            "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
        ) as mock_custom_api:
            mock_custom_api.return_value.list_namespaced_custom_object.return_value = (
                mock_mcpservices
            )

            with patch(
                "nimbletools_control_plane.routes.servers.get_deployment_if_exists"
            ) as mock_get_deployment:
                mock_get_deployment.return_value = mock_deployment

                result = await list_workspace_servers(
                    workspace_id=mock_workspace_id,
                    request=mock_request,
                    namespace_name=mock_namespace_name,
                )

                # Verify the result
                assert result.total == 1
                server = result.servers[0]
                assert (
                    server.status == "Pending"
                )  # Should show Pending when total > 0 but ready = 0

    @pytest.mark.asyncio
    async def test_list_servers_with_deployment_none_status(
        self, mock_workspace_id, mock_namespace_name, mock_request
    ):
        """Test listing servers when deployment exists but status is None."""
        mock_mcpservices = {
            "items": [
                self.create_mock_mcpservice("echo-server", "Starting"),
            ]
        }

        # Create deployment with None status (can happen during startup)
        mock_deployment = Mock()
        mock_deployment.status = None

        with patch(
            "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
        ) as mock_custom_api:
            mock_custom_api.return_value.list_namespaced_custom_object.return_value = (
                mock_mcpservices
            )

            with patch(
                "nimbletools_control_plane.routes.servers.get_deployment_if_exists"
            ) as mock_get_deployment:
                mock_get_deployment.return_value = mock_deployment

                result = await list_workspace_servers(
                    workspace_id=mock_workspace_id,
                    request=mock_request,
                    namespace_name=mock_namespace_name,
                )

                # Should not crash and fall back to MCPService status
                assert result.total == 1
                server = result.servers[0]
                assert server.status == "Starting"  # Should fall back to MCPService status

    @pytest.mark.asyncio
    async def test_list_servers_with_deployment_none_replicas(
        self, mock_workspace_id, mock_namespace_name, mock_request
    ):
        """Test listing servers when deployment has None replica counts."""
        mock_mcpservices = {
            "items": [
                self.create_mock_mcpservice("echo-server", "Initializing"),
            ]
        }

        # Create deployment with None replica counts (can happen during very early startup)
        mock_deployment = self.create_mock_deployment(ready_replicas=None, total_replicas=None)

        with patch(
            "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
        ) as mock_custom_api:
            mock_custom_api.return_value.list_namespaced_custom_object.return_value = (
                mock_mcpservices
            )

            with patch(
                "nimbletools_control_plane.routes.servers.get_deployment_if_exists"
            ) as mock_get_deployment:
                mock_get_deployment.return_value = mock_deployment

                result = await list_workspace_servers(
                    workspace_id=mock_workspace_id,
                    request=mock_request,
                    namespace_name=mock_namespace_name,
                )

                # Should not crash and show as Stopped (0 replicas)
                assert result.total == 1
                server = result.servers[0]
                assert server.status == "Stopped"  # ready_replicas=0, total_replicas=0 -> Stopped

    @pytest.mark.asyncio
    async def test_list_servers_with_get_deployment_exception(
        self, mock_workspace_id, mock_namespace_name, mock_request
    ):
        """Test listing servers when get_deployment_if_exists throws an exception."""
        mock_mcpservices = {
            "items": [
                self.create_mock_mcpservice("echo-server", "Error"),
            ]
        }

        with patch(
            "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
        ) as mock_custom_api:
            mock_custom_api.return_value.list_namespaced_custom_object.return_value = (
                mock_mcpservices
            )

            with patch(
                "nimbletools_control_plane.routes.servers.get_deployment_if_exists"
            ) as mock_get_deployment:
                # Simulate an unexpected error when trying to get deployment
                mock_get_deployment.side_effect = Exception(
                    "Kubernetes API temporarily unavailable"
                )

                # Should not crash the entire API call
                result = await list_workspace_servers(
                    workspace_id=mock_workspace_id,
                    request=mock_request,
                    namespace_name=mock_namespace_name,
                )

                # Should still return the server with fallback status
                assert result.total == 1
                server = result.servers[0]
                assert server.status == "Error"  # Should fall back to MCPService status

    @pytest.mark.asyncio
    async def test_list_servers_with_kubernetes_operation_error(
        self, mock_workspace_id, mock_namespace_name, mock_request
    ):
        """Test listing servers when get_deployment_if_exists throws a KubernetesOperationError (transient K8s error)."""
        mock_mcpservices = {
            "items": [
                self.create_mock_mcpservice("echo-server", "Pending"),
                self.create_mock_mcpservice("finnhub-server", "Running"),
            ]
        }

        with patch(
            "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
        ) as mock_custom_api:
            mock_custom_api.return_value.list_namespaced_custom_object.return_value = (
                mock_mcpservices
            )

            with patch(
                "nimbletools_control_plane.routes.servers.get_deployment_if_exists"
            ) as mock_get_deployment:
                # Simulate a transient Kubernetes error (e.g., timeout, connection issue)
                # This is the specific bug we're fixing - transient errors during pod startup
                api_exception = ApiException(status=503, reason="Service Temporarily Unavailable")
                mock_get_deployment.side_effect = KubernetesOperationError(
                    message="Failed to read deployment: Service Temporarily Unavailable",
                    operation="reading",
                    resource="deployment:echo-server-deployment",
                    api_exception=api_exception,
                )

                # Should not crash the entire API call - this is the key fix
                result = await list_workspace_servers(
                    workspace_id=mock_workspace_id,
                    request=mock_request,
                    namespace_name=mock_namespace_name,
                )

                # Should still return both servers with fallback statuses
                assert result.total == 2
                assert len(result.servers) == 2

                # Both servers should have their MCPService status as fallback
                servers_by_id = {s.id: s for s in result.servers}
                assert (
                    servers_by_id["echo-server"].status == "Pending"
                )  # Falls back to MCPService status
                assert (
                    servers_by_id["finnhub-server"].status == "Running"
                )  # Falls back to MCPService status

    @pytest.mark.asyncio
    async def test_list_servers_with_multiple_servers_mixed_states(
        self, mock_workspace_id, mock_namespace_name, mock_request
    ):
        """Test listing multiple servers in different states doesn't crash if one has issues."""
        mock_mcpservices = {
            "items": [
                self.create_mock_mcpservice("running-server", "Running"),
                self.create_mock_mcpservice("pending-server", "Pending"),
                self.create_mock_mcpservice("error-server", "Error"),
            ]
        }

        def mock_get_deployment_side_effect(deployment_name, namespace):
            """Mock different deployment states for different servers."""
            if "running-server" in deployment_name:
                return self.create_mock_deployment(ready_replicas=1, total_replicas=1)
            elif "pending-server" in deployment_name:
                return self.create_mock_deployment(ready_replicas=0, total_replicas=1)
            elif "error-server" in deployment_name:
                # Simulate an error for this server
                raise Exception("Deployment API error")
            return None

        with patch(
            "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
        ) as mock_custom_api:
            mock_custom_api.return_value.list_namespaced_custom_object.return_value = (
                mock_mcpservices
            )

            with patch(
                "nimbletools_control_plane.routes.servers.get_deployment_if_exists"
            ) as mock_get_deployment:
                mock_get_deployment.side_effect = mock_get_deployment_side_effect

                result = await list_workspace_servers(
                    workspace_id=mock_workspace_id,
                    request=mock_request,
                    namespace_name=mock_namespace_name,
                )

                # Should return all servers despite one having an error
                assert result.total == 3
                assert len(result.servers) == 3

                # Check each server status
                servers_by_id = {s.id: s for s in result.servers}

                assert servers_by_id["running-server"].status == "Running"
                assert servers_by_id["pending-server"].status == "Pending"
                assert (
                    servers_by_id["error-server"].status == "Error"
                )  # Falls back to MCPService status

    @pytest.mark.asyncio
    async def test_list_servers_kubernetes_api_completely_down(
        self, mock_workspace_id, mock_namespace_name, mock_request
    ):
        """Test that complete Kubernetes API failure is properly handled."""
        with patch(
            "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
        ) as mock_custom_api:
            # Simulate complete Kubernetes API failure
            mock_custom_api.return_value.list_namespaced_custom_object.side_effect = ApiException(
                status=500, reason="Internal Server Error"
            )

            # This should raise a proper HTTP exception, not crash the API
            with pytest.raises(HTTPException):  # Kubernetes API error converted to HTTPException
                await list_workspace_servers(
                    workspace_id=mock_workspace_id,
                    request=mock_request,
                    namespace_name=mock_namespace_name,
                )

    @pytest.mark.asyncio
    async def test_list_servers_no_mcpservices(
        self, mock_workspace_id, mock_namespace_name, mock_request
    ):
        """Test listing servers when no MCPServices exist (empty workspace)."""
        mock_mcpservices = {"items": []}

        with patch(
            "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
        ) as mock_custom_api:
            mock_custom_api.return_value.list_namespaced_custom_object.return_value = (
                mock_mcpservices
            )

            result = await list_workspace_servers(
                workspace_id=mock_workspace_id,
                request=mock_request,
                namespace_name=mock_namespace_name,
            )

            # Should return empty list without crashing
            assert result.total == 0
            assert len(result.servers) == 0
            assert result.workspace_id == UUID(mock_workspace_id)
