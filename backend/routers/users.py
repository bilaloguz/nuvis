from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import User
from schemas import UserResponse, UserUpdate, UserPasswordUpdate, UserListResponse, UserCreate
from auth import get_current_user, verify_password, get_password_hash
from security import admin_ip_guard
from audit_utils import log_audit

router = APIRouter(dependencies=[Depends(admin_ip_guard)])

@router.post("/", response_model=UserResponse)
def create_user(
    user_create: UserCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can create new users
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create new users"
        )
    
    # Validate password length
    if len(user_create.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long"
        )
    
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == user_create.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_create.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )
    
    # Create new user
    new_user = User(
        username=user_create.username,
        email=user_create.email,
        password_hash=get_password_hash(user_create.password),
        role=user_create.role
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    log_audit(db, action="user_create", resource_type="user", resource_id=new_user.id, user_id=current_user.id, details={"username": new_user.username, "role": new_user.role})
    
    return new_user

@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/", response_model=UserListResponse)
def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=10000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can list all users
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can list all users"
        )
    
    users = db.query(User).offset(skip).limit(limit).all()
    total = db.query(User).count()
    
    return UserListResponse(users=users, total=total)

@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Users can only view their own profile, admins can view any
    if current_user.id != user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own profile"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Users can only update their own profile, admins can update any
    if current_user.id != user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own profile"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if username is being changed and if it already exists
    if user_update.username and user_update.username != user.username:
        existing_user = db.query(User).filter(User.username == user_update.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
    
    # Check if email is being changed and if it already exists
    if user_update.email and user_update.email != user.email:
        existing_user = db.query(User).filter(User.email == user_update.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
    
    # Update fields
    if user_update.username is not None:
        user.username = user_update.username
    if user_update.email is not None:
        user.email = user_update.email
    if user_update.role is not None and current_user.role == "admin":
        user.role = user_update.role
    
    db.commit()
    db.refresh(user)
    
    log_audit(db, action="user_update", resource_type="user", resource_id=user.id, user_id=current_user.id, details={"username": user.username})
    
    return user

@router.put("/{user_id}/password")
def update_user_password(
    user_id: int,
    password_update: UserPasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Users can only change their own password
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only change your own password"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Verify current password
    if not verify_password(password_update.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    user.password_hash = get_password_hash(password_update.new_password)
    db.commit()
    
    return {"message": "Password updated successfully"}

@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can delete users
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete users"
        )
    
    # Prevent admin from deleting themselves
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    username = user.username
    db.delete(user)
    db.commit()
    
    log_audit(db, action="user_delete", resource_type="user", resource_id=user_id, user_id=current_user.id, details={"username": username})
    
    return {"message": "User deleted successfully"}
