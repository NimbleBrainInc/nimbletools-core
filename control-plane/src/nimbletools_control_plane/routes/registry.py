"""
Registry Router for NimbleTools Control Plane
"""

import logging
import re
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from kubernetes import client
from kubernetes.client.rest import ApiException

from nimbletools_control_plane.auth import AuthenticatedRequest, create_auth_provider
from nimbletools_control_plane.k8s_utils import get_user_registry_namespaces
from nimbletools_control_plane.middlewares import get_auth_context
from nimbletools_control_plane.models import (
    Registry,
    RegistryEnableRequest,
    RegistryEnableResponse,
    RegistryInfo,
    RegistryListResponse,
    RegistryServersResponse,
    RegistryServerSummary,
)
from nimbletools_control_plane.registry_client import RegistryClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/registry", tags=["registry"])
auth_provider = create_auth_provider()


# Kubernetes clients will be created dynamically to ensure proper config
registry_client = RegistryClient()


@router.get("/servers")
async def list_registry_servers(
    request: Request,
    auth_context: AuthenticatedRequest = Depends(get_auth_context),
) -> RegistryServersResponse:
    """
    List available MCP servers from all registries owned by the user
    Aggregates servers from all registries created by the authenticated user
    """
    try:
        owner = auth_context.user.user_id if auth_context.user else "community-user"
        logger.info("Listing servers for owner: %s", owner)

        # Get all registry namespaces owned by this user
        registry_namespaces = await get_user_registry_namespaces(owner)

        all_servers = []
        registries_info = []

        for namespace_info in registry_namespaces:
            namespace = namespace_info["name"]
            registry_name = namespace_info["registry_name"]
            registry_url = namespace_info.get("registry_url")

            logger.info("Getting servers from registry namespace: %s", namespace)

            try:
                # Get registry ConfigMap from this namespace
                configmap_name = f"{registry_name}-registry"
                configmap = client.CoreV1Api().read_namespaced_config_map(
                    name=configmap_name, namespace=namespace
                )

                # Parse registry data from ConfigMap

                registry_yaml = configmap.data.get("registry.yaml")
                if registry_yaml:
                    registry_data = yaml.safe_load(registry_yaml)
                    servers = registry_data.get("servers", [])
                    active_servers = [s for s in servers if s.get("status") == "active"]

                    # Convert registry servers to server format
                    for server in active_servers:
                        server_dict = _registry_server_to_api_format(
                            server, registry_name, namespace
                        )
                        server_model = RegistryServerSummary(**server_dict)
                        all_servers.append(server_model)

                    registries_info.append(
                        {
                            "name": registry_name,
                            "namespace": namespace,
                            "url": registry_url,
                            "server_count": len(active_servers),
                        }
                    )
                else:
                    logger.warning(
                        "Registry ConfigMap %s has no registry.yaml data",
                        configmap_name,
                    )

            except ApiException as e:
                if e.status != 404:
                    logger.error(
                        "Error getting registry ConfigMap from namespace %s: %s",
                        namespace,
                        e,
                    )
                # Continue with other namespaces

        logger.info(
            "Found %s servers across %s registries",
            len(all_servers),
            len(registries_info),
        )

        return RegistryServersResponse(
            servers=all_servers,
            total=len(all_servers),
            registries=registries_info,
            owner=owner,
        )

    except Exception as e:
        logger.error("Error listing registry servers: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Error listing registry servers: {e!s}"
        ) from e


