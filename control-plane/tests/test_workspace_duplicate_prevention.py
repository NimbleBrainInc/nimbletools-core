"""Tests for workspace duplicate prevention functionality."""

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from nimbletools_control_plane.models import WorkspaceCreateRequest, WorkspaceCreateResponse
from nimbletools_control_plane.routes.workspaces import create_workspace


class TestWorkspaceDuplicatePrevention:
    """Tests for preventing duplicate workspace names within an organization."""

    @pytest.mark.asyncio
    async def test_create_workspace_prevents_duplicate_names_in_org(self):
        """Test that creating a workspace with duplicate name in same org returns 409."""
        # Mock user with org ID
        mock_user = {
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "organization_id": "123e4567-e89b-12d3-a456-426614174000",
            "email": "test@example.com",
            "role": "admin",
        }

        # Mock existing workspace with same name in same org
        existing_ws = Mock()
        existing_ws.metadata.name = "ws-my-project-770e8400-e29b-41d4-a716-446655440003"
        existing_ws.metadata.labels = {
            "mcp.nimbletools.dev/workspace": "true",
            "mcp.nimbletools.dev/workspace_id": "770e8400-e29b-41d4-a716-446655440003",
            "mcp.nimbletools.dev/workspace_name": "my-project",
            "mcp.nimbletools.dev/user_id": "550e8400-e29b-41d4-a716-446655440000",
            "mcp.nimbletools.dev/organization_id": "123e4567-e89b-12d3-a456-426614174000",
            "mcp.nimbletools.dev/unique_key": "my-project-123e4567-e89b-12d3-a456-426614174000",
        }

        mock_namespaces = Mock()
        mock_namespaces.items = [existing_ws]

        # Mock Kubernetes client
        with patch("nimbletools_control_plane.routes.workspaces.client.CoreV1Api") as mock_k8s:
            mock_k8s_instance = Mock()
            mock_k8s.return_value = mock_k8s_instance
            mock_k8s_instance.list_namespace.return_value = mock_namespaces

            # Try to create workspace with duplicate name
            workspace_request = WorkspaceCreateRequest(
                name="my-project", description="Test project"
            )

            # Should raise HTTP 409 Conflict
            with pytest.raises(HTTPException) as exc_info:
                await create_workspace(workspace_request, mock_user)

            assert exc_info.value.status_code == 409
            assert "already exists in your organization" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_create_workspace_allows_same_name_different_org(self):
        """Test that creating a workspace with same name in different org succeeds."""
        # Mock user with different org ID
        mock_user = {
            "user_id": "660e9500-f39c-52e5-b827-557766551111",
            "organization_id": "987e6543-f21c-32e4-b567-537877662222",
            "email": "other@example.com",
            "role": "admin",
        }

        # Mock existing workspace with same name in DIFFERENT org
        existing_ws = Mock()
        existing_ws.metadata.name = "ws-my-project-880e8400-e29b-41d4-a716-446655440004"
        existing_ws.metadata.labels = {
            "mcp.nimbletools.dev/workspace": "true",
            "mcp.nimbletools.dev/workspace_id": "880e8400-e29b-41d4-a716-446655440004",
            "mcp.nimbletools.dev/workspace_name": "my-project",
            "mcp.nimbletools.dev/user_id": "550e8400-e29b-41d4-a716-446655440000",
            "mcp.nimbletools.dev/organization_id": "123e4567-e89b-12d3-a456-426614174000",
            "mcp.nimbletools.dev/unique_key": "my-project-123e4567-e89b-12d3-a456-426614174000",
        }

        # This workspace should not be returned since we're filtering by different org
        mock_namespaces = Mock()
        mock_namespaces.items = []  # No workspaces in this org

        # Mock Kubernetes client
        with patch("nimbletools_control_plane.routes.workspaces.client.CoreV1Api") as mock_k8s:
            mock_k8s_instance = Mock()
            mock_k8s.return_value = mock_k8s_instance
            mock_k8s_instance.list_namespace.return_value = mock_namespaces

            # Mock successful creation
            with patch(
                "nimbletools_control_plane.routes.workspaces.generate_workspace_identifiers"
            ) as mock_gen_ids:
                mock_gen_ids.return_value = {
                    "workspace_id": "550e8400-e29b-41d4-a716-446655440001",
                    "workspace_name": "my-project",
                    "namespace_name": "ws-my-project-550e8400-e29b-41d4-a716-446655440001",
                }

                # Mock namespace creation
                mock_k8s_instance.create_namespace.return_value = None

                workspace_request = WorkspaceCreateRequest(
                    name="my-project", description="Test project in different org"
                )

                # Should succeed without raising exception
                result = await create_workspace(workspace_request, mock_user)
                assert isinstance(result, WorkspaceCreateResponse)
                assert result.workspace_name == "my-project"
                assert result.status == "ready"

    @pytest.mark.asyncio
    async def test_create_workspace_adds_unique_key_label(self):
        """Test that created workspaces have the unique_key label."""
        mock_user = {
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "organization_id": "123e4567-e89b-12d3-a456-426614174000",
            "email": "test@example.com",
            "role": "admin",
        }

        # No existing workspaces
        mock_namespaces = Mock()
        mock_namespaces.items = []

        # Mock Kubernetes client
        with patch("nimbletools_control_plane.routes.workspaces.client.CoreV1Api") as mock_k8s:
            mock_k8s_instance = Mock()
            mock_k8s.return_value = mock_k8s_instance
            mock_k8s_instance.list_namespace.return_value = mock_namespaces

            with patch(
                "nimbletools_control_plane.routes.workspaces.generate_workspace_identifiers"
            ) as mock_gen_ids:
                mock_gen_ids.return_value = {
                    "workspace_id": "660e8400-e29b-41d4-a716-446655440002",
                    "workspace_name": "test-workspace",
                    "namespace_name": "ws-test-workspace-660e8400-e29b-41d4-a716-446655440002",
                }

                workspace_request = WorkspaceCreateRequest(
                    name="test-workspace", description="Test workspace"
                )

                await create_workspace(workspace_request, mock_user)

                # Verify namespace was created with correct labels
                create_call = mock_k8s_instance.create_namespace.call_args
                namespace_obj = create_call[0][0]
                labels = namespace_obj.metadata.labels

                # Check that unique_key label is present and correct
                assert "mcp.nimbletools.dev/unique_key" in labels
                assert (
                    labels["mcp.nimbletools.dev/unique_key"]
                    == "test-workspace-123e4567-e89b-12d3-a456-426614174000"
                )

    @pytest.mark.asyncio
    async def test_create_workspace_checks_correct_label_selector(self):
        """Test that duplicate check uses correct label selector for organization."""
        mock_user = {
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "organization_id": "123e4567-e89b-12d3-a456-426614174000",
            "email": "test@example.com",
            "role": "admin",
        }

        mock_namespaces = Mock()
        mock_namespaces.items = []

        with patch("nimbletools_control_plane.routes.workspaces.client.CoreV1Api") as mock_k8s:
            mock_k8s_instance = Mock()
            mock_k8s.return_value = mock_k8s_instance
            mock_k8s_instance.list_namespace.return_value = mock_namespaces

            with patch(
                "nimbletools_control_plane.routes.workspaces.generate_workspace_identifiers"
            ) as mock_gen_ids:
                mock_gen_ids.return_value = {
                    "workspace_id": "990e8400-e29b-41d4-a716-446655440005",
                    "workspace_name": "test-workspace",
                    "namespace_name": "ws-test-workspace-990e8400-e29b-41d4-a716-446655440005",
                }

                workspace_request = WorkspaceCreateRequest(
                    name="test-workspace", description="Test workspace"
                )

                await create_workspace(workspace_request, mock_user)

                # Verify correct label selector was used to check for duplicates
                mock_k8s_instance.list_namespace.assert_called_with(
                    label_selector="mcp.nimbletools.dev/workspace=true,mcp.nimbletools.dev/organization_id=123e4567-e89b-12d3-a456-426614174000"
                )
