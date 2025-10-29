# biRun

A powerful web-based application for managing and executing scripts across multiple servers with scheduling, monitoring, and workflow capabilities.

## 🚀 Features

- **Multi-Server Management**: Execute scripts on multiple servers simultaneously
- **Scheduled Execution**: Cron-based scheduling for automated script runs
- **Real-time Monitoring**: Live output streaming and execution status tracking
- **Workflow Builder**: Create complex automation workflows with conditional logic
- **Health Monitoring**: System and server health checks with detailed metrics
- **User Management**: Role-based access control (Admin/User)
- **Terminal Access**: Interactive terminal sessions via WebSocket
- **Queue Management**: Redis-based job queue with concurrency limits

## 📋 Prerequisites

- Python 3.8+
- Node.js 16+
- PostgreSQL 12+
- Redis 6+
- Git

## 🛠️ Installation

### Backend Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd script-manager
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your database and Redis credentials
   ```

5. **Set up database**
   ```bash
   # Run migrations
   alembic upgrade head
   
   # Create admin user
   python create_admin.py
   ```

6. **Start the backend**
   ```bash
   python main.py
   ```

### Frontend Setup

1. **Install dependencies**
   ```bash
   cd frontend
   npm install
   ```

2. **Start development server**
   ```bash
   npm start
   ```

3. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## 🏗️ Architecture

### Backend (FastAPI)
- **API Layer**: FastAPI with automatic OpenAPI documentation
- **Database**: SQLAlchemy ORM with PostgreSQL
- **Queue System**: Redis Queue (RQ) for background job processing
- **Authentication**: JWT-based authentication
- **WebSocket**: Real-time terminal sessions

### Frontend (React)
- **UI Framework**: React 18 with Bootstrap 5
- **State Management**: React Context API
- **Charts**: Recharts for data visualization
- **Routing**: React Router for navigation

### Infrastructure
- **Database**: PostgreSQL for data persistence
- **Cache/Queue**: Redis for job queuing and caching
- **Migrations**: Alembic for database schema management

## 📚 API Documentation

### Authentication

#### Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "password"
}
```

#### Register
```http
POST /api/auth/register
Content-Type: application/json

{
  "username": "user",
  "password": "password",
  "email": "user@example.com"
}
```

### Servers

#### List Servers
```http
GET /api/servers/
Authorization: Bearer <token>
```

#### Create Server
```http
POST /api/servers/
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Web Server",
  "hostname": "192.168.1.100",
  "username": "ubuntu",
  "port": 22,
  "auth_type": "key",
  "ssh_key": "-----BEGIN OPENSSH PRIVATE KEY-----..."
}
```

#### Execute Script on Server
```http
POST /api/servers/{server_id}/execute
Authorization: Bearer <token>
Content-Type: application/json

{
  "script_content": "echo 'Hello World'",
  "timeout": 30
}
```

### Scripts

#### List Scripts
```http
GET /api/scripts/
Authorization: Bearer <token>
```

#### Create Script
```http
POST /api/scripts/
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Backup Script",
  "content": "#!/bin/bash\ntar -czf backup.tar.gz /var/www",
  "description": "Creates a backup of web files"
}
```

#### Execute Script
```http
POST /api/scripts/{script_id}/execute
Authorization: Bearer <token>
Content-Type: application/json

{
  "server_ids": [1, 2, 3],
  "timeout": 60
}
```

### Schedules

#### List Schedules
```http
GET /api/schedules/
Authorization: Bearer <token>
```

#### Create Schedule
```http
POST /api/schedules/
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Daily Backup",
  "cron_expression": "0 2 * * *",
  "script_id": 1,
  "server_ids": [1, 2, 3],
  "enabled": true
}
```

### Health Monitoring

#### System Health
```http
GET /api/health
Authorization: Bearer <token>
```

#### Server Health
```http
GET /api/health/summary
Authorization: Bearer <token>
```

#### Check All Servers
```http
POST /api/health/check-all
Authorization: Bearer <token>
```

## 🔧 Configuration

### Environment Variables

#### Backend (.env)
```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/script_manager

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Application
MAX_CONCURRENT_EXECUTIONS=8
LONG_RUNNING_DELAY_SECONDS=30
SCHEDULE_TRIGGER_TOLERANCE_SECONDS=60
```

#### Frontend (.env)
```env
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000
```

## 🚀 Deployment

### Production Setup

1. **Configure production database**
   ```bash
   # Update DATABASE_URL in .env
   DATABASE_URL=postgresql://user:password@prod-db:5432/script_manager
   ```

2. **Set up Redis**
   ```bash
   # Install Redis on production server
   sudo apt-get install redis-server
   ```

3. **Configure reverse proxy (Nginx)**
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://localhost:3000;
       }
       
       location /api {
           proxy_pass http://localhost:8000;
       }
       
       location /ws {
           proxy_pass http://localhost:8000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
       }
   }
   ```

4. **Deploy with Docker (Optional)**
   ```bash
   # Create docker-compose.yml
   docker-compose up -d
   ```

## 🔍 Troubleshooting

### Common Issues

#### Database Connection Errors
```bash
# Check database connectivity
python -c "from database import engine; print(engine.execute('SELECT 1').scalar())"
```

#### Redis Connection Issues
```bash
# Test Redis connection
redis-cli ping
```

#### Worker Queue Problems
```bash
# Check RQ workers
python -c "from rq import Worker; print(Worker.all())"
```

#### SSH Connection Failures
- Verify SSH keys are properly formatted
- Check server connectivity and credentials
- Ensure SSH service is running on target servers

### Logs

#### Backend Logs
```bash
# View application logs
tail -f logs/app.log

# View error logs
tail -f logs/error.log
```

#### Frontend Logs
```bash
# View browser console for frontend errors
# Check Network tab for API call failures
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For support and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Review the API documentation

## 🔄 Changelog

### v1.0.0
- Initial release
- Multi-server script execution
- Scheduled execution with cron
- Real-time monitoring
- Workflow builder
- Health monitoring system
- User management and authentication