@router.get("/servers/{server_id}")
async def get_registry_server(
    server_id: str,
    request: Request,
    auth_context: AuthenticatedRequest = Depends(get_auth_context),
) -> dict[str, Any]:
    """
    Get detailed information about a specific server from user's registries
    Searches across all registries owned by the authenticated user
    """
    try:
        owner = auth_context.user.user_id if auth_context.user else "community-user"
        logger.info("Getting server %s for owner: %s", server_id, owner)

        # Get all registry namespaces owned by this user
        registry_namespaces = await get_user_registry_namespaces(owner)

        # Search for the server across all registries
        for namespace_info in registry_namespaces:
            namespace = namespace_info["name"]
            registry_name = namespace_info["registry_name"]

            try:
                # Try to get the MCPService from this namespace
                mcpservice = client.CustomObjectsApi().get_namespaced_custom_object(
                    group="mcp.nimbletools.dev",
                    version="v1",
                    namespace=namespace,
                    plural="mcpservices",
                    name=server_id,
                )

                # Found it! Convert to detailed server format
                server = _mcpservice_to_detailed_server_format(
                    mcpservice, registry_name
                )
                logger.info("Found server %s in registry %s", server_id, registry_name)
                return server

            except ApiException as e:
                if e.status == 404:
                    # Server not in this registry, continue searching
                    continue
                else:
                    logger.error(
                        "Error checking namespace %s for server %s: %s",
                        namespace,
                        server_id,
                        e,
                    )
                    # Continue with other namespaces

        # Server not found in any of the user's registries
        raise HTTPException(
            status_code=404,
            detail=f"Server '{server_id}' not found in any of your registries",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting registry server %s: %s", server_id, e)
        raise HTTPException(
            status_code=500, detail=f"Error getting server information: {e!s}"
        ) from e


@router.post("/")
async def create_registry(
    request: RegistryEnableRequest,
    auth_context: AuthenticatedRequest = Depends(get_auth_context),
) -> RegistryEnableResponse:
    """
    Create a registry from URL and deploy its services
    Creates namespace and deploys all active services from the registry
    """
    try:
        # Fetch registry data
        logger.info("Enabling registry from URL: %s", request.registry_url)
        registry_data = await registry_client.fetch_registry(request.registry_url)

        # Get registry info
        registry_info = registry_client.get_registry_info(registry_data)
        registry_name = registry_info["name"]

        # Determine namespace name
        namespace = request.namespace_override or _sanitize_namespace_name(
            registry_name
        )

        logger.info("Creating namespace: %s", namespace)

        # Create namespace
        owner = auth_context.user.user_id if auth_context.user else "community-user"
        await _create_namespace(namespace, registry_name, request.registry_url, owner)

        # Get active servers
        active_servers = registry_client.get_active_servers(registry_data)

        # Store registry data as ConfigMap (templates only, no actual deployments)
        await _create_registry_configmap(
            namespace, registry_info["name"], registry_data
        )

        created_services = [server.get("name", "unknown") for server in active_servers]

        logger.info(
            "Successfully enabled registry %s: %s service templates stored",
            registry_name,
            len(created_services),
        )

        return RegistryEnableResponse(
            registry_name=registry_name,
            registry_version=registry_info["version"],
            namespace=namespace,
            services_created=len(created_services),
            services=created_services,
        )

    except Exception as e:
        logger.error("Error enabling registry: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Error enabling registry: {e!s}"
        ) from e


@router.get("/info")
async def get_registry_info_endpoint(
    registry_url: str, auth_context: AuthenticatedRequest = Depends(get_auth_context)
) -> RegistryInfo:
    """
    Get information about a registry from its URL
    """
    try:
        # Fetch registry data
        registry_data = await registry_client.fetch_registry(registry_url)

        # Get registry info
        info = registry_client.get_registry_info(registry_data)

        return RegistryInfo(
            name=info["name"],
            version=info["version"],
            url=registry_url,
            last_updated=info["last_updated"],
            total_servers=info["total_servers"],
            active_servers=info["active_servers"],
        )

    except Exception as e:
        logger.error("Error getting registry info: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Error getting registry info: {e!s}"
        ) from e


@router.get("/")
async def list_registries(
    auth_context: AuthenticatedRequest = Depends(get_auth_context),
) -> RegistryListResponse:
    """
    List all registries owned by the authenticated user
    """
    try:
        owner = auth_context.user.user_id if auth_context.user else "community-user"
        logger.info("Listing registries for owner: %s", owner)

        # Get all registry namespaces owned by this user
        registry_namespaces = await get_user_registry_namespaces(owner)

        registries = []
        total_servers = 0

        for namespace_info in registry_namespaces:
            namespace = namespace_info["name"]
            registry_name = namespace_info["registry_name"]
            registry_url = namespace_info.get("registry_url")

            try:
                # Get MCPServices count from this namespace
                mcpservices = client.CustomObjectsApi().list_namespaced_custom_object(
                    group="mcp.nimbletools.dev",
                    version="v1",
                    namespace=namespace,
                    plural="mcpservices",
                )

                server_count = len(mcpservices.get("items", []))
                total_servers += server_count

                # Get namespace creation time
                ns = client.CoreV1Api().read_namespace(namespace)
                created_at = ns.metadata.creation_timestamp

                registries.append(
                    Registry(
                        name=registry_name,
                        namespace=namespace,
                        url=registry_url,
                        server_count=server_count,
                        created_at=created_at,
                        owner=owner,
                    )
                )

            except ApiException as e:
                if e.status != 404:
                    logger.error(
                        "Error getting info for registry namespace %s: %s", namespace, e
                    )
                # Continue with other namespaces

        logger.info(
            "Found %s registries with %s total servers for owner %s",
            len(registries),
            total_servers,
            owner,
        )

        return RegistryListResponse(
            registries=registries,
            total=len(registries),
            total_servers=total_servers,
            owner=owner,
        )

    except Exception as e:
        logger.error("Error listing registries: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Error listing registries: {e!s}"
        ) from e


def _sanitize_namespace_name(name: str) -> str:
    """Sanitize registry name for use as Kubernetes namespace"""
    # Convert to lowercase
    sanitized = name.lower()

    # Replace non-alphanumeric characters with dashes
    sanitized = re.sub(r"[^a-z0-9-]", "-", sanitized)

    # Remove leading/trailing dashes
    sanitized = sanitized.strip("-")

    # Ensure it doesn't start with a dash
    if sanitized.startswith("-"):
        sanitized = sanitized[1:]

    # Add prefix to avoid conflicts
    sanitized = f"registry-{sanitized}"

    # Limit length to 63 characters (k8s limit) - must be after adding prefix
    if len(sanitized) > 63:
        sanitized = sanitized[:63]

    logger.info("Sanitized namespace name: %s -> %s", name, sanitized)
    return sanitized


async def _create_namespace(
    namespace: str, registry_name: str, registry_url: str, owner: str
) -> None:
    """Create Kubernetes namespace for registry"""
    try:
        # Check if namespace already exists
        try:
            client.CoreV1Api().read_namespace(namespace)
            logger.info("Namespace %s already exists", namespace)
            return
        except ApiException as e:
            if e.status != 404:
                raise

        # Create namespace
        namespace_manifest = {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": namespace,
                "labels": {
                    "mcp.nimbletools.dev/registry": "true",
                    "mcp.nimbletools.dev/registry-name": registry_name,
                    "mcp.nimbletools.dev/owner": owner,
                    "mcp.nimbletools.dev/managed-by": "nimbletools-control-plane",
                },
                "annotations": {
                    "mcp.nimbletools.dev/registry-url": registry_url,
                    "mcp.nimbletools.dev/created-by": "control-plane",
                },
            },
        }

        client.CoreV1Api().create_namespace(body=namespace_manifest)
        logger.info("Created namespace: %s", namespace)

    except Exception as e:
        logger.error("Failed to create namespace %s: %s", namespace, e)
        raise


