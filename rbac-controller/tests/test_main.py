"""Tests for the main RBAC controller module."""

from unittest.mock import MagicMock, patch

from kubernetes.client.rest import ApiException

from nimbletools_rbac_controller.main import (
    MCP_OPERATOR_CLUSTER_ROLE,
    MCP_OPERATOR_NAMESPACE,
    MCP_OPERATOR_SERVICE_ACCOUNT,
    WORKSPACE_LABEL,
    WORKSPACE_PREFIX,
    create_mcp_operator_rolebinding,
    is_workspace_namespace,
    log,
)


class TestWorkspaceNamespaceDetection:
    """Test workspace namespace detection logic."""

    def test_should_detect_workspace_namespace_with_prefix_and_label(self):
        """Test detection of valid workspace namespace."""
        namespace_name = "ws-test-workspace"
        labels = {WORKSPACE_LABEL: "test-workspace"}

        result = is_workspace_namespace(namespace_name, labels)

        assert result is True

    def test_should_reject_namespace_without_workspace_prefix(self):
        """Test rejection of namespace without workspace prefix."""
        namespace_name = "default"
        labels = {WORKSPACE_LABEL: "test-workspace"}

        result = is_workspace_namespace(namespace_name, labels)

        assert result is False

    def test_should_reject_workspace_prefix_without_label(self):
        """Test rejection of namespace with prefix but no label."""
        namespace_name = "ws-test-workspace"
        labels = {}

        result = is_workspace_namespace(namespace_name, labels)

        assert result is False

    def test_should_handle_none_labels(self):
        """Test handling of None labels."""
        namespace_name = "ws-test-workspace"
        labels = None

        result = is_workspace_namespace(namespace_name, labels)

        assert result is False

    def test_should_handle_missing_workspace_label(self):
        """Test handling when workspace label is missing."""
        namespace_name = "ws-test-workspace"
        labels = {"other-label": "value"}

        result = is_workspace_namespace(namespace_name, labels)

        assert result is False


