# Troubleshooting Guide

## Quick Diagnostics

### System Health Check
```bash
# Check all services
sudo systemctl status script-manager-backend script-manager-workers postgresql redis

# Check application health
curl http://localhost:8000/api/health/ping

# Check database connectivity
sudo -u postgres psql -c "SELECT 1;"

# Check Redis connectivity
redis-cli ping
```

### Log Locations
```bash
# Application logs
sudo journalctl -u script-manager-backend -f
sudo journalctl -u script-manager-workers -f

# Database logs
sudo tail -f /var/log/postgresql/postgresql-14-main.log

# Redis logs
sudo tail -f /var/log/redis/redis-server.log

# Reverse proxy logs (if used)
# Check your platform-specific proxy logs
```

## Common Issues

### 1. Application Won't Start

#### Symptoms
- Service fails to start
- Error messages in logs
- 502 Bad Gateway errors

#### Diagnosis
```bash
# Check service status
sudo systemctl status script-manager-backend

# Check detailed logs
sudo journalctl -u script-manager-backend -n 100

# Check if port is in use
sudo netstat -tulpn | grep :8000
```

#### Solutions

**Port Already in Use:**
```bash
# Find process using port 8000
sudo lsof -i :8000

# Kill the process
sudo kill -9 <PID>

# Restart service
sudo systemctl restart script-manager-backend
```

**Database Connection Failed:**
```bash
# Check database status
sudo systemctl status postgresql

# Test database connection
psql -h localhost -U script_manager_user -d script_manager

# Check database configuration
sudo nano /etc/postgresql/14/main/postgresql.conf
sudo nano /etc/postgresql/14/main/pg_hba.conf
```

**Missing Dependencies:**
```bash
# Reinstall Python dependencies
cd /home/scriptmanager/script-manager/backend
source venv/bin/activate
pip install -r requirements.txt
```

**Permission Issues:**
```bash
# Fix ownership
sudo chown -R scriptmanager:scriptmanager /home/scriptmanager/script-manager

# Fix permissions
chmod +x /home/scriptmanager/script-manager/backend/main.py
```

### 2. Database Issues

#### Symptoms
- "Connection refused" errors
- "Authentication failed" errors
- Slow query performance

#### Diagnosis
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Check database logs
sudo tail -f /var/log/postgresql/postgresql-14-main.log

# Test connection
psql -h localhost -U script_manager_user -d script_manager
```

#### Solutions

**PostgreSQL Not Running:**
```bash
# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Check if it's listening
sudo netstat -tulpn | grep :5432
```

**Authentication Issues:**
```bash
# Reset user password
sudo -u postgres psql
ALTER USER script_manager_user PASSWORD 'new_password';

# Update .env file with new password
nano /home/scriptmanager/script-manager/backend/.env
```

**Database Doesn't Exist:**
```bash
# Create database
sudo -u postgres createdb script_manager
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE script_manager TO script_manager_user;"
```

**Migration Issues:**
```bash
# Check migration status
cd /home/scriptmanager/script-manager/backend
source venv/bin/activate
alembic current

# Run migrations
alembic upgrade head

# If migrations fail, check for conflicts
alembic history
alembic show <revision_id>
```

### 3. Redis Issues

#### Symptoms
- "Connection refused" to Redis
- Queue jobs not processing
- Memory usage errors

#### Diagnosis
```bash
# Check Redis status
sudo systemctl status redis

# Test Redis connection
redis-cli ping

# Check Redis logs
sudo tail -f /var/log/redis/redis-server.log

# Check Redis memory usage
redis-cli info memory
```

#### Solutions

**Redis Not Running:**
```bash
# Start Redis
sudo systemctl start redis
sudo systemctl enable redis

# Check configuration
sudo nano /etc/redis/redis.conf
```

**Memory Issues:**
```bash
# Check memory usage
redis-cli info memory

# Clear Redis cache (WARNING: This will clear all data)
redis-cli FLUSHALL

# Configure memory limits
sudo nano /etc/redis/redis.conf
# Add: maxmemory 256mb
# Add: maxmemory-policy allkeys-lru
```

**Connection Issues:**
```bash
# Check Redis configuration
sudo nano /etc/redis/redis.conf
# Ensure: bind 127.0.0.1

