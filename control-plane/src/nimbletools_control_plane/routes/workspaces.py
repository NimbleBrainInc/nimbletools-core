"""
Workspace Router for NimbleTools Control Plane
"""

import base64
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from kubernetes import client
from kubernetes.client.rest import ApiException

from nimbletools_control_plane.auth import (
    AuthenticatedRequest,
    AuthType,
    create_auth_provider,
)
from nimbletools_control_plane.exceptions import (
    convert_to_http_exception,
    log_operation_start,
    log_operation_success,
)
from nimbletools_control_plane.middlewares import (
    create_workspace_access_validator,
    get_auth_context,
)
from nimbletools_control_plane.models import (
    WorkspaceCreateRequest,
    WorkspaceCreateResponse,
    WorkspaceDeleteResponse,
    WorkspaceDetailsResponse,
    WorkspaceListResponse,
    WorkspaceSecretResponse,
    WorkspaceSecretSetRequest,
    WorkspaceSecretsResponse,
    WorkspaceSummary,
    WorkspaceTokenResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/workspaces", tags=["workspaces"])
auth_provider = create_auth_provider()


@router.post("")
async def create_workspace(
    workspace_request: WorkspaceCreateRequest,
    auth_context: AuthenticatedRequest = Depends(get_auth_context),
) -> WorkspaceCreateResponse:
    """Create a new workspace - compatible with ntcli"""

    try:
        workspace_name_base = workspace_request.name
        tier = workspace_request.tier.value

        # Generate UUID-based workspace name
        workspace_uuid = str(uuid.uuid4())
        workspace_name = f"{workspace_name_base}-{workspace_uuid}"
        workspace_id = workspace_uuid  # Use UUID as workspace ID for API paths
        namespace_name = f"ws-{workspace_name}"

        log_operation_start("creating workspace", "workspace", workspace_name)
        logger.info("Creating workspace: %s (tier: %s)", workspace_name, tier)

        # Get user ID from authentication context
        user_id = auth_context.user.user_id if auth_context.user else "community-user"

        # Create Kubernetes namespace
        k8s_core = client.CoreV1Api()

        namespace = client.V1Namespace(
            metadata=client.V1ObjectMeta(
                name=namespace_name,
                labels={
                    "mcp.nimbletools.dev/workspace": "true",
                    "mcp.nimbletools.dev/workspace_id": workspace_uuid,
                    "mcp.nimbletools.dev/owner": user_id,
                    "mcp.nimbletools.dev/tier": tier,
                    "mcp.nimbletools.dev/version": "core",
                },
                annotations={
                    "mcp.nimbletools.dev/created": datetime.now(UTC).isoformat(),
                    "mcp.nimbletools.dev/tier": tier,
                },
            )
        )

        k8s_core.create_namespace(namespace)
        logger.info("Created workspace namespace: %s", namespace_name)

        response = WorkspaceCreateResponse(
            workspace_name=workspace_name_base,
            workspace_id=workspace_id,
            namespace=namespace_name,
            tier=tier,
            created=datetime.now(UTC).isoformat(),
            status="ready",
            message=f"Workspace '{workspace_name_base}' created successfully",
        )

        # For community version, we don't generate access tokens
        # Enterprise version would include token generation here

        log_operation_success("creating workspace", "workspace", workspace_name)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create workspace: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Failed to create workspace. Please try again or contact support.",
        ) from e


@router.get("")
async def list_workspaces(
    auth_context: AuthenticatedRequest = Depends(get_auth_context),
) -> WorkspaceListResponse:
    """List workspaces - compatible with ntcli"""
    try:
        k8s_core = client.CoreV1Api()

        # Get user ID for filtering (in community version, this is always "community-user")
        user_id = auth_context.user.user_id if auth_context.user else "community-user"

        # In community mode with no auth, list all workspace namespaces
        if auth_context.auth_type == AuthType.NONE:
            namespaces = k8s_core.list_namespace(
                label_selector="mcp.nimbletools.dev/workspace=true"
            )
        else:
            # In enterprise mode, filter by owner
            namespaces = k8s_core.list_namespace(
                label_selector=f"mcp.nimbletools.dev/workspace=true,mcp.nimbletools.dev/owner={user_id}"
            )

        workspaces = []
        for ns in namespaces.items:
            labels = ns.metadata.labels or {}
            annotations = ns.metadata.annotations or {}

            # Extract workspace UUID from namespace name (ws-name-uuid format)
            namespace_parts = ns.metadata.name.split("-")
            workspace_id = labels.get("mcp.nimbletools.dev/workspace_id")
            if not workspace_id and len(namespace_parts) >= 6:
                # Extract UUID from namespace name: ws-name-uuid -> take last 5 parts as UUID
                workspace_id = "-".join(namespace_parts[-5:])

            # Extract workspace name from namespace (remove ws- prefix and UUID suffix)
            workspace_name = ns.metadata.name
            if workspace_name.startswith("ws-") and len(namespace_parts) >= 6:
                # ws-name-uuid -> extract "name" part
                workspace_name = "-".join(namespace_parts[1:-5])

            workspaces.append(
                WorkspaceSummary(
                    workspace_id=workspace_id,
                    workspace_name=workspace_name,
                    namespace=ns.metadata.name,
                    tier=labels.get("mcp.nimbletools.dev/tier", "community"),
                    created=annotations.get("mcp.nimbletools.dev/created")
                    or (
                        ns.metadata.creation_timestamp.isoformat()
                        if ns.metadata.creation_timestamp
                        else None
                    ),
                    owner=labels.get("mcp.nimbletools.dev/owner"),
                    status="active",
                )
            )

        logger.info("Listed %s workspaces for user %s", len(workspaces), user_id)

        return WorkspaceListResponse(
            workspaces=workspaces, total=len(workspaces), user_id=user_id
        )

    except Exception as e:
        user_id = auth_context.user.user_id if auth_context.user else "unknown"
        logger.error("Error listing workspaces for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=500,
            detail="Error listing workspaces. Please try again or contact support.",
        ) from e


