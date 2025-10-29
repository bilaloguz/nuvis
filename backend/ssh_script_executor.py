"""
SSH Script Executor

This module provides a robust script execution function that uses the SSH connection manager.
"""

import time
from typing import Tuple, Optional
from datetime import datetime, timezone
from sqlalchemy import func

from models import Script, Server, ScriptExecution
from ssh_manager import get_ssh_connection, SSHConnectionError
from utils_logging import get_logger

logger = get_logger(__name__)

def execute_script_on_server(
    script: Script, 
    server: Server, 
    execution: ScriptExecution,
    is_infinite: bool = False,
    virtual_timeout_duration: int = 60
) -> Tuple[str, str, int]:
    """
    Execute a script on a server using the robust SSH connection manager.
    
    Returns:
        Tuple of (output, error, exit_code)
    """
    try:
        with get_ssh_connection(server) as ssh:
            logger.info(f"SSH connection successful for {server.name}")
            
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
                is_windows = 'windows' in (server.name or '').lower() or 'win' in (server.name or '').lower()
            
            # Precompute effective timeout and helper before branching
            eff_timeout = script.per_server_timeout_seconds if (script.per_server_timeout_seconds or 0) > 0 else 3600
            script_content = script.content or ''

            def _run_with_timeout(cmd: str, content_to_stdin: str | None = None, timeout_sec: int | None = None, virtual_timeout: int = virtual_timeout_duration):
                logger.debug(f"_run_with_timeout called with timeout_sec={timeout_sec}, eff_timeout={eff_timeout}")
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
                    except:
                        out_text = b"".join(out_chunks).decode('utf-8', errors='ignore')
                    try:
                        err_text = b"".join(err_chunks).decode('cp1252', errors='ignore')
                    except:
                        err_text = b"".join(err_chunks).decode('utf-8', errors='ignore')
                else:
                    out_text = b"".join(out_chunks).decode('utf-8', errors='ignore')
                    err_text = b"".join(err_chunks).decode('utf-8', errors='ignore')
                return out_text, err_text, exit_code_local
            
            # Execute script
            if is_infinite:
                # For infinite scripts: run command, capture output for 60 seconds, keep running
                if script.script_type == 'powershell':
                    stdin, stdout, stderr = ssh.exec_command(script_content)
                else:
                    stdin, stdout, stderr = ssh.exec_command(script_content)
                
                # Capture output for 60 seconds
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
                exit_code = 0  # Infinite scripts don't have a real exit code
            else:
                # Regular script execution
                if script.script_type == 'python':
                    # For Python scripts, write to a temporary file and execute
                    remote_path = f"/tmp/script_{execution.id}.py"
                    sftp = ssh.open_sftp()
                    with sftp.file(remote_path, 'w') as f:
                        f.write(script_content)
                    sftp.close()
                    out, err, exit_code = _run_with_timeout(f"python3 {remote_path}; rm -f {remote_path}")
                elif script.script_type == 'powershell':
                    out, err, exit_code = _run_with_timeout(script_content)
                else:
                    out, err, exit_code = _run_with_timeout("/bin/sh -s", content_to_stdin=script_content)
            
            return out, err, exit_code
            
    except SSHConnectionError as e:
        logger.error(f"SSH connection failed for {server.name}: {e}")
        raise e
    except Exception as e:
        logger.error(f"Script execution failed for {server.name}: {e}")
        raise e


