"""Tests for auth module."""

from unittest.mock import Mock

import pytest
from fastapi import Request

from nimbletools_control_plane.auth import (
    AuthenticatedRequest,
    AuthType,
    NoneAuthProvider,
    UserContext,
    create_auth_provider,
)


class TestNoneAuthProvider:
    """Test the NoneAuthProvider."""

    @pytest.fixture
    def provider(self):
        return NoneAuthProvider()

    @pytest.fixture
    def mock_request(self):
        request = Mock(spec=Request)
        request.headers = {}
        return request

    @pytest.mark.asyncio
    async def test_authenticate_returns_user_context(self, provider, mock_request):
        """Test that NoneAuthProvider returns user context."""
        result = await provider.authenticate(mock_request)
        assert result is not None
        assert result["user_id"] == "community-user"
        assert result["email"] == "community@nimbletools.dev"
        assert result["role"] == "admin"


def test_create_auth_provider_default():
    """Test that create_auth_provider returns NoneAuthProvider by default."""
    provider = create_auth_provider()
    assert isinstance(provider, NoneAuthProvider)


def test_user_context():
    """Test UserContext data class."""
    context = UserContext(user_id="test-user", email="test@example.com", role="admin")
    assert context.user_id == "test-user"
    assert context.email == "test@example.com"
    assert context.role == "admin"


def test_authenticated_request():
    """Test AuthenticatedRequest data class."""
    user = UserContext(user_id="test-user", email="test@example.com", role="admin")
    auth_req = AuthenticatedRequest(
        auth_type=AuthType.JWT, authenticated=True, user=user
    )
    assert auth_req.auth_type == AuthType.JWT
    assert auth_req.authenticated is True
    assert auth_req.user == user