async def _create_mcpservice(mcpservice: dict[str, Any], namespace: str) -> None:
    """Create MCPService custom resource"""
    try:
        service_name = mcpservice["metadata"]["name"]

        # Check if service already exists
        try:
            client.CustomObjectsApi().get_namespaced_custom_object(
                group="mcp.nimbletools.dev",
                version="v1",
                namespace=namespace,
                plural="mcpservices",
                name=service_name,
            )
            logger.info(
                "MCPService %s already exists in namespace %s", service_name, namespace
            )
            return
        except ApiException as e:
            if e.status != 404:
                raise

        # Create MCPService
        client.CustomObjectsApi().create_namespaced_custom_object(
            group="mcp.nimbletools.dev",
            version="v1",
            namespace=namespace,
            plural="mcpservices",
            body=mcpservice,
        )
        logger.info("Created MCPService: %s in namespace %s", service_name, namespace)

    except Exception as e:
        service_name = mcpservice.get("metadata", {}).get("name", "unknown")
        logger.error("Failed to create MCPService %s: %s", service_name, e)
        raise


def _mcpservice_to_server_format(
    mcpservice: dict[str, Any], registry_name: str
) -> dict[str, Any]:
    """Convert MCPService resource to server format for API response"""
    metadata = mcpservice.get("metadata", {})
    spec = mcpservice.get("spec", {})
    status = mcpservice.get("status", {})

    # Extract basic info
    name = metadata.get("name", "unknown")
    namespace = metadata.get("namespace", "unknown")
    labels = metadata.get("labels", {})
    annotations = metadata.get("annotations", {})

    # Get deployment info
    deployment = spec.get("deployment", {})
    container = spec.get("container", {})

    # Get status info
    phase = status.get("phase", "Unknown")
    replicas = status.get("replicas", 0)
    ready_replicas = status.get("readyReplicas", 0)

    # Convert to server format
    server = {
        "id": name,
        "name": annotations.get("mcp.nimbletools.dev/description", name),
        "description": annotations.get(
            "mcp.nimbletools.dev/description", f"{name} MCP service"
        ),
        "image": container.get("image", "unknown"),
        "version": labels.get("mcp.nimbletools.dev/version", "unknown"),
        "status": "running" if phase == "Running" and ready_replicas > 0 else "pending",
        "registry": registry_name,
        "namespace": namespace,
        "deployment": {
            "type": deployment.get("type", "http"),
            "port": container.get("port", 8000),
        },
        "tools": spec.get("tools", []),
        "replicas": {
            "desired": spec.get("replicas", 1),
            "current": replicas,
            "ready": ready_replicas,
        },
        "category": labels.get("mcp.nimbletools.dev/category"),
        "tags": (
            annotations.get("mcp.nimbletools.dev/tags", "").split(",")
            if annotations.get("mcp.nimbletools.dev/tags")
            else []
        ),
    }

    return server