class TestRoleBindingCreation:
    """Test RoleBinding creation functionality."""

    @patch('nimbletools_rbac_controller.main.rbac_v1')
    @patch('nimbletools_rbac_controller.main.log')
    def test_should_create_rolebinding_successfully(self, _mock_log, mock_rbac_v1):
        """Test successful RoleBinding creation."""
        # Arrange - Set the global rbac_v1 to the mock
        import nimbletools_rbac_controller.main as main_module
        main_module.rbac_v1 = mock_rbac_v1

        mock_rbac_v1.read_namespaced_role_binding.side_effect = ApiException(status=404)
        mock_rbac_v1.create_namespaced_role_binding.return_value = MagicMock()
        namespace_name = "ws-test-workspace"

        # Act
        result = create_mcp_operator_rolebinding(namespace_name)

        # Assert
        assert result is True
        mock_rbac_v1.create_namespaced_role_binding.assert_called_once()
        call_args = mock_rbac_v1.create_namespaced_role_binding.call_args
        assert call_args[1]["namespace"] == namespace_name

        # Verify RoleBinding structure
        rolebinding = call_args[1]["body"]
        assert rolebinding.metadata.name == "nimbletools-operator-access"
        assert rolebinding.metadata.namespace == namespace_name
        assert rolebinding.subjects[0].name == MCP_OPERATOR_SERVICE_ACCOUNT
        assert rolebinding.subjects[0].namespace == MCP_OPERATOR_NAMESPACE
        assert rolebinding.role_ref.name == MCP_OPERATOR_CLUSTER_ROLE

        # Cleanup
        main_module.rbac_v1 = None

    @patch('nimbletools_rbac_controller.main.rbac_v1')
    @patch('nimbletools_rbac_controller.main.log')
    def test_should_skip_creation_when_rolebinding_exists(self, mock_log, mock_rbac_v1):
        """Test skipping creation when RoleBinding already exists."""
        # Arrange - Set the global rbac_v1 to the mock
        import nimbletools_rbac_controller.main as main_module
        main_module.rbac_v1 = mock_rbac_v1

        mock_rbac_v1.read_namespaced_role_binding.return_value = MagicMock()
        namespace_name = "ws-test-workspace"

        # Act
        result = create_mcp_operator_rolebinding(namespace_name)

        # Assert
        assert result is True
        mock_rbac_v1.create_namespaced_role_binding.assert_not_called()
        mock_log.assert_called_with(
            "RoleBinding nimbletools-operator-access already exists in ws-test-workspace"
        )

        # Cleanup
        main_module.rbac_v1 = None

    @patch('nimbletools_rbac_controller.main.rbac_v1')
    @patch('nimbletools_rbac_controller.main.log')
    def test_should_handle_api_exception_during_creation(self, mock_log, mock_rbac_v1):
        """Test handling of ApiException during RoleBinding creation."""
        # Arrange - Set the global rbac_v1 to the mock
        import nimbletools_rbac_controller.main as main_module
        main_module.rbac_v1 = mock_rbac_v1

        mock_rbac_v1.read_namespaced_role_binding.side_effect = ApiException(status=404)
        mock_rbac_v1.create_namespaced_role_binding.side_effect = ApiException(
            status=500, reason="Internal Server Error"
        )
        namespace_name = "ws-test-workspace"

        # Act
        result = create_mcp_operator_rolebinding(namespace_name)

        # Assert
        assert result is False
        mock_log.assert_called_with(
            "❌ Failed to create RoleBinding in ws-test-workspace: "
            "(500)\nReason: Internal Server Error\n"
        )

        # Cleanup
        main_module.rbac_v1 = None

    @patch('nimbletools_rbac_controller.main.rbac_v1')
    @patch('nimbletools_rbac_controller.main.log')
    def test_should_handle_unexpected_exception(self, mock_log, mock_rbac_v1):
        """Test handling of unexpected exceptions."""
        # Arrange - Set the global rbac_v1 to the mock
        import nimbletools_rbac_controller.main as main_module
        main_module.rbac_v1 = mock_rbac_v1

        mock_rbac_v1.read_namespaced_role_binding.side_effect = ValueError("Unexpected error")
        namespace_name = "ws-test-workspace"

        # Act
        result = create_mcp_operator_rolebinding(namespace_name)

        # Assert
        assert result is False
        mock_log.assert_called_with(
            "❌ Unexpected error creating RoleBinding in ws-test-workspace: Unexpected error"
        )

        # Cleanup
        main_module.rbac_v1 = None

    @patch('nimbletools_rbac_controller.main.rbac_v1')
    @patch('nimbletools_rbac_controller.main.log')
    def test_should_reraise_non_404_api_exceptions_during_check(self, _mock_log, mock_rbac_v1):
        """Test that non-404 ApiExceptions during existence check are re-raised."""
        # Arrange - Set the global rbac_v1 to the mock
        import nimbletools_rbac_controller.main as main_module
        main_module.rbac_v1 = mock_rbac_v1

        mock_rbac_v1.read_namespaced_role_binding.side_effect = ApiException(
            status=403, reason="Forbidden"
        )
        namespace_name = "ws-test-workspace"

        # Act
        result = create_mcp_operator_rolebinding(namespace_name)

        # Assert
        assert result is False
        mock_rbac_v1.create_namespaced_role_binding.assert_not_called()

        # Cleanup
        main_module.rbac_v1 = None

    @patch('nimbletools_rbac_controller.main.log')
    def test_should_return_false_when_rbac_client_not_initialized(self, mock_log):
        """Test handling when RBAC client is not initialized."""
        # Arrange - Ensure rbac_v1 is None
        import nimbletools_rbac_controller.main as main_module
        main_module.rbac_v1 = None
        namespace_name = "ws-test-workspace"

        # Act
        result = create_mcp_operator_rolebinding(namespace_name)

        # Assert
        assert result is False
        mock_log.assert_called_with("❌ RBAC client not initialized")


class TestLogging:
    """Test logging functionality."""

    @patch('nimbletools_rbac_controller.main.print')
    def test_should_format_log_message_correctly(self, mock_print):
        """Test that log messages are formatted correctly."""
        # Act
        log("Test message")

        # Assert
        mock_print.assert_called_once_with("RBAC-Controller: Test message", flush=True)


class TestConstants:
    """Test that constants are properly defined."""

    def test_constants_are_defined(self):
        """Test that all required constants are defined."""
        assert MCP_OPERATOR_SERVICE_ACCOUNT == "nimbletools-core"
        assert MCP_OPERATOR_NAMESPACE == "nimbletools-system"
        assert MCP_OPERATOR_CLUSTER_ROLE == "nimbletools-core-operator"
        assert WORKSPACE_LABEL == "mcp.nimbletools.dev/workspace_id"
        assert WORKSPACE_PREFIX == "ws-"

