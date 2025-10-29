# biRun Architecture

biRun is a modern web application designed for managing and executing scripts across multiple servers. It follows a microservices-inspired architecture with clear separation of concerns between the backend API, frontend UI, and supporting services.

## System Architecture

### High-Level Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Database      │
│   (React)       │◄──►│   (FastAPI)     │◄──►│   (PostgreSQL)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         │              ┌─────────────────┐              │
         │              │     Redis       │              │
         │              │   (Cache/Queue) │              │
         │              └─────────────────┘              │
         │                       │                       │
         │              ┌─────────────────┐              │
         └──────────────►│   WebSocket     │             │
                        │   (Terminal)    │              │
                        └─────────────────┘              │
                                 │                       │
                        ┌─────────────────┐              │
                        │   Target        │              │
                        │   Servers       │              │
                        │   (SSH)         │              │
                        └─────────────────┘              │
```

## Component Architecture

### Frontend (React)

#### Technology Stack
- **React 18**: Modern UI library with hooks and context
- **Bootstrap 5**: CSS framework for responsive design
- **React Router**: Client-side routing
- **Axios**: HTTP client for API communication
- **Recharts**: Data visualization library
- **WebSocket API**: Real-time terminal communication

#### Component Structure
```
src/
├── components/
│   ├── Dashboard.js          # Main dashboard with health monitoring
│   ├── ScriptManagement.js   # Script CRUD operations
│   ├── ServerManagement.js   # Server management interface
│   ├── Schedules.js          # Schedule management
│   ├── Executions.js         # Execution history and monitoring
│   ├── Workflows.js          # Workflow builder interface
│   ├── Settings.js           # Application settings
│   └── Auth/                 # Authentication components
├── contexts/
│   └── AuthContext.js        # Authentication state management
├── services/
│   ├── api.js               # API service layer
│   └── websocket.js         # WebSocket service
└── utils/
    └── helpers.js           # Utility functions
```

#### State Management
- **React Context**: Global state for authentication
- **Local State**: Component-specific state with useState/useReducer
- **Custom Hooks**: Reusable stateful logic

### Backend (FastAPI)

#### Technology Stack
- **FastAPI**: Modern Python web framework
- **SQLAlchemy**: ORM for database operations
- **Alembic**: Database migration tool
- **Pydantic**: Data validation and serialization
- **JWT**: Token-based authentication
- **Paramiko**: SSH client for server connections
- **Redis Queue (RQ)**: Background job processing
- **WebSocket**: Real-time communication

#### API Structure
```
backend/
├── main.py                   # FastAPI application entry point
├── database.py              # Database connection and session management
├── models.py                # SQLAlchemy models
├── schemas.py               # Pydantic schemas
├── auth.py                  # Authentication utilities
├── routers/
│   ├── auth.py              # Authentication endpoints
│   ├── servers.py           # Server management endpoints
│   ├── scripts.py           # Script management endpoints
│   ├── schedules.py         # Schedule management endpoints
│   ├── executions.py        # Execution monitoring endpoints
│   ├── workflows.py         # Workflow management endpoints
│   ├── health.py            # Health monitoring endpoints
│   └── terminal.py          # WebSocket terminal endpoints
├── services/
│   ├── script_executor.py   # Script execution service
│   ├── scheduler.py         # Schedule management service
│   └── health_checker.py    # Health monitoring service
├── tasks.py                 # RQ background tasks
├── rq_queue.py              # Redis queue configuration
└── migrations/              # Alembic migration files
```

#### API Design Principles
- **RESTful**: Follows REST conventions
- **Stateless**: No server-side session state
- **Resource-based**: URLs represent resources
- **HTTP Methods**: Proper use of GET, POST, PUT, DELETE
- **Status Codes**: Meaningful HTTP status codes
- **Error Handling**: Consistent error response format

### Database (PostgreSQL)

#### Schema Design
```sql
-- Core entities
users (id, username, email, password_hash, role, created_at)
servers (id, name, hostname, username, port, auth_type, ssh_key, password, created_at)
scripts (id, name, content, description, created_at, updated_at)
schedules (id, name, cron_expression, script_id, server_ids, enabled, next_run_at, created_at)
executions (id, script_id, server_id, status, started_at, completed_at, output, exit_code, created_at)
workflows (id, name, description, nodes, edges, enabled, created_at, updated_at)

