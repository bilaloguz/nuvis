from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List
from database import get_db
from models import ServerGroup, User
from schemas import ServerGroupResponse, ServerGroupCreate, ServerGroupUpdate, ServerGroupListResponse
from auth import get_current_user
from audit_utils import log_audit

router = APIRouter()

@router.post("/", response_model=ServerGroupResponse)
def create_server_group(
    group_create: ServerGroupCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can create server groups
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create server groups"
        )
    
    # Check if group name already exists
    existing_group = db.query(ServerGroup).filter(ServerGroup.name == group_create.name).first()
    if existing_group:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Server group name already exists"
        )
    
    # Create new server group
    new_group = ServerGroup(
        name=group_create.name,
        description=group_create.description,
        color=group_create.color
    )
    
    db.add(new_group)
    db.commit()
    db.refresh(new_group)
    
    log_audit(db, action="server_group_create", resource_type="server_group", resource_id=new_group.id, user_id=current_user.id, details={"name": new_group.name})
    
    return new_group

@router.get("/", response_model=ServerGroupListResponse)
def get_server_groups(
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=10000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can list server groups
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can list server groups"
        )
    
    groups = db.query(ServerGroup).options(
        joinedload(ServerGroup.servers)
    ).offset(skip).limit(limit).all()
    total = db.query(ServerGroup).count()
    
    return ServerGroupListResponse(groups=groups, total=total)

@router.get("/{group_id}", response_model=ServerGroupResponse)
def get_server_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can view server group details
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view server group details"
        )
    
    group = db.query(ServerGroup).options(
        joinedload(ServerGroup.servers)
    ).filter(ServerGroup.id == group_id).first()
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server group not found"
        )
    return group

@router.put("/{group_id}", response_model=ServerGroupResponse)
def update_server_group(
    group_id: int,
    group_update: ServerGroupUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can update server groups
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update server groups"
        )
    
    group = db.query(ServerGroup).filter(ServerGroup.id == group_id).first()
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server group not found"
        )
    
    # Check if name is being changed and if it already exists
    if group_update.name and group_update.name != group.name:
        existing_group = db.query(ServerGroup).filter(ServerGroup.name == group_update.name).first()
        if existing_group:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Server group name already exists"
            )
    
    # Update fields
    if group_update.name is not None:
        group.name = group_update.name
    if group_update.description is not None:
        group.description = group_update.description
    if group_update.color is not None:
        group.color = group_update.color
    
    db.commit()
    db.refresh(group)
    
    log_audit(db, action="server_group_update", resource_type="server_group", resource_id=group.id, user_id=current_user.id, details={"name": group.name})
    
    return group

@router.delete("/{group_id}")
def delete_server_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can delete server groups
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete server groups"
        )
    
    group = db.query(ServerGroup).filter(ServerGroup.id == group_id).first()
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server group not found"
        )
    
    # Check if group has servers
    from models import ServerGroupAssociation
    servers_in_group = db.query(ServerGroupAssociation).filter(ServerGroupAssociation.group_id == group_id).count()
    if servers_in_group > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete group '{group.name}' - it contains {servers_in_group} server(s). Remove or reassign servers first."
        )
    
    group_name = group.name
    db.delete(group)
    db.commit()
    
    log_audit(db, action="server_group_delete", resource_type="server_group", resource_id=group_id, user_id=current_user.id, details={"name": group_name})
    
    return {"message": "Server group deleted successfully"}
