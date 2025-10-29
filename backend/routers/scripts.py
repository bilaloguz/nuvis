from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
from database import get_db
from models import Script, ScriptExecution, User, Server, ServerGroup, WorkflowNode, Settings
from schemas import (
    ScriptResponse, ScriptCreate, ScriptUpdate, ScriptListResponse,
    ScriptExecutionResponse, ScriptExecutionCreate, ScriptExecutionListResponse, SettingsResponse
)
from auth import get_current_user
from audit_logger import AuditLogger, AuditActions
from audit_utils import log_audit
from sqlalchemy import func
import os
import paramiko
import io
import time
import io
import csv
from datetime import datetime, timezone
from secrets_vault import SecretsVault
from auth_logger import auth_logger
from ssh_key_utils import detect_key_type_from_file, get_paramiko_key_class
from rq_queue import get_queue
from tasks import execute_script_job
from utils_logging import get_logger, kv
from rq.job import Job
from rq_queue import get_redis
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError, OperationalError

router = APIRouter()

@router.post("/", response_model=ScriptResponse)
def create_script(
    script_create: ScriptCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can create scripts
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create scripts"
        )
    
    # Check if script name already exists
    existing_script = db.query(Script).filter(Script.name == script_create.name).first()
    if existing_script:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Script name already exists"
        )
    
    # Create new script
    new_script = Script(
        name=script_create.name,
        description=script_create.description,
        content=script_create.content,
        script_type=script_create.script_type,
        category=script_create.category,
        parameters=script_create.parameters,
        created_by=current_user.id
    )

    # Optional execution settings
    if script_create.concurrency_limit is not None:
        new_script.concurrency_limit = script_create.concurrency_limit
    if script_create.continue_on_error is not None:
        new_script.continue_on_error = 1 if script_create.continue_on_error else 0
    if script_create.per_server_timeout_seconds is not None:
        new_script.per_server_timeout_seconds = script_create.per_server_timeout_seconds
    
    db.add(new_script)
    db.commit()
    db.refresh(new_script)
    
    # Log script creation
    AuditLogger.log_user_action(
        db=db,
        user=current_user,
        action=AuditActions.SCRIPT_CREATE,
        resource_type="script",
        resource_id=new_script.id,
        details={
            "script_name": new_script.name,
            "script_type": new_script.script_type,
            "category": new_script.category,
            "has_parameters": bool(new_script.parameters)
        },
        success=True
    )
    
    return new_script

