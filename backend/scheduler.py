import threading
import time
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from database import SessionLocal
from models import Schedule, Script, Server, ServerGroup, ScriptExecution, Workflow, Settings
from secrets_vault import SecretsVault
from auth_logger import auth_logger
from ssh_key_utils import detect_key_type_from_file, get_paramiko_key_class

import os
import paramiko

try:
    from croniter import croniter  # optional
except Exception:
    croniter = None

from rq_queue import acquire_lock, release_lock, get_queue

# APScheduler imports
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR


def _now_utc() -> datetime:
    return datetime.utcnow().replace(tzinfo=timezone.utc)


def _compute_next_run(schedule: Schedule, from_time: Optional[datetime] = None) -> Optional[datetime]:
    """Compute next run time in UTC, honoring schedule.timezone for cron entries."""
    base_utc = from_time or _now_utc()
    if schedule.cron_expression and croniter is not None:
        try:
            tzname = (getattr(schedule, "timezone", None) or "UTC").strip() or "UTC"
            try:
                tz = ZoneInfo(tzname)
            except Exception:
                tz = ZoneInfo("UTC")
            # Use true local "now" in the schedule timezone (aware)
            local_now = datetime.now(tz)
            it = croniter(schedule.cron_expression, local_now)
            next_local = it.get_next(datetime)
            # Ensure timezone-awareness
            if next_local.tzinfo is None:
                next_local = next_local.replace(tzinfo=tz)
            # Convert next occurrence back to UTC
            return next_local.astimezone(timezone.utc)
        except Exception as e:
            print(f"Error computing next run for schedule {schedule.id}: {e}")
            return None
    if schedule.interval_seconds and schedule.interval_seconds > 0:
        return base_utc + timedelta(seconds=schedule.interval_seconds)
    # Run once immediately by default
    return None


