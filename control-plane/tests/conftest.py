"""Test configuration and fixtures."""

from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from nimbletools_control_plane.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_k8s_config():
    """Mock Kubernetes configuration loading."""
    with (
        patch("nimbletools_control_plane.main.config.load_incluster_config"),
        patch("nimbletools_control_plane.main.config.load_kube_config"),
    ):
        yield


@pytest.fixture
def mock_auth_provider():
    """Mock authentication provider using new auth system."""

    # Create a mock auth provider that implements the new protocol
    class MockAuthProvider:
        async def validate_token(self, token: str) -> dict[str, Any] | None:
            return {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",  # Valid UUID
                "organization_id": "123e4567-e89b-12d3-a456-426614174000",  # Valid UUID for org
                "email": "test@example.com",
                "role": "admin",
            }

        async def check_workspace_access(self, user: dict[str, Any], workspace_id: str) -> bool:
            return True

        async def check_permission(self, user: dict[str, Any], resource: str, action: str) -> bool:
            return True

        async def create_workspace_token(self, workspace_id: str, user: dict[str, Any]) -> str:
            return f"test_token_{workspace_id}"

        async def validate_mcp_token(self, token: str, workspace_id: str) -> bool:
            return True

        async def initialize(self) -> None:
            pass

        async def shutdown(self) -> None:
            pass

    mock_provider = MockAuthProvider()

    # Patch the provider module to use our mock
    with patch("nimbletools_control_plane.provider._provider", mock_provider):
        yield mock_provider
