"""Tests for main module."""

from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient, mock_k8s_config, mock_auth_provider):
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "NimbleTools Control Plane"
    assert data["version"] == "1.0.0"
    assert "endpoints" in data


def test_health_check(client: TestClient, mock_k8s_config, mock_auth_provider):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data["service"] == "Powered by NimbleTools.ai"


def test_cors_headers(client: TestClient, mock_k8s_config, mock_auth_provider):
    """Test that CORS headers are properly set."""
    response = client.get("/", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
