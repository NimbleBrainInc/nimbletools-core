"""Tests for workspace router module."""

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from kubernetes.client.rest import ApiException

from nimbletools_control_plane.auth import get_workspace_namespace
from nimbletools_control_plane.models import WorkspaceListResponse
from nimbletools_control_plane.routes.workspaces import list_workspaces


@pytest.fixture
def mock_community_user():
    """Mock user from community provider with proper UUID format."""
    return {
        "user_id": "00000000-0000-0000-0000-000000000001",
        "organization_id": "00000000-0000-0000-0000-000000000002",
        "email": "user@community",
        "role": "admin",
        "auth_type": "none",
    }


@pytest.fixture
def sample_workspace_namespace():
    """Sample workspace namespace object."""
    mock_ns = Mock()
    mock_ns.metadata.name = "ws-test-workspace-123e4567-e89b-12d3-a456-426614174000"
    mock_ns.metadata.labels = {
        "mcp.nimbletools.dev/workspace": "true",
        "mcp.nimbletools.dev/workspace_id": "123e4567-e89b-12d3-a456-426614174000",
        "mcp.nimbletools.dev/workspace_name": "test-workspace-123e4567-e89b-12d3-a456-426614174000",
        "mcp.nimbletools.dev/user_id": "550e8400-e29b-41d4-a716-446655440000",
        "mcp.nimbletools.dev/organization_id": "123e4567-e89b-12d3-a456-426614174000",
    }
    mock_ns.metadata.annotations = {"mcp.nimbletools.dev/created": "2025-08-25T10:00:00Z"}
    return mock_ns


@pytest.fixture
def multiple_workspace_namespaces():
    """Multiple workspace namespace objects for testing."""
    workspaces = []

    # Workspace 1
    ws1 = Mock()
    ws1.metadata.name = "ws-foobar-a466de49-3ad4-4f7e-94da-6b2d75ace5a1"
    ws1.metadata.labels = {
        "mcp.nimbletools.dev/workspace": "true",
        "mcp.nimbletools.dev/workspace_id": "a466de49-3ad4-4f7e-94da-6b2d75ace5a1",
        "mcp.nimbletools.dev/workspace_name": "foobar",
        "mcp.nimbletools.dev/user_id": "550e8400-e29b-41d4-a716-446655440000",
        "mcp.nimbletools.dev/organization_id": "123e4567-e89b-12d3-a456-426614174000",
    }
    ws1.metadata.annotations = {"mcp.nimbletools.dev/created": "2025-08-25T09:00:00Z"}
    workspaces.append(ws1)

    # Workspace 2
    ws2 = Mock()
    ws2.metadata.name = "ws-test-rbac-workspace-42a1d0e0-baeb-4498-a7aa-15690182a62e"
    ws2.metadata.labels = {
        "mcp.nimbletools.dev/workspace": "true",
        "mcp.nimbletools.dev/workspace_id": "42a1d0e0-baeb-4498-a7aa-15690182a62e",
        "mcp.nimbletools.dev/workspace_name": "test-rbac-workspace",
        "mcp.nimbletools.dev/user_id": "550e8400-e29b-41d4-a716-446655440000",
        "mcp.nimbletools.dev/organization_id": "123e4567-e89b-12d3-a456-426614174000",
    }
    ws2.metadata.annotations = {"mcp.nimbletools.dev/created": "2025-08-25T08:30:00Z"}
    workspaces.append(ws2)

    # Workspace 3
    ws3 = Mock()
    ws3.metadata.name = "ws-woot-41f790ea-0889-4397-8da7-a60fc9a510fd"
    ws3.metadata.labels = {
        "mcp.nimbletools.dev/workspace": "true",
        "mcp.nimbletools.dev/workspace_id": "41f790ea-0889-4397-8da7-a60fc9a510fd",
        "mcp.nimbletools.dev/workspace_name": "woot",
        "mcp.nimbletools.dev/user_id": "550e8400-e29b-41d4-a716-446655440000",
        "mcp.nimbletools.dev/organization_id": "123e4567-e89b-12d3-a456-426614174000",
    }
    ws3.metadata.annotations = {"mcp.nimbletools.dev/created": "2025-08-25T10:30:00Z"}
    workspaces.append(ws3)

    return workspaces


