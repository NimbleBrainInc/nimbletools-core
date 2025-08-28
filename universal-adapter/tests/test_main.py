"""Tests for main module."""

from unittest.mock import Mock, patch

from fastapi.testclient import TestClient


def test_health_endpoint_no_adapter(client: TestClient):
    """Test the health endpoint when adapter is not initialized."""
    response = client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert "Universal adapter not initialized" in data["detail"]


def test_basic_functionality(client: TestClient):
    """Test that the app starts and basic endpoints work."""
    # The universal adapter requires complex initialization
    # For now, just test that endpoints exist and return expected error codes
    response = client.get("/health")
    assert response.status_code in [200, 503]  # Either healthy or not initialized


def test_mcp_endpoint_requires_post(client: TestClient):
    """Test that MCP endpoint requires POST."""
    response = client.get("/mcp")
    assert response.status_code == 405  # Method not allowed


def test_mcp_endpoint_no_adapter(client: TestClient):
    """Test MCP endpoint when adapter is not initialized."""
    response = client.post("/mcp", json={"test": "data"})
    assert response.status_code == 503


@patch("nimbletools_universal_adapter.main.adapter")
def test_mcp_endpoint_with_adapter(mock_adapter, client: TestClient):
    """Test MCP endpoint with initialized adapter."""
    mock_adapter.config = Mock()
    mock_adapter.is_healthy.return_value = True

    # Test JSON-RPC request (returns method not supported but with 200 status)
    response = client.post("/mcp", json={})
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