@router.post("/marketplace/import", response_model=None)
def import_marketplace(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can import marketplace scripts")
    created = 0
    for s in _MARKETPLACE_SEEDS:
        if db.query(Script).filter(Script.name == s["name"]).first():
            continue
        sc = Script(
            name=s["name"],
            description=s.get("description"),
            category=s.get("category"),
            content=s["content"],
            script_type=s.get("script_type", "shell"),
            parameters=s.get("parameters"),
            created_by=current_user.id,
        )
        db.add(sc)
        created += 1
    db.commit()
    return {"imported": created}

# Extended marketplace seed set
_MARKETPLACE_SEEDS = [
    # Linux System Monitoring
    {
        "name": "disk-usage-linux",
        "description": "Disk usage summary with largest directories",
        "category": "linux",
        "script_type": "shell",
        "content": """
set -e
echo "== Disk Usage (df -h) =="
df -h
echo
echo "== Top 10 directories by size (sudo may be required) =="
du -xh / 2>/dev/null | sort -hr | head -n 10
""".strip(),
    },
    {
        "name": "top-processes-linux",
        "description": "Top CPU and memory processes",
        "category": "linux",
        "script_type": "shell",
        "content": """
echo "== Top CPU =="
ps -eo pid,comm,%cpu,%mem --sort=-%cpu | head -n 15
echo
echo "== Top Memory =="
ps -eo pid,comm,%mem,%cpu --sort=-%mem | head -n 15
""".strip(),
    },
    {
        "name": "ports-linux",
        "description": "Listening ports (ss)",
        "category": "linux",
        "script_type": "shell",
        "content": "ss -tulpn | sed 's/\t/ /g'",
    },
    {
        "name": "journal-errors-linux",
        "description": "Recent system errors from journalctl",
        "category": "linux",
        "script_type": "shell",
        "content": "journalctl -p 3 -xn || true",
    },
    {
        "name": "find-large-files-linux",
        "description": ">1G files under /",
        "category": "linux",
        "script_type": "shell",
        "content": "find / -type f -size +1G -printf '%s %p\n' 2>/dev/null | sort -nr | head -n 30",
    },
    
    # Network & Security
    {
        "name": "network-connections-linux",
        "description": "Active network connections and bandwidth usage",
        "category": "network",
        "script_type": "shell",
        "content": """
echo "== Active Connections =="
ss -tuln
echo
echo "== Network Statistics =="
cat /proc/net/dev
echo
echo "== Established TCP Connections =="
ss -tuln | grep ESTAB
""".strip(),
    },
    {
        "name": "firewall-status-linux",
        "description": "Check iptables/firewalld status",
        "category": "security",
        "script_type": "shell",
        "content": """
echo "== iptables rules =="
iptables -L -n -v || echo "iptables not available"
echo
echo "== firewalld status =="
systemctl is-active firewalld && firewall-cmd --list-all || echo "firewalld not active"
echo
echo "== ufw status =="
ufw status || echo "ufw not available"
""".strip(),
    },
    {
        "name": "ssl-cert-check",
        "description": "Check SSL certificate expiry for domains",
        "category": "security",
        "script_type": "shell",
        "content": """
#!/bin/bash
# Usage: ./ssl-cert-check.sh domain.com
DOMAIN=${1:-"example.com"}
echo "Checking SSL certificate for: $DOMAIN"
echo | openssl s_client -servername $DOMAIN -connect $DOMAIN:443 2>/dev/null | openssl x509 -noout -dates
""".strip(),
    },
    
    # Docker & Containers
    {
        "name": "docker-stats",
        "description": "Docker container statistics and resource usage",
        "category": "docker",
        "script_type": "shell",
        "content": """
echo "== Docker System Info =="
docker system df
echo
echo "== Running Containers =="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo
echo "== Container Resource Usage =="
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
""".strip(),
    },
    {
        "name": "docker-logs-errors",
        "description": "Check Docker container logs for errors",
        "category": "docker",
        "script_type": "shell",
        "content": """
echo "== Recent Docker Logs (last 50 lines) =="
docker ps -q | while read container; do
    echo "=== Container: $container ==="
    docker logs --tail 50 $container 2>&1 | grep -i error || echo "No errors found"
done
""".strip(),
    },
    
    # Database & Services
    {
        "name": "mysql-status",
        "description": "MySQL/MariaDB status and connections",
        "category": "database",
        "script_type": "shell",
        "content": """
echo "== MySQL Status =="
mysql -e "SHOW STATUS LIKE 'Connections';" 2>/dev/null || echo "MySQL not accessible"
echo
echo "== MySQL Process List =="
mysql -e "SHOW PROCESSLIST;" 2>/dev/null || echo "MySQL not accessible"
""".strip(),
    },
    {
        "name": "postgres-status",
        "description": "PostgreSQL status and connections",
        "category": "database",
        "script_type": "shell",
        "content": """
echo "== PostgreSQL Status =="
psql -c "SELECT count(*) as active_connections FROM pg_stat_activity;" 2>/dev/null || echo "PostgreSQL not accessible"
echo
echo "== PostgreSQL Locks =="
psql -c "SELECT * FROM pg_locks WHERE NOT granted;" 2>/dev/null || echo "PostgreSQL not accessible"
""".strip(),
    },
    
    # Windows System Monitoring
    {
        "name": "disk-usage-windows",
        "description": "Disk usage per drive",
        "category": "windows",
        "script_type": "powershell",
        "content": "Get-PSDrive -PSProvider FileSystem | Select-Object Name,Used,Free,@{Name='UsedGB';Expression={[math]::Round($_.Used/1GB,2)}},@{Name='FreeGB';Expression={[math]::Round($_.Free/1GB,2)}} | Format-Table -AutoSize",
    },
    {
        "name": "top-processes-windows",
        "description": "Top processes by CPU and WorkingSet",
        "category": "windows",
        "script_type": "powershell",
        "content": "Get-Process | Sort-Object CPU -Descending | Select-Object -First 15 Name,Id,CPU,WorkingSet | Format-Table -AutoSize",
    },
    {
        "name": "open-ports-windows",
        "description": "Open TCP connections",
        "category": "windows",
        "script_type": "powershell",
        "content": "Get-NetTCPConnection | Where-Object {$_.State -eq 'Listen'} | Select-Object LocalAddress,LocalPort,OwningProcess | Sort-Object LocalPort | Format-Table -AutoSize",
    },
    {
        "name": "windows-services",
        "description": "Windows services status and startup type",
        "category": "windows",
        "script_type": "powershell",
        "content": "Get-Service | Where-Object {$_.Status -ne 'Running'} | Select-Object Name,Status,StartType | Format-Table -AutoSize",
    },
    {
        "name": "windows-event-logs",
        "description": "Recent Windows event log errors",
        "category": "windows",
        "script_type": "powershell",
        "content": "Get-WinEvent -FilterHashtable @{LogName='System','Application'; Level=2,3} -MaxEvents 20 | Select-Object TimeCreated,Id,LevelDisplayName,Message | Format-Table -Wrap",
    },
    
    # Log Analysis
    {
        "name": "nginx-logs-analysis",
        "description": "Analyze Nginx access and error logs",
        "category": "logs",
        "script_type": "shell",
        "content": """
echo "== Top IPs by requests =="
awk '{print $1}' /var/log/nginx/access.log | sort | uniq -c | sort -nr | head -10
echo
echo "== Top requested URLs =="
awk '{print $7}' /var/log/nginx/access.log | sort | uniq -c | sort -nr | head -10
echo
echo "== Recent 404 errors =="
grep " 404 " /var/log/nginx/access.log | tail -10
""".strip(),
    },
    {
        "name": "apache-logs-analysis",
        "description": "Analyze Apache access and error logs",
        "category": "logs",
        "script_type": "shell",
        "content": """
echo "== Top IPs by requests =="
awk '{print $1}' /var/log/apache2/access.log | sort | uniq -c | sort -nr | head -10
echo
echo "== Top requested URLs =="
awk '{print $7}' /var/log/apache2/access.log | sort | uniq -c | sort -nr | head -10
echo
echo "== Recent errors =="
tail -20 /var/log/apache2/error.log
""".strip(),
    },
    
    # System Maintenance
    {
        "name": "cleanup-temp-files",
        "description": "Clean temporary files and logs",
        "category": "maintenance",
        "script_type": "shell",
        "content": """
echo "== Cleaning /tmp =="
find /tmp -type f -atime +7 -delete 2>/dev/null || true
echo "== Cleaning old logs =="
find /var/log -name "*.log" -type f -mtime +30 -delete 2>/dev/null || true
echo "== Cleaning package cache =="
apt-get clean 2>/dev/null || yum clean all 2>/dev/null || true
echo "Cleanup completed"
""".strip(),
    },
    {
        "name": "system-updates-check",
        "description": "Check for available system updates",
        "category": "maintenance",
        "script_type": "shell",
        "content": """
echo "== Checking for updates =="
if command -v apt &> /dev/null; then
    apt list --upgradable 2>/dev/null | grep -v "Listing..."
elif command -v yum &> /dev/null; then
    yum check-update 2>/dev/null || echo "No updates available"
elif command -v dnf &> /dev/null; then
    dnf check-update 2>/dev/null || echo "No updates available"
else
    echo "Package manager not recognized"
fi
""".strip(),
    },
]

@router.get("/", response_model=ScriptListResponse)
def get_scripts(
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=10000),
    category: str = Query(None, description="Filter by category"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can list scripts
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can list scripts"
        )
    
    query = db.query(Script).options(joinedload(Script.creator))
    
    # Apply category filter if provided
    if category:
        query = query.filter(Script.category == category)
    
    scripts = query.offset(skip).limit(limit).all()
    total = query.count()
    
    return ScriptListResponse(scripts=scripts, total=total)

@router.get("/{script_id}", response_model=ScriptResponse)
def get_script(
    script_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can view script details
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view script details"
        )
    
    script = db.query(Script).options(
        joinedload(Script.creator)
    ).filter(Script.id == script_id).first()
    
    if script is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Script not found"
        )
    
    return script

