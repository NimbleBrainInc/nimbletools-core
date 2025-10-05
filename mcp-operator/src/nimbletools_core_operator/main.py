#!/usr/bin/env python3
"""
NimbleTools Core MCP Operator for Kubernetes
"""

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import kopf
import yaml
from kubernetes import client, config
from kubernetes.client.models import (
    V1Capabilities,
    V1ConfigMap,
    V1Container,
    V1ContainerPort,
    V1Deployment,
    V1DeploymentSpec,
    V1EmptyDirVolumeSource,
    V1EnvVar,
    V1HTTPGetAction,
    V1HTTPIngressPath,
    V1HTTPIngressRuleValue,
    V1Ingress,
    V1IngressBackend,
    V1IngressRule,
    V1IngressServiceBackend,
    V1IngressSpec,
    V1LabelSelector,
    V1ObjectMeta,
    V1PodSecurityContext,
    V1PodSpec,
    V1PodTemplateSpec,
    V1Probe,
    V1ResourceRequirements,
    V1SecurityContext,
    V1Service,
    V1ServiceBackendPort,
    V1ServicePort,
    V1ServiceSpec,
    V1Volume,
    V1VolumeMount,
)
from kubernetes.client.rest import ApiException

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Load Kubernetes config
try:
    config.load_incluster_config()
    logger.info("Loaded in-cluster Kubernetes config")
except config.ConfigException:
    config.load_kube_config()
    logger.info("Loaded local Kubernetes config")

# Initialize Kubernetes clients
k8s_apps = client.AppsV1Api()
k8s_core = client.CoreV1Api()
k8s_custom = client.CustomObjectsApi()


