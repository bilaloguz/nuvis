# API Documentation

## Overview

The biRun API is built with FastAPI and provides comprehensive endpoints for managing servers, scripts, schedules, and workflows. All API endpoints require authentication unless otherwise specified.

## Base URL

```
http://localhost:8000/api
```

## Authentication

The API uses JWT (JSON Web Token) authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

## Response Format

All API responses follow a consistent format:

### Success Response
```json
{
  "data": <response_data>,
  "message": "Success",
  "status": "success"
}
```

### Error Response
```json
{
  "error": "Error message",
  "status": "error",
  "details": <additional_error_info>
}
```

## Endpoints

### Authentication

#### POST /auth/login
Authenticate user and receive JWT token.

**Request Body:**
```json
{
  "username": "string",
  "password": "string"
}
```

**Response:**
```json
{
  "access_token": "string",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "role": "admin"
  }
}
```

#### POST /auth/register
Register a new user account.

**Request Body:**
```json
{
  "username": "string",
  "password": "string",
  "email": "string"
}
```

**Response:**
```json
{
  "message": "User created successfully",
  "user": {
    "id": 2,
    "username": "newuser",
    "email": "newuser@example.com",
    "role": "user"
  }
}
```

### Servers

#### GET /servers/
List all servers.

**Query Parameters:**
- `page` (int): Page number (default: 1)
- `limit` (int): Items per page (default: 10)
- `search` (string): Search term for server name/hostname

**Response:**
```json
{
  "servers": [
    {
      "id": 1,
      "name": "Web Server",
      "hostname": "192.168.1.100",
      "username": "ubuntu",
      "port": 22,
      "auth_type": "key",
      "created_at": "2024-01-01T00:00:00Z",
      "last_health_check": "2024-01-01T12:00:00Z",
      "health_status": "healthy"
    }
  ],
  "total": 1,
  "page": 1,
  "pages": 1
}
```

#### POST /servers/
Create a new server.

**Request Body:**
```json
{
  "name": "string",
  "hostname": "string",
  "username": "string",
  "port": 22,
  "auth_type": "key|password",
  "ssh_key": "string", // Required if auth_type is "key"
  "password": "string", // Required if auth_type is "password"
  "description": "string"
}
```

#### GET /servers/{server_id}
Get server details.

#### PUT /servers/{server_id}
Update server.

#### DELETE /servers/{server_id}
Delete server.

#### POST /servers/{server_id}/execute
Execute a script directly on the server.

**Request Body:**
```json
{
  "script_content": "string",
  "timeout": 30
}
```

#### POST /servers/{server_id}/health/check
Trigger health check for specific server.

### Scripts

#### GET /scripts/
List all scripts.

**Query Parameters:**
- `page` (int): Page number
- `limit` (int): Items per page
- `search` (string): Search term

**Response:**
```json
{
  "scripts": [
    {
      "id": 1,
      "name": "Backup Script",
      "content": "#!/bin/bash\ntar -czf backup.tar.gz /var/www",
      "description": "Creates a backup of web files",
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "pages": 1
}
```

#### POST /scripts/
Create a new script.

**Request Body:**
```json
{
  "name": "string",
  "content": "string",
  "description": "string"
}
```

#### GET /scripts/{script_id}
Get script details.

#### PUT /scripts/{script_id}
Update script.

#### DELETE /scripts/{script_id}
Delete script.

#### POST /scripts/{script_id}/execute
Execute script on multiple servers.

**Request Body:**
```json
{
  "server_ids": [1, 2, 3],
  "timeout": 60,
  "group_id": 1 // Optional: execute on server group
}
```

**Response:**
```json
{
  "execution_id": "uuid",
  "status": "queued",
  "message": "Script execution queued successfully"
}
```

#### GET /scripts/{script_id}/executions
Get execution history for a script.

### Schedules

#### GET /schedules/
List all schedules.

