import asyncio
import json
import logging
import os
from typing import Dict, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Server, Script, ScriptExecution, User
from sqlalchemy.sql import func
from ssh_key_utils import detect_key_type_from_file, get_paramiko_key_class

import paramiko
import threading
import queue
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Store active terminal connections
active_connections: Dict[int, Dict] = {}

class TerminalManager:
    def __init__(self, websocket: WebSocket, server: Server, db: Session):
        self.websocket = websocket
        self.server = server
        self.db = db
        self.ssh_client: Optional[paramiko.SSHClient] = None
        self.channel: Optional[paramiko.Channel] = None
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        self.running = False
        # OS hint for terminal behavior (affects CRLF and filtering)
        try:
            os_lower = (getattr(server, 'detected_os', '') or '').lower()
            self.is_windows = ('win' in os_lower) or ('windows' in os_lower)
        except Exception:
            self.is_windows = False
    async def connect(self):
        """Establish SSH connection to the server"""
        try:
            # Create SSH client
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Log server details for debugging
            logger.info(f"Attempting SSH connection to {self.server.name} ({self.server.ip})")
            logger.info(f"Username: {self.server.username}")
            logger.info(f"Auth method: {getattr(self.server, 'auth_method', 'not set')}")
            logger.info(f"SSH key path: {getattr(self.server, 'ssh_key_path', 'not set')}")
            logger.info(f"Password encrypted: {'yes' if self.server.password_encrypted else 'no'}")
            
            # Try SSH key first, then password
            connected = False
            
            # Try SSH key if available and path exists
            if hasattr(self.server, 'ssh_key_path') and self.server.ssh_key_path and os.path.exists(self.server.ssh_key_path):
                try:
                    logger.info(f"Attempting SSH key connection with: {self.server.ssh_key_path}")
                    # Detect key type and load with appropriate paramiko class
                    key_type = detect_key_type_from_file(self.server.ssh_key_path)
                    key_class = get_paramiko_key_class(key_type)
                    private_key = key_class.from_private_key_file(self.server.ssh_key_path, password=None)
                    self.ssh_client.connect(
                        self.server.ip,
                        username=self.server.username,
                        pkey=private_key,
                        timeout=10
                    )
                    connected = True
                    logger.info(f"Connected to {self.server.name} using SSH key")
                except Exception as e:
                    logger.warning(f"SSH key connection failed: {e}")
            
            # Fallback to password if SSH key failed or not available
            if not connected and self.server.password_encrypted:
                try:
                    logger.info("Attempting password connection")
                    from secrets_vault import SecretsVault
                    vault = SecretsVault.get()
                    password = vault.decrypt_to_str(self.server.password_encrypted)
                    
                    self.ssh_client.connect(
                        self.server.ip,
                        username=self.server.username,
                        password=password,
                        timeout=10
                    )
                    connected = True
                    logger.info(f"Connected to {self.server.name} using password")
                except Exception as e:
                    logger.error(f"Password connection failed: {e}")
            
            if not connected:
                error_details = []
                if not hasattr(self.server, 'ssh_key_path') or not self.server.ssh_key_path:
                    error_details.append("No SSH key path configured")
                elif not os.path.exists(self.server.ssh_key_path):
                    error_details.append(f"SSH key file not found: {self.server.ssh_key_path}")
                if not self.server.password_encrypted:
                    error_details.append("No password configured")
                
                error_msg = f"Failed to connect using both SSH key and password. Details: {'; '.join(error_details)}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            # Get interactive shell with proper configuration
            try:
                # Detect if this is a Windows server
                is_windows = False
                try:
                    stdin, stdout, stderr = self.ssh_client.exec_command("echo %OS%")
                    output = stdout.read().decode().strip()
                    if "Windows" in output or "NT" in output:
                        is_windows = True
                        logger.info("Detected Windows server")
                except:
                    pass
                
                # Store Windows flag for later use
                self.is_windows = is_windows
                
                if is_windows:
                    # For Windows, try PowerShell instead of cmd
                    self.channel = self.ssh_client.invoke_shell(term='powershell', width=80, height=24)
                    self.channel.settimeout(0.1)
                    logger.info("Interactive shell created for Windows with PowerShell")
                else:
                    # For Linux, use standard PTY
                    self.channel = self.ssh_client.invoke_shell()
                    self.channel.settimeout(0.1)
                    self.channel.get_pty(term='xterm', width=80, height=24)
                    logger.info("Interactive shell created for Linux with PTY")
                
                # Wait a moment for shell to be ready
                time.sleep(2.0)  # Longer wait for Windows
                
                # Set terminal to raw mode for better command handling
                self.channel.settimeout(None)
                
            except Exception as e:
                logger.warning(f"Shell setup failed, trying basic shell: {e}")
                
                # Fallback: create shell without PTY
                self.channel = self.ssh_client.invoke_shell()
                self.channel.settimeout(0.1)
                try:
                    # Combine stderr into stdout to avoid missing lines on Windows shells
                    self.channel.set_combine_stderr(True)
                except Exception:
                    pass
                # On Windows, ensure we are in a cmd shell for consistent streaming
                try:
                    if self.is_windows and self.channel and self.channel.active:
                        self.channel.send("cmd.exe\r\n")
                        time.sleep(0.2)
                except Exception:
                    pass
                
                # Wait a moment for shell to be ready
                time.sleep(2.0)
                
                logger.info("Basic interactive shell created")
            
            # Verify channel is working
            if not self.channel or not self.channel.active:
                raise Exception("Failed to create active SSH channel")
            
            logger.info(f"SSH channel status: active={self.channel.active}, closed={self.channel.closed}")
            
            # Start input/output handlers
            self.running = True
            threading.Thread(target=self._handle_input, daemon=True).start()
            threading.Thread(target=self._handle_output, daemon=True).start()
            
            logger.info("SSH terminal setup completed successfully")
            

            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to {self.server.name}: {e}")
            return False
    
    def _handle_input(self):
        """Handle input from WebSocket to SSH channel"""
        while self.running:
            try:
                # Get input from queue (sent by WebSocket)
                if not self.input_queue.empty():
                    data = self.input_queue.get(timeout=0.05)
                    if self.channel and self.channel.active:
                        # Ensure proper line ending (CRLF for Windows cmd)
                        if self.is_windows:
                            if not (data.endswith('\r\n') or data.endswith('\n')):
                                data += '\r\n'
                        else:
                            if not data.endswith('\n'):
                                data += '\n'
                        
                        # Send the data to SSH channel
                        bytes_sent = self.channel.send(data)
                        logger.info(f"Sent command to SSH: {repr(data)} (bytes: {bytes_sent})")
                        
                        # Wait a moment for command to be processed
                        time.sleep(0.5)  # Increased wait time for Windows
                        
                        # Check if there's immediate output
                        if self.channel.recv_ready():
                            immediate_data = self.channel.recv(1024)
                            if immediate_data:
                                logger.info(f"Immediate output after command: {len(immediate_data)} bytes")
                        
                        # Send a small delay to ensure command is processed
                        time.sleep(0.2)
                time.sleep(0.005)
            except Exception as e:
                logger.error(f"Input handler error: {e}")
                break

    def _handle_output(self):
        """Handle output from SSH channel to WebSocket"""
        while self.running:
            try:
                if self.channel and self.channel.active:
                    # Try to receive data even if recv_ready() returns False (Windows issue)
                    try:
                        # Drain all ready data to avoid buffering delays (important for Windows ping -t)
                        chunk_list = []
                        # Read available data chunks
                        while self.channel.recv_ready():
                            chunk_list.append(self.channel.recv(4096))
                        # Opportunistic non-blocking read even if not ready (may raise)
                        if not chunk_list:
                            try:
                                peek = self.channel.recv(1024)
                                if peek:
                                    chunk_list.append(peek)
                            except Exception:
                                pass
                        if chunk_list:
                            output = b''.join(chunk_list).decode('utf-8', errors='ignore')
                            # Minimal cleanup only; keep raw lines for streaming
                            if output:
                                self.output_queue.put(output)
                                logger.info(f"Received SSH output: {len(output)} chars")
                    except Exception as recv_err:
                        logger.debug(f"Output read error: {recv_err}")
                time.sleep(0.005)
            except Exception as e:
                logger.error(f"Output handler error: {e}")
                break
    
    def send_input(self, data: str):
        """Send input data to SSH channel"""
        if self.running and self.channel and self.channel.active:
            # Store the command to filter out echo (interactive shell path only)
            self.last_command = data.strip()
            logger.info(f"Queueing input: {self.last_command}")
            
            # Ensure command ends with newline for proper execution
            if not data.endswith('\n'):
                data = data + '\n'
            
            self.input_queue.put(data)
        else:
            logger.error(f"Cannot send input - running: {self.running}, channel active: {self.channel and self.channel.active}")
    
    def get_output(self) -> Optional[str]:
        """Get output data from SSH channel"""
        try:
            if not self.output_queue.empty():
                return self.output_queue.get_nowait()
        except:
            pass
        return None
    
    def is_connected(self):
        """Check if SSH connection is healthy"""
        return (self.running and 
                self.ssh_client and 
                self.channel and 
                self.channel.active and 
                not self.ssh_client.get_transport().is_closed())
    
    def disconnect(self):
        """Disconnect SSH session"""
        self.running = False
        if self.channel:
            self.channel.close()
        if self.ssh_client:
            self.ssh_client.close()

