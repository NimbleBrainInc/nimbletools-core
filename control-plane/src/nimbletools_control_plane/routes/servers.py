"""
Server Router for NimbleTools Control Plane
"""

import logging
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from kubernetes import client
from kubernetes.client.rest import ApiException

from nimbletools_control_plane.auth import create_auth_provider
from nimbletools_control_plane.exceptions import (
    convert_to_http_exception,
    handle_optional_kubernetes_resource,
    log_operation_start,
    log_operation_success,
)
from nimbletools_control_plane.k8s_utils import get_user_registry_namespaces
from nimbletools_control_plane.middlewares import create_workspace_access_validator
from nimbletools_control_plane.models import (
    ServerDeleteResponse,
    ServerDeployRequest,
    ServerDeployResponse,
    ServerDetailsResponse,
    ServerListResponse,
    ServerScaleRequest,
    ServerScaleResponse,
    ServerSummary,
)
from nimbletools_control_plane.schema_validator import (
    validate_mcpservice_spec,
    validate_registry_server_spec,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/workspaces", tags=["servers"])
auth_provider = create_auth_provider()


async def _find_server_in_registries(server_id: str, owner: str) -> tuple[dict[str, Any] | None, str | None]:
    """Find server specification in user's registries"""
    registry_namespaces = await get_user_registry_namespaces(owner)

    for namespace_info in registry_namespaces:
        registry_namespace = namespace_info["name"]
        registry_name = namespace_info["registry_name"]

        try:
            # Get registry ConfigMap from this namespace
            configmap_name = f"{registry_name}-registry"
            configmap = client.CoreV1Api().read_namespaced_config_map(
                name=configmap_name, namespace=registry_namespace
            )

            # Parse registry data from ConfigMap
            registry_yaml = configmap.data.get("registry.yaml")
            if registry_yaml:
                registry_data = yaml.safe_load(registry_yaml)
                servers = registry_data.get("servers", [])

                # Find the server
                for server in servers:
                    if server.get("name") == server_id and server.get("status") == "active":
                        return server, registry_name

        except ApiException as e:
            if e.status != 404:
                logger.error("Error reading registry ConfigMap from namespace %s: %s", registry_namespace, e)

    return None, None


def _create_mcpservice_spec(server_id: str, server_spec: dict[str, Any], server_request: ServerDeployRequest, workspace_id: str, namespace_name: str, found_registry: str) -> dict[str, Any]:
    """Create MCPService specification from registry server spec and request"""
    container_spec = server_spec.get("container", {})
    deployment_spec = server_spec.get("deployment", {})

    return {
        "apiVersion": "mcp.nimbletools.dev/v1",
        "kind": "MCPService",
        "metadata": {
            "name": server_id,
            "namespace": namespace_name,
            "labels": {
                "mcp.nimbletools.dev/workspace": workspace_id,
                "mcp.nimbletools.dev/service": "true",
                "mcp.nimbletools.dev/registry": found_registry,
            },
            "annotations": {
                "mcp.nimbletools.dev/version": server_spec.get("version", "unknown"),
                "mcp.nimbletools.dev/description": server_spec.get("meta", {}).get("description", server_id),
            },
        },
        "spec": {
            "deployment": deployment_spec,
            "container": {
                "image": container_spec.get("image", "unknown"),
                "registry": container_spec.get("registry", "docker.io"),
                "port": container_spec.get("port", 8000)
            },
            "replicas": server_request.replicas,
            "timeout": server_request.timeout,
            "environment": server_request.environment,
            "credentials": server_spec.get("credentials", []),
            "tools": server_spec.get("tools", []),
            "mcp_resources": server_spec.get("mcp_resources", []),
            "prompts": server_spec.get("prompts", []),
            "resources": server_spec.get("resources", {}),
            "routing": {
                "path": f"/services/{server_id}",
                "port": container_spec.get("port", 8000),
                "healthPath": deployment_spec.get("healthPath", "/health"),
                "discoveryPath": "/mcp/discover",
                **server_request.routing
            },
            "scaling": {
                "minReplicas": 0,
                "maxReplicas": 10,
                "targetConcurrency": 10,
                "scaleDownDelay": "5m",
                **server_request.scaling
            },
        },
    }


def _debug_log_mcpservice_creation(server_id: str, mcpservice: dict[str, Any]) -> None:
    """Debug logging for MCPService creation"""
    # Debug: Log the MCPService we're about to create
    logger.error("DEBUG: MCPService spec before validation: %s", mcpservice["spec"])
    logger.error("DEBUG: Credentials in MCPService spec: %s", mcpservice["spec"].get("credentials", "MISSING"))


def _debug_log_mcpservice_post_validation(mcpservice: dict[str, Any]) -> None:
    """Debug logging after MCPService validation"""
    logger.error("DEBUG: MCPService spec after validation: %s", mcpservice["spec"])


def _debug_log_created_mcpservice(server_id: str, k8s_custom: client.CustomObjectsApi, namespace_name: str) -> None:
    """Debug logging for created MCPService verification"""
    try:
        created_mcpservice = k8s_custom.get_namespaced_custom_object(
            group="mcp.nimbletools.dev",
            version="v1",
            namespace=namespace_name,
            plural="mcpservices",
            name=server_id,
        )
        logger.error("DEBUG: Created MCPService spec: %s", created_mcpservice.get("spec", {}))
        logger.error("DEBUG: Created MCPService credentials: %s", created_mcpservice.get("spec", {}).get("credentials", "MISSING"))
    except Exception as e:
        logger.error("DEBUG: Failed to read back created MCPService: %s", e)


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
    namespace_name: str = Depends(create_workspace_access_validator("workspace_id")),
) -> ServerListResponse:
    """List servers - authentication handled by dependency"""

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
        k8s_apps = client.AppsV1Api()

        for mcpservice in mcpservices.get("items", []):
            server_name = mcpservice.get("metadata", {}).get("name")
            spec = mcpservice.get("spec", {})
            status = mcpservice.get("status", {})

            # Get actual deployment status since MCPService status might not be populated
            deployment_status = "Unknown"
            try:
                deployment = k8s_apps.read_namespaced_deployment(
                    name=f"{server_name}-deployment",
                    namespace=namespace_name
                )
                if deployment.status.ready_replicas and deployment.status.ready_replicas > 0:
                    deployment_status = "Running"
                elif deployment.status.replicas and deployment.status.replicas > 0:
                    deployment_status = "Pending"
                else:
                    deployment_status = "Unknown"
            except Exception:
                # Deployment doesn't exist or error reading it
                deployment_status = status.get("phase", "Unknown")

            servers.append(
                ServerSummary(
                    id=server_name,
                    name=server_name,
                    workspace_id=workspace_id,
                    namespace=namespace_name,
                    image=spec.get("container", {}).get("image", ""),
                    status=deployment_status,
                    replicas=spec.get("replicas", 0),
                    created=mcpservice.get("metadata", {}).get("creationTimestamp"),
                )
            )

        result = ServerListResponse(
            servers=servers,
            workspace_id=workspace_id,
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
    server_request: ServerDeployRequest,
    request: Request,
    namespace_name: str = Depends(create_workspace_access_validator("workspace_id")),
) -> ServerDeployResponse:
    """Deploy server - authentication handled by dependency"""

    try:
        logger.error("DEBUG: Starting server deployment for workspace %s", workspace_id)

        server_id = server_request.server_id.strip()

        if not server_id:
            logger.error("Server ID validation failed")
            raise HTTPException(status_code=400, detail="server_id is required")

        log_operation_start("deploying server", "server", server_id)

        # Get authenticated user
        auth_provider = create_auth_provider()

        user_context = await auth_provider.authenticate(request)

        owner = (
            user_context.get("user_id", "community-user")
            if user_context
            else "community-user"
        )

        # Search for server in user's registries
        server_spec, found_registry = await _find_server_in_registries(server_id, owner)

        if not server_spec or not found_registry:
            logger.error("Server %s not found in any registry", server_id)
            raise HTTPException(
                status_code=404, detail=f"Server '{server_id}' not found in registry"
            )

        logger.info("Deploying server %s from registry %s to workspace %s", server_id, found_registry, workspace_id)

        # Debug: Log what we got from registry
        credentials_from_registry = server_spec.get("credentials", [])
        logger.error("DEBUG: Registry credentials for %s: %s", server_id, credentials_from_registry)

        # Validate registry server spec has required fields
        validate_registry_server_spec(server_spec, server_id)

        # Create MCPService based on registry spec
        mcpservice = _create_mcpservice_spec(server_id, server_spec, server_request, workspace_id, namespace_name, found_registry)

        _debug_log_mcpservice_creation(server_id, mcpservice)

        # Validate MCPService against CRD schema before creation
        validate_mcpservice_spec(mcpservice, server_id)

        _debug_log_mcpservice_post_validation(mcpservice)

        # Create MCPService in workspace
        k8s_custom = client.CustomObjectsApi()
        k8s_custom.create_namespaced_custom_object(
            group="mcp.nimbletools.dev",
            version="v1",
            namespace=namespace_name,
            plural="mcpservices",
            body=mcpservice,
        )

        _debug_log_created_mcpservice(server_id, k8s_custom, namespace_name)

        return ServerDeployResponse(
            server_id=server_id,
            workspace_id=workspace_id,
            namespace=namespace_name,
            status="deployed",
            message=f"Server {server_id} deployed successfully",
            service_endpoint=f"/{workspace_id}/{server_id}/mcp",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error deploying server to workspace %s: %s", workspace_id, e)
        # Return detailed error for debugging
        raise HTTPException(
            status_code=500,
            detail=f"Deployment error: {e!s} (Type: {type(e).__name__})",
        ) from e


@router.get("/{workspace_id}/servers/{server_id}")
async def get_workspace_server(
    workspace_id: str,
    server_id: str,
    request: Request,
    namespace_name: str = Depends(create_workspace_access_validator("workspace_id")),
) -> ServerDetailsResponse:
    """Get server details - authentication handled by dependency"""

    try:
        log_operation_start("reading server details", "server", server_id)
        k8s_custom = client.CustomObjectsApi()

        # Get MCPService
        mcpservice = k8s_custom.get_namespaced_custom_object(
            group="mcp.nimbletools.dev",
            version="v1",
            namespace=namespace_name,
            plural="mcpservices",
            name=server_id,
        )

        # Get Deployment status (optional - may not exist yet)
        deployment = await get_deployment_if_exists(
            f"{server_id}-deployment", namespace_name
        )

        # Get Service (optional - may not exist yet)
        service = await get_service_if_exists(f"{server_id}-service", namespace_name)

        spec = mcpservice.get("spec", {})
        status = mcpservice.get("status", {})

        return ServerDetailsResponse(
            id=server_id,
            name=server_id,
            workspace_id=workspace_id,
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
                    f"/{workspace_id}/{server_id}/mcp"
                    if service
                    else None
                ),
            },
            created=mcpservice.get("metadata", {}).get("creationTimestamp"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Error getting server %s in workspace %s: %s", server_id, workspace_id, e
        )
        raise convert_to_http_exception(e, default_status_code=500) from e


