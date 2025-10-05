"""
Provider system for NimbleTools Control Plane.

This module implements a duck-typed provider pattern where providers
implement expected methods without inheritance. Enterprise providers
can be added via Docker composition without importing from this module.

Provider Protocol (methods that providers should implement):
- async validate_token(token: str) -> dict | None
- async check_workspace_access(user: dict, workspace_id: str) -> bool
- async check_permission(user: dict, resource: str, action: str) -> bool
- async initialize() -> None
- async shutdown() -> None
"""

import importlib
import logging
import os
from pathlib import Path
from typing import Any, Protocol, cast

import yaml

logger = logging.getLogger(__name__)


class ProviderProtocol(Protocol):
    """Protocol defining the provider interface."""

    async def validate_token(self, token: str) -> dict[str, Any] | None:
        """Validate an authentication token."""
        ...

    async def check_workspace_access(self, user: dict[str, Any], workspace_id: str) -> bool:
        """Check if user can access a workspace."""
        ...

    async def check_permission(self, user: dict[str, Any], resource: str, action: str) -> bool:
        """Check if user can perform an action on a resource."""
        ...

    async def initialize(self) -> None:
        """Initialize the provider."""
        ...

    async def shutdown(self) -> None:
        """Shutdown the provider."""
        ...


# Global provider instance
_provider: ProviderProtocol | None = None


def load_provider_config() -> dict[str, Any]:
    """Load provider configuration from YAML file."""
    config_path = os.getenv("PROVIDER_CONFIG", "")

    if not config_path:
        raise RuntimeError(
            "PROVIDER_CONFIG environment variable not set. "
            "Provider configuration is required for security. "
            "Set PROVIDER_CONFIG to the path of your provider configuration YAML file."
        )

    if not Path(config_path).exists():
        raise RuntimeError(
            f"Provider configuration file not found at: {config_path}. "
            "Please ensure the PROVIDER_CONFIG environment variable points to a valid configuration file."
        )

    logger.info("Loading provider config from: %s", config_path)
    with Path(config_path).open() as f:
        result = yaml.safe_load(f)
        return cast("dict[str, Any]", result)


def configure() -> None:
    """Configure the global provider from configuration."""
    global _provider  # noqa: PLW0603

    config = load_provider_config()
    class_path = config.get("class")
    kwargs = config.get("kwargs", {})

    if not class_path:
        raise ValueError("Provider class not specified in configuration")

    try:
        # Split module and class name
        module_path, class_name = class_path.rsplit(".", 1)

        # Import the module
        logger.info("Loading provider module: %s", module_path)
        module = importlib.import_module(module_path)

        # Get the class
        provider_class = getattr(module, class_name)

        # Instantiate the provider
        logger.info("Creating provider instance: %s", class_name)
        _provider = provider_class(**kwargs)

        logger.info("Provider configured successfully: %s", class_path)

    except Exception as e:
        logger.error("Failed to configure provider %s: %s", class_path, e)
        raise RuntimeError(f"Failed to load configured provider {class_path}: {e}") from e


def get_provider() -> ProviderProtocol:
    """Get the configured provider instance."""
    if _provider is None:
        configure()

    # Typecheck
    if _provider is None:
        raise RuntimeError("Provider not configured")

    return _provider


# Module-level convenience functions that delegate to the provider
async def validate_token(token: str) -> dict[str, Any] | None:
    """Validate an authentication token."""
    return await get_provider().validate_token(token)


async def check_workspace_access(user: dict[str, Any], workspace_id: str) -> bool:
    """Check if user can access a workspace."""
    return await get_provider().check_workspace_access(user, workspace_id)


async def check_permission(user: dict[str, Any], resource: str, action: str) -> bool:
    """Check if user can perform an action on a resource."""
    return await get_provider().check_permission(user, resource, action)


async def initialize() -> None:
    """Initialize the provider."""
    await get_provider().initialize()


async def shutdown() -> None:
    """Shutdown the provider."""
    await get_provider().shutdown()
