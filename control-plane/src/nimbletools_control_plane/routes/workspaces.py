"""
Workspace Router for NimbleTools Control Plane
"""

import base64
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID as UUID_cls

from fastapi import APIRouter, Depends, HTTPException, Request
from kubernetes import client
from kubernetes.client.rest import ApiException

from nimbletools_control_plane import auth
from nimbletools_control_plane.exceptions import (
    convert_to_http_exception,
    log_operation_start,
    log_operation_success,
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
)
from nimbletools_control_plane.workspace_utils import generate_workspace_identifiers

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/workspaces", tags=["workspaces"])


@router.post("")
async def create_workspace(
    workspace_request: WorkspaceCreateRequest,
    user: dict[str, Any] = Depends(auth.get_current_user),
) -> WorkspaceCreateResponse:
    """Create a new workspace - compatible with ntcli"""

    try:
        workspace_name_base = workspace_request.name

        # Get user ID and organization ID from authenticated user context
        user_id = user.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=401, detail="User authentication failed: missing user_id"
            )
        user_id_str = str(user_id)

        organization_id = user.get("organization_id")
        if not organization_id:
            raise HTTPException(
                status_code=401, detail="User authentication failed: missing organization_id"
            )
        organization_id_str = str(organization_id)

        # Create Kubernetes client
        k8s_core = client.CoreV1Api()

        # Check if a workspace with the same name already exists in this organization
        # We use a composite label to ensure uniqueness within an org
        # Note: Using dash instead of colon as Kubernetes labels don't allow colons
        unique_workspace_key = f"{workspace_name_base}-{organization_id_str}"

        # Check for existing workspace with same name in this org
        label_selector = f"mcp.nimbletools.dev/workspace=true,mcp.nimbletools.dev/organization_id={organization_id_str}"
        existing_namespaces = k8s_core.list_namespace(label_selector=label_selector)

        for ns in existing_namespaces.items:
            existing_labels = ns.metadata.labels or {}
            existing_unique_key = existing_labels.get("mcp.nimbletools.dev/unique_key")
            if existing_unique_key == unique_workspace_key:
                logger.warning(
                    "User %s attempted to create duplicate workspace '%s' in org %s",
                    user_id_str,
                    workspace_name_base,
                    organization_id_str,
                )
                raise HTTPException(
                    status_code=409,
                    detail=f"A workspace named '{workspace_name_base}' already exists in your organization",
                )

        # Generate workspace identifiers using utility function
        workspace_ids = generate_workspace_identifiers(workspace_name_base)
        workspace_id = workspace_ids["workspace_id"]
        workspace_name = workspace_ids["workspace_name"]
        namespace_name = workspace_ids["namespace_name"]

        log_operation_start("creating workspace", "workspace", workspace_name)
        logger.info("Creating workspace: %s", workspace_name)

        # Build labels
        labels = {
            "mcp.nimbletools.dev/workspace": "true",
            "mcp.nimbletools.dev/workspace_id": workspace_id,
            "mcp.nimbletools.dev/workspace_name": workspace_name,  # Store the user-provided workspace name
            "mcp.nimbletools.dev/user_id": user_id_str,  # Standardized field for workspace owner
            "mcp.nimbletools.dev/organization_id": organization_id_str,
            "mcp.nimbletools.dev/unique_key": unique_workspace_key,  # Composite key for uniqueness
        }

        # Build annotations
        annotations = {
            "mcp.nimbletools.dev/created": datetime.now(UTC).isoformat(),
            "mcp.nimbletools.dev/organization_id": organization_id_str,
        }

        namespace = client.V1Namespace(
            metadata=client.V1ObjectMeta(
                name=namespace_name,
                labels=labels,
                annotations=annotations,
            )
        )

        k8s_core.create_namespace(namespace)
        logger.info("Created workspace namespace: %s", namespace_name)

        # Parse user_id and org_id back to UUID for response
        response = WorkspaceCreateResponse(
            workspace_name=workspace_name,  # Use the workspace_name from generate function
            workspace_id=UUID_cls(workspace_id),
            namespace=namespace_name,
            user_id=UUID_cls(user_id_str),
            organization_id=UUID_cls(organization_id_str),
            created_at=datetime.now(UTC),
            status="ready",
            message=f"Workspace '{workspace_name}' created successfully",
        )
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
    user: dict[str, Any] = Depends(auth.get_current_user),
) -> WorkspaceListResponse:
    """List workspaces"""
    try:
        k8s_core = client.CoreV1Api()

        # Get user ID and organization ID for filtering
        user_id = user.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=401, detail="User authentication failed: missing user_id"
            )

        organization_id = user.get("organization_id")
        if not organization_id:
            raise HTTPException(
                status_code=401, detail="User authentication failed: missing organization_id"
            )

        # Filter workspaces by organization_id
        # This ensures users only see workspaces from their organization
        label_selector = f"mcp.nimbletools.dev/workspace=true,mcp.nimbletools.dev/organization_id={organization_id}"
        namespaces = k8s_core.list_namespace(label_selector=label_selector)

        workspaces = []
        for ns in namespaces.items:
            labels = ns.metadata.labels or {}
            annotations = ns.metadata.annotations or {}

            # Read workspace_id from label (required)
            workspace_id = labels.get("mcp.nimbletools.dev/workspace_id")
            if not workspace_id:
                logger.error("Namespace %s missing workspace_id label, skipping", ns.metadata.name)
                continue  # Skip workspaces without proper labels

            # Read workspace_name from label (required)
            workspace_name = labels.get("mcp.nimbletools.dev/workspace_name")
            if not workspace_name:
                logger.error(
                    "Namespace %s missing workspace_name label, skipping", ns.metadata.name
                )
                continue

            # Parse timestamps
            created_str = annotations.get("mcp.nimbletools.dev/created")
            if not created_str and ns.metadata.creation_timestamp:
                created_str = ns.metadata.creation_timestamp.isoformat()
            created_dt = (
                datetime.fromisoformat(created_str.replace("Z", "+00:00")) if created_str else None
            )

            # Get user_id and organization_id (both required)
            user_id_str = labels.get("mcp.nimbletools.dev/user_id")
            if not user_id_str:
                logger.error("Namespace %s missing user_id label, skipping", ns.metadata.name)
                continue

            org_id_str = labels.get("mcp.nimbletools.dev/organization_id")
            if not org_id_str:
                logger.error(
                    "Namespace %s missing organization_id label, skipping", ns.metadata.name
                )
                continue

            workspaces.append(
                WorkspaceSummary(
                    workspace_id=UUID_cls(workspace_id),
                    workspace_name=workspace_name,
                    namespace=ns.metadata.name,
                    user_id=UUID_cls(user_id_str),
                    organization_id=UUID_cls(org_id_str),
                    created_at=created_dt,
                    status="active",
                )
            )

        logger.info("Listed %s workspaces for user %s", len(workspaces), user_id)

        return WorkspaceListResponse(
            workspaces=workspaces, total=len(workspaces), user_id=UUID_cls(user_id)
        )

    except HTTPException:
        raise
    except Exception as e:
        user_id = user.get("user_id", "unknown")
        logger.error("Error listing workspaces for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=500,
            detail="Error listing workspaces. Please try again or contact support.",
        ) from e


