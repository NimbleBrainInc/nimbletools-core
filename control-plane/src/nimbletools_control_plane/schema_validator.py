"""
Schema validation utilities for MCPService resources
"""

import logging
from typing import Any

import jsonschema
from fastapi import HTTPException
from kubernetes import client

logger = logging.getLogger(__name__)


class MCPServiceSchemaCache:
    """Cache for MCPService CRD schema to avoid repeated API calls"""

    def __init__(self) -> None:
        self._cached_schema: dict[str, Any] | None = None

    def get_schema(self) -> dict[str, Any]:
        """Get the MCPService schema from the CRD"""
        if self._cached_schema is not None:
            return self._cached_schema

        try:
            # Get CRD from Kubernetes API
            k8s_apiextensions = client.ApiextensionsV1Api()
            crd = k8s_apiextensions.read_custom_resource_definition(
                name="mcpservices.mcp.nimbletools.dev"
            )

            # Extract schema from CRD
            versions = crd.spec.versions
            for version in versions:
                if version.name == "v1" and version.served:
                    if hasattr(version.schema, "open_api_v3_schema"):
                        schema = version.schema.open_api_v3_schema
                    elif hasattr(version.schema, "openAPIV3Schema"):
                        schema = version.schema.openAPIV3Schema
                    else:
                        schema = version.schema

                    # Convert to dict if it's an object
                    if hasattr(schema, "to_dict"):
                        schema_dict: dict[str, Any] = schema.to_dict()
                    else:
                        schema_dict = dict(schema) if schema else {}

                    self._cached_schema = schema_dict
                    logger.info("Loaded MCPService schema from CRD")
                    return schema_dict

            raise ValueError("No served v1 version found in MCPService CRD")

        except Exception as e:
            logger.error("Failed to load MCPService schema: %s", e)
            raise HTTPException(
                status_code=500, detail="Failed to load MCPService schema for validation"
            ) from e

    def clear_cache(self) -> None:
        """Clear the cached schema (useful for testing or schema updates)"""
        self._cached_schema = None
        logger.info("MCPService schema cache cleared")


# Global instance
_schema_cache = MCPServiceSchemaCache()


def get_mcpservice_schema() -> dict[str, Any]:
    """Get the MCPService schema from the CRD"""
    return _schema_cache.get_schema()


def validate_mcpservice_spec(mcpservice_body: dict[str, Any], server_id: str) -> None:
    """
    Validate an MCPService resource against the CRD schema

    Args:
        mcpservice_body: The complete MCPService resource body
        server_id: Server ID for error messages

    Raises:
        HTTPException: If validation fails
    """
    try:
        schema = get_mcpservice_schema()

        # Validate the entire MCPService resource
        jsonschema.validate(instance=mcpservice_body, schema=schema)

        logger.info("MCPService %s passed schema validation", server_id)

    except jsonschema.ValidationError as e:
        # Extract the specific validation error
        error_path = (
            " -> ".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
        )
        error_msg = f"Schema validation failed for server '{server_id}' at {error_path}: {e.message}"

        logger.error("MCPService validation failed: %s", error_msg)
        raise HTTPException(
            status_code=400, detail=f"Invalid server specification: {error_msg}"
        ) from e

    except jsonschema.SchemaError as e:
        logger.error("Invalid MCPService schema: %s", e)
        raise HTTPException(
            status_code=500, detail="Internal schema validation error"
        ) from e


def validate_registry_server_spec(server_spec: dict[str, Any], server_id: str) -> None:
    """
    Validate that a registry server spec has the minimum required fields
    for creating a valid MCPService

    Args:
        server_spec: Server specification from registry
        server_id: Server ID for error messages

    Raises:
        HTTPException: If required fields are missing
    """
    # Check required container fields
    container_spec = server_spec.get("container", {})
    if not container_spec.get("image"):
        raise HTTPException(
            status_code=400,
            detail=f"Server '{server_id}' missing required 'container.image' in registry",
        )

    # Check deployment type is valid
    deployment_spec = server_spec.get("deployment", {})
    deployment_type = deployment_spec.get("type", "http")
    if deployment_type not in ["http", "stdio"]:
        raise HTTPException(
            status_code=400,
            detail=f"Server '{server_id}' has invalid deployment.type: {deployment_type}. Must be 'http' or 'stdio'",
        )

    # If stdio type, validate stdio configuration
    if deployment_type == "stdio":
        stdio_config = deployment_spec.get("stdio", {})
        if not stdio_config.get("executable"):
            raise HTTPException(
                status_code=400,
                detail=f"Server '{server_id}' stdio deployment missing required 'executable' field",
            )

    # Validate credentials structure
    credentials = server_spec.get("credentials", [])
    for i, cred in enumerate(credentials):
        if not isinstance(cred, dict):
            raise HTTPException(
                status_code=400,
                detail=f"Server '{server_id}' credential {i} must be an object",
            )
        if not cred.get("name"):
            raise HTTPException(
                status_code=400,
                detail=f"Server '{server_id}' credential {i} missing required 'name' field",
            )
        # Validate required field is boolean
        if "required" in cred and not isinstance(cred["required"], bool):
            raise HTTPException(
                status_code=400,
                detail=f"Server '{server_id}' credential '{cred['name']}' 'required' field must be boolean",
            )

    logger.info("Registry server spec %s passed validation", server_id)


def clear_schema_cache() -> None:
    """Clear the cached schema (useful for testing or schema updates)"""
    _schema_cache.clear_cache()