@router.get("/{workspace_id}")
async def get_workspace_details(
    workspace_id: str,
    request: Request,
    namespace_name: str = Depends(create_workspace_access_validator("workspace_id")),
) -> WorkspaceDetailsResponse:
    """Get workspace details - authentication handled by dependency"""

    try:
        k8s_core = client.CoreV1Api()
        namespace = k8s_core.read_namespace(namespace_name)
        labels = namespace.metadata.labels or {}
        annotations = namespace.metadata.annotations or {}

        # Extract workspace name from namespace
        workspace_name = None
        parts = namespace_name.split("-")
        if len(parts) >= 3:
            workspace_name = "-".join(parts[1:-5])

        return WorkspaceDetailsResponse(
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            namespace=namespace_name,
            tier=annotations.get("mcp.nimbletools.dev/tier", "community"),
            created=annotations.get("mcp.nimbletools.dev/created"),
            owner=labels.get("mcp.nimbletools.dev/owner"),
            status="active",
        )

    except Exception as e:
        logger.error("Error getting workspace details: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Error getting workspace details. Please try again or contact support.",
        ) from e


@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    request: Request,
    namespace_name: str = Depends(create_workspace_access_validator("workspace_id")),
) -> WorkspaceDeleteResponse:
    """Delete workspace - authentication handled by dependency"""

    try:
        k8s_core = client.CoreV1Api()

        log_operation_start("deleting workspace", "workspace", workspace_id)
        # Delete the namespace (cascades to all resources)
        k8s_core.delete_namespace(namespace_name)
        logger.info("Deleted workspace namespace: %s", namespace_name)

        result = WorkspaceDeleteResponse(
            workspace_id=workspace_id,
            namespace=namespace_name,
            message="Workspace deleted successfully",
        )
        log_operation_success("deleting workspace", "workspace", workspace_id)
        return result

    except ApiException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail="Workspace not found") from e
        logger.exception("Failed to delete workspace: %s", e)
        raise convert_to_http_exception(e, default_status_code=500) from e
    except Exception as e:
        logger.exception("Error deleting workspace: %s", e)
        raise convert_to_http_exception(e, default_status_code=500) from e


@router.post("/{workspace_id}/tokens")
async def get_workspace_token(
    workspace_id: str,
    request: Request,
    namespace_name: str = Depends(create_workspace_access_validator("workspace_id")),
) -> WorkspaceTokenResponse:
    """Generate workspace token - simplified for community version"""

    # Community version returns a placeholder token
    # Enterprise version would generate real JWT tokens
    return WorkspaceTokenResponse(
        access_token="community-token-placeholder",
        token_type="Bearer",
        scope=[
            "workspace:read",
            "workspace:manage",
            "servers:read",
            "servers:manage",
        ],
        workspace_id=workspace_id,
        expires_in=31536000,  # 1 year
        message="Community version - token authentication not required",
    )


@router.get("/{workspace_id}/secrets")
async def list_workspace_secrets(
    workspace_id: str,
    request: Request,
    namespace_name: str = Depends(create_workspace_access_validator("workspace_id")),
) -> WorkspaceSecretsResponse:
    """List all secrets for a workspace"""

    try:
        log_operation_start("listing secrets", "workspace", workspace_id)
        k8s_core = client.CoreV1Api()

        # List all secrets in the workspace namespace that are managed by us
        secrets = k8s_core.list_namespaced_secret(
            namespace=namespace_name,
            label_selector="mcp.nimbletools.dev/managed-by=nimbletools-control-plane",
        )

        secret_keys = []
        for secret in secrets.items:
            # Extract the secret keys from the secret data
            if secret.data:
                for key in secret.data:
                    if not key.startswith("."):  # Skip metadata keys
                        secret_keys.append(key)

        log_operation_success("listing secrets", "workspace", workspace_id)
        return WorkspaceSecretsResponse(
            workspace_id=workspace_id,
            secrets=sorted(secret_keys),
            count=len(secret_keys),
            message=f"Found {len(secret_keys)} secrets",
        )

    except Exception as e:
        logger.error("Error listing secrets for workspace %s: %s", workspace_id, e)
        raise convert_to_http_exception(e, default_status_code=500)


