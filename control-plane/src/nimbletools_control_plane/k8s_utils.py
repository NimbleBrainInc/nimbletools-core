"""
Kubernetes utility functions shared across routers
"""

import logging
from typing import Any

from kubernetes import client

logger = logging.getLogger(__name__)


async def get_user_registry_namespaces(owner: str) -> list[dict[str, Any]]:
    """Get all registry namespaces owned by a user"""
    try:
        k8s_core = client.CoreV1Api()

        # List namespaces with registry labels and owner
        namespaces = k8s_core.list_namespace(
            label_selector=f"mcp.nimbletools.dev/registry=true,mcp.nimbletools.dev/owner={owner}"
        )

        registry_namespaces = []
        for ns in namespaces.items:
            labels = ns.metadata.labels or {}
            annotations = ns.metadata.annotations or {}

            registry_namespaces.append(
                {
                    "name": ns.metadata.name,
                    "registry_name": labels.get("mcp.nimbletools.dev/registry-name", "unknown"),
                    "registry_url": annotations.get("mcp.nimbletools.dev/registry-url"),
                    "owner": labels.get("mcp.nimbletools.dev/owner", "unknown"),
                }
            )

        logger.info("Found %d registry namespaces for owner %s", len(registry_namespaces), owner)
        return registry_namespaces

    except Exception as e:
        logger.error("Error getting registry namespaces for owner %s: %s", owner, e)
        raise
