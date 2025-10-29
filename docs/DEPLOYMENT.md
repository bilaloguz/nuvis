# Deployment Guide

## Overview

This guide covers deploying the biRun application in various environments, from development to production.

## Prerequisites

### System Requirements

#### Minimum Requirements
- **CPU**: 2 cores
- **RAM**: 4GB
- **Storage**: 20GB SSD
- **OS**: Ubuntu 20.04+ / CentOS 8+ / RHEL 8+

#### Recommended Requirements
- **CPU**: 4+ cores
- **RAM**: 8GB+
- **Storage**: 50GB+ SSD
- **OS**: Ubuntu 22.04 LTS

### Software Dependencies

#### Backend
- Python 3.8+
- PostgreSQL 12+
- Redis 6+
- Git

#### Frontend
- Node.js 16+
- npm 8+

#### System Packages
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv postgresql postgresql-contrib redis-server git

# CentOS/RHEL
sudo yum update
sudo yum install -y python3 python3-pip postgresql-server postgresql-contrib redis git
```

## Development Deployment

### Quick Start

1. **Clone Repository**
   ```bash
   git clone <repository-url>
   cd script-manager
   ```

2. **Backend Setup**
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Database Setup**
   ```bash
   # Start PostgreSQL
   sudo systemctl start postgresql
   sudo systemctl enable postgresql
   
   # Create database
   sudo -u postgres createdb script_manager
   sudo -u postgres createuser script_manager_user
   sudo -u postgres psql -c "ALTER USER script_manager_user PASSWORD 'your_password';"
   sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE script_manager TO script_manager_user;"
   ```

4. **Redis Setup**
   ```bash
   sudo systemctl start redis
   sudo systemctl enable redis
   ```

5. **Environment Configuration**
   ```bash
   cp .env.example .env
   # Edit .env with your database and Redis credentials
   ```

6. **Database Migration**
   ```bash
   alembic upgrade head
   ```

7. **Create Admin User**
   ```bash
   python create_admin.py
   ```

8. **Start Backend**
   ```bash
   python main.py
   ```

9. **Frontend Setup** (New Terminal)
   ```bash
   cd frontend
   npm install
   npm start
   ```

10. **Access Application**
    - Frontend: http://localhost:3000
    - Backend API: http://localhost:8000
    - API Docs: http://localhost:8000/docs

## Production Deployment

### Server Preparation

#### 1. System Updates
```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo reboot
```

#### 2. Create Application User
```bash
sudo adduser scriptmanager
sudo usermod -aG sudo scriptmanager
sudo su - scriptmanager
```

#### 3. Install Dependencies
```bash
# Python
sudo apt-get install -y python3 python3-pip python3-venv python3-dev

# PostgreSQL
sudo apt-get install -y postgresql postgresql-contrib postgresql-client

# Redis
sudo apt-get install -y redis-server

# Reverse proxy (optional)
# If you decide to use one, configure separately (not required).

# Node.js (using NodeSource repository)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### Database Setup

#### 1. Configure PostgreSQL
```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE script_manager;
CREATE USER script_manager_user WITH PASSWORD 'secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE script_manager TO script_manager_user;
ALTER USER script_manager_user CREATEDB;
\q
```

#### 2. Configure PostgreSQL for Production
```bash
sudo nano /etc/postgresql/14/main/postgresql.conf
```

Update the following settings:
```conf
listen_addresses = 'localhost'
port = 5432
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
```

#### 3. Configure PostgreSQL Authentication
```bash
sudo nano /etc/postgresql/14/main/pg_hba.conf
```

Add:
```conf
local   script_manager    script_manager_user    md5
host    script_manager    script_manager_user    127.0.0.1/32    md5
```

#### 4. Restart PostgreSQL
```bash
sudo systemctl restart postgresql
sudo systemctl enable postgresql
```

### Redis Setup

#### 1. Configure Redis
```bash
sudo nano /etc/redis/redis.conf
```