# Restart Redis
sudo systemctl restart redis
```

### 4. Frontend Issues

#### Symptoms
- White screen or loading errors
- API calls failing
- Static files not loading

#### Diagnosis
```bash
# Check if frontend is built
ls -la /home/scriptmanager/script-manager/frontend/build/

# Check browser console for errors
# Open Developer Tools (F12) and check Console tab
```

#### Solutions

**Frontend Not Built:**
```bash
# Build frontend
cd /home/scriptmanager/script-manager/frontend
npm install
npm run build
```

**Reverse Proxy Issues (if used):**
```bash
# Validate your reverse proxy configuration and logs per your platform
```

**API Connection Issues:**
```bash
# Check if backend is running
curl http://localhost:8000/api/health/ping
```

### 5. Script Execution Issues

#### Symptoms
- Scripts stuck in "running" status
- Scripts fail immediately
- No output from scripts

#### Diagnosis
```bash
# Check worker status
sudo systemctl status script-manager-workers

# Check Redis queue
redis-cli
> LLEN rq:queue:default
> LRANGE rq:queue:default 0 -1

# Check execution logs
sudo journalctl -u script-manager-workers -f
```

#### Solutions

**Workers Not Running:**
```bash
# Start workers
sudo systemctl start script-manager-workers
sudo systemctl enable script-manager-workers

# Check worker logs
sudo journalctl -u script-manager-workers -n 50
```

**Queue Backlog:**
```bash
# Check queue length
redis-cli LLEN rq:queue:default

# Clear failed jobs
redis-cli
> LREM rq:queue:failed 0 "*"

# Restart workers to clear stuck jobs
sudo systemctl restart script-manager-workers
```

**SSH Connection Issues:**
```bash
# Test SSH connection manually
ssh -i /path/to/key user@server

# Check SSH key format
head -1 /path/to/key
# Should show: -----BEGIN OPENSSH PRIVATE KEY-----

# Check server credentials in database
psql -h localhost -U script_manager_user -d script_manager
SELECT name, hostname, username, auth_type FROM servers;
```

### 6. Performance Issues

#### Symptoms
- Slow page loads
- High CPU/memory usage
- Timeout errors

#### Diagnosis
```bash
# Check system resources
htop
iostat -x 1
free -h
df -h

# Check database performance
sudo -u postgres psql -d script_manager
EXPLAIN ANALYZE SELECT * FROM script_executions WHERE status = 'running';

# Check Redis performance
redis-cli info stats
```

#### Solutions

**High CPU Usage:**
```bash
# Check running processes
top -p $(pgrep -f "script-manager")

# Optimize database queries
# Add indexes for frequently queried columns
sudo -u postgres psql -d script_manager
CREATE INDEX idx_executions_status ON script_executions(status);
CREATE INDEX idx_executions_created_at ON script_executions(created_at);
```

**High Memory Usage:**
```bash
# Check memory usage by process
ps aux --sort=-%mem | head -10

# Optimize Redis memory
redis-cli CONFIG SET maxmemory 256mb
redis-cli CONFIG SET maxmemory-policy allkeys-lru

# Restart services to clear memory
sudo systemctl restart script-manager-backend script-manager-workers
```

**Slow Database Queries:**
```sql
-- Check slow queries
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;

-- Add missing indexes
CREATE INDEX idx_executions_script_id ON script_executions(script_id);
CREATE INDEX idx_executions_server_id ON script_executions(server_id);
```

### 7. Security Issues

#### Symptoms
- Unauthorized access attempts
- Failed login attempts
- Suspicious activity in logs

#### Diagnosis
```bash
# Check authentication logs
sudo tail -f /var/log/auth.log

# Check application logs for failed logins
sudo journalctl -u script-manager-backend | grep -i "failed\|error\|unauthorized"

# Check database for suspicious activity
psql -h localhost -U script_manager_user -d script_manager
SELECT * FROM audit_logs WHERE action = 'login_failed' ORDER BY created_at DESC LIMIT 10;
```

#### Solutions

**Brute Force Attacks:**
```bash
# Install fail2ban
sudo apt-get install fail2ban

# Configure fail2ban for SSH
sudo nano /etc/fail2ban/jail.local
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
port = ssh
logpath = /var/log/auth.log
maxretry = 3