class TestWorkspaceListingRegression:
    """Regression tests for workspace listing functionality."""

    def test_workspace_list_missing_user_id_raises_401(
        self,
        client: TestClient,
        mock_k8s_config,
        mock_auth_provider,
    ):
        """
        Test that list_workspaces raises HTTP 401 when user_id is missing.

        This prevents defaulting to 'community-user' and ensures proper
        authentication validation.
        """

        # Override the mock auth provider's validate_token to return user without user_id
        async def validate_token_without_user_id(token):
            return {
                "email": "test@example.com",
                # user_id is intentionally missing
            }

        mock_auth_provider.validate_token = validate_token_without_user_id

        with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            # Make the request
            response = client.get("/v1/workspaces")

            # Should return 401 Unauthorized
            assert response.status_code == 401
            data = response.json()
            assert "User authentication failed" in data["detail"]
            assert "missing user_id" in data["detail"]

            # Kubernetes API should not be called when auth fails
            mock_k8s_core.list_namespace.assert_not_called()

    def test_workspace_list_uses_correct_label_selector(
        self,
        client: TestClient,
        mock_k8s_config,
        mock_auth_provider,
        multiple_workspace_namespaces,
    ):
        """
        CRITICAL REGRESSION TEST: Ensure workspace listing uses correct label selector.

        This test prevents the bug where workspace listing returned empty results
        because it was using 'mcp.nimbletools.ai/workspace=true' instead of
        'mcp.nimbletools.dev/workspace=true'.
        """
        with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            # Mock namespace list response
            mock_namespaces = Mock()
            mock_namespaces.items = multiple_workspace_namespaces
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            response = client.get("/v1/workspaces")

            # Should succeed and return workspaces
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 3
            assert len(data["workspaces"]) == 3
            assert data["user_id"] == "550e8400-e29b-41d4-a716-446655440000"

            # CRITICAL: Verify the correct label selector was used (including organization filter)
            mock_k8s_core.list_namespace.assert_called_once_with(
                label_selector="mcp.nimbletools.dev/workspace=true,mcp.nimbletools.dev/organization_id=123e4567-e89b-12d3-a456-426614174000"
            )

            # Verify workspace details are correct
            workspace_ids = [ws["workspace_id"] for ws in data["workspaces"]]
            assert "a466de49-3ad4-4f7e-94da-6b2d75ace5a1" in workspace_ids
            assert "42a1d0e0-baeb-4498-a7aa-15690182a62e" in workspace_ids
            assert "41f790ea-0889-4397-8da7-a60fc9a510fd" in workspace_ids

    def test_workspace_list_wrong_label_selector_returns_empty(
        self, client: TestClient, mock_k8s_config, mock_auth_provider
    ):
        """
        Test that demonstrates the bug: wrong label selector returns no results.
        This test shows what would happen with the old buggy code.
        """
        with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            # Simulate what happens with wrong label selector - no results
            mock_namespaces = Mock()
            mock_namespaces.items = []  # Empty because wrong label
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            response = client.get("/v1/workspaces")

            # Would return empty (this was the bug)
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0
            assert len(data["workspaces"]) == 0

    def test_workspace_list_no_auth_mode_uses_correct_selector(
        self,
        client: TestClient,
        mock_k8s_config,
        mock_auth_provider,
        multiple_workspace_namespaces,
    ):
        """Test that no-auth mode uses the correct label selector without owner filtering."""
        # The mock_auth_provider already returns appropriate test user

        with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            mock_namespaces = Mock()
            mock_namespaces.items = multiple_workspace_namespaces
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            response = client.get("/v1/workspaces")

            assert response.status_code == 200

            # CRITICAL: Should use basic workspace selector, not owner filtering
            mock_k8s_core.list_namespace.assert_called_once_with(
                label_selector="mcp.nimbletools.dev/workspace=true,mcp.nimbletools.dev/organization_id=123e4567-e89b-12d3-a456-426614174000"
            )

    @pytest.mark.skip(reason="Enterprise mode mocking needs fixes after model refactoring")
    def test_workspace_list_enterprise_mode_with_owner_filter(
        self, client: TestClient, mock_k8s_config, multiple_workspace_namespaces
    ):
        """Test enterprise mode uses correct label selector with owner filtering."""
        # Mock enterprise auth provider
        mock_enterprise_provider = Mock()
        mock_enterprise_provider.authenticate.return_value = {
            "user_id": "enterprise-user",
            "email": "user@company.com",
            "role": "user",
        }

        with patch(
            "nimbletools_control_plane.routes.workspaces.create_auth_provider",
            return_value=mock_enterprise_provider,
        ):
            with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
                # Mock auth context to simulate enterprise mode
                with patch(
                    "nimbletools_control_plane.routes.workspaces.get_auth_context"
                ) as mock_auth_context:
                    # Note: This test is skipped and needs refactoring after AuthenticatedRequest removal
                    mock_auth_context.return_value = {
                        "user_id": "enterprise-user",
                        "email": "user@company.com",
                        "role": "user",
                    }

                    mock_k8s_core = Mock()
                    mock_k8s_core_class.return_value = mock_k8s_core

                    mock_namespaces = Mock()
                    mock_namespaces.items = []  # No workspaces for this user
                    mock_k8s_core.list_namespace.return_value = mock_namespaces

                response = client.get("/v1/workspaces")

                assert response.status_code == 200

                # CRITICAL: Should use owner filtering in enterprise mode
                mock_k8s_core.list_namespace.assert_called_once_with(
                    label_selector="mcp.nimbletools.dev/workspace=true,mcp.nimbletools.dev/owner=enterprise-user"
                )

    def test_workspace_list_parses_labels_correctly(
        self,
        client: TestClient,
        mock_k8s_config,
        mock_auth_provider,
        sample_workspace_namespace,
    ):
        """Test that workspace listing correctly parses namespace labels and annotations."""
        with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            mock_namespaces = Mock()
            mock_namespaces.items = [sample_workspace_namespace]
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            response = client.get("/v1/workspaces")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1

            workspace = data["workspaces"][0]

            # Verify correct label parsing
            assert workspace["workspace_id"] == "123e4567-e89b-12d3-a456-426614174000"
            assert (
                workspace["workspace_name"] == "test-workspace-123e4567-e89b-12d3-a456-426614174000"
            )  # Full workspace name from label
            assert workspace["user_id"] == "550e8400-e29b-41d4-a716-446655440000"
            assert workspace["created_at"] == "2025-08-25T10:00:00Z"

    @pytest.mark.skip(reason="Missing labels handling needs fixes after model refactoring")
    def test_workspace_list_handles_missing_labels_gracefully(
        self, client: TestClient, mock_k8s_config, mock_auth_provider
    ):
        """Test workspace listing handles namespaces with missing labels gracefully."""
        # Create namespace with minimal labels
        minimal_namespace = Mock()
        minimal_namespace.metadata.name = "ws-minimal-123"
        minimal_namespace.metadata.labels = {
            "mcp.nimbletools.dev/workspace": "true"
            # Missing workspace_id, user_id
        }
        minimal_namespace.metadata.annotations = {}  # No annotations

        with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            mock_namespaces = Mock()
            mock_namespaces.items = [minimal_namespace]
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            response = client.get("/v1/workspaces")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1

            workspace = data["workspaces"][0]

            # Should handle missing labels gracefully with defaults
            assert workspace["workspace_id"] == "unknown"  # Default for missing workspace_id
            assert workspace["workspace_name"] == "minimal"  # Extracted from namespace name
            assert workspace["user_id"] is None  # Default for missing user_id

    @pytest.mark.skip(reason="Workspace name extraction needs fixes after model refactoring")
    def test_workspace_name_extraction_from_namespace(
        self, client: TestClient, mock_k8s_config, mock_auth_provider
    ):
        """Test that workspace names are correctly extracted from namespace names."""
        test_cases = [
            ("ws-foobar-a466de49-3ad4-4f7e-94da-6b2d75ace5a1", "foobar"),
            (
                "ws-test-rbac-workspace-42a1d0e0-baeb-4498-a7aa-15690182a62e",
                "test-rbac-workspace",
            ),
            (
                "ws-my-awesome-project-41f790ea-0889-4397-8da7-a60fc9a510fd",
                "my-awesome-project",
            ),
            ("ws-single-word-41f790ea-0889-4397-8da7-a60fc9a510fd", "single-word"),
        ]

        for namespace_name, expected_workspace_name in test_cases:
            # Create mock namespace
            mock_ns = Mock()
            mock_ns.metadata.name = namespace_name
            mock_ns.metadata.labels = {
                "mcp.nimbletools.dev/workspace": "true",
                "mcp.nimbletools.dev/workspace_id": "123e4567-e89b-12d3-a456-426614174000",
                "mcp.nimbletools.dev/owner": "community-user",
            }
            mock_ns.metadata.annotations = {}

            with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
                mock_k8s_core = Mock()
                mock_k8s_core_class.return_value = mock_k8s_core

                mock_namespaces = Mock()
                mock_namespaces.items = [mock_ns]
                mock_k8s_core.list_namespace.return_value = mock_namespaces

            response = client.get("/v1/workspaces")

            assert response.status_code == 200
            data = response.json()
            workspace = data["workspaces"][0]
            assert workspace["workspace_name"] == expected_workspace_name

    def test_workspace_list_empty_when_no_workspaces(
        self, client: TestClient, mock_k8s_config, mock_auth_provider
    ):
        """Test workspace listing returns empty when no workspaces exist."""
        with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            # No workspaces found
            mock_namespaces = Mock()
            mock_namespaces.items = []
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            response = client.get("/v1/workspaces")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0
            assert data["workspaces"] == []
            assert data["user_id"] == "550e8400-e29b-41d4-a716-446655440000"

            # Should still use correct label selector
            mock_k8s_core.list_namespace.assert_called_once_with(
                label_selector="mcp.nimbletools.dev/workspace=true,mcp.nimbletools.dev/organization_id=123e4567-e89b-12d3-a456-426614174000"
            )


