"""
Unit tests for schema validation functionality
"""

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from nimbletools_control_plane.schema_validator import (
    clear_schema_cache,
    get_mcpservice_schema,
    validate_mcpservice_spec,
    validate_registry_server_spec,
)


class TestRegistryServerSpecValidation:
    """Test validation of registry server specifications"""

    def test_valid_http_server_spec(self):
        """Test that a valid HTTP server spec passes validation"""
        server_spec = {
            "name": "test-server",
            "container": {
                "image": "test/server:latest",
                "port": 8000
            },
            "deployment": {
                "type": "http",
                "healthPath": "/health"
            },
            "credentials": [
                {
                    "name": "API_KEY",
                    "required": True,
                    "description": "API key for service"
                }
            ]
        }

        # Should not raise any exception
        validate_registry_server_spec(server_spec, "test-server")

    def test_valid_stdio_server_spec(self):
        """Test that a valid stdio server spec passes validation"""
        server_spec = {
            "name": "stdio-server",
            "container": {
                "image": "universal-adapter:latest",
                "port": 8000
            },
            "deployment": {
                "type": "stdio",
                "stdio": {
                    "executable": "npx",
                    "args": ["some-package"],
                    "workingDir": "/tmp"
                }
            },
            "credentials": []
        }

        # Should not raise any exception
        validate_registry_server_spec(server_spec, "stdio-server")

    def test_missing_container_image(self):
        """Test that missing container.image is rejected"""
        server_spec = {
            "container": {},  # Missing image
            "deployment": {"type": "http"}
        }

        with pytest.raises(HTTPException) as exc_info:
            validate_registry_server_spec(server_spec, "test-server")

        assert exc_info.value.status_code == 400
        assert "missing required 'container.image'" in exc_info.value.detail

    def test_missing_container_spec(self):
        """Test that missing container spec is rejected"""
        server_spec = {
            "deployment": {"type": "http"}
            # Missing container entirely
        }

        with pytest.raises(HTTPException) as exc_info:
            validate_registry_server_spec(server_spec, "test-server")

        assert exc_info.value.status_code == 400
        assert "missing required 'container.image'" in exc_info.value.detail

    def test_invalid_deployment_type(self):
        """Test that invalid deployment type is rejected"""
        server_spec = {
            "container": {"image": "test:latest"},
            "deployment": {"type": "invalid-type"}
        }

        with pytest.raises(HTTPException) as exc_info:
            validate_registry_server_spec(server_spec, "test-server")

        assert exc_info.value.status_code == 400
        assert "invalid deployment.type: invalid-type" in exc_info.value.detail
        assert "Must be 'http' or 'stdio'" in exc_info.value.detail

    def test_stdio_missing_executable(self):
        """Test that stdio deployment without executable is rejected"""
        server_spec = {
            "container": {"image": "test:latest"},
            "deployment": {
                "type": "stdio",
                "stdio": {}  # Missing executable
            }
        }

        with pytest.raises(HTTPException) as exc_info:
            validate_registry_server_spec(server_spec, "test-server")

        assert exc_info.value.status_code == 400
        assert "stdio deployment missing required 'executable'" in exc_info.value.detail

    def test_stdio_missing_stdio_config(self):
        """Test that stdio deployment without stdio config is rejected"""
        server_spec = {
            "container": {"image": "test:latest"},
            "deployment": {"type": "stdio"}  # Missing stdio config
        }

        with pytest.raises(HTTPException) as exc_info:
            validate_registry_server_spec(server_spec, "test-server")

        assert exc_info.value.status_code == 400
        assert "stdio deployment missing required 'executable'" in exc_info.value.detail

    def test_invalid_credential_structure(self):
        """Test that invalid credential structure is rejected"""
        server_spec = {
            "container": {"image": "test:latest"},
            "deployment": {"type": "http"},
            "credentials": [
                "invalid-credential"  # Should be object, not string
            ]
        }

        with pytest.raises(HTTPException) as exc_info:
            validate_registry_server_spec(server_spec, "test-server")

        assert exc_info.value.status_code == 400
        assert "credential 0 must be an object" in exc_info.value.detail

    def test_credential_missing_name(self):
        """Test that credential without name is rejected"""
        server_spec = {
            "container": {"image": "test:latest"},
            "deployment": {"type": "http"},
            "credentials": [
                {
                    "required": True,
                    "description": "Some credential"
                    # Missing name
                }
            ]
        }

        with pytest.raises(HTTPException) as exc_info:
            validate_registry_server_spec(server_spec, "test-server")

        assert exc_info.value.status_code == 400
        assert "credential 0 missing required 'name'" in exc_info.value.detail

    def test_credential_invalid_required_field(self):
        """Test that credential with non-boolean required field is rejected"""
        server_spec = {
            "container": {"image": "test:latest"},
            "deployment": {"type": "http"},
            "credentials": [
                {
                    "name": "API_KEY",
                    "required": "yes"  # Should be boolean, not string
                }
            ]
        }

        with pytest.raises(HTTPException) as exc_info:
            validate_registry_server_spec(server_spec, "test-server")

        assert exc_info.value.status_code == 400
        assert "credential 'API_KEY' 'required' field must be boolean" in exc_info.value.detail

    def test_empty_credentials_list(self):
        """Test that empty credentials list is valid"""
        server_spec = {
            "container": {"image": "test:latest"},
            "deployment": {"type": "http"},
            "credentials": []
        }

        # Should not raise any exception
        validate_registry_server_spec(server_spec, "test-server")

    def test_missing_credentials_field(self):
        """Test that missing credentials field is valid (defaults to empty)"""
        server_spec = {
            "container": {"image": "test:latest"},
            "deployment": {"type": "http"}
            # No credentials field
        }

        # Should not raise any exception
        validate_registry_server_spec(server_spec, "test-server")


