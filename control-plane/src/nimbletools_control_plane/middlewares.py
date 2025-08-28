"""
Shared middlewares and validators for NimbleTools Control Plane
"""

import logging
from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException, Request
from kubernetes import client

from .auth import AuthenticatedRequest, AuthType, UserContext, create_auth_provider

logger = logging.getLogger(__name__)
auth_provider = create_auth_provider()


async def get_auth_context(request: Request) -> AuthenticatedRequest:
    """Dependency to get authentication context"""
    user_context = await auth_provider.authenticate(request)
    if user_context:
        return AuthenticatedRequest(
            auth_type=(AuthType.NONE if user_context.get("auth_type") == "none" else AuthType.JWT),
            authenticated=True,
            user=UserContext(
                user_id=user_context.get("user_id", "community-user"),
                email=user_context.get("email", "community@nimbletools.dev"),
                role=user_context.get("role", "admin"),
            ),
        )
    return AuthenticatedRequest(auth_type=AuthType.NONE, authenticated=False)


def create_workspace_access_validator(
    workspace_param_name: str = "workspace_id",
) -> Callable[[Request, AuthenticatedRequest], Awaitable[str]]:
    """Creates a dependency function that validates workspace access"""

    async def validate_workspace_access(
        request: Request, auth_context: AuthenticatedRequest = Depends(get_auth_context)
    ) -> str:
        """Validate workspace access and return actual namespace name

        Args:
            request: FastAPI request object containing path params
            auth_context: Authentication context (used in enterprise version for ownership validation)
        """
        workspace_id = request.path_params.get(workspace_param_name)
        if not workspace_id:
            raise HTTPException(status_code=400, detail="Workspace ID required")

        # Query workspace by ID to get actual namespace name
        try:
            k8s_core = client.CoreV1Api()
            namespaces = k8s_core.list_namespace(
                label_selector=f"mcp.nimbletools.dev/workspace=true,mcp.nimbletools.dev/workspace_id={workspace_id}"
            )

            if not namespaces.items:
                raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")

            if len(namespaces.items) > 1:
                raise HTTPException(
                    status_code=500,
                    detail=f"Multiple namespaces found for workspace {workspace_id}",
                )

            workspace_namespace = namespaces.items[0].metadata.name

            # In enterprise version, this would also validate ownership
            # For now, just return the namespace name
            return str(workspace_namespace)

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error validating workspace access for %s: %s", workspace_id, e)
            raise HTTPException(status_code=500, detail="Error validating workspace access") from e

    return validate_workspace_access
