"""
Audit Logging Utility Module

This module provides functions to log user actions and system events
for security and compliance purposes.
"""

import json
from typing import Optional, Any, Dict
from fastapi import Request
from sqlalchemy.orm import Session
from models import AuditLog, User

class AuditLogger:
    """Utility class for logging audit events."""
    
    @staticmethod
    def log_action(
        db: Session,
        user_id: Optional[int],
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True
    ):
        """Log an audit event to the database."""
        try:
            # Convert details dict to JSON string
            details_json = json.dumps(details) if details else None
            
            audit_log = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details_json,
                ip_address=ip_address,
                user_agent=user_agent,
                success=success
            )
            
            db.add(audit_log)
            db.commit()
            
        except Exception as e:
            # Don't fail the main operation if audit logging fails
            print(f"Audit logging failed: {e}")
            db.rollback()
    
    @staticmethod
    def log_user_action(
        db: Session,
        user: User,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
        success: bool = True
    ):
        """Log a user action with request context."""
        ip_address = None
        user_agent = None
        
        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
        
        AuditLogger.log_action(
            db=db,
            user_id=user.id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success
        )
    
    @staticmethod
    def log_system_event(
        db: Session,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True
    ):
        """Log a system event (no user associated)."""
        AuditLogger.log_action(
            db=db,
            user_id=None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            success=success
        )

# Common audit actions
class AuditActions:
    # User actions
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    USER_PASSWORD_CHANGE = "user_password_change"
    
    # Server actions
    SERVER_CREATE = "server_create"
    SERVER_UPDATE = "server_update"
    SERVER_DELETE = "server_delete"
    SERVER_CONNECTION_TEST = "server_connection_test"
    SERVER_SSH_KEY_DEPLOY = "server_ssh_key_deploy"
    
    # Script actions
    SCRIPT_CREATE = "script_create"
    SCRIPT_UPDATE = "script_update"
    SCRIPT_DELETE = "script_delete"
    SCRIPT_EXECUTE = "script_execute"
    SCRIPT_EXECUTE_GROUP = "script_execute_group"
    
    # Schedule actions
    SCHEDULE_CREATE = "schedule_create"
    SCHEDULE_UPDATE = "schedule_update"
    SCHEDULE_DELETE = "schedule_delete"
    SCHEDULE_ENABLE = "schedule_enable"
    SCHEDULE_DISABLE = "schedule_disable"
    
    # Group actions
    GROUP_CREATE = "group_create"
    GROUP_UPDATE = "group_update"
    GROUP_DELETE = "group_delete"
    
    # Settings actions
    SETTINGS_UPDATE = "settings_update"
    
    # System actions
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    BACKUP_CREATE = "backup_create"
    BACKUP_RESTORE = "backup_restore"
