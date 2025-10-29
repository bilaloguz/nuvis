"""
OS Detection utilities for servers.
"""
import paramiko
import socket
import re
from typing import Tuple, Optional
from secrets_vault import SecretsVault

def detect_os_via_ssh(ip: str, username: str, password: str = None, ssh_key_path: str = None) -> Tuple[Optional[str], str]:
    """
    Detect OS by connecting via SSH and running detection commands.
    
    Args:
        ip: Server IP address
        username: SSH username
        password: SSH password (if using password auth)
        ssh_key_path: Path to SSH private key (if using key auth)
    
    Returns:
        Tuple of (detected_os, detection_method)
    """
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Try SSH key first if available
        if ssh_key_path and password is None:
            try:
                from ssh_key_utils import detect_key_type_from_file, get_paramiko_key_class
                key_type = detect_key_type_from_file(ssh_key_path)
                key_class = get_paramiko_key_class(key_type)
                pkey = key_class.from_private_key_file(ssh_key_path)
                ssh.connect(ip, username=username, pkey=pkey, timeout=10)
            except Exception:
                return None, "ssh_connect_failed"
        else:
            # Try password authentication
            if password:
                # Decrypt password if it's encrypted
                if password.startswith('encrypted:'):
                    vault = SecretsVault()
                    try:
                        password = vault.decrypt(password[10:])
                    except Exception:
                        return None, "password_decrypt_failed"
                
                ssh.connect(ip, username=username, password=password, timeout=10)
            else:
                return None, "no_credentials"
        
        # Run OS detection commands
        os_commands = [
            ("uname -s", "unix"),  # Linux, macOS, FreeBSD
            ("echo %OS%", "windows"),  # Windows
            ("ver", "windows_alt"),  # Windows alternative
        ]
        
        for command, os_type in os_commands:
            try:
                stdin, stdout, stderr = ssh.exec_command(command, timeout=5)
                output = stdout.read().decode('utf-8', errors='ignore').strip().lower()
                
                if os_type == "unix":
                    if "linux" in output:
                        return "linux", "ssh_connect"
                    elif "darwin" in output:
                        return "macos", "ssh_connect"
                    elif "freebsd" in output:
                        return "freebsd", "ssh_connect"
                elif os_type in ["windows", "windows_alt"]:
                    if "windows" in output:
                        return "windows", "ssh_connect"
                        
            except Exception:
                continue
        
        ssh.close()
        return "unknown", "ssh_connect"
        
    except Exception as e:
        return None, f"ssh_connect_error: {str(e)}"

def detect_os_via_port_scan(ip: str) -> Tuple[Optional[str], str]:
    """
    Detect OS by scanning common ports and analyzing responses.
    
    Args:
        ip: Server IP address
    
    Returns:
        Tuple of (detected_os, detection_method)
    """
    try:
        # Check SSH port (22) - most reliable indicator
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((ip, 22))
            sock.close()
            
            if result == 0:
                # SSH port is open, try to get banner
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(3)
                    sock.connect((ip, 22))
                    banner = sock.recv(1024).decode('utf-8', errors='ignore').lower()
                    sock.close()
                    
                    if "openssh" in banner:
                        # Can't determine specific OS from SSH banner alone
                        return "unix_like", "port_scan"
                except Exception:
                    pass
        except Exception:
            pass
        
        # Check RDP port (3389) - Windows indicator
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((ip, 3389))
            sock.close()
            
            if result == 0:
                return "windows", "port_scan"
        except Exception:
            pass
        
        return "unknown", "port_scan"
        
    except Exception as e:
        return None, f"port_scan_error: {str(e)}"

def detect_os_automatically(ip: str, username: str, password: str = None, ssh_key_path: str = None) -> Tuple[Optional[str], str]:
    """
    Automatically detect OS using multiple methods.
    
    Args:
        ip: Server IP address
        username: SSH username
        password: SSH password (if using password auth)
        ssh_key_path: Path to SSH private key (if using key auth)
    
    Returns:
        Tuple of (detected_os, detection_method)
    """
    # Try SSH detection first (most accurate)
    if username and (password or ssh_key_path):
        os_result, method = detect_os_via_ssh(ip, username, password, ssh_key_path)
        if os_result and os_result != "unknown":
            return os_result, method
    
    # Fallback to port scanning
    os_result, method = detect_os_via_port_scan(ip)
    if os_result and os_result != "unknown":
        return os_result, method
    
    return "unknown", "unknown"

def get_os_icon(os_type: str) -> str:
    """
    Get the appropriate icon for the OS type.
    
    Args:
        os_type: The detected OS type
    
    Returns:
        Icon string/emoji
    """
    icons = {
        "linux": "🐧",
        "windows": "🪟",
        "macos": "🍎",
        "freebsd": "😈",
        "unix_like": "🐧",
        "unknown": "❓"
    }
    return icons.get(os_type, "❓")

def get_os_display_name(os_type: str) -> str:
    """
    Get the display name for the OS type.
    
    Args:
        os_type: The detected OS type
    
    Returns:
        Display name
    """
    names = {
        "linux": "Linux",
        "windows": "Windows",
        "macos": "macOS",
        "freebsd": "FreeBSD",
        "unix_like": "Unix-like",
        "unknown": "Unknown"
    }
    return names.get(os_type, "Unknown")
