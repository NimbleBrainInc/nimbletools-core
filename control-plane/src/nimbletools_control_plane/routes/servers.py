"""
Server Router for NimbleTools Control Plane
"""

import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID as UUID_cls

from fastapi import APIRouter, Depends, HTTPException, Request
from kubernetes import client
from kubernetes.client.rest import ApiException

from nimbletools_control_plane.auth import get_workspace_namespace
from nimbletools_control_plane.exceptions import (
    KubernetesOperationError,
    convert_to_http_exception,
    handle_optional_kubernetes_resource,
    log_operation_start,
    log_operation_success,
)
from nimbletools_control_plane.mcp_server_models import MCPServer
from nimbletools_control_plane.models import (
    LogLevel,
    ServerDeleteResponse,
    ServerDeployResponse,
    ServerDetailsResponse,
    ServerListResponse,
    ServerLogEntry,
    ServerLogsRequest,
    ServerLogsResponse,
    ServerRestartRequest,
    ServerRestartResponse,
    ServerScaleRequest,
    ServerScaleResponse,
    ServerSummary,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/workspaces", tags=["servers"])


def _extract_container_config(mcp_server: MCPServer) -> dict[str, Any]:
    """Extract container configuration from MCP server definition"""
    container_config = {
        "image": "unknown",
        "registry": "docker.io",
        "port": 8000,
    }

    # Extract image from packages if available
    if mcp_server.packages:
        for package in mcp_server.packages:
            if package.registryType == "oci":
                # Construct full image reference with version tag
                image_identifier = package.identifier
                image_version = package.version
                container_config["image"] = f"{image_identifier}:{image_version}"

                if package.registryBaseUrl:
                    container_config["registry"] = package.registryBaseUrl
                break

    # Override port with runtime config if available
    runtime = mcp_server.nimbletools_runtime
    if (
        runtime
        and runtime.container
        and runtime.container.healthCheck
        and runtime.container.healthCheck.port
    ):
        container_config["port"] = runtime.container.healthCheck.port

    return container_config


def _build_resources_config(runtime: Any) -> dict[str, Any]:
    """Build resource requirements from runtime config"""
    if not runtime or not runtime.resources:
        return {}

    return {
        "requests": {
            "cpu": runtime.resources.requests.cpu,
            "memory": runtime.resources.requests.memory,
        },
        "limits": {
            "cpu": runtime.resources.limits.cpu,
            "memory": runtime.resources.limits.memory,
        },
    }


def _build_scaling_config(runtime: Any, user_scaling: dict[str, Any] | None) -> dict[str, Any]:
    """Build scaling configuration"""
    default_scaling = {
        "minReplicas": 0,
        "maxReplicas": 10,
        "targetConcurrency": 10,
        "scaleDownDelay": "5m",
    }

    if runtime and runtime.scaling:
        default_scaling.update(
            {
                "minReplicas": runtime.scaling.minReplicas,
                "maxReplicas": runtime.scaling.maxReplicas,
                "enabled": runtime.scaling.enabled,
            }
        )

    if user_scaling:
        default_scaling.update(user_scaling)

    return default_scaling


def _build_labels_and_annotations(
    mcp_server: MCPServer, workspace_id: str, runtime: Any
) -> tuple[dict[str, str], dict[str, str]]:
    """Build labels and annotations for the MCPService"""
    # Build labels
    labels = {
        "mcp.nimbletools.dev/workspace": workspace_id,
        "mcp.nimbletools.dev/service": "true",
        "mcp.nimbletools.dev/server-name": mcp_server.name.replace("/", "-"),
    }

    # Add categories as labels
    if runtime and runtime.registry and runtime.registry.categories:
        for i, category in enumerate(runtime.registry.categories[:3]):
            labels[f"mcp.nimbletools.dev/category-{i}"] = category

    # Build annotations
    annotations = {
        "mcp.nimbletools.dev/version": mcp_server.version,
        "mcp.nimbletools.dev/description": mcp_server.description,
        "mcp.nimbletools.dev/status": mcp_server.status,
    }

    if mcp_server.repository:
        annotations["mcp.nimbletools.dev/repository"] = str(mcp_server.repository.url)

    if runtime and runtime.registry and runtime.registry.tags:
        annotations["mcp.nimbletools.dev/tags"] = ",".join(runtime.registry.tags)

    return labels, annotations


def _serialize_packages(packages: list[Any] | None) -> list[dict[str, Any]]:
    """Safely serialize packages to dict format"""
    if not packages:
        logger.info("No packages to serialize")
        return []

    try:
        serialized = [
            pkg.model_dump(exclude_none=False, by_alias=False, mode="python") for pkg in packages
        ]
        logger.info("Serialized %d packages successfully", len(serialized))
        return serialized
    except Exception as e:
        logger.error("Failed to serialize packages: %s", e)
        return []


def _create_mcpservice_spec_from_mcp_server(
    mcp_server: MCPServer,
    workspace_id: str,
    namespace_name: str,
    replicas: int = 1,
    environment: dict[str, str] | None = None,
    timeout: int = 300,
    scaling: dict[str, Any] | None = None,
    routing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create MCPService specification from MCP server definition"""
    server_id = mcp_server.name.split("/")[-1]
    runtime = mcp_server.nimbletools_runtime

    # Extract configurations using helper functions
    container_config = _extract_container_config(mcp_server)
    resources = _build_resources_config(runtime)
    default_scaling = _build_scaling_config(runtime, scaling)
    labels, annotations = _build_labels_and_annotations(mcp_server, workspace_id, runtime)

    # Build routing config with health path and MCP endpoint path
    health_path = "/health"
    health_check_enabled = True
    mcp_path = "/mcp"  # Default MCP endpoint path

    if runtime and runtime.container and runtime.container.healthCheck:
        health_path = runtime.container.healthCheck.path
        health_check_enabled = runtime.container.healthCheck.enabled

    # Read MCP endpoint path from deployment config if available
    if (
        runtime
        and hasattr(runtime, "deployment")
        and runtime.deployment
        and hasattr(runtime.deployment, "mcpPath")
    ):
        mcp_path = runtime.deployment.mcpPath

    default_routing = {
        "path": f"/services/{server_id}",
        "port": container_config["port"],
        "healthPath": health_path,
        "healthCheck": health_check_enabled,
        "mcpPath": mcp_path,
        "discoveryPath": "/mcp/discover",
    }
    if routing:
        default_routing.update(routing)

    return {
        "apiVersion": "mcp.nimbletools.dev/v1",
        "kind": "MCPService",
        "metadata": {
            "name": server_id,
            "namespace": namespace_name,
            "labels": labels,
            "annotations": annotations,
        },
        "spec": {
            "container": container_config,
            "replicas": replicas,
            "timeout": timeout,
            "packages": _serialize_packages(mcp_server.packages),
            "tools": [],
            "mcp_resources": [],
            "prompts": [],
            "resources": resources,
            "routing": default_routing,
            "scaling": default_scaling,
        },
    }


@handle_optional_kubernetes_resource("reading", "deployment", default_value=None)  # type: ignore[misc]
async def get_deployment_if_exists(name: str, namespace: str) -> Any:
    """Get deployment if it exists, return None if not found"""
    k8s_apps = client.AppsV1Api()
    return k8s_apps.read_namespaced_deployment(name=name, namespace=namespace)


@handle_optional_kubernetes_resource("reading", "service", default_value=None)  # type: ignore[misc]
async def get_service_if_exists(name: str, namespace: str) -> Any:
    """Get service if it exists, return None if not found"""
    k8s_core = client.CoreV1Api()
    return k8s_core.read_namespaced_service(name=name, namespace=namespace)


@router.get("/{workspace_id}/servers")
async def list_workspace_servers(
    workspace_id: str,
    request: Request,
    namespace_name: str = Depends(get_workspace_namespace),
) -> ServerListResponse:
    """List servers deployed in a workspace"""

    try:
        log_operation_start("listing servers", "workspace", workspace_id)
        k8s_custom = client.CustomObjectsApi()

        # List MCPServices in the workspace namespace
        mcpservices = k8s_custom.list_namespaced_custom_object(
            group="mcp.nimbletools.dev",
            version="v1",
            namespace=namespace_name,
            plural="mcpservices",
        )

        servers = []

        for mcpservice in mcpservices.get("items", []):
            server_name = mcpservice.get("metadata", {}).get("name")
            spec = mcpservice.get("spec", {})
            status = mcpservice.get("status", {})

            # Get actual deployment status
            deployment_status = "Unknown"
            try:
                deployment = await get_deployment_if_exists(
                    f"{server_name}-deployment", namespace_name
                )
                if deployment and deployment.status:
                    ready_replicas = deployment.status.ready_replicas or 0
                    total_replicas = deployment.status.replicas or 0

                    if ready_replicas > 0:
                        deployment_status = "Running"
                    elif total_replicas > 0:
                        deployment_status = "Pending"
                    else:
                        deployment_status = "Stopped"
                else:
                    # Deployment doesn't exist yet, use MCPService status or default to Pending
                    deployment_status = status.get("phase", "Pending")
            except KubernetesOperationError as e:
                # Handle transient Kubernetes API errors gracefully
                logger.warning(
                    "Kubernetes error getting deployment status for server %s: %s",
                    server_name,
                    e.message,
                )
                # Use MCPService status as fallback
                deployment_status = status.get("phase", "Pending")
            except Exception as e:
                # Log unexpected errors but don't fail the entire list operation
                logger.warning(
                    "Unexpected error getting deployment status for server %s: %s", server_name, e
                )
                deployment_status = status.get("phase", "Unknown")

            servers.append(
                ServerSummary(
                    id=server_name,
                    name=server_name,
                    workspace_id=UUID_cls(workspace_id),
                    namespace=namespace_name,
                    image=spec.get("container", {}).get("image", ""),
                    status=deployment_status,
                    replicas=spec.get("replicas", 0),
                    created=mcpservice.get("metadata", {}).get("creationTimestamp"),
                )
            )

        result = ServerListResponse(
            servers=servers,
            workspace_id=UUID_cls(workspace_id),
            namespace=namespace_name,
            total=len(servers),
        )
        log_operation_success("listing servers", "workspace", workspace_id)
        return result

    except Exception as e:
        logger.exception("Error listing servers for workspace %s: %s", workspace_id, e)
        raise convert_to_http_exception(e, default_status_code=500)


@router.post("/{workspace_id}/servers")
async def deploy_server_to_workspace(
    workspace_id: str,
    server_request: dict[str, Any],
    request: Request,
    namespace_name: str = Depends(get_workspace_namespace),
) -> ServerDeployResponse:
    """Deploy server to workspace - accepts MCP server definition from registry"""

    try:
        # The CLI sends the server definition in a "server" field
        mcp_server_data = server_request.get("server", server_request)

        # Create MCP server model
        logger.info(
            "Creating MCPServer from data: packages=%s",
            mcp_server_data.get("packages", "NOT_FOUND"),
        )
        mcp_server = MCPServer(**mcp_server_data)
        logger.info(
            "MCPServer created: packages=%s",
            len(mcp_server.packages) if mcp_server.packages else "None",
        )

        # Extract server ID from name
        server_id = mcp_server.name.split("/")[-1]

        log_operation_start("deploying server", "server", server_id)
        logger.info(
            "Deploying server %s (version %s) to workspace %s",
            mcp_server.name,
            mcp_server.version,
            workspace_id,
        )

        # Check if server is active
        if mcp_server.status != "active":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot deploy server with status '{mcp_server.status}'. Only 'active' servers can be deployed.",
            )

        # Extract optional parameters from request
        replicas = server_request.get("replicas", 1)
        environment = server_request.get("environment", {})
        timeout = server_request.get("timeout", 300)
        scaling = server_request.get("scaling", {})
        routing = server_request.get("routing", {})

        # Create MCPService spec from MCP server definition
        mcpservice = _create_mcpservice_spec_from_mcp_server(
            mcp_server,
            workspace_id,
            namespace_name,
            replicas,
            environment,
            timeout,
            scaling,
            routing,
        )
        logger.info(
            "Created MCPService spec with packages: %s", "packages" in mcpservice.get("spec", {})
        )
        if "packages" in mcpservice.get("spec", {}):
            logger.info("MCPService packages field: %s", len(mcpservice["spec"]["packages"]))

        # Create MCPService in workspace
        k8s_custom = client.CustomObjectsApi()

        # Check if MCPService already exists
        try:
            k8s_custom.get_namespaced_custom_object(
                group="mcp.nimbletools.dev",
                version="v1",
                namespace=namespace_name,
                plural="mcpservices",
                name=server_id,
            )
            # If it exists, update it instead
            logger.info("MCPService %s already exists, updating...", server_id)
            k8s_custom.replace_namespaced_custom_object(
                group="mcp.nimbletools.dev",
                version="v1",
                namespace=namespace_name,
                plural="mcpservices",
                name=server_id,
                body=mcpservice,
            )
            message = f"Server {server_id} updated successfully"
        except ApiException as e:
            if e.status == 404:
                # Create new MCPService
                k8s_custom.create_namespaced_custom_object(
                    group="mcp.nimbletools.dev",
                    version="v1",
                    namespace=namespace_name,
                    plural="mcpservices",
                    body=mcpservice,
                )
                message = f"Server {server_id} deployed successfully"
            else:
                raise

        log_operation_success("deploying server", "server", server_id)

        return ServerDeployResponse(
            server_id=server_id,
            workspace_id=UUID_cls(workspace_id),
            namespace=namespace_name,
            status="pending",
            message=f"{message}. Deployment is being processed by the operator.",
            service_endpoint=f"/{workspace_id}/{server_id}/mcp",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error deploying server: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Deployment error: {e!s}",
        ) from e


def _parse_log_level(level_str: str) -> LogLevel:
    """Parse log level string to LogLevel enum."""
    level_str = level_str.upper()
    if level_str == "WARN":
        return LogLevel.WARNING
    elif level_str == "FATAL":
        return LogLevel.CRITICAL
    elif level_str in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        return LogLevel[level_str]
    return LogLevel.INFO


def _parse_log_line(log_line: str) -> tuple[datetime | None, LogLevel, str]:
    """Parse a log line to extract timestamp, level, and message"""
    # Try to match Kubernetes timestamp format (with no space before log content)
    # Example: 2025-09-29T05:46:08.722799261Z INFO:     10.42.1.1:42920 - "GET /health HTTP/1.1" 200 OK
    k8s_pattern = r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)\s*(\w+):?\s+(.*)$"
    match = re.match(k8s_pattern, log_line)

    if match:
        timestamp_str, level_str, message = match.groups()
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            level = _parse_log_level(level_str)
            return timestamp, level, message
        except (ValueError, KeyError):
            pass

    # Try to match ISO/RFC3339 format with log level in brackets
    iso_pattern = r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s*\[?(\w+)\]?\s+(.*)$"
    match = re.match(iso_pattern, log_line)

    if match:
        timestamp_str, level_str, message = match.groups()
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            level = _parse_log_level(level_str)
            return timestamp, level, message
        except (ValueError, KeyError):
            pass

    # Try to extract just log level from brackets anywhere in line
    level_pattern = r"\[(\w+)\]"
    level_match = re.search(level_pattern, log_line)
    level = _parse_log_level(level_match.group(1)) if level_match else LogLevel.INFO

    return None, level, log_line


def _should_include_log(log_entry: ServerLogEntry, logs_request: ServerLogsRequest) -> bool:
    """Check if a log entry should be included based on filters."""
    # Apply time-based filters
    if logs_request.since and log_entry.timestamp < logs_request.since:
        return False
    if logs_request.until and log_entry.timestamp > logs_request.until:
        return False

    # Apply level filter
    if logs_request.level:
        level_order = {
            LogLevel.DEBUG: 0,
            LogLevel.INFO: 1,
            LogLevel.WARNING: 2,
            LogLevel.ERROR: 3,
            LogLevel.CRITICAL: 4,
        }
        if level_order.get(log_entry.level, 1) < level_order.get(logs_request.level, 1):
            return False

    return True


async def _collect_pod_logs(
    pod: Any,
    k8s_core: client.CoreV1Api,
    logs_request: ServerLogsRequest,
    namespace_name: str,
) -> list[ServerLogEntry]:
    """Collect and parse logs from a single pod."""
    pod_name = pod.metadata.name
    logs: list[ServerLogEntry] = []

    # Skip if filtering by pod and this isn't the one
    if logs_request.pod_name and pod_name != logs_request.pod_name:
        return logs

    # Get container names
    container_names = [c.name for c in pod.spec.containers]

    for container_name in container_names:
        try:
            # Prepare API call parameters
            kwargs: dict[str, Any] = {
                "name": pod_name,
                "namespace": namespace_name,
                "container": container_name,
                "timestamps": True,
                "tail_lines": logs_request.limit * 2,  # Get more for filtering
            }

            # Add time-based filters if provided
            if logs_request.since:
                kwargs["since_seconds"] = int(
                    (datetime.now(UTC) - logs_request.since).total_seconds()
                )

            # Read logs from pod
            log_content = k8s_core.read_namespaced_pod_log(**kwargs)

            logger.debug(
                "Fetched %d bytes of logs from pod %s container %s",
                len(log_content) if log_content else 0,
                pod_name,
                container_name,
            )

            if log_content:
                # Parse each log line
                lines = log_content.strip().split("\n")
                logger.debug("Processing %d log lines", len(lines))

                for line in lines:
                    if not line.strip():
                        continue

                    # Parse the log line
                    timestamp, level, message = _parse_log_line(line)
                    logger.debug(
                        "Parsed line - timestamp: %s, level: %s, message: %s",
                        timestamp,
                        level,
                        message[:50] if message else None,
                    )

                    # Use current time if we couldn't parse timestamp
                    if timestamp is None:
                        timestamp = datetime.now(UTC)

                    # Create log entry
                    log_entry = ServerLogEntry(
                        timestamp=timestamp,
                        level=level,
                        message=message,
                        pod_name=pod_name,
                        container_name=container_name,
                    )

                    # Check if should include based on filters
                    should_include = _should_include_log(log_entry, logs_request)
                    logger.debug(
                        "Should include log entry: %s (filters - since: %s, until: %s, level: %s)",
                        should_include,
                        logs_request.since,
                        logs_request.until,
                        logs_request.level,
                    )
                    if should_include:
                        logs.append(log_entry)

        except ApiException as e:
            logger.warning(
                "Error reading logs from pod %s container %s: %s",
                pod_name,
                container_name,
                e,
            )

    return logs


@router.get("/{workspace_id}/servers/{server_id:path}/logs")
async def get_server_logs(
    workspace_id: str,
    server_id: str,
    request: Request,
    logs_request: ServerLogsRequest = Depends(),
    namespace_name: str = Depends(get_workspace_namespace),
) -> ServerLogsResponse:
    """Get logs for a server deployment"""
    logger.info(
        "Get server logs - workspace_id: %s, server_id: %s, namespace: %s",
        workspace_id,
        server_id,
        namespace_name,
    )
    logger.info(
        "Request params - limit: %s, since: %s, until: %s, level: %s, pod_name: %s",
        logs_request.limit,
        logs_request.since,
        logs_request.until,
        logs_request.level,
        logs_request.pod_name,
    )

    try:
        # Handle both full server names (ai.nimblebrain/echo) and simple IDs (echo)
        actual_server_id = server_id.split("/")[-1] if "/" in server_id else server_id

        log_operation_start("reading server logs", "server", actual_server_id)
        k8s_core = client.CoreV1Api()

        # Get pods for this server
        # The pods are labeled with app=<server_id>, not app=<server_id>-deployment
        label_selector = f"app={actual_server_id}"

        try:
            pods = k8s_core.list_namespaced_pod(
                namespace=namespace_name, label_selector=label_selector
            )
            logger.info(
                "Found %d pods for server %s with label selector %s",
                len(pods.items) if pods.items else 0,
                actual_server_id,
                label_selector,
            )
        except ApiException as e:
            if e.status == 404:
                raise HTTPException(
                    status_code=404, detail=f"Server {server_id} not found or has no running pods"
                )
            raise

        if not pods.items:
            # Return empty logs if no pods
            logger.warning("No pods found for server %s", actual_server_id)
            return ServerLogsResponse(
                version=logs_request.version,
                server_id=actual_server_id,
                workspace_id=UUID_cls(workspace_id),
                logs=[],
                count=0,
                has_more=False,
                query_timestamp=datetime.now(UTC),
            )

        # Collect logs from all pods
        all_logs: list[ServerLogEntry] = []
        for pod in pods.items:
            pod_logs = await _collect_pod_logs(pod, k8s_core, logs_request, namespace_name)
            all_logs.extend(pod_logs)

        # Sort logs by timestamp (newest first)
        all_logs.sort(key=lambda x: x.timestamp, reverse=True)

        # Apply limit
        has_more = len(all_logs) > logs_request.limit
        limited_logs = all_logs[: logs_request.limit]

        log_operation_success("reading server logs", "server", actual_server_id)

        return ServerLogsResponse(
            version=logs_request.version,
            server_id=actual_server_id,
            workspace_id=UUID_cls(workspace_id),
            logs=limited_logs,
            count=len(limited_logs),
            has_more=has_more,
            query_timestamp=datetime.now(UTC),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error getting logs for server %s in workspace %s: %s", server_id, workspace_id, e
        )
        raise HTTPException(status_code=500, detail=f"Error retrieving server logs: {e!s}")


@router.post("/{workspace_id}/servers/{server_id:path}/scale")
async def scale_workspace_server(
    workspace_id: str,
    server_id: str,
    scale_request: ServerScaleRequest,
    namespace_name: str = Depends(get_workspace_namespace),
) -> ServerScaleResponse:
    """Scale server - authentication handled by dependency"""

    try:
        # Handle both full server names (ai.nimblebrain/echo) and simple IDs (echo)
        actual_server_id = server_id.split("/")[-1] if "/" in server_id else server_id

        replicas = scale_request.replicas

        # Scale the server
        k8s_custom = client.CustomObjectsApi()

        # Patch the MCPService to update replicas
        patch_body = {"spec": {"replicas": replicas}}

        k8s_custom.patch_namespaced_custom_object(
            group="mcp.nimbletools.dev",
            version="v1",
            namespace=namespace_name,
            plural="mcpservices",
            name=actual_server_id,
            body=patch_body,
        )

        return ServerScaleResponse(
            server_id=actual_server_id,
            workspace_id=UUID_cls(workspace_id),
            replicas=replicas,
            status="scaled",
            message=f"Server {server_id} scaled to {replicas} replicas",
        )

    except HTTPException:
        # Re-raise HTTPExceptions (including 404) as-is
        raise
    except Exception as e:
        logger.error("Error scaling server %s in workspace %s: %s", server_id, workspace_id, e)
        raise HTTPException(status_code=500, detail=f"Error scaling server: {e!s}")


@router.post("/{workspace_id}/servers/{server_id:path}/restart")
async def restart_workspace_server(
    workspace_id: str,
    server_id: str,
    restart_request: ServerRestartRequest,
    request: Request,
    namespace_name: str = Depends(get_workspace_namespace),
) -> ServerRestartResponse:
    """Restart server deployment - authentication handled by dependency"""

    try:
        # Handle both full server names (ai.nimblebrain/echo) and simple IDs (echo)
        actual_server_id = server_id.split("/")[-1] if "/" in server_id else server_id

        log_operation_start("restarting server", "server", actual_server_id)
        k8s_apps = client.AppsV1Api()

        deployment_name = f"{actual_server_id}-deployment"

        # Check if deployment exists
        try:
            deployment = k8s_apps.read_namespaced_deployment(
                name=deployment_name, namespace=namespace_name
            )
        except ApiException as e:
            if e.status == 404:
                raise HTTPException(
                    status_code=404, detail=f"Server {server_id} not found or not deployed"
                )
            raise

        # Check if force restart is needed
        if not restart_request.force and deployment.status.ready_replicas == 0:
            raise HTTPException(
                status_code=400,
                detail=f"Server {server_id} is not running. Use force=true to restart anyway",
            )

        # Perform rolling restart by updating pod template annotation

        # Get current pod template annotations or create new dict
        pod_template = deployment.spec.template
        pod_annotations = (
            pod_template.metadata.annotations if pod_template.metadata.annotations else {}
        )

        # Add restart annotation with current timestamp to trigger rolling restart
        restart_time = datetime.utcnow().isoformat()
        pod_annotations["kubectl.kubernetes.io/restartedAt"] = restart_time

        # Patch the deployment's pod template to trigger rolling restart
        patch_body = {"spec": {"template": {"metadata": {"annotations": pod_annotations}}}}

        k8s_apps.patch_namespaced_deployment(
            name=deployment_name,
            namespace=namespace_name,
            body=patch_body,
        )

        # Also trigger operator reprocessing by updating MCPService
        # This ensures secrets added after deployment are picked up
        try:
            k8s_custom = client.CustomObjectsApi()
            mcpservice_patch = {
                "metadata": {
                    "annotations": {
                        "kubectl.kubernetes.io/restartedAt": restart_time,
                        "mcp.nimbletools.dev/reprocess-secrets": restart_time,
                    }
                }
            }

            k8s_custom.patch_namespaced_custom_object(
                group="mcp.nimbletools.dev",
                version="v1",
                namespace=namespace_name,
                plural="mcpservices",
                name=actual_server_id,
                body=mcpservice_patch,
            )
            logger.info("Triggered operator reprocessing for server %s", actual_server_id)
        except ApiException as e:
            if e.status == 404:
                logger.warning(
                    "MCPService %s not found, skipping operator reprocessing", actual_server_id
                )
            else:
                logger.warning(
                    "Failed to trigger operator reprocessing for %s: %s", actual_server_id, e
                )
                # Don't fail the restart if MCPService update fails

        log_operation_success("restarting server", "server", actual_server_id)

        return ServerRestartResponse(
            server_id=actual_server_id,
            workspace_id=UUID_cls(workspace_id),
            status="restarting",
            message=f"Server {server_id} restart initiated successfully",
            timestamp=datetime.now(UTC),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error restarting server %s in workspace %s: %s", server_id, workspace_id, e)
        raise HTTPException(status_code=500, detail=f"Error restarting server: {e!s}")


@router.get("/{workspace_id}/servers/{server_id:path}")
async def get_workspace_server(
    workspace_id: str,
    server_id: str,
    request: Request,
    namespace_name: str = Depends(get_workspace_namespace),
) -> ServerDetailsResponse:
    """Get server details"""

    try:
        # Handle both full server names (ai.nimblebrain/echo) and simple IDs (echo)
        # If the server_id contains a slash, extract just the last part
        if "/" in server_id:
            actual_server_id = server_id.split("/")[-1]
            logger.debug(
                "Extracting server ID from full name: %s -> %s", server_id, actual_server_id
            )
        else:
            actual_server_id = server_id

        log_operation_start("reading server details", "server", actual_server_id)
        k8s_custom = client.CustomObjectsApi()

        # Get MCPService
        mcpservice = k8s_custom.get_namespaced_custom_object(
            group="mcp.nimbletools.dev",
            version="v1",
            namespace=namespace_name,
            plural="mcpservices",
            name=actual_server_id,
        )

        # Get Deployment status (optional - may not exist yet)
        deployment = None
        try:
            deployment = await get_deployment_if_exists(
                f"{actual_server_id}-deployment", namespace_name
            )
        except KubernetesOperationError as e:
            logger.warning(
                "Kubernetes error getting deployment for server %s: %s", actual_server_id, e.message
            )
        except Exception as e:
            logger.warning(
                "Unexpected error getting deployment for server %s: %s", actual_server_id, e
            )

        # Get Service (optional - may not exist yet)
        service = None
        try:
            service = await get_service_if_exists(f"{actual_server_id}-service", namespace_name)
        except KubernetesOperationError as e:
            logger.warning(
                "Kubernetes error getting service for server %s: %s", actual_server_id, e.message
            )
        except Exception as e:
            logger.warning(
                "Unexpected error getting service for server %s: %s", actual_server_id, e
            )

        spec = mcpservice.get("spec", {})
        status = mcpservice.get("status", {})

        return ServerDetailsResponse(
            id=actual_server_id,
            name=actual_server_id,
            workspace_id=UUID_cls(workspace_id),
            namespace=namespace_name,
            image=spec.get("container", {}).get("image", ""),
            spec=spec,
            status={
                "phase": status.get("phase", "Unknown"),
                "deployment_ready": (
                    deployment
                    and deployment.status.ready_replicas
                    and deployment.status.ready_replicas > 0
                ),
                "replicas": deployment.status.replicas if deployment else 0,
                "ready_replicas": deployment.status.ready_replicas if deployment else 0,
                "service_endpoint": (
                    f"/{workspace_id}/{actual_server_id}/mcp" if service else None
                ),
            },
            created=mcpservice.get("metadata", {}).get("creationTimestamp"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting server %s in workspace %s: %s", server_id, workspace_id, e)
        raise convert_to_http_exception(e, default_status_code=500) from e


@router.delete("/{workspace_id}/servers/{server_id:path}")
async def remove_workspace_server(
    workspace_id: str,
    server_id: str,
    request: Request,
    namespace_name: str = Depends(get_workspace_namespace),
) -> ServerDeleteResponse:
    """Remove server from workspace"""

    try:
        # Handle both full server names (ai.nimblebrain/echo) and simple IDs (echo)
        actual_server_id = server_id.split("/")[-1] if "/" in server_id else server_id

        log_operation_start("removing server", "server", actual_server_id)
        k8s_custom = client.CustomObjectsApi()

        # Delete the MCPService - operator will handle cleanup of all resources
        k8s_custom.delete_namespaced_custom_object(
            group="mcp.nimbletools.dev",
            version="v1",
            namespace=namespace_name,
            plural="mcpservices",
            name=actual_server_id,
        )

        log_operation_success("removing server", "server", actual_server_id)

        return ServerDeleteResponse(
            server_id=actual_server_id,
            workspace_id=UUID_cls(workspace_id),
            namespace=namespace_name,
            status="removed",
            message=f"Server {server_id} removed successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error removing server %s from workspace %s: %s", server_id, workspace_id, e)
        raise HTTPException(status_code=500, detail=f"Error removing server: {e!s}")
