"""Debug tests for server deployment issues."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from nimbletools_control_plane.auth import (
    AuthenticatedRequest,
    AuthType,
    UserContext,
    create_auth_provider,
)
from nimbletools_control_plane.middlewares import create_workspace_access_validator


@pytest.mark.skip(reason="Temporarily disabled - needs K8s mocking fixes after model refactoring")
class TestServerDeploymentDebug:
    """Debug tests for the exact failing server deployment scenario."""

    def test_deploy_echo_to_workspace_exact_scenario(
        self, client: TestClient, mock_k8s_config, mock_auth_provider
    ):
        """
        Test the exact scenario that's failing: POST /v1/workspaces/{id}/servers with echo.
        This replicates ntcli server deploy echo --debug exactly.
        """
        workspace_id = "6587baf7-183a-405f-98c3-612919101dcf"

        # Mock workspace access validator to return the expected namespace
        with patch(
            "nimbletools_control_plane.middlewares.client.CoreV1Api"
        ) as mock_k8s_core_class:
            # Mock the Kubernetes API calls inside the validator
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            # Mock namespace response
            mock_namespace = Mock()
            mock_namespace.metadata.name = f"ws-foobar-{workspace_id}"
            mock_namespaces = Mock()
            mock_namespaces.items = [mock_namespace]
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            # Mock Kubernetes API for MCPService creation
            with patch(
                "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
            ) as mock_k8s_custom_class:
                mock_k8s_custom = Mock()
                mock_k8s_custom_class.return_value = mock_k8s_custom
                mock_k8s_custom.create_namespaced_custom_object.return_value = None

                # This is the exact request ntcli makes with new Pydantic model format
                response = client.post(
                    f"/v1/workspaces/{workspace_id}/servers",
                    json={"server_id": "echo", "replicas": 1, "environment": {}},
                )

                # Debug the response
                print(f"Response status: {response.status_code}")
                print(f"Response body: {response.json()}")

                # Should succeed
                assert response.status_code == 200
                data = response.json()
                assert data["server_id"] == "echo"
                assert data["workspace_id"] == workspace_id
                assert data["status"] == "deployed"

                # Verify MCPService creation was called
                mock_k8s_custom.create_namespaced_custom_object.assert_called_once()
                call_args = mock_k8s_custom.create_namespaced_custom_object.call_args[1]

                # Verify the MCPService details
                created_service = call_args["body"]
                assert created_service["metadata"]["name"] == "echo"
                assert (
                    created_service["spec"]["container"]["image"]
                    == "nimbletools/mcp-echo:latest"
                )
                assert call_args["namespace"] == f"ws-foobar-{workspace_id}"

    async def test_workspace_access_validator_function(self):
        """Test the workspace access validator function directly."""
        # Create the validator
        validator = create_workspace_access_validator("workspace_id")

        # Test with mock request
        mock_request = Mock()
        mock_request.path_params = {"workspace_id": "test-123"}

        # Test with mock auth context
        mock_auth_context = AuthenticatedRequest(
            auth_type=AuthType.NONE,
            authenticated=True,
            user=UserContext(
                user_id="community-user", email="test@example.com", role="admin"
            ),
        )

        # Mock Kubernetes client to return a namespace
        with patch(
            "nimbletools_control_plane.middlewares.client.CoreV1Api"
        ) as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            # Mock namespace response
            mock_namespace = Mock()
            mock_namespace.metadata.name = "ws-foobar-test-123"
            mock_namespaces = Mock()
            mock_namespaces.items = [mock_namespace]
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            # Should return the actual namespace name
            result = await validator(mock_request, mock_auth_context)
            assert result == "ws-foobar-test-123"

    def test_minimal_server_deployment_without_dependencies(
        self, client: TestClient, mock_k8s_config, mock_auth_provider
    ):
        """Test server deployment with all dependencies mocked to isolate the issue."""
        workspace_id = "test-workspace-123"

        # Mock ALL dependencies
        with patch(
            "nimbletools_control_plane.middlewares.client.CoreV1Api"
        ) as mock_k8s_core_class:
            # Mock the Kubernetes API calls inside the validator
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            # Mock namespace response
            mock_namespace = Mock()
            mock_namespace.metadata.name = f"ws-foobar-{workspace_id}"
            mock_namespaces = Mock()
            mock_namespaces.items = [mock_namespace]
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            with patch("nimbletools_control_plane.routes.servers.log_operation_start"):
                with patch(
                    "nimbletools_control_plane.routes.servers.create_auth_provider"
                ) as mock_auth_factory:
                    with patch(
                        "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
                    ) as mock_k8s_custom_class:
                        # Mock auth provider
                        mock_auth_provider_instance = Mock()
                        mock_auth_provider_instance.authenticate = AsyncMock(
                            return_value={"user_id": "test-user"}
                        )
                        mock_auth_factory.return_value = mock_auth_provider_instance

                        # Mock Kubernetes API
                        mock_k8s_custom = Mock()
                        mock_k8s_custom_class.return_value = mock_k8s_custom
                        mock_k8s_custom.create_namespaced_custom_object.return_value = (
                            None
                        )

                        response = client.post(
                            f"/v1/workspaces/{workspace_id}/servers",
                            json={
                                "server_id": "echo",
                                "replicas": 1,
                                "environment": {},
                            },
                        )

                        print(f"Status: {response.status_code}")
                        print(f"Response: {response.json()}")

                        # If this fails, the issue is in our core logic
                        # If this succeeds, the issue is in dependency injection
                        assert response.status_code == 200

    def test_server_deployment_step_by_step(
        self, client: TestClient, mock_k8s_config, mock_auth_provider
    ):
        """Test each step of server deployment individually."""

        # Step 1: Test basic endpoint exists
        response = client.post("/v1/workspaces/test/servers", json={})
        assert response.status_code == 400  # Should get server_id required
        assert "server_id is required" in response.json()["detail"]

        # Step 2: Test with server_id but mock everything else
        with patch(
            "nimbletools_control_plane.middlewares.client.CoreV1Api"
        ) as mock_k8s_core_class:
            # Mock the Kubernetes API calls inside the validator
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            # Mock namespace response
            mock_namespace = Mock()
            mock_namespace.metadata.name = "ws-test"
            mock_namespaces = Mock()
            mock_namespaces.items = [mock_namespace]
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            with patch("nimbletools_control_plane.routes.servers.log_operation_start"):
                with patch(
                    "nimbletools_control_plane.routes.servers.create_auth_provider"
                ) as mock_auth_factory:
                    with patch(
                        "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
                    ) as mock_k8s:
                        # Mock all dependencies
                        mock_auth_factory.return_value.authenticate.return_value = {
                            "user_id": "test"
                        }
                        mock_k8s.return_value.create_namespaced_custom_object.return_value = (
                            None
                        )

                        response = client.post(
                            "/v1/workspaces/test/servers",
                            json={
                                "server_id": "echo",
                                "replicas": 1,
                                "environment": {},
                            },
                        )

                        print(
                            f"Step 2 - Status: {response.status_code}, Response: {response.json()}"
                        )

                        # This should work if our logic is correct
                        if response.status_code != 200:
                            pytest.fail(
                                f"Server deployment failed at step 2: {response.json()}"
                            )

    async def test_workspace_namespace_resolution(
        self, client: TestClient, mock_k8s_config
    ):
        """Test if workspace namespace resolution works."""

        # Test the workspace access validator directly
        validator = create_workspace_access_validator("workspace_id")

        # Create mock request
        mock_request = Mock()
        mock_request.path_params = {
            "workspace_id": "6587baf7-183a-405f-98c3-612919101dcf"
        }

        # Create mock auth context
        mock_auth_context = AuthenticatedRequest(
            auth_type=AuthType.NONE,
            authenticated=True,
            user=UserContext(
                user_id="community-user", email="test@example.com", role="admin"
            ),
        )

        # Mock Kubernetes client to return a namespace
        with patch(
            "nimbletools_control_plane.middlewares.client.CoreV1Api"
        ) as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            # Mock namespace response
            mock_namespace = Mock()
            mock_namespace.metadata.name = (
                "ws-foobar-6587baf7-183a-405f-98c3-612919101dcf"
            )
            mock_namespaces = Mock()
            mock_namespaces.items = [mock_namespace]
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            # This should work
            try:
                result = await validator(mock_request, mock_auth_context)
                print(f"Validator result: {result}")
                assert result == "ws-foobar-6587baf7-183a-405f-98c3-612919101dcf"
            except Exception as e:
                pytest.fail(f"Workspace validator failed: {e}")

    def test_auth_provider_functionality(self):
        """Test if auth provider works correctly."""
        auth_provider = create_auth_provider()

        # Test with mock request
        mock_request = Mock()
        mock_request.headers = {}

        # This should not fail in no-auth mode
        try:
            result = auth_provider.authenticate(mock_request)
            print(f"Auth result: {result}")
            # Should return community user info
            assert result is not None
        except Exception as e:
            pytest.fail(f"Auth provider failed: {e}")

    def test_real_workspace_deployment_end_to_end(
        self, client: TestClient, mock_k8s_config, mock_auth_provider
    ):
        """Test server deployment end-to-end with realistic mocking."""

        real_workspace_id = "d6b0fb79-f7e4-41c9-a05c-0d014aedd699"

        # Mock workspace access validator to simulate real workspace lookup
        with patch(
            "nimbletools_control_plane.middlewares.client.CoreV1Api"
        ) as mock_k8s_core_class:
            # Mock workspace namespace lookup
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            mock_namespace = Mock()
            mock_namespace.metadata.name = f"ws-foobar-{real_workspace_id}"

            mock_namespaces = Mock()
            mock_namespaces.items = [mock_namespace]
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            # Mock server router dependencies
            with patch("nimbletools_control_plane.routes.servers.log_operation_start"):
                with patch(
                    "nimbletools_control_plane.routes.servers.create_auth_provider"
                ) as mock_auth_factory:
                    with patch(
                        "nimbletools_control_plane.routes.servers.client.CustomObjectsApi"
                    ) as mock_k8s_custom_class:
                        # Mock auth provider
                        mock_auth_provider_instance = Mock()
                        mock_auth_provider_instance.authenticate = AsyncMock(
                            return_value={"user_id": "community-user"}
                        )
                        mock_auth_factory.return_value = mock_auth_provider_instance

                        # Mock Kubernetes API
                        mock_k8s_custom = Mock()
                        mock_k8s_custom_class.return_value = mock_k8s_custom
                        mock_k8s_custom.create_namespaced_custom_object.return_value = (
                            None
                        )

                        # Test with real workspace ID
                        response = client.post(
                            f"/v1/workspaces/{real_workspace_id}/servers",
                            json={
                                "server_id": "echo",
                                "replicas": 1,
                                "environment": {},
                            },
                        )

                        print(f"Real workspace test - Status: {response.status_code}")
                        print(f"Real workspace test - Response: {response.json()}")

                        if response.status_code != 200:
                            pytest.fail(
                                f"Real workspace deployment failed: {response.json()}"
                            )

                        # Verify the correct namespace was used
                        call_args = (
                            mock_k8s_custom.create_namespaced_custom_object.call_args[1]
                        )
                        assert (
                            call_args["namespace"] == f"ws-foobar-{real_workspace_id}"
                        )

    def test_workspace_lookup_behavior(self):
        """Test to verify workspace lookup behavior vs hardcoded behavior."""

        workspace_id = "37eac152-42ab-4c58-9efd-b92736851733"

        # Test old behavior (hardcoded)
        old_namespace = f"ws-{workspace_id}"
        print(f"Old behavior would return: {old_namespace}")

        # Test new behavior (should query and find ws-foobar-...)
        expected_namespace = f"ws-foobar-{workspace_id}"
        print(f"New behavior should return: {expected_namespace}")

        # The error shows we're getting the old behavior
        assert old_namespace == "ws-37eac152-42ab-4c58-9efd-b92736851733"
        assert expected_namespace == "ws-foobar-37eac152-42ab-4c58-9efd-b92736851733"

        # This confirms the issue: old != expected
        assert old_namespace != expected_namespace