# Start fail2ban
sudo systemctl start fail2ban
sudo systemctl enable fail2ban
```

**Weak Passwords:**
```bash
# Check user passwords in database
psql -h localhost -U script_manager_user -d script_manager
SELECT username, created_at FROM users;

# Force password reset
# Update user password in application or database
```

**SSL/TLS Issues:**
```bash
# Check SSL certificate
openssl x509 -in /etc/letsencrypt/live/your-domain.com/cert.pem -text -noout

# Renew SSL certificate
sudo certbot renew --dry-run
sudo certbot renew
```

## Advanced Troubleshooting

### Database Recovery

#### Backup and Restore
```bash
# Create backup
pg_dump -h localhost -U script_manager_user script_manager > backup.sql

# Restore from backup
psql -h localhost -U script_manager_user script_manager < backup.sql
```

#### Database Corruption
```bash
# Check database integrity
sudo -u postgres psql -d script_manager -c "VACUUM ANALYZE;"

# Reindex database
sudo -u postgres psql -d script_manager -c "REINDEX DATABASE script_manager;"
```

### Application Recovery

#### Reset Application State
```bash
# Stop all services
sudo systemctl stop script-manager-backend script-manager-workers

# Clear Redis queues
redis-cli FLUSHALL

# Restart services
sudo systemctl start script-manager-backend script-manager-workers
```

#### Rebuild Application
```bash
# Backup current state
cp -r /home/scriptmanager/script-manager /home/scriptmanager/script-manager.backup

# Pull latest changes
cd /home/scriptmanager/script-manager
git pull origin main

# Rebuild backend
cd backend
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head

# Rebuild frontend
cd ../frontend
npm install
npm run build

# Restart services
sudo systemctl restart script-manager-backend script-manager-workers
```

### Monitoring and Alerting

#### Set Up Monitoring
```bash
# Install monitoring tools
sudo apt-get install htop iotop nethogs

# Create monitoring script
nano /home/scriptmanager/monitor.sh
```

```bash
#!/bin/bash
# monitor.sh

# Check services
echo "=== Service Status ==="
systemctl is-active script-manager-backend script-manager-workers postgresql redis

# Check resources
echo "=== Resource Usage ==="
free -h
df -h

# Check database connections
echo "=== Database Connections ==="
psql -h localhost -U script_manager_user -d script_manager -c "SELECT count(*) FROM pg_stat_activity;"

# Check Redis memory
echo "=== Redis Memory ==="
redis-cli info memory | grep used_memory_human
```

#### Set Up Alerts
```bash
# Create alert script
nano /home/scriptmanager/alert.sh
```

```bash
#!/bin/bash
# alert.sh

# Check if services are running
if ! systemctl is-active --quiet script-manager-backend; then
    echo "ALERT: biRun Backend is down!" | mail -s "Service Alert" admin@example.com
fi

if ! systemctl is-active --quiet postgresql; then
    echo "ALERT: PostgreSQL is down!" | mail -s "Service Alert" admin@example.com
fi

# Check disk space
if [ $(df / | awk 'NR==2 {print $5}' | sed 's/%//') -gt 80 ]; then
    echo "ALERT: Disk space is above 80%!" | mail -s "Disk Alert" admin@example.com
fi
```

## Getting Help

### Log Collection
```bash
# Collect all relevant logs
mkdir -p /tmp/script-manager-debug
cd /tmp/script-manager-debug

# System logs
sudo journalctl -u script-manager-backend --no-pager > backend.log
sudo journalctl -u script-manager-workers --no-pager > workers.log
sudo journalctl -u postgresql --no-pager > postgresql.log
sudo journalctl -u redis --no-pager > redis.log

# Application logs
sudo tail -100 /var/log/postgresql/postgresql-14-main.log > postgresql-detail.log
sudo tail -100 /var/log/redis/redis-server.log > redis-detail.log

# System information
uname -a > system-info.txt
free -h >> system-info.txt
df -h >> system-info.txt
ps aux >> system-info.txt

# Create archive
tar -czf script-manager-debug-$(date +%Y%m%d-%H%M%S).tar.gz *.log *.txt
```

### Support Resources
- Check the [User Guide](USER_GUIDE.md) for common usage issues
- Review the [API Documentation](API.md) for integration problems
- Check the [Deployment Guide](DEPLOYMENT.md) for installation issues
- Create an issue in the repository with collected logs
- Contact system administrator for critical issues
