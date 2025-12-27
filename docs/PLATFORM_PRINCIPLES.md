# Platform Design Principles

## Core Principle: No Server-Specific Logic

All platform components (operator, control-plane) must remain completely generic and server-agnostic. They process server definitions from the registry but never contain server-specific logic.

## Configuration Over Code

The platform is driven by **declarative server definitions** from the registry. Server-specific behavior is configured through schemas, not hardcoded in platform components.

### What This Means

- **No hardcoded server behavior**: Platform components never contain logic specific to individual MCP servers (e.g., postgres-mcp, tavily-mcp, finnhub, etc.)
- **Configuration via server definitions**: All server-specific behavior (startup commands, arguments, ports, environment variables, resource limits) comes from the server definition in the registry
- **Extensibility through schemas**: New server types and behaviors are supported by extending the server definition schema, not by modifying platform code
- **Registry-driven deployment**: Platform components are pure interpreters of server definitions
- **Third-party compatibility**: External developers can add servers to the registry without any platform code changes

## Component Responsibilities

**Operator**: Deploys and manages MCP servers
- Reads server definitions and creates Kubernetes resources generically
- Never contains server-specific deployment logic

**Control Plane**: API for workspace and server management
- Routes requests and validates schemas generically
- Never contains server-specific API logic or special cases

**MCPB Base Images**: Runtime containers for MCPB bundles
- Execute bundles based on manifest configuration
- Never contain server-specific wrapper logic
- Supergateway images handle stdio-to-HTTP wrapping generically

## Correct Approach

When a server needs special startup arguments or configuration, add to server definition in registry:

```json
{
  "name": "ai.nimbletools/postgres-mcp",
  "packages": [{
    "registryType": "oci",
    "identifier": "crystaldba/postgres-mcp",
    "transport": {"type": "streamable-http"},
    "runtimeArguments": [
      {"type": "named", "name": "--transport", "value": "sse"},
      {"type": "named", "name": "--sse-host", "value": "0.0.0.0"},
      {"type": "named", "name": "--sse-port", "value": "8000"}
    ],
    "environmentVariables": [
      {"name": "DATABASE_URI", "isSecret": true, "isRequired": true}
    ]
  }],
  "_meta": {
    "ai.nimbletools.mcp/v1": {
      "resources": {
        "limits": {"memory": "512Mi", "cpu": "200m"}
      }
    }
  }
}
```

Platform reads and applies generically:

```python
# Operator - works for ANY server
args = self._extract_runtime_args(spec.get("packages", []))
env_vars = self._create_env_vars_from_packages(spec.get("packages", []))
resources = self._build_resources_config(runtime)

# Control plane - works for ANY server
mcp_server = MCPServer(**server_definition)
mcpservice_spec = _create_mcpservice_spec_from_mcp_server(mcp_server, ...)
```

## Incorrect Approach

Never hardcode server-specific logic:

```python
# WRONG - Don't do this in operator, control-plane, or any platform component!
if server_name == "postgres-mcp":
    args = ["--transport", "sse"]
    resources = {"memory": "512Mi"}
elif server_name == "tavily-mcp":
    args = ["--some-other-flag"]
```

Never add server-specific configuration to platform code:

```python
# WRONG - Don't do this!
SERVER_CONFIGS = {
    "postgres-mcp": {"transport": "sse", "port": 8000},
    "tavily-mcp": {"transport": "stdio"},
}
```

Never create server-specific API endpoints:

```python
# WRONG - Don't do this!
@router.post("/servers/postgres-mcp/special-action")
async def postgres_special_action():
    pass
```

## Why This Matters

1. **Scalability**: Platform supports unlimited server types without code changes
2. **Maintainability**: Server-specific logic stays with server definitions
3. **Separation of concerns**: Registry teams manage definitions, platform team manages orchestration
4. **Third-party ecosystem**: External developers contribute to registry, not platform code
5. **Testing**: Generic code paths mean fewer edge cases
6. **Velocity**: Adding a new server requires no platform deployment

## Adding New Features Checklist

When adding platform features, ask:

1. "Can this be configured via the server definition schema?" - If yes, extend the schema
2. "Will this work for all servers?" - If no, it doesn't belong in the platform
3. "Am I reading configuration from the definition, or hardcoding it?"
4. "Does this require platform code changes for each new server?" - If yes, redesign
5. "Would a third-party developer need to modify platform code?" - If yes, the design is wrong

## Red Flags

If you find yourself:
- Writing `if server_name == "..."` - STOP, use server definition schema
- Creating server-specific config objects - STOP, extend the schema
- Adding special cases for certain servers - STOP, make it generic
- Implementing server-specific endpoints - STOP, use generic patterns

**The platform is a generic MCP server orchestrator, not a collection of server-specific handlers.**