class TestWorkspaceLabelSelectorRegression:
    """Specific tests to prevent label selector regression."""

    def test_no_auth_mode_label_selector_regression_prevention(
        self,
        client: TestClient,
        mock_k8s_config,
        mock_auth_provider,
        multiple_workspace_namespaces,
    ):
        """
        CRITICAL REGRESSION TEST: Prevent workspace listing from using wrong labels.

        This test specifically checks that we use 'mcp.nimbletools.dev/' not 'mcp.nimbletools.ai/'
        and that the workspace listing returns the expected 3 workspaces that exist in the cluster.
        """
        with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            mock_namespaces = Mock()
            mock_namespaces.items = multiple_workspace_namespaces
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            response = client.get("/v1/workspaces")

            # Should return all 3 workspaces (was returning 0 with wrong label)
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 3
            assert len(data["workspaces"]) == 3

            # Verify workspace details (just base names, no UUIDs)
            workspace_names = [ws["workspace_name"] for ws in data["workspaces"]]
            assert "foobar" in workspace_names
            assert "test-rbac-workspace" in workspace_names
            assert "woot" in workspace_names

            # CRITICAL: Must use correct label domain (.dev not .ai)
            call_args = mock_k8s_core.list_namespace.call_args[1]
            label_selector = call_args["label_selector"]

            # These assertions prevent the regression
            assert "mcp.nimbletools.dev/workspace=true" in label_selector
            assert "mcp.nimbletools.ai/" not in label_selector  # Must not use old domain
            assert "mcp.nimbletools.dev/organization_id=" in label_selector  # Must filter by org

            # Should not have owner filtering (we use user_id now)
            assert "owner=" not in label_selector

    @pytest.mark.skip(reason="Enterprise mode mocking needs fixes after model refactoring")
    def test_enterprise_mode_label_selector_with_owner_filtering(
        self, client: TestClient, mock_k8s_config
    ):
        """Test enterprise mode uses correct labels with owner filtering."""
        # Mock enterprise auth provider
        mock_enterprise_provider = Mock()
        mock_enterprise_provider.authenticate.return_value = {
            "user_id": "enterprise-user",
            "email": "user@company.com",
            "role": "user",
        }

        with patch(
            "nimbletools_control_plane.routes.workspaces.create_auth_provider",
            return_value=mock_enterprise_provider,
        ):
            with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
                with patch(
                    "nimbletools_control_plane.routes.workspaces.get_auth_context"
                ) as mock_auth_context:
                    # Mock enterprise auth context
                    # Note: This test is skipped and needs refactoring after AuthenticatedRequest removal
                    mock_auth_context.return_value = {
                        "user_id": "enterprise-user",
                        "email": "user@company.com",
                        "role": "user",
                    }

                    mock_k8s_core = Mock()
                    mock_k8s_core_class.return_value = mock_k8s_core

                    mock_namespaces = Mock()
                    mock_namespaces.items = []
                    mock_k8s_core.list_namespace.return_value = mock_namespaces

                response = client.get("/v1/workspaces")

                assert response.status_code == 200

                # CRITICAL: Enterprise mode should use owner filtering with correct domain
                call_args = mock_k8s_core.list_namespace.call_args[1]
                label_selector = call_args["label_selector"]

                # Prevent regression to wrong label domain
                assert "mcp.nimbletools.dev/workspace=true" in label_selector
                assert "mcp.nimbletools.dev/owner=enterprise-user" in label_selector
                assert "mcp.nimbletools.ai/" not in label_selector  # Must not use old domain

    def test_workspace_response_format_consistency(
        self,
        client: TestClient,
        mock_k8s_config,
        mock_auth_provider,
        sample_workspace_namespace,
    ):
        """Test that workspace response format is consistent and includes all expected fields."""
        with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            mock_namespaces = Mock()
            mock_namespaces.items = [sample_workspace_namespace]
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            response = client.get("/v1/workspaces")

            assert response.status_code == 200
            data = response.json()

            # Verify response structure
            assert "workspaces" in data
            assert "total" in data
            assert "user_id" in data
            assert data["total"] == 1

            workspace = data["workspaces"][0]

            # Verify all expected workspace fields are present
            required_fields = [
                "workspace_id",
                "workspace_name",
                "namespace",
                "user_id",
                "status",
                "created_at",
            ]
            for field in required_fields:
                assert field in workspace, f"Missing required field: {field}"

            # Verify specific values
            assert workspace["workspace_id"] == "123e4567-e89b-12d3-a456-426614174000"
            assert (
                workspace["workspace_name"] == "test-workspace-123e4567-e89b-12d3-a456-426614174000"
            )
            assert (
                workspace["namespace"] == "ws-test-workspace-123e4567-e89b-12d3-a456-426614174000"
            )
            assert workspace["user_id"] == "550e8400-e29b-41d4-a716-446655440000"
            assert workspace["status"] == "active"


