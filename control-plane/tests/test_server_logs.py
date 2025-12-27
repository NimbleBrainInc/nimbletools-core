"""Tests for server logs endpoint."""

from datetime import UTC, datetime
from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException
from kubernetes.client.rest import ApiException

from nimbletools_control_plane.models import (
    LogLevel,
    ServerLogsRequest,
    ServerLogsResponse,
)
from nimbletools_control_plane.routes.servers import _parse_log_line, get_server_logs


class TestLogLineParsing:
    """Test log line parsing logic."""

    def test_parse_iso_format_with_brackets(self):
        """Test parsing ISO format with bracketed log level."""
        line = "2024-01-01T12:00:00.000Z [INFO] Application started"
        timestamp, level, message = _parse_log_line(line)

        assert timestamp is not None
        assert timestamp.year == 2024
        assert timestamp.month == 1
        assert timestamp.day == 1
        assert level == LogLevel.INFO
        assert message == "Application started"

    def test_parse_rfc3339_format_no_brackets(self):
        """Test parsing RFC3339 format without brackets."""
        line = "2024-01-01T12:00:00Z ERROR Database connection failed"
        timestamp, level, message = _parse_log_line(line)

        assert timestamp is not None
        assert level == LogLevel.ERROR
        assert message == "Database connection failed"

    def test_parse_with_warn_level(self):
        """Test parsing WARN level (should map to WARNING)."""
        line = "2024-01-01T12:00:00Z [WARN] Low memory"
        timestamp, level, message = _parse_log_line(line)

        assert level == LogLevel.WARNING
        assert message == "Low memory"

    def test_parse_with_fatal_level(self):
        """Test parsing FATAL level (should map to CRITICAL)."""
        line = "2024-01-01T12:00:00Z [FATAL] System crash"
        timestamp, level, message = _parse_log_line(line)

        assert level == LogLevel.CRITICAL
        assert message == "System crash"

    def test_parse_no_timestamp(self):
        """Test parsing line with no timestamp."""
        line = "[DEBUG] This is a debug message"
        timestamp, level, message = _parse_log_line(line)

        assert timestamp is None
        assert level == LogLevel.DEBUG
        assert message == line  # Full line becomes message when no timestamp

    def test_parse_malformed_line(self):
        """Test parsing malformed line defaults to INFO."""
        line = "Random log message without structure"
        timestamp, level, message = _parse_log_line(line)

        assert timestamp is None
        assert level == LogLevel.INFO
        assert message == line

    def test_parse_iso_format_without_z_is_timezone_aware(self):
        """Test that timestamps without Z suffix are parsed as timezone-aware UTC.

        This prevents comparison errors between offset-naive and offset-aware datetimes
        when filtering logs by since/until parameters.
        """
        # ISO format without Z (can occur in some log formats)
        line = "2024-01-01T12:00:00 [INFO] Message without Z suffix"
        timestamp, level, message = _parse_log_line(line)

        assert timestamp is not None
        # Critical: timestamp must be timezone-aware to compare with request filters
        assert timestamp.tzinfo is not None
        assert timestamp.tzinfo == UTC
        assert level == LogLevel.INFO

    def test_parse_iso_format_with_z_is_timezone_aware(self):
        """Test that timestamps with Z suffix are parsed as timezone-aware."""
        line = "2024-01-01T12:00:00Z [INFO] Message with Z suffix"
        timestamp, level, message = _parse_log_line(line)

        assert timestamp is not None
        assert timestamp.tzinfo is not None
        assert level == LogLevel.INFO


