from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user
from models import User
from auth_logger import auth_logger

router = APIRouter()

@router.get("/auth-notifications")
def get_auth_notifications(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recent authentication notifications for UI display
    """
    # Only admins can view auth notifications
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view authentication notifications"
        )
    
    notifications = auth_logger.get_ui_notifications(limit)
    return {
        "notifications": notifications,
        "total": len(notifications)
    }

@router.delete("/auth-notifications")
def clear_auth_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Clear authentication notifications
    """
    # Only admins can clear notifications
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can clear notifications"
        )
    
    auth_logger.clear_ui_notifications()
    return {"message": "Notifications cleared successfully"}
