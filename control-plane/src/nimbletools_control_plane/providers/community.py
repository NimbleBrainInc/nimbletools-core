"""
Community provider implementation.

This provider allows open access with no authentication.
All users are treated as administrators with full access.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class CommunityProvider:
    """
    Community provider

    It simply implements the expected methods (duck typing).
    """

    def __init__(self, **kwargs: dict[str, Any]):
        """Initialize community provider."""
        self.config = kwargs
        logger.info("Community provider initialized")

    async def validate_token(self, _token: str) -> dict[str, Any] | None:
        """
        Validate a token - always returns a community user.

        Args:
            token: Authentication token (ignored)

        Returns:
            User dictionary with community defaults
        """
        return {
            "user_id": "00000000-0000-0000-0000-000000000001",
            "organization_id": "00000000-0000-0000-0000-000000000002",
        }

    async def check_workspace_access(self, _user: dict[str, Any], _workspace_id: str) -> bool:
        """
        Check workspace access - always allowed in community edition.

        Args:
            user: User dictionary
            workspace_id: Workspace to check

        Returns:
            True (always allowed)
        """
        return True

    async def check_permission(self, _user: dict[str, Any], _resource: str, _action: str) -> bool:
        """
        Check permissions - always allowed in community edition.

        Args:
            user: User dictionary
            resource: Resource identifier
            action: Action to perform

        Returns:
            True (always allowed)
        """
        return True

    async def initialize(self) -> None:
        """Initialize provider - no-op for community."""
        logger.info("Community provider ready")

    async def shutdown(self) -> None:
        """Shutdown provider - no-op for community."""
        logger.info("Community provider shutdown")
