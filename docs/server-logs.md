# Server Logs API

## Overview

The Server Logs API provides structured access to logs from deployed MCP servers, with support for filtering, pagination, and multi-pod aggregation.

## Endpoint

```
GET /v1/workspaces/{workspace_id}/servers/{server_id}/logs
```

## Authentication

Requires Bearer token authentication:

```
Authorization: Bearer {token}
```

## Path Parameters

| Parameter      | Type   | Required | Description                                                                                        |
| -------------- | ------ | -------- | -------------------------------------------------------------------------------------------------- |
| `workspace_id` | UUID   | Yes      | The workspace containing the server                                                                |
| `server_id`    | string | Yes      | Server identifier (supports both simple IDs like "echo" and full names like "ai.nimblebrain/echo") |

## Query Parameters

| Parameter  | Type     | Default | Range/Format                          | Description                                       |
| ---------- | -------- | ------- | ------------------------------------- | ------------------------------------------------- |
| `limit`    | integer  | 10      | 1-1000                                | Maximum number of log entries to return           |
| `since`    | datetime | -       | ISO 8601                              | Only return logs after this timestamp             |
| `until`    | datetime | -       | ISO 8601                              | Only return logs before this timestamp            |
| `level`    | string   | -       | debug, info, warning, error, critical | Minimum log level (returns this level and higher) |
| `pod_name` | string   | -       | -                                     | Filter logs from a specific pod                   |

## Response Schema

### Success Response (200 OK)

```json
{
  "version": "v1",
  "server_id": "string",
  "workspace_id": "uuid",
  "logs": [
    {
      "timestamp": "datetime",
      "level": "string",
      "message": "string",
      "pod_name": "string",
      "container_name": "string"
    }
  ],
  "count": "integer",
  "has_more": "boolean",
  "query_timestamp": "datetime"
}
```

### Response Fields

| Field                   | Type     | Description                                             |
| ----------------------- | -------- | ------------------------------------------------------- |
| `version`               | string   | API version (always "v1")                               |
| `server_id`             | string   | The server ID (normalized)                              |
| `workspace_id`          | UUID     | The workspace UUID                                      |
| `logs`                  | array    | Array of log entries sorted by timestamp (newest first) |
| `logs[].timestamp`      | datetime | When the log was generated (ISO 8601 format)            |
| `logs[].level`          | string   | Log level: debug, info, warning, error, or critical     |
| `logs[].message`        | string   | The actual log message                                  |
| `logs[].pod_name`       | string   | Name of the pod that generated the log                  |
| `logs[].container_name` | string   | Name of the container within the pod                    |
| `count`                 | integer  | Number of log entries returned                          |
| `has_more`              | boolean  | Whether additional logs exist beyond the limit          |
| `query_timestamp`       | datetime | When the logs were queried                              |

## Error Responses

### 404 Not Found

Server not found or has no running pods

```json
{
  "detail": "Server echo not found or has no running pods"
}
```

### 401 Unauthorized

Missing or invalid authentication token

```json
{
  "detail": "Not authenticated"
}
```

### 403 Forbidden

User lacks permission to access this workspace

```json
{
  "detail": "Access denied to workspace"
}
```

### 500 Internal Server Error

Server error while retrieving logs

```json
{
  "detail": "Error retrieving server logs: {error_details}"
}
```

## Log Level Filtering

When using the `level` parameter, the API returns logs at the specified level and all higher severity levels:

- `debug` → Returns all logs (debug, info, warning, error, critical)
- `info` → Returns info, warning, error, critical
- `warning` → Returns warning, error, critical
- `error` → Returns error, critical
- `critical` → Returns only critical

## Log Format Parsing

The API automatically detects and parses common log formats:

### Supported Formats

- **ISO 8601**: `2024-01-01T12:00:00.000Z [INFO] Message`
- **RFC3339**: `2024-01-01T12:00:00Z ERROR Message`
- **Bracketed**: `[DEBUG] This is a debug message`

### Level Mapping

- `WARN` → `WARNING`
- `FATAL` → `CRITICAL`

## Examples

### 1. Get Latest 10 Logs (Default)

```bash
curl -X GET \
  "https://api.nimbletools.dev/v1/workspaces/550e8400-e29b-41d4-a716-446655440000/servers/echo/logs" \
  -H "Authorization: Bearer $TOKEN"
```

### 2. Get 50 Most Recent Error Logs