@router.put("/{workspace_id}/secrets/{secret_key}")
async def set_workspace_secret(
    workspace_id: str,
    secret_key: str,
    secret_request: WorkspaceSecretSetRequest,
    request: Request,
    namespace_name: str = Depends(create_workspace_access_validator("workspace_id")),
) -> WorkspaceSecretResponse:
    """Set a secret for a workspace"""

    try:
        log_operation_start("setting secret", "workspace", workspace_id)
        k8s_core = client.CoreV1Api()

        # Create or update the secret in the workspace namespace
        secret_name = "workspace-secrets"

        # Encode the secret value in base64 as required by Kubernetes
        encoded_value = base64.b64encode(
            secret_request.secret_value.encode("utf-8")
        ).decode("utf-8")

        try:
            # Try to get existing secret
            existing_secret = k8s_core.read_namespaced_secret(
                name=secret_name, namespace=namespace_name
            )

            # Update existing secret
            if existing_secret.data is None:
                existing_secret.data = {}
            existing_secret.data[secret_key] = encoded_value

            k8s_core.patch_namespaced_secret(
                name=secret_name, namespace=namespace_name, body=existing_secret
            )
            logger.info("Updated secret %s in workspace %s", secret_key, workspace_id)

        except ApiException as e:
            if e.status == 404:
                # Create new secret
                secret_manifest = client.V1Secret(
                    metadata=client.V1ObjectMeta(
                        name=secret_name,
                        namespace=namespace_name,
                        labels={
                            "mcp.nimbletools.dev/managed-by": "nimbletools-control-plane",
                            "mcp.nimbletools.dev/workspace": workspace_id,
                        },
                        annotations={
                            "mcp.nimbletools.dev/created": datetime.now(
                                UTC
                            ).isoformat(),
                        },
                    ),
                    data={secret_key: encoded_value},
                    type="Opaque",
                )

                k8s_core.create_namespaced_secret(
                    namespace=namespace_name, body=secret_manifest
                )
                logger.info(
                    "Created secret %s in workspace %s", secret_key, workspace_id
                )
            else:
                raise

        log_operation_success("setting secret", "workspace", workspace_id)
        return WorkspaceSecretResponse(
            workspace_id=workspace_id,
            secret_key=secret_key,
            status="success",
            message=f"Secret '{secret_key}' set successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error setting secret %s for workspace %s: %s", secret_key, workspace_id, e
        )
        raise convert_to_http_exception(e, default_status_code=500)


@router.delete("/{workspace_id}/secrets/{secret_key}")
async def delete_workspace_secret(
    workspace_id: str,
    secret_key: str,
    request: Request,
    namespace_name: str = Depends(create_workspace_access_validator("workspace_id")),
) -> WorkspaceSecretResponse:
    """Delete a secret from a workspace"""

    try:
        log_operation_start("deleting secret", "workspace", workspace_id)
        k8s_core = client.CoreV1Api()

        secret_name = "workspace-secrets"

        try:
            # Get the existing secret
            existing_secret = k8s_core.read_namespaced_secret(
                name=secret_name, namespace=namespace_name
            )

            if existing_secret.data is None or secret_key not in existing_secret.data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Secret '{secret_key}' not found in workspace",
                )

            # Remove the specific secret key
            del existing_secret.data[secret_key]

            # If no more secrets remain, delete the entire secret resource
            if not existing_secret.data:
                k8s_core.delete_namespaced_secret(
                    name=secret_name, namespace=namespace_name
                )
                logger.info(
                    "Deleted empty secret resource for workspace %s", workspace_id
                )
            else:
                # Update the secret without the deleted key
                k8s_core.patch_namespaced_secret(
                    name=secret_name, namespace=namespace_name, body=existing_secret
                )
                logger.info(
                    "Removed secret %s from workspace %s", secret_key, workspace_id
                )

        except ApiException as e:
            if e.status == 404:
                raise HTTPException(
                    status_code=404,
                    detail=f"Secret '{secret_key}' not found in workspace",
                ) from e
            else:
                raise

        log_operation_success("deleting secret", "workspace", workspace_id)
        return WorkspaceSecretResponse(
            workspace_id=workspace_id,
            secret_key=secret_key,
            status="success",
            message=f"Secret '{secret_key}' deleted successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error deleting secret %s from workspace %s: %s",
            secret_key,
            workspace_id,
            e,
        )
        raise convert_to_http_exception(e, default_status_code=500) from e
