"""
Routes module for NimbleTools Control Plane
"""

from .servers import router as servers_router
from .workspaces import router as workspaces_router

__all__ = ["servers_router", "workspaces_router"]
