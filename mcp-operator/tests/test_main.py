"""Tests for main operator module."""

import os
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client.models import (
    V1ConfigMap,
    V1Deployment,
    V1EnvVar,
    V1Ingress,
    V1Service,
)
from kubernetes.client.rest import ApiException

# Mock Kubernetes configuration before importing the main module
with (
    patch("kubernetes.config.load_incluster_config"),
    patch("kubernetes.config.load_kube_config"),
    patch("kubernetes.client.AppsV1Api"),
    patch("kubernetes.client.CoreV1Api"),
    patch("kubernetes.client.NetworkingV1Api"),
):
    from nimbletools_core_operator.main import CoreMCPOperator, delete_mcpservice, operator


class TestCoreMCPOperator:
    """Test the CoreMCPOperator class."""

    @pytest.fixture
    def operator(
        self, mock_k8s_config: Any, mock_k8s_clients: Any
    ) -> Generator[CoreMCPOperator, None, None]:
        """Create operator instance with mocks."""
        yield CoreMCPOperator()

    def test_operator_initialization(self, operator: CoreMCPOperator) -> None:
        """Test operator initializes correctly."""
        assert isinstance(operator, CoreMCPOperator)
        assert hasattr(operator, "operator_namespace")
        assert hasattr(operator, "control_plane_service")
        # Verify the control plane service is discovered on init
        assert operator.control_plane_service == (
            "nimbletools-core-control-plane",
            "nimbletools-system",
            8080,
        )

    def test_is_valid_namespace(self, operator: CoreMCPOperator) -> None:
        """Test namespace validation."""
        assert operator.is_valid_namespace("ws-test") is True
        assert operator.is_valid_namespace("kube-system") is False
        assert operator.is_valid_namespace("default") is False

    def test_detect_deployment_type(self, operator: CoreMCPOperator) -> None:
        """Test deployment type detection.

        With MCPB, all deployments are HTTP-based. stdio servers use the
        supergateway runtime which wraps stdio as HTTP.
        """
        # Test streamable-http transport -> http deployment
        http_spec = {"packages": [{"transport": {"type": "streamable-http"}}]}
        assert operator.detect_deployment_type(http_spec) == "http"

        # Test sse transport -> error
        sse_spec = {"packages": [{"transport": {"type": "sse"}}]}
        with pytest.raises(ValueError, match="SSE transport type is not supported"):
            operator.detect_deployment_type(sse_spec)

        # Test default (no packages/transport specified)
        empty_spec: dict[str, Any] = {}
        assert operator.detect_deployment_type(empty_spec) == "http"

    def test_create_configmap(self, operator: CoreMCPOperator) -> None:
        """Test ConfigMap creation with proper Kubernetes models."""
        config_data = {"test": "value"}
        result = operator.create_configmap("test-service", config_data, "test-namespace")

        assert isinstance(result, V1ConfigMap)
        assert result.metadata.name == "test-service-config"
        assert result.metadata.namespace == "test-namespace"
        assert "app" in result.metadata.labels
        assert result.metadata.labels["app"] == "test-service"
        assert "config.yaml" in result.data

    def test_create_service(self, operator: CoreMCPOperator) -> None:
        """Test Service creation with proper Kubernetes models."""
        spec = {"container": {"port": 9000}}
        result = operator.create_service("test-service", spec, "test-namespace")

        assert isinstance(result, V1Service)
        assert result.metadata.name == "test-service-service"
        assert result.metadata.namespace == "test-namespace"
        assert result.spec.selector["app"] == "test-service"
        assert result.spec.ports[0].port == 9000
        assert result.spec.ports[0].target_port == "http"

    def test_create_service_default_port(self, operator: CoreMCPOperator) -> None:
        """Test Service creation with default port."""
        spec: dict[str, Any] = {}
        result = operator.create_service("test-service", spec, "test-namespace")

        assert result.spec.ports[0].port == 8000  # Default port

    def test_create_env_vars_from_environment(self, operator: CoreMCPOperator) -> None:
        """Test environment variable creation."""
        env_dict = {"VAR1": "value1", "VAR2": "value2"}
        result = operator._create_env_vars_from_environment(env_dict)

        assert len(result) == 2
        assert all(isinstance(env_var, V1EnvVar) for env_var in result)
        assert result[0].name == "VAR1"
        assert result[0].value == "value1"
        assert result[1].name == "VAR2"
        assert result[1].value == "value2"

    def test_create_env_vars_empty_environment(self, operator: CoreMCPOperator) -> None:
        """Test environment variable creation with empty dict."""
        result = operator._create_env_vars_from_environment({})
        assert result == []

    def test_create_env_vars_from_packages_with_default_field(
        self, operator: CoreMCPOperator
    ) -> None:
        """Test that 'default' field is supported for third-party compatibility."""
        packages = [
            {
                "environmentVariables": [
                    {
                        "name": "LOG_LEVEL",
                        "default": "info",
                        "isRequired": False,
                    },
                    {
                        "name": "DEBUG_MODE",
                        "value": "false",
                        "isRequired": False,
                    },
                ]
            }
        ]
        # Mock methods to isolate the test
        with (
            patch.object(operator, "_get_workspace_secret_keys", return_value=set()),
            patch.object(operator, "_select_package_for_cluster", return_value=None),
        ):
            env_vars = operator._create_env_vars_from_packages(
                packages, "test-namespace", "test-server"
            )

        assert len(env_vars) == 2
        assert env_vars[0].name == "LOG_LEVEL"
        assert env_vars[0].value == "info"
        assert env_vars[1].name == "DEBUG_MODE"
        assert env_vars[1].value == "false"

    def test_create_env_vars_from_packages_value_takes_precedence(
        self, operator: CoreMCPOperator
    ) -> None:
        """Test that 'value' takes precedence over 'default' if both are present."""
        packages = [
            {
                "environmentVariables": [
                    {
                        "name": "CONFIG",
                        "value": "production",
                        "default": "development",
                        "isRequired": False,
                    }
                ]
            }
        ]
        # Mock methods to isolate the test
        with (
            patch.object(operator, "_get_workspace_secret_keys", return_value=set()),
            patch.object(operator, "_select_package_for_cluster", return_value=None),
        ):
            env_vars = operator._create_env_vars_from_packages(
                packages, "test-namespace", "test-server"
            )

        assert len(env_vars) == 1
        assert env_vars[0].name == "CONFIG"
        assert env_vars[0].value == "production"

    def test_create_env_vars_from_packages_skips_secrets(self, operator: CoreMCPOperator) -> None:
        """Test that variables from workspace-secrets are referenced, not values."""
        packages = [
            {
                "environmentVariables": [
                    {
                        "name": "API_KEY",
                        "isSecret": True,
                        "isRequired": True,
                    },
                    {
                        "name": "LOG_LEVEL",
                        "default": "info",
                        "isSecret": False,
                    },
                ]
            }
        ]
        # Mock API_KEY being in workspace-secrets
        with (
            patch.object(operator, "_get_workspace_secret_keys", return_value={"API_KEY"}),
            patch.object(operator, "_select_package_for_cluster", return_value=None),
        ):
            env_vars = operator._create_env_vars_from_packages(
                packages, "test-namespace", "test-server"
            )

        # Should have both: API_KEY from secret reference, LOG_LEVEL from value
        assert len(env_vars) == 2
        assert env_vars[0].name == "API_KEY"
        assert env_vars[0].value_from is not None  # Secret reference
        assert env_vars[1].name == "LOG_LEVEL"
        assert env_vars[1].value == "info"

    def test_create_env_vars_from_packages_extracts_bundle_url(
        self, operator: CoreMCPOperator
    ) -> None:
        """Test that BUNDLE_URL is extracted from selected package identifier."""
        packages = [
            {
                "identifier": "https://github.com/org/server/releases/download/v1.0.0/bundle-linux-amd64.tar.gz",
                "environmentVariables": [
                    {
                        "name": "LOG_LEVEL",
                        "default": "info",
                    }
                ],
            }
        ]
        # Mock _select_package_for_cluster to return the package with identifier
        with (
            patch.object(operator, "_get_workspace_secret_keys", return_value=set()),
            patch.object(operator, "_select_package_for_cluster", return_value=packages[0]),
        ):
            env_vars = operator._create_env_vars_from_packages(
                packages, "test-namespace", "test-server"
            )

        # Should have BUNDLE_URL first, then LOG_LEVEL
        assert len(env_vars) == 2
        assert env_vars[0].name == "BUNDLE_URL"
        assert (
            env_vars[0].value
            == "https://github.com/org/server/releases/download/v1.0.0/bundle-linux-amd64.tar.gz"
        )
        assert env_vars[1].name == "LOG_LEVEL"
        assert env_vars[1].value == "info"

    def test_select_package_for_cluster_prefers_matching_architecture(
        self, operator: CoreMCPOperator
    ) -> None:
        """Test that _select_package_for_cluster selects package matching cluster arch."""
        packages = [
            {
                "identifier": "https://example.com/bundle-linux-arm64.tar.gz",
                "environmentVariables": [],
            },
            {
                "identifier": "https://example.com/bundle-linux-amd64.tar.gz",
                "environmentVariables": [],
            },
        ]
        # Mock cluster with amd64 architecture
        with patch.object(operator, "_get_cluster_architectures", return_value={"amd64"}):
            selected = operator._select_package_for_cluster(packages, "test-server")

        assert selected is not None
        assert selected["identifier"] == "https://example.com/bundle-linux-amd64.tar.gz"

    def test_select_package_for_cluster_selects_arm64_for_arm_cluster(
        self, operator: CoreMCPOperator
    ) -> None:
        """Test that _select_package_for_cluster selects arm64 package for arm cluster."""
        packages = [
            {
                "identifier": "https://example.com/bundle-linux-amd64.tar.gz",
                "environmentVariables": [],
            },
            {
                "identifier": "https://example.com/bundle-linux-arm64.tar.gz",
                "environmentVariables": [],
            },
        ]
        # Mock cluster with arm64 architecture
        with patch.object(operator, "_get_cluster_architectures", return_value={"arm64"}):
            selected = operator._select_package_for_cluster(packages, "test-server")

        assert selected is not None
        assert selected["identifier"] == "https://example.com/bundle-linux-arm64.tar.gz"

    def test_select_package_for_cluster_raises_error_on_arch_mismatch(
        self, operator: CoreMCPOperator
    ) -> None:
        """Test that _select_package_for_cluster raises ValueError when no arch matches."""
        packages = [
            {
                "identifier": "https://example.com/bundle-linux-arm64.tar.gz",
                "environmentVariables": [],
            },
        ]
        # Mock cluster with amd64 architecture only
        with patch.object(operator, "_get_cluster_architectures", return_value={"amd64"}):
            with pytest.raises(ValueError, match="No compatible package"):
                operator._select_package_for_cluster(packages, "test-server")

    def test_select_package_for_cluster_falls_back_when_arch_unknown(
        self, operator: CoreMCPOperator
    ) -> None:
        """Test that _select_package_for_cluster falls back to amd64 preference when arch unknown."""
        packages = [
            {
                "identifier": "https://example.com/bundle-linux-arm64.tar.gz",
                "environmentVariables": [],
            },
            {
                "identifier": "https://example.com/bundle-linux-amd64.tar.gz",
                "environmentVariables": [],
            },
        ]
        # Mock cluster architecture detection failure (returns empty set)
        with patch.object(operator, "_get_cluster_architectures", return_value=set()):
            selected = operator._select_package_for_cluster(packages, "test-server")

        # Should prefer amd64 when arch is unknown
        assert selected is not None
        assert selected["identifier"] == "https://example.com/bundle-linux-amd64.tar.gz"

    def test_select_package_for_cluster_returns_none_for_no_identifiers(
        self, operator: CoreMCPOperator
    ) -> None:
        """Test that _select_package_for_cluster returns None when packages have no identifiers."""
        packages = [
            {
                "environmentVariables": [{"name": "LOG_LEVEL", "default": "info"}],
            }
        ]
        result = operator._select_package_for_cluster(packages, "test-server")
        assert result is None

    def test_get_cluster_architectures_success(self, operator: CoreMCPOperator) -> None:
        """Test _get_cluster_architectures returns architectures from node labels."""
        # Create mock nodes with architecture labels
        mock_node1 = MagicMock()
        mock_node1.metadata.labels = {"kubernetes.io/arch": "amd64"}
        mock_node2 = MagicMock()
        mock_node2.metadata.labels = {"kubernetes.io/arch": "arm64"}
        mock_node3 = MagicMock()
        mock_node3.metadata.labels = {"kubernetes.io/arch": "amd64"}  # Duplicate

        mock_node_list = MagicMock()
        mock_node_list.items = [mock_node1, mock_node2, mock_node3]

        with patch.object(operator.k8s_core, "list_node", return_value=mock_node_list):
            archs = operator._get_cluster_architectures()

        assert archs == {"amd64", "arm64"}

    def test_get_cluster_architectures_handles_api_error(self, operator: CoreMCPOperator) -> None:
        """Test _get_cluster_architectures returns empty set on API error."""
        with patch.object(
            operator.k8s_core,
            "list_node",
            side_effect=ApiException(status=403, reason="Forbidden"),
        ):
            archs = operator._get_cluster_architectures()

        assert archs == set()

    def test_create_deployment(self, operator: CoreMCPOperator) -> None:
        """Test deployment creation calls the HTTP deployment method."""
        spec = {"container": {"image": "test-image"}}

        with patch.object(operator, "_create_http_deployment") as mock_method:
            mock_deployment = MagicMock(spec=V1Deployment)
            mock_method.return_value = mock_deployment

            result = operator.create_deployment("test", spec, "test-ns")

            mock_method.assert_called_once_with("test", spec, "test-ns")
            assert result == mock_deployment

    def test_http_deployment_missing_image(self, operator: CoreMCPOperator) -> None:
        """Test HTTP deployment raises error when container image is missing."""
        spec: dict[str, Any] = {"container": {}}  # No image specified

        with pytest.raises(ValueError, match="HTTP service 'test' missing container.image"):
            operator._create_http_deployment("test", spec, "test-ns")

    def test_create_http_deployment(self, operator: CoreMCPOperator) -> None:
        """Test HTTP deployment creation."""
        spec = {
            "container": {"image": "test-image:latest", "port": 9000},
            "environment": {"HTTP_VAR": "http-value"},
            "replicas": 3,
        }

        result = operator._create_http_deployment("test-service", spec, "test-ns")

        assert isinstance(result, V1Deployment)
        assert result.metadata.name == "test-service-deployment"
        assert result.metadata.namespace == "test-ns"
        assert result.spec.replicas == 3

        container = result.spec.template.spec.containers[0]
        assert container.name == "test-service"
        assert container.image == "docker.io/test-image:latest"
        assert len(container.env) == 1  # Only custom environment variables
        assert container.env[0].name == "HTTP_VAR"
        assert container.env[0].value == "http-value"

    def test_create_service_ingress(self, operator: CoreMCPOperator) -> None:
        """Test ingress creation for workspace services."""
        spec = {"container": {"port": 9000}}

        result = operator.create_service_ingress(
            "test-service", spec, "test-namespace", "workspace-123"
        )

        assert isinstance(result, V1Ingress)
        assert result.metadata.name == "test-service-ingress"
        assert result.metadata.namespace == "test-namespace"
        assert result.metadata.labels["mcp.nimbletools.dev/workspace_id"] == "workspace-123"
        assert result.metadata.labels["mcp.nimbletools.dev/server_id"] == "test-service"

        # Check ingress rules
        assert len(result.spec.rules) == 1
        rule = result.spec.rules[0]
        assert rule.host == f"mcp.{os.getenv('DOMAIN', 'nimbletools.dev')}"
        assert len(rule.http.paths) == 1
        path = rule.http.paths[0]
        assert path.path == "/workspace-123/test-service/mcp"
        assert path.backend.service.name == "test-service-service"
        assert path.backend.service.port.number == 9000

    @patch("nimbletools_core_operator.main.k8s_core")
    def test_extract_workspace_id_from_namespace_with_label(
        self, mock_k8s_core: Any, operator: CoreMCPOperator
    ) -> None:
        """Test workspace ID extraction from namespace labels."""
        # Mock namespace with workspace ID label
        mock_namespace = MagicMock()
        mock_namespace.metadata.labels = {"mcp.nimbletools.dev/workspace_id": "workspace-456"}
        mock_k8s_core.read_namespace.return_value = mock_namespace

        result = operator._extract_workspace_id_from_namespace("ws-test")

        assert result == "workspace-456"
        mock_k8s_core.read_namespace.assert_called_once_with("ws-test")

    @patch("nimbletools_core_operator.main.k8s_core")
    def test_extract_workspace_id_from_namespace_fallback(
        self, mock_k8s_core: Any, operator: CoreMCPOperator
    ) -> None:
        """Test workspace ID extraction fallback from namespace name pattern."""
        # Mock namespace without workspace ID label
        mock_namespace = MagicMock()
        mock_namespace.metadata.labels = {}
        mock_k8s_core.read_namespace.return_value = mock_namespace

        # Test with valid UUID pattern - need exactly 36 characters
        result = operator._extract_workspace_id_from_namespace(
            "ws-name-abcd-12345678-1234-1234-1234-123456789abc"
        )

        assert result == "12345678-1234-1234-1234-123456789abc"

    @patch("nimbletools_core_operator.main.k8s_core")
    def test_extract_workspace_id_none_cases(
        self, mock_k8s_core: Any, operator: CoreMCPOperator
    ) -> None:
        """Test workspace ID extraction returns None for invalid cases."""
        mock_namespace = MagicMock()
        mock_namespace.metadata.labels = {}
        mock_k8s_core.read_namespace.return_value = mock_namespace

        # Test with short namespace name (less than 6 parts)
        result = operator._extract_workspace_id_from_namespace("ws-short")
        assert result is None

        # Test with non-ws namespace
        result = operator._extract_workspace_id_from_namespace("regular-namespace")
        assert result is None

        # Test with ws namespace but UUID too short (not 36 chars)
        result = operator._extract_workspace_id_from_namespace(
            "ws-name-abcd-1234-1234-1234-1234-123456789"
        )
        assert result is None

        # Test with ws namespace but UUID too long (not 36 chars)
        result = operator._extract_workspace_id_from_namespace(
            "ws-name-abcd-12345678-1234-1234-1234-123456789abcd"
        )
        assert result is None

    @patch("nimbletools_core_operator.main.k8s_core")
    def test_extract_workspace_id_exception_handling(
        self, mock_k8s_core: Any, operator: CoreMCPOperator
    ) -> None:
        """Test workspace ID extraction handles exceptions."""
        mock_k8s_core.read_namespace.side_effect = Exception("API Error")

        result = operator._extract_workspace_id_from_namespace("ws-test")

        assert result is None

    def test_additional_namespace_validation_cases(self, operator: CoreMCPOperator) -> None:
        """Test additional namespace validation cases."""
        # Test all system namespaces
        system_namespaces = [
            "kube-system",
            "kube-public",
            "kube-node-lease",
            "default",
            "ingress-nginx",
            "cert-manager",
        ]

        for ns in system_namespaces:
            assert operator.is_valid_namespace(ns) is False

        # Test valid namespaces
        valid_namespaces = ["ws-test", "my-app", "prod-env", "staging"]
        for ns in valid_namespaces:
            assert operator.is_valid_namespace(ns) is True

    def test_deployment_type_edge_cases(self, operator: CoreMCPOperator) -> None:
        """Test deployment type detection edge cases."""
        # Test with packages but no transport
        spec_no_transport: dict[str, Any] = {"packages": [{}]}
        assert operator.detect_deployment_type(spec_no_transport) == "http"

        # Test with streamable-http (should return http)
        spec_http = {
            "packages": [
                {"transport": {"type": "streamable-http"}},
            ]
        }
        assert operator.detect_deployment_type(spec_http) == "http"

        # Test with nested structure but no packages
        spec_nested = {"other": {"nested": "value"}}
        assert operator.detect_deployment_type(spec_nested) == "http"

    def test_http_deployment_defaults(self, operator: CoreMCPOperator) -> None:
        """Test HTTP deployment with default values."""
        spec = {
            "container": {
                "image": "test-image:latest"
                # No port specified to test default
            }
            # No replicas, resources_config, or environment to test defaults
        }

        result = operator._create_http_deployment("test", spec, "test-ns")

        # Check defaults
        assert result.spec.replicas == 1  # Default replicas
        container = result.spec.template.spec.containers[0]
        assert container.ports[0].container_port == 8000  # Default port
        assert len(container.env) == 0  # No environment vars by default

        # Check default resource requirements
        assert container.resources.requests["cpu"] == "50m"
        assert container.resources.limits["memory"] == "256Mi"

    def test_http_deployment_with_ghcr_registry(self, operator: CoreMCPOperator) -> None:
        """Test HTTP deployment constructs correct image path for GitHub Container Registry."""
        spec = {
            "container": {
                "image": "github/github-mcp-server",
                "registry": "https://ghcr.io",
            }
        }

        result = operator._create_http_deployment("test", spec, "test-ns")

        container = result.spec.template.spec.containers[0]
        assert container.image == "ghcr.io/github/github-mcp-server"

    def test_http_deployment_with_dockerhub_default(self, operator: CoreMCPOperator) -> None:
        """Test HTTP deployment defaults to docker.io when no registry specified."""
        spec = {
            "container": {
                "image": "myorg/myimage",
            }
        }

        result = operator._create_http_deployment("test", spec, "test-ns")

        container = result.spec.template.spec.containers[0]
        assert container.image == "docker.io/myorg/myimage"

    def test_http_deployment_strips_protocol_from_registry(self, operator: CoreMCPOperator) -> None:
        """Test HTTP deployment strips http/https protocol from registry URL."""
        spec = {
            "container": {
                "image": "company/image",
                "registry": "http://registry.example.com",
            }
        }

        result = operator._create_http_deployment("test", spec, "test-ns")

        container = result.spec.template.spec.containers[0]
        assert container.image == "registry.example.com/company/image"

    def test_ingress_default_port(self, operator: CoreMCPOperator) -> None:
        """Test ingress creation with default port."""
        spec: dict[str, Any] = {"container": {}}  # No port specified

        result = operator.create_service_ingress("test-service", spec, "test-ns", "workspace-789")

        path = result.spec.rules[0].http.paths[0]
        assert path.backend.service.port.number == 8000  # Default port

    def test_http_deployment_with_custom_resources(self, operator: CoreMCPOperator) -> None:
        """Test HTTP deployment with custom resource requirements."""
        spec = {
            "container": {"image": "test:latest"},
            "resources": {
                "requests": {"cpu": "200m", "memory": "512Mi"},
                "limits": {"cpu": "1000m", "memory": "1Gi"},
            },
        }

        result = operator._create_http_deployment("test", spec, "test-ns")

        container = result.spec.template.spec.containers[0]
        assert container.resources.requests["cpu"] == "200m"
        assert container.resources.limits["memory"] == "1Gi"

    @patch("nimbletools_core_operator.main.k8s_core")
    def test_extract_workspace_id_with_none_labels(
        self, mock_k8s_core: Any, operator: CoreMCPOperator
    ) -> None:
        """Test workspace ID extraction when namespace has None labels."""
        mock_namespace = MagicMock()
        mock_namespace.metadata.labels = None  # Explicitly None
        mock_k8s_core.read_namespace.return_value = mock_namespace

        result = operator._extract_workspace_id_from_namespace("ws-test")

        # Should still check fallback pattern
        assert result is None  # Since "ws-test" doesn't match UUID pattern

    def test_http_deployment_security_context(self, operator: CoreMCPOperator) -> None:
        """Test HTTP deployment has correct security context."""
        spec = {"container": {"image": "test:latest"}}

        result = operator._create_http_deployment("test", spec, "test-ns")

        # Check pod security context
        pod_security = result.spec.template.spec.security_context
        assert pod_security.run_as_non_root is True
        assert pod_security.run_as_user == 1000
        assert pod_security.fs_group == 1000

        # Check container security context
        container_security = result.spec.template.spec.containers[0].security_context
        assert container_security.run_as_non_root is True
        assert container_security.capabilities.drop == ["ALL"]

    def test_http_deployment_default_probe_timings(self, operator: CoreMCPOperator) -> None:
        """Test HTTP deployment uses sensible default probe timings."""
        spec = {"container": {"image": "test:latest"}}

        result = operator._create_http_deployment("test", spec, "test-ns")

        container = result.spec.template.spec.containers[0]

        # Default probe timings optimized for fast-starting MCPB bundles
        assert container.liveness_probe.initial_delay_seconds == 10
        assert container.liveness_probe.period_seconds == 10
        assert container.liveness_probe.timeout_seconds == 5
        assert container.liveness_probe.failure_threshold == 3
        assert container.readiness_probe.initial_delay_seconds == 5
        assert container.readiness_probe.period_seconds == 5
        assert container.readiness_probe.timeout_seconds == 5
        assert container.readiness_probe.failure_threshold == 3

    def test_http_deployment_custom_probe_config(self, operator: CoreMCPOperator) -> None:
        """Test HTTP deployment respects custom probe configuration from container config."""
        spec = {
            "container": {
                "image": "test:latest",
                "healthCheck": {
                    "interval": 30,
                    "timeout": 10,
                    "retries": 5,
                },
                "startupProbe": {
                    "initialDelaySeconds": 60,
                    "periodSeconds": 15,
                    "failureThreshold": 10,
                },
            }
        }

        result = operator._create_http_deployment("test", spec, "test-ns")

        container = result.spec.template.spec.containers[0]

        # Custom probe timings from container config
        assert container.liveness_probe.initial_delay_seconds == 60
        assert container.liveness_probe.period_seconds == 30
        assert container.liveness_probe.timeout_seconds == 10
        assert container.liveness_probe.failure_threshold == 5
        assert container.readiness_probe.initial_delay_seconds == 60
        assert container.readiness_probe.period_seconds == 30
        assert container.readiness_probe.timeout_seconds == 10
        assert container.readiness_probe.failure_threshold == 5

    def test_ingress_annotations_configuration(self, operator: CoreMCPOperator) -> None:
        """Test ingress has correct nginx annotations."""
        spec = {"container": {"port": 9000}}

        result = operator.create_service_ingress("test", spec, "test-ns", "ws-123")

        annotations = result.metadata.annotations

        # Check key nginx annotations
        assert annotations["nginx.ingress.kubernetes.io/priority"] == "1000"
        assert annotations["nginx.ingress.kubernetes.io/ssl-redirect"] == "false"
        assert annotations["nginx.ingress.kubernetes.io/rewrite-target"] == "/mcp"
        assert annotations["nginx.ingress.kubernetes.io/proxy-buffering"] == "off"
        # Configuration snippet was removed due to ingress controller security restrictions
        assert "nginx.ingress.kubernetes.io/configuration-snippet" not in annotations

    def test_ingress_auth_url_uses_discovered_service(self, operator: CoreMCPOperator) -> None:
        """Test that ingress auth-url annotation uses the discovered control-plane service."""
        spec = {"container": {"port": 8000}}

        result = operator.create_service_ingress("test", spec, "test-ns", "ws-123")

        annotations = result.metadata.annotations

        # Verify the auth-url uses the discovered service details
        service_name, service_ns, service_port = operator.control_plane_service
        expected_auth_url = (
            f"http://{service_name}.{service_ns}.svc.cluster.local:{service_port}/v1/token_auth"
        )
        assert "nginx.ingress.kubernetes.io/auth-url" in annotations
        assert annotations["nginx.ingress.kubernetes.io/auth-url"] == expected_auth_url

        # Also check other auth-related annotations are present
        assert "nginx.ingress.kubernetes.io/auth-response-headers" in annotations
        assert "nginx.ingress.kubernetes.io/auth-cache-key" in annotations
        assert "nginx.ingress.kubernetes.io/auth-cache-duration" in annotations