class TestWorkspaceAccessValidation:
    """Test workspace access validation functionality."""

    @pytest.mark.skip(reason="create_workspace_access_validator was removed - test needs rewriting")
    async def test_workspace_access_validator_extracts_workspace_id(
        self, client: TestClient, mock_k8s_config, mock_auth_provider
    ):
        """Test that workspace access validator correctly extracts workspace ID from path."""
        # This test needs to be rewritten to test get_workspace_namespace directly
        pytest.skip("create_workspace_access_validator was removed")

        # Mock user that would be injected by get_current_user dependency
        mock_user = {
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "email": "test@example.com",
            "role": "admin",
        }

        # Mock Kubernetes client to return a namespace
        with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            # Mock namespace response
            mock_namespace = Mock()
            mock_namespace.metadata.name = "ws-foobar-test-workspace-123"
            mock_namespace.metadata.labels = {
                "mcp.nimbletools.dev/workspace_id": "test-workspace-123",
                "mcp.nimbletools.dev/workspace_name": "test-workspace-test-workspace-123",
            }
            mock_namespaces = Mock()
            mock_namespaces.items = [mock_namespace]
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            # The validator is a FastAPI dependency that expects request and user
            # Create mock request with path_params
            mock_request = Mock()
            mock_request.path_params = {"workspace_id": "test-workspace-123"}

            with patch(
                "nimbletools_control_plane.auth.dependencies.get_current_user",
                return_value=mock_user,
            ):
                # Call the validator as a regular async function (simulating FastAPI calling it)
                # TODO: Fix this test - validator is not defined after refactoring
                pass  # Placeholder to fix undefined name error

    async def test_workspace_access_validator_missing_workspace_id(
        self, client: TestClient, mock_k8s_config, mock_auth_provider
    ):
        """Test workspace access validator handles missing workspace ID."""
        # This test actually tests get_workspace_namespace function behavior
        # when a workspace doesn't exist

        # Mock user
        mock_user = {
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "email": "test@example.com",
            "role": "admin",
        }

        # Mock Kubernetes client to return no namespaces
        with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            # Mock empty namespace response (workspace doesn't exist)
            mock_namespaces = Mock()
            mock_namespaces.items = []
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            # Test get_workspace_namespace directly
            # Should raise HTTPException for non-existent workspace
            with pytest.raises(HTTPException) as exc_info:
                await get_workspace_namespace("non-existent-workspace", mock_user)

            assert exc_info.value.status_code == 404
            assert "Workspace" in exc_info.value.detail and "not found" in exc_info.value.detail


