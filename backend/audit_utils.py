from typing import Optional, Any, Dict
from sqlalchemy.orm import Session
from models import AuditLog


def log_audit(
    db: Session,
    *,
    action: str,
    resource_type: str,
    resource_id: Optional[int] = None,
    user_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    success: bool = True,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    try:
        log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=(None if details is None else str(details)),
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
        )
        db.add(log)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