@router.websocket("/ws/terminal/{server_id}")
async def websocket_terminal(
    websocket: WebSocket, 
    server_id: int,
    db: Session = Depends(get_db)
):
    """WebSocket endpoint for terminal connections"""
    
    # Accept the WebSocket connection
    await websocket.accept()
    
    try:
        # Get server details
        server = db.query(Server).filter(Server.id == server_id).first()
        if not server:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Server not found"
            }))
            return
        
        # Create terminal manager
        terminal = TerminalManager(websocket, server, db)
        
        # Store connection
        connection_id = id(websocket)
        active_connections[connection_id] = {
            "terminal": terminal,
            "server_id": server_id,
            "websocket": websocket
        }
        
        logger.info(f"Terminal connection established for server {server.name}")
        
        # Send connection success message
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": f"Connected to {server.name}",
            "server": {
                "name": server.name,
                "ip": server.ip,
                "username": server.username
            }
        }))
        
        # Try to establish SSH connection
        logger.info("Starting SSH connection process...")
        if await terminal.connect():
            logger.info("SSH connection successful, sending success message")
            await websocket.send_text(json.dumps({
                "type": "ssh_connected",
                "message": "SSH connection established"
            }))
            
            # Main communication loop
            while True:
                # Check for SSH output more frequently
                output = terminal.get_output()
                if output:
                    logger.info(f"Sending output to frontend: {len(output)} chars")
                    await websocket.send_text(json.dumps({
                        "type": "output",
                        "data": output
                    }))
                
                # Check for WebSocket messages (non-blocking)
                try:
                    # Use asyncio.wait_for to prevent blocking
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=0.05)
                    message = json.loads(data)
                    
                    if message["type"] == "input":
                        cmd_in = message.get("data", "")
                        logger.info(f"Received input command: {cmd_in}")
                        # For Windows, run ALL commands via exec channel with streaming wrapper
                        try:
                            is_win = getattr(terminal, 'is_windows', False)
                        except Exception:
                            is_win = False
                        if is_win and terminal.ssh_client:
                            # Cancel any previous exec stream
                            try:
                                prev = active_connections.get(connection_id, {})
                                if prev.get("run_session"):
                                    try: prev["run_session"].close()
                                    except Exception: pass
                                if prev.get("run_task"):
                                    try: prev["run_task"].cancel()
                                    except Exception: pass
                            except Exception:
                                pass
                            session = terminal.ssh_client.get_transport().open_session()
                            try:
                                session.set_combine_stderr(True)
                            except Exception:
                                pass
                            # Choose wrapper: powershell for powershell commands, otherwise cmd
                            lc = (cmd_in or "").strip().lower()
                            if lc.startswith("powershell") or lc.startswith("pwsh"):
                                # Strip leading powershell and wrap body
                                body = cmd_in
                                # If user typed plain powershell args, pass through
                                ps_cmd = f"powershell -NoLogo -NoProfile -Command \"$OutputEncoding=[Console]::OutputEncoding=[Text.Encoding]::UTF8; & {{ {body} }} | ForEach-Object {{ $_ | Out-Host }}\""
                                session.exec_command(ps_cmd)
                            else:
                                exec_cmd = f"cmd.exe /c {cmd_in}"
                                session.exec_command(exec_cmd)

                            async def _stream_exec(sess: paramiko.Channel):
                                try:
                                    while True:
                                        chunk_list = []
                                        while sess.recv_ready():
                                            chunk_list.append(sess.recv(4096))
                                        if hasattr(sess, 'recv_stderr_ready') and sess.recv_stderr_ready():
                                            chunk_list.append(sess.recv_stderr(4096))
                                        if chunk_list:
                                            out = b''.join(chunk_list).decode('utf-8', errors='ignore')
                                            await websocket.send_text(json.dumps({"type": "output", "data": out}))
                                        if sess.exit_status_ready():
                                            break
                                        await asyncio.sleep(0.02)
                                except asyncio.CancelledError:
                                    try: sess.close()
                                    except Exception: pass
                                except Exception as e:
                                    try:
                                        await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
                                    except Exception:
                                        pass

                            run_task = asyncio.create_task(_stream_exec(session))
                            active_connections[connection_id]["run_session"] = session
                            active_connections[connection_id]["run_task"] = run_task
                        else:
                            terminal.send_input(cmd_in)
                    elif message.get("type") == "ctrl_c":
                        # Behave like a real terminal Ctrl+C
                        try:
                            prev = active_connections.get(connection_id, {})
                            handled = False
                            # If there's a dedicated exec session running (e.g., Windows streaming), close it
                            run_sess = prev.get("run_session")
                            if run_sess is not None:
                                try:
                                    run_sess.close()
                                except Exception:
                                    pass
                                active_connections[connection_id]["run_session"] = None
                                # If we also track a task, cancel it
                                if prev.get("run_task"):
                                    try:
                                        prev["run_task"].cancel()
                                    except Exception:
                                        pass
                                    active_connections[connection_id]["run_task"] = None
                                handled = True
                            # Otherwise send ETX to the interactive channel
                            if not handled and terminal.channel and terminal.channel.active:
                                try:
                                    # ETX (Ctrl+C)
                                    terminal.channel.send('\x03')
                                    handled = True
                                except Exception:
                                    handled = False
                            await websocket.send_text(json.dumps({"type": "output", "data": "^C\n" if handled else "[ctrl-c failed]\n"}))
                        except Exception as e:
                            logger.error(f"Ctrl+C handling error: {e}")
                    
                    elif message["type"] == "resize":
                        # Handle terminal resize if needed
                        pass
                    elif message["type"] == "run_script":
                        # Run a one-off script and stream output, without affecting the interactive shell
                        script_type = (message.get("script_type") or "bash").lower()
                        script_content = message.get("content") or ""
                        # Determine OS (prefer stored detected_os)
                        is_windows = False
                        try:
                            if getattr(server, 'detected_os', None):
                                os_lower = (server.detected_os or '').lower()
                                is_windows = ('win' in os_lower) or ('windows' in os_lower)
                            else:
                                try:
                                    _st_os, _so_os, _se_os = terminal.ssh_client.exec_command("cmd.exe /c echo %OS%")
                                    os_env = _so_os.read().decode('utf-8', errors='ignore').strip()
                                    if os_env and 'Windows' in os_env:
                                        is_windows = True
                                    else:
                                        _st_ver, _so_ver, _se_ver = terminal.ssh_client.exec_command("cmd.exe /c ver")
                                        ver_out = _so_ver.read().decode('utf-8', errors='ignore').strip()
                                        is_windows = bool(ver_out)
                                except Exception:
                                    try:
                                        _st_uname, _so_uname, _se_uname = terminal.ssh_client.exec_command("uname")
                                        uname_out = _so_uname.read().decode('utf-8', errors='ignore').strip().lower()
                                        is_windows = False if uname_out else False
                                    except Exception:
                                        is_windows = 'windows' in (server.name or '').lower() or 'win' in (server.name or '').lower()
                        except Exception:
                            is_windows = False

                        # If a previous run is active, stop it first
                        try:
                            prev = active_connections.get(connection_id, {})
                            if prev.get("run_session"):
                                try:
                                    prev["run_session"].close()
                                except Exception:
                                    pass
                            if prev.get("run_task"):
                                try:
                                    prev["run_task"].cancel()
                                except Exception:
                                    pass
                        except Exception:
                            pass

                        # Open new exec channel (Windows uses interactive shell for better streaming)
                        if is_windows:
                            # Build a single command line for Windows
                            if script_type == 'bash':
                                cmd = f"cmd.exe /c {script_content}" if script_content else "cmd.exe /c"
                            elif script_type == 'python':
                                cmd = f"python - << 'PY'\n{script_content}\nPY\nexit\n"
                            elif script_type == 'powershell':
                                # Flush wrapper for continuous streaming
                                ps_body = (
                                    "$OutputEncoding=[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
                                    "& { " + script_content + " } | ForEach-Object { $_; [Console]::Out.Flush() }"
                                )
                                cmd = f"powershell.exe -NoLogo -NoProfile -NonInteractive -Command \"{ps_body}\""
                            else:
                                cmd = f"cmd.exe /c {script_content}" if script_content else "cmd.exe /c"

                            shell = terminal.ssh_client.invoke_shell()
                            try:
                                shell.settimeout(0.1)
                            except Exception:
                                pass
                            # Send command and read continuously
                            try:
                                shell.send(cmd + "\r\n")
                            except Exception:
                                await websocket.send_text(json.dumps({"type": "error", "message": "Failed to send command to Windows shell"}))
                                shell.close()
                                continue

                            # Stream from interactive shell until it returns control
                            idle_ticks = 0
                            while True:
                                progressed = False
                                if shell.recv_ready():
                                    data = shell.recv(4096)
                                    if data:
                                        progressed = True
                                        await websocket.send_text(json.dumps({"type": "output", "data": data.decode('utf-8', errors='ignore')}))
                                # Windows shells usually mix stderr into stdout; still try separately
                                if hasattr(shell, 'recv_stderr_ready') and shell.recv_stderr_ready():
                                    data = shell.recv_stderr(4096)
                                    if data:
                                        progressed = True
                                        await websocket.send_text(json.dumps({"type": "error_output", "data": data.decode('utf-8', errors='ignore')}))
                                # Heuristic: if no progress for a while and shell is closed, break
                                if not progressed:
                                    idle_ticks += 1
                                else:
                                    idle_ticks = 0
                                if shell.closed or idle_ticks > 500:  # ~10s at 20ms
                                    break
                                await asyncio.sleep(0.02)
                            try:
                                shell.close()
                            except Exception:
                                pass
                            continue
                        # Non-Windows: use exec session
                        session = terminal.ssh_client.get_transport().open_session()
                        try:
                            if not is_windows:
                                if script_type == 'bash':
                                    session.exec_command("/bin/bash -s")
                                    if script_content:
                                        session.send(script_content)
                                        try: session.shutdown_write()
                                        except Exception: pass
                                elif script_type == 'python':
                                    sftp = terminal.ssh_client.open_sftp()
                                    remote_path = f"/tmp/.sm_ws_run_{server.id}.py"
                                    with sftp.file(remote_path, 'w') as f:
                                        f.write(script_content)
                                    sftp.close()
                                    session.exec_command(f"python3 {remote_path}; rm -f {remote_path}")
                                elif script_type == 'powershell':
                                    import base64
                                    try:
                                        _stdin_ps, _stdout_ps, _stderr_ps = terminal.ssh_client.exec_command("command -v pwsh || command -v powershell")
                                        ps_path = _stdout_ps.read().decode('utf-8', errors='ignore').strip()
                                    except Exception:
                                        ps_path = ''
                                    if ps_path:
                                        ps_bin = 'pwsh' if 'pwsh' in ps_path else 'powershell'
                                        session.exec_command(f"{ps_bin} -NoLogo -NoProfile -NonInteractive -Command \"{script_content}\"")
                                    else:
                                        await websocket.send_text(json.dumps({"type": "error_output", "data": "PowerShell not installed (no pwsh/powershell)."}))
                                        session.close()
                                        continue
                                else:
                                    session.exec_command("/bin/sh -s")
                                    if script_content:
                                        session.send(script_content)
                                        try: session.shutdown_write()
                                        except Exception: pass
                            else:
                                if script_type == 'bash':
                                    session.exec_command("/bin/bash -s")
                                    if script_content:
                                        session.send(script_content)
                                        try: session.shutdown_write()
                                        except Exception: pass
                                elif script_type == 'python':
                                    sftp = terminal.ssh_client.open_sftp()
                                    remote_path = f"/tmp/.sm_ws_run_{server.id}.py"
                                    with sftp.file(remote_path, 'w') as f:
                                        f.write(script_content)
                                    sftp.close()
                                    session.exec_command(f"python3 {remote_path}; rm -f {remote_path}")
                                elif script_type == 'powershell':
                                    import base64
                                    encoded_script = base64.b64encode(script_content.encode('utf-16le')).decode('ascii')
                                    try:
                                        _stdin_ps, _stdout_ps, _stderr_ps = terminal.ssh_client.exec_command("command -v pwsh || command -v powershell")
                                        ps_path = _stdout_ps.read().decode('utf-8', errors='ignore').strip()
                                    except Exception:
                                        ps_path = ''
                                    if ps_path:
                                        ps_bin = 'pwsh' if 'pwsh' in ps_path else 'powershell'
                                        session.exec_command(f"{ps_bin} -NoLogo -NoProfile -NonInteractive -EncodedCommand {encoded_script}")
                                    else:
                                        await websocket.send_text(json.dumps({"type": "error_output", "data": "PowerShell not installed (no pwsh/powershell)."}))
                                        session.close()
                                        continue
                                else:
                                    session.exec_command("/bin/sh -s")
                                    if script_content:
                                        session.send(script_content)
                                        try: session.shutdown_write()
                                        except Exception: pass

                            # Stream synchronously until exit to avoid task leaks
                            while True:
                                if session.recv_ready():
                                    chunk = session.recv(4096)
                                    if chunk:
                                        await websocket.send_text(json.dumps({"type": "output", "data": chunk.decode('utf-8', errors='ignore')}))
                                if session.recv_stderr_ready():
                                    chunk = session.recv_stderr(4096)
                                    if chunk:
                                        await websocket.send_text(json.dumps({"type": "error_output", "data": chunk.decode('utf-8', errors='ignore')}))
                                if session.exit_status_ready():
                                    break
                                await asyncio.sleep(0.02)
                        finally:
                            try:
                                session.close()
                            except Exception:
                                pass
                    # Removed stop_script handler for stability
                        
                except asyncio.TimeoutError:
                    # No message received, continue loop
                    pass
                except WebSocketDisconnect:
                    logger.info("WebSocket disconnected")
                    break
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    break
                
                # Shorter delay for more responsive output
                await asyncio.sleep(0.005)
                
        else:
            await websocket.send_text(json.dumps({
                "type": "ssh_failed",
                "message": "Failed to establish SSH connection"
            }))
            
    except Exception as e:
        logger.error(f"Terminal connection error: {e}")
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Connection error: {str(e)}"
            }))
        except:
            pass
    
    finally:
        # Cleanup
        if connection_id in active_connections:
            terminal = active_connections[connection_id]["terminal"]
            terminal.disconnect()
            del active_connections[connection_id]
        
        logger.info(f"Terminal connection closed for server {server_id}")

