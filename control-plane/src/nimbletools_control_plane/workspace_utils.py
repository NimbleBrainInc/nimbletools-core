"""Workspace utility functions."""

import uuid as uuid_module


def generate_workspace_identifiers(workspace_name_base: str) -> dict[str, str]:
    """Generate workspace identifiers including UUID, name, and namespace.

    Args:
        workspace_name_base: The base name for the workspace (user-provided name)

    Returns:
        Dictionary containing:
        - workspace_id: UUID for the workspace
        - workspace_name: User-provided workspace name (without UUID)
        - namespace_name: Kubernetes namespace name (ws-{name}-{uuid})
    """
    workspace_uuid = str(uuid_module.uuid4())
    workspace_id = workspace_uuid
    workspace_name = workspace_name_base  # Just the user-provided name, no UUID
    namespace_name = f"ws-{workspace_name_base}-{workspace_uuid}"

    return {
        "workspace_id": workspace_id,
        "workspace_name": workspace_name,
        "namespace_name": namespace_name,
    }


def get_namespace_from_workspace_id(workspace_id: str) -> str:
    """Get the Kubernetes namespace name for a workspace ID.

    Args:
        workspace_id: The workspace UUID

    Returns:
        The namespace name (ws-{workspace_id})
    """
    return f"ws-{workspace_id}"
