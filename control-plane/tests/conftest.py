"""Test configuration and fixtures."""

from unittest.mock import Mock, patch

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
    """Mock authentication provider."""
    mock_provider = Mock()
    mock_provider.authenticate.return_value = {
        "user_id": "test-user",
        "email": "test@example.com",
        "role": "admin",
    }

    with patch("nimbletools_control_plane.main.create_auth_provider", return_value=mock_provider):
        yield mock_provider