**Response:**
```json
{
  "schedules": [
    {
      "id": 1,
      "name": "Daily Backup",
      "cron_expression": "0 2 * * *",
      "script_id": 1,
      "server_ids": [1, 2, 3],
      "enabled": true,
      "next_run_at": "2024-01-02T02:00:00Z",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### POST /schedules/
Create a new schedule.

**Request Body:**
```json
{
  "name": "string",
  "cron_expression": "string",
  "script_id": 1,
  "server_ids": [1, 2, 3],
  "enabled": true
}
```

#### GET /schedules/{schedule_id}
Get schedule details.

#### PUT /schedules/{schedule_id}
Update schedule.

#### DELETE /schedules/{schedule_id}
Delete schedule.

#### POST /schedules/{schedule_id}/toggle
Enable/disable schedule.

### Executions

#### GET /scripts/executions/
List script executions.

**Query Parameters:**
- `page` (int): Page number
- `limit` (int): Items per page
- `status` (string): Filter by status (completed, running, failed)
- `script_id` (int): Filter by script ID
- `server_id` (int): Filter by server ID
- `start_date` (string): Filter by start date (ISO format)
- `end_date` (string): Filter by end date (ISO format)

**Response:**
```json
{
  "executions": [
    {
      "id": 1,
      "script_id": 1,
      "server_id": 1,
      "status": "completed",
      "started_at": "2024-01-01T12:00:00Z",
      "completed_at": "2024-01-01T12:05:00Z",
      "output": "Script executed successfully",
      "exit_code": 0,
      "script": {
        "id": 1,
        "name": "Backup Script"
      },
      "server": {
        "id": 1,
        "name": "Web Server"
      }
    }
  ],
  "total": 1,
  "page": 1,
  "pages": 1
}
```

#### GET /scripts/executions/{execution_id}
Get execution details.

#### POST /scripts/executions/{execution_id}/stop
Stop a running execution.

### Health Monitoring

#### GET /health
Get comprehensive system health status.

**Response:**
```json
{
  "overall_status": "healthy",
  "total_response_time_ms": 45,
  "components": {
    "database": {
      "status": "healthy",
      "response_time_ms": 12,
      "message": "Connection successful"
    },
    "redis": {
      "status": "healthy",
      "response_time_ms": 8,
      "redis_version": "6.2.7",
      "used_memory_human": "1.2M",
      "connected_clients": 3
    },
    "worker_queue": {
      "status": "healthy",
      "response_time_ms": 25,
      "active_workers": 2,
      "queue_stats": {
        "queue_length": 0,
        "failed_jobs": 0
      }
    }
  },
  "system_metrics": {
    "max_concurrent_executions": 8,
    "current_running_executions": 2,
    "recent_executions_1h": {
      "completed": 15,
      "running": 2,
      "failed": 1
    }
  }
}
```

#### GET /health/summary
Get server health summary.

**Response:**
```json
{
  "servers": [
    {
      "server_id": 1,
      "server_name": "Web Server",
      "status": "healthy",
      "uptime_seconds": 86400,
      "load_1min": 0.5,
      "disk_usage": 45.2,
      "memory_usage": 67.8,
      "last_checked": "2024-01-01T12:00:00Z"
    }
  ]
}
```

#### POST /health/check-all
Trigger health check for all servers.

### Workflows

#### GET /workflows/
List all workflows.

#### POST /workflows/
Create a new workflow.

**Request Body:**
```json
{
  "name": "string",
  "description": "string",
  "nodes": [
    {
      "id": "node1",
      "type": "trigger",
      "config": {
        "cron_expression": "0 2 * * *"
      }
    },
    {
      "id": "node2",
      "type": "script",
      "config": {
        "script_id": 1,
        "server_ids": [1, 2]
      }
    }
  ],
  "edges": [
    {
      "from": "node1",
      "to": "node2"
    }
  ]
}
```

#### GET /workflows/{workflow_id}
Get workflow details.

#### PUT /workflows/{workflow_id}
Update workflow.

#### DELETE /workflows/{workflow_id}
Delete workflow.

#### POST /workflows/{workflow_id}/run
Execute workflow manually.

### Server Groups

#### GET /server-groups/
List all server groups.

#### POST /server-groups/
Create a new server group.

**Request Body:**
```json
{
  "name": "string",
  "description": "string",
  "server_ids": [1, 2, 3]
}
```

#### GET /server-groups/{group_id}
Get server group details.

#### PUT /server-groups/{group_id}
Update server group.

#### DELETE /server-groups/{group_id}
Delete server group.

### Settings

#### GET /settings/
Get application settings.

**Response:**
```json
{
  "max_concurrent_executions": 8,
  "long_running_delay_seconds": 30,
  "schedule_trigger_tolerance_seconds": 60,
  "access_token_expire_minutes": 30
}
```

#### PUT /settings/
Update application settings.

**Request Body:**
```json
{
  "max_concurrent_executions": 10,
  "long_running_delay_seconds": 45,
  "schedule_trigger_tolerance_seconds": 90,
  "access_token_expire_minutes": 60
}
```

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid request data |
| 401 | Unauthorized - Invalid or missing authentication |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource not found |
| 422 | Unprocessable Entity - Validation error |
| 500 | Internal Server Error - Server error |

## Rate Limiting

API endpoints are rate limited to prevent abuse:
- Authentication endpoints: 5 requests per minute
- Other endpoints: 100 requests per minute

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

## WebSocket Endpoints

### Terminal Sessions

Connect to WebSocket for interactive terminal sessions:

```
ws://localhost:8000/ws/terminal/{server_id}
```

**Authentication:** Include JWT token in query parameter:
```
ws://localhost:8000/ws/terminal/1?token=<jwt-token>
```

**Message Format:**
```json
{
  "type": "command",
  "data": "ls -la"
}
```

**Response Format:**
```json
{
  "type": "output",
  "data": "total 12\ndrwxr-xr-x 2 ubuntu ubuntu 4096 Jan 1 12:00 ."
}
```