def _run_script_on_server(db: Session, script: Script, server: Server, executed_by: int, parameters_used: Optional[str], timeout_sec: int | None) -> ScriptExecution:
    try:
        print(f"SCHEDULER: Starting execution of script '{script.name}' on server '{server.name}'")
        exec_row = ScriptExecution(
            script_id=script.id,
            server_id=server.id,
            executed_by=executed_by,
            parameters_used=parameters_used,
            status="running",
        )
        # Ensure SQLite assigns a fresh rowid
        try:
            exec_row.id = None
        except Exception:
            pass
        db.add(exec_row)
        db.commit()
        db.refresh(exec_row)
        
        # Ensure variables exist in this scope for all branches
        exec_cmd = None
        is_windows = False

        # Get virtual timeout duration from settings for infinite scripts
        from sqlalchemy.exc import OperationalError
        from sqlalchemy import text
        settings = db.query(Settings).first()
        if not settings:
            settings = Settings()
            db.add(settings)
            db.commit()
            db.refresh(settings)
        virtual_timeout_duration = settings.virtual_timeout_duration or 60

        # Initialize common variables and helpers before any auth path so they're always in scope
        exec_cmd = None
        is_windows = False
        # Effective timeout: default 60s; 0 means infinite (use 3600 sentinel), >0 uses value
        if script.per_server_timeout_seconds is None:
            eff_timeout = 60
        elif script.per_server_timeout_seconds == 0:
            eff_timeout = 3600  # infinite sentinel
        else:
            eff_timeout = script.per_server_timeout_seconds
        script_content = script.content or ''

        def _run_with_timeout(cmd: str, content_to_stdin: str | None = None, timeout_sec: int | None = eff_timeout, virtual_timeout: int = virtual_timeout_duration):
            print(f"DEBUG: _run_with_timeout called with timeout_sec={timeout_sec}, eff_timeout={eff_timeout}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            if content_to_stdin:
                stdin.write(content_to_stdin)
                try:
                    stdin.channel.shutdown_write()
                except Exception:
                    pass
            if is_windows:
                time.sleep(1)
            chan = stdout.channel
            start = time.time()
            out_chunks, err_chunks = [], []
            # Infinite (3600 sentinel) -> capture for virtual window
            if timeout_sec == 3600:
                max_read_time = virtual_timeout
                while time.time() - start < max_read_time:
                    if chan.recv_ready():
                        out_chunks.append(chan.recv(4096))
                    if chan.recv_stderr_ready():
                        err_chunks.append(chan.recv_stderr(4096))
                    if chan.exit_status_ready():
                        break
                    time.sleep(0.1)
                exit_code_local = 0
                out_text = b"".join(out_chunks).decode('utf-8', errors='ignore')
                err_text = b"".join(err_chunks).decode('utf-8', errors='ignore')
                return out_text, err_text, exit_code_local
            # Finite timeout -> wait for completion or timeout
            while True:
                if chan.recv_ready():
                    out_chunks.append(chan.recv(4096))
                if chan.recv_stderr_ready():
                    err_chunks.append(chan.recv_stderr(4096))
                if chan.exit_status_ready():
                    break
                if time.time() - start > (timeout_sec or eff_timeout):
                    try:
                        chan.close()
                    except Exception:
                        pass
                    raise TimeoutError(f"Command timed out after {timeout_sec}s")
                time.sleep(0.1)
            exit_code_local = chan.recv_exit_status()
            if is_windows:
                try:
                    out_text = b"".join(out_chunks).decode('cp1252', errors='ignore')
                except Exception:
                    out_text = b"".join(out_chunks).decode('utf-8', errors='ignore')
                try:
                    err_text = b"".join(err_chunks).decode('cp1252', errors='ignore')
                except Exception:
                    err_text = b"".join(err_chunks).decode('utf-8', errors='ignore')
            else:
                out_text = b"".join(out_chunks).decode('utf-8', errors='ignore')
                err_text = b"".join(err_chunks).decode('utf-8', errors='ignore')
            return out_text, err_text, exit_code_local

        # Check if this is an infinite script
        is_infinite = (script.per_server_timeout_seconds == 0)
        print(f"DEBUG: timeout_sec={timeout_sec}, script.per_server_timeout_seconds={script.per_server_timeout_seconds}, is_infinite={is_infinite}")

        # Start background task to mark as long_running after a configurable delay
        import threading
        import time
        # Read configurable delay from settings if available; default to 300s
        try:
            long_running_delay_seconds = getattr(settings, 'long_running_delay_seconds', 300) or 300
        except Exception:
            long_running_delay_seconds = 300

        def mark_long_running(execution_id: int):
            time.sleep(long_running_delay_seconds)
            try:
                # Check if still running
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
        
        long_running_thread = threading.Thread(target=mark_long_running, args=(exec_row.id,), daemon=True)
        long_running_thread.start()

        # Use the robust SSH connection manager
        from ssh_manager import get_ssh_connection, SSHConnectionError
        
        script_content = script.content or ''
        exec_cmd = None  # ensure defined for all branches
        
        try:
            with get_ssh_connection(server) as ssh:
                print(f"SSH connection successful for {server.name}")
                
                # Log successful authentication
                auth_logger.log_script_execution_auth(
                    script_name=script.name,
                    server_name=server.name,
                    server_ip=server.ip,
                    auth_method_used="ssh_manager",
                    success=True,
                    details={"scheduled": True}
                )
                
                # Detect Windows server and adjust commands accordingly
                is_windows = False
                # Prefer stored detected_os if available
                try:
                    if getattr(server, 'detected_os', None):
                        os_lower = (server.detected_os or '').lower()
                        if 'win' in os_lower or 'windows' in os_lower:
                            is_windows = True
                        else:
                            is_windows = False
                    else:
                        # Probe only if not set
                        try:
                            stdin, stdout, stderr = ssh.exec_command("echo %OS%")
                            os_output = stdout.read().decode('utf-8', errors='ignore').strip()
                            if 'Windows' in os_output or 'NT' in os_output:
                                is_windows = True
                        except Exception:
                            is_windows = 'windows' in (server.name or '').lower() or 'win' in (server.name or '').lower()
                except Exception:
                    is_windows = False
                
                # Precompute effective timeout and helper before branching
                # Effective timeout inside SSH branch: mirror logic above
                if script.per_server_timeout_seconds is None:
                    eff_timeout = 60
                elif script.per_server_timeout_seconds == 0:
                    eff_timeout = 3600
                else:
                    eff_timeout = script.per_server_timeout_seconds

                def _run_with_timeout(cmd: str, content_to_stdin: str | None = None, timeout_sec: int | None = eff_timeout, virtual_timeout: int = virtual_timeout_duration):
                    print(f"DEBUG: _run_with_timeout called with timeout_sec={timeout_sec}, eff_timeout={eff_timeout}")
                    stdin, stdout, stderr = ssh.exec_command(cmd)
                    if content_to_stdin:
                        stdin.write(content_to_stdin)
                        try:
                            stdin.channel.shutdown_write()
                        except Exception:
                            pass
                    if is_windows:
                        time.sleep(1)
                    chan = stdout.channel
                    start = time.time()
                    out_chunks, err_chunks = [], []
                    if timeout_sec == 3600:
                        max_read_time = virtual_timeout
                        while time.time() - start < max_read_time:
                            if chan.recv_ready():
                                out_chunks.append(chan.recv(4096))
                            if chan.recv_stderr_ready():
                                err_chunks.append(chan.recv_stderr(4096))
                            if chan.exit_status_ready():
                                break
                            time.sleep(0.1)
                        exit_code_local = 0
                        out_text = b"".join(out_chunks).decode('utf-8', errors='ignore')
                        err_text = b"".join(err_chunks).decode('utf-8', errors='ignore')
                        return out_text, err_text, exit_code_local
                    else:
                        while True:
                            if chan.recv_ready():
                                out_chunks.append(chan.recv(4096))
                            if chan.recv_stderr_ready():
                                err_chunks.append(chan.recv_stderr(4096))
                            if chan.exit_status_ready():
                                break
                            if time.time() - start > (timeout_sec or eff_timeout):
                                try:
                                    chan.close()
                                except Exception:
                                    pass
                                raise TimeoutError(f"Command timed out after {timeout_sec}s")
                            time.sleep(0.1)
                        exit_code_local = chan.recv_exit_status()
                    if is_windows:
                        try:
                            out_text = b"".join(out_chunks).decode('cp1252', errors='ignore')
                        except Exception:
                            out_text = b"".join(out_chunks).decode('utf-8', errors='ignore')
                        try:
                            err_text = b"".join(err_chunks).decode('cp1252', errors='ignore')
                        except Exception:
                            err_text = b"".join(err_chunks).decode('utf-8', errors='ignore')
                    else:
                        out_text = b"".join(out_chunks).decode('utf-8', errors='ignore')
                        err_text = b"".join(err_chunks).decode('utf-8', errors='ignore')
                    return out_text, err_text, exit_code_local

                # Handle infinite scripts first
                if is_infinite:
                    print("DEBUG: Executing infinite script path")
                    # Start remote command
                    if script.script_type == 'powershell':
                        import base64
                        encoded_script = base64.b64encode(script_content.encode('utf-16le')).decode('ascii')
                        ps_cmd = f"powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand {encoded_script}"
                        print(f"DEBUG: Executing PowerShell command: {ps_cmd[:100]}...")
                        stdin, stdout, stderr = ssh.exec_command(ps_cmd)
                    else:
                        print(f"DEBUG: Executing script content: {script_content[:200]}...")
                        stdin, stdout, stderr = ssh.exec_command(script_content)

                    # Background capture so scheduler loop doesn't block
                    def _bg_capture(execution_id: int, out_stream, err_stream, ssh_client):
                        try:
                            start_ts = time.time()
                            out_chunks_bg = []
                            err_chunks_bg = []
                            while time.time() - start_ts < virtual_timeout_duration:
                                if out_stream.channel.recv_ready():
                                    out_chunks_bg.append(out_stream.channel.recv(4096))
                                if err_stream.channel.recv_stderr_ready():
                                    err_chunks_bg.append(err_stream.channel.recv_stderr(4096))
                                if out_stream.channel.exit_status_ready():
                                    break
                                time.sleep(0.1)
                            out_text_bg = b"".join(out_chunks_bg).decode('utf-8', errors='ignore')
                            sess = SessionLocal()
                            try:
                                row = sess.query(ScriptExecution).filter(ScriptExecution.id == execution_id).first()
                                if row and row.status in ("running", "long_running"):
                                    row.output = out_text_bg
                                    sess.commit()
                            finally:
                                sess.close()
                        except Exception as e:
                            print(f"BG capture error: {e}")
                        finally:
                            try:
                                ssh_client.close()
                            except Exception:
                                pass

                    t = threading.Thread(target=_bg_capture, args=(exec_row.id, stdout, stderr, ssh), daemon=True)
                    t.start()

                    # Mark running and return immediately; long_running marker remains
                    exec_row.status = "running"
                    exec_row.error = None
                    db.commit()
                    db.refresh(exec_row)
                    return exec_row

                if is_windows:
                    # Windows-specific commands
                    if script.script_type == 'bash':
                        # For shell scripts on Windows, execute the content directly with cmd.exe
                        exec_cmd = "cmd.exe /c"
                        # Don't use stdin for shell scripts on Windows, execute directly
                        script_content = script_content.strip()
                    elif script.script_type == 'python':
                        exec_cmd = None  # handled separately
                    elif script.script_type == 'powershell':
                        import base64
                        # Encode the script content to base64 for -EncodedCommand
                        encoded_script = base64.b64encode(script_content.encode('utf-16le')).decode('ascii')
                        exec_cmd = f"powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand {encoded_script}"
                    else:
                        exec_cmd = "cmd.exe /c"
                else:
                    # Unix/Linux commands
                    try:
                        if script.script_type == 'bash':
                            exec_cmd = "/bin/bash -s"
                        elif script.script_type == 'python':
                            exec_cmd = None  # handled separately
                        elif script.script_type == 'powershell':
                            import base64
                            # Prefer pwsh or powershell if available; fallback to /bin/sh -s
                            encoded_script = base64.b64encode(script_content.encode('utf-16le')).decode('ascii')
                            stdin_detect, stdout_detect, stderr_detect = ssh.exec_command("command -v pwsh || command -v powershell")
                            ps_path = stdout_detect.read().decode('utf-8', errors='ignore').strip()
                            if ps_path:
                                ps_bin = 'pwsh' if 'pwsh' in ps_path else 'powershell'
                                exec_cmd = f"{ps_bin} -NoLogo -NoProfile -NonInteractive -EncodedCommand {encoded_script}"
                            else:
                                exec_cmd = "/bin/sh -s"
                        else:
                            exec_cmd = "/bin/sh -s"
                    except Exception:
                        exec_cmd = "/bin/sh -s"

                # Calculate effective timeout
                eff_timeout = script.per_server_timeout_seconds if script.per_server_timeout_seconds > 0 else 3600

                def _run_with_timeout(cmd: str, content_to_stdin: str | None = None, timeout_sec: int | None = eff_timeout, virtual_timeout: int = virtual_timeout_duration):
                    print(f"DEBUG: _run_with_timeout called with timeout_sec={timeout_sec}, eff_timeout={eff_timeout}")
                    # For infinite scripts (timeout_sec = 3600), capture output for virtual_timeout duration then return
                    if timeout_sec == 3600:  # This is our "infinite" script
                        stdin, stdout, stderr = ssh.exec_command(cmd)
                    else:
                        stdin, stdout, stderr = ssh.exec_command(cmd)
                    if content_to_stdin:
                        stdin.write(content_to_stdin)
                        try:
                            stdin.channel.shutdown_write()
                        except Exception:
                            pass
                    
                    # For Windows commands, we need to wait a bit longer for output
                    if is_windows:
                        time.sleep(1)  # Give Windows commands time to produce output
                    
                    chan = stdout.channel
                    start = time.time()
                    out_chunks, err_chunks = [], []
                    
                    # Read output more aggressively for Windows
                    if timeout_sec == 3600:  # This is our "infinite" script
                        # For infinite scripts, read output for virtual_timeout seconds then return what we have
                        max_read_time = virtual_timeout
                        while time.time() - start < max_read_time:
                            if chan.recv_ready():
                                chunk = chan.recv(4096)
                                out_chunks.append(chunk)
                            if chan.recv_stderr_ready():
                                chunk = chan.recv_stderr(4096)
                                err_chunks.append(chunk)
                            if chan.exit_status_ready():
                                break
                            time.sleep(0.1)
                        
                        # For infinite scripts, don't wait for exit status, just return what we captured
                        exit_code_local = 0  # Assume success for infinite scripts
                        
                        # Return immediately for infinite scripts
                        out_text = b"".join(out_chunks).decode('utf-8', errors='ignore')
                        err_text = b"".join(err_chunks).decode('utf-8', errors='ignore')
                        return out_text, err_text, exit_code_local
                    else:
                        # Normal timeout-based reading
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
                            time.sleep(0.1)  # Slightly longer sleep for Windows
                        
                        exit_code_local = chan.recv_exit_status()
                    
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
                    
                    # Ensure variables are always defined
                    if 'out_text' not in locals():
                        out_text = b"".join(out_chunks).decode('utf-8', errors='ignore')
                    if 'err_text' not in locals():
                        err_text = b"".join(err_chunks).decode('utf-8', errors='ignore')
                    return out_text, err_text, exit_code_local

            # Execute script (only for regular scripts, infinite scripts already handled above)
            if script.script_type == 'python':
                sftp = ssh.open_sftp()
                if is_windows:
                    remote_path = f"C:\\temp\\.sm_py_exec_{server.id}_{exec_row.id}.py"
                    out, err, exit_code = _run_with_timeout(f"python {remote_path} & del {remote_path}", timeout_sec=timeout_sec)
                else:
                    remote_path = f"/tmp/.sm_py_exec_{server.id}_{exec_row.id}.py"
                    out, err, exit_code = _run_with_timeout(f"python3 {remote_path}; rm -f {remote_path}", timeout_sec=timeout_sec)
                
                with sftp.file(remote_path, 'w') as f:
                    f.write(script_content)
                sftp.close()
            elif exec_cmd:
                if is_windows and script.script_type == 'bash':
                    full_cmd = f"{exec_cmd} {script_content}"
                    out, err, exit_code = _run_with_timeout(full_cmd, timeout_sec=timeout_sec)
                elif script.script_type == 'powershell':
                    out, err, exit_code = _run_with_timeout(exec_cmd, timeout_sec=timeout_sec)
                else:
                    out, err, exit_code = _run_with_timeout(exec_cmd, content_to_stdin=script_content, timeout_sec=timeout_sec)
            else:
                fallback_cmd = "cmd.exe /c" if is_windows else "/bin/sh -s"
                out, err, exit_code = _run_with_timeout(fallback_cmd, content_to_stdin=script_content, timeout_sec=timeout_sec)
            
                # Infinite scripts: keep as running and do not set completed_at
                if is_infinite or eff_timeout == 3600:
                    exec_row.status = "running"
                    exec_row.output = out
                    exec_row.error = None
                    # Do not set completed_at
                    db.commit()
                    db.refresh(exec_row)
                    return exec_row

                # Regular script completion
                exec_row.status = "completed" if exit_code == 0 else "failed"
                exec_row.output = out
                exec_row.error = err if exit_code != 0 else None
                exec_row.completed_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(exec_row)
                return exec_row
                
        except SSHConnectionError as e:
            print(f"SSH connection failed for {server.name}: {e}")
            
            # Log failed authentication
            auth_logger.log_script_execution_auth(
                script_name=script.name,
                server_name=server.name,
                server_ip=server.ip,
                auth_method_used="ssh_manager",
                success=False,
                details={"error": str(e), "scheduled": True}
            )
            
            exec_row.status = "failed"
            exec_row.error = f"SSH connection failed: {e}"
            exec_row.completed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(exec_row)
            return exec_row
            
    except Exception as e:
        print(f"SCHEDULER ERROR: {e}")
        import traceback
        traceback.print_exc()
        exec_row.status = "failed"
        exec_row.error = str(e)
        exec_row.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(exec_row)
        return exec_row


def _run_script_for_schedule(script_id: int, server_id: int, executed_by: Optional[int], timeout_sec: int | None):
    """Spawnable helper that opens its own DB session and runs the script on one server.
    Keeps the scheduler loop non-blocking when firing groups."""
    sess = None
    try:
        sess = SessionLocal()
        script = sess.query(Script).filter(Script.id == script_id).first()
        server = sess.query(Server).filter(Server.id == server_id).first()
        if not script or not server:
            return
        print(f"DEBUG: [group-launch] {datetime.utcnow().isoformat()}Z -> starting '{script.name}' on '{server.name}' (id={server.id})")
        _ = _run_script_on_server(sess, script, server, executed_by=executed_by or 1, parameters_used=None, timeout_sec=timeout_sec)
    except Exception:
        pass
    finally:
        try:
            if sess:
                sess.close()
        except Exception:
            pass


# APScheduler instance
_scheduler = None

def _execute_scheduled_script(schedule_id: int):
    """Execute a scheduled script - called by APScheduler"""
    db = SessionLocal()
    try:
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule or not schedule.enabled:
            return
            
        script = db.query(Script).filter(Script.id == schedule.script_id).first()
        if not script:
            return
            
        print(f"DEBUG: APScheduler executing schedule {schedule_id} - script '{script.name}' target_type={schedule.target_type} target_id={schedule.target_id}")
        
        # Update last_run_at
        schedule.last_run_at = _now_utc()
        db.commit()
        
        # Get tolerance settings
        tol_seconds = 30
        try:
            settings_row = db.query(Settings).first()
            if settings_row and getattr(settings_row, 'schedule_trigger_tolerance_seconds', None) is not None:
                tol_seconds = settings_row.schedule_trigger_tolerance_seconds or 30
        except Exception:
            tol_seconds = 30
            
        if schedule.target_type == 'server':
            srv = db.query(Server).filter(Server.id == schedule.target_id).first()
            if srv:
                print(f"DEBUG: Executing scheduled script '{script.name}' on server '{srv.name}'")
                # Idempotent guard per (script, server, tolerance bucket)
                key = _guard_key(script.id, srv.id, tol_seconds or 30)
                if not acquire_lock(key, ttl_seconds=max(120, tol_seconds*2)):
                    print(f"DEBUG: Skip duplicate for '{script.name}' on '{srv.name}' (lock)")
                else:
                    try:
                        q = get_queue("execute")
                        from tasks import execute_script_job
                        q.enqueue(execute_script_job, script.id, srv.id, schedule.created_by, None)
                    except Exception as e:
                        print(f"WARN: enqueue failed for '{srv.name}': {e}")
        elif schedule.target_type == 'group':
            grp = db.query(ServerGroup).filter(ServerGroup.id == schedule.target_id).first()
            if grp and grp.servers:
                servers_list = list(grp.servers)
                print(f"DEBUG: Firing group '{grp.name}' with {len(servers_list)} servers for script '{script.name}' at {datetime.utcnow().isoformat()}Z")
                for srv in servers_list:
                    try:
                        print(f"DEBUG: Queueing server '{srv.name}' (id={srv.id}) for immediate start")
                        key = _guard_key(script.id, srv.id, tol_seconds or 30)
                        if not acquire_lock(key, ttl_seconds=max(120, tol_seconds*2)):
                            print(f"DEBUG: Skip duplicate for '{script.name}' on '{srv.name}' (lock)")
                            continue
                        q = get_queue("execute")
                        from tasks import execute_script_job
                        q.enqueue(execute_script_job, script.id, srv.id, schedule.created_by, None)
                    except Exception as e:
                        print(f"WARN: Failed to enqueue server '{srv.name}': {e}")
    except Exception as e:
        print(f"ERROR: Failed to execute scheduled script {schedule_id}: {e}")
    finally:
        db.close()

def _execute_scheduled_workflow(workflow_id: int):
    """Execute a scheduled workflow - called by APScheduler"""
    db = SessionLocal()
    try:
        print(f"DEBUG: APScheduler executing workflow {workflow_id}")
        
        from routers.workflows import execute_workflow
        execute_workflow(db=db, workflow_id=workflow_id, triggered_by=None, context=None)
    except Exception as e:
        print(f"ERROR: Failed to execute scheduled workflow {workflow_id}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

def _job_listener(event):
    """APScheduler job event listener"""
    if event.exception:
        print(f"ERROR: Job {event.job_id} failed: {event.exception}")
    else:
        print(f"DEBUG: Job {event.job_id} executed successfully")

def _sync_schedules_to_apscheduler():
    """Sync database schedules to APScheduler jobs"""
    global _scheduler
    if not _scheduler:
        return
        
    db = SessionLocal()
    try:
        # Remove all existing schedule jobs
        for job in _scheduler.get_jobs():
            if job.id.startswith('schedule_') or job.id.startswith('workflow_'):
                _scheduler.remove_job(job.id)
        
        # Add enabled schedules
        schedules = db.query(Schedule).filter(Schedule.enabled == True).all()
        print(f"DEBUG: Syncing {len(schedules)} enabled schedules to APScheduler")
        
        for schedule in schedules:
            if schedule.cron_expression:
                try:
                    # Parse cron expression
                    parts = schedule.cron_expression.strip().split()
                    if len(parts) == 5:
                        minute, hour, day, month, day_of_week = parts
                        
                        # Create CronTrigger with schedule's timezone
                        tzname = (schedule.timezone or 'UTC').strip() or 'UTC'
                        try:
                            tz = ZoneInfo(tzname)
                        except Exception:
                            tz = ZoneInfo('UTC')
                            
                        trigger = CronTrigger(
                            minute=minute,
                            hour=hour,
                            day=day,
                            month=month,
                            day_of_week=day_of_week,
                            timezone=tz
                        )
                        
                        job_id = f"schedule_{schedule.id}"
                        _scheduler.add_job(
                            _execute_scheduled_script,
                            trigger=trigger,
                            args=[schedule.id],
                            id=job_id,
                            replace_existing=True
                        )
                        print(f"DEBUG: Added schedule job {job_id} with cron '{schedule.cron_expression}' in timezone '{tzname}'")
                        
                except Exception as e:
                    print(f"ERROR: Failed to add schedule {schedule.id}: {e}")
                    
        # Add scheduled workflows
        workflows = db.query(Workflow).filter(Workflow.trigger_type == 'schedule', Workflow.schedule_cron.isnot(None)).all()
        print(f"DEBUG: Syncing {len(workflows)} scheduled workflows to APScheduler")
        
        for workflow in workflows:
            try:
                # Parse cron expression
                parts = workflow.schedule_cron.strip().split()
                if len(parts) == 5:
                    minute, hour, day, month, day_of_week = parts
                    
                    # Create CronTrigger with workflow's timezone
                    tzname = (workflow.schedule_timezone or 'UTC').strip() or 'UTC'
                    try:
                        tz = ZoneInfo(tzname)
                    except Exception:
                        tz = ZoneInfo('UTC')
                        
                    trigger = CronTrigger(
                        minute=minute,
                        hour=hour,
                        day=day,
                        month=month,
                        day_of_week=day_of_week,
                        timezone=tz
                    )
                    
                    job_id = f"workflow_{workflow.id}"
                    _scheduler.add_job(
                        _execute_scheduled_workflow,
                        trigger=trigger,
                        args=[workflow.id],
                        id=job_id,
                        replace_existing=True
                    )
                    print(f"DEBUG: Added workflow job {job_id} with cron '{workflow.schedule_cron}' in timezone '{tzname}'")
                    
            except Exception as e:
                print(f"ERROR: Failed to add workflow {workflow.id}: {e}")
                
    finally:
        db.close()

def scheduler_loop(stop_event: threading.Event):
    """Legacy scheduler loop - now just syncs schedules to APScheduler"""
    print("DEBUG: Scheduler loop started (APScheduler mode)")
    global _scheduler
    
    # Initialize APScheduler
    jobstores = {
        'default': SQLAlchemyJobStore(url='sqlite:///apscheduler_jobs.db')
    }
    executors = {
        'default': ThreadPoolExecutor(max_workers=20)
    }
    job_defaults = {
        'coalesce': False,
        'max_instances': 1
    }
    
    _scheduler = BackgroundScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
        timezone='UTC'
    )
    
    # Add job listener
    _scheduler.add_listener(_job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    
    # Start scheduler
    _scheduler.start()
    print("DEBUG: APScheduler started")
    
    # Initial sync
    _sync_schedules_to_apscheduler()
    
    # Keep running and sync periodically
    while not stop_event.is_set():
        try:
            # Sync schedules every 30 seconds
            stop_event.wait(30.0)
            if not stop_event.is_set():
                _sync_schedules_to_apscheduler()
        except Exception as e:
            print(f"ERROR: Scheduler loop error: {e}")
            stop_event.wait(5.0)  # Wait before retrying
    
    # Shutdown APScheduler
    if _scheduler:
        _scheduler.shutdown()
        print("DEBUG: APScheduler stopped")


_scheduler_thread = None
_stop_event = threading.Event()


def sync_schedules():
    """Manually sync schedules to APScheduler (call after schedule changes)"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _sync_schedules_to_apscheduler()

def get_next_run_time(workflow_id: int) -> Optional[datetime]:
    """Get next run time for a workflow from APScheduler"""
    global _scheduler
    if not _scheduler or not _scheduler.running:
        return None
    
    job_id = f"workflow_{workflow_id}"
    try:
        job = _scheduler.get_job(job_id)
        if job and job.next_run_time:
            return job.next_run_time
    except Exception:
        pass
    return None

def start_scheduler():
    global _scheduler_thread, _stop_event
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _stop_event = threading.Event()
    _scheduler_thread = threading.Thread(target=scheduler_loop, args=(_stop_event,), daemon=True)
    _scheduler_thread.start()


def stop_scheduler():
    global _stop_event, _scheduler
    try:
        _stop_event.set()
        if _scheduler and _scheduler.running:
            _scheduler.shutdown()
    except Exception:
        pass


def _guard_key(script_id: int, server_id: int, window_sec: int) -> str:
    from math import floor
    now_bucket = floor(time.time() / max(1, window_sec))
    return f"sched:lock:{script_id}:{server_id}:{now_bucket}"

# In places where scheduled execution is launched, before _run_script_on_server call, acquire the lock:
# Example usage (documentation-only snippet to indicate guard placement):
# key = _guard_key(script.id, server.id, getattr(settings, 'schedule_trigger_tolerance_seconds', 30) or 30)
# if not acquire_lock(key, ttl_seconds=120):
#     logger.info(f"skip duplicate launch for {script.name} on {server.name}")
#     return
# try:
#     # proceed with run
# finally:
#     release_lock(key)


