from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import Settings, User
from schemas import SettingsResponse, SettingsUpdate
from auth import get_current_user
from security import admin_ip_guard

router = APIRouter(dependencies=[Depends(admin_ip_guard)])


def _get_singleton(db: Session) -> Settings:
    row = db.query(Settings).first()
    if not row:
        row = Settings()
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("/", response_model=SettingsResponse)
def get_settings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")
    return _get_singleton(db)


@router.put("/", response_model=SettingsResponse)
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")
    row = _get_singleton(db)
    for k, v in payload.dict(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