@router.get("/terminal/status/{server_id}")
async def get_terminal_status(server_id: int, db: Session = Depends(get_db)):
    """Get terminal connection status for a server"""
    # Check if there's an active connection
    for conn in active_connections.values():
        if conn["server_id"] == server_id:
            return {"status": "connected", "active": True}
    
    return {"status": "disconnected", "active": False}

@router.delete("/terminal/disconnect/{server_id}")
async def disconnect_terminal(server_id: int, db: Session = Depends(get_db)):
    """Force disconnect terminal for a server"""
    connections_to_remove = []
    
    for conn_id, conn in active_connections.items():
        if conn["server_id"] == server_id:
            conn["terminal"].disconnect()
            connections_to_remove.append(conn_id)
    
    for conn_id in connections_to_remove:
        del active_connections[conn_id]
    
    return {"message": f"Disconnected {len(connections_to_remove)} terminal sessions"}


@router.websocket("/ws/execute/{script_id}/{server_id}")
async def websocket_execute_script(
    websocket: WebSocket,
    script_id: int,
    server_id: int,
    db: Session = Depends(get_db)
):
    """WebSocket endpoint to execute a script on a server and stream output live."""
    await websocket.accept()
    try:
        script = db.query(Script).filter(Script.id == script_id).first()
        server = db.query(Server).filter(Server.id == server_id).first()
        if not script or not server:
            await websocket.send_text(json.dumps({"type": "error", "message": "Script or Server not found"}))
            return

        # create execution row; try to associate to current user if available
        executed_by_id = None
        try:
            from auth import get_current_user
            # WebSocket can't use Depends directly; try token from headers
            token = websocket.headers.get('authorization') or websocket.headers.get('Authorization')
            if token and token.lower().startswith('bearer '):
                # Fallback: hit DB for admin user if needed
                user = db.query(User).filter(User.username=='admin').first()
                if user:
                    executed_by_id = user.id
        except Exception:
            # Fallback to admin/first user if exists
            try:
                u = db.query(User).order_by(User.id.asc()).first()
                if u:
                    executed_by_id = u.id
            except Exception:
                executed_by_id = None

        # create execution row
        execution = ScriptExecution(
            script_id=script.id,
            server_id=server.id,
            executed_by=executed_by_id,
            status="running"
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)

        # Removed noisy 'started' message

        # setup ssh similar to scripts API - support both SSH key and password
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        connection_success = False
        
        # Add a small delay to avoid rate limiting
        import time
        time.sleep(0.5)
        
        try:
            # Try SSH key first if available
            if server.auth_method == 'ssh_key' and server.ssh_key_path:
                try:
                    key_path = server.ssh_key_path
                    if not os.path.isabs(key_path):
                        key_path = os.path.join(os.getcwd(), key_path)
                    if os.path.exists(key_path):
                        # Try loading without password parameter first (for unencrypted keys)
                        # Detect key type and load with appropriate paramiko class
                        key_type = detect_key_type_from_file(key_path)
                        key_class = get_paramiko_key_class(key_type)
                        pkey = key_class.from_private_key_file(key_path)
                        ssh.connect(
                            hostname=server.ip, 
                            username=server.username, 
                            pkey=pkey, 
                            timeout=30,
                            banner_timeout=30,
                            auth_timeout=30,
                            allow_agent=False,
                            look_for_keys=False
                        )
                        connection_success = True
                        print(f"SSH key connection successful for {server.name}")
                except Exception as e:
                    print(f"SSH key connection failed for {server.name}: {e}")
            
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
                        banner_timeout=30,
                        auth_timeout=30,
                        allow_agent=False,
                        look_for_keys=False
                    )
                    connection_success = True
                    print(f"Password connection successful for {server.name}")
                except Exception as e2:
                    print(f"Password connection failed for {server.name}: {e2}")
            
            if not connection_success:
                await websocket.send_text(json.dumps({"type": "error", "message": "Failed to connect to server with both SSH key and password"}))
                execution.status = "failed"
                execution.error = "Failed to connect to server with both SSH key and password"
                execution.completed_at = datetime.now(timezone.utc)
                db.commit()
                return

            script_content = script.content or ''
            # Detect Windows robustly
            # Prefer stored detected_os if available, else probe robustly (also use 'where')
            is_windows = False
            try:
                if getattr(server, 'detected_os', None):
                    os_lower = (server.detected_os or '').lower()
                    is_windows = ('win' in os_lower) or ('windows' in os_lower)
                else:
                    # Quick Windows indicators
                    try:
                        _st_where_ps, _so_where_ps, _se_where_ps = ssh.exec_command("where powershell")
                        where_ps = _so_where_ps.read().decode('utf-8', errors='ignore').strip()
                        if where_ps:
                            is_windows = True
                        else:
                            _st_where_cmd, _so_where_cmd, _se_where_cmd = ssh.exec_command("where cmd")
                            where_cmd = _so_where_cmd.read().decode('utf-8', errors='ignore').strip()
                            if where_cmd:
                                is_windows = True
                    except Exception:
                        pass
                    if not is_windows:
                        try:
                            _st_os, _so_os, _se_os = ssh.exec_command("cmd.exe /c echo %OS%")
                            os_env = _so_os.read().decode('utf-8', errors='ignore').strip()
                            if os_env and 'Windows' in os_env:
                                is_windows = True
                            else:
                                _st_ver, _so_ver, _se_ver = ssh.exec_command("cmd.exe /c ver")
                                ver_out = _so_ver.read().decode('utf-8', errors='ignore').strip()
                                is_windows = bool(ver_out)
                        except Exception:
                            try:
                                _st_uname, _so_uname, _se_uname = ssh.exec_command("uname")
                                uname_out = _so_uname.read().decode('utf-8', errors='ignore').strip().lower()
                                is_windows = False if uname_out else False
                            except Exception:
                                is_windows = 'windows' in (server.name or '').lower() or 'win' in (server.name or '').lower()
            except Exception:
                is_windows = False

            selected_cmd_preview = ""
            if is_windows:
                # Windows paths
                if script.script_type == 'bash':
                    # Run content directly with cmd.exe
                    cmd = f"cmd.exe /c {script_content}" if script_content else "cmd.exe /c"
                    selected_cmd_preview = cmd[:140]
                    stdin, stdout, stderr = ssh.exec_command(cmd)
                elif script.script_type == 'python':
                    # Use python and inline heredoc-like execution
                    cmd = f"python - << 'PY'\n{script_content}\nPY\nexit\n"
                    selected_cmd_preview = "python heredoc"
                    stdin, stdout, stderr = ssh.exec_command(cmd)
                elif script.script_type == 'powershell':
                    import base64
                    # Wrap with output encoding and explicit flush to improve streaming
                    ps_body = (
                        "$OutputEncoding=[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
                        "& { " + script_content + " } | ForEach-Object { $_; [Console]::Out.Flush() }"
                    )
                    encoded_script = base64.b64encode(ps_body.encode('utf-16le')).decode('ascii')
                    # Always use Windows PowerShell on Windows hosts
                    cmd = f"powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand {encoded_script}"
                    selected_cmd_preview = "powershell.exe -EncodedCommand (flush wrapper)"
                    stdin, stdout, stderr = ssh.exec_command(cmd)
                else:
                    cmd = f"cmd.exe /c {script_content}" if script_content else "cmd.exe /c"
                    selected_cmd_preview = cmd[:140]
                    stdin, stdout, stderr = ssh.exec_command(cmd)
            else:
                # Unix/Linux paths
                if script.script_type == 'bash':
                    cmd = "/bin/bash -s"
                    selected_cmd_preview = cmd
                    stdin, stdout, stderr = ssh.exec_command(cmd)
                    if script_content:
                        stdin.write(script_content)
                        try:
                            stdin.channel.shutdown_write()
                        except Exception:
                            pass
                elif script.script_type == 'python':
                    sftp = ssh.open_sftp()
                    remote_path = f"/tmp/.sm_py_ws_{server.id}_{execution.id}.py"
                    with sftp.file(remote_path, 'w') as f:
                        f.write(script_content)
                    sftp.close()
                    cmd = f"python3 {remote_path}; rm -f {remote_path}"
                    selected_cmd_preview = cmd
                    stdin, stdout, stderr = ssh.exec_command(cmd)
                elif script.script_type == 'powershell':
                    import base64
                    encoded_script = base64.b64encode(script_content.encode('utf-16le')).decode('ascii')
                    # Detect available PowerShell binary (pwsh or powershell)
                    try:
                        _stdin_ps, _stdout_ps, _stderr_ps = ssh.exec_command("command -v pwsh || command -v powershell")
                        ps_path = _stdout_ps.read().decode('utf-8', errors='ignore').strip()
                    except Exception:
                        ps_path = ''
                    if ps_path:
                        ps_bin = 'pwsh' if 'pwsh' in ps_path else 'powershell'
                        cmd = f"{ps_bin} -NoLogo -NoProfile -NonInteractive -EncodedCommand {encoded_script}"
                        selected_cmd_preview = f"{ps_bin} -EncodedCommand ..."
                        stdin, stdout, stderr = ssh.exec_command(cmd)
                    else:
                        # Stream a clear error and fail this execution
                        await websocket.send_text(json.dumps({"type": "error_output", "data": "PowerShell is not installed on target server (no pwsh/powershell)."}))
                        execution.status = "failed"
                        execution.error = "PowerShell not available on target"
                        execution.completed_at = datetime.now(timezone.utc)
                        db.commit()
                        db.refresh(execution)
                        await websocket.send_text(json.dumps({"type": "finished", "status": execution.status, "execution_id": execution.id}))
                        return
                else:
                    cmd = "/bin/sh -s"
                    selected_cmd_preview = cmd
                    stdin, stdout, stderr = ssh.exec_command(cmd)
                    if script_content:
                        stdin.write(script_content)
                        try:
                            stdin.channel.shutdown_write()
                        except Exception:
                            pass

            # Omit debug exec-info line to keep output clean

            chan = stdout.channel
            err_chan = stderr.channel
            out_chunks = []
            err_chunks = []
            while True:
                if chan.recv_ready():
                    data = chan.recv(4096)
                    if data:
                        txt = data.decode('utf-8', errors='ignore')
                        out_chunks.append(data)
                        await websocket.send_text(json.dumps({"type": "output", "data": txt}))
                if err_chan.recv_stderr_ready() or stderr.channel.recv_stderr_ready():
                    data = stderr.channel.recv_stderr(4096)
                    if data:
                        txt = data.decode('utf-8', errors='ignore')
                        err_chunks.append(data)
                        await websocket.send_text(json.dumps({"type": "error_output", "data": txt}))
                if chan.exit_status_ready():
                    break
                await asyncio.sleep(0.02)

            exit_code = chan.recv_exit_status()
            out_text = b"".join(out_chunks).decode('utf-8', errors='ignore')
            err_text = b"".join(err_chunks).decode('utf-8', errors='ignore')
            execution.status = "completed" if exit_code == 0 else "failed"
            execution.output = out_text
            execution.error = err_text if exit_code != 0 else None
            execution.completed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(execution)

            await websocket.send_text(json.dumps({"type": "finished", "status": execution.status, "execution_id": execution.id}))
        except Exception as e:
            execution.status = "failed"
            execution.error = str(e)
            execution.completed_at = datetime.now(timezone.utc)
            db.commit()
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
        finally:
            try:
                ssh.close()
            except Exception:
                pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