class TestServerLogsEndpoint:
    """Test server logs endpoint functionality."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request object."""
        request = Mock()
        request.state = Mock()
        request.state.auth_context = Mock()
        request.state.auth_context.user_id = "user-123"
        request.state.auth_context.organization_id = "org-456"
        return request

    @pytest.fixture
    def sample_pods(self):
        """Sample pod list response."""
        container1 = Mock()
        container1.name = "echo-container"

        container2 = Mock()
        container2.name = "echo-container"

        pod1 = Mock()
        pod1.metadata.name = "echo-deployment-abc123"
        pod1.spec.containers = [container1]

        pod2 = Mock()
        pod2.metadata.name = "echo-deployment-def456"
        pod2.spec.containers = [container2]

        pods = Mock()
        pods.items = [pod1, pod2]
        return pods

    @pytest.fixture
    def sample_log_content(self):
        """Sample log content from Kubernetes."""
        return """2024-01-01T10:00:00Z [INFO] Server starting
2024-01-01T10:00:01Z [INFO] Loading configuration
2024-01-01T10:00:02Z [DEBUG] Configuration loaded successfully
2024-01-01T10:00:03Z [INFO] Starting HTTP server on port 8000
2024-01-01T10:00:04Z [INFO] Server ready to accept connections
2024-01-01T10:01:00Z [WARNING] High memory usage detected
2024-01-01T10:02:00Z [ERROR] Failed to connect to database
2024-01-01T10:02:01Z [ERROR] Retrying database connection
2024-01-01T10:02:02Z [INFO] Database connection restored
2024-01-01T10:03:00Z [INFO] Processing request from client"""

    @pytest.mark.asyncio
    @patch("nimbletools_control_plane.routes.servers.client.CoreV1Api")
    async def test_get_server_logs_default_limit(
        self, mock_k8s_core, mock_request, sample_pods, sample_log_content
    ):
        """Test getting server logs with default limit of 10."""
        # Setup mocks
        mock_api = Mock()
        mock_k8s_core.return_value = mock_api
        mock_api.list_namespaced_pod.return_value = sample_pods
        mock_api.read_namespaced_pod_log.return_value = sample_log_content

        # Create request
        logs_request = ServerLogsRequest()

        # Call endpoint
        response = await get_server_logs(
            workspace_id="550e8400-e29b-41d4-a716-446655440000",
            server_id="echo",
            request=mock_request,
            logs_request=logs_request,
            namespace_name="ws-test-namespace",
        )

        # Verify response
        assert isinstance(response, ServerLogsResponse)
        assert response.server_id == "echo"
        assert response.workspace_id == UUID("550e8400-e29b-41d4-a716-446655440000")
        assert response.count == 10  # Default limit
        assert len(response.logs) == 10
        # We have 20 total logs (10 from each of 2 pods), so has_more should be True
        assert response.has_more is True

        # Verify logs are sorted newest first
        for i in range(1, len(response.logs)):
            assert response.logs[i - 1].timestamp >= response.logs[i].timestamp

    @pytest.mark.asyncio
    @patch("nimbletools_control_plane.routes.servers.client.CoreV1Api")
    async def test_get_server_logs_with_level_filter(
        self, mock_k8s_core, mock_request, sample_pods, sample_log_content
    ):
        """Test getting server logs filtered by log level."""
        # Setup mocks
        mock_api = Mock()
        mock_k8s_core.return_value = mock_api
        mock_api.list_namespaced_pod.return_value = sample_pods
        mock_api.read_namespaced_pod_log.return_value = sample_log_content

        # Create request filtering for WARNING and above
        logs_request = ServerLogsRequest(level=LogLevel.WARNING, limit=50)

        # Call endpoint
        response = await get_server_logs(
            workspace_id="550e8400-e29b-41d4-a716-446655440000",
            server_id="echo",
            request=mock_request,
            logs_request=logs_request,
            namespace_name="ws-test-namespace",
        )

        # Should only have WARNING and ERROR logs (from 2 pods each)
        assert response.count == 6  # (1 WARNING + 2 ERROR logs) * 2 pods
        for log_entry in response.logs:
            assert log_entry.level in [LogLevel.WARNING, LogLevel.ERROR]

    @pytest.mark.asyncio
    @patch("nimbletools_control_plane.routes.servers.client.CoreV1Api")
    async def test_get_server_logs_with_time_range(
        self, mock_k8s_core, mock_request, sample_pods, sample_log_content
    ):
        """Test getting server logs within a time range."""
        # Setup mocks
        mock_api = Mock()
        mock_k8s_core.return_value = mock_api
        mock_api.list_namespaced_pod.return_value = sample_pods
        mock_api.read_namespaced_pod_log.return_value = sample_log_content

        # Create request with time range
        since_time = datetime(2024, 1, 1, 10, 1, 0, tzinfo=UTC)
        until_time = datetime(2024, 1, 1, 10, 2, 30, tzinfo=UTC)
        logs_request = ServerLogsRequest(since=since_time, until=until_time, limit=50)

        # Call endpoint
        response = await get_server_logs(
            workspace_id="550e8400-e29b-41d4-a716-446655440000",
            server_id="echo",
            request=mock_request,
            logs_request=logs_request,
            namespace_name="ws-test-namespace",
        )

        # Should only have logs between 10:01:00 and 10:02:30 (from 2 pods each)
        assert response.count == 8  # (Logs at 10:01, 10:02:00, 10:02:01, 10:02:02) * 2 pods
        for log_entry in response.logs:
            assert log_entry.timestamp >= since_time
            assert log_entry.timestamp <= until_time

    @pytest.mark.asyncio
    @patch("nimbletools_control_plane.routes.servers.client.CoreV1Api")
    async def test_get_server_logs_no_pods(self, mock_k8s_core, mock_request):
        """Test getting logs when no pods exist."""
        # Setup mocks
        mock_api = Mock()
        mock_k8s_core.return_value = mock_api

        # No pods found
        empty_pods = Mock()
        empty_pods.items = []
        mock_api.list_namespaced_pod.return_value = empty_pods

        # Create request
        logs_request = ServerLogsRequest()

        # Call endpoint
        response = await get_server_logs(
            workspace_id="550e8400-e29b-41d4-a716-446655440000",
            server_id="echo",
            request=mock_request,
            logs_request=logs_request,
            namespace_name="ws-test-namespace",
        )

        # Should return empty logs
        assert response.count == 0
        assert len(response.logs) == 0
        assert response.has_more is False

    @pytest.mark.asyncio
    @patch("nimbletools_control_plane.routes.servers.client.CoreV1Api")
    async def test_get_server_logs_pod_filter(
        self, mock_k8s_core, mock_request, sample_pods, sample_log_content
    ):
        """Test getting logs from specific pod."""
        # Setup mocks
        mock_api = Mock()
        mock_k8s_core.return_value = mock_api
        mock_api.list_namespaced_pod.return_value = sample_pods
        mock_api.read_namespaced_pod_log.return_value = sample_log_content

        # Create request for specific pod
        logs_request = ServerLogsRequest(pod_name="echo-deployment-abc123")

        # Call endpoint
        response = await get_server_logs(
            workspace_id="550e8400-e29b-41d4-a716-446655440000",
            server_id="echo",
            request=mock_request,
            logs_request=logs_request,
            namespace_name="ws-test-namespace",
        )

        # Verify only one pod was queried
        assert mock_api.read_namespaced_pod_log.call_count == 1
        call_args = mock_api.read_namespaced_pod_log.call_args[1]
        assert call_args["name"] == "echo-deployment-abc123"

        # Should have logs from that pod
        assert response.count > 0
        for log_entry in response.logs:
            assert log_entry.pod_name == "echo-deployment-abc123"

    @pytest.mark.asyncio
    @patch("nimbletools_control_plane.routes.servers.client.CoreV1Api")
    async def test_get_server_logs_server_not_found(self, mock_k8s_core, mock_request):
        """Test getting logs for non-existent server."""
        # Setup mocks
        mock_api = Mock()
        mock_k8s_core.return_value = mock_api

        # Simulate 404 when listing pods
        mock_api.list_namespaced_pod.side_effect = ApiException(status=404)

        # Create request
        logs_request = ServerLogsRequest()

        # Call endpoint - should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await get_server_logs(
                workspace_id="550e8400-e29b-41d4-a716-446655440000",
                server_id="nonexistent",
                request=mock_request,
                logs_request=logs_request,
                namespace_name="ws-test-namespace",
            )

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    @patch("nimbletools_control_plane.routes.servers.client.CoreV1Api")
    async def test_get_server_logs_handles_full_server_name(
        self, mock_k8s_core, mock_request, sample_pods, sample_log_content
    ):
        """Test that full server names like ai.nimblebrain/echo are handled correctly."""
        # Setup mocks
        mock_api = Mock()
        mock_k8s_core.return_value = mock_api
        mock_api.list_namespaced_pod.return_value = sample_pods
        mock_api.read_namespaced_pod_log.return_value = sample_log_content

        # Create request
        logs_request = ServerLogsRequest()

        # Call with full server name
        response = await get_server_logs(
            workspace_id="550e8400-e29b-41d4-a716-446655440000",
            server_id="ai.nimblebrain/echo",  # Full name with slashes
            request=mock_request,
            logs_request=logs_request,
            namespace_name="ws-test-namespace",
        )

        # Should extract just "echo" as the server ID
        assert response.server_id == "echo"

        # Verify correct label selector was used
        mock_api.list_namespaced_pod.assert_called_once()
        call_args = mock_api.list_namespaced_pod.call_args[1]
        assert call_args["label_selector"] == "app=echo"

    @pytest.mark.asyncio
    @patch("nimbletools_control_plane.routes.servers.client.CoreV1Api")
    async def test_get_server_logs_with_has_more_flag(
        self, mock_k8s_core, mock_request, sample_pods
    ):
        """Test that has_more flag is set correctly when more logs exist."""
        # Create log content with more lines than limit
        many_logs = "\n".join(
            [f"2024-01-01T10:00:{i:02d}Z [INFO] Log message {i}" for i in range(30)]
        )

        # Setup mocks
        mock_api = Mock()
        mock_k8s_core.return_value = mock_api
        mock_api.list_namespaced_pod.return_value = sample_pods
        mock_api.read_namespaced_pod_log.return_value = many_logs

        # Create request with limit of 10
        logs_request = ServerLogsRequest(limit=10)

        # Call endpoint
        response = await get_server_logs(
            workspace_id="550e8400-e29b-41d4-a716-446655440000",
            server_id="echo",
            request=mock_request,
            logs_request=logs_request,
            namespace_name="ws-test-namespace",
        )

        # Should have exactly 10 logs with has_more=True
        assert response.count == 10
        assert len(response.logs) == 10
        assert response.has_more is True
