"""
RBAC Controller for NimbleTools Core

This controller automatically creates RoleBindings to grant the MCP Operator
access to workspace namespaces when they are created by the control plane.
"""

import sys
from typing import Any

import kopf
from kubernetes import client, config
from kubernetes.client import RbacV1Subject
from kubernetes.client.models import (
    V1NamespaceList,
    V1ObjectMeta,
    V1RoleBinding,
    V1RoleRef,
)
from kubernetes.client.rest import ApiException


def log(message: str) -> None:
    """Simple logging to stdout"""
    print(f"RBAC-Controller: {message}", flush=True)


# Global variables for Kubernetes clients (initialized in main)
v1: client.CoreV1Api | None = None
rbac_v1: client.RbacAuthorizationV1Api | None = None

# Constants for NimbleTools Core
MCP_OPERATOR_SERVICE_ACCOUNT = "nimbletools-core"
MCP_OPERATOR_NAMESPACE = "nimbletools-system"
MCP_OPERATOR_CLUSTER_ROLE = "nimbletools-core-operator"
WORKSPACE_LABEL = "mcp.nimbletools.dev/workspace_id"
WORKSPACE_PREFIX = "ws-"


def is_workspace_namespace(namespace_name: str, labels: dict | None) -> bool:
    """Check if namespace is a workspace namespace."""
    if not namespace_name.startswith(WORKSPACE_PREFIX):
        return False

    if labels and WORKSPACE_LABEL in labels:
        return True

    return False


def create_mcp_operator_rolebinding(namespace_name: str) -> bool:
    """Create RoleBinding to grant MCP Operator access to workspace namespace."""
    if rbac_v1 is None:
        log("❌ RBAC client not initialized")
        return False

    rolebinding_name = "nimbletools-operator-access"

    try:
        # Check if RoleBinding already exists
        try:
            rbac_v1.read_namespaced_role_binding(name=rolebinding_name, namespace=namespace_name)
            log(f"RoleBinding {rolebinding_name} already exists in {namespace_name}")
            return True
        except ApiException as e:
            if e.status != 404:
                raise

        # Create RoleBinding using strongly typed models
        rolebinding_body = V1RoleBinding(
            api_version="rbac.authorization.k8s.io/v1",
            kind="RoleBinding",
            metadata=V1ObjectMeta(
                name=rolebinding_name,
                namespace=namespace_name,
                labels={
                    "app": "nimbletools-rbac-controller",
                    "component": "operator-access",
                    "security-approach": "minimal-rbac",
                },
            ),
            subjects=[
                RbacV1Subject(
                    kind="ServiceAccount",
                    name=MCP_OPERATOR_SERVICE_ACCOUNT,
                    namespace=MCP_OPERATOR_NAMESPACE,
                )
            ],
            role_ref=V1RoleRef(
                api_group="rbac.authorization.k8s.io",
                kind="ClusterRole",
                name=MCP_OPERATOR_CLUSTER_ROLE,
            ),
        )

        rbac_v1.create_namespaced_role_binding(namespace=namespace_name, body=rolebinding_body)

        log(f"✅ Created RoleBinding {rolebinding_name} in namespace {namespace_name}")
        return True

    except ApiException as e:
        log(f"❌ Failed to create RoleBinding in {namespace_name}: {e}")
        return False
    except Exception as e:
        log(f"❌ Unexpected error creating RoleBinding in {namespace_name}: {e}")
        return False


@kopf.on.startup()
async def startup_handler(**kwargs: Any) -> None:
    """Handle startup - process existing workspace namespaces."""
    log("🚀 NimbleTools RBAC Controller starting up...")

    if v1 is None:
        log("❌ Core API client not initialized")
        raise RuntimeError("Kubernetes clients not initialized")

    try:
        # Get all existing namespaces
        namespaces: V1NamespaceList = v1.list_namespace()

        workspace_count = 0
        for namespace in namespaces.items:
            namespace_name = namespace.metadata.name
            labels = namespace.metadata.labels or {}

            if is_workspace_namespace(namespace_name, labels):
                log(f"🔍 Processing existing workspace namespace: {namespace_name}")
                success = create_mcp_operator_rolebinding(namespace_name)
                if success:
                    workspace_count += 1
                else:
                    log(f"⚠️ Failed to process workspace {namespace_name}")

        log(f"✅ Startup complete. Processed {workspace_count} existing workspace namespaces")

    except Exception as e:
        log(f"❌ Error during startup: {e}")
        raise


@kopf.on.create("", "v1", "namespaces")
async def namespace_created(meta: Any, spec: Any, **kwargs: Any) -> None:
    """Handle namespace creation events."""
    namespace_name = meta.get("name")
    labels = meta.get("labels", {})

    log(f"📝 Namespace created: {namespace_name}")

    # Check if this is a workspace namespace
    if not is_workspace_namespace(namespace_name, labels):
        log(f"⏭️ Ignoring non-workspace namespace: {namespace_name}")
        return

    log(f"🎯 Detected workspace namespace creation: {namespace_name}")

    # Create RoleBinding for MCP Operator
    success = create_mcp_operator_rolebinding(namespace_name)

    if success:
        log(f"✅ Successfully configured RBAC for workspace: {namespace_name}")
    else:
        log(f"❌ Failed to configure RBAC for workspace: {namespace_name}")
        # Raise exception to trigger kopf retry
        raise kopf.TemporaryError("Failed to create RoleBinding", delay=30)


@kopf.on.delete("", "v1", "namespaces")
async def namespace_deleted(meta: Any, **kwargs: Any) -> None:
    """Handle namespace deletion events."""
    namespace_name = meta.get("name")
    labels = meta.get("labels", {})

    # Only log workspace namespace deletions
    if is_workspace_namespace(namespace_name, labels):
        log(f"🗑️ Workspace namespace deleted: {namespace_name}")
        log("RoleBinding will be automatically cleaned up with namespace")


def _initialize_kubernetes_clients() -> None:
    """Initialize Kubernetes clients."""
    global v1, rbac_v1

    try:
        config.load_incluster_config()
        log("Loaded in-cluster Kubernetes configuration")
    except config.ConfigException:
        config.load_kube_config()
        log("Loaded local Kubernetes configuration")

    v1 = client.CoreV1Api()
    rbac_v1 = client.RbacAuthorizationV1Api()


def main() -> None:
    """Main entry point for the RBAC controller."""
    log("🎬 Starting NimbleTools RBAC Controller...")

    try:
        _initialize_kubernetes_clients()
        kopf.run(clusterwide=True)
    except Exception as e:
        log(f"💥 Failed to start controller: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
