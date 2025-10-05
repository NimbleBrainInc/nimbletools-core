"""Tests for workspace utility functions."""

import uuid

from nimbletools_control_plane.workspace_utils import (
    generate_workspace_identifiers,
    get_namespace_from_workspace_id,
)


def test_generate_workspace_identifiers():
    """Test workspace identifier generation."""
    base_name = "test-workspace"

    result = generate_workspace_identifiers(base_name)

    # Check all required keys are present
    assert "workspace_id" in result
    assert "workspace_name" in result
    assert "namespace_name" in result

    # Check workspace_id is a valid UUID
    workspace_id = result["workspace_id"]
    assert uuid.UUID(workspace_id)  # Will raise if not valid UUID

    # Check workspace_name is just the base name (no UUID)
    workspace_name = result["workspace_name"]
    assert workspace_name == base_name

    # Check namespace_name format (includes base name and UUID)
    namespace_name = result["namespace_name"]
    assert namespace_name == f"ws-{base_name}-{workspace_id}"


def test_generate_workspace_identifiers_with_special_chars():
    """Test workspace identifier generation with special characters in name."""
    base_name = "my-awesome-workspace"

    result = generate_workspace_identifiers(base_name)

    # workspace_name should be just the base name
    workspace_name = result["workspace_name"]
    assert workspace_name == base_name

    # namespace should contain the UUID
    namespace_name = result["namespace_name"]
    assert namespace_name.startswith(f"ws-{base_name}-")

    # Extract and validate UUID from namespace
    uuid_part = namespace_name.replace(f"ws-{base_name}-", "")
    assert uuid.UUID(uuid_part)


def test_generate_workspace_identifiers_uniqueness():
    """Test that successive calls generate unique identifiers."""
    base_name = "test"

    result1 = generate_workspace_identifiers(base_name)
    result2 = generate_workspace_identifiers(base_name)

    # Same base name should produce different UUIDs
    assert result1["workspace_id"] != result2["workspace_id"]
    # workspace_name should be the same (just the base name)
    assert result1["workspace_name"] == result2["workspace_name"]
    assert result1["workspace_name"] == base_name
    # namespace_name should be different (contains different UUIDs)
    assert result1["namespace_name"] != result2["namespace_name"]


def test_get_namespace_from_workspace_id():
    """Test namespace generation from workspace ID."""
    workspace_id = "550e8400-e29b-41d4-a716-446655440000"

    namespace = get_namespace_from_workspace_id(workspace_id)

    assert namespace == f"ws-{workspace_id}"
    assert namespace == "ws-550e8400-e29b-41d4-a716-446655440000"


def test_get_namespace_from_workspace_id_with_string():
    """Test namespace generation with string workspace ID."""
    workspace_id = "test-workspace-123"

    namespace = get_namespace_from_workspace_id(workspace_id)

    assert namespace == f"ws-{workspace_id}"
    assert namespace == "ws-test-workspace-123"
