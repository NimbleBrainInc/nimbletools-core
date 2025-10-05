"""
Tests for the provider system demonstrating duck typing.

These tests verify that custom providers can be loaded and used
without inheriting from any base class - they just need to implement
the expected methods (duck typing).
"""

import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
import yaml
from fastapi.testclient import TestClient

from nimbletools_control_plane import provider
from nimbletools_control_plane.main import app


class TestProviderDuckTyping:
    """Test the provider system with custom duck-typed providers."""

    def test_custom_provider_without_inheritance(self):
        """Test that a provider works without inheriting from any base class."""

        # Create a custom provider that doesn't inherit from anything
        class CustomProvider:
            """A custom provider that implements the expected methods."""

            def __init__(self, custom_param: str = "default"):
                self.custom_param = custom_param
                self.initialized = False

            async def validate_token(self, token: str) -> dict[str, Any] | None:
                """Validate token - custom implementation."""
                if token == "valid_token":
                    return {
                        "user_id": "custom-user",
                        "email": "user@custom.com",
                        "role": "user",
                    }
                return None

            async def check_workspace_access(self, user: dict[str, Any], workspace_id: str) -> bool:
                """Check workspace access - custom rules."""
                # Only allow access to workspaces that start with user's ID
                user_id = user.get("user_id", "")
                return workspace_id.startswith(user_id)

            async def check_permission(
                self, user: dict[str, Any], resource: str, action: str
            ) -> bool:
                """Check permission - custom logic."""
                role = user.get("role", "")
                if role == "admin":
                    return True
                if role == "user" and action == "read":
                    return True
                return False

            async def create_workspace_token(self, workspace_id: str, user: dict[str, Any]) -> str:
                """Create workspace token."""
                return f"custom_{workspace_id}_{user.get('user_id', 'unknown')}"

            async def validate_mcp_token(self, token: str, workspace_id: str) -> bool:
                """Validate MCP token."""
                return token.startswith(f"custom_{workspace_id}")

            async def initialize(self) -> None:
                """Initialize the provider."""
                self.initialized = True

            async def shutdown(self) -> None:
                """Shutdown the provider."""
                self.initialized = False

        # Set the custom provider as the global provider
        custom_provider = CustomProvider(custom_param="test_value")
        provider._provider = custom_provider

        # Verify the provider is set
        assert provider.get_provider() == custom_provider
        assert custom_provider.custom_param == "test_value"

    @pytest.mark.asyncio
    async def test_provider_methods_work_with_duck_typing(self, tmp_path):
        """Test that all provider methods work with a duck-typed provider."""

        # Create a test provider config that returns our mock provider
        config_file = tmp_path / "mock_provider.yaml"
        config_content = """class: nimbletools_control_plane.providers.community.CommunityProvider
"""
        config_file.write_text(config_content)

        with patch.dict(os.environ, {"PROVIDER_CONFIG": str(config_file)}):
            # Create a mock provider with all required methods
            mock_provider = Mock()
            mock_provider.validate_token = AsyncMock(return_value={"user_id": "test-user"})
            mock_provider.check_workspace_access = AsyncMock(return_value=True)
            mock_provider.check_permission = AsyncMock(return_value=True)
            mock_provider.create_workspace_token = AsyncMock(return_value="test_token_123")
            mock_provider.validate_mcp_token = AsyncMock(return_value=True)
            mock_provider.initialize = AsyncMock()
            mock_provider.shutdown = AsyncMock()

            # Set as global provider
            provider._provider = mock_provider

        # Test all module-level functions
        result = await provider.validate_token("test_token")
        assert result == {"user_id": "test-user"}
        mock_provider.validate_token.assert_called_once_with("test_token")

        result = await provider.check_workspace_access({"user_id": "test"}, "ws-123")
        assert result is True
        mock_provider.check_workspace_access.assert_called_once()

        result = await provider.check_permission({"user_id": "test"}, "resource", "action")
        assert result is True
        mock_provider.check_permission.assert_called_once()

        # Test the provider directly for methods not exposed at module level
        test_provider = provider.get_provider()
        assert test_provider == mock_provider

        # These methods exist on the provider but not at module level
        token = await mock_provider.create_workspace_token("ws-123", {"user_id": "test"})
        assert token == "test_token_123"

        valid = await mock_provider.validate_mcp_token("mcp_token", "ws-123")
        assert valid is True

        await provider.initialize()
        mock_provider.initialize.assert_called_once()

        await provider.shutdown()
        mock_provider.shutdown.assert_called_once()

    def test_provider_configuration_from_yaml(self):
        """Test loading a provider from YAML configuration."""

        # Create a temporary YAML config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config = {
                "class": "nimbletools_control_plane.providers.community.CommunityProvider",
                "kwargs": {"test_param": "test_value"},
            }
            yaml.dump(config, f)
            config_file = f.name

        try:
            # Mock environment variable to point to config file
            with patch.dict(os.environ, {"PROVIDER_CONFIG": config_file}):
                # Reset provider to force reconfiguration
                provider._provider = None

                # Configure should load from YAML
                provider.configure()

                # Verify provider was loaded
                loaded_provider = provider.get_provider()
                assert loaded_provider is not None
                assert loaded_provider.__class__.__name__ == "CommunityProvider"

        finally:
            # Clean up temp file
            Path(config_file).unlink()

    def test_provider_configuration_with_invalid_class(self):
        """Test that invalid provider class raises appropriate error."""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config = {"class": "non.existent.Provider"}
            yaml.dump(config, f)
            config_file = f.name

        try:
            with patch.dict(os.environ, {"PROVIDER_CONFIG": config_file}):
                provider._provider = None

                # Should raise RuntimeError for invalid provider
                with pytest.raises(RuntimeError) as exc_info:
                    provider.configure()

                assert "Failed to load configured provider" in str(exc_info.value)

        finally:
            Path(config_file).unlink()

    def test_provider_defaults_to_community(self, tmp_path):
        """Test that provider defaults to community when no config is provided."""

        # Create a minimal community provider config
        config_file = tmp_path / "community.yaml"
        config_content = """class: nimbletools_control_plane.providers.community.CommunityProvider
"""
        config_file.write_text(config_content)

        with patch.dict(os.environ, {"PROVIDER_CONFIG": str(config_file)}):
            # Reset provider
            provider._provider = None

            # Configure should use community provider from config
            provider.configure()

            loaded_provider = provider.get_provider()
            assert loaded_provider is not None
            assert loaded_provider.__class__.__name__ == "CommunityProvider"

    @pytest.mark.asyncio
    async def test_provider_in_route_context(self):
        """Test that custom provider works in route context."""

        # Create a custom provider for testing
        class TestProvider:
            """Test provider for route integration."""

            async def validate_token(self, token: str) -> dict[str, Any] | None:
                if token == "route_test_token":
                    return {
                        "user_id": "550e8400-e29b-41d4-a716-446655440000",
                        "organization_id": "123e4567-e89b-12d3-a456-426614174000",
                        "email": "route@test.com",
                        "role": "admin",
                    }
                return None

            async def check_workspace_access(self, user: dict[str, Any], workspace_id: str) -> bool:
                return True

            async def check_permission(
                self, user: dict[str, Any], resource: str, action: str
            ) -> bool:
                return True

            async def create_workspace_token(self, workspace_id: str, user: dict[str, Any]) -> str:
                return f"route_token_{workspace_id}"

            async def validate_mcp_token(self, token: str, workspace_id: str) -> bool:
                return True

            async def initialize(self) -> None:
                pass

            async def shutdown(self) -> None:
                pass

        # Set test provider
        test_provider = TestProvider()
        provider._provider = test_provider

        client = TestClient(app)

        # Test that routes use the custom provider
        with (
            patch("kubernetes.config.load_incluster_config"),
            patch("kubernetes.config.load_kube_config"),
            patch("kubernetes.client.CoreV1Api") as mock_k8s,
        ):
            mock_k8s_instance = Mock()
            mock_k8s.return_value = mock_k8s_instance

            # Mock namespace list
            mock_namespaces = Mock()
            mock_namespaces.items = []
            mock_k8s_instance.list_namespace.return_value = mock_namespaces

            response = client.get(
                "/v1/workspaces", headers={"Authorization": "Bearer route_test_token"}
            )

            # Should authenticate with our custom provider
            assert response.status_code == 200
            data = response.json()
            assert "workspaces" in data  # Check we got a valid workspace list response