@router.put("/{script_id}", response_model=ScriptResponse)
def update_script(
    script_id: int,
    script_update: ScriptUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can update scripts
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update scripts"
        )
    
    script = db.query(Script).filter(Script.id == script_id).first()
    if script is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Script not found"
        )
    
    # Check if name is being changed and if it already exists
    if script_update.name and script_update.name != script.name:
        existing_script = db.query(Script).filter(Script.name == script_update.name).first()
        if existing_script:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Script name already exists"
            )
    
    # Update fields
    if script_update.name is not None:
        script.name = script_update.name
    if script_update.description is not None:
        script.description = script_update.description
    if script_update.content is not None:
        script.content = script_update.content
    if script_update.script_type is not None:
        script.script_type = script_update.script_type
    if script_update.category is not None:
        script.category = script_update.category
    if script_update.parameters is not None:
        script.parameters = script_update.parameters
    # Execution settings
    if script_update.concurrency_limit is not None:
        script.concurrency_limit = script_update.concurrency_limit
    if script_update.continue_on_error is not None:
        script.continue_on_error = 1 if script_update.continue_on_error else 0
    if script_update.per_server_timeout_seconds is not None:
        script.per_server_timeout_seconds = script_update.per_server_timeout_seconds
    
    db.commit()
    db.refresh(script)
    return script