class TestServiceDiscovery:
    """Test control-plane service discovery functionality."""

    def test_discover_control_plane_service_success(
        self, mock_k8s_config: Any, mock_k8s_clients: Any
    ) -> None:
        """Test successful control-plane service discovery."""
        with patch("nimbletools_core_operator.main.client.CoreV1Api") as mock_core_api:
            # Setup mock service
            mock_service_list = MagicMock()
            mock_service = MagicMock()
            mock_service.metadata.name = "test-release-control-plane"
            mock_service.metadata.namespace = "custom-namespace"
            mock_service.spec.ports = [MagicMock(port=9090)]
            mock_service_list.items = [mock_service]

            mock_core_instance = MagicMock()
            mock_core_instance.list_namespaced_service.return_value = mock_service_list
            mock_core_api.return_value = mock_core_instance

            operator = CoreMCPOperator()

            # Verify discovered service details
            assert operator.control_plane_service == (
                "test-release-control-plane",
                "custom-namespace",
                9090,
            )

            # Verify API was called with correct label selector
            mock_core_instance.list_namespaced_service.assert_called_once()
            call_args = mock_core_instance.list_namespaced_service.call_args
            assert call_args.kwargs["label_selector"] == "app.kubernetes.io/component=control-plane"

    def test_discover_control_plane_service_not_found(self, mock_k8s_config: Any) -> None:
        """Test service discovery fails when control-plane service not found."""
        with patch("nimbletools_core_operator.main.client.CoreV1Api") as mock_core_api:
            # Setup mock with empty service list
            mock_service_list = MagicMock()
            mock_service_list.items = []  # No services found

            mock_core_instance = MagicMock()
            mock_core_instance.list_namespaced_service.return_value = mock_service_list
            mock_core_api.return_value = mock_core_instance

            # Should raise RuntimeError with descriptive message
            with pytest.raises(RuntimeError, match="Control plane service not found"):
                CoreMCPOperator()

    def test_discover_control_plane_service_api_exception(self, mock_k8s_config: Any) -> None:
        """Test service discovery handles API exceptions."""
        with patch("nimbletools_core_operator.main.client.CoreV1Api") as mock_core_api:
            # Setup mock to raise ApiException
            mock_core_instance = MagicMock()
            mock_core_instance.list_namespaced_service.side_effect = ApiException(
                status=403, reason="Forbidden"
            )
            mock_core_api.return_value = mock_core_instance

            # Should raise RuntimeError with RBAC hint
            with pytest.raises(RuntimeError, match="Check RBAC permissions"):
                CoreMCPOperator()

    def test_ingress_uses_custom_release_service(self, mock_k8s_config: Any) -> None:
        """Test ingress creation uses service from custom Helm release."""
        with patch("nimbletools_core_operator.main.client.CoreV1Api") as mock_core_api:
            # Setup mock service with custom release name
            mock_service_list = MagicMock()
            mock_service = MagicMock()
            mock_service.metadata.name = "staging-nimbletools-core-control-plane"
            mock_service.metadata.namespace = "staging-namespace"
            mock_service.spec.ports = [MagicMock(port=8080)]
            mock_service_list.items = [mock_service]

            mock_core_instance = MagicMock()
            mock_core_instance.list_namespaced_service.return_value = mock_service_list
            mock_core_api.return_value = mock_core_instance

            operator = CoreMCPOperator()

            # Create ingress and verify it uses the discovered service
            spec = {"container": {"port": 8000}}
            result = operator.create_service_ingress("test", spec, "test-ns", "ws-123")

            annotations = result.metadata.annotations
            expected_auth_url = "http://staging-nimbletools-core-control-plane.staging-namespace.svc.cluster.local:8080/v1/token_auth"
            assert annotations["nginx.ingress.kubernetes.io/auth-url"] == expected_auth_url