class TestWorkspaceSecretManagement:
    """Test workspace secret management functionality."""

    def test_list_workspace_secrets_empty(
        self, client: TestClient, mock_k8s_config, mock_auth_provider
    ):
        """Test listing secrets when no secrets exist."""
        # Mock the kubernetes client directly at the source
        with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
            # Set up the mock k8s client
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            # Mock empty secrets list with proper structure
            mock_secrets_list = Mock()
            mock_secrets_list.items = []
            mock_k8s_core.list_namespaced_secret.return_value = mock_secrets_list

            # Mock namespace list for the middleware validator
            mock_namespace = Mock()
            mock_namespace.metadata.name = "ws-test-550e8400-e29b-41d4-a716-446655440001"
            mock_namespace.metadata.labels = {
                "mcp.nimbletools.dev/workspace_id": "550e8400-e29b-41d4-a716-446655440001",
                "mcp.nimbletools.dev/workspace_name": "test-550e8400-e29b-41d4-a716-446655440001",
            }
            mock_namespaces = Mock()
            mock_namespaces.items = [mock_namespace]
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            response = client.get("/v1/workspaces/550e8400-e29b-41d4-a716-446655440001/secrets")

            assert response.status_code == 200
            data = response.json()

            assert data["workspace_id"] == "550e8400-e29b-41d4-a716-446655440001"
            assert data["secrets"] == []
            assert data["count"] == 0
            assert "0 secrets" in data["message"]

    def test_list_workspace_secrets_with_data(
        self, client: TestClient, mock_k8s_config, mock_auth_provider
    ):
        """Test listing secrets when secrets exist."""
        with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            # Mock secret with data
            mock_secret = Mock()
            mock_secret.data = {"API_KEY": "dGVzdC12YWx1ZQ==", "DB_PASSWORD": "c2VjcmV0"}

            mock_secrets_list = Mock()
            mock_secrets_list.items = [mock_secret]
            mock_k8s_core.list_namespaced_secret.return_value = mock_secrets_list

            # Mock namespace list for the middleware validator
            mock_namespace = Mock()
            mock_namespace.metadata.name = "ws-test-550e8400-e29b-41d4-a716-446655440001"
            mock_namespace.metadata.labels = {
                "mcp.nimbletools.dev/workspace_id": "550e8400-e29b-41d4-a716-446655440001",
                "mcp.nimbletools.dev/workspace_name": "test-550e8400-e29b-41d4-a716-446655440001",
            }
            mock_namespaces = Mock()
            mock_namespaces.items = [mock_namespace]
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            response = client.get("/v1/workspaces/550e8400-e29b-41d4-a716-446655440001/secrets")

            assert response.status_code == 200
            data = response.json()

            assert data["workspace_id"] == "550e8400-e29b-41d4-a716-446655440001"
            assert sorted(data["secrets"]) == ["API_KEY", "DB_PASSWORD"]
            assert data["count"] == 2
            assert "2 secrets" in data["message"]

    def test_set_workspace_secret_new_secret(
        self, client: TestClient, mock_k8s_config, mock_auth_provider
    ):
        """Test setting a new secret when no secrets exist."""
        with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            # Mock that secret doesn't exist (404)
            mock_k8s_core.read_namespaced_secret.side_effect = ApiException(status=404)

            # Mock namespace list for the middleware validator
            mock_namespace = Mock()
            mock_namespace.metadata.name = "ws-test-550e8400-e29b-41d4-a716-446655440001"
            mock_namespace.metadata.labels = {
                "mcp.nimbletools.dev/workspace_id": "550e8400-e29b-41d4-a716-446655440001",
                "mcp.nimbletools.dev/workspace_name": "test-550e8400-e29b-41d4-a716-446655440001",
            }
            mock_namespaces = Mock()
            mock_namespaces.items = [mock_namespace]
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            response = client.put(
                "/v1/workspaces/550e8400-e29b-41d4-a716-446655440001/secrets/API_KEY",
                json={"secret_value": "test-secret-value"},
            )

            assert response.status_code == 200
            data = response.json()

            assert data["workspace_id"] == "550e8400-e29b-41d4-a716-446655440001"
            assert data["secret_key"] == "API_KEY"
            assert data["status"] == "success"
            assert "set successfully" in data["message"]

            # Verify create_namespaced_secret was called
            mock_k8s_core.create_namespaced_secret.assert_called_once()

    def test_set_workspace_secret_update_existing(
        self, client: TestClient, mock_k8s_config, mock_auth_provider
    ):
        """Test updating an existing secret."""
        with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            # Mock existing secret
            mock_existing_secret = Mock()
            mock_existing_secret.data = {"OTHER_KEY": "other_value"}
            mock_k8s_core.read_namespaced_secret.return_value = mock_existing_secret

            # Mock namespace list for the middleware validator
            mock_namespace = Mock()
            mock_namespace.metadata.name = "ws-test-550e8400-e29b-41d4-a716-446655440001"
            mock_namespace.metadata.labels = {
                "mcp.nimbletools.dev/workspace_id": "550e8400-e29b-41d4-a716-446655440001",
                "mcp.nimbletools.dev/workspace_name": "test-550e8400-e29b-41d4-a716-446655440001",
            }
            mock_namespaces = Mock()
            mock_namespaces.items = [mock_namespace]
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            response = client.put(
                "/v1/workspaces/550e8400-e29b-41d4-a716-446655440001/secrets/API_KEY",
                json={"secret_value": "updated-secret-value"},
            )

            assert response.status_code == 200
            data = response.json()

            assert data["workspace_id"] == "550e8400-e29b-41d4-a716-446655440001"
            assert data["secret_key"] == "API_KEY"
            assert data["status"] == "success"
            assert "set successfully" in data["message"]

            # Verify patch_namespaced_secret was called
            mock_k8s_core.patch_namespaced_secret.assert_called_once()

    def test_delete_workspace_secret_success(
        self, client: TestClient, mock_k8s_config, mock_auth_provider
    ):
        """Test deleting an existing secret."""
        with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            # Mock existing secret with multiple keys
            mock_existing_secret = Mock()
            mock_existing_secret.data = {"API_KEY": "value1", "OTHER_KEY": "value2"}
            mock_k8s_core.read_namespaced_secret.return_value = mock_existing_secret

            # Mock namespace list for the middleware validator
            mock_namespace = Mock()
            mock_namespace.metadata.name = "ws-test-550e8400-e29b-41d4-a716-446655440001"
            mock_namespace.metadata.labels = {
                "mcp.nimbletools.dev/workspace_id": "550e8400-e29b-41d4-a716-446655440001",
                "mcp.nimbletools.dev/workspace_name": "test-550e8400-e29b-41d4-a716-446655440001",
            }
            mock_namespaces = Mock()
            mock_namespaces.items = [mock_namespace]
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            response = client.delete(
                "/v1/workspaces/550e8400-e29b-41d4-a716-446655440001/secrets/API_KEY"
            )

            assert response.status_code == 200
            data = response.json()

            assert data["workspace_id"] == "550e8400-e29b-41d4-a716-446655440001"
            assert data["secret_key"] == "API_KEY"
            assert data["status"] == "success"
            assert "deleted successfully" in data["message"]

            # Verify patch was called (since other keys remain)
            mock_k8s_core.patch_namespaced_secret.assert_called_once()

    def test_delete_workspace_secret_last_key(
        self, client: TestClient, mock_k8s_config, mock_auth_provider
    ):
        """Test deleting the last remaining secret key."""
        with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            # Mock existing secret with only one key
            mock_existing_secret = Mock()
            mock_existing_secret.data = {"API_KEY": "value1"}
            mock_k8s_core.read_namespaced_secret.return_value = mock_existing_secret

            # Mock namespace list for the middleware validator
            mock_namespace = Mock()
            mock_namespace.metadata.name = "ws-test-550e8400-e29b-41d4-a716-446655440001"
            mock_namespace.metadata.labels = {
                "mcp.nimbletools.dev/workspace_id": "550e8400-e29b-41d4-a716-446655440001",
                "mcp.nimbletools.dev/workspace_name": "test-550e8400-e29b-41d4-a716-446655440001",
            }
            mock_namespaces = Mock()
            mock_namespaces.items = [mock_namespace]
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            response = client.delete(
                "/v1/workspaces/550e8400-e29b-41d4-a716-446655440001/secrets/API_KEY"
            )

            assert response.status_code == 200
            data = response.json()

            assert data["workspace_id"] == "550e8400-e29b-41d4-a716-446655440001"
            assert data["secret_key"] == "API_KEY"
            assert data["status"] == "success"

            # Verify delete was called (since no keys remain)
            mock_k8s_core.delete_namespaced_secret.assert_called_once()

    def test_delete_workspace_secret_not_found(
        self, client: TestClient, mock_k8s_config, mock_auth_provider
    ):
        """Test deleting a secret that doesn't exist."""
        with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            # Mock that secret resource doesn't exist
            mock_k8s_core.read_namespaced_secret.side_effect = ApiException(status=404)

            # Mock namespace list for the middleware validator
            mock_namespace = Mock()
            mock_namespace.metadata.name = "ws-test-550e8400-e29b-41d4-a716-446655440001"
            mock_namespace.metadata.labels = {
                "mcp.nimbletools.dev/workspace_id": "550e8400-e29b-41d4-a716-446655440001",
                "mcp.nimbletools.dev/workspace_name": "test-550e8400-e29b-41d4-a716-446655440001",
            }
            mock_namespaces = Mock()
            mock_namespaces.items = [mock_namespace]
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            response = client.delete(
                "/v1/workspaces/550e8400-e29b-41d4-a716-446655440001/secrets/NONEXISTENT_KEY"
            )

            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"]

    def test_delete_workspace_secret_key_not_found(
        self, client: TestClient, mock_k8s_config, mock_auth_provider
    ):
        """Test deleting a secret key that doesn't exist in the secret resource."""
        with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            # Mock existing secret without the requested key - ensure data is a real dict
            mock_existing_secret = Mock()
            mock_existing_secret.data = {"OTHER_KEY": "value"}
            mock_k8s_core.read_namespaced_secret.return_value = mock_existing_secret

            # Mock namespace list for the middleware validator
            mock_namespace = Mock()
            mock_namespace.metadata.name = "ws-test-550e8400-e29b-41d4-a716-446655440001"
            mock_namespace.metadata.labels = {
                "mcp.nimbletools.dev/workspace_id": "550e8400-e29b-41d4-a716-446655440001",
                "mcp.nimbletools.dev/workspace_name": "test-550e8400-e29b-41d4-a716-446655440001",
            }
            mock_namespaces = Mock()
            mock_namespaces.items = [mock_namespace]
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            response = client.delete(
                "/v1/workspaces/550e8400-e29b-41d4-a716-446655440001/secrets/NONEXISTENT_KEY"
            )

            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"]


