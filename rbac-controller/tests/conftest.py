"""Pytest configuration and shared fixtures."""

from unittest.mock import MagicMock, patch

import pytest
from kubernetes import client
from kubernetes.client.models import (
    V1Namespace,
    V1NamespaceList,
    V1ObjectMeta,
    V1RoleBinding,
)


@pytest.fixture
def mock_k8s_config():
    """Mock kubernetes configuration loading."""
    with patch("nimbletools_rbac_controller.main.config") as mock_config:
        mock_config.load_incluster_config.side_effect = Exception("Not in cluster")
        mock_config.ConfigException = Exception
        yield mock_config


@pytest.fixture
def mock_k8s_clients():
    """Mock kubernetes API clients."""
    with patch("nimbletools_rbac_controller.main.client") as mock_client:
        mock_v1 = MagicMock(spec=client.CoreV1Api)
        mock_rbac_v1 = MagicMock(spec=client.RbacAuthorizationV1Api)

        mock_client.CoreV1Api.return_value = mock_v1
        mock_client.RbacAuthorizationV1Api.return_value = mock_rbac_v1

        yield {"v1": mock_v1, "rbac_v1": mock_rbac_v1, "client": mock_client}


@pytest.fixture
def sample_namespace():
    """Create a sample workspace namespace."""
    return V1Namespace(
        metadata=V1ObjectMeta(
            name="ws-test-workspace", labels={"mcp.nimbletools.dev/workspace_id": "test-workspace"}
        )
    )


@pytest.fixture
def sample_namespace_list(sample_namespace):
    """Create a sample namespace list."""
    return V1NamespaceList(items=[sample_namespace])


@pytest.fixture
def sample_rolebinding():
    """Create a sample RoleBinding."""
    return V1RoleBinding(
        metadata=V1ObjectMeta(name="nimbletools-operator-access", namespace="ws-test-workspace")
    )
