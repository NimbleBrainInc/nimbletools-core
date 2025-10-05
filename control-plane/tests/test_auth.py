"""Tests for auth module."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException, Request

from nimbletools_control_plane.auth import (
    UserContext,
    extract_token,
    get_current_user,
)


class TestAuthModels:
    """Test auth model classes."""

    def test_user_context(self):
        """Test UserContext data class."""
        context = UserContext(user_id="test-user", email="test@example.com", role="admin")
        assert context.user_id == "test-user"
        assert context.email == "test@example.com"
        assert context.role == "admin"


class TestAuthFunctions:
    """Test auth functions."""

    @pytest.fixture
    def mock_request(self):
        request = Mock(spec=Request)
        request.headers = {}
        return request

    def test_extract_token_no_header(self, mock_request):
        """Test extract_token with no auth header."""
        assert extract_token(mock_request) is None

    def test_extract_token_with_bearer(self, mock_request):
        """Test extract_token with Bearer token."""
        mock_request.headers = {"authorization": "Bearer test-token"}
        assert extract_token(mock_request) == "test-token"

    def test_extract_token_without_bearer(self, mock_request):
        """Test extract_token with non-Bearer auth."""
        mock_request.headers = {"authorization": "Basic test-token"}
        assert extract_token(mock_request) is None

    @pytest.mark.asyncio
    async def test_get_current_user_with_valid_token(self, mock_request):
        """Test get_current_user with valid token."""
        mock_request.headers = {"authorization": "Bearer valid-token"}

        with patch("nimbletools_control_plane.auth.base.provider") as mock_provider:
            mock_provider.validate_token = AsyncMock(
                return_value={"user_id": "test-user", "email": "test@example.com", "role": "admin"}
            )

            user = await get_current_user(mock_request)
            assert user["user_id"] == "test-user"
            assert user["email"] == "test@example.com"
            mock_provider.validate_token.assert_awaited_once_with("valid-token")

    @pytest.mark.asyncio
    async def test_get_current_user_with_invalid_token(self, mock_request):
        """Test get_current_user with invalid token."""
        mock_request.headers = {"authorization": "Bearer invalid-token"}

        with patch("nimbletools_control_plane.auth.base.provider") as mock_provider:
            mock_provider.validate_token = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_request)

            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Authentication required"
