"""
Authentication models for NimbleTools Control Plane.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class UserContext:
    """User context information."""

    user_id: str
    email: str | None = None
    role: str = "user"
    metadata: dict[str, Any] | None = None