```bash
curl -X GET \
  "https://api.nimbletools.dev/v1/workspaces/550e8400-e29b-41d4-a716-446655440000/servers/echo/logs?limit=50&level=error" \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Get Logs from Last Hour

```bash
# Calculate timestamp for 1 hour ago
SINCE=$(date -u -d '1 hour ago' '+%Y-%m-%dT%H:%M:%SZ')

curl -X GET \
  "https://api.nimbletools.dev/v1/workspaces/550e8400-e29b-41d4-a716-446655440000/servers/echo/logs?since=$SINCE&limit=100" \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Get Logs Between Two Timestamps

```bash
curl -X GET \
  "https://api.nimbletools.dev/v1/workspaces/550e8400-e29b-41d4-a716-446655440000/servers/echo/logs?since=2024-01-01T10:00:00Z&until=2024-01-01T11:00:00Z" \
  -H "Authorization: Bearer $TOKEN"
```

### 5. Get Logs from Specific Pod

```bash
curl -X GET \
  "https://api.nimbletools.dev/v1/workspaces/550e8400-e29b-41d4-a716-446655440000/servers/echo/logs?pod_name=echo-deployment-abc123" \
  -H "Authorization: Bearer $TOKEN"
```

### 6. Using Full Server Name

```bash
# Server names with namespaces are supported
curl -X GET \
  "https://api.nimbletools.dev/v1/workspaces/550e8400-e29b-41d4-a716-446655440000/servers/ai.nimblebrain%2Fecho/logs" \
  -H "Authorization: Bearer $TOKEN"
```

## Response Example

```json
{
  "version": "v1",
  "server_id": "echo",
  "workspace_id": "550e8400-e29b-41d4-a716-446655440000",
  "logs": [
    {
      "timestamp": "2024-01-01T10:03:00Z",
      "level": "info",
      "message": "Processing request from client 192.168.1.1",
      "pod_name": "echo-deployment-abc123",
      "container_name": "echo-container"
    },
    {
      "timestamp": "2024-01-01T10:02:45Z",
      "level": "warning",
      "message": "High memory usage detected: 85%",
      "pod_name": "echo-deployment-abc123",
      "container_name": "echo-container"
    },
    {
      "timestamp": "2024-01-01T10:02:30Z",
      "level": "info",
      "message": "Health check passed",
      "pod_name": "echo-deployment-def456",
      "container_name": "echo-container"
    }
  ],
  "count": 3,
  "has_more": true,
  "query_timestamp": "2024-01-01T12:00:00Z"
}
```

## Implementation Notes

### Multi-Pod Aggregation

- Logs are collected from all pods belonging to the server deployment
- Results are merged and sorted by timestamp (newest first)
- Each log entry maintains its source pod and container identification

### Performance Considerations

- The API fetches up to 2x the requested limit to account for filtering
- Time-based filtering is applied at the Kubernetes API level when possible
- Large log volumes may require pagination using the `limit` parameter

### Empty Responses

When no logs match the filters or no pods exist, the API returns:

```json
{
  "version": "v1",
  "server_id": "echo",
  "workspace_id": "550e8400-e29b-41d4-a716-446655440000",
  "logs": [],
  "count": 0,
  "has_more": false,
  "query_timestamp": "2024-01-01T12:00:00Z"
}
```

## CLI Integration

The `ntcli` tool provides a convenient interface for accessing logs:

```bash
# Basic usage
ntcli server logs <server-id> --workspace <workspace-id>

# With options
ntcli server logs echo \
  --workspace 550e8400-e29b-41d4-a716-446655440000 \
  --limit 50 \
  --level error \
  --since "1 hour ago"

# Export to file
ntcli server logs echo \
  --workspace 550e8400-e29b-41d4-a716-446655440000 \
  --format json > logs.json
```

## Rate Limiting

The logs endpoint follows standard API rate limiting:

- Default: 100 requests per minute per user
- Burst: Up to 10 concurrent requests
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

## Best Practices

1. **Use Time Filters**: For large deployments, always specify `since` to limit data transfer
2. **Appropriate Limits**: Start with smaller limits and increase if needed
3. **Pod Filtering**: When debugging specific issues, filter by pod to reduce noise
4. **Level Filtering**: Use `level=warning` or higher for production monitoring
5. **Timestamp Handling**: Always use UTC timestamps to avoid timezone issues

## Future Enhancements

- WebSocket support for real-time log streaming
- Full-text search within log messages
- Log export in multiple formats (CSV, JSON Lines, Plain Text)
- Cross-server log aggregation
- Log retention policies and archival