class CoreMCPOperator:
    """Core operator for NimbleTools OSS"""

    def __init__(self) -> None:
        # Get operator's own namespace (where control-plane should also be)
        self.operator_namespace = self._get_operator_namespace()
        self.universal_adapter_image = os.getenv(
            "UNIVERSAL_ADAPTER_IMAGE",
            "ghcr.io/nimblebrain/nimbletools-core-universal-adapter:latest",
        )

        # Kubernetes API clients
        self.k8s_core = client.CoreV1Api()
        self.k8s_apps = client.AppsV1Api()

        # Discover control-plane service on startup
        self.control_plane_service = self._discover_control_plane_service()

    def _get_operator_namespace(self) -> str:
        """
        Get the operator's namespace.

        When running in-cluster, reads from the service account namespace file.
        Falls back to environment variable or default for local development.
        """
        # Try to read from service account (in-cluster)
        namespace_path = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
        try:
            with namespace_path.open() as f:
                namespace = f.read().strip()
                logger.info("Detected operator namespace from service account: %s", namespace)
                return namespace
        except FileNotFoundError:
            # Not running in-cluster, use env var or default
            namespace = os.getenv("NAMESPACE", "nimbletools-system")
            logger.info("Using namespace from environment/default: %s", namespace)
            return namespace

    def _discover_control_plane_service(self) -> tuple[str, str, int]:
        """
        Discover control-plane service using label selectors.

        Returns:
            Tuple of (service_name, namespace, port)

        Raises:
            RuntimeError: If service cannot be found or discovered
        """
        try:
            # Search for control-plane service by component label
            services = self.k8s_core.list_namespaced_service(
                namespace=self.operator_namespace,
                label_selector="app.kubernetes.io/component=control-plane",
            )

            if not services.items:
                msg = (
                    "Control plane service not found in namespace %s. "
                    "Ensure the control-plane component is deployed and has label "
                    "'app.kubernetes.io/component=control-plane'"
                )
                logger.error(msg, self.operator_namespace)
                raise RuntimeError(msg % self.operator_namespace)

            service = services.items[0]
            service_name = service.metadata.name
            namespace = service.metadata.namespace
            port = service.spec.ports[0].port

            logger.info(
                "Discovered control-plane service: %s.%s.svc.cluster.local:%d",
                service_name,
                namespace,
                port,
            )

            return (service_name, namespace, port)

        except ApiException as e:
            msg = (
                "Failed to discover control-plane service: %s. "
                "Check RBAC permissions for listing services."
            )
            logger.error(msg, e.reason)
            raise RuntimeError(msg % e.reason) from e

    def is_valid_namespace(self, namespace: str) -> bool:
        """OSS version - simple validation"""
        # Remove complex workspace validation
        # Allow any namespace except system namespaces
        system_namespaces = [
            "kube-system",
            "kube-public",
            "kube-node-lease",
            "default",
            "ingress-nginx",
            "cert-manager",
        ]
        return namespace not in system_namespaces

    def detect_deployment_type(self, spec: dict[str, Any]) -> str:
        """Detect deployment type from service specification"""
        # Check packages for transport type - this determines deployment strategy
        packages = spec.get("packages", [])
        for package in packages:
            transport = package.get("transport", {})
            transport_type = transport.get("type")

            if transport_type == "stdio":
                return "stdio"
            elif transport_type == "streamable-http":
                return "http"
            elif transport_type == "sse":
                raise ValueError(
                    "SSE transport type is not supported. Use 'stdio' or 'streamable-http'."
                )

        # Default to HTTP for no transport specified
        return "http"

    def create_configmap(
        self, name: str, config_data: dict[str, Any], namespace: str
    ) -> V1ConfigMap:
        """Create ConfigMap with service configuration"""
        return V1ConfigMap(
            metadata=V1ObjectMeta(
                name=f"{name}-config",
                namespace=namespace,
                labels={
                    "app": name,
                    "mcp.nimbletools.dev/service": "true",
                    "mcp.nimbletools.dev/managed-by": "nimbletools-core-operator",
                },
            ),
            data={"config.yaml": yaml.dump(config_data, default_flow_style=False)},
        )

    def create_deployment(
        self,
        name: str,
        spec: dict[str, Any],
        namespace: str,
        deployment_type: str,
    ) -> V1Deployment:
        """Create deployment based on type"""
        if deployment_type == "stdio":
            return self._create_universal_adapter_deployment(name, spec, namespace)
        else:
            return self._create_http_deployment(name, spec, namespace)

    def _parse_runtime_arguments(self, runtime_args: list[dict[str, Any] | str]) -> list[str]:
        """Parse runtime arguments from package definition to string list"""
        args = []
        for arg in runtime_args:
            if isinstance(arg, dict):
                arg_type = arg.get("type")
                if arg_type == "positional":
                    value = arg.get("value", "")
                    if value:
                        args.append(value)
                elif arg_type == "named":
                    arg_name = arg.get("name", "")
                    value = arg.get("value", "")
                    if arg_name:
                        args.append(arg_name)
                        if value:
                            args.append(value)
            else:
                args.append(str(arg))
        return args

    def _create_universal_adapter_deployment(
        self, name: str, spec: dict[str, Any], namespace: str
    ) -> V1Deployment:
        """Create deployment using universal adapter for stdio servers"""

        # Extract stdio configuration from packages (standard MCP approach)
        executable = ""
        args = []
        working_dir = "/tmp"

        packages = spec.get("packages", [])
        for package in packages:
            if package.get("transport", {}).get("type") == "stdio":
                # Use runtimeHint and runtimeArguments to construct the command
                runtime_hint = package.get("runtimeHint", "")
                runtime_args = package.get("runtimeArguments", [])

                if runtime_hint:
                    executable = runtime_hint
                    args = self._parse_runtime_arguments(runtime_args)
                break

        # If still no executable, fail with clear error
        if not executable:
            raise ValueError(
                f"No executable found for stdio server '{name}'. "
                "Provide runtimeHint and runtimeArguments in the package definition."
            )

        # Extract capabilities from spec
        tools = spec.get("tools", [])
        mcp_resources = spec.get("mcp_resources", [])
        prompts = spec.get("prompts", [])

        # Get container configuration
        container_config = spec.get("container", {})
        port = container_config.get("port", 8000)

        # Get resource requirements
        resource_config = spec.get("resources", {})
        resources_spec = V1ResourceRequirements(
            requests=resource_config.get("requests", {"cpu": "50m", "memory": "128Mi"}),
            limits=resource_config.get("limits", {"cpu": "200m", "memory": "256Mi"}),
        )

        # Get packages from spec
        packages = spec.get("packages", [])

        # Extract environment variable names to forward to subprocess
        env_var_names = []
        for package in packages:
            for env_var in package.get("environmentVariables", []):
                env_var_names.append(env_var.get("name"))

        # Create environment variables
        env_vars = [
            V1EnvVar(name="MCP_SERVER_NAME", value=name),
            V1EnvVar(name="MCP_EXECUTABLE", value=executable),
            V1EnvVar(name="MCP_ARGS", value=json.dumps(args)),
            V1EnvVar(name="MCP_WORKING_DIR", value=working_dir),
            V1EnvVar(name="MCP_TOOLS", value=json.dumps(tools)),
            V1EnvVar(name="MCP_RESOURCES", value=json.dumps(mcp_resources)),
            V1EnvVar(name="MCP_PROMPTS", value=json.dumps(prompts)),
            V1EnvVar(name="MCP_ENV_VARS", value=json.dumps(env_var_names)),
            V1EnvVar(name="PORT", value=str(port)),
            *self._create_env_vars_from_environment(spec.get("environment", {})),
            *self._create_env_vars_from_packages(packages),
            *self._create_credential_env_vars(packages, namespace),
        ]

        return V1Deployment(
            metadata=V1ObjectMeta(
                name=f"{name}-deployment",
                namespace=namespace,
                labels={
                    "app": name,
                    "mcp.nimbletools.dev/service": "true",
                    "mcp.nimbletools.dev/server": name,
                    "mcp.nimbletools.dev/managed-by": "nimbletools-core-operator",
                    "mcp.nimbletools.dev/deployment-type": "universal-adapter",
                },
            ),
            spec=V1DeploymentSpec(
                replicas=spec.get("replicas", 1),
                selector=V1LabelSelector(match_labels={"app": name}),
                template=V1PodTemplateSpec(
                    metadata=V1ObjectMeta(
                        labels={"app": name, "mcp.nimbletools.dev/service": "true"}
                    ),
                    spec=V1PodSpec(
                        security_context=V1PodSecurityContext(
                            run_as_non_root=True,
                            run_as_user=1000,
                            fs_group=1000,
                        ),
                        containers=[
                            V1Container(
                                name="universal-adapter",
                                image=self.universal_adapter_image,
                                image_pull_policy="IfNotPresent",
                                security_context=V1SecurityContext(
                                    run_as_non_root=True,
                                    run_as_user=1000,
                                    allow_privilege_escalation=False,
                                    read_only_root_filesystem=True,
                                    capabilities=V1Capabilities(drop=["ALL"]),
                                ),
                                ports=[V1ContainerPort(container_port=port, name="http")],
                                resources=resources_spec,
                                env=env_vars,
                                volume_mounts=[V1VolumeMount(name="tmp-volume", mount_path="/tmp")],
                                liveness_probe=V1Probe(
                                    http_get=V1HTTPGetAction(path="/health", port="http"),
                                    initial_delay_seconds=30,
                                    period_seconds=10,
                                    failure_threshold=3,
                                ),
                                readiness_probe=V1Probe(
                                    http_get=V1HTTPGetAction(path="/health", port="http"),
                                    initial_delay_seconds=30,
                                    period_seconds=5,
                                    failure_threshold=3,
                                ),
                            )
                        ],
                        volumes=[V1Volume(name="tmp-volume", empty_dir=V1EmptyDirVolumeSource())],
                    ),
                ),
            ),
        )

    def _create_http_deployment(
        self, name: str, spec: dict[str, Any], namespace: str
    ) -> V1Deployment:
        """Create deployment for HTTP MCP servers"""

        # Get container image
        container_config = spec.get("container", {})
        container_image = container_config.get("image")
        if not container_image:
            raise ValueError(f"HTTP service '{name}' missing container.image")

        # Construct full image path with registry
        registry = container_config.get("registry", "docker.io")
        # Remove protocol prefix if present (e.g., https://ghcr.io -> ghcr.io)
        registry = registry.replace("https://", "").replace("http://", "")
        full_image = f"{registry}/{container_image}"

        port = container_config.get("port", 8000)

        # Get health check path from routing configuration
        routing_config = spec.get("routing", {})
        health_path = routing_config.get("healthPath", "/health")

        # Check if health checks should be disabled (from _meta or routing config)
        health_checks_enabled = routing_config.get("healthCheck", True)
        if not isinstance(health_checks_enabled, bool):
            health_checks_enabled = True

        # Get resource requirements
        resource_config = spec.get("resources", {})
        resources_spec = V1ResourceRequirements(
            requests=resource_config.get("requests", {"cpu": "50m", "memory": "128Mi"}),
            limits=resource_config.get("limits", {"cpu": "200m", "memory": "256Mi"}),
        )

        return V1Deployment(
            metadata=V1ObjectMeta(
                name=f"{name}-deployment",
                namespace=namespace,
                labels={
                    "app": name,
                    "mcp.nimbletools.dev/service": "true",
                    "mcp.nimbletools.dev/server": name,
                    "mcp.nimbletools.dev/managed-by": "nimbletools-core-operator",
                    "mcp.nimbletools.dev/deployment-type": "http",
                },
            ),
            spec=V1DeploymentSpec(
                replicas=spec.get("replicas", 1),
                selector=V1LabelSelector(match_labels={"app": name}),
                template=V1PodTemplateSpec(
                    metadata=V1ObjectMeta(
                        labels={"app": name, "mcp.nimbletools.dev/service": "true"}
                    ),
                    spec=V1PodSpec(
                        security_context=V1PodSecurityContext(
                            run_as_non_root=True,
                            run_as_user=1000,
                            fs_group=1000,
                        ),
                        containers=[
                            V1Container(
                                name=name,
                                image=full_image,
                                image_pull_policy="IfNotPresent",
                                # Use runtimeArguments from package definition to support custom startup args
                                args=self._extract_runtime_args(spec.get("packages", []), port),
                                security_context=V1SecurityContext(
                                    run_as_non_root=True,
                                    run_as_user=1000,
                                    allow_privilege_escalation=False,
                                    read_only_root_filesystem=True,
                                    capabilities=V1Capabilities(drop=["ALL"]),
                                ),
                                ports=[V1ContainerPort(container_port=port, name="http")],
                                resources=resources_spec,
                                env=[
                                    *self._create_env_vars_from_environment(
                                        spec.get("environment", {})
                                    ),
                                    *self._create_env_vars_from_packages(spec.get("packages", [])),
                                    *self._create_credential_env_vars(
                                        spec.get("packages", []), namespace
                                    ),
                                ],
                                volume_mounts=[V1VolumeMount(name="tmp-volume", mount_path="/tmp")],
                                # Only add health checks if enabled
                                liveness_probe=(
                                    V1Probe(
                                        http_get=V1HTTPGetAction(path=health_path, port="http"),
                                        initial_delay_seconds=10,
                                        period_seconds=10,
                                        failure_threshold=3,
                                    )
                                    if health_checks_enabled
                                    else None
                                ),
                                readiness_probe=(
                                    V1Probe(
                                        http_get=V1HTTPGetAction(path=health_path, port="http"),
                                        initial_delay_seconds=2,
                                        period_seconds=3,
                                        failure_threshold=3,
                                    )
                                    if health_checks_enabled
                                    else None
                                ),
                            )
                        ],
                        volumes=[V1Volume(name="tmp-volume", empty_dir=V1EmptyDirVolumeSource())],
                    ),
                ),
            ),
        )

    def _extract_runtime_args(self, packages: list[dict[str, Any]], _port: int) -> list[str]:
        """Extract runtime arguments from package definition for HTTP servers.

        This allows server definitions to specify custom startup arguments.
        If no runtimeArguments are provided, returns empty list (use container's default CMD).
        """
        args = []

        for package in packages:
            runtime_args = package.get("runtimeArguments", [])
            if not runtime_args:
                continue

            # Convert runtime arguments to string list
            for arg in runtime_args:
                if isinstance(arg, dict):
                    arg_type = arg.get("type")
                    if arg_type == "positional":
                        value = arg.get("value", "")
                        if value:
                            args.append(str(value))
                    elif arg_type == "named":
                        name = arg.get("name", "")
                        value = arg.get("value", "")
                        if name:
                            args.append(str(name))
                        if value:
                            args.append(str(value))
                else:
                    args.append(str(arg))

            # Found runtime args, stop looking
            break

        return args

    def _create_env_vars_from_packages(self, packages: list[dict[str, Any]]) -> list[V1EnvVar]:
        """Create environment variables from MCP server packages"""
        env_vars = []

        for package in packages:
            env_variables = package.get("environmentVariables", [])
            for env_var in env_variables:
                name = env_var.get("name")
                if not name:
                    continue

                # If it's a secret, we'll handle it in _create_credential_env_vars
                # Default to False if isSecret is not specified for third-party compatibility
                if env_var.get("isSecret", False):
                    continue

                # Use provided value or default, supporting both fields for third-party compatibility
                # "value" takes precedence over "default" if both are present
                value = env_var.get("value") or env_var.get("default", "")
                env_vars.append(V1EnvVar(name=name, value=value))

        return env_vars

    def _create_credential_env_vars(
        self, packages: list[dict[str, Any]], namespace: str
    ) -> list[V1EnvVar]:
        """Create environment variables for secrets from MCP server packages"""
        env_vars = []

        # Get workspace secrets to check which keys are available
        workspace_secret_keys = self._get_workspace_secret_keys(namespace)

        for package in packages:
            env_variables = package.get("environmentVariables", [])
            for env_var in env_variables:
                name = env_var.get("name")
                if not name or not env_var.get("isSecret", False):
                    continue

                if name in workspace_secret_keys:
                    # Use secret reference for credentials that exist in workspace-secrets
                    env_vars.append(
                        V1EnvVar(
                            name=name,
                            value_from=client.V1EnvVarSource(
                                secret_key_ref=client.V1SecretKeySelector(
                                    name="workspace-secrets",
                                    key=name,
                                    optional=False,  # Secrets should be required
                                )
                            ),
                        )
                    )
                else:
                    logger.warning(
                        f"Required secret environment variable {name} not found in workspace-secrets in namespace {namespace}"
                    )

        return env_vars

    def _create_env_vars_from_environment(self, environment: dict[str, str]) -> list[V1EnvVar]:
        """Create environment variables from a dictionary of environment variables"""
        return [V1EnvVar(name=name, value=value) for name, value in environment.items()]

    def _get_workspace_secret_keys(self, namespace: str) -> set[str]:
        """Get the keys available in workspace-secrets"""
        try:
            secret = self.k8s_core.read_namespaced_secret(
                name="workspace-secrets", namespace=namespace
            )
            return set(secret.data.keys()) if secret.data else set()
        except client.ApiException as e:
            if e.status == 404:
                logger.info(f"No workspace-secrets found in namespace {namespace}")
                return set()
            else:
                logger.warning(f"Failed to read workspace-secrets in {namespace}: {e}")
                return set()

    def create_service(self, name: str, spec: dict[str, Any], namespace: str) -> V1Service:
        """Create Kubernetes Service"""
        container_config = spec.get("container", {})
        port = container_config.get("port", 8000)

        return V1Service(
            metadata=V1ObjectMeta(
                name=f"{name}-service",
                namespace=namespace,
                labels={
                    "app": name,
                    "mcp.nimbletools.dev/service": "true",
                    "mcp.nimbletools.dev/managed-by": "nimbletools-core-operator",
                },
            ),
            spec=V1ServiceSpec(
                selector={"app": name},
                ports=[
                    V1ServicePort(
                        name="http",
                        port=port,
                        target_port="http",
                        protocol="TCP",
                    )
                ],
                type="ClusterIP",
            ),
        )

    def _extract_workspace_id_from_namespace(self, namespace: str) -> str | None:
        """Extract workspace ID from namespace labels"""
        try:
            # Get namespace object to read labels
            ns = k8s_core.read_namespace(namespace)
            labels = ns.metadata.labels or {}

            # Look for workspace ID in labels
            workspace_id = labels.get("mcp.nimbletools.dev/workspace_id")
            if workspace_id:
                return str(workspace_id)

            # Fallback: extract UUID from namespace name pattern (ws-name-uuid)
            if namespace.startswith("ws-") and len(namespace.split("-")) >= 6:
                parts = namespace.split("-")
                # Take last 5 parts as UUID (uuid format: 8-4-4-4-12 chars with dashes)
                potential_uuid = "-".join(parts[-5:])
                if len(potential_uuid) == 36:  # UUID length
                    return potential_uuid

            return None

        except Exception as e:
            logger.error("Failed to extract workspace ID from namespace %s: %s", namespace, e)
            return None

    def create_service_ingress(
        self, name: str, spec: dict[str, Any], namespace: str, workspace_id: str
    ) -> V1Ingress:
        """Create individual ingress for MCP service in workspace"""
        container_config = spec.get("container", {})
        routing_config = spec.get("routing", {})

        # Prefer routing.port over container.port
        port = routing_config.get("port", container_config.get("port", 8000))

        # Get MCP endpoint path from routing config (defaults to /mcp)
        mcp_endpoint = routing_config.get("mcpPath", "/mcp")

        # Create MCP endpoint path: /workspace_id/server_id/mcp
        mcp_path = f"/{workspace_id}/{name}/mcp"

        # Build annotations
        annotations = {
            # High priority for individual service ingresses
            "nginx.ingress.kubernetes.io/priority": "1000",
            "nginx.ingress.kubernetes.io/ssl-redirect": "false",
            "nginx.ingress.kubernetes.io/force-ssl-redirect": "false",
            "nginx.ingress.kubernetes.io/rewrite-target": mcp_endpoint,
            # SSE/Streaming support for MCP protocol
            "nginx.ingress.kubernetes.io/proxy-buffering": "off",
            "nginx.ingress.kubernetes.io/proxy-read-timeout": "3600",
            "nginx.ingress.kubernetes.io/proxy-send-timeout": "3600",
            "nginx.ingress.kubernetes.io/proxy-connect-timeout": "60",
            "nginx.ingress.kubernetes.io/upstream-hash-by": "$request_uri",
        }

        # Core edition returns 200 OK, enterprise editions can implement real auth.
        # Build auth URL from discovered control-plane service
        service_name, service_ns, service_port = self.control_plane_service
        auth_url = (
            f"http://{service_name}.{service_ns}.svc.cluster.local:{service_port}/v1/token_auth"
        )

        annotations.update(
            {
                # Auth validation via control-plane service
                "nginx.ingress.kubernetes.io/auth-url": auth_url,
                "nginx.ingress.kubernetes.io/auth-response-headers": "X-Auth-User-Id,X-Auth-User-Email,X-Auth-Workspace-Id,X-Auth-Scope",
                "nginx.ingress.kubernetes.io/auth-cache-key": "$remote_user$http_authorization",
                "nginx.ingress.kubernetes.io/auth-cache-duration": "200 202 10m, 401 1m",
            }
        )
        logger.info("Configured ingress %s-ingress with auth URL: %s", name, auth_url)

        return V1Ingress(
            metadata=V1ObjectMeta(
                name=f"{name}-ingress",
                namespace=namespace,
                labels={
                    "app": name,
                    "mcp.nimbletools.dev/service": "true",
                    "mcp.nimbletools.dev/managed-by": "nimbletools-core-operator",
                    "mcp.nimbletools.dev/workspace_id": workspace_id,
                    "mcp.nimbletools.dev/server_id": name,
                },
                annotations=annotations,
            ),
            spec=V1IngressSpec(
                ingress_class_name="nginx",
                rules=[
                    V1IngressRule(
                        host=f"mcp.{os.getenv('DOMAIN', 'nimbletools.dev')}",
                        http=V1HTTPIngressRuleValue(
                            paths=[
                                V1HTTPIngressPath(
                                    path=mcp_path,
                                    path_type="Prefix",
                                    backend=V1IngressBackend(
                                        service=V1IngressServiceBackend(
                                            name=f"{name}-service",
                                            port=V1ServiceBackendPort(number=port),
                                        )
                                    ),
                                )
                            ]
                        ),
                    )
                ],
            ),
        )


