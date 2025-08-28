"""
Simple Registry Client for Control Plane
Fetches and processes MCP registry data
"""

import logging
from typing import Any, cast

import aiohttp
import yaml
from aiohttp import ClientTimeout

logger = logging.getLogger(__name__)


class RegistryClient:
    """Simple registry client for control plane"""

    def __init__(self) -> None:
        """Initialize registry client"""
        self.timeout = 30

    async def fetch_registry(self, registry_url: str) -> dict[str, Any]:
        """Fetch registry data from URL

        Args:
            registry_url: URL to registry.yaml file

        Returns:
            Registry data dictionary

        Raises:
            Exception: If registry cannot be fetched or is invalid
        """
        try:
            logger.info("Fetching registry from %s", registry_url)

            async with (
                aiohttp.ClientSession() as session,
                session.get(registry_url, timeout=ClientTimeout(total=self.timeout)) as response,
            ):
                if response.status != 200:
                    raise Exception(f"Failed to fetch registry: HTTP {response.status}")

                content = await response.text()
                registry_data = yaml.safe_load(content)

                # Basic validation
                self._validate_registry(registry_data)

                logger.info(
                    "Successfully fetched registry: %s",
                    registry_data.get("metadata", {}).get("name", "unknown"),
                )
                # Ensure we return the correct type
                return dict(registry_data) if registry_data else {}

        except TimeoutError:
            raise Exception(f"Timeout fetching registry from {registry_url}") from None
        except Exception as e:
            logger.error("Error fetching registry: %s", e)
            raise

    def _validate_registry(self, registry_data: dict[str, Any]) -> None:
        """Basic registry validation

        Args:
            registry_data: Registry data to validate

        Raises:
            Exception: If registry is invalid
        """
        if not isinstance(registry_data, dict):
            raise Exception("Registry data must be a dictionary")

        # Check required fields
        if registry_data.get("apiVersion") != "registry.nimbletools.ai/v1":
            raise Exception("Invalid or missing apiVersion")

        if registry_data.get("kind") != "MCPRegistry":
            raise Exception("Invalid or missing kind")

        metadata = registry_data.get("metadata", {})
        if not metadata.get("name"):
            raise Exception("Registry metadata missing name")

        servers = registry_data.get("servers", [])
        if not isinstance(servers, list):
            raise Exception("Registry servers must be a list")

        logger.info("Registry validation passed: %d servers found", len(servers))

    def get_registry_info(self, registry_data: dict[str, Any]) -> dict[str, Any]:
        """Extract registry information

        Args:
            registry_data: Registry data

        Returns:
            Registry information dictionary
        """
        metadata = registry_data.get("metadata", {})
        servers = registry_data.get("servers", [])
        active_servers = [s for s in servers if s.get("status") == "active"]

        return {
            "name": metadata.get("name", "unknown"),
            "version": metadata.get("version", "unknown"),
            "last_updated": metadata.get("lastUpdated"),
            "total_servers": len(servers),
            "active_servers": len(active_servers),
        }

    def get_active_servers(self, registry_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Get list of active servers from registry

        Args:
            registry_data: Registry data

        Returns:
            List of active server definitions
        """
        servers = registry_data.get("servers", [])
        active_servers = [s for s in servers if s.get("status") == "active"]

        logger.info("Found %d active servers out of %d total", len(active_servers), len(servers))
        return active_servers

    def convert_to_mcpservice(self, server: dict[str, Any], namespace: str) -> dict[str, Any]:
        """Convert registry server to MCPService resource

        Args:
            server: Server definition from registry
            namespace: Target Kubernetes namespace

        Returns:
            MCPService resource dictionary
        """
        server_name = server.get("name", "unknown")
        version = server.get("version", "1.0.0")
        description = server.get("meta", {}).get("description", f"{server_name} MCP service")

        # Create MCPService resource
        mcpservice = {
            "apiVersion": "mcp.nimbletools.dev/v1",
            "kind": "MCPService",
            "metadata": {
                "name": server_name,
                "namespace": namespace,
                "labels": {
                    "mcp.nimbletools.dev/service": "true",
                    "mcp.nimbletools.dev/version": version,
                    "mcp.nimbletools.dev/managed-by": "nimbletools-control-plane",
                    "mcp.nimbletools.dev/source": "registry",
                },
                "annotations": {
                    "mcp.nimbletools.dev/description": description,
                    "mcp.nimbletools.dev/generated-from": "registry",
                },
            },
            "spec": self._build_service_spec(server),
        }

        # Add category label if available
        category = server.get("meta", {}).get("category")
        if category:
            labels = cast("dict[str, Any]", mcpservice["metadata"]["labels"])  # type: ignore[index]
            labels["mcp.nimbletools.dev/category"] = category

        # Add tags as annotations if available
        tags = server.get("meta", {}).get("tags", [])
        if tags:
            annotations = cast("dict[str, Any]", mcpservice["metadata"]["annotations"])  # type: ignore[index]
            annotations["mcp.nimbletools.dev/tags"] = ",".join(tags)

        return mcpservice

    def _build_service_spec(self, server: dict[str, Any]) -> dict[str, Any]:
        """Build MCPService spec from registry server definition"""
        spec = {}

        # Handle deployment configuration
        deployment_config = server.get("deployment", {})
        if deployment_config:
            spec["deployment"] = self._process_deployment_config(deployment_config)

        # Handle container configuration
        container_config = server.get("container", {})
        if container_config:
            spec["container"] = self._process_container_config(container_config)

        # Handle environment variables
        environment = server.get("environment", {})
        if environment:
            spec["environment"] = environment

        # Handle resources configuration
        resources_config = server.get("resources", {})
        if resources_config:
            spec["resources"] = self._process_resources_config(resources_config)

        # Handle replicas
        replicas = server.get("replicas", 1)
        spec["replicas"] = replicas

        # Handle capabilities (tools, resources, prompts) - from schema format
        capabilities = server.get("capabilities", {})

        tools = capabilities.get("tools", [])
        if tools:
            spec["tools"] = tools

        mcp_resources = capabilities.get("resources", [])
        if mcp_resources:
            spec["mcp_resources"] = mcp_resources

        prompts = capabilities.get("prompts", [])
        if prompts:
            spec["prompts"] = prompts

        return spec

    def _process_deployment_config(self, deployment_config: dict[str, Any]) -> dict[str, Any]:
        """Process deployment configuration from registry format"""
        processed = {}

        # Handle deployment type
        deployment_type = deployment_config.get("type", "http")
        processed["type"] = deployment_type

        if deployment_type == "stdio":
            # Handle stdio configuration
            stdio_config = deployment_config.get("stdio", {})
            if stdio_config:
                processed["stdio"] = {
                    "executable": stdio_config.get("executable", ""),
                    "args": stdio_config.get("args", []),
                    "workingDir": stdio_config.get("workingDir", "/tmp"),
                }
        elif deployment_type == "http":
            # Handle HTTP configuration
            http_config = deployment_config.get("http", {})
            if http_config:
                processed["http"] = {
                    "port": http_config.get("port", 8000),
                    "path": http_config.get("path", "/mcp"),
                }

        return processed

    def _process_container_config(self, container_config: dict[str, Any]) -> dict[str, Any]:
        """Process container configuration from registry format"""
        processed = {}

        # Required fields
        if "image" in container_config:
            processed["image"] = container_config["image"]

        # Optional fields
        if "port" in container_config:
            processed["port"] = container_config["port"]

        if "tag" in container_config:
            processed["tag"] = container_config["tag"]

        return processed

    def _process_resources_config(self, resources_config: dict[str, Any]) -> dict[str, Any]:
        """Process Kubernetes resources configuration"""
        processed = {}

        # Handle requests
        requests = resources_config.get("requests", {})
        if requests:
            processed["requests"] = {
                "cpu": requests.get("cpu", "50m"),
                "memory": requests.get("memory", "128Mi"),
            }

        # Handle limits
        limits = resources_config.get("limits", {})
        if limits:
            processed["limits"] = {
                "cpu": limits.get("cpu", "200m"),
                "memory": limits.get("memory", "256Mi"),
            }

        return processed
