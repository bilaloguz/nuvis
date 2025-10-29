"""
Robust SSH Connection Manager

This module provides a reliable SSH connection manager with:
- Connection pooling and reuse
- Exponential backoff retry logic
- Connection validation and health checks
- Proper error handling and logging
- Support for both SSH key and password authentication
"""

import paramiko
import time
import os
import threading
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager
import logging

from models import Server
from utils_logging import get_logger
from secrets_vault import SecretsVault

logger = get_logger(__name__)

class SSHConnectionError(Exception):
    """Custom exception for SSH connection errors"""
    pass

class SSHConnectionManager:
    """Manages SSH connections with pooling, retry logic, and health checks"""
    
    def __init__(self, max_connections_per_server: int = 3, connection_timeout: int = 30):
        self.max_connections_per_server = max_connections_per_server
        self.connection_timeout = connection_timeout
        self._connections: Dict[str, list] = {}  # server_key -> list of connections
        self._connection_locks: Dict[str, threading.Lock] = {}
        self._last_health_check: Dict[str, datetime] = {}
        self._health_check_interval = timedelta(minutes=5)
        self._lock = threading.Lock()
    
    def _get_server_key(self, server: Server) -> str:
        """Generate a unique key for the server"""
        return f"{server.ip}:{server.username}"
    
    def _get_connection_lock(self, server: Server) -> threading.Lock:
        """Get or create a lock for the server"""
        server_key = self._get_server_key(server)
        with self._lock:
            if server_key not in self._connection_locks:
                self._connection_locks[server_key] = threading.Lock()
            return self._connection_locks[server_key]
    
    def _is_connection_healthy(self, ssh_client: paramiko.SSHClient) -> bool:
        """Check if an SSH connection is still healthy"""
        try:
            if not ssh_client.get_transport() or not ssh_client.get_transport().is_active():
                return False
            
            # Try a simple command to test the connection
            stdin, stdout, stderr = ssh_client.exec_command("echo 'health_check'", timeout=5)
            stdout.channel.recv_exit_status()
            return True
        except Exception:
            return False
    
    def _create_new_connection(self, server: Server) -> paramiko.SSHClient:
        """Create a new SSH connection with retry logic"""
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                ssh_client = paramiko.SSHClient()
                ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                # Configure connection parameters
                connect_kwargs = {
                    'hostname': server.ip,
                    'username': server.username,
                    'timeout': self.connection_timeout,
                    'banner_timeout': self.connection_timeout,
                    'auth_timeout': self.connection_timeout,
                    'allow_agent': False,
                    'look_for_keys': False
                }
                
                # Try SSH key authentication first
                if hasattr(server, 'ssh_key_path') and server.ssh_key_path:
                    key_path = server.ssh_key_path
                    if not os.path.isabs(key_path):
                        key_path = os.path.join(os.getcwd(), key_path)
                    
                    if os.path.exists(key_path):
                        try:
                            # Detect key type and load with appropriate paramiko class
                            key_type = self._detect_key_type_from_file(key_path)
                            key_class = self._get_paramiko_key_class(key_type)
                            private_key = key_class.from_private_key_file(key_path, password=None)
                            
                            ssh_client.connect(pkey=private_key, **connect_kwargs)
                            logger.info(f"SSH key connection successful for {server.name} (attempt {attempt + 1})")
                            return ssh_client
                        except Exception as e:
                            logger.warning(f"SSH key connection failed for {server.name}: {e}")
                
                # Fall back to password authentication
                if hasattr(server, 'password_encrypted') and server.password_encrypted:
                    try:
                        vault = SecretsVault.get()
                        password = vault.decrypt_to_str(server.password_encrypted)
                        ssh_client.connect(password=password, **connect_kwargs)
                        logger.info(f"Password connection successful for {server.name} (attempt {attempt + 1})")
                        return ssh_client
                    except Exception as e:
                        logger.warning(f"Password connection failed for {server.name}: {e}")
                
                # If we get here, both methods failed
                raise SSHConnectionError(f"Both SSH key and password authentication failed for {server.name}")
                
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"SSH connection attempt {attempt + 1} failed for {server.name}: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"All SSH connection attempts failed for {server.name}: {e}")
                    raise SSHConnectionError(f"Failed to connect to {server.name} after {max_retries} attempts: {e}")
    
    def _detect_key_type_from_file(self, key_path: str) -> str:
        """Detect SSH key type from file content"""
        try:
            with open(key_path, 'r') as f:
                content = f.read()
            
            if 'BEGIN RSA PRIVATE KEY' in content:
                return 'rsa'
            elif 'BEGIN OPENSSH PRIVATE KEY' in content:
                return 'openssh'
            elif 'BEGIN EC PRIVATE KEY' in content:
                return 'ecdsa'
            elif 'BEGIN PRIVATE KEY' in content:
                return 'ed25519'
            else:
                return 'rsa'  # Default fallback
        except Exception:
            return 'rsa'
    
    def _get_paramiko_key_class(self, key_type: str):
        """Get the appropriate paramiko key class"""
        if key_type == 'rsa':
            return paramiko.RSAKey
        elif key_type == 'openssh':
            return paramiko.Ed25519Key
        elif key_type == 'ecdsa':
            return paramiko.ECDSAKey
        elif key_type == 'ed25519':
            return paramiko.Ed25519Key
        else:
            return paramiko.RSAKey
    
    def _cleanup_unhealthy_connections(self, server: Server):
        """Remove unhealthy connections from the pool"""
        server_key = self._get_server_key(server)
        if server_key not in self._connections:
            return
        
        healthy_connections = []
        for conn in self._connections[server_key]:
            try:
                if self._is_connection_healthy(conn):
                    healthy_connections.append(conn)
                else:
                    try:
                        conn.close()
                    except Exception:
                        pass
            except Exception:
                pass
        
        self._connections[server_key] = healthy_connections
    
    def _should_check_health(self, server: Server) -> bool:
        """Check if we should perform a health check"""
        server_key = self._get_server_key(server)
        last_check = self._last_health_check.get(server_key)
        if not last_check:
            return True
        return datetime.now(timezone.utc) - last_check > self._health_check_interval
    
    @contextmanager
    def get_connection(self, server: Server):
        """Get an SSH connection from the pool or create a new one"""
        server_key = self._get_server_key(server)
        connection_lock = self._get_connection_lock(server)
        
        with connection_lock:
            # Clean up unhealthy connections if needed
            if self._should_check_health(server):
                self._cleanup_unhealthy_connections(server)
                self._last_health_check[server_key] = datetime.now(timezone.utc)
            
            # Try to get an existing healthy connection
            if server_key in self._connections:
                for conn in self._connections[server_key]:
                    if self._is_connection_healthy(conn):
                        try:
                            yield conn
                            return
                        except Exception as e:
                            logger.warning(f"Error using pooled connection for {server.name}: {e}")
                            # Remove the bad connection
                            try:
                                conn.close()
                            except Exception:
                                pass
                            self._connections[server_key].remove(conn)
            
            # Create a new connection if we don't have a healthy one
            if server_key not in self._connections:
                self._connections[server_key] = []
            
            if len(self._connections[server_key]) < self.max_connections_per_server:
                try:
                    new_conn = self._create_new_connection(server)
                    self._connections[server_key].append(new_conn)
                    yield new_conn
                    return
                except Exception as e:
                    logger.error(f"Failed to create new connection for {server.name}: {e}")
                    raise
            
            # If we can't create a new connection, try to reuse an existing one
            if self._connections[server_key]:
                conn = self._connections[server_key][0]
                try:
                    yield conn
                    return
                except Exception as e:
                    logger.error(f"Failed to reuse existing connection for {server.name}: {e}")
                    raise
            
            # Last resort: create a temporary connection
            try:
                temp_conn = self._create_new_connection(server)
                yield temp_conn
            finally:
                try:
                    temp_conn.close()
                except Exception:
                    pass
    
    def close_all_connections(self):
        """Close all connections in the pool"""
        with self._lock:
            for server_key, connections in self._connections.items():
                for conn in connections:
                    try:
                        conn.close()
                    except Exception:
                        pass
            self._connections.clear()
            self._connection_locks.clear()
            self._last_health_check.clear()

# Global instance
ssh_manager = SSHConnectionManager()

def get_ssh_connection(server: Server):
    """Get an SSH connection for the given server"""
    return ssh_manager.get_connection(server)

def close_all_ssh_connections():
    """Close all SSH connections"""
    ssh_manager.close_all_connections()