def _mcpservice_to_detailed_server_format(
    mcpservice: dict[str, Any], registry_name: str
) -> dict[str, Any]:
    """Convert MCPService resource to detailed server format for API response"""
    # Get basic server info
    server = _mcpservice_to_server_format(mcpservice, registry_name)

    # Add detailed information
    metadata = mcpservice.get("metadata", {})
    spec = mcpservice.get("spec", {})
    status = mcpservice.get("status", {})

    # Add additional details
    server.update(
        {
            "requirements": {
                "cpu": spec.get("resources", {})
                .get("requests", {})
                .get("cpu", "50m"),
                "memory": spec.get("resources", {})
                .get("requests", {})
                .get("memory", "128Mi"),
            },
            "limits": {
                "cpu": spec.get("resources", {})
                .get("limits", {})
                .get("cpu", "200m"),
                "memory": spec.get("resources", {})
                .get("limits", {})
                .get("memory", "256Mi"),
            },
            "environment": spec.get("environment", {}),
            "resources": spec.get("mcp_resources", []),  # MCP resources
            "prompts": spec.get("prompts", []),
            "conditions": status.get("conditions", []),
            "created_at": metadata.get("creationTimestamp"),
            "updated_at": status.get("lastUpdated"),
        }
    )

    # Add deployment paths
    deployment = server.get("deployment", {})
    if deployment.get("type") == "http":
        deployment.update({"health_path": "/health", "mcp_path": "/mcp"})

    return server


async def _create_registry_configmap(
    namespace: str, registry_name: str, registry_data: dict[str, Any]
) -> None:
    """Create ConfigMap with registry data (templates only)"""
    try:
        configmap_name = f"{registry_name}-registry"

        # Check if ConfigMap already exists
        try:
            client.CoreV1Api().read_namespaced_config_map(
                name=configmap_name, namespace=namespace
            )
            logger.info(
                "Registry ConfigMap %s already exists in namespace %s",
                configmap_name,
                namespace,
            )
            return
        except ApiException as e:
            if e.status != 404:
                raise

        # Create ConfigMap with registry data
        configmap_manifest = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": configmap_name,
                "namespace": namespace,
                "labels": {
                    "mcp.nimbletools.dev/registry": "true",
                    "mcp.nimbletools.dev/registry-name": registry_name,
                    "mcp.nimbletools.dev/managed-by": "nimbletools-control-plane",
                },
                "annotations": {"mcp.nimbletools.dev/content-type": "registry-data"},
            },
            "data": {
                "registry.yaml": yaml.dump(registry_data, default_flow_style=False)
            },
        }

        client.CoreV1Api().create_namespaced_config_map(
            namespace=namespace, body=configmap_manifest
        )
        logger.info(
            "Created registry ConfigMap: %s in namespace %s", configmap_name, namespace
        )

    except Exception as e:
        logger.error(
            "Failed to create registry ConfigMap in namespace %s: %s", namespace, e
        )
        raise


def _registry_server_to_api_format(
    server: dict[str, Any], registry_name: str, namespace: str
) -> dict[str, Any]:
    """Convert registry server definition to API server format"""

    # Extract basic info
    name = server.get("name", "unknown")
    version = server.get("version", "unknown")
    description = server.get("meta", {}).get("description", f"{name} MCP service")
    category = server.get("meta", {}).get("category")
    tags = server.get("meta", {}).get("tags", [])

    # Get deployment info
    deployment = server.get("deployment", {})
    container = server.get("container", {})

    # Convert to API format
    server_info = {
        "id": name,
        "name": description,
        "description": description,
        "image": container.get("image", "unknown"),
        "version": version,
        "status": "available",  # Templates are always available
        "registry": registry_name,
        "namespace": namespace,
        "deployment": {
            "type": deployment.get("type", "http"),
            "port": container.get("port", 8000),
        },
        "tools": server.get("tools", []),
        "replicas": {
            "desired": server.get("replicas", 1),
            "current": 0,  # Not deployed yet
            "ready": 0,  # Not deployed yet
        },
        "category": category,
        "tags": tags if isinstance(tags, list) else [],
    }

    return server_info