# Initialize core operator
operator: CoreMCPOperator = CoreMCPOperator()


@kopf.on.create("mcp.nimbletools.dev", "v1", "mcpservices")
async def create_mcpservice(spec, name, namespace, logger, **_kwargs):  # type: ignore
    """Handle MCPService creation using core operator"""
    logger.info(f"Creating MCPService: {name} in namespace: {namespace}")

    # Simple namespace validation for OSS version
    if not operator.is_valid_namespace(namespace):
        error_msg = f"Cannot deploy to system namespace: {namespace}"
        logger.error(error_msg)
        raise kopf.PermanentError(error_msg)

    try:
        # Convert Kopf objects to plain dictionaries and use directly
        spec_for_deployment = dict(spec) if hasattr(spec, "__iter__") else spec
        logger.info(f"Creating MCPService {name} from provided spec (templates generated by CLI)")

        # Detect deployment type
        deployment_type = operator.detect_deployment_type(spec_for_deployment)
        logger.info(f"Detected deployment type: {deployment_type}")

        # Create ConfigMap for HTTP services (stdio uses environment variables)
        if deployment_type != "stdio":
            full_config = {
                "apiVersion": "mcp.nimbletools.dev/v1",
                "kind": "MCPService",
                "metadata": {"name": name},
                "spec": spec_for_deployment,
            }
            configmap_manifest = operator.create_configmap(name, full_config, namespace)
            k8s_core.create_namespaced_config_map(namespace=namespace, body=configmap_manifest)
            logger.info(f"Created ConfigMap for {name}")

        # Create Deployment
        deployment_manifest = operator.create_deployment(
            name, spec_for_deployment, namespace, deployment_type
        )
        k8s_apps.create_namespaced_deployment(namespace=namespace, body=deployment_manifest)
        logger.info(f"Created deployment for {name}")

        # Create Service
        service_manifest = operator.create_service(name, spec_for_deployment, namespace)
        k8s_core.create_namespaced_service(namespace=namespace, body=service_manifest)
        logger.info(f"Created service for {name}")

        # Create individual ingress for MCP runtime (only for workspace namespaces)
        if namespace.startswith("ws-"):
            try:
                # Extract workspace ID from namespace (ws-{workspace_name} -> get UUID from labels)
                workspace_id = operator._extract_workspace_id_from_namespace(namespace)
                if workspace_id:
                    ingress_manifest = operator.create_service_ingress(
                        name, spec_for_deployment, namespace, workspace_id
                    )
                    k8s_networking = client.NetworkingV1Api()
                    k8s_networking.create_namespaced_ingress(
                        namespace=namespace, body=ingress_manifest
                    )
                    logger.info(f"Created individual ingress for {name}")
                else:
                    logger.warning(f"Could not extract workspace_id from namespace {namespace}")
            except Exception as e:
                logger.error(f"Failed to create ingress for {name}: {e}")
                # Don't fail the deployment if ingress creation fails

        return {
            "phase": "Running",
            "namespace": namespace,
            "deploymentType": deployment_type,
            "conditions": [
                {
                    "type": "Ready",
                    "status": "True",
                    "lastTransitionTime": datetime.now(UTC).isoformat(),
                    "reason": "MCPServiceCreated",
                    "message": f"MCP Service {name} created successfully",
                }
            ],
        }

    except Exception as e:
        logger.error(f"Failed to create MCPService {name}: {e}")
        return {
            "phase": "Failed",
            "conditions": [
                {
                    "type": "Ready",
                    "status": "False",
                    "lastTransitionTime": datetime.now(UTC).isoformat(),
                    "reason": "CreationFailed",
                    "message": str(e),
                }
            ],
        }


