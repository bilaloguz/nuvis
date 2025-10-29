"""
Server Health Monitoring API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, text
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import paramiko
import subprocess
import json
import time

from database import get_db, engine
from models import Server, ServerHealth, User, Settings
from schemas import (
    ServerHealthResponse, ServerHealthListResponse, 
    ServerHealthSummary, ServerHealthBase
)
from auth import get_current_user
from secrets_vault import SecretsVault
from health_commands import (
    get_health_commands, determine_health_status, detect_os, parse_health_output
)
from os_detection import detect_os_automatically
from rq_queue import get_redis, get_queue

router = APIRouter()

def check_database_health() -> Dict[str, Any]:
    """Check database connectivity and basic health"""
    try:
        start_time = time.time()
        
        # Test basic connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).fetchone()
            if not result or result[0] != 1:
                return {
                    "status": "unhealthy",
                    "error": "Database query returned unexpected result",
                    "response_time_ms": 0
                }
        
        response_time = (time.time() - start_time) * 1000
        
        # Test table access
        with engine.connect() as conn:
            conn.execute(text("SELECT COUNT(*) FROM users LIMIT 1"))
        
        return {
            "status": "healthy",
            "response_time_ms": round(response_time, 2),
            "message": "Database connection successful"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "response_time_ms": 0
        }

def check_redis_health() -> Dict[str, Any]:
    """Check Redis connectivity and basic health"""
    try:
        start_time = time.time()
        
        redis_client = get_redis()
        
        # Test basic ping
        pong = redis_client.ping()
        if not pong:
            return {
                "status": "unhealthy",
                "error": "Redis ping failed",
                "response_time_ms": 0
            }
        
        response_time = (time.time() - start_time) * 1000
        
        # Get Redis info
        info = redis_client.info()
        
        return {
            "status": "healthy",
            "response_time_ms": round(response_time, 2),
            "redis_version": info.get('redis_version', 'unknown'),
            "used_memory_human": info.get('used_memory_human', 'unknown'),
            "connected_clients": info.get('connected_clients', 0),
            "message": "Redis connection successful"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "response_time_ms": 0
        }

def check_worker_queue_health() -> Dict[str, Any]:
    """Check worker queue status and health"""
    try:
        start_time = time.time()
        
        queue = get_queue()
        redis_client = get_redis()
        
        # Get queue statistics
        queue_stats = {
            "queue_length": len(queue),
            "failed_jobs": queue.failed_job_registry.count,
            "finished_jobs": queue.finished_job_registry.count,
            "started_jobs": queue.started_job_registry.count,
            "scheduled_jobs": queue.scheduled_job_registry.count,
        }
        
        # Check if workers are active
        try:
            # Use RQ's Worker class to get active workers
            from rq import Worker
            workers = Worker.all(connection=redis_client)
            active_workers = len(workers)
        except Exception:
            active_workers = 0
        
        response_time = (time.time() - start_time) * 1000
        
        # Determine overall queue health
        if active_workers == 0:
            status = "warning"
            message = "No active workers found"
        elif queue_stats["failed_jobs"] > 100:  # Arbitrary threshold
            status = "warning"
            message = f"High number of failed jobs: {queue_stats['failed_jobs']}"
        else:
            status = "healthy"
            message = "Worker queue is healthy"
        
        return {
            "status": status,
            "response_time_ms": round(response_time, 2),
            "active_workers": active_workers,
            "queue_stats": queue_stats,
            "message": message
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "response_time_ms": 0
        }

def get_system_metrics() -> Dict[str, Any]:
    """Get basic system metrics"""
    try:
        # Get settings for max concurrent executions
        db = next(get_db())
        settings = db.query(Settings).first()
        max_concurrent = getattr(settings, 'max_concurrent_executions', 8) if settings else 8
        
        # Get current execution counts from database
        current_running = db.query(ServerHealth).filter(
            ServerHealth.status.in_(['running', 'long_running'])
        ).count()
        
        # Get recent execution stats
        recent_executions = db.execute(text("""
            SELECT status, COUNT(*) as count 
            FROM script_executions 
            WHERE started_at > datetime('now', '-1 hour')
            GROUP BY status
        """)).fetchall()
        
        recent_stats = {row[0]: row[1] for row in recent_executions}
        
        return {
            "max_concurrent_executions": max_concurrent,
            "current_running_executions": current_running,
            "recent_executions_1h": recent_stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "error": f"Failed to get system metrics: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }

def execute_health_check(server: Server, db: Session) -> Optional[ServerHealthBase]:
    """Execute health check on a server and return health data"""
    try:
        vault = SecretsVault.get()
        
        # Get SSH connection details
        ssh_key_path = server.ssh_key_path
        password = None
        
        # Always try to get password as fallback, regardless of auth_method
        if server.password_encrypted:
            try:
                password = vault.decrypt_to_str(server.password_encrypted)
                print(f"DEBUG: Successfully decrypted password for {server.name}")
            except Exception as e:
                print(f"Failed to decrypt password for server {server.name}: {e}")
                # Don't return None here, continue without password
        
        # Connect via SSH
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            connection_success = False
            
            # Try SSH key first if available
            if server.auth_method == "ssh_key" and ssh_key_path:
                try:
                    ssh.connect(
                        hostname=server.ip,
                        username=server.username,
                        key_filename=ssh_key_path,
                        timeout=10
                    )
                    connection_success = True
                except Exception as e:
                    print(f"SSH key connection failed for {server.name}: {e}, trying password...")
            
            # Fall back to password if SSH key failed or not available
            if not connection_success and password:
                try:
                    ssh.connect(
                        hostname=server.ip,
                        username=server.username,
                        password=password,
                        timeout=10
                    )
                    connection_success = True
                except Exception as e:
                    print(f"Password connection failed for {server.name}: {e}")
            
            if not connection_success:
                print(f"Health check failed: No connection method worked for {server.name}")
                return None
            
            print(f"Health check connection successful for {server.name}")
            
            # Detect OS first
            os_type = detect_os(ssh)
            print(f"Detected OS for {server.name}: {os_type}")
            
            # Update server OS detection if we have a successful connection
            if os_type and os_type != "unknown":
                # Map the detected OS to our standard format
                os_mapping = {
                    "linux": "linux",
                    "windows": "windows", 
                    "darwin": "macos",
                    "freebsd": "freebsd"
                }
                detected_os = os_mapping.get(os_type, "unknown")
                if detected_os != "unknown":
                    server.detected_os = detected_os
                    server.os_detection_method = "ssh_connect"
                    db.commit()
                    print(f"Updated server {server.name} OS to: {detected_os}")
            
            # Execute health check commands
            commands = get_health_commands(os_type)
            
            health_data = {}
            
            # Execute each health check command
            for command_type, command in commands.items():
                try:
                    stdin, stdout, stderr = ssh.exec_command(command)
                    
                    # Handle different encodings for Windows vs Linux
                    raw_output = stdout.read()
                    try:
                        if os_type == "windows":
                            # For Windows servers, try Windows-1252 first
                            try:
                                output = raw_output.decode('windows-1252')
                            except UnicodeDecodeError:
                                # Fallback to UTF-8 for Windows
                                output = raw_output.decode('utf-8', errors='ignore')
                        else:
                            # For Linux servers, use UTF-8
                            output = raw_output.decode('utf-8')
                    except UnicodeDecodeError:
                        # Final fallback for any OS
                        output = raw_output.decode('latin-1', errors='ignore')
                    
                    # Parse output based on OS and command type
                    parsed_data = parse_health_output(os_type, command_type, output)
                    health_data.update(parsed_data)
                    
                except Exception as e:
                    print(f"Failed to execute {command_type} for {server.name}: {e}")
            
            # Determine overall health status
            health_data['status'] = determine_health_status(
                health_data.get('load_1min'),
                health_data.get('disk_usage'),
                health_data.get('memory_usage'),
                health_data.get('cpu_usage')
            )
            
            return ServerHealthBase(**health_data)
            
        finally:
            ssh.close()
            
    except Exception as e:
        print(f"Health check failed for server {server.name}: {e}")
        print(f"DEBUG: Exception type: {type(e)}")
        import traceback
        print(f"DEBUG: Exception traceback: {traceback.format_exc()}")
        return ServerHealthBase(status="unknown")

@router.get("/servers/{server_id}/health", response_model=ServerHealthListResponse)
def get_server_health(
    server_id: int,
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get health history for a specific server"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    health_records = db.query(ServerHealth).filter(
        ServerHealth.server_id == server_id
    ).order_by(desc(ServerHealth.created_at)).limit(limit).all()
    
    return ServerHealthListResponse(
        health_records=health_records,
        total=len(health_records)
    )

@router.post("/servers/{server_id}/health/check")
def check_server_health(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Manually trigger a health check for a specific server"""
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    # Execute health check
    print(f"DEBUG: Starting health check for server {server.name} (ID: {server_id})")
    health_data = execute_health_check(server, db)
    print(f"DEBUG: Health check result: {health_data}")
    if not health_data:
        print(f"DEBUG: Health check returned None for server {server.name}")
        raise HTTPException(status_code=500, detail="Failed to execute health check")
    
    # Save health record
    try:
        # Debug: Print health data before saving
        print(f"DEBUG: Saving health record for server {server_id}")
        print(f"DEBUG: Health data: {health_data}")
        print(f"DEBUG: Status: {health_data.status}")
        print(f"DEBUG: Server ID: {server_id}")
        
        health_record = ServerHealth(
            server_id=server_id,
            status=health_data.status,
            cpu_usage=health_data.cpu_usage,
            memory_usage=health_data.memory_usage,
            disk_usage=health_data.disk_usage,
            load_1min=health_data.load_1min,
            load_5min=health_data.load_5min,
            load_15min=health_data.load_15min,
            uptime_seconds=health_data.uptime_seconds,
            network_interfaces=json.dumps(health_data.network_interfaces) if health_data.network_interfaces else None
        )
        
        print(f"DEBUG: Created health record object")
        db.add(health_record)
        print(f"DEBUG: Added to session")
        db.commit()
        print(f"DEBUG: Committed to database")
        db.refresh(health_record)
        print(f"DEBUG: Refreshed health record")
    except Exception as e:
        print(f"Error saving health record for server {server_id}: {e}")
        print(f"Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save health record: {str(e)}")
    
    return {"message": "Health check completed", "health_record": health_record}

