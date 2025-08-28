"""
Routes module for NimbleTools Control Plane
"""

from .registry import router as registry_router
from .servers import router as servers_router
from .workspaces import router as workspaces_router

__all__ = ["registry_router", "servers_router", "workspaces_router"]
