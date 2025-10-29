from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi import Request
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from database import get_db
from models import AuditLog, User
from schemas import AuditLogResponse, AuditLogListResponse, AuditLogCreate
from auth import get_current_user
from sqlalchemy import desc
import json

router = APIRouter()

@router.get("/", response_model=AuditLogListResponse)
def get_audit_logs(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    success: Optional[bool] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get audit logs with filtering and pagination. Admin only."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view audit logs"
        )
    
    # Build query - explicitly select all AuditLog fields
    query = db.query(AuditLog).options(
        joinedload(AuditLog.user)
    )
    
    # Apply filters
    if action:
        query = query.filter(AuditLog.action.contains(action))
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if success is not None:
        query = query.filter(AuditLog.success == success)
    if from_date:
        query = query.filter(AuditLog.created_at >= from_date)
    if to_date:
        query = query.filter(AuditLog.created_at <= to_date)
    
    # Get total count
    total = query.count()
    
    # Apply pagination and ordering
    logs = query.order_by(desc(AuditLog.created_at)).offset((page - 1) * size).limit(size).all()
    
    return AuditLogListResponse(
        logs=logs,
        total=total,
        page=page,
        size=size
    )

@router.post("/")
def create_audit_log(
    audit_log: AuditLogCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create an audit log entry. This endpoint is for internal use."""
    # Get client IP and user agent
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    # Create audit log entry
    db_audit_log = AuditLog(
        user_id=audit_log.user_id or current_user.id,
        action=audit_log.action,
        resource_type=audit_log.resource_type,
        resource_id=audit_log.resource_id,
        details=audit_log.details,
        ip_address=client_ip,
        user_agent=user_agent,
        success=audit_log.success
    )
    
    db.add(db_audit_log)
    db.commit()
    db.refresh(db_audit_log)
    
    return {"id": db_audit_log.id, "message": "Audit log created"}

@router.get("/actions")
def get_audit_actions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of available audit actions for filtering. Admin only."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view audit actions"
        )
    
    actions = db.query(AuditLog.action).distinct().all()
    return {"actions": [action[0] for action in actions]}

@router.get("/resource-types")
def get_resource_types(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of available resource types for filtering. Admin only."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view resource types"
        )
    
    types = db.query(AuditLog.resource_type).distinct().filter(AuditLog.resource_type.isnot(None)).all()
    return {"resource_types": [type_[0] for type_ in types]}
