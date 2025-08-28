# Universal MCP Adapter

The Universal MCP Adapter is a core component of NimbleTools Core that provides HTTP/JSON-RPC interface for any MCP server. It bridges the gap between stdio-based MCP servers and HTTP-based communication.

## Features

- **Dynamic Package Management**: Automatically installs npm packages and clones GitHub repositories as needed
- **Memory Optimized**: Efficient cleanup and caching strategies
- **Multi-Protocol Support**: Works with HTTP and stdio MCP servers
- **Environment-Based Configuration**: Configured via environment variables set by the operator
- **Capability-Aware**: Dynamically handles tools, resources, and prompts based on server capabilities

## How It Works

The Universal Adapter acts as a bridge:

1. **HTTP Client** ← JSON-RPC → **Universal Adapter** ← stdio/JSON-RPC → **MCP Server**

The adapter:
- Receives HTTP requests with JSON-RPC payloads
- Forwards appropriate requests to the underlying MCP server via stdio
- Handles initialization and capability negotiation
- Provides health checks and monitoring endpoints

## Environment Variables

The adapter is configured entirely through environment variables set by the MCP Operator:

### Required Variables

- `MCP_EXECUTABLE`: The executable command to run (e.g., `npx`, `node`, `python`)
- `MCP_SERVER_NAME`: Name of the MCP server

### Optional Variables

- `MCP_ARGS`: Arguments for the executable (JSON array or comma-separated)
- `MCP_WORKING_DIR`: Working directory for the process (default: `/tmp`)
- `MCP_TOOLS`: JSON array of available tools
- `MCP_RESOURCES`: JSON array of available resources  
- `MCP_PROMPTS`: JSON array of available prompts
- `PORT`: HTTP port to listen on (default: `8000`)

### Environment Variable Forwarding

The adapter forwards environment variables to the MCP server:

- Standard API keys: `API_KEY`, `OPENAI_API_KEY`, `NPS_API_KEY`
- Configuration: `LOG_LEVEL`, `NODE_ENV`, `DEBUG`
- Custom variables: Any variable prefixed with `MCP_ENV_` (prefix is removed)

Example:
```bash
MCP_ENV_TAVILY_API_KEY=your-key  # Forwarded as TAVILY_API_KEY
MCP_ENV_DATABASE_URL=postgres:// # Forwarded as DATABASE_URL
```

## Package Management

The adapter automatically detects and installs required packages:

### NPM Packages
- Detects `npx` commands and installs packages on-demand
- Supports versioned packages (`package@1.0.0`)
- Memory-efficient caching and cleanup

### GitHub Repositories
- Clones repositories with `--depth 1` for efficiency
- Automatically runs `npm install` if `package.json` exists
- Supports branch/tag specification

### System Executables
- Verifies system executables are available
- No installation needed for system commands

## API Endpoints

### Health Check
```
GET /health
```

Returns adapter status, configuration, and capability information.

### MCP Protocol
```
POST /mcp
```

Handles all MCP JSON-RPC requests. Supports:
- `initialize` - Handled locally with capability negotiation
- `tools/*` - Forwarded to server if tools are supported
- `resources/*` - Forwarded to server if resources are supported  
- `prompts/*` - Forwarded to server if prompts are supported
- Notifications - Handled locally

## Example Usage

### HTTP-based MCP Server
```yaml
apiVersion: mcp.nimbletools.dev/v1
kind: MCPService
metadata:
  name: calculator
spec:
  container:
    image: calculator-mcp:latest
    port: 8000
  deployment:
    type: http
```

### stdio-based MCP Server with Universal Adapter
```yaml
apiVersion: mcp.nimbletools.dev/v1
kind: MCPService
metadata:
  name: echo-mcp
spec:
  container:
    image: ghcr.io/nimblebrain/nimbletools-core-universal-adapter:latest
    port: 8000
  deployment:
    type: stdio
    stdio:
      executable: npx
      args: ["@modelcontextprotocol/server-echo"]
```

## Development

Build the adapter:

```bash
docker build -t nimbletools-core-universal-adapter .
```

Test locally:

```bash
export MCP_EXECUTABLE="npx"
export MCP_ARGS='["@modelcontextprotocol/server-echo"]'
export MCP_SERVER_NAME="echo-test"
python main.py
```

The adapter will be available at `http://localhost:8000/health`.

## Architecture Notes

- **Stateless**: Each request is independent
- **Process Management**: Automatically restarts failed MCP processes
- **Memory Efficient**: Cleans up npm cache and temporary packages
- **Security**: Runs as non-root user in container
- **Monitoring**: Comprehensive health checks and logging

This adapter enables NimbleTools Core to run any MCP server, regardless of whether it was designed for HTTP or stdio communication.