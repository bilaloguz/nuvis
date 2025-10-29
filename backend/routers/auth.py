from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from database import get_db
from models import User
from schemas import UserCreate, UserResponse, Token, UserLogin
from auth import verify_password, get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user
from models import Settings
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from audit_logger import AuditLogger, AuditActions

router = APIRouter()

@router.post("/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    # Check if username already exists
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email already exists
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        password_hash=hashed_password,
        role=user.role
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

@router.post("/login", response_model=Token)
def login(user_credentials: UserLogin, request: Request, db: Session = Depends(get_db)):
    # Find user by username
    user = db.query(User).filter(User.username == user_credentials.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify password
    if not verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token (settings override)
    settings = db.query(Settings).first()
    expire_minutes = (getattr(settings, 'access_token_expire_minutes', None) or ACCESS_TOKEN_EXPIRE_MINUTES or 30)
    access_token_expires = timedelta(minutes=int(expire_minutes))
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # Log successful login
    AuditLogger.log_user_action(
        db=db,
        user=user,
        action=AuditActions.USER_LOGIN,
        resource_type="user",
        resource_id=user.id,
        details={"username": user.username},
        request=request,
        success=True
    )

    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Logout user and log the action."""
    # Log logout
    AuditLogger.log_user_action(
        db=db,
        user=current_user,
        action=AuditActions.USER_LOGOUT,
        resource_type="user",
        resource_id=current_user.id,
        details={"username": current_user.username},
        request=request,
        success=True
    )
    
    return {"message": "Successfully logged out"}