-- Supporting tables
server_groups (id, name, description, server_ids, created_at)
audit_logs (id, user_id, action, resource_type, resource_id, details, created_at)
settings (id, key, value, updated_at)
```

#### Design Principles
- **Normalization**: Proper database normalization
- **Indexing**: Strategic indexes for performance
- **Constraints**: Foreign key and check constraints
- **Migrations**: Version-controlled schema changes
- **Backups**: Regular backup strategy

### Cache and Queue (Redis)

#### Redis Usage
- **Session Storage**: JWT token blacklist
- **Job Queue**: Background script execution
- **Caching**: Frequently accessed data
- **Rate Limiting**: API rate limiting
- **Semaphores**: Concurrency control

#### Queue Architecture
```
Redis Queue (RQ)
├── default queue           # Script execution jobs
├── failed queue           # Failed job storage
├── workers                # Background worker processes
└── semaphores             # Concurrency control
```

## Data Flow

### Script Execution Flow

1. **User Request**: User initiates script execution via UI
2. **API Validation**: Backend validates request and user permissions
3. **Job Enqueue**: Script execution job added to Redis queue
4. **Worker Processing**: RQ worker picks up job from queue
5. **SSH Connection**: Worker establishes SSH connection to target server
6. **Script Execution**: Script executed on target server
7. **Output Capture**: Real-time output captured and stored
8. **Status Update**: Execution status updated in database
9. **UI Notification**: Frontend notified of completion via polling

### Schedule Execution Flow

1. **Scheduler Loop**: Background scheduler checks for due schedules
2. **Schedule Validation**: Validates schedule and target servers
3. **Job Creation**: Creates execution jobs for each target server
4. **Queue Processing**: Jobs processed by RQ workers
5. **Execution Monitoring**: Scheduler monitors execution status
6. **Next Run Calculation**: Calculates next scheduled run time

### Health Monitoring Flow

1. **Health Check Trigger**: Manual or scheduled health check initiated
2. **Server Connection**: SSH connection established to target server
3. **System Metrics**: System metrics collected (CPU, memory, disk, etc.)
4. **Database Update**: Health data stored in database
5. **UI Refresh**: Dashboard updated with latest health information

## Security Architecture

### Authentication and Authorization

#### JWT Token Flow
```
1. User Login → 2. Credential Validation → 3. JWT Generation → 4. Token Storage
5. API Request → 6. Token Validation → 7. User Context → 8. Resource Access
```

#### Role-Based Access Control
- **Admin**: Full system access
- **User**: Limited access to assigned resources
- **API**: Token-based authentication
- **WebSocket**: Token-based authentication

### Data Security

#### Encryption
- **Passwords**: bcrypt hashing
- **SSH Keys**: Encrypted storage
- **API Keys**: Secure storage
- **Database**: Connection encryption

#### Input Validation
- **Pydantic Schemas**: Request validation
- **SQL Injection**: Parameterized queries
- **XSS Prevention**: Input sanitization
- **CSRF Protection**: Token validation

## Performance Architecture

### Caching Strategy

#### Redis Caching
- **User Sessions**: JWT token validation
- **Server Health**: Cached health data
- **Script Metadata**: Frequently accessed script information
- **API Responses**: Cached API responses

#### Database Optimization
- **Indexing**: Strategic database indexes
- **Query Optimization**: Efficient SQL queries
- **Connection Pooling**: Database connection management
- **Read Replicas**: Future scalability option

### Scalability Considerations

#### Horizontal Scaling
- **Load Balancer**: Multiple backend instances
- **Database Clustering**: PostgreSQL clustering
- **Redis Clustering**: Redis cluster setup
- **Worker Scaling**: Multiple RQ workers

#### Vertical Scaling
- **Resource Monitoring**: CPU, memory, disk usage
- **Performance Tuning**: Database and Redis tuning
- **Caching**: Aggressive caching strategy
- **CDN**: Static asset delivery

## Deployment Architecture

### Development Environment
```
Developer Machine
├── Frontend (React Dev Server)
├── Backend (FastAPI Dev Server)
├── Database (PostgreSQL)
├── Redis (Local Instance)
└── Target Servers (SSH)
```

### Production Environment
```
Load Balancer (optional)
├── Frontend (Static Files)
├── Backend (Gunicorn + Uvicorn)
├── Workers (RQ Workers)
├── Database (PostgreSQL Cluster)
├── Redis (Redis Cluster)
└── Target Servers (SSH)
```

### Container Architecture (Docker)
```
Docker Compose
├── Frontend Container
├── Backend Container
├── Worker Container
├── Database Container
├── Redis Container
└── Reverse proxy (optional)
```

## Monitoring and Observability

### Logging Strategy

#### Application Logs
- **Structured Logging**: JSON format logs
- **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Log Aggregation**: Centralized log collection
- **Log Rotation**: Automated log rotation

#### Audit Logs
- **User Actions**: Login, logout, resource access
- **System Events**: Script executions, schedule changes
- **Security Events**: Failed logins, permission denials
- **Data Changes**: CRUD operations on resources

### Health Monitoring

#### System Health
- **Database Health**: Connection status, query performance
- **Redis Health**: Memory usage, connection status
- **Worker Health**: Queue length, worker status
- **API Health**: Response times, error rates

#### Server Health
- **SSH Connectivity**: Connection status
- **System Metrics**: CPU, memory, disk usage
- **Service Status**: Running services
- **Performance Metrics**: Load averages, response times

### Metrics and Alerting

#### Key Metrics
- **Execution Success Rate**: Percentage of successful executions
- **Average Execution Time**: Mean execution duration
- **Queue Length**: Number of pending jobs
- **Error Rate**: Percentage of failed operations
- **Response Time**: API response times

#### Alerting Rules
- **High Error Rate**: Alert when error rate > 5%
- **Queue Backlog**: Alert when queue length > 100
- **Server Down**: Alert when server unreachable
- **Resource Usage**: Alert when CPU/memory > 80%

## Integration Architecture

### External Integrations

#### SSH Integration
- **Paramiko Library**: Python SSH client
- **Key Authentication**: SSH key support
- **Password Authentication**: Password fallback
- **Connection Pooling**: Reuse SSH connections

#### Database Integration
- **SQLAlchemy ORM**: Object-relational mapping
- **Connection Pooling**: Efficient connection management
- **Migration System**: Alembic migrations
- **Query Optimization**: Efficient database queries

#### Redis Integration
- **Redis Queue**: Background job processing
- **Caching**: Data caching layer
- **Pub/Sub**: Real-time notifications
- **Lua Scripts**: Atomic operations

### API Integration

#### REST API
- **OpenAPI Specification**: Automatic API documentation
- **Request Validation**: Pydantic schema validation
- **Response Serialization**: Consistent response format
- **Error Handling**: Standardized error responses

#### WebSocket API
- **Real-time Communication**: Terminal sessions
- **Authentication**: JWT token validation
- **Message Protocol**: Structured message format
- **Connection Management**: Connection lifecycle

## Future Architecture Considerations

### Planned Enhancements

#### Microservices Migration
- **Service Decomposition**: Break into smaller services
- **API Gateway**: Centralized API management
- **Service Discovery**: Dynamic service registration
- **Event Sourcing**: Event-driven architecture

#### Cloud Native Features
- **Kubernetes**: Container orchestration
- **Service Mesh**: Istio or Linkerd
- **Observability**: Prometheus, Grafana, Jaeger
- **CI/CD**: GitOps deployment pipeline

#### Advanced Features
- **Multi-tenancy**: Tenant isolation
- **Plugin System**: Extensible architecture
- **API Versioning**: Backward compatibility
- **GraphQL**: Alternative API interface

### Scalability Roadmap

#### Phase 1: Current
- Single instance deployment
- Basic monitoring
- Simple caching

#### Phase 2: Scaling
- Load balancing
- Database clustering
- Redis clustering
- Worker scaling

#### Phase 3: Advanced
- Microservices architecture
- Event-driven design
- Cloud native deployment
- Advanced monitoring

## Technology Decisions

### Why FastAPI?
- **Performance**: High performance Python framework
- **Type Safety**: Built-in type hints and validation
- **Documentation**: Automatic OpenAPI documentation
- **Modern**: Async/await support
- **Ecosystem**: Rich ecosystem and community

### Why React?
- **Component-based**: Reusable UI components
- **Performance**: Virtual DOM and efficient rendering
- **Ecosystem**: Large ecosystem and community
- **Developer Experience**: Excellent tooling and debugging
- **Future-proof**: Modern JavaScript features

### Why PostgreSQL?
- **ACID Compliance**: Reliable data integrity
- **Performance**: Excellent query performance
- **Features**: Rich feature set and extensions
- **Scalability**: Horizontal and vertical scaling
- **Open Source**: No licensing costs

### Why Redis?
- **Performance**: In-memory data store
- **Versatility**: Multiple data structures
- **Persistence**: Optional data persistence
- **Clustering**: Built-in clustering support
- **Ecosystem**: Rich ecosystem and tools

This architecture provides a solid foundation for the biRun application while maintaining flexibility for future enhancements and scalability requirements.
