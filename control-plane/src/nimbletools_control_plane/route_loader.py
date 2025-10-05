"""
Dynamic route loader for NimbleTools Control Plane
"""

import importlib
import logging
from pathlib import Path

from fastapi import APIRouter, FastAPI

logger = logging.getLogger(__name__)


def load_routes(app: FastAPI) -> None:
    """
    Dynamically load all route modules from the routes directory.

    Each route module must have a 'router' attribute that is a FastAPI APIRouter instance.
    """
    routes_dir = Path(__file__).parent / "routes"

    if not routes_dir.exists():
        logger.warning("Routes directory not found: %s", routes_dir)
        return

    # Find all Python files in the routes directory (except __init__.py)
    route_files = [
        f for f in routes_dir.glob("*.py") if f.name != "__init__.py" and not f.name.startswith("_")
    ]

    for route_file in route_files:
        module_name = f"nimbletools_control_plane.routes.{route_file.stem}"

        try:
            # Import the module
            module = importlib.import_module(module_name)

            # Check if the module has a 'router' attribute
            if hasattr(module, "router"):
                router = module.router
                if isinstance(router, APIRouter):
                    app.include_router(router)
                    logger.info("Loaded router from module: %s", module_name)
                else:
                    logger.warning(
                        "Module %s has 'router' attribute but it's not an APIRouter instance",
                        module_name,
                    )
            else:
                logger.debug("Module %s does not have a 'router' attribute, skipping", module_name)

        except ImportError as e:
            logger.error("Failed to import route module %s: %s", module_name, e)
        except Exception as e:
            logger.error("Unexpected error loading route module %s: %s", module_name, e)


def get_available_routes() -> list[str]:
    """
    Get a list of available route modules.

    Returns:
        List of module names that can be loaded.
    """
    routes_dir = Path(__file__).parent / "routes"

    if not routes_dir.exists():
        return []

    route_files = [
        f.stem
        for f in routes_dir.glob("*.py")
        if f.name != "__init__.py" and not f.name.startswith("_")
    ]

    return route_files