@router.get("/health/summary", response_model=List[ServerHealthSummary])
def get_health_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get health summary for all servers"""
    # Get latest health record for each server
    subquery = db.query(
        ServerHealth.server_id,
        func.max(ServerHealth.created_at).label('latest_check')
    ).group_by(ServerHealth.server_id).subquery()
    
    latest_health = db.query(ServerHealth).join(
        subquery,
        (ServerHealth.server_id == subquery.c.server_id) &
        (ServerHealth.created_at == subquery.c.latest_check)
    ).all()
    
    # Get server names
    server_ids = [h.server_id for h in latest_health]
    servers = db.query(Server).filter(Server.id.in_(server_ids)).all()
    server_names = {s.id: s.name for s in servers}
    
    # Build summary
    summary = []
    for health in latest_health:
        summary.append(ServerHealthSummary(
            server_id=health.server_id,
            server_name=server_names.get(health.server_id, "Unknown"),
            status=health.status,
            uptime_seconds=health.uptime_seconds,
            load_1min=health.load_1min,
            disk_usage=health.disk_usage,
            memory_usage=health.memory_usage,
            last_checked=health.last_checked
        ))
    
    return summary

@router.post("/health/check-all")
def check_all_servers_health(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Manually trigger health checks for all servers"""
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admins only")
    
    servers = db.query(Server).all()
    results = []
    
    for server in servers:
        try:
            health_data = execute_health_check(server, db)
            if health_data:
                # Save health record
                try:
                    health_record = ServerHealth(
                        server_id=server.id,
                        status=health_data.status,
                        cpu_usage=health_data.cpu_usage,
                        memory_usage=health_data.memory_usage,
                        disk_usage=health_data.disk_usage,
                        load_1min=health_data.load_1min,
                        load_5min=health_data.load_5min,
                        load_15min=health_data.load_15min,
                        uptime_seconds=health_data.uptime_seconds,
                        network_interfaces=json.dumps(health_data.network_interfaces) if health_data.network_interfaces else None
                    )
                    db.add(health_record)
                except Exception as e:
                    print(f"Error saving health record for server {server.id}: {e}")
                    results.append({
                        "server_id": server.id,
                        "server_name": server.name,
                        "status": "failed",
                        "error": f"Failed to save health record: {str(e)}"
                    })
                    continue
                results.append({
                    "server_id": server.id,
                    "server_name": server.name,
                    "status": "success",
                    "health_status": health_data.status
                })
            else:
                results.append({
                    "server_id": server.id,
                    "server_name": server.name,
                    "status": "failed",
                    "error": "Failed to execute health check"
                })
        except Exception as e:
            results.append({
                "server_id": server.id,
                "server_name": server.name,
                "status": "failed",
                "error": str(e)
            })
    
    db.commit()
    
    return {
        "message": f"Health checks completed for {len(servers)} servers",
        "results": results
    }