Update key settings:
```conf
bind 127.0.0.1
port 6379
timeout 300
tcp-keepalive 300
maxmemory 256mb
maxmemory-policy allkeys-lru
```

#### 2. Start Redis
```bash
sudo systemctl restart redis
sudo systemctl enable redis
```

### Application Deployment

#### 1. Clone and Setup
```bash
cd /home/scriptmanager
git clone <repository-url> script-manager
cd script-manager
```

#### 2. Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

#### 3. Environment Configuration
```bash
cp .env.example .env
nano .env
```

Production `.env`:
```env
# Database
DATABASE_URL=postgresql://script_manager_user:secure_password_here@localhost:5432/script_manager

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-very-secure-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Application
MAX_CONCURRENT_EXECUTIONS=8
LONG_RUNNING_DELAY_SECONDS=30
SCHEDULE_TRIGGER_TOLERANCE_SECONDS=60

# Production
DEBUG=False
LOG_LEVEL=INFO
```

#### 4. Database Migration
```bash
alembic upgrade head
```

#### 5. Create Admin User
```bash
python create_admin.py
```

#### 6. Frontend Build
```bash
cd ../frontend
npm install
npm run build
```

### Process Management

#### 1. Create Systemd Service for Backend
```bash
sudo nano /etc/systemd/system/script-manager-backend.service
```

```ini
[Unit]
Description=biRun Backend
After=network.target postgresql.service redis.service

[Service]
Type=exec
User=scriptmanager
Group=scriptmanager
WorkingDirectory=/home/scriptmanager/script-manager/backend
Environment=PATH=/home/scriptmanager/script-manager/backend/venv/bin
ExecStart=/home/scriptmanager/script-manager/backend/venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8000 main:app
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 2. Create Systemd Service for RQ Workers
```bash
sudo nano /etc/systemd/system/script-manager-workers.service
```

```ini
[Unit]
Description=biRun RQ Workers
After=network.target postgresql.service redis.service

[Service]
Type=exec
User=scriptmanager
Group=scriptmanager
WorkingDirectory=/home/scriptmanager/script-manager/backend
Environment=PATH=/home/scriptmanager/script-manager/backend/venv/bin
ExecStart=/home/scriptmanager/script-manager/backend/venv/bin/python -m rq worker --url redis://localhost:6379/0
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 3. Start Services
```bash
sudo systemctl daemon-reload
sudo systemctl start script-manager-backend
sudo systemctl start script-manager-workers
sudo systemctl enable script-manager-backend
sudo systemctl enable script-manager-workers
```

### Reverse Proxy (optional)
If you choose to put a reverse proxy in front, configure it per your infra.
We do not require or ship Nginx configuration by default.

### SSL Configuration (Optional)

#### 1. Install Certbot
```bash
sudo apt-get install -y certbot
```

#### 2. Obtain SSL Certificate
```bash
sudo certbot certonly --standalone -d your-domain.com -d www.your-domain.com
```

#### 3. Auto-renewal
```bash
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

## Docker Deployment

### Docker Compose Setup

#### 1. Create docker-compose.yml
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:14
    environment:
      POSTGRES_DB: script_manager
      POSTGRES_USER: script_manager_user
      POSTGRES_PASSWORD: secure_password_here
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql://script_manager_user:secure_password_here@postgres:5432/script_manager
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: your-very-secure-secret-key-here
    depends_on:
      - postgres
      - redis
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
    command: >
      sh -c "alembic upgrade head && 
             python create_admin.py && 
             gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 main:app"

  workers:
    build: ./backend
    environment:
      DATABASE_URL: postgresql://script_manager_user:secure_password_here@postgres:5432/script_manager
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    volumes:
      - ./backend:/app
    command: python -m rq worker --url redis://redis:6379/0

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules

volumes:
  postgres_data:
  redis_data:
```

#### 2. Create Dockerfiles

**Backend Dockerfile:**
```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

**Frontend Dockerfile:**
```dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "start"]
```