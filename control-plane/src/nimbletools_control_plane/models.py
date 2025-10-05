"""
Data models for NimbleTools Control Plane
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


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
    env: list[ContainerEnv] | None = Field(default=None, description="Environment variables")


class DeploymentSpec(BaseModel):
    """Deployment specification"""

    type: DeploymentType = Field(..., description="Deployment type")
    executable: str | None = Field(default=None, description="Executable path for stdio deployment")
    args: list[str] | None = Field(default=None, description="Arguments for stdio executable")
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
    lastUpdated: datetime | None = Field(default=None, description="Last updated timestamp")


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
    description: str | None = Field(default=None, description="Workspace description")


class WorkspaceCreateResponse(BaseModel):
    """Workspace creation response"""

    workspace_name: str = Field(..., description="Base workspace name")
    workspace_id: UUID = Field(..., description="Unique workspace ID")
    namespace: str = Field(..., description="Kubernetes namespace")
    user_id: UUID = Field(..., description="User ID who created the workspace")
    organization_id: UUID = Field(..., description="Organization ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    status: str = Field(..., description="Workspace status")
    message: str = Field(..., description="Success message")


class WorkspaceSummary(BaseModel):
    """Workspace summary for list responses"""

    workspace_id: UUID = Field(..., description="Unique workspace ID")
    workspace_name: str = Field(..., description="Workspace name")
    namespace: str = Field(..., description="Kubernetes namespace")
    user_id: UUID | None = Field(default=None, description="User ID who owns the workspace")
    organization_id: UUID | None = Field(default=None, description="Organization ID")
    created_at: datetime | None = Field(default=None, description="Creation timestamp")
    status: str = Field(..., description="Workspace status")


class WorkspaceListResponse(BaseModel):
    """Workspace list response"""

    workspaces: list[WorkspaceSummary] = Field(..., description="List of workspaces")
    total: int = Field(..., description="Total number of workspaces")
    user_id: UUID = Field(..., description="User ID requesting the list")


class WorkspaceDetailsResponse(BaseModel):
    """Workspace details response"""

    workspace_id: UUID = Field(..., description="Unique workspace ID")
    workspace_name: str | None = Field(default=None, description="Workspace name")
    namespace: str = Field(..., description="Kubernetes namespace")
    user_id: UUID | None = Field(default=None, description="User ID who owns the workspace")
    organization_id: UUID | None = Field(default=None, description="Organization ID")
    created_at: datetime | None = Field(default=None, description="Creation timestamp")
    status: str = Field(..., description="Workspace status")


class WorkspaceDeleteResponse(BaseModel):
    """Workspace delete response"""

    workspace_id: UUID = Field(..., description="Deleted workspace ID")
    namespace: str = Field(..., description="Deleted namespace")
    message: str = Field(..., description="Success message")


class WorkspaceTokenResponse(BaseModel):
    """Workspace token response"""

    access_token: str = Field(..., description="Access token")
    token_type: str = Field(..., description="Token type")
    scope: list[str] = Field(..., description="Token scope")
    workspace_id: UUID = Field(..., description="Workspace ID")
    expires_in: int = Field(..., description="Token expiration in seconds")
    message: str = Field(..., description="Additional message")


class WorkspaceTokenCreateRequest(BaseModel):
    """Request to create a new workspace token"""

    version: str = Field(default="v1", description="API version")
    expires_in: int | None = Field(
        default=None,
        description="Token expiration in seconds (max 31536000 = 1 year)",
        ge=1,
        le=31536000,
    )
    expires_at: int | None = Field(
        default=None,
        description="Token expiration timestamp (alternative to expires_in)",
    )
    scope: list[str] = Field(
        default=["workspace:read", "servers:read"],
        description="Token permissions scope",
    )


class WorkspaceTokenCreateResponse(BaseModel):
    """Response from creating a workspace token"""

    version: str = Field(default="v1", description="API version")
    access_token: str = Field(..., description="The generated access token")
    token_type: str = Field(default="Bearer", description="Token type")
    scope: list[str] = Field(..., description="Granted permissions scope")
    workspace_id: UUID = Field(..., description="Associated workspace ID")
    expires_in: int = Field(..., description="Token expiration in seconds")


class WorkspaceTokenInfo(BaseModel):
    """Information about a workspace token"""

    jti: str = Field(..., description="JWT ID (unique token identifier)")
    user_id: str = Field(..., description="User who created the token")
    created_at: str = Field(..., description="Token creation timestamp")
    expires_at: str = Field(..., description="Token expiration timestamp")
    scope: list[str] = Field(..., description="Token permissions scope")
    status: str = Field(..., description="Token status (active/revoked)")


class WorkspaceTokenListResponse(BaseModel):
    """Response listing workspace tokens"""

    version: str = Field(default="v1", description="API version")
    workspace_id: UUID = Field(..., description="Workspace ID")
    tokens: list[WorkspaceTokenInfo] = Field(..., description="List of token information")
    count: int = Field(..., description="Total number of tokens")


class WorkspaceTokenRevokeResponse(BaseModel):
    """Response from revoking a workspace token"""

    version: str = Field(default="v1", description="API version")
    workspace_id: UUID = Field(..., description="Workspace ID")
    token_jti: str = Field(..., description="JWT ID of revoked token")
    status: str = Field(default="revoked", description="Token status")
    revoked_at: str = Field(..., description="Revocation timestamp")


class WorkspaceSecretsResponse(BaseModel):
    """Workspace secrets list response"""

    workspace_id: UUID = Field(..., description="Workspace ID")
    secrets: list[str] = Field(..., description="List of secret keys")
    count: int = Field(..., description="Number of secrets")
    message: str = Field(..., description="Additional message")


class WorkspaceSecretSetRequest(BaseModel):
    """Workspace secret set request"""

    secret_value: str = Field(..., description="Secret value to store")


class WorkspaceSecretResponse(BaseModel):
    """Workspace secret operation response"""

    workspace_id: UUID = Field(..., description="Workspace ID")
    secret_key: str = Field(..., description="Secret key")
    status: str = Field(..., description="Operation status")
    message: str = Field(..., description="Operation message")


class Workspace(BaseModel):
    """Workspace resource"""

    workspace_id: UUID = Field(..., description="Unique workspace ID")
    name: str = Field(..., description="Workspace name")
    namespace: str = Field(..., description="Kubernetes namespace")
    owner: str = Field(..., description="Workspace owner")
    status: str = Field(..., description="Workspace status")
    created_at: datetime = Field(..., description="Creation timestamp")


class ServerDeployRequest(BaseModel):
    """Server deployment request"""

    server_id: str = Field(..., description="Server ID to deploy")
    replicas: int = Field(default=1, description="Number of replicas", ge=1, le=4)
    environment: dict[str, str] = Field(default_factory=dict, description="Environment variables")
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
    workspace_id: UUID = Field(..., description="Workspace ID")
    namespace: str = Field(..., description="Kubernetes namespace")
    image: str = Field(..., description="Container image")
    status: str = Field(..., description="Server status")
    replicas: int = Field(..., description="Number of replicas")
    created: str | None = Field(default=None, description="Creation timestamp")


class ServerListResponse(BaseModel):
    """Server list response"""

    servers: list[ServerSummary] = Field(..., description="List of servers")
    workspace_id: UUID = Field(..., description="Workspace ID")
    namespace: str = Field(..., description="Kubernetes namespace")
    total: int = Field(..., description="Total number of servers")


class ServerDeployResponse(BaseModel):
    """Server deployment response"""

    server_id: str = Field(..., description="Deployed server ID")
    workspace_id: UUID = Field(..., description="Workspace ID")
    namespace: str = Field(..., description="Kubernetes namespace")
    status: str = Field(..., description="Deployment status")
    message: str = Field(..., description="Deployment message")
    service_endpoint: str = Field(..., description="MCP service endpoint URL")


class ServerDetailsResponse(BaseModel):
    """Server details response"""

    id: str = Field(..., description="Server ID")
    name: str = Field(..., description="Server name")
    workspace_id: UUID = Field(..., description="Workspace ID")
    namespace: str = Field(..., description="Kubernetes namespace")
    image: str = Field(..., description="Container image")
    spec: dict[str, Any] = Field(..., description="Server specification")
    status: dict[str, Any] = Field(..., description="Server status details")
    created: str | None = Field(default=None, description="Creation timestamp")


class ServerScaleResponse(BaseModel):
    """Server scaling response"""

    server_id: str = Field(..., description="Scaled server ID")
    workspace_id: UUID = Field(..., description="Workspace ID")
    replicas: int = Field(..., description="New replica count")
    status: str = Field(..., description="Scaling status")
    message: str = Field(..., description="Scaling message")


class ServerDeleteResponse(BaseModel):
    """Server deletion response"""

    server_id: str = Field(..., description="Deleted server ID")
    workspace_id: UUID = Field(..., description="Workspace ID")
    namespace: str = Field(..., description="Kubernetes namespace")
    status: str = Field(..., description="Deletion status")
    message: str = Field(..., description="Deletion message")


class ServerRestartRequest(BaseModel):
    """Server restart request"""

    version: str = Field(default="v1", description="API version")
    force: bool = Field(default=False, description="Force restart even if server is running")


class ServerRestartResponse(BaseModel):
    """Server restart response"""

    version: str = Field(default="v1", description="API version")
    server_id: str = Field(..., description="Restarted server ID")
    workspace_id: UUID = Field(..., description="Workspace ID")
    status: str = Field(..., description="Restart status")
    message: str = Field(..., description="Restart message")
    timestamp: datetime = Field(..., description="Restart timestamp")


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
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


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


class LogLevel(str, Enum):
    """Log level enumeration"""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ServerLogEntry(BaseModel):
    """Individual server log entry"""

    timestamp: datetime = Field(..., description="Log timestamp")
    level: LogLevel = Field(..., description="Log level")
    message: str = Field(..., description="Log message")
    pod_name: str | None = Field(default=None, description="Pod name that generated the log")
    container_name: str | None = Field(default=None, description="Container name")


class ServerLogsRequest(BaseModel):
    """Server logs request"""

    version: str = Field(default="v1", description="API version")
    limit: int = Field(
        default=10, description="Maximum number of log entries to return", ge=1, le=1000
    )
    since: datetime | None = Field(default=None, description="Start timestamp for log retrieval")
    until: datetime | None = Field(default=None, description="End timestamp for log retrieval")
    level: LogLevel | None = Field(default=None, description="Filter by log level")
    pod_name: str | None = Field(default=None, description="Filter by specific pod")


class ServerLogsResponse(BaseModel):
    """Server logs response"""

    version: str = Field(default="v1", description="API version")
    server_id: str = Field(..., description="Server ID")
    workspace_id: UUID = Field(..., description="Workspace ID")
    logs: list[ServerLogEntry] = Field(..., description="Log entries")
    count: int = Field(..., description="Number of log entries returned")
    has_more: bool = Field(..., description="Whether more logs are available")
    query_timestamp: datetime = Field(..., description="Timestamp when logs were queried")


class ServiceLogsResponse(BaseModel):
    """Service logs response"""

    logs: str = Field(..., description="Service logs")
    lines: int = Field(..., description="Number of log lines")
    timestamp: datetime = Field(..., description="Log retrieval timestamp")