@router.get("/health", response_model=Dict[str, Any])
def get_system_health(
    current_user: User = Depends(get_current_user)
):
    """
    Comprehensive system health check endpoint.
    Returns database, Redis, worker queue, and system metrics status.
    """
    start_time = time.time()
    
    # Run all health checks in parallel
    database_health = check_database_health()
    redis_health = check_redis_health()
    worker_queue_health = check_worker_queue_health()
    system_metrics = get_system_metrics()
    
    total_response_time = (time.time() - start_time) * 1000
    
    # Determine overall system health
    health_statuses = [
        database_health.get("status"),
        redis_health.get("status"),
        worker_queue_health.get("status")
    ]
    
    if "unhealthy" in health_statuses:
        overall_status = "unhealthy"
    elif "warning" in health_statuses:
        overall_status = "warning"
    else:
        overall_status = "healthy"
    
    return {
        "overall_status": overall_status,
        "total_response_time_ms": round(total_response_time, 2),
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "database": database_health,
            "redis": redis_health,
            "worker_queue": worker_queue_health
        },
        "system_metrics": system_metrics
    }

@router.get("/health/database")
def get_database_health(
    current_user: User = Depends(get_current_user)
):
    """Get detailed database health information"""
    return check_database_health()

@router.get("/health/redis")
def get_redis_health(
    current_user: User = Depends(get_current_user)
):
    """Get detailed Redis health information"""
    return check_redis_health()

@router.get("/health/worker-queue")
def get_worker_queue_health(
    current_user: User = Depends(get_current_user)
):
    """Get detailed worker queue health information"""
    return check_worker_queue_health()

@router.get("/health/metrics")
def get_system_metrics_endpoint(
    current_user: User = Depends(get_current_user)
):
    """Get system metrics and statistics"""
    return get_system_metrics()

@router.get("/health/ping")
def health_ping():
    """
    Simple health ping endpoint for basic monitoring.
    No authentication required - returns basic system status.
    """
    try:
        # Quick database check
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        # Quick Redis check
        redis_client = get_redis()
        redis_client.ping()
        
        return {
            "status": "healthy",
            "message": "System is operational",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
