"""Test configuration and fixtures."""

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest


@pytest.fixture
def mock_k8s_config() -> Generator[None, None, None]:
    """Mock Kubernetes configuration loading."""
    with patch("nimbletools_core_operator.main.config.load_incluster_config"), \
         patch("nimbletools_core_operator.main.config.load_kube_config"):
        yield


@pytest.fixture
def mock_k8s_clients() -> Generator[dict[str, Any], None, None]:
    """Mock Kubernetes API clients."""
    with patch("nimbletools_core_operator.main.client.CoreV1Api") as mock_core, \
         patch("nimbletools_core_operator.main.client.AppsV1Api") as mock_apps, \
         patch("nimbletools_core_operator.main.client.CustomObjectsApi") as mock_custom:

        yield {
            "core": mock_core.return_value,
            "apps": mock_apps.return_value,
            "custom": mock_custom.return_value,
        }

