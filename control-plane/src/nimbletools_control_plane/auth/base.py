"""
Authentication and authorization for NimbleTools Control Plane.

This module provides FastAPI dependencies for authentication using
the configured provider.
"""

import logging
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request
from kubernetes import client
from kubernetes.client.rest import ApiException

from nimbletools_control_plane import provider

logger = logging.getLogger(__name__)


def extract_token(request: Request) -> str | None:
    """Extract authentication token from request headers."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.replace("Bearer ", "")
    return None


async def get_current_user(request: Request) -> dict[str, Any]:
    """
    Get the current authenticated user.

    This dependency extracts the token and validates it using the provider.
    """
    token = extract_token(request) or ""

    user = await provider.validate_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    return user


async def get_workspace_namespace(
    workspace_id: str,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> str:
    """
    Validate user can access a workspace and return namespace name.

    This is a dependency that:
    1. Gets the current user
    2. Checks workspace access via provider
    3. Returns the namespace name

    Args:
        workspace_id: Workspace ID from path
        user: Current authenticated user

    Returns:
        Namespace name for the workspace

    Raises:
        HTTPException: If access denied or workspace not found
    """
    # Check access using provider
    if not await provider.check_workspace_access(user, workspace_id):
        logger.warning(
            "Access denied for user %s to workspace %s",
            user.get("user_id", "unknown"),
            workspace_id,
        )
        raise HTTPException(status_code=403, detail="Access denied to workspace")

    # Resolve workspace_id to namespace name
    try:
        k8s_core = client.CoreV1Api()
        namespaces = k8s_core.list_namespace(
            label_selector=f"mcp.nimbletools.dev/workspace_id={workspace_id}"
        )

        if not namespaces.items:
            raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")

        return str(namespaces.items[0].metadata.name)

    except ApiException as e:
        if e.status == 404:
            raise HTTPException(
                status_code=404, detail=f"Workspace {workspace_id} not found"
            ) from e
        logger.error("Error looking up workspace namespace: %s", e)
        raise HTTPException(status_code=500, detail="Error validating workspace access") from e


async def require_permission(
    resource: str, action: str, user: Annotated[dict[str, Any], Depends(get_current_user)]
) -> dict[str, Any]:
    """
    Validate user can perform an action on a resource.

    Args:
        resource: Resource identifier (e.g., "workspaces", "servers")
        action: Action to perform (e.g., "read", "write", "create", "delete")
        user: Current authenticated user

    Returns:
        User dictionary if authorized

    Raises:
        HTTPException: If permission denied
    """
    if not await provider.check_permission(user, resource, action):
        logger.warning(
            "Permission denied for user %s: cannot %s %s",
            user.get("user_id", "unknown"),
            action,
            resource,
        )
        raise HTTPException(
            status_code=403, detail=f"Permission denied: cannot {action} {resource}"
        )

    return user
