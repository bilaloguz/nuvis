import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
from database import SessionLocal
from models import Server, User
from sqlalchemy.orm import Session

class AuthLogger:
    """
    Centralized authentication logger for both file and UI logging
    """
    
    def __init__(self):
        # Setup file logging
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # Create logger for authentication events
        self.logger = logging.getLogger('auth_events')
        self.logger.setLevel(logging.INFO)
        
        # Remove existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # File handler for detailed logs
        file_handler = logging.FileHandler(self.log_dir / "auth_events.log")
        file_handler.setLevel(logging.INFO)
        
        # Console handler for immediate feedback
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # UI notification storage (in-memory for now, could be database)
        self.ui_notifications = []
    
    def log_auth_attempt(self, 
                        server_name: str, 
                        server_ip: str,
                        auth_method: str,
                        success: bool,
                        details: Optional[Dict[str, Any]] = None,
                        user_id: Optional[int] = None):
        """
        Log authentication attempt with detailed information
        """
        timestamp = datetime.now().isoformat()
        
        log_data = {
            "timestamp": timestamp,
            "server_name": server_name,
            "server_ip": server_ip,
            "auth_method": auth_method,
            "success": success,
            "details": details or {},
            "user_id": user_id
        }
        
        # Log to file
        status = "SUCCESS" if success else "FAILED"
        message = f"[{status}] {auth_method.upper()} auth to {server_name} ({server_ip})"
        if details:
            message += f" - {json.dumps(details)}"
        
        self.logger.info(message)
        
        # Store for UI notifications
        ui_notification = {
            "id": f"auth_{timestamp}_{server_name}",
            "timestamp": timestamp,
            "type": "auth_attempt",
            "server_name": server_name,
            "server_ip": server_ip,
            "auth_method": auth_method,
            "success": success,
            "message": self._format_ui_message(server_name, auth_method, success, details),
            "details": details or {}
        }
        
        self.ui_notifications.append(ui_notification)
        
        # Keep only last 100 notifications to avoid memory issues
        if len(self.ui_notifications) > 100:
            self.ui_notifications = self.ui_notifications[-100:]
    
    def log_ssh_key_deployment(self,
                              server_name: str,
                              server_ip: str,
                              key_name: str,
                              success: bool,
                              details: Optional[Dict[str, Any]] = None):
        """
        Log SSH key deployment attempt
        """
        timestamp = datetime.now().isoformat()
        
        log_data = {
            "timestamp": timestamp,
            "server_name": server_name,
            "server_ip": server_ip,
            "key_name": key_name,
            "success": success,
            "details": details or {}
        }
        
        # Log to file
        status = "SUCCESS" if success else "FAILED"
        message = f"[{status}] SSH key deployment '{key_name}' to {server_name} ({server_ip})"
        if details:
            message += f" - {json.dumps(details)}"
        
        self.logger.info(message)
        
        # Store for UI notifications
        ui_notification = {
            "id": f"ssh_deploy_{timestamp}_{server_name}",
            "timestamp": timestamp,
            "type": "ssh_deployment",
            "server_name": server_name,
            "server_ip": server_ip,
            "key_name": key_name,
            "success": success,
            "message": self._format_ssh_deployment_message(server_name, key_name, success, details),
            "details": details or {}
        }
        
        self.ui_notifications.append(ui_notification)
        
        # Keep only last 100 notifications
        if len(self.ui_notifications) > 100:
            self.ui_notifications = self.ui_notifications[-100:]
    
    def log_script_execution_auth(self,
                                 script_name: str,
                                 server_name: str,
                                 server_ip: str,
                                 auth_method_used: str,
                                 success: bool,
                                 details: Optional[Dict[str, Any]] = None):
        """
        Log authentication method used during script execution
        """
        timestamp = datetime.now().isoformat()
        
        log_data = {
            "timestamp": timestamp,
            "script_name": script_name,
            "server_name": server_name,
            "server_ip": server_ip,
            "auth_method_used": auth_method_used,
            "success": success,
            "details": details or {}
        }
        
        # Log to file
        status = "SUCCESS" if success else "FAILED"
        message = f"[{status}] Script '{script_name}' execution on {server_name} using {auth_method_used.upper()}"
        if details:
            message += f" - {json.dumps(details)}"
        
        self.logger.info(message)
        
        # Store for UI notifications
        ui_notification = {
            "id": f"script_auth_{timestamp}_{script_name}_{server_name}",
            "timestamp": timestamp,
            "type": "script_execution_auth",
            "script_name": script_name,
            "server_name": server_name,
            "server_ip": server_ip,
            "auth_method_used": auth_method_used,
            "success": success,
            "message": self._format_script_auth_message(script_name, server_name, auth_method_used, success, details),
            "details": details or {}
        }
        
        self.ui_notifications.append(ui_notification)
        
        # Keep only last 100 notifications
        if len(self.ui_notifications) > 100:
            self.ui_notifications = self.ui_notifications[-100:]
    
    def _format_ui_message(self, server_name: str, auth_method: str, success: bool, details: Optional[Dict[str, Any]]) -> str:
        """Format user-friendly message for UI"""
        if success:
            return f"✅ Connected to {server_name} using {auth_method.upper()} authentication"
        else:
            error_msg = details.get('error', 'Unknown error') if details else 'Unknown error'
            return f"❌ Failed to connect to {server_name} using {auth_method.upper()}: {error_msg}"
    
    def _format_ssh_deployment_message(self, server_name: str, key_name: str, success: bool, details: Optional[Dict[str, Any]]) -> str:
        """Format SSH deployment message for UI"""
        if success:
            return f"🔑 SSH key '{key_name}' successfully deployed to {server_name}"
        else:
            error_msg = details.get('error', 'Unknown error') if details else 'Unknown error'
            return f"❌ Failed to deploy SSH key '{key_name}' to {server_name}: {error_msg}"
    
    def _format_script_auth_message(self, script_name: str, server_name: str, auth_method: str, success: bool, details: Optional[Dict[str, Any]]) -> str:
        """Format script execution auth message for UI"""
        if success:
            return f"🚀 Script '{script_name}' executed on {server_name} using {auth_method.upper()}"
        else:
            error_msg = details.get('error', 'Unknown error') if details else 'Unknown error'
            return f"❌ Script '{script_name}' failed on {server_name} using {auth_method.upper()}: {error_msg}"
    
    def get_ui_notifications(self, limit: int = 50) -> list:
        """Get recent UI notifications for display"""
        return self.ui_notifications[-limit:]
    
    def clear_ui_notifications(self):
        """Clear UI notifications"""
        self.ui_notifications.clear()

# Global instance
auth_logger = AuthLogger()
