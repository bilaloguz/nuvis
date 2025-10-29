"""
Marketplace API endpoints for browsing and importing scripts
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
from models import MarketplaceScript, Script, User
from schemas import ScriptResponse
from auth import get_current_user
import json

router = APIRouter()

@router.get("/scripts")
def list_marketplace_scripts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List available marketplace scripts"""
    query = db.query(MarketplaceScript)
    
    # Apply filters
    if category:
        query = query.filter(MarketplaceScript.category == category)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (MarketplaceScript.name.ilike(search_term)) |
            (MarketplaceScript.description.ilike(search_term))
        )
    
    # Order by downloads and rating
    scripts = query.order_by(
        MarketplaceScript.downloads.desc(),
        MarketplaceScript.rating.desc(),
        MarketplaceScript.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    total = query.count()
    
    return {
        "scripts": scripts,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.get("/scripts/{script_id}")
def get_marketplace_script(
    script_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific marketplace script"""
    script = db.query(MarketplaceScript).filter(MarketplaceScript.id == script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    
    return script

@router.get("/categories")
def get_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all available categories"""
    categories = db.query(MarketplaceScript.category).filter(
        MarketplaceScript.category.isnot(None)
    ).distinct().all()
    
    return [cat[0] for cat in categories if cat[0]]

@router.post("/scripts/{script_id}/import")
def import_marketplace_script(
    script_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Import a marketplace script to user's scripts"""
    # Get marketplace script
    marketplace_script = db.query(MarketplaceScript).filter(
        MarketplaceScript.id == script_id
    ).first()
    
    if not marketplace_script:
        raise HTTPException(status_code=404, detail="Script not found")
    
    # Check if script with same name already exists
    existing_script = db.query(Script).filter(
        Script.name == marketplace_script.name
    ).first()
    
    if existing_script:
        raise HTTPException(
            status_code=400, 
            detail=f"Script with name '{marketplace_script.name}' already exists"
        )
    
    # Create new script from marketplace script
    new_script = Script(
        name=marketplace_script.name,
        description=marketplace_script.description,
        content=marketplace_script.content,
        script_type=marketplace_script.script_type,
        category=marketplace_script.category,
        parameters=marketplace_script.parameters,
        created_by=current_user.id
    )
    
    db.add(new_script)
    
    # Update download count
    marketplace_script.downloads = (marketplace_script.downloads or 0) + 1
    
    db.commit()
    db.refresh(new_script)
    
    return {
        "message": f"Script '{marketplace_script.name}' imported successfully",
        "script": new_script
    }

@router.post("/populate")
def populate_marketplace(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Populate marketplace with seed scripts (admin only)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can populate marketplace")
    
    # Check if marketplace is already populated
    existing_count = db.query(MarketplaceScript).count()
    if existing_count > 0:
        return {"message": f"Marketplace already has {existing_count} scripts"}
    
    # Seed data - Comprehensive collection of useful scripts
    seed_scripts = [
        # System Monitoring
        {
            "name": "disk-usage-linux",
            "description": "Disk usage summary with largest directories",
            "category": "monitoring",
            "script_type": "shell",
            "content": """set -e
echo "== Disk Usage (df -h) =="
df -h
echo
echo "== Top 10 directories by size (sudo may be required) =="
du -xh / 2>/dev/null | sort -hr | head -n 10""",
            "author": "biRun Team",
            "tags": json.dumps(["disk", "monitoring", "linux"])
        },
        {
            "name": "memory-usage-linux",
            "description": "Memory usage and process information",
            "category": "monitoring",
            "script_type": "shell",
            "content": """set -e
echo "== Memory Usage =="
free -h
echo
echo "== Top Memory Consuming Processes =="
ps aux --sort=-%mem | head -n 10""",
            "author": "biRun Team",
            "tags": json.dumps(["memory", "monitoring", "linux"])
        },
        {
            "name": "cpu-usage-linux",
            "description": "CPU usage and process monitoring",
            "category": "monitoring",
            "script_type": "shell",
            "content": """set -e
echo "== CPU Information =="
lscpu
echo
echo "== Load Average =="
uptime
echo
echo "== Top CPU Consuming Processes =="
ps aux --sort=-%cpu | head -n 10
echo
echo "== CPU Usage (1 second sample) =="
top -bn1 | grep "Cpu(s)""",
            "author": "biRun Team",
            "tags": json.dumps(["cpu", "monitoring", "linux"])
        },
        {
            "name": "network-stats-linux",
            "description": "Network interface statistics and connections",
            "category": "monitoring",
            "script_type": "shell",
            "content": """set -e
echo "== Network Interfaces =="
ip addr show
echo
echo "== Network Statistics =="
ss -tuln
echo
echo "== Active Connections =="
ss -tuln | wc -l
echo "Total connections: $(ss -tuln | wc -l)"
echo
echo "== Network Usage ="
cat /proc/net/dev""",
            "author": "biRun Team",
            "tags": json.dumps(["network", "monitoring", "linux"])
        },
        {
            "name": "system-info-linux",
            "description": "Comprehensive system information",
            "category": "monitoring",
            "script_type": "shell",
            "content": """set -e
echo "== System Information =="
uname -a
echo
echo "== CPU Information =="
lscpu
echo
echo "== Load Average =="
uptime
echo
echo "== Network Interfaces =="
ip addr show
echo
echo "== Mounted Filesystems =="
df -h
echo
echo "== Memory Information =="
free -h""",
            "author": "biRun Team",
            "tags": json.dumps(["system", "info", "linux"])
        },
        
        # Docker & Containers
        {
            "name": "docker-stats",
            "description": "Docker container statistics and status",
            "category": "docker",
            "script_type": "shell",
            "content": """set -e
echo "== Docker Containers =="
docker ps -a
echo
echo "== Docker Stats =="
docker stats --no-stream --format "table {{.Container}}\\t{{.CPUPerc}}\\t{{.MemUsage}}\\t{{.NetIO}}\\t{{.BlockIO}}"
echo
echo "== Docker Images =="
docker images""",
            "author": "biRun Team",
            "tags": json.dumps(["docker", "containers", "monitoring"])
        },
        {
            "name": "docker-cleanup",
            "description": "Clean up unused Docker resources",
            "category": "docker",
            "script_type": "shell",
            "content": """set -e
echo "== Docker Cleanup =="
echo "Removing stopped containers..."
docker container prune -f
echo
echo "Removing unused images..."
docker image prune -f
echo
echo "Removing unused volumes..."
docker volume prune -f
echo
echo "Removing unused networks..."
docker network prune -f
echo
echo "Docker cleanup completed!""",
            "author": "biRun Team",
            "tags": json.dumps(["docker", "cleanup", "maintenance"])
        },
        {
            "name": "docker-logs",
            "description": "View Docker container logs with filtering",
            "category": "docker",
            "script_type": "shell",
            "content": """set -e
echo "== Docker Container Logs =="
echo "Available containers:"
docker ps --format "table {{.Names}}\\t{{.Status}}"
echo
echo "Enter container name to view logs (or press Enter for all):"
read -r container_name
if [ -z "$container_name" ]; then
    echo "Showing logs for all containers..."
    docker logs --tail=50 $(docker ps -q) 2>/dev/null || echo "No running containers"
else
    echo "Showing logs for $container_name..."
    docker logs --tail=50 "$container_name" 2>/dev/null || echo "Container not found or no logs"
fi""",
            "author": "biRun Team",
            "tags": json.dumps(["docker", "logs", "debugging"])
        },
        
        # File Operations
        {
            "name": "find-large-files",
            "description": "Find largest files on the system",
            "category": "files",
            "script_type": "shell",
            "content": """set -e
echo "== Finding Large Files =="
echo "Files larger than 100MB:"
find / -type f -size +100M 2>/dev/null | head -20
echo
echo "Files larger than 1GB:"
find / -type f -size +1G 2>/dev/null | head -10
echo
echo "Top 20 largest files:"
find / -type f -exec du -h {} + 2>/dev/null | sort -hr | head -20""",
            "author": "biRun Team",
            "tags": json.dumps(["files", "disk", "search"])
        },
        {
            "name": "backup-important-files",
            "description": "Backup important configuration files",
            "category": "backup",
            "script_type": "shell",
            "content": """set -e
BACKUP_DIR="/tmp/backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "== Creating Backup in $BACKUP_DIR =="

# Backup important config files
echo "Backing up configuration files..."
cp -r /etc "$BACKUP_DIR/" 2>/dev/null || echo "Could not backup /etc"
cp -r ~/.ssh "$BACKUP_DIR/" 2>/dev/null || echo "Could not backup ~/.ssh"
cp -r ~/.bashrc "$BACKUP_DIR/" 2>/dev/null || echo "Could not backup ~/.bashrc"

# Backup home directory structure (without large files)
echo "Backing up home directory structure..."
find ~ -maxdepth 2 -type d -exec mkdir -p "$BACKUP_DIR/home/{}" \\; 2>/dev/null || true

echo "Backup completed: $BACKUP_DIR"
ls -la "$BACKUP_DIR" """,
            "author": "biRun Team",
            "tags": json.dumps(["backup", "config", "files"])
        },
        {
            "name": "file-permissions-fix",
            "description": "Fix common file permission issues",
            "category": "maintenance",
            "script_type": "shell",
            "content": """set -e
echo "== File Permissions Fix =="
echo "Fixing home directory permissions..."
chmod 755 ~
echo
echo "Fixing SSH directory permissions..."
chmod 700 ~/.ssh 2>/dev/null || echo "No .ssh directory"
chmod 600 ~/.ssh/id_* 2>/dev/null || echo "No SSH keys found"
chmod 644 ~/.ssh/known_hosts 2>/dev/null || echo "No known_hosts file"
echo
echo "Fixing script permissions..."
find ~ -name "*.sh" -exec chmod +x {} \\; 2>/dev/null || echo "No shell scripts found"
echo
echo "Permission fixes completed!""",
            "author": "biRun Team",
            "tags": json.dumps(["permissions", "security", "maintenance"])
        },
        
        # System Maintenance
        {
            "name": "log-cleanup",
            "description": "Clean up old log files to free space",
            "category": "maintenance",
            "script_type": "shell",
            "content": """set -e
echo "== Log Cleanup Script =="
echo "Cleaning logs older than 30 days..."

# Clean system logs
sudo find /var/log -name "*.log" -type f -mtime +30 -delete 2>/dev/null || true
sudo find /var/log -name "*.gz" -type f -mtime +30 -delete 2>/dev/null || true

# Clean journal logs
sudo journalctl --vacuum-time=30d 2>/dev/null || true

echo "Log cleanup completed!""",
            "author": "biRun Team",
            "tags": json.dumps(["logs", "cleanup", "maintenance"])
        },
        {
            "name": "system-update",
            "description": "Update system packages safely",
            "category": "maintenance",
            "script_type": "shell",
            "content": """set -e
echo "== System Update =="
echo "Updating package lists..."
sudo apt update
echo
echo "Upgrading packages..."
sudo apt upgrade -y
echo
echo "Cleaning up..."
sudo apt autoremove -y
sudo apt autoclean
echo
echo "System update completed!""",
            "author": "biRun Team",
            "tags": json.dumps(["update", "packages", "maintenance"])
        },
        {
            "name": "service-status",
            "description": "Check status of important system services",
            "category": "monitoring",
            "script_type": "shell",
            "content": """set -e
echo "== Service Status Check =="
services=("ssh" "docker" "nginx" "apache2" "mysql" "postgresql" "redis" "cron")
for service in "${services[@]}"; do
    if systemctl is-active --quiet "$service" 2>/dev/null; then
        echo "✓ $service: RUNNING"
    elif systemctl is-enabled --quiet "$service" 2>/dev/null; then
        echo "✗ $service: STOPPED (but enabled)"
    else
        echo "- $service: NOT INSTALLED"
    fi
done
echo
echo "== Failed Services =="
systemctl --failed --no-pager""",
            "author": "biRun Team",
            "tags": json.dumps(["services", "monitoring", "system"])
        },
        
        # Security
        {
            "name": "security-scan",
            "description": "Basic security scan and checks",
            "category": "security",
            "script_type": "shell",
            "content": """set -e
echo "== Security Scan =="
echo "Checking for failed login attempts..."
sudo grep "Failed password" /var/log/auth.log 2>/dev/null | tail -10 || echo "No failed logins found"
echo
echo "Checking for root login attempts..."
sudo grep "root" /var/log/auth.log 2>/dev/null | tail -5 || echo "No root logins found"
echo
echo "Checking open ports..."
ss -tuln | grep LISTEN
echo
echo "Checking for SUID files..."
find / -perm -4000 2>/dev/null | head -10
echo
echo "Security scan completed!""",
            "author": "biRun Team",
            "tags": json.dumps(["security", "scan", "audit"])
        },
        {
            "name": "firewall-status",
            "description": "Check firewall status and rules",
            "category": "security",
            "script_type": "shell",
            "content": """set -e
echo "== Firewall Status =="
if command -v ufw >/dev/null 2>&1; then
    echo "UFW Status:"
    sudo ufw status verbose
elif command -v iptables >/dev/null 2>&1; then
    echo "iptables Status:"
    sudo iptables -L -n
else
    echo "No firewall found (ufw or iptables)"
fi
echo
echo "== Open Ports =="
ss -tuln | grep LISTEN""",
            "author": "biRun Team",
            "tags": json.dumps(["firewall", "security", "network"])
        },
        {
            "name": "ssl-cert-check",
            "description": "Check SSL certificate expiry for domains",
            "category": "security",
            "script_type": "shell",
            "content": """#!/bin/bash
# Usage: ./ssl-cert-check.sh domain.com
DOMAIN=${1:-"example.com"}
echo "Checking SSL certificate for: $DOMAIN"
echo | openssl s_client -servername $DOMAIN -connect $DOMAIN:443 2>/dev/null | openssl x509 -noout -dates""",
            "author": "biRun Team",
            "tags": json.dumps(["ssl", "security", "certificates"])
        },
        
        # Database
        {
            "name": "postgres-status",
            "description": "PostgreSQL database status and info",
            "category": "database",
            "script_type": "shell",
            "content": """set -e
echo "== PostgreSQL Status =="
if systemctl is-active --quiet postgresql; then
    echo "✓ PostgreSQL is running"
    echo
    echo "== Database Sizes =="
    sudo -u postgres psql -c "SELECT datname, pg_size_pretty(pg_database_size(datname)) as size FROM pg_database ORDER BY pg_database_size(datname) DESC;"
    echo
    echo "== Active Connections =="
    sudo -u postgres psql -c "SELECT count(*) as active_connections FROM pg_stat_activity WHERE state = 'active';"
else
    echo "✗ PostgreSQL is not running"
fi""",
            "author": "biRun Team",
            "tags": json.dumps(["postgresql", "database", "monitoring"])
        },
        {
            "name": "mysql-status",
            "description": "MySQL database status and info",
            "category": "database",
            "script_type": "shell",
            "content": """set -e
echo "== MySQL Status =="
if systemctl is-active --quiet mysql; then
    echo "✓ MySQL is running"
    echo
    echo "== Database Sizes =="
    mysql -e "SELECT table_schema AS 'Database', ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS 'Size (MB)' FROM information_schema.tables GROUP BY table_schema ORDER BY SUM(data_length + index_length) DESC;"
    echo
    echo "== Process List =="
    mysql -e "SHOW PROCESSLIST;"
else
    echo "✗ MySQL is not running"
fi""",
            "author": "biRun Team",
            "tags": json.dumps(["mysql", "database", "monitoring"])
        },
        
        # Web Server
        {
            "name": "nginx-status",
            "description": "Nginx web server status and configuration",
            "category": "web",
            "script_type": "shell",
            "content": """set -e
echo "== Nginx Status =="
if systemctl is-active --quiet nginx; then
    echo "✓ Nginx is running"
    echo
    echo "== Configuration Test =="
    sudo nginx -t
    echo
    echo "== Active Sites =="
    sudo nginx -T 2>/dev/null | grep -E "server_name|listen" | head -10
    echo
    echo "== Access Logs (last 10 lines) =="
    sudo tail -10 /var/log/nginx/access.log 2>/dev/null || echo "No access logs found"
else
    echo "✗ Nginx is not running"
fi""",
            "author": "biRun Team",
            "tags": json.dumps(["nginx", "web", "monitoring"])
        },
        {
            "name": "apache-status",
            "description": "Apache web server status and configuration",
            "category": "web",
            "script_type": "shell",
            "content": """set -e
echo "== Apache Status =="
if systemctl is-active --quiet apache2; then
    echo "✓ Apache is running"
    echo
    echo "== Configuration Test =="
    sudo apache2ctl configtest
    echo
    echo "== Enabled Sites =="
    sudo a2ensite --list 2>/dev/null || echo "No sites enabled"
    echo
    echo "== Access Logs (last 10 lines) =="
    sudo tail -10 /var/log/apache2/access.log 2>/dev/null || echo "No access logs found"
else
    echo "✗ Apache is not running"
fi""",
            "author": "biRun Team",
            "tags": json.dumps(["apache", "web", "monitoring"])
        },
        
        # Development
        {
            "name": "git-status-all",
            "description": "Check git status for all repositories in a directory",
            "category": "development",
            "script_type": "shell",
            "content": """set -e
echo "== Git Status Check =="
if [ -z "$1" ]; then
    SEARCH_DIR="."
else
    SEARCH_DIR="$1"
fi

echo "Searching for git repositories in: $SEARCH_DIR"
echo

find "$SEARCH_DIR" -name ".git" -type d 2>/dev/null | while read -r gitdir; do
    repo_dir=$(dirname "$gitdir")
    echo "=== Repository: $repo_dir ==="
    cd "$repo_dir"
    
    # Check if there are changes
    if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
        echo "Status: HAS CHANGES"
        git status --short
    else
        echo "Status: Clean"
    fi
    
    # Check if behind/ahead
    git fetch --quiet 2>/dev/null || true
    behind=$(git rev-list --count HEAD..@{u} 2>/dev/null || echo "0")
    ahead=$(git rev-list --count @{u}..HEAD 2>/dev/null || echo "0")
    
    if [ "$behind" -gt 0 ] || [ "$ahead" -gt 0 ]; then
        echo "Branch status: $ahead ahead, $behind behind"
    else
        echo "Branch status: Up to date"
    fi
    
    echo
done""",
            "author": "biRun Team",
            "tags": json.dumps(["git", "development", "repositories"])
        },
        {
            "name": "python-env-check",
            "description": "Check Python environment and installed packages",
            "category": "development",
            "script_type": "shell",
            "content": """set -e
echo "== Python Environment Check =="
echo "Python version:"
python3 --version
echo
echo "Pip version:"
pip3 --version
echo
echo "Virtual environment:"
if [ -n "$VIRTUAL_ENV" ]; then
    echo "✓ Virtual environment active: $VIRTUAL_ENV"
else
    echo "✗ No virtual environment active"
fi
echo
echo "Installed packages (top 20):"
pip3 list | head -20
echo
echo "Outdated packages:"
pip3 list --outdated 2>/dev/null || echo "No outdated packages found" """,
            "author": "biRun Team",
            "tags": json.dumps(["python", "development", "packages"])
        },
        
        # Utilities
        {
            "name": "weather-check",
            "description": "Check weather using wttr.in service",
            "category": "utilities",
            "script_type": "shell",
            "content": """set -e
echo "== Weather Check =="
if command -v curl >/dev/null 2>&1; then
    echo "Current weather:"
    curl -s "wttr.in?format=3" || echo "Weather service unavailable"
    echo
    echo "Detailed forecast:"
    curl -s "wttr.in?format=1" || echo "Weather service unavailable"
else
    echo "curl not available for weather check"
fi""",
            "author": "biRun Team",
            "tags": json.dumps(["weather", "utilities", "external"])
        },
        {
            "name": "system-health-check",
            "description": "Comprehensive system health check",
            "category": "monitoring",
            "script_type": "shell",
            "content": """set -e
echo "== System Health Check =="
echo "Timestamp: $(date)"
echo

echo "=== Uptime ==="
uptime
echo

echo "=== Memory Usage ==="
free -h
echo

echo "=== Disk Usage ==="
df -h
echo

echo "=== Load Average ==="
cat /proc/loadavg
echo

echo "=== CPU Usage ==="
top -bn1 | grep "Cpu(s)"
echo

echo "=== Network Status ==="
ss -tuln | wc -l
echo "Active connections: $(ss -tuln | wc -l)"
echo

echo "=== Service Status ==="
systemctl --failed --no-pager | head -5
echo

echo "=== Recent Errors ==="
sudo journalctl --since "1 hour ago" --priority=err --no-pager | head -5
echo

echo "Health check completed!""",
            "author": "biRun Team",
            "tags": json.dumps(["health", "monitoring", "system"])
        },
        {
            "name": "top-processes-linux",
            "description": "Top CPU and memory processes",
            "category": "monitoring",
            "script_type": "shell",
            "content": """echo "== Top CPU =="
ps -eo pid,comm,%cpu,%mem --sort=-%cpu | head -n 15
echo
echo "== Top Memory =="
ps -eo pid,comm,%mem,%cpu --sort=-%mem | head -n 15""",
            "author": "biRun Team",
            "tags": json.dumps(["processes", "monitoring", "linux"])
        },
        {
            "name": "network-connections-linux",
            "description": "Active network connections and bandwidth usage",
            "category": "monitoring",
            "script_type": "shell",
            "content": """echo "== Active Connections =="
ss -tuln
echo
echo "== Network Statistics =="
cat /proc/net/dev
echo
echo "== Established TCP Connections =="
ss -tuln | grep ESTAB""",
            "author": "biRun Team",
            "tags": json.dumps(["network", "connections", "linux"])
        }
    ]
    
    created = 0
    for script_data in seed_scripts:
        script = MarketplaceScript(**script_data)
        db.add(script)
        created += 1
    
    db.commit()
    
    return {"message": f"Marketplace populated with {created} scripts"}