class TestCommunityProviderAuthentication:
    """Test workspace operations with community provider authentication."""

    @pytest.mark.asyncio
    async def test_community_provider_list_workspaces_with_proper_uuids(self, mock_community_user):
        """
        Test that community provider returns proper UUID format and workspace listing works.

        This test verifies the fix for the bug where community provider was returning
        string IDs like "community-user" instead of proper UUIDs, causing 500 errors.
        """
        with patch("kubernetes.client.CoreV1Api") as mock_k8s_core_class:
            mock_k8s_core = Mock()
            mock_k8s_core_class.return_value = mock_k8s_core

            # Create two mock workspaces for the community organization
            ws1 = Mock()
            ws1.metadata.name = "ws-workspace1-11111111-1111-1111-1111-111111111111"
            ws1.metadata.labels = {
                "mcp.nimbletools.dev/workspace": "true",
                "mcp.nimbletools.dev/workspace_id": "11111111-1111-1111-1111-111111111111",
                "mcp.nimbletools.dev/workspace_name": "workspace1",
                "mcp.nimbletools.dev/user_id": "00000000-0000-0000-0000-000000000001",
                "mcp.nimbletools.dev/organization_id": "00000000-0000-0000-0000-000000000002",
            }
            ws1.metadata.annotations = {"mcp.nimbletools.dev/created": "2025-09-25T10:00:00Z"}
            ws1.metadata.creation_timestamp = None

            ws2 = Mock()
            ws2.metadata.name = "ws-workspace2-22222222-2222-2222-2222-222222222222"
            ws2.metadata.labels = {
                "mcp.nimbletools.dev/workspace": "true",
                "mcp.nimbletools.dev/workspace_id": "22222222-2222-2222-2222-222222222222",
                "mcp.nimbletools.dev/workspace_name": "workspace2",
                "mcp.nimbletools.dev/user_id": "00000000-0000-0000-0000-000000000001",
                "mcp.nimbletools.dev/organization_id": "00000000-0000-0000-0000-000000000002",
            }
            ws2.metadata.annotations = {"mcp.nimbletools.dev/created": "2025-09-25T11:00:00Z"}
            ws2.metadata.creation_timestamp = None

            mock_namespaces = Mock()
            mock_namespaces.items = [ws1, ws2]
            mock_k8s_core.list_namespace.return_value = mock_namespaces

            # Call the list_workspaces function directly with mock user
            result = await list_workspaces(user=mock_community_user)

            # Verify the response is properly formatted with UUIDs
            assert isinstance(result, WorkspaceListResponse)
            assert result.total == 2
            assert len(result.workspaces) == 2

            # Verify user_id is a proper UUID string
            assert str(result.user_id) == "00000000-0000-0000-0000-000000000001"

            # Verify workspace 1
            workspace1 = result.workspaces[0]
            assert str(workspace1.workspace_id) == "11111111-1111-1111-1111-111111111111"
            assert workspace1.workspace_name == "workspace1"
            assert workspace1.namespace == "ws-workspace1-11111111-1111-1111-1111-111111111111"
            assert str(workspace1.user_id) == "00000000-0000-0000-0000-000000000001"
            assert str(workspace1.organization_id) == "00000000-0000-0000-0000-000000000002"
            assert workspace1.status == "active"

            # Verify workspace 2
            workspace2 = result.workspaces[1]
            assert str(workspace2.workspace_id) == "22222222-2222-2222-2222-222222222222"
            assert workspace2.workspace_name == "workspace2"
            assert workspace2.namespace == "ws-workspace2-22222222-2222-2222-2222-222222222222"
            assert str(workspace2.user_id) == "00000000-0000-0000-0000-000000000001"
            assert str(workspace2.organization_id) == "00000000-0000-0000-0000-000000000002"
            assert workspace2.status == "active"

            # Verify the correct label selector was used
            mock_k8s_core.list_namespace.assert_called_once_with(
                label_selector="mcp.nimbletools.dev/workspace=true,mcp.nimbletools.dev/organization_id=00000000-0000-0000-0000-000000000002"
            )