@router.post("/{workspace_id}/servers/{server_id}/scale")
async def scale_workspace_server(
    workspace_id: str,
    server_id: str,
    scale_request: ServerScaleRequest,
    namespace_name: str = Depends(create_workspace_access_validator("workspace_id")),
) -> ServerScaleResponse:
    """Scale server - authentication handled by dependency"""

    try:
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
            name=server_id,
            body=patch_body,
        )

        return ServerScaleResponse(
            server_id=server_id,
            workspace_id=workspace_id,
            replicas=replicas,
            status="scaled",
            message=f"Server {server_id} scaled to {replicas} replicas",
        )

    except HTTPException:
        # Re-raise HTTPExceptions (including 404) as-is
        raise
    except Exception as e:
        logger.error(
            "Error scaling server %s in workspace %s: %s", server_id, workspace_id, e
        )
        raise HTTPException(status_code=500, detail=f"Error scaling server: {e!s}")


@router.delete("/{workspace_id}/servers/{server_id}")
async def remove_workspace_server(
    workspace_id: str,
    server_id: str,
    request: Request,
    namespace_name: str = Depends(create_workspace_access_validator("workspace_id")),
) -> ServerDeleteResponse:
    """Remove server - authentication handled by dependency"""

    try:
        k8s_custom = client.CustomObjectsApi()

        # Delete the ingress first
        # Delete the MCPService - operator will handle cleanup of all resources
        k8s_custom.delete_namespaced_custom_object(
            group="mcp.nimbletools.dev",
            version="v1",
            namespace=namespace_name,
            plural="mcpservices",
            name=server_id,
        )

        return ServerDeleteResponse(
            server_id=server_id,
            workspace_id=workspace_id,
            namespace=namespace_name,
            status="removed",
            message=f"Server {server_id} removed successfully",
        )

    except HTTPException:
        # Re-raise HTTPExceptions (including 404) as-is
        raise
    except Exception as e:
        logger.error(
            "Error removing server %s from workspace %s: %s", server_id, workspace_id, e
        )
        raise HTTPException(status_code=500, detail=f"Error removing server: {e!s}")
