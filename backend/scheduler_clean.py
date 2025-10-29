import threading
import time
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
import paramiko
import os

from models import Script, Server, ScriptExecution, Schedule, Settings
from database import SessionLocal, get_db
from auth_logger import auth_logger
from ssh_utils import detect_key_type_from_file, get_paramiko_key_class


def calculate_next_run_time(schedule: Schedule, last_run: Optional[datetime] = None) -> Optional[datetime]:
    """Calculate the next run time for a schedule"""
    if not schedule.enabled:
        return None
    
    base_utc = last_run or datetime.utcnow()
    
    if schedule.cron_expression:
        # For cron expressions, we'd need a cron parser library
        # For now, just return None to run immediately
        return None
    if schedule.interval_seconds and schedule.interval_seconds > 0:
        return base_utc + timedelta(seconds=schedule.interval_seconds)
    # Run once immediately by default
    return None


def _connect_to_server(server: Server):
    """Connect to server via SSH, trying key first then password"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    connection_success = False
    
    # Add a small delay to avoid rate limiting
    time.sleep(0.5)
    
    # Try SSH key first if available
    if server.auth_method == 'ssh_key' and server.ssh_key_path:
        try:
            key_path = server.ssh_key_path
            if not os.path.isabs(key_path):
                key_path = os.path.join(os.getcwd(), key_path)
            if os.path.exists(key_path):
                # Detect key type and load with appropriate paramiko class
                key_type = detect_key_type_from_file(key_path)
                key_class = get_paramiko_key_class(key_type)
                pkey = key_class.from_private_key_file(key_path)
                ssh.connect(
                    hostname=server.ip, 
                    username=server.username, 
                    pkey=pkey, 
                    timeout=30,
                    allow_agent=False,
                    look_for_keys=False
                )
                connection_success = True
                print(f"SSH key connection successful for {server.name}")
                
                # Log successful SSH key authentication
                auth_logger.log_script_execution_auth(
                    script_name="scheduled_script",
                    server_name=server.name,
                    server_ip=server.ip,
                    auth_method_used="ssh_key",
                    success=True,
                    details={"key_path": key_path, "scheduled": True}
                )
        except Exception as e:
            print(f"SSH key connection failed for {server.name}: {e}")
            
            # Log failed SSH key authentication
            auth_logger.log_script_execution_auth(
                script_name="scheduled_script",
                server_name=server.name,
                server_ip=server.ip,
                auth_method_used="ssh_key",
                success=False,
                details={"error": str(e), "key_path": key_path, "scheduled": True}
            )
    
    # Fall back to password authentication if SSH key failed or not available
    if not connection_success and server.password_encrypted:
        try:
            from secrets_vault import SecretsVault
            vault = SecretsVault.get()
            password = vault.decrypt_to_str(server.password_encrypted)
            ssh.connect(
                hostname=server.ip, 
                username=server.username, 
                password=password, 
                timeout=30,
                allow_agent=False,
                look_for_keys=False
            )
            connection_success = True
            print(f"Password connection successful for {server.name}")
            
            # Log successful password authentication
            auth_logger.log_script_execution_auth(
                script_name="scheduled_script",
                server_name=server.name,
                server_ip=server.ip,
                auth_method_used="password",
                success=True,
                details={"scheduled": True}
            )
        except Exception as e2:
            print(f"Password connection failed for {server.name}: {e2}")
            
            # Log failed password authentication
            auth_logger.log_script_execution_auth(
                script_name="scheduled_script",
                server_name=server.name,
                server_ip=server.ip,
                auth_method_used="password",
                success=False,
                details={"error": str(e2), "scheduled": True}
            )
    
    if not connection_success:
        raise Exception("Failed to connect to server with both SSH key and password")
    
    return ssh


def _execute_infinite_script(ssh, script, virtual_timeout_duration):
    """Execute an infinite script and capture output for virtual timeout duration"""
    script_content = script.content or ''
    
    # Detect Windows server and adjust commands accordingly
    is_windows = False
    try:
        # Try to detect Windows by running a simple command
        stdin, stdout, stderr = ssh.exec_command("echo %OS%")
        os_output = stdout.read().decode('utf-8', errors='ignore').strip()
        if 'Windows' in os_output or 'NT' in os_output:
            is_windows = True
    except Exception as e:
        # Fallback: assume Windows if server name suggests it
        is_windows = 'windows' in script.name.lower() or 'win' in script.name.lower()
    
    if is_windows:
        # Windows-specific commands
        if script.script_type == 'powershell':
            import base64
            # Encode the script content to base64 for -EncodedCommand
            encoded_script = base64.b64encode(script_content.encode('utf-16le')).decode('ascii')
            exec_cmd = f"powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand {encoded_script}"
            stdin, stdout, stderr = ssh.exec_command(exec_cmd)
        else:
            stdin, stdout, stderr = ssh.exec_command(script_content)
    else:
        # Unix/Linux commands
        if script.script_type == 'powershell':
            import base64
            # Encode the script content to base64 for -EncodedCommand
            encoded_script = base64.b64encode(script_content.encode('utf-16le')).decode('ascii')
            exec_cmd = f"pwsh -NoLogo -NoProfile -NonInteractive -EncodedCommand {encoded_script}"
            stdin, stdout, stderr = ssh.exec_command(exec_cmd)
        else:
            stdin, stdout, stderr = ssh.exec_command(script_content)
    
    # Capture output for virtual timeout duration
    start_time = time.time()
    out_chunks = []
    err_chunks = []
    
    while time.time() - start_time < virtual_timeout_duration:
        if stdout.channel.recv_ready():
            chunk = stdout.channel.recv(4096)
            out_chunks.append(chunk)
        if stderr.channel.recv_stderr_ready():
            chunk = stderr.channel.recv_stderr(4096)
            err_chunks.append(chunk)
        if stdout.channel.exit_status_ready():
            break
        time.sleep(0.1)
    
    out = b"".join(out_chunks).decode('utf-8', errors='ignore')
    err = b"".join(err_chunks).decode('utf-8', errors='ignore')
    exit_code = 0  # Success for infinite scripts
    
    return out, err, exit_code


def _execute_regular_script(ssh, script, timeout_sec):
    """Execute a regular script with timeout"""
    script_content = script.content or ''
    
    # Detect Windows server and adjust commands accordingly
    is_windows = False
    try:
        # Try to detect Windows by running a simple command
        stdin, stdout, stderr = ssh.exec_command("echo %OS%")
        os_output = stdout.read().decode('utf-8', errors='ignore').strip()
        if 'Windows' in os_output or 'NT' in os_output:
            is_windows = True
    except Exception as e:
        # Fallback: assume Windows if server name suggests it
        is_windows = 'windows' in script.name.lower() or 'win' in script.name.lower()
    
    if is_windows:
        # Windows-specific commands
        if script.script_type == 'bash':
            exec_cmd = "cmd.exe /c"
            full_cmd = f"{exec_cmd} {script_content}"
            stdin, stdout, stderr = ssh.exec_command(full_cmd)
        elif script.script_type == 'python':
            sftp = ssh.open_sftp()
            remote_path = f"C:\\temp\\.sm_py_exec_{script.id}.py"
            with sftp.file(remote_path, 'w') as f:
                f.write(script_content)
            sftp.close()
            stdin, stdout, stderr = ssh.exec_command(f"python {remote_path} & del {remote_path}")
        elif script.script_type == 'powershell':
            import base64
            encoded_script = base64.b64encode(script_content.encode('utf-16le')).decode('ascii')
            exec_cmd = f"powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand {encoded_script}"
            stdin, stdout, stderr = ssh.exec_command(exec_cmd)
        else:
            stdin, stdout, stderr = ssh.exec_command(script_content)
    else:
        # Unix/Linux commands
        if script.script_type == 'bash':
            exec_cmd = "/bin/bash -s"
            stdin, stdout, stderr = ssh.exec_command(exec_cmd)
            if script_content:
                stdin.write(script_content)
                stdin.channel.shutdown_write()
        elif script.script_type == 'python':
            sftp = ssh.open_sftp()
            remote_path = f"/tmp/.sm_py_exec_{script.id}.py"
            with sftp.file(remote_path, 'w') as f:
                f.write(script_content)
            sftp.close()
            stdin, stdout, stderr = ssh.exec_command(f"python3 {remote_path}; rm -f {remote_path}")
        elif script.script_type == 'powershell':
            import base64
            encoded_script = base64.b64encode(script_content.encode('utf-16le')).decode('ascii')
            exec_cmd = f"pwsh -NoLogo -NoProfile -NonInteractive -EncodedCommand {encoded_script}"
            stdin, stdout, stderr = ssh.exec_command(exec_cmd)
        else:
            stdin, stdout, stderr = ssh.exec_command(script_content)
    
    # Wait for completion with timeout
    chan = stdout.channel
    start = time.time()
    out_chunks, err_chunks = [], []
    
    while True:
        if chan.recv_ready():
            chunk = chan.recv(4096)
            out_chunks.append(chunk)
        if chan.recv_stderr_ready():
            chunk = chan.recv_stderr(4096)
            err_chunks.append(chunk)
        if chan.exit_status_ready():
            break
        if time.time() - start > timeout_sec:
            try:
                chan.close()
            except Exception:
                pass
            raise TimeoutError(f"Command timed out after {timeout_sec}s")
        time.sleep(0.1)
    
    exit_code = chan.recv_exit_status()
    
    # Try different encodings for Windows
    if is_windows:
        try:
            out_text = b"".join(out_chunks).decode('cp1252', errors='ignore')
        except:
            out_text = b"".join(out_chunks).decode('utf-8', errors='ignore')
        try:
            err_text = b"".join(err_chunks).decode('cp1252', errors='ignore')
        except:
            err_text = b"".join(err_chunks).decode('utf-8', errors='ignore')
    else:
        out_text = b"".join(out_chunks).decode('utf-8', errors='ignore')
        err_text = b"".join(err_chunks).decode('utf-8', errors='ignore')
    
    return out_text, err_text, exit_code


def _run_script_on_server(db: Session, script: Script, server: Server, executed_by: int, parameters_used: Optional[str], timeout_sec: int | None) -> ScriptExecution:
    print(f"SCHEDULER: Starting execution of script '{script.name}' on server '{server.name}'")
    
    # Create execution record
    exec_row = ScriptExecution(
        script_id=script.id,
        server_id=server.id,
        executed_by=executed_by,
        parameters_used=parameters_used,
        status="running",
    )
    db.add(exec_row)
    db.commit()
    db.refresh(exec_row)
    
    try:
        # Get virtual timeout duration from settings for infinite scripts
        settings = db.query(Settings).first()
        if not settings:
            settings = Settings()
            db.add(settings)
            db.commit()
            db.refresh(settings)
        virtual_timeout_duration = settings.virtual_timeout_duration or 60

        # Check if this is an infinite script
        is_infinite = (timeout_sec == 0) or (timeout_sec is None and script.per_server_timeout_seconds == 0)

        # Start background task to mark as long_running after 5 minutes
        def mark_long_running():
            time.sleep(300)  # 5 minutes
            try:
                db_session = SessionLocal()
                exec_row_update = db_session.query(ScriptExecution).filter(ScriptExecution.id == exec_row.id).first()
                if exec_row_update and exec_row_update.status == "running":
                    exec_row_update.status = "long_running"
                    db_session.commit()
                db_session.close()
            except Exception as e:
                print(f"Error updating execution status: {e}")
                if 'db_session' in locals():
                    db_session.close()
        
        long_running_thread = threading.Thread(target=mark_long_running, daemon=True)
        long_running_thread.start()

        # Connect to server
        ssh = _connect_to_server(server)
        
        # Execute script
        if is_infinite:
            out, err, exit_code = _execute_infinite_script(ssh, script, virtual_timeout_duration)
        else:
            out, err, exit_code = _execute_regular_script(ssh, script, timeout_sec)
        
        # Update execution record
        if is_infinite:
            exec_row.status = "running"
            exec_row.error = None
        else:
            exec_row.status = "completed" if exit_code == 0 else "failed"
            exec_row.error = err if exit_code != 0 else None
            exec_row.completed_at = func.now()
        
        exec_row.output = out
        db.commit()
        db.refresh(exec_row)
        return exec_row
        
    except Exception as e:
        print(f"SCHEDULER ERROR: {e}")
        import traceback
        traceback.print_exc()
        exec_row.status = "failed"
        exec_row.error = str(e)
        exec_row.completed_at = func.now()
        db.commit()
        db.refresh(exec_row)
        return exec_row


def scheduler_loop(stop_event: threading.Event):
    print("DEBUG: Scheduler loop started")
    while not stop_event.is_set():
        try:
            db: Session = SessionLocal()
            try:
                # Get all enabled schedules
                schedules = db.query(Schedule).filter(Schedule.enabled == True).all()
                
                for schedule in schedules:
                    try:
                        # Get the last execution for this schedule
                        last_execution = db.query(ScriptExecution).filter(
                            ScriptExecution.script_id == schedule.script_id
                        ).order_by(ScriptExecution.created_at.desc()).first()
                        
                        last_run = last_execution.created_at if last_execution else None
                        next_run = calculate_next_run_time(schedule, last_run)
                        
                        if next_run and next_run <= datetime.utcnow():
                            # Time to run this schedule
                            script = db.query(Script).filter(Script.id == schedule.script_id).first()
                            if script:
                                # Get servers for this script
                                servers = db.query(Server).filter(Server.id.in_(schedule.server_ids)).all()
                                
                                for server in servers:
                                    try:
                                        # Run script on server
                                        _run_script_on_server(
                                            db=db,
                                            script=script,
                                            server=server,
                                            executed_by=schedule.created_by,
                                            parameters_used=schedule.parameters,
                                            timeout_sec=script.per_server_timeout_seconds
                                        )
                                    except Exception as e:
                                        print(f"Error running script {script.name} on server {server.name}: {e}")
                                        continue
                    except Exception as e:
                        print(f"Error processing schedule {schedule.id}: {e}")
                        continue
                        
            finally:
                db.close()
                
        except Exception as e:
            print(f"Scheduler loop error: {e}")
            import traceback
            traceback.print_exc()
        
        # Wait before next iteration
        time.sleep(60)  # Check every minute


# Global scheduler thread
_scheduler_thread = None
_scheduler_stop_event = None


def start_scheduler():
    """Start the scheduler in a background thread"""
    global _scheduler_thread, _scheduler_stop_event
    
    if _scheduler_thread and _scheduler_thread.is_alive():
        print("Scheduler is already running")
        return
    
    _scheduler_stop_event = threading.Event()
    _scheduler_thread = threading.Thread(target=scheduler_loop, args=(_scheduler_stop_event,), daemon=True)
    _scheduler_thread.start()
    print("Scheduler started")


def stop_scheduler():
    """Stop the scheduler"""
    global _scheduler_thread, _scheduler_stop_event
    
    if _scheduler_stop_event:
        _scheduler_stop_event.set()
    
    if _scheduler_thread and _scheduler_thread.is_alive():
        _scheduler_thread.join(timeout=5)
        print("Scheduler stopped")
    else:
        print("Scheduler was not running")