@kopf.on.delete("mcp.nimbletools.dev", "v1", "mcpservices")
async def delete_mcpservice(name, namespace, logger, **_kwargs):  # type: ignore
    """Handle MCPService deletion"""
    logger.info(f"Deleting MCPService: {name}")

    try:
        # Delete ingress (if it exists in workspace namespace)
        if namespace.startswith("ws-"):
            try:
                k8s_networking = client.NetworkingV1Api()
                k8s_networking.delete_namespaced_ingress(
                    name=f"{name}-ingress", namespace=namespace
                )
                logger.info(f"Deleted ingress for {name}")
            except ApiException as e:
                if e.status != 404:
                    logger.warning(f"Failed to delete ingress for {name}: {e}")

        # Delete Service
        try:
            k8s_core.delete_namespaced_service(name=f"{name}-service", namespace=namespace)
            logger.info(f"Deleted service for {name}")
        except ApiException as e:
            if e.status != 404:
                logger.warning(f"Failed to delete service for {name}: {e}")

        # Delete Deployment
        try:
            k8s_apps.delete_namespaced_deployment(name=f"{name}-deployment", namespace=namespace)
            logger.info(f"Deleted deployment for {name}")
        except ApiException as e:
            if e.status != 404:
                logger.warning(f"Failed to delete deployment for {name}: {e}")

        # Delete ConfigMap
        try:
            k8s_core.delete_namespaced_config_map(name=f"{name}-config", namespace=namespace)
            logger.info(f"Deleted ConfigMap for {name}")
        except ApiException as e:
            if e.status != 404:
                logger.warning(f"Failed to delete ConfigMap for {name}: {e}")

        logger.info(f"Successfully deleted MCPService {name}")

    except Exception as e:
        logger.error(f"Error during MCPService {name} deletion (non-fatal): {e}")
        # Don't raise - allow finalizer to be removed even if cleanup had issues


