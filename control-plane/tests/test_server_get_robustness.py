"""Tests for get_workspace_server robustness when Kubernetes API has transient errors."""

from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException
from kubernetes.client.rest import ApiException

from nimbletools_control_plane.exceptions import KubernetesOperationError
from nimbletools_control_plane.routes.servers import get_workspace_server


class TestServerGetRobustness:
    """Test getting individual server details handles transient errors gracefully."""

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
        deployment.status.unavailable_replicas = (
            0 if ready_replicas and ready_replicas > 0 else (total_replicas or 0)
        )
        deployment.status.conditions = None
        return deployment

    def create_mock_service(self):
        """Create a mock Kubernetes service."""
        service = Mock()
        service.metadata = Mock()
        service.metadata.name = "test-service"
        return service

    @pytest.mark.asyncio
    async def test_get_server_with_transient_deployment_error(
        self, mock_workspace_id, mock_namespace_name, mock_request
    ):
        """Test getting server details when deployment check has transient error (503, timeout, etc)."""
        server_id = "echo-server"
        mock_mcpservice = self.create_mock_mcpservice(server_id, "Running")

        with patch(
            "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
        ) as mock_custom_api:
            mock_custom_api.return_value.get_namespaced_custom_object.return_value = mock_mcpservice

            with patch(
                "nimbletools_control_plane.routes.servers.get_deployment_if_exists"
            ) as mock_get_deployment:
                # Simulate a transient Kubernetes error when checking deployment
                api_exception = ApiException(status=503, reason="Service Temporarily Unavailable")
                mock_get_deployment.side_effect = KubernetesOperationError(
                    message="Failed to read deployment: Service Temporarily Unavailable",
                    operation="reading",
                    resource=f"deployment:{server_id}-deployment",
                    api_exception=api_exception,
                )

                with patch(
                    "nimbletools_control_plane.routes.servers.get_service_if_exists"
                ) as mock_get_service:
                    mock_get_service.return_value = self.create_mock_service()

                    # Should not crash - deployment will be None but service check succeeds
                    result = await get_workspace_server(
                        workspace_id=mock_workspace_id,
                        server_id=server_id,
                        request=mock_request,
                        namespace_name=mock_namespace_name,
                    )

                    # Should still return server details with degraded deployment info
                    assert result.id == server_id
                    assert result.workspace_id == UUID(mock_workspace_id)
                    assert result.status["deployment_ready"] in [
                        False,
                        None,
                    ]  # No deployment info available
                    assert result.status["replicas"] == 0  # Default when deployment is None
                    assert result.status["ready_replicas"] == 0
                    assert result.status["service_endpoint"] is not None  # Service was found

    @pytest.mark.asyncio
    async def test_get_server_with_transient_service_error(
        self, mock_workspace_id, mock_namespace_name, mock_request
    ):
        """Test getting server details when service check has transient error."""
        server_id = "echo-server"
        mock_mcpservice = self.create_mock_mcpservice(server_id, "Running")
        mock_deployment = self.create_mock_deployment(ready_replicas=1, total_replicas=1)

        with patch(
            "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
        ) as mock_custom_api:
            mock_custom_api.return_value.get_namespaced_custom_object.return_value = mock_mcpservice

            with patch(
                "nimbletools_control_plane.routes.servers.get_deployment_if_exists"
            ) as mock_get_deployment:
                mock_get_deployment.return_value = mock_deployment

                with patch(
                    "nimbletools_control_plane.routes.servers.get_service_if_exists"
                ) as mock_get_service:
                    # Simulate a transient error when checking service
                    api_exception = ApiException(status=504, reason="Gateway Timeout")
                    mock_get_service.side_effect = KubernetesOperationError(
                        message="Failed to read service: Gateway Timeout",
                        operation="reading",
                        resource=f"service:{server_id}-service",
                        api_exception=api_exception,
                    )

                    # Should not crash - service will be None but deployment check succeeds
                    result = await get_workspace_server(
                        workspace_id=mock_workspace_id,
                        server_id=server_id,
                        request=mock_request,
                        namespace_name=mock_namespace_name,
                    )

                    # Should still return server details with deployment info but no service endpoint
                    assert result.id == server_id
                    assert result.status["deployment_ready"] is True  # Deployment is ready
                    assert result.status["replicas"] == 1
                    assert result.status["ready_replicas"] == 1
                    assert result.status["service_endpoint"] is None  # Service check failed

    @pytest.mark.asyncio
    async def test_get_server_with_both_deployment_and_service_errors(
        self, mock_workspace_id, mock_namespace_name, mock_request
    ):
        """Test getting server details when both deployment and service checks have transient errors."""
        server_id = "echo-server"
        mock_mcpservice = self.create_mock_mcpservice(server_id, "Pending")

        with patch(
            "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
        ) as mock_custom_api:
            mock_custom_api.return_value.get_namespaced_custom_object.return_value = mock_mcpservice

            with patch(
                "nimbletools_control_plane.routes.servers.get_deployment_if_exists"
            ) as mock_get_deployment:
                # Both deployment and service checks fail with transient errors
                mock_get_deployment.side_effect = KubernetesOperationError(
                    message="Connection timeout",
                    operation="reading",
                    resource=f"deployment:{server_id}-deployment",
                    api_exception=None,  # Could be a network timeout
                )

                with patch(
                    "nimbletools_control_plane.routes.servers.get_service_if_exists"
                ) as mock_get_service:
                    mock_get_service.side_effect = KubernetesOperationError(
                        message="Connection timeout",
                        operation="reading",
                        resource=f"service:{server_id}-service",
                        api_exception=None,
                    )

                    # Should not crash - returns minimal info from MCPService
                    result = await get_workspace_server(
                        workspace_id=mock_workspace_id,
                        server_id=server_id,
                        request=mock_request,
                        namespace_name=mock_namespace_name,
                    )

                    # Should still return basic server details from MCPService
                    assert result.id == server_id
                    assert result.status["phase"] == "Pending"  # From MCPService status
                    assert result.status["deployment_ready"] in [False, None]
                    assert result.status["replicas"] == 0
                    assert result.status["service_endpoint"] is None

    @pytest.mark.asyncio
    async def test_get_server_mcpservice_not_found(
        self, mock_workspace_id, mock_namespace_name, mock_request
    ):
        """Test that MCPService not found still raises 404 as expected."""
        server_id = "nonexistent-server"

        with patch(
            "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
        ) as mock_custom_api:
            # MCPService doesn't exist - this should still fail with 404
            mock_custom_api.return_value.get_namespaced_custom_object.side_effect = ApiException(
                status=404, reason="Not Found"
            )

            # This should raise HTTPException with 404
            with pytest.raises(HTTPException) as exc_info:
                await get_workspace_server(
                    workspace_id=mock_workspace_id,
                    server_id=server_id,
                    request=mock_request,
                    namespace_name=mock_namespace_name,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_server_with_unexpected_exception(
        self, mock_workspace_id, mock_namespace_name, mock_request
    ):
        """Test getting server details when an unexpected (non-KubernetesOperationError) exception occurs."""
        server_id = "echo-server"
        mock_mcpservice = self.create_mock_mcpservice(server_id, "Running")

        with patch(
            "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
        ) as mock_custom_api:
            mock_custom_api.return_value.get_namespaced_custom_object.return_value = mock_mcpservice

            with patch(
                "nimbletools_control_plane.routes.servers.get_deployment_if_exists"
            ) as mock_get_deployment:
                # Simulate an unexpected error (not KubernetesOperationError)
                mock_get_deployment.side_effect = RuntimeError("Unexpected internal error")

                with patch(
                    "nimbletools_control_plane.routes.servers.get_service_if_exists"
                ) as mock_get_service:
                    mock_get_service.return_value = None

                    # Should not crash - handles unexpected exceptions too
                    result = await get_workspace_server(
                        workspace_id=mock_workspace_id,
                        server_id=server_id,
                        request=mock_request,
                        namespace_name=mock_namespace_name,
                    )

                    # Should still return server details
                    assert result.id == server_id
                    assert result.status["deployment_ready"] in [False, None]
                    assert result.status["replicas"] == 0
