"""
Pluggable Authentication System for NimbleTools Control Plane
Defaults to NO authentication for community version
Enterprise authentication provided via plugins/extensions
"""

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from fastapi import Request

logger = logging.getLogger(__name__)


class AuthType(Enum):
    """Authentication types"""

    NONE = "none"
    JWT = "jwt"


@dataclass
class UserContext:
    """User context from authentication"""

    user_id: str
    email: str = "community@nimbletools.dev"
    role: str = "user"


@dataclass
class AuthenticatedRequest:
    """Authenticated request context"""

    auth_type: AuthType
    authenticated: bool
    user: UserContext | None = None


class AuthProvider(ABC):
    """Abstract base class for pluggable authentication providers"""

    @abstractmethod
    async def authenticate(self, request: Request) -> dict[str, Any] | None:
        """
        Authenticate a request and return user context
        Returns None if authentication fails or is not required
        """
        pass

    @abstractmethod
    async def authorize_workspace(self, user_context: dict[str, Any], workspace_id: str) -> bool:
        """
        Check if user can access a specific workspace
        Returns True if access is granted, False otherwise
        """
        pass


class NoneAuthProvider(AuthProvider):
    """
    Community/OSS default: No authentication required
    All users have full access to all resources
    """

    async def authenticate(self, _request: Request) -> dict[str, Any]:
        """Always return a default community user context"""
        return {
            "user_id": "community-user",
            "email": "community@nimbletools.dev",
            "role": "admin",  # Community version gives admin access
            "auth_type": "none",
        }

    async def authorize_workspace(self, _user_context: dict[str, Any], _workspace_id: str) -> bool:
        """Community version allows access to all workspaces"""
        return True


def create_auth_provider() -> AuthProvider:
    """
    Factory function to create the appropriate authentication provider

    Supports pluggable providers via AUTH_PROVIDER environment variable:
    - "none" (default): No authentication, full access for community version
    - Custom providers can be registered via plugins/extensions
    """
    auth_provider_name = os.getenv("AUTH_PROVIDER", "none").lower()

    if auth_provider_name == "none":
        logger.info("🔓 Using no-auth provider (community default)")
        return NoneAuthProvider()
    else:
        logger.warning("⚠️  Unknown auth provider '%s', falling back to no-auth", auth_provider_name)
        return NoneAuthProvider()
