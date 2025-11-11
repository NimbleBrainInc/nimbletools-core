"""Tests for deployment phase determination logic"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nimbletools_control_plane.routes.servers import (
    _check_pod_failure_status,
    determine_deployment_phase,
)


class TestCheckPodFailureStatus:
    """Tests for _check_pod_failure_status helper function"""

    @pytest.mark.asyncio
    async def test_returns_true_for_image_pull_backoff(self):
        """Should detect ImagePullBackOff as failure"""
        mock_pod = MagicMock()
        mock_container_status = MagicMock()
        mock_container_status.state.waiting.reason = "ImagePullBackOff"
        mock_pod.status.container_statuses = [mock_container_status]

        mock_pods_list = MagicMock()
        mock_pods_list.items = [mock_pod]

        with patch("nimbletools_control_plane.routes.servers.client.CoreV1Api") as mock_api:
            mock_api.return_value.list_namespaced_pod.return_value = mock_pods_list

            result = await _check_pod_failure_status("test-namespace", "test-server")
            assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_for_crash_loop_backoff(self):
        """Should detect CrashLoopBackOff as failure"""
        mock_pod = MagicMock()
        mock_container_status = MagicMock()
        mock_container_status.state.waiting.reason = "CrashLoopBackOff"
        mock_pod.status.container_statuses = [mock_container_status]

        mock_pods_list = MagicMock()
        mock_pods_list.items = [mock_pod]

        with patch("nimbletools_control_plane.routes.servers.client.CoreV1Api") as mock_api:
            mock_api.return_value.list_namespaced_pod.return_value = mock_pods_list

            result = await _check_pod_failure_status("test-namespace", "test-server")
            assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_for_normal_waiting_state(self):
        """Should not treat ContainerCreating as failure"""
        mock_pod = MagicMock()
        mock_container_status = MagicMock()
        mock_container_status.state.waiting.reason = "ContainerCreating"
        mock_pod.status.container_statuses = [mock_container_status]

        mock_pods_list = MagicMock()
        mock_pods_list.items = [mock_pod]

        with patch("nimbletools_control_plane.routes.servers.client.CoreV1Api") as mock_api:
            mock_api.return_value.list_namespaced_pod.return_value = mock_pods_list

            result = await _check_pod_failure_status("test-namespace", "test-server")
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_pods(self):
        """Should return False when no pods exist"""
        mock_pods_list = MagicMock()
        mock_pods_list.items = []

        with patch("nimbletools_control_plane.routes.servers.client.CoreV1Api") as mock_api:
            mock_api.return_value.list_namespaced_pod.return_value = mock_pods_list

            result = await _check_pod_failure_status("test-namespace", "test-server")
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_exception(self):
        """Should return False and log warning on API exception"""
        with patch("nimbletools_control_plane.routes.servers.client.CoreV1Api") as mock_api:
            mock_api.return_value.list_namespaced_pod.side_effect = Exception("API error")

            result = await _check_pod_failure_status("test-namespace", "test-server")
            assert result is False


class TestDetermineDeploymentPhase:
    """Tests for determine_deployment_phase function"""

    @pytest.mark.asyncio
    async def test_returns_pending_when_no_deployment(self):
        """Should return Pending when deployment is None"""
        result = await determine_deployment_phase(None, "test-ns", "test-server")
        assert result == "Pending"

    @pytest.mark.asyncio
    async def test_returns_pending_when_deployment_has_no_status(self):
        """Should return Pending when deployment.status is None"""
        mock_deployment = MagicMock()
        mock_deployment.status = None

        result = await determine_deployment_phase(mock_deployment, "test-ns", "test-server")
        assert result == "Pending"

    @pytest.mark.asyncio
    async def test_returns_failed_for_replica_failure_condition(self):
        """Should return Failed when ReplicaFailure condition is True"""
        mock_deployment = MagicMock()
        mock_condition = MagicMock()
        mock_condition.type = "ReplicaFailure"
        mock_condition.status = "True"
        mock_deployment.status.conditions = [mock_condition]
        mock_deployment.status.ready_replicas = 0
        mock_deployment.status.replicas = 1
        mock_deployment.status.unavailable_replicas = 1

        result = await determine_deployment_phase(mock_deployment, "test-ns", "test-server")
        assert result == "Failed"

    @pytest.mark.asyncio
    async def test_returns_failed_for_progress_deadline_exceeded(self):
        """Should return Failed when Progressing=False with ProgressDeadlineExceeded"""
        mock_deployment = MagicMock()
        mock_condition = MagicMock()
        mock_condition.type = "Progressing"
        mock_condition.status = "False"
        mock_condition.reason = "ProgressDeadlineExceeded"
        mock_deployment.status.conditions = [mock_condition]
        mock_deployment.status.ready_replicas = 0
        mock_deployment.status.replicas = 1
        mock_deployment.status.unavailable_replicas = 1

        result = await determine_deployment_phase(mock_deployment, "test-ns", "test-server")
        assert result == "Failed"

    @pytest.mark.asyncio
    async def test_returns_running_when_ready_replicas_exists(self):
        """Should return Running when ready_replicas > 0"""
        mock_deployment = MagicMock()
        mock_deployment.status.conditions = None
        mock_deployment.status.ready_replicas = 1
        mock_deployment.status.replicas = 1
        mock_deployment.status.unavailable_replicas = 0

        result = await determine_deployment_phase(mock_deployment, "test-ns", "test-server")
        assert result == "Running"

    @pytest.mark.asyncio
    async def test_returns_stopped_when_no_replicas(self):
        """Should return Stopped when total_replicas is 0"""
        mock_deployment = MagicMock()
        mock_deployment.status.conditions = None
        mock_deployment.status.ready_replicas = 0
        mock_deployment.status.replicas = 0
        mock_deployment.status.unavailable_replicas = 0

        result = await determine_deployment_phase(mock_deployment, "test-ns", "test-server")
        assert result == "Stopped"

    @pytest.mark.asyncio
    async def test_returns_failed_when_pods_have_image_pull_backoff(self):
        """Should return Failed when pods are in ImagePullBackOff"""
        mock_deployment = MagicMock()
        mock_deployment.status.conditions = None
        mock_deployment.status.ready_replicas = 0
        mock_deployment.status.replicas = 1
        mock_deployment.status.unavailable_replicas = 1

        with patch(
            "nimbletools_control_plane.routes.servers._check_pod_failure_status",
            new_callable=AsyncMock,
        ) as mock_check:
            mock_check.return_value = True

            result = await determine_deployment_phase(mock_deployment, "test-ns", "test-server")
            assert result == "Failed"
            mock_check.assert_called_once_with("test-ns", "test-server")

    @pytest.mark.asyncio
    async def test_returns_pending_when_replicas_exist_but_no_failures(self):
        """Should return Pending when replicas exist but none ready and no pod failures"""
        mock_deployment = MagicMock()
        mock_deployment.status.conditions = None
        mock_deployment.status.ready_replicas = 0
        mock_deployment.status.replicas = 1
        mock_deployment.status.unavailable_replicas = 1

        with patch(
            "nimbletools_control_plane.routes.servers._check_pod_failure_status",
            new_callable=AsyncMock,
        ) as mock_check:
            mock_check.return_value = False

            result = await determine_deployment_phase(mock_deployment, "test-ns", "test-server")
            assert result == "Pending"

    @pytest.mark.asyncio
    async def test_does_not_check_pod_status_when_no_unavailable_replicas(self):
        """Should not check pod status when unavailable_replicas is 0"""
        mock_deployment = MagicMock()
        mock_deployment.status.conditions = None
        mock_deployment.status.ready_replicas = 0
        mock_deployment.status.replicas = 1
        mock_deployment.status.unavailable_replicas = 0

        with patch(
            "nimbletools_control_plane.routes.servers._check_pod_failure_status",
            new_callable=AsyncMock,
        ) as mock_check:
            result = await determine_deployment_phase(mock_deployment, "test-ns", "test-server")
            assert result == "Pending"
            mock_check.assert_not_called()