@router.get("/{workspace_id}")
async def get_workspace_details(
    workspace_id: str,
    _request: Request,
    namespace_name: str = Depends(auth.get_workspace_namespace),
) -> WorkspaceDetailsResponse:
    """Get workspace details - authentication and access handled by dependency"""

    try:
        k8s_core = client.CoreV1Api()
        namespace = k8s_core.read_namespace(namespace_name)
        labels = namespace.metadata.labels or {}
        annotations = namespace.metadata.annotations or {}

        # Read workspace_name from label (required)
        workspace_name = labels.get("mcp.nimbletools.dev/workspace_name")
        if not workspace_name:
            raise HTTPException(
                status_code=500,
                detail=f"Workspace {workspace_id} missing required workspace_name label",
            )

        # Verify workspace_id exists and matches what's in the label
        label_workspace_id = labels.get("mcp.nimbletools.dev/workspace_id")
        if not label_workspace_id:
            raise HTTPException(
                status_code=500,
                detail=f"Workspace {workspace_id} missing required workspace_id label",
            )
        if label_workspace_id != workspace_id:
            logger.error(
                "Workspace ID mismatch: requested %s but namespace has %s",
                workspace_id,
                label_workspace_id,
            )
            raise HTTPException(status_code=500, detail="Workspace configuration error")

        # Parse timestamps
        created_str = annotations.get("mcp.nimbletools.dev/created")
        created_dt = (
            datetime.fromisoformat(created_str.replace("Z", "+00:00")) if created_str else None
        )

        # Get user_id and organization_id (both required)
        user_id_str = labels.get("mcp.nimbletools.dev/user_id")
        if not user_id_str:
            raise HTTPException(
                status_code=500, detail=f"Workspace {workspace_id} missing required user_id label"
            )

        org_id_str = labels.get("mcp.nimbletools.dev/organization_id")
        if not org_id_str:
            raise HTTPException(
                status_code=500,
                detail=f"Workspace {workspace_id} missing required organization_id label",
            )

        return WorkspaceDetailsResponse(
            workspace_id=UUID_cls(workspace_id),
            workspace_name=workspace_name,
            namespace=namespace_name,
            user_id=UUID_cls(user_id_str),
            organization_id=UUID_cls(org_id_str),
            created_at=created_dt,
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
    _request: Request,
    namespace_name: str = Depends(auth.get_workspace_namespace),
) -> WorkspaceDeleteResponse:
    """Delete workspace - authentication and access handled by dependency"""

    try:
        k8s_core = client.CoreV1Api()

        log_operation_start("deleting workspace", "workspace", workspace_id)
        # Delete the namespace (cascades to all resources)
        k8s_core.delete_namespace(namespace_name)
        logger.info("Deleted workspace namespace: %s", namespace_name)

        result = WorkspaceDeleteResponse(
            workspace_id=UUID_cls(workspace_id),
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


@router.get("/{workspace_id}/secrets")
async def list_workspace_secrets(
    workspace_id: str,
    request: Request,
    namespace_name: str = Depends(auth.get_workspace_namespace),
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
            workspace_id=UUID_cls(workspace_id),
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
    namespace_name: str = Depends(auth.get_workspace_namespace),
) -> WorkspaceSecretResponse:
    """Set a secret for a workspace"""

    try:
        log_operation_start("setting secret", "workspace", workspace_id)
        k8s_core = client.CoreV1Api()

        # Create or update the secret in the workspace namespace
        secret_name = "workspace-secrets"

        # Encode the secret value in base64 as required by Kubernetes
        encoded_value = base64.b64encode(secret_request.secret_value.encode("utf-8")).decode(
            "utf-8"
        )

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
                            "mcp.nimbletools.dev/created": datetime.now(UTC).isoformat(),
                        },
                    ),
                    data={secret_key: encoded_value},
                    type="Opaque",
                )

                k8s_core.create_namespaced_secret(namespace=namespace_name, body=secret_manifest)
                logger.info("Created secret %s in workspace %s", secret_key, workspace_id)
            else:
                raise

        log_operation_success("setting secret", "workspace", workspace_id)
        return WorkspaceSecretResponse(
            workspace_id=UUID_cls(workspace_id),
            secret_key=secret_key,
            status="success",
            message=f"Secret '{secret_key}' set successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error setting secret %s for workspace %s: %s", secret_key, workspace_id, e)
        raise convert_to_http_exception(e, default_status_code=500)


@router.delete("/{workspace_id}/secrets/{secret_key}")
async def delete_workspace_secret(
    workspace_id: str,
    secret_key: str,
    request: Request,
    namespace_name: str = Depends(auth.get_workspace_namespace),
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
                k8s_core.delete_namespaced_secret(name=secret_name, namespace=namespace_name)
                logger.info("Deleted empty secret resource for workspace %s", workspace_id)
            else:
                # Update the secret without the deleted key
                k8s_core.patch_namespaced_secret(
                    name=secret_name, namespace=namespace_name, body=existing_secret
                )
                logger.info("Removed secret %s from workspace %s", secret_key, workspace_id)

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
            workspace_id=UUID_cls(workspace_id),
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