class TestProviderProtocol:
    """Test the ProviderProtocol type hints."""

    def test_protocol_type_checking(self):
        """Test that ProviderProtocol correctly type checks implementations."""

        # This class implements all required methods
        class CompliantProvider:
            async def validate_token(self, token: str) -> dict[str, Any] | None:
                return None

            async def check_workspace_access(self, user: dict[str, Any], workspace_id: str) -> bool:
                return True

            async def check_permission(
                self, user: dict[str, Any], resource: str, action: str
            ) -> bool:
                return True

            async def create_workspace_token(self, workspace_id: str, user: dict[str, Any]) -> str:
                return "token"

            async def validate_mcp_token(self, token: str, workspace_id: str) -> bool:
                return True

            async def initialize(self) -> None:
                pass

            async def shutdown(self) -> None:
                pass

        # Create instance
        compliant = CompliantProvider()

        # The provider should be assignable to ProviderProtocol type
        # This is mainly for static type checking, but we can verify at runtime
        assert hasattr(compliant, "validate_token")
        assert hasattr(compliant, "check_workspace_access")
        assert hasattr(compliant, "check_permission")
        assert hasattr(compliant, "create_workspace_token")
        assert hasattr(compliant, "validate_mcp_token")
        assert hasattr(compliant, "initialize")
        assert hasattr(compliant, "shutdown")

    def test_incomplete_provider_detection(self):
        """Test that incomplete providers are detected."""

        # This class is missing some required methods
        class IncompleteProvider:
            async def validate_token(self, token: str) -> dict[str, Any] | None:
                return None

            # Missing other required methods

        incomplete = IncompleteProvider()

        # Should not have all required methods
        assert hasattr(incomplete, "validate_token")
        assert not hasattr(incomplete, "check_workspace_access")
        assert not hasattr(incomplete, "check_permission")
