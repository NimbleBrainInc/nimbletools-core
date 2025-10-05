"""
Test dynamic route loader functionality
"""

from unittest.mock import MagicMock, patch

from fastapi import APIRouter, FastAPI

from nimbletools_control_plane.route_loader import get_available_routes, load_routes


def test_load_routes_finds_and_loads_routers():
    """Test that load_routes discovers and loads router modules."""
    app = FastAPI()

    # Mock the routes directory with test files
    with patch("nimbletools_control_plane.route_loader.Path") as MockPath:
        mock_routes_dir = MagicMock()
        mock_routes_dir.exists.return_value = True

        # Mock finding two route files
        mock_file1 = MagicMock()
        mock_file1.name = "workspaces.py"
        mock_file1.stem = "workspaces"

        mock_file2 = MagicMock()
        mock_file2.name = "servers.py"
        mock_file2.stem = "servers"

        mock_routes_dir.glob.return_value = [mock_file1, mock_file2]
        # Setup the Path mock properly
        mock_path_instance = MagicMock()
        mock_path_instance.__truediv__ = MagicMock(return_value=mock_routes_dir)
        MockPath.return_value = mock_path_instance
        mock_path_instance.parent = mock_path_instance

        # Mock importlib to return modules with routers
        with patch("nimbletools_control_plane.route_loader.importlib.import_module") as mock_import:
            mock_module1 = MagicMock()
            mock_module1.router = APIRouter()

            mock_module2 = MagicMock()
            mock_module2.router = APIRouter()

            def import_side_effect(name):
                if name == "nimbletools_control_plane.routes.workspaces":
                    return mock_module1
                elif name == "nimbletools_control_plane.routes.servers":
                    return mock_module2
                raise ImportError(f"Module {name} not found")

            mock_import.side_effect = import_side_effect

            # Load routes
            load_routes(app)

            # Verify modules were imported
            assert mock_import.call_count == 2
            mock_import.assert_any_call("nimbletools_control_plane.routes.workspaces")
            mock_import.assert_any_call("nimbletools_control_plane.routes.servers")


def test_load_routes_skips_files_without_router():
    """Test that load_routes skips modules without a router attribute."""
    app = FastAPI()

    with patch("nimbletools_control_plane.route_loader.Path") as MockPath:
        mock_routes_dir = MagicMock()
        mock_routes_dir.exists.return_value = True

        mock_file = MagicMock()
        mock_file.name = "utils.py"
        mock_file.stem = "utils"

        mock_routes_dir.glob.return_value = [mock_file]
        mock_path_instance = MagicMock()
        mock_path_instance.__truediv__ = MagicMock(return_value=mock_routes_dir)
        MockPath.return_value = mock_path_instance
        mock_path_instance.parent = mock_path_instance

        with patch("nimbletools_control_plane.route_loader.importlib.import_module") as mock_import:
            # Module without router attribute
            mock_module = MagicMock(spec=[])
            mock_import.return_value = mock_module

            # Load routes
            load_routes(app)

            # Module was imported but router not included
            mock_import.assert_called_once_with("nimbletools_control_plane.routes.utils")


def test_load_routes_handles_import_errors():
    """Test that load_routes handles import errors gracefully."""
    app = FastAPI()

    with patch("nimbletools_control_plane.route_loader.Path") as MockPath:
        mock_routes_dir = MagicMock()
        mock_routes_dir.exists.return_value = True

        mock_file = MagicMock()
        mock_file.name = "broken.py"
        mock_file.stem = "broken"

        mock_routes_dir.glob.return_value = [mock_file]
        mock_path_instance = MagicMock()
        mock_path_instance.__truediv__ = MagicMock(return_value=mock_routes_dir)
        MockPath.return_value = mock_path_instance
        mock_path_instance.parent = mock_path_instance

        with patch("nimbletools_control_plane.route_loader.importlib.import_module") as mock_import:
            mock_import.side_effect = ImportError("Module not found")

            # Should not raise, just log the error
            load_routes(app)
            mock_import.assert_called_once()


def test_get_available_routes():
    """Test that get_available_routes returns list of route modules."""
    with patch("nimbletools_control_plane.route_loader.Path") as MockPath:
        mock_routes_dir = MagicMock()
        mock_routes_dir.exists.return_value = True

        mock_file1 = MagicMock()
        mock_file1.name = "workspaces.py"
        mock_file1.stem = "workspaces"

        mock_file2 = MagicMock()
        mock_file2.name = "servers.py"
        mock_file2.stem = "servers"

        mock_file3 = MagicMock()
        mock_file3.name = "__init__.py"
        mock_file3.stem = "__init__"

        mock_routes_dir.glob.return_value = [mock_file1, mock_file2, mock_file3]
        mock_path_instance = MagicMock()
        mock_path_instance.__truediv__ = MagicMock(return_value=mock_routes_dir)
        MockPath.return_value = mock_path_instance
        mock_path_instance.parent = mock_path_instance

        routes = get_available_routes()

        # Should exclude __init__.py
        assert len(routes) == 2
        assert "workspaces" in routes
        assert "servers" in routes
        assert "__init__" not in routes


def test_get_available_routes_missing_directory():
    """Test that get_available_routes returns empty list when directory doesn't exist."""
    with patch("nimbletools_control_plane.route_loader.Path") as MockPath:
        mock_routes_dir = MagicMock()
        mock_routes_dir.exists.return_value = False
        mock_path_instance = MagicMock()
        mock_path_instance.__truediv__ = MagicMock(return_value=mock_routes_dir)
        MockPath.return_value = mock_path_instance
        mock_path_instance.parent = mock_path_instance

        routes = get_available_routes()
        assert routes == []
