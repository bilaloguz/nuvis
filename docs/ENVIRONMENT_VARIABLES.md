# Environment Variables

## Overview

This document describes all environment variables used by the biRun application.

## Backend Environment Variables

### Database Configuration

#### DATABASE_URL
- **Description**: PostgreSQL database connection string
- **Format**: `postgresql://username:password@host:port/database`
- **Example**: `postgresql://script_manager_user:password@localhost:5432/script_manager`
- **Required**: Yes
- **Default**: None

### Redis Configuration

#### REDIS_URL
- **Description**: Redis connection string for caching and job queue
- **Format**: `redis://host:port/database`
- **Example**: `redis://localhost:6379/0`
- **Required**: Yes
- **Default**: None

### Security Configuration

#### SECRET_KEY
- **Description**: Secret key for JWT token signing and encryption
- **Format**: String (minimum 32 characters)
- **Example**: `your-very-secure-secret-key-here-change-this-in-production`
- **Required**: Yes
- **Default**: None
- **Security Note**: Must be unique and kept secret in production

#### ACCESS_TOKEN_EXPIRE_MINUTES
- **Description**: JWT token expiration time in minutes
- **Format**: Integer
- **Example**: `30`
- **Required**: No
- **Default**: `30`

### Application Configuration

#### MAX_CONCURRENT_EXECUTIONS
- **Description**: Maximum number of script executions that can run simultaneously
- **Format**: Integer
- **Example**: `8`
- **Required**: No
- **Default**: `8`

#### LONG_RUNNING_DELAY_SECONDS
- **Description**: Time in seconds before marking a script as "long running"
- **Format**: Integer
- **Example**: `30`
- **Required**: No
- **Default**: `30`

#### SCHEDULE_TRIGGER_TOLERANCE_SECONDS
- **Description**: Tolerance in seconds for schedule trigger timing
- **Format**: Integer
- **Example**: `60`
- **Required**: No
- **Default**: `60`

### Development Configuration

#### DEBUG
- **Description**: Enable debug mode for development
- **Format**: Boolean (`True`/`False`)
- **Example**: `True`
- **Required**: No
- **Default**: `False`
- **Production Note**: Should be `False` in production

