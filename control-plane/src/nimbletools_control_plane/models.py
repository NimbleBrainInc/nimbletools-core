"""
Data models for NimbleTools Control Plane
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WorkspaceTier(str, Enum):
    """Workspace tier options"""

    COMMUNITY = "community"
    ENTERPRISE = "enterprise"


class DeploymentType(str, Enum):
    """MCP service deployment types"""

    HTTP = "http"
    STDIO = "stdio"


class MCPTool(BaseModel):
    """MCP tool definition"""

    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")


class ContainerEnv(BaseModel):
    """Container environment variable"""

    name: str = Field(..., description="Environment variable name")
    value: str = Field(..., description="Environment variable value")


class ContainerSpec(BaseModel):
    """Container specification"""

    image: str = Field(..., description="Container image")
    port: int = Field(..., description="Container port", ge=1, le=65535)
    env: list[ContainerEnv] | None = Field(
        default=None, description="Environment variables"
    )


class DeploymentSpec(BaseModel):
    """Deployment specification"""

    type: DeploymentType = Field(..., description="Deployment type")
    executable: str | None = Field(
        default=None, description="Executable path for stdio deployment"
    )
    args: list[str] | None = Field(
        default=None, description="Arguments for stdio executable"
    )
    workingDir: str | None = Field(
        default=None, description="Working directory for stdio executable"
    )


class MCPServiceSpec(BaseModel):
    """MCPService specification"""

    description: str = Field(..., description="Service description")
    container: ContainerSpec = Field(..., description="Container configuration")
    deployment: DeploymentSpec = Field(..., description="Deployment configuration")
    tools: list[MCPTool] = Field(..., description="Available MCP tools")
    replicas: int = Field(default=1, description="Number of replicas", ge=0, le=10)


class ServicePhase(str, Enum):
    """Service lifecycle phases"""

    PENDING = "Pending"
    RUNNING = "Running"
    FAILED = "Failed"
    SCALING = "Scaling"


class ServiceCondition(BaseModel):
    """Service condition"""

    type: str = Field(..., description="Condition type")
    status: str = Field(..., description="Condition status")
    lastTransitionTime: datetime = Field(..., description="Last transition time")
    reason: str | None = Field(default=None, description="Reason")
    message: str | None = Field(default=None, description="Message")


class MCPServiceStatus(BaseModel):
    """MCPService status"""

    phase: ServicePhase = Field(..., description="Current phase")
    replicas: int = Field(default=0, description="Current replica count")
    readyReplicas: int = Field(default=0, description="Ready replica count")
    conditions: list[ServiceCondition] | None = Field(
        default=None, description="Service conditions"
    )
    lastUpdated: datetime | None = Field(
        default=None, description="Last updated timestamp"
    )


class MCPService(BaseModel):
    """Complete MCPService resource"""

    apiVersion: str = Field(default="mcp.nimbletools.dev/v1", description="API version")
    kind: str = Field(default="MCPService", description="Resource kind")
    metadata: dict[str, Any] = Field(..., description="Kubernetes metadata")
    spec: MCPServiceSpec = Field(..., description="Service specification")
    status: MCPServiceStatus | None = Field(default=None, description="Service status")


class WorkspaceCreateRequest(BaseModel):
    """Workspace creation request"""

    name: str = Field(..., description="Workspace name", pattern=r"^[a-z0-9-_]+$")
    tier: WorkspaceTier = Field(
        default=WorkspaceTier.COMMUNITY, description="Workspace tier"
    )
    description: str | None = Field(default=None, description="Workspace description")


class WorkspaceCreateResponse(BaseModel):
    """Workspace creation response"""

    workspace_name: str = Field(..., description="Base workspace name")
    workspace_id: str = Field(..., description="Unique workspace ID")
    namespace: str = Field(..., description="Kubernetes namespace")
    tier: str = Field(..., description="Workspace tier")
    created: str = Field(..., description="Creation timestamp")
    status: str = Field(..., description="Workspace status")
    message: str = Field(..., description="Success message")


class WorkspaceSummary(BaseModel):
    """Workspace summary for list responses"""

    workspace_id: str | None = Field(..., description="Unique workspace ID")
    workspace_name: str = Field(..., description="Workspace name")
    namespace: str = Field(..., description="Kubernetes namespace")
    tier: str = Field(..., description="Workspace tier")
    created: str | None = Field(..., description="Creation timestamp")
    owner: str | None = Field(..., description="Workspace owner")
    status: str = Field(..., description="Workspace status")


class WorkspaceListResponse(BaseModel):
    """Workspace list response"""

    workspaces: list[WorkspaceSummary] = Field(..., description="List of workspaces")
    total: int = Field(..., description="Total number of workspaces")
    user_id: str = Field(..., description="User ID")


class WorkspaceDetailsResponse(BaseModel):
    """Workspace details response"""

    workspace_id: str = Field(..., description="Unique workspace ID")
    workspace_name: str | None = Field(default=None, description="Workspace name")
    namespace: str = Field(..., description="Kubernetes namespace")
    tier: str = Field(..., description="Workspace tier")
    created: str | None = Field(default=None, description="Creation timestamp")
    owner: str | None = Field(default=None, description="Workspace owner")
    status: str = Field(..., description="Workspace status")


class WorkspaceDeleteResponse(BaseModel):
    """Workspace delete response"""

    workspace_id: str = Field(..., description="Deleted workspace ID")
    namespace: str = Field(..., description="Deleted namespace")
    message: str = Field(..., description="Success message")


class WorkspaceTokenResponse(BaseModel):
    """Workspace token response"""

    access_token: str = Field(..., description="Access token")
    token_type: str = Field(..., description="Token type")
    scope: list[str] = Field(..., description="Token scope")
    workspace_id: str = Field(..., description="Workspace ID")
    expires_in: int = Field(..., description="Token expiration in seconds")
    message: str = Field(..., description="Additional message")


class WorkspaceSecretsResponse(BaseModel):
    """Workspace secrets list response"""

    workspace_id: str = Field(..., description="Workspace ID")
    secrets: list[str] = Field(..., description="List of secret keys")
    count: int = Field(..., description="Number of secrets")
    message: str = Field(..., description="Additional message")


class WorkspaceSecretSetRequest(BaseModel):
    """Workspace secret set request"""
    secret_value: str = Field(..., description="Secret value to store")


class WorkspaceSecretResponse(BaseModel):
    """Workspace secret operation response"""

    workspace_id: str = Field(..., description="Workspace ID")
    secret_key: str = Field(..., description="Secret key")
    status: str = Field(..., description="Operation status")
    message: str = Field(..., description="Operation message")


class Workspace(BaseModel):
    """Workspace resource"""

    workspace_id: str = Field(..., description="Unique workspace ID")
    name: str = Field(..., description="Workspace name")
    namespace: str = Field(..., description="Kubernetes namespace")
    owner: str = Field(..., description="Workspace owner")
    status: str = Field(..., description="Workspace status")
    created_at: datetime = Field(..., description="Creation timestamp")


class ServerDeployRequest(BaseModel):
    """Server deployment request"""

    server_id: str = Field(..., description="Server ID to deploy")
    replicas: int = Field(default=1, description="Number of replicas", ge=1, le=4)
    environment: dict[str, str] = Field(
        default_factory=dict, description="Environment variables"
    )
    timeout: int = Field(default=300, description="Request timeout in seconds", ge=1, le=3600)
    scaling: dict[str, Any] = Field(default_factory=dict, description="Auto-scaling configuration")
    routing: dict[str, Any] = Field(default_factory=dict, description="Routing configuration")


class ServerScaleRequest(BaseModel):
    """Server scaling request"""

    replicas: int = Field(..., description="Number of replicas", ge=1, le=4)


class ServerSummary(BaseModel):
    """Server summary for list responses"""

    id: str = Field(..., description="Server ID")
    name: str = Field(..., description="Server name")
    workspace_id: str = Field(..., description="Workspace ID")
    namespace: str = Field(..., description="Kubernetes namespace")
    image: str = Field(..., description="Container image")
    status: str = Field(..., description="Server status")
    replicas: int = Field(..., description="Number of replicas")
    created: str | None = Field(default=None, description="Creation timestamp")


class ServerListResponse(BaseModel):
    """Server list response"""

    servers: list[ServerSummary] = Field(..., description="List of servers")
    workspace_id: str = Field(..., description="Workspace ID")
    namespace: str = Field(..., description="Kubernetes namespace")
    total: int = Field(..., description="Total number of servers")


class ServerDeployResponse(BaseModel):
    """Server deployment response"""

    server_id: str = Field(..., description="Deployed server ID")
    workspace_id: str = Field(..., description="Workspace ID")
    namespace: str = Field(..., description="Kubernetes namespace")
    status: str = Field(..., description="Deployment status")
    message: str = Field(..., description="Deployment message")
    service_endpoint: str = Field(..., description="MCP service endpoint URL")


class ServerDetailsResponse(BaseModel):
    """Server details response"""

    id: str = Field(..., description="Server ID")
    name: str = Field(..., description="Server name")
    workspace_id: str = Field(..., description="Workspace ID")
    namespace: str = Field(..., description="Kubernetes namespace")
    image: str = Field(..., description="Container image")
    spec: dict[str, Any] = Field(..., description="Server specification")
    status: dict[str, Any] = Field(..., description="Server status details")
    created: str | None = Field(default=None, description="Creation timestamp")


class ServerScaleResponse(BaseModel):
    """Server scaling response"""

    server_id: str = Field(..., description="Scaled server ID")
    workspace_id: str = Field(..., description="Workspace ID")
    replicas: int = Field(..., description="New replica count")
    status: str = Field(..., description="Scaling status")
    message: str = Field(..., description="Scaling message")


class ServerDeleteResponse(BaseModel):
    """Server deletion response"""

    server_id: str = Field(..., description="Deleted server ID")
    workspace_id: str = Field(..., description="Workspace ID")
    namespace: str = Field(..., description="Kubernetes namespace")
    status: str = Field(..., description="Deletion status")
    message: str = Field(..., description="Deletion message")


class HealthCheck(BaseModel):
    """Health check response"""

    status: str = Field(..., description="Health status")
    version: str = Field(..., description="API version")
    service: str = Field(..., description="API service")
    timestamp: datetime = Field(..., description="Check timestamp")


class ErrorResponse(BaseModel):
    """Error response model"""

    detail: str = Field(..., description="Error message")
    error_code: str | None = Field(default=None, description="Error code")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Error timestamp"
    )


class User(BaseModel):
    """User model for authentication"""

    user_id: str = Field(..., description="User ID")
    role: str = Field(..., description="User role")
    permissions: list[str] = Field(default=[], description="User permissions")


class AuthContext(BaseModel):
    """Authentication context"""

    user: User | None = Field(default=None, description="Authenticated user")
    authenticated: bool = Field(..., description="Authentication status")
    provider: str = Field(..., description="Authentication provider")


# Request/Response models for specific endpoints
class ServiceLogsResponse(BaseModel):
    """Service logs response"""

    logs: str = Field(..., description="Service logs")
    lines: int = Field(..., description="Number of log lines")
    timestamp: datetime = Field(..., description="Log retrieval timestamp")


# Registry models
class RegistryEnableRequest(BaseModel):
    """Registry enable request"""

    registry_url: str = Field(..., description="URL to registry.yaml file")
    namespace_override: str | None = Field(
        default=None, description="Override namespace name"
    )


class RegistryEnableResponse(BaseModel):
    """Registry enable response"""

    registry_name: str = Field(..., description="Registry name")
    registry_version: str = Field(..., description="Registry version")
    namespace: str = Field(..., description="Created namespace")
    services_created: int = Field(..., description="Number of services created")
    services: list[str] = Field(..., description="List of created service names")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Enable timestamp"
    )


class RegistryInfo(BaseModel):
    """Registry information"""

    name: str = Field(..., description="Registry name")
    version: str = Field(..., description="Registry version")
    url: str = Field(..., description="Registry URL")
    last_updated: str | None = Field(default=None, description="Last updated date")
    total_servers: int = Field(..., description="Total servers in registry")
    active_servers: int = Field(..., description="Active servers in registry")


class Registry(BaseModel):
    """Registry resource"""

    name: str = Field(..., description="Registry name")
    namespace: str = Field(..., description="Kubernetes namespace")
    url: str | None = Field(default=None, description="Registry URL")
    server_count: int = Field(..., description="Number of servers in this registry")
    created_at: datetime = Field(..., description="Creation timestamp")
    owner: str = Field(..., description="Registry owner")


class RegistryServerSummary(BaseModel):
    """Registry server summary for list responses"""

    id: str = Field(..., description="Server ID")
    name: str = Field(..., description="Server name")
    description: str = Field(..., description="Server description")
    image: str = Field(..., description="Container image")
    version: str = Field(..., description="Server version")
    status: str = Field(..., description="Server status")
    registry: str = Field(..., description="Registry name")
    namespace: str = Field(..., description="Namespace")
    deployment: dict[str, Any] = Field(..., description="Deployment config")
    tools: list[str] = Field(default_factory=list, description="Available tools")
    replicas: dict[str, int] = Field(..., description="Replica information")
    category: str | None = Field(default=None, description="Server category")
    tags: list[str] = Field(default_factory=list, description="Server tags")


class RegistryServersResponse(BaseModel):
    """Registry servers list response"""

    servers: list[RegistryServerSummary] = Field(..., description="List of servers")
    total: int = Field(..., description="Total number of servers")
    registries: list[dict[str, Any]] = Field(..., description="Registry information")
    owner: str = Field(..., description="Owner")


class RegistryListResponse(BaseModel):
    """Registry list response"""

    registries: list[Registry] = Field(..., description="List of registries")
    total: int = Field(..., description="Total number of registries")
    total_servers: int = Field(..., description="Total servers across all registries")
    owner: str = Field(..., description="Owner of the registries")