@kopf.on.update("mcp.nimbletools.dev", "v1", "mcpservices")
async def update_mcpservice(spec, old, name, namespace, logger, **_kwargs):  # type: ignore
    """Handle MCPService updates, particularly scaling operations"""
    logger.info(f"Updating MCPService: {name} in namespace: {namespace}")

    try:
        # Check if replicas field has changed
        old_replicas = old.get("spec", {}).get("replicas", 1)
        new_replicas = spec.get("replicas", 1)

        if old_replicas != new_replicas:
            logger.info(f"Scaling {name} from {old_replicas} to {new_replicas} replicas")

            # Update the deployment with the new replica count
            try:
                deployment = k8s_apps.read_namespaced_deployment(
                    name=f"{name}-deployment", namespace=namespace
                )

                # Update the replica count
                deployment.spec.replicas = new_replicas

                # Apply the update
                k8s_apps.patch_namespaced_deployment(
                    name=f"{name}-deployment", namespace=namespace, body=deployment
                )

                logger.info(f"Successfully scaled {name} to {new_replicas} replicas")

            except ApiException as e:
                logger.error(f"Failed to scale deployment {name}: {e}")
                raise

        return {
            "phase": "Running",
            "conditions": [
                {
                    "type": "Ready",
                    "status": "True",
                    "lastTransitionTime": datetime.now(UTC).isoformat(),
                    "reason": "MCPServiceUpdated",
                    "message": f"MCP Service {name} updated successfully",
                }
            ],
        }

    except Exception as e:
        logger.error(f"Failed to update MCPService {name}: {e}")
        return {
            "phase": "Failed",
            "conditions": [
                {
                    "type": "Ready",
                    "status": "False",
                    "lastTransitionTime": datetime.now(UTC).isoformat(),
                    "reason": "UpdateFailed",
                    "message": str(e),
                }
            ],
        }


def main() -> None:
    """Main entry point for the operator."""

    logger.info("Starting NimbleTools Core MCP Operator...")
    logger.info("Operator is reactive - responds to MCPService resources created by control_plane")

    # Run with health endpoints enabled
    kopf.run(
        clusterwide=True,
        # Enable built-in health endpoints
        liveness_endpoint="http://0.0.0.0:8080/healthz",
    )


if __name__ == "__main__":
    main()