#### LOG_LEVEL
- **Description**: Logging level for the application
- **Format**: String (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`)
- **Example**: `INFO`
- **Required**: No
- **Default**: `INFO`

### Optional External Services

#### SMTP Configuration
These variables are optional and only needed if email notifications are enabled.

##### SMTP_HOST
- **Description**: SMTP server hostname
- **Format**: String
- **Example**: `smtp.gmail.com`
- **Required**: No
- **Default**: None

##### SMTP_PORT
- **Description**: SMTP server port
- **Format**: Integer
- **Example**: `587`
- **Required**: No
- **Default**: `587`

##### SMTP_USERNAME
- **Description**: SMTP authentication username
- **Format**: String
- **Example**: `your-email@gmail.com`
- **Required**: No
- **Default**: None

##### SMTP_PASSWORD
- **Description**: SMTP authentication password
- **Format**: String
- **Example**: `your-app-password`
- **Required**: No
- **Default**: None

##### SMTP_FROM_EMAIL
- **Description**: From email address for notifications
- **Format**: String (valid email)
- **Example**: `noreply@yourdomain.com`
- **Required**: No
- **Default**: None

### Optional Monitoring

#### SENTRY_DSN
- **Description**: Sentry DSN for error tracking and monitoring
- **Format**: String (Sentry DSN URL)
- **Example**: `https://your-sentry-dsn@sentry.io/project-id`
- **Required**: No
- **Default**: None

## Frontend Environment Variables

### API Configuration

#### REACT_APP_API_URL
- **Description**: Backend API base URL
- **Format**: String (URL)
- **Example**: `http://localhost:8000`
- **Required**: No
- **Default**: `http://localhost:8000`

#### REACT_APP_WS_URL
- **Description**: WebSocket URL for terminal sessions
- **Format**: String (WebSocket URL)
- **Example**: `ws://localhost:8000`
- **Required**: No
- **Default**: `ws://localhost:8000`

## Environment File Setup

### Development Environment

Create a `.env` file in the backend directory:

```bash
# Database
DATABASE_URL=postgresql://script_manager_user:password@localhost:5432/script_manager

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-very-secure-secret-key-here-change-this-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Application
MAX_CONCURRENT_EXECUTIONS=8
LONG_RUNNING_DELAY_SECONDS=30
SCHEDULE_TRIGGER_TOLERANCE_SECONDS=60

# Development
DEBUG=True
LOG_LEVEL=DEBUG
```

### Production Environment

Create a `.env` file in the backend directory:

```bash
# Database
DATABASE_URL=postgresql://script_manager_user:secure_password@localhost:5432/script_manager

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-very-secure-production-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Application
MAX_CONCURRENT_EXECUTIONS=16
LONG_RUNNING_DELAY_SECONDS=60
SCHEDULE_TRIGGER_TOLERANCE_SECONDS=120

# Production
DEBUG=False
LOG_LEVEL=INFO

# Optional: Email notifications
SMTP_HOST=smtp.yourdomain.com
SMTP_PORT=587
SMTP_USERNAME=noreply@yourdomain.com
SMTP_PASSWORD=your-smtp-password
SMTP_FROM_EMAIL=noreply@yourdomain.com

# Optional: Monitoring
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
```

### Docker Environment

For Docker deployments, you can use environment variables directly in `docker-compose.yml`:

```yaml
version: '3.8'

services:
  backend:
    environment:
      - DATABASE_URL=postgresql://script_manager_user:password@postgres:5432/script_manager
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY=your-secret-key
      - DEBUG=False
      - LOG_LEVEL=INFO
```

## Security Best Practices

### Secret Key Generation

Generate a secure secret key for production:

```bash
# Using Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Using OpenSSL
openssl rand -base64 32

# Using /dev/urandom
head -c 32 /dev/urandom | base64
```

### Environment File Security

1. **Never commit `.env` files to version control**
2. **Use different secret keys for different environments**
3. **Rotate secret keys regularly**
4. **Use strong, unique passwords for database and Redis**
5. **Restrict file permissions**: `chmod 600 .env`

### Production Security

1. **Use environment variables instead of `.env` files in production**
2. **Use a secrets management system (e.g., HashiCorp Vault, AWS Secrets Manager)**
3. **Enable SSL/TLS for all connections**
4. **Use strong authentication for database and Redis**
5. **Regularly update and patch all dependencies**

## Validation

### Backend Validation

The application validates environment variables on startup:

```python
# Example validation in main.py
import os
from typing import Optional

def validate_environment():
    required_vars = [
        'DATABASE_URL',
        'REDIS_URL',
        'SECRET_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    # Validate DATABASE_URL format
    database_url = os.getenv('DATABASE_URL')
    if not database_url.startswith('postgresql://'):
        raise ValueError("DATABASE_URL must be a valid PostgreSQL connection string")
    
    # Validate REDIS_URL format
    redis_url = os.getenv('REDIS_URL')
    if not redis_url.startswith('redis://'):
        raise ValueError("REDIS_URL must be a valid Redis connection string")
```

### Frontend Validation

Frontend environment variables are validated at build time:

```javascript
// Example validation in frontend
const requiredEnvVars = {
  REACT_APP_API_URL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
  REACT_APP_WS_URL: process.env.REACT_APP_WS_URL || 'ws://localhost:8000'
};

// Validate URLs
Object.entries(requiredEnvVars).forEach(([key, value]) => {
  try {
    new URL(value);
  } catch (error) {
    throw new Error(`Invalid URL for ${key}: ${value}`);
  }
});
```

## Troubleshooting

### Common Issues

#### Database Connection Errors
```bash
# Check if DATABASE_URL is set
echo $DATABASE_URL

# Test database connection
psql $DATABASE_URL -c "SELECT 1;"
```

#### Redis Connection Errors
```bash
# Check if REDIS_URL is set
echo $REDIS_URL

# Test Redis connection
redis-cli -u $REDIS_URL ping
```

#### Missing Environment Variables
```bash
# Check all environment variables
env | grep -E "(DATABASE|REDIS|SECRET|DEBUG)"

# Check .env file
cat .env
```

#### Invalid Configuration
```bash
# Check application logs for configuration errors
sudo journalctl -u script-manager-backend | grep -i "config\|environment\|variable"
```

### Debug Mode

Enable debug mode to see detailed configuration information:

```bash
# Set debug mode
export DEBUG=True
export LOG_LEVEL=DEBUG

# Restart application
sudo systemctl restart script-manager-backend
```

This will log all environment variables and configuration details to help with troubleshooting.