class TestMCPServiceSchemaValidation:
    """Test validation against CRD schema"""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear schema cache before each test"""
        clear_schema_cache()

    def test_valid_mcpservice_spec(self):
        """Test that a valid MCPService passes schema validation"""
        # Mock the CRD schema
        mock_schema = {
            "type": "object",
            "properties": {
                "apiVersion": {"type": "string"},
                "kind": {"type": "string"},
                "metadata": {"type": "object"},
                "spec": {
                    "type": "object",
                    "required": ["container", "deployment"],
                    "properties": {
                        "container": {
                            "type": "object",
                            "required": ["image"],
                            "properties": {
                                "image": {"type": "string"},
                                "port": {"type": "integer", "minimum": 1, "maximum": 65535}
                            }
                        },
                        "deployment": {
                            "type": "object",
                            "required": ["type"],
                            "properties": {
                                "type": {"type": "string", "enum": ["http", "stdio"]}
                            }
                        },
                        "credentials": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["name", "required"],
                                "properties": {
                                    "name": {"type": "string"},
                                    "required": {"type": "boolean"},
                                    "description": {"type": "string"}
                                }
                            }
                        },
                        "replicas": {"type": "integer", "minimum": 0},
                        "environment": {"type": "object"},
                        "tools": {"type": "array"},
                        "resources": {"type": "array"},
                        "prompts": {"type": "array"}
                    }
                }
            },
            "required": ["apiVersion", "kind", "spec"]
        }

        mcpservice = {
            "apiVersion": "mcp.nimbletools.dev/v1",
            "kind": "MCPService",
            "metadata": {"name": "test-server"},
            "spec": {
                "container": {
                    "image": "test:latest",
                    "port": 8000
                },
                "deployment": {
                    "type": "http"
                },
                "credentials": [
                    {
                        "name": "API_KEY",
                        "required": True,
                        "description": "API key"
                    }
                ],
                "replicas": 1,
                "environment": {},
                "tools": [],
                "mcp_resources": [],
                "prompts": []
            }
        }

        with patch('nimbletools_control_plane.schema_validator.get_mcpservice_schema', return_value=mock_schema):
            # Should not raise any exception
            validate_mcpservice_spec(mcpservice, "test-server")

    def test_missing_required_fields(self):
        """Test that MCPService missing required fields is rejected"""
        mock_schema = {
            "type": "object",
            "properties": {
                "spec": {
                    "type": "object",
                    "required": ["container", "deployment"],
                    "properties": {
                        "container": {
                            "type": "object",
                            "required": ["image"],
                            "properties": {"image": {"type": "string"}}
                        },
                        "deployment": {"type": "object"}
                    }
                }
            },
            "required": ["spec"]
        }

        mcpservice = {
            "spec": {
                "container": {},  # Missing required 'image'
                "deployment": {"type": "http"}
            }
        }

        with patch('nimbletools_control_plane.schema_validator.get_mcpservice_schema', return_value=mock_schema):
            with pytest.raises(HTTPException) as exc_info:
                validate_mcpservice_spec(mcpservice, "test-server")

            assert exc_info.value.status_code == 400
            assert "Schema validation failed" in exc_info.value.detail
            assert "test-server" in exc_info.value.detail

    def test_invalid_field_type(self):
        """Test that MCPService with wrong field types is rejected"""
        mock_schema = {
            "type": "object",
            "properties": {
                "spec": {
                    "type": "object",
                    "properties": {
                        "replicas": {"type": "integer", "minimum": 0}
                    }
                }
            }
        }

        mcpservice = {
            "spec": {
                "replicas": "not-a-number"  # Should be integer
            }
        }

        with patch('nimbletools_control_plane.schema_validator.get_mcpservice_schema', return_value=mock_schema):
            with pytest.raises(HTTPException) as exc_info:
                validate_mcpservice_spec(mcpservice, "test-server")

            assert exc_info.value.status_code == 400
            assert "Schema validation failed" in exc_info.value.detail

    def test_schema_loading_error(self):
        """Test that schema loading errors are handled properly"""
        with patch('nimbletools_control_plane.schema_validator.client.ApiextensionsV1Api') as mock_api:
            mock_api.return_value.read_custom_resource_definition.side_effect = Exception("API error")

            with pytest.raises(HTTPException) as exc_info:
                get_mcpservice_schema()

            assert exc_info.value.status_code == 500
            assert "Failed to load MCPService schema" in exc_info.value.detail


class TestSchemaCache:
    """Test schema caching functionality"""

    def test_schema_caching(self):
        """Test that schema is cached after first load"""
        mock_schema = {"type": "object"}

        with patch('nimbletools_control_plane.schema_validator.client.ApiextensionsV1Api') as mock_api:
            # Mock successful CRD response
            mock_crd = Mock()
            mock_version = Mock()
            mock_version.name = "v1"
            mock_version.served = True
            mock_version.schema.open_api_v3_schema.to_dict.return_value = mock_schema
            mock_crd.spec.versions = [mock_version]

            mock_api.return_value.read_custom_resource_definition.return_value = mock_crd

            # First call should fetch from API
            schema1 = get_mcpservice_schema()
            assert schema1 == mock_schema
            assert mock_api.return_value.read_custom_resource_definition.call_count == 1

            # Second call should use cache
            schema2 = get_mcpservice_schema()
            assert schema2 == mock_schema
            assert mock_api.return_value.read_custom_resource_definition.call_count == 1  # Not called again

    def test_clear_cache(self):
        """Test that cache can be cleared"""
        clear_schema_cache()

        with patch('nimbletools_control_plane.schema_validator.client.ApiextensionsV1Api') as mock_api:
            mock_crd = Mock()
            mock_version = Mock()
            mock_version.name = "v1"
            mock_version.served = True
            mock_version.schema.open_api_v3_schema.to_dict.return_value = {"type": "object"}
            mock_crd.spec.versions = [mock_version]
            mock_api.return_value.read_custom_resource_definition.return_value = mock_crd

            # Load schema
            get_mcpservice_schema()
            assert mock_api.return_value.read_custom_resource_definition.call_count == 1

            # Clear cache and load again
            clear_schema_cache()
            get_mcpservice_schema()
            assert mock_api.return_value.read_custom_resource_definition.call_count == 2
