"""Test configuration and fixtures."""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from nimbletools_universal_adapter.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_subprocess():
    """Mock subprocess calls."""
    with patch("nimbletools_universal_adapter.main.subprocess") as mock_sub:
        yield mock_sub


@pytest.fixture
def mock_mcp_process():
    """Mock MCP process management."""
    mock_process = Mock()
    mock_process.poll.return_value = None  # Process is running
    mock_process.stdout.readline.return_value = b'{"result": "test"}\n'
    mock_process.stderr.readline.return_value = b""

    with patch("nimbletools_universal_adapter.main.subprocess.Popen", return_value=mock_process):
        yield mock_process