class TestGlobalOperator:
    """Test global operator instantiation and module-level functionality."""

    def test_global_operator_exists(self) -> None:
        """Test that global operator instance is created."""
        assert operator is not None
        assert isinstance(operator, CoreMCPOperator)


class TestDeleteHandler:
    """Test the delete_mcpservice handler for proper error handling."""

    @pytest.mark.asyncio
    async def test_delete_mcpservice_handles_exceptions_gracefully(self) -> None:
        """Test that delete handler doesn't raise exceptions, allowing finalizer removal."""
        # Mock logger
        mock_logger = MagicMock()

        # Mock the Kubernetes API clients to raise exceptions
        with (
            patch("nimbletools_core_operator.main.k8s_core") as mock_core,
            patch("nimbletools_core_operator.main.k8s_apps") as mock_apps,
            patch("nimbletools_core_operator.main.client.NetworkingV1Api") as mock_networking_api,
        ):
            # Create a mock networking client instance
            mock_networking = MagicMock()
            mock_networking_api.return_value = mock_networking

            # Simulate various failure scenarios
            # 404 errors (resources already deleted) - should be handled gracefully
            mock_networking.delete_namespaced_ingress.side_effect = ApiException(status=404)
            mock_core.delete_namespaced_service.side_effect = ApiException(status=404)
            mock_apps.delete_namespaced_deployment.side_effect = ApiException(status=404)
            mock_core.delete_namespaced_config_map.side_effect = ApiException(status=404)

            # Call the handler - it should NOT raise an exception
            await delete_mcpservice(
                name="test-service",
                namespace="ws-test-namespace",
                logger=mock_logger,
            )

            # Verify no exceptions were raised (test passes if we get here)
            # Verify appropriate logging occurred
            assert mock_logger.info.called
            assert not mock_logger.error.called  # No errors for 404s

    @pytest.mark.asyncio
    async def test_delete_mcpservice_handles_unexpected_exceptions(self) -> None:
        """Test that delete handler handles unexpected exceptions without raising."""
        # Mock logger
        mock_logger = MagicMock()

        with (
            patch("nimbletools_core_operator.main.k8s_core") as mock_core,
            patch("nimbletools_core_operator.main.client.NetworkingV1Api") as mock_networking_api,
        ):
            # Create a mock networking client instance
            mock_networking = MagicMock()
            mock_networking_api.return_value = mock_networking

            # Simulate unexpected exception during deletion
            mock_core.delete_namespaced_service.side_effect = Exception("Unexpected error")

            # Call the handler - it should NOT raise an exception
            await delete_mcpservice(
                name="test-service",
                namespace="ws-test-namespace",
                logger=mock_logger,
            )

            # Verify the error was logged but not raised
            mock_logger.error.assert_called_once()
            error_message = mock_logger.error.call_args[0][0]
            assert "non-fatal" in error_message
            assert "test-service" in error_message

    @pytest.mark.asyncio
    async def test_delete_mcpservice_mixed_success_and_failure(self) -> None:
        """Test that delete handler continues deletion even when some resources fail."""
        # Mock logger
        mock_logger = MagicMock()

        with (
            patch("nimbletools_core_operator.main.k8s_core") as mock_core,
            patch("nimbletools_core_operator.main.k8s_apps") as mock_apps,
            patch("nimbletools_core_operator.main.client.NetworkingV1Api") as mock_networking_api,
        ):
            # Create a mock networking client instance
            mock_networking = MagicMock()
            mock_networking_api.return_value = mock_networking

            # Mix of successes and failures
            mock_networking.delete_namespaced_ingress.return_value = None  # Success
            mock_core.delete_namespaced_service.side_effect = ApiException(
                status=500
            )  # Server error
            mock_apps.delete_namespaced_deployment.return_value = None  # Success
            mock_core.delete_namespaced_config_map.side_effect = ApiException(
                status=404
            )  # Not found

            # Call the handler - it should NOT raise an exception
            await delete_mcpservice(
                name="test-service",
                namespace="ws-test-namespace",
                logger=mock_logger,
            )

            # Verify all delete operations were attempted
            mock_networking.delete_namespaced_ingress.assert_called_once()
            mock_core.delete_namespaced_service.assert_called_once()
            mock_apps.delete_namespaced_deployment.assert_called_once()
            mock_core.delete_namespaced_config_map.assert_called_once()

            # Verify appropriate logging
            assert mock_logger.warning.called  # Warning for 500 error
            assert mock_logger.info.called  # Info for successful deletions