@router.delete("/{script_id}")
def delete_script(
    script_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can delete scripts
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete scripts"
        )
    
    script = db.query(Script).filter(Script.id == script_id).first()
    if script is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Script not found"
        )
    
    # Note: We allow script deletion even if it has past executions
    # The execution history is preserved for audit purposes
    
    # Log the deletion for audit purposes
    log_audit(db, action="script_delete", resource_type="script", resource_id=script.id, user_id=current_user.id, details={"name": script.name})
    
    # Set foreign key references to NULL to preserve execution history and workflow nodes
    # but allow script deletion
    db.query(ScriptExecution).filter(ScriptExecution.script_id == script_id).update({"script_id": None})
    db.query(WorkflowNode).filter(WorkflowNode.script_id == script_id).update({"script_id": None})
    
    # Delete the script
    db.delete(script)
    db.commit()
    
    return {"message": "Script deleted successfully"}

# Script Execution endpoints
@router.post("/executions/{execution_id}/stop")
def stop_script_execution(
    execution_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Stop a running script execution
    """
    # Only admins can stop script executions
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can stop script executions"
        )
    
    # Get the execution
    execution = db.query(ScriptExecution).filter(ScriptExecution.id == execution_id).first()
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )
    
    # Check if it's still running
    if execution.status not in ["running", "long_running"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Execution is not running (status: {execution.status})"
        )
    
    # Mark as cancelled
    execution.status = "cancelled"
    execution.completed_at = datetime.now(timezone.utc)
    db.commit()
    
    return {"message": "Script execution stopped successfully"}

@router.get("/executions/by-id/{execution_id}")
def get_script_execution(
    execution_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can view script executions
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view script executions"
        )

    ex = db.query(ScriptExecution).options(
        joinedload(ScriptExecution.script, innerjoin=False),
        joinedload(ScriptExecution.server, innerjoin=False),
        joinedload(ScriptExecution.executor, innerjoin=False)
    ).filter(ScriptExecution.id == execution_id).first()

    if not ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")

    item = {
        "id": ex.id,
        "script_id": ex.script_id,
        "server_id": ex.server_id,
        "executed_by": ex.executed_by,
        "status": ex.status,
        "output": ex.output,
        "error": ex.error,
        "started_at": ex.started_at,
        "completed_at": ex.completed_at,
        "parameters_used": ex.parameters_used,
    }
    if getattr(ex, "script", None):
        item["script"] = {"id": ex.script.id, "name": ex.script.name}
    if getattr(ex, "server", None):
        item["server"] = {"id": ex.server.id, "name": ex.server.name, "timezone": getattr(ex.server, 'timezone', 'UTC')}
    if getattr(ex, "executor", None):
        item["executor"] = {"id": ex.executor.id, "username": ex.executor.username}
    return item
@router.post("/{script_id}/execute", response_model=ScriptExecutionResponse)
def execute_script(
    script_id: int,
    execution_create: ScriptExecutionCreate,
    timeout_seconds: int | None = Query(None, ge=0, le=3600, description="Override per-server timeout (0 = no timeout, default script or 60)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can execute scripts
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can execute scripts"
        )
    
    # Verify script exists
    script = db.query(Script).filter(Script.id == script_id).first()
    if script is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Script not found"
        )
    
    # Verify server exists
    server = db.query(Server).filter(Server.id == execution_create.server_id).first()
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    # Check if this is an infinite script
    is_infinite = (timeout_seconds == 0) or (timeout_seconds is None and script.per_server_timeout_seconds == 0)
    
    # Get virtual timeout duration from settings for infinite scripts
    from sqlalchemy.exc import OperationalError
    settings = db.query(Settings).first()
    if not settings:
        settings = Settings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    virtual_timeout_duration = settings.virtual_timeout_duration or 60
    
    # Create execution record
    execution = ScriptExecution(
        script_id=script_id,
        server_id=execution_create.server_id,
        executed_by=current_user.id,
        parameters_used=execution_create.parameters_used,
        status="running"
    )
    try:
        execution.id = None
    except Exception:
        pass
    
    db.add(execution)
    db.commit()
    db.refresh(execution)
    
    # Start background task to mark as long_running after a configurable delay
    import threading
    # Read configurable delay from settings if available; default to 300s
    try:
        long_running_delay_seconds = getattr(settings, 'long_running_delay_seconds', 300) or 300
    except Exception:
        long_running_delay_seconds = 300

    def mark_long_running(execution_id: int):
        time.sleep(long_running_delay_seconds)
        try:
            # Check if still running
            from database import SessionLocal
            db_session = SessionLocal()
            exec_check = db_session.query(ScriptExecution).filter(ScriptExecution.id == execution_id).first()
            if exec_check and exec_check.status == "running":
                exec_check.status = "long_running"
                db_session.commit()
                print(f"Marked execution {execution_id} as long_running after {long_running_delay_seconds}s")
        except Exception as e:
            print(f"Error marking execution as long_running: {e}")
        finally:
            if 'db_session' in locals():
                db_session.close()
    
    long_running_thread = threading.Thread(target=mark_long_running, args=(execution.id,), daemon=True)
    long_running_thread.start()
    
    # Execute over SSH using the robust SSH connection manager
    try:
        from ssh_script_executor import execute_script_on_server
        from ssh_manager import SSHConnectionError
        
        # Log successful authentication attempt
        auth_logger.log_script_execution_auth(
            script_name=script.name,
            server_name=server.name,
            server_ip=server.ip,
            auth_method_used="ssh_manager",
            success=True,
            details={"user_id": current_user.id}
        )
        
        # Execute the script
        out, err, exit_code = execute_script_on_server(
            script=script,
            server=server,
            execution=execution,
            is_infinite=is_infinite,
            virtual_timeout_duration=virtual_timeout_duration
        )
        
        # Handle script execution results
        if is_infinite:
            # For infinite scripts, keep status as "running" and don't set completed_at
            execution.status = "running"
            execution.output = out
            execution.error = None  # No error for infinite scripts
            # Don't set completed_at - let it stay None
        else:
            # Regular script
            execution.status = "completed" if exit_code == 0 else "failed"
            execution.output = out
            execution.error = err if exit_code != 0 else None
            execution.completed_at = func.now()

        db.commit()
        db.refresh(execution)
        return execution
        
    except SSHConnectionError as e:
        print(f"SSH connection failed for {server.name}: {e}")
        
        # Log failed authentication
        auth_logger.log_script_execution_auth(
            script_name=script.name,
            server_name=server.name,
            server_ip=server.ip,
            auth_method_used="ssh_manager",
            success=False,
            details={"error": str(e), "user_id": current_user.id}
        )
        
        execution.status = "failed"
        execution.error = f"SSH connection failed: {e}"
        execution.completed_at = func.now()
        db.commit()
        db.refresh(execution)
        return execution

@router.get("/executions/", response_model=ScriptExecutionListResponse)
def get_script_executions(
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=10000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can view script executions
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view script executions"
        )
    
    executions = db.query(ScriptExecution).options(
        joinedload(ScriptExecution.script, innerjoin=False),
        joinedload(ScriptExecution.server, innerjoin=False),
        joinedload(ScriptExecution.executor, innerjoin=False)
    ).order_by(ScriptExecution.id.desc()).offset(skip).limit(limit).all()
    
    total = db.query(ScriptExecution).count()
    
    # Serialize manually to include server/script names and server groups
    items = []
    for ex in executions:
        item = {
            "id": ex.id,
            "script_id": ex.script_id,
            "server_id": ex.server_id,
            "executed_by": ex.executed_by,
            "status": ex.status,
            "output": ex.output,
            "error": ex.error,
            "started_at": ex.started_at,
            "completed_at": ex.completed_at,
            "parameters_used": ex.parameters_used,
        }
        if getattr(ex, "script", None):
            item["script"] = {"id": ex.script.id, "name": ex.script.name}
        if getattr(ex, "server", None):
            item["server"] = {"id": ex.server.id, "name": ex.server.name, "timezone": getattr(ex.server, 'timezone', 'UTC')}
            # Get server groups separately to avoid complex joins
            try:
                from models import ServerGroupAssociation
                group_assocs = db.query(ServerGroupAssociation).filter(ServerGroupAssociation.server_id == ex.server.id).all()
                group_ids = [ga.group_id for ga in group_assocs]
                if group_ids:
                    from models import ServerGroup
                    groups = db.query(ServerGroup).filter(ServerGroup.id.in_(group_ids)).all()
                    item["server_groups"] = [{"id": g.id, "name": g.name} for g in groups]
                else:
                    item["server_groups"] = []
            except Exception:
                item["server_groups"] = []
        if getattr(ex, "executor", None):
            item["executor"] = {"id": ex.executor.id, "username": ex.executor.username}
        items.append(item)
    
    return {"executions": items, "total": total}


@router.get("/executions/latest", response_model=ScriptExecutionListResponse)
def get_latest_script_executions(
    limit: int = Query(1000, ge=1, le=10000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can view script executions
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view script executions"
        )

    executions = db.query(ScriptExecution).order_by(ScriptExecution.id.desc()).limit(limit).all()

    items = []
    for ex in executions:
        item = {
            "id": ex.id,
            "script_id": ex.script_id,
            "server_id": ex.server_id,
            "executed_by": ex.executed_by,
            "status": ex.status,
            "output": ex.output,
            "error": ex.error,
            "started_at": ex.started_at,
            "completed_at": ex.completed_at,
            "parameters_used": ex.parameters_used,
        }
        items.append(item)

    total = db.query(ScriptExecution).count()
    return {"executions": items, "total": total}

@router.get("/executions/export")
def export_script_executions(
    format: str = Query("csv", pattern="^(csv|json)$"),
    status_filter: str | None = Query(None, description="completed|running|failed"),
    script_ids: str | None = Query(None, description="comma-separated script ids"),
    server_ids: str | None = Query(None, description="comma-separated server ids"),
    group_ids: str | None = Query(None, description="comma-separated group ids"),
    from_date: str | None = Query(None, description="YYYY-MM-DD"),
    to_date: str | None = Query(None, description="YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can export")

    executions = db.query(ScriptExecution).options(
        joinedload(ScriptExecution.script),
        joinedload(ScriptExecution.server).joinedload(Server.groups),
        joinedload(ScriptExecution.executor)
    ).all()

    def parse_ids(s: str | None):
        if not s:
            return set()
        try:
            return set(int(x) for x in s.split(",") if x.strip())
        except Exception:
            return set()

    script_id_set = parse_ids(script_ids)
    server_id_set = parse_ids(server_ids)
    group_id_set = parse_ids(group_ids)

    # Apply filters
    items = []
    for ex in executions:
        if status_filter and ex.status != status_filter:
            continue
        if script_id_set and ex.script_id not in script_id_set:
            continue
        if server_id_set and ex.server_id not in server_id_set:
            continue
        if group_id_set:
            s_groups = getattr(getattr(ex, "server", None), "groups", []) or []
            s_group_ids = {g.id for g in s_groups}
            if not (s_group_ids & group_id_set):
                continue
        if from_date:
            try:
                y, m, d = [int(x) for x in from_date.split("-")]
                if not ex.started_at or ex.started_at < func.datetime(f"{y:04d}-{m:02d}-{d:02d} 00:00:00"):
                    # fallback: do client-side compare when materialized
                    pass
            except Exception:
                pass
        if to_date:
            try:
                y, m, d = [int(x) for x in to_date.split("-")]
            except Exception:
                pass

        item = {
            "id": ex.id,
            "script_id": ex.script_id,
            "script_name": (ex.script.name if getattr(ex, "script", None) else None),
            "server_id": ex.server_id,
            "server_name": (ex.server.name if getattr(ex, "server", None) else None),
            "status": ex.status,
            "output": ex.output,
            "error": ex.error,
            "started_at": ex.started_at.isoformat() if ex.started_at else None,
            "completed_at": ex.completed_at.isoformat() if ex.completed_at else None,
            "executor": (ex.executor.username if getattr(ex, "executor", None) else None),
        }
        items.append(item)

    # Date range filtering in python (sa func not evaluated client-side)
    from_dt = None
    to_dt = None
    try:
        if from_date:
            from_dt = time.strptime(from_date, "%Y-%m-%d")
        if to_date:
            to_dt = time.strptime(to_date, "%Y-%m-%d")
    except Exception:
        pass

    def in_range(iso: str | None):
        if not iso:
            return False
        try:
            dt = time.strptime(iso[:10], "%Y-%m-%d")
            if from_dt and dt < from_dt:
                return False
            if to_dt and dt > to_dt:
                return False
            return True
        except Exception:
            return True

    if from_dt or to_dt:
        items = [it for it in items if in_range(it.get("started_at"))]

    if format == "json":
        return JSONResponse(items)

    # CSV export
    headers = ["id","script_id","script_name","server_id","server_name","status","started_at","completed_at","executor","output","error"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers)
    writer.writeheader()
    for it in items:
        # Avoid newlines breaking csv cells
        row = {k: (str(it.get(k)).replace("\n","\\n") if it.get(k) is not None else "") for k in headers}
        writer.writerow(row)
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=executions.csv"})


@router.post("/{script_id}/execute-group")
def execute_script_group(
    script_id: int,
    group_id: int = Query(..., description="Target server group ID"),
    concurrency: int | None = Query(None, ge=1, le=20, description="Override concurrency (default script or 5)"),
    continue_on_error: bool | None = Query(None, description="Override continue-on-error (default script or true)"),
    timeout_seconds: int | None = Query(None, ge=0, le=3600, description="Override per-server timeout (0 = no timeout, default script or 60)"),
    parameters_used: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can execute scripts")

    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    group = db.query(ServerGroup).options(joinedload(ServerGroup.servers)).filter(ServerGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server group not found")

    servers = list(group.servers or [])
    if not servers:
        return {"summary": {"total": 0, "enqueued": 0}, "results": []}

    # Enqueue one RQ job per server using the robust path; do NOT pre-create execution rows here
    from rq_queue import get_queue
    from tasks import execute_script_job

    q = get_queue("execute")
    results = []
    for srv in servers:
        job = q.enqueue(execute_script_job, script.id, srv.id, current_user.id, None)
        results.append({
            "server_id": srv.id,
            "server_name": srv.name,
            "job_id": job.id,
            "status": "enqueued"
        })

    return {"summary": {"total": len(servers), "enqueued": len(results)}, "results": results}

@router.post("/execute/enqueue/{script_id}/{server_id}")
def enqueue_execute_script(script_id: int, server_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    logger = get_logger(__name__)
    # Basic existence checks
    script = db.query(Script).filter(Script.id == script_id).first()
    server = db.query(Server).filter(Server.id == server_id).first()
    if not script or not server:
        raise HTTPException(status_code=404, detail="Script or Server not found")

    # Enqueue job
    q = get_queue("execute")
    job = q.enqueue(execute_script_job, script_id, server_id, current_user.id if current_user else None, None)
    logger.info(f"enqueued {kv(job_id=job.id, script_id=script_id, server_id=server_id)}")
    return {"enqueued": True, "job_id": job.id}

@router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    try:
        conn = get_redis()
        job = Job.fetch(job_id, connection=conn)
        status = {
            "id": job.id,
            "enqueued_at": getattr(job, 'enqueued_at', None).isoformat() if getattr(job, 'enqueued_at', None) else None,
            "started_at": getattr(job, 'started_at', None).isoformat() if getattr(job, 'started_at', None) else None,
            "ended_at": getattr(job, 'ended_at', None).isoformat() if getattr(job, 'ended_at', None) else None,
            "is_finished": job.is_finished,
            "is_failed": job.is_failed,
        }
        if job.is_finished and isinstance(job.result, dict):
            status.update({
                "result": job.result,
                "execution_id": job.result.get("execution_id")
            })
        return status
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Job not found: {str(e)}")

@router.get("/settings", response_model=SettingsResponse)
def get_settings(db: Session = Depends(get_db)):
    s = db.query(Settings).first()
    if not s:
        s = Settings()
        db.add(s)
        db.commit()
        db.refresh(s)
    return s

@router.put("/settings", response_model=SettingsResponse)
def update_settings(payload: dict, db: Session = Depends(get_db)):
    s = db.query(Settings).first()
    if not s:
        s = Settings()
        db.add(s)
    # Update existing settings
    if 'virtual_timeout_duration' in payload:
        try:
            val = int(payload.get('virtual_timeout_duration') or 0)
            s.virtual_timeout_duration = max(1, val)
        except Exception:
            pass
    if 'long_running_delay_seconds' in payload:
        try:
            val = int(payload.get('long_running_delay_seconds') or 0)
            s.long_running_delay_seconds = max(1, val)
        except Exception:
            pass
    if 'max_concurrent_executions' in payload:
        try:
            val = int(payload.get('max_concurrent_executions') or 0)
            s.max_concurrent_executions = max(1, val)
        except Exception:
            pass
    db.commit()
    db.refresh(s)
    return s
