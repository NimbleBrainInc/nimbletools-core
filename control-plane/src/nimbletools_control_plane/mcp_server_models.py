"""
MCP Server Models

Pydantic models for MCP server definitions based on the NimbleBrain registry schema
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class Repository(BaseModel):
    """Repository metadata for the MCP server source code"""

    url: HttpUrl = Field(..., description="Repository URL for browsing source code")
    source: str = Field(..., description="Repository hosting service identifier (e.g., 'github')")
    id: str | None = Field(
        default=None, description="Repository identifier from the hosting service"
    )
    subfolder: str | None = Field(
        default=None, description="Optional relative path from repository root"
    )


class TransportProtocol(BaseModel):
    """Transport protocol configuration for MCP servers"""

    type: Literal["stdio", "streamable-http"] = Field(..., description="Transport protocol type")


class EnvironmentVariable(BaseModel):
    """Environment variable definition for MCP server packages"""

    name: str = Field(..., description="Environment variable name")
    value: str | None = Field(default=None, description="Optional default value")
    default: str | None = Field(
        default=None, description="Alias for 'value' (for third-party compatibility)"
    )
    isSecret: bool = Field(default=False, description="Whether this is a secret value")
    isRequired: bool = Field(default=False, description="Whether this variable is required")
    description: str | None = Field(
        default=None, description="Description of the environment variable"
    )
    example: str | None = Field(default=None, description="Example value for documentation")


class Package(BaseModel):
    """Package information for MCP server distribution"""

    registryType: str = Field(
        ..., description="Registry type (e.g., 'npm', 'pypi', 'oci', 'nuget', 'mcpb')"
    )
    identifier: str = Field(..., description="Package identifier in the registry")
    version: str = Field(..., description="Package version")
    transport: TransportProtocol = Field(..., description="Transport protocol configuration")
    registryBaseUrl: str | None = Field(
        default=None, description="Optional custom registry base URL"
    )
    runtimeHint: str | None = Field(
        default=None, description="Runtime command hint (e.g., 'npx', 'uvx', 'docker')"
    )
    runtimeArguments: list[dict[str, Any]] | None = Field(
        default=None, description="Arguments to pass to the runtime command"
    )
    environmentVariables: list[EnvironmentVariable] = Field(
        default_factory=list, description="Environment variables for this package"
    )


class HealthCheck(BaseModel):
    """Health check configuration for HTTP-based containers"""

    enabled: bool = Field(default=True, description="Whether health checks are enabled")
    path: str = Field(default="/health", pattern=r"^/.*", description="Health check endpoint path")
    port: int | None = Field(
        default=None,
        ge=1,
        le=65535,
        description="Health check port (if different from service port)",
    )
    interval: int = Field(default=30, ge=1, description="Health check interval in seconds")
    timeout: int = Field(default=5, ge=1, description="Health check timeout in seconds")
    retries: int = Field(default=3, ge=1, description="Number of retries before marking unhealthy")


class StartupProbe(BaseModel):
    """Startup probe for slow-starting containers"""

    initialDelaySeconds: int = Field(default=10, ge=0)
    periodSeconds: int = Field(default=10, ge=1)
    failureThreshold: int = Field(default=3, ge=1)


class ContainerConfig(BaseModel):
    """Container-specific configuration for OCI packages"""

    healthCheck: HealthCheck | None = Field(default=None)
    startupProbe: StartupProbe | None = Field(default=None)


class ResourceLimits(BaseModel):
    """Container resource limits"""

    memory: str = Field(
        default="256Mi", pattern=r"^[0-9]+(Mi|Gi)$", description="Memory limit (e.g., 256Mi, 1Gi)"
    )
    cpu: str = Field(
        default="100m", pattern=r"^[0-9]+(m)?$", description="CPU limit (e.g., 100m, 1)"
    )


class ResourceRequests(BaseModel):
    """Container resource requests"""

    memory: str = Field(default="128Mi", pattern=r"^[0-9]+(Mi|Gi)$", description="Memory request")
    cpu: str = Field(default="50m", pattern=r"^[0-9]+(m)?$", description="CPU request")


class Resources(BaseModel):
    """Container resource requirements"""

    limits: ResourceLimits = Field(default_factory=ResourceLimits)
    requests: ResourceRequests = Field(default_factory=ResourceRequests)


class Scaling(BaseModel):
    """Auto-scaling configuration"""

    enabled: bool = Field(default=False)
    minReplicas: int = Field(default=1, ge=0)
    maxReplicas: int = Field(default=3, ge=1)
    targetCPUUtilizationPercentage: int = Field(default=80, ge=10, le=100)


class Metrics(BaseModel):
    """Metrics configuration"""

    enabled: bool = Field(default=True)
    path: str = Field(default="/metrics", pattern=r"^/.*")
    port: int | None = Field(default=None, ge=1, le=65535)


class Tracing(BaseModel):
    """Tracing configuration"""

    enabled: bool = Field(default=False)
    endpoint: HttpUrl | None = Field(default=None, description="OpenTelemetry collector endpoint")


class Observability(BaseModel):
    """Monitoring and logging configuration"""

    metrics: Metrics = Field(default_factory=Metrics)
    tracing: Tracing = Field(default_factory=Tracing)


class Security(BaseModel):
    """Security configuration"""

    runAsNonRoot: bool = Field(default=True)
    runAsUser: int = Field(default=1000, ge=1)
    readOnlyRootFilesystem: bool = Field(default=False)
    allowPrivilegeEscalation: bool = Field(default=False)


class Ingress(BaseModel):
    """Ingress configuration"""

    enabled: bool = Field(default=False)
    hosts: list[str] = Field(default_factory=list)
    tls: bool = Field(default=True)
    annotations: dict[str, str] = Field(default_factory=dict)


class Service(BaseModel):
    """Service configuration"""

    type: Literal["ClusterIP", "NodePort", "LoadBalancer"] = Field(default="ClusterIP")
    annotations: dict[str, str] = Field(default_factory=dict)


class Networking(BaseModel):
    """Network configuration"""

    ingress: Ingress = Field(default_factory=Ingress)
    service: Service = Field(default_factory=Service)


class Deployment(BaseModel):
    """Deployment configuration"""

    protocol: Literal["http", "stdio"] = Field(default="http", description="Deployment protocol")
    port: int | None = Field(default=None, ge=1, le=65535, description="Service port")
    mcpPath: str = Field(default="/mcp", description="MCP endpoint path on the container")


class Branding(BaseModel):
    """Branding and visual assets"""

    logoUrl: HttpUrl | None = Field(default=None, description="URL to logo image")
    iconUrl: HttpUrl | None = Field(default=None, description="URL to square icon")
    primaryColor: str | None = Field(
        default=None, pattern=r"^#[0-9A-Fa-f]{6}$", description="Primary brand color in hex"
    )
    accentColor: str | None = Field(
        default=None, pattern=r"^#[0-9A-Fa-f]{6}$", description="Accent color in hex"
    )


class Documentation(BaseModel):
    """Documentation and content configuration"""

    readmeUrl: HttpUrl | None = Field(default=None, description="URL to README file")
    changelogUrl: HttpUrl | None = Field(default=None, description="URL to changelog file")
    licenseUrl: HttpUrl | None = Field(default=None, description="URL to license file")
    examplesUrl: HttpUrl | None = Field(default=None, description="URL to examples or tutorials")


class Screenshot(BaseModel):
    """Screenshot or demo image"""

    url: HttpUrl = Field(..., description="Screenshot URL")
    caption: str | None = Field(default=None, max_length=200)
    thumbnail: HttpUrl | None = Field(default=None, description="Optional thumbnail URL")


class Showcase(BaseModel):
    """Showcase and promotional content"""

    featured: bool = Field(default=False, description="Whether this server should be featured")
    screenshots: list[Screenshot] = Field(default_factory=list, max_length=5)
    videoUrl: HttpUrl | None = Field(default=None, description="Demo video URL")


class RegistryMetadata(BaseModel):
    """Registry-specific metadata and display configuration"""

    categories: list[str] = Field(
        default_factory=list, max_length=3, description="Primary categories for this server"
    )
    tags: list[str] = Field(
        default_factory=list, max_length=10, description="Free-form tags for searchability"
    )
    branding: Branding | None = Field(default=None)
    documentation: Documentation | None = Field(default=None)
    showcase: Showcase | None = Field(default=None)


class NimbleToolsRuntime(BaseModel):
    """NimbleTools-specific runtime configuration"""

    container: ContainerConfig | None = Field(default=None)
    resources: Resources = Field(default_factory=Resources)
    scaling: Scaling = Field(default_factory=Scaling)
    observability: Observability = Field(default_factory=Observability)
    security: Security = Field(default_factory=Security)
    networking: Networking = Field(default_factory=Networking)
    deployment: Deployment | None = Field(default=None)
    registry: RegistryMetadata | None = Field(default=None)


class ServerMetadata(BaseModel):
    """Extended metadata for NimbleBrain MCP servers"""

    class Config:
        extra = "allow"

    ai_nimbletools_mcp_v1: NimbleToolsRuntime | None = Field(
        default=None, alias="ai.nimbletools.mcp/v1"
    )


class MCPServer(BaseModel):
    """MCP Server definition based on NimbleBrain registry schema"""

    # Core MCP server fields
    name: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$",
        min_length=3,
        max_length=200,
        description="Server name in reverse-DNS format",
    )
    description: str = Field(
        ..., min_length=1, max_length=100, description="Clear human-readable explanation"
    )
    version: str = Field(..., max_length=255, description="Version string for this server")
    status: Literal["active", "deprecated", "deleted"] = Field(
        default="active", description="Server lifecycle status"
    )

    # Optional fields
    repository: Repository | None = Field(default=None, description="Repository metadata")
    websiteUrl: HttpUrl | None = Field(
        default=None, description="Server's homepage or documentation"
    )
    packages: list[Package] = Field(default_factory=list, description="Package information")

    # Extended metadata
    meta: ServerMetadata | None = Field(
        default=None, alias="_meta", description="Extended metadata"
    )

    # Runtime extracted fields for convenience
    @property
    def nimbletools_runtime(self) -> NimbleToolsRuntime | None:
        """Get NimbleTools runtime configuration if available"""
        if self.meta and self.meta.ai_nimbletools_mcp_v1:
            return self.meta.ai_nimbletools_mcp_v1
        return None


class MCPServerCreateRequest(BaseModel):
    """Request to create/deploy an MCP server in a workspace"""

    version: str = Field(default="v1", description="API version")
    server: MCPServer = Field(..., description="MCP server definition")
    workspace_id: str = Field(..., description="Target workspace ID")
    replicas: int = Field(default=1, ge=0, le=10, description="Number of replicas to deploy")
    environment: dict[str, str] = Field(
        default_factory=dict, description="Environment variables for the server"
    )


class MCPServerCreateResponse(BaseModel):
    """Response from creating/deploying an MCP server"""

    version: str = Field(default="v1", description="API version")
    server_id: str = Field(..., description="Deployed server ID")
    workspace_id: str = Field(..., description="Workspace ID where server was deployed")
    status: str = Field(..., description="Deployment status")
    created_at: datetime = Field(..., description="Creation timestamp")
    message: str | None = Field(default=None, description="Optional status message")


class MCPServerUpdateRequest(BaseModel):
    """Request to update an MCP server deployment"""

    version: str = Field(default="v1", description="API version")
    replicas: int | None = Field(default=None, ge=0, le=10, description="Update replica count")
    environment: dict[str, str] | None = Field(
        default=None, description="Update environment variables"
    )
    server: MCPServer | None = Field(default=None, description="Updated server definition")


class MCPServerUpdateResponse(BaseModel):
    """Response from updating an MCP server"""

    version: str = Field(default="v1", description="API version")
    server_id: str = Field(..., description="Server ID")
    workspace_id: str = Field(..., description="Workspace ID")
    status: str = Field(..., description="Update status")
    updated_at: datetime = Field(..., description="Update timestamp")
    message: str | None = Field(default=None, description="Optional status message")