class TestImagePullPolicy:
    """Test _determine_image_pull_policy helper function."""

    @pytest.fixture
    def operator(
        self, mock_k8s_config: Any, mock_k8s_clients: Any
    ) -> Generator[CoreMCPOperator, None, None]:
        """Create operator instance with mocks."""
        yield CoreMCPOperator()

    def test_pull_policy_for_latest_tag(self, operator: CoreMCPOperator) -> None:
        """Test that :latest tag uses 'Always' pull policy."""
        assert operator._determine_image_pull_policy("docker.io/myapp:latest") == "Always"

    def test_pull_policy_for_edge_tag(self, operator: CoreMCPOperator) -> None:
        """Test that :edge tag uses 'Always' pull policy."""
        assert operator._determine_image_pull_policy("docker.io/myapp:edge") == "Always"

    def test_pull_policy_for_dev_tag(self, operator: CoreMCPOperator) -> None:
        """Test that :dev tag uses 'Always' pull policy."""
        assert operator._determine_image_pull_policy("ghcr.io/org/myapp:dev") == "Always"

    def test_pull_policy_for_semantic_version(self, operator: CoreMCPOperator) -> None:
        """Test that semantic version tags use 'IfNotPresent' pull policy."""
        assert operator._determine_image_pull_policy("docker.io/myapp:1.0.1") == "IfNotPresent"
        assert operator._determine_image_pull_policy("docker.io/myapp:v2.3.4") == "IfNotPresent"
        assert operator._determine_image_pull_policy("docker.io/myapp:0.1.0-rc.1") == "IfNotPresent"

    def test_pull_policy_for_no_tag(self, operator: CoreMCPOperator) -> None:
        """Test that images without explicit tag default to 'Always' (implies :latest)."""
        assert operator._determine_image_pull_policy("docker.io/myapp") == "Always"

    def test_pull_policy_for_main_branch_tag(self, operator: CoreMCPOperator) -> None:
        """Test that :main branch tag uses 'Always' pull policy."""
        assert operator._determine_image_pull_policy("docker.io/myapp:main") == "Always"

    def test_pull_policy_for_staging_tag(self, operator: CoreMCPOperator) -> None:
        """Test that :staging tag uses 'Always' pull policy."""
        assert operator._determine_image_pull_policy("docker.io/myapp:staging") == "Always"

    def test_http_deployment_uses_smart_pull_policy(self, operator: CoreMCPOperator) -> None:
        """Test that HTTP deployment uses the determined pull policy."""
        # Test with :latest tag - should use Always
        spec_latest = {"container": {"image": "myapp:latest"}}
        result_latest = operator._create_http_deployment("test", spec_latest, "test-ns")
        assert result_latest.spec.template.spec.containers[0].image_pull_policy == "Always"

        # Test with semantic version - should use IfNotPresent
        spec_version = {"container": {"image": "myapp:1.0.1"}}
        result_version = operator._create_http_deployment("test", spec_version, "test-ns")
        assert result_version.spec.template.spec.containers[0].image_pull_policy == "IfNotPresent"
