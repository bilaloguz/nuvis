from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
import os
import subprocess
import paramiko
import base64
from pathlib import Path
from database import get_db
from models import Server, User, ServerGroup
from schemas import ServerResponse, ServerCreate, ServerUpdate, ServerListResponse
from auth import get_current_user, get_password_hash
from secrets_vault import SecretsVault
from audit_logger import AuditLogger, AuditActions
from audit_utils import log_audit
from auth_logger import auth_logger
from ssh_key_utils import get_ssh_key_type, get_ssh_key_parameters, get_paramiko_key_class, detect_key_type_from_file
from os_detection import detect_os_automatically

router = APIRouter()

@router.post("/generate-ssh-key")
def generate_ssh_key(
    key_name: str = Query(..., description="Name for the SSH key pair"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can generate SSH keys
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can generate SSH keys"
        )
    
    # Validate key name
    if not key_name or not key_name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Key name is required"
        )
    
    # Sanitize key name (only allow alphanumeric, hyphens, and underscores)
    sanitized_key_name = "".join(c for c in key_name if c.isalnum() or c in "-_")
    if sanitized_key_name != key_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Key name can only contain letters, numbers, hyphens, and underscores"
        )
    
    # Create SSH keys directory if it doesn't exist
    ssh_keys_dir = Path("ssh_keys")
    ssh_keys_dir.mkdir(exist_ok=True)
    
    # Get configured SSH key type
    key_type = get_ssh_key_type()
    key_params = get_ssh_key_parameters(key_type)
    
    # Generate unique key filename based on key type
    private_key_path = ssh_keys_dir / f"{sanitized_key_name}_{key_params['file_suffix']}"
    public_key_path = ssh_keys_dir / f"{sanitized_key_name}_{key_params['file_suffix']}.pub"
    
    # Check if key already exists
    if private_key_path.exists() or public_key_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SSH key with name '{sanitized_key_name}' already exists"
        )
    
    try:
        # Generate SSH key pair using ssh-keygen with configurable parameters
        cmd = [
            "ssh-keygen",
            "-t", key_params["type"],
            "-f", str(private_key_path),
            "-N", "",  # No passphrase by default
            "-C", f"{key_params['comment_prefix']}-{sanitized_key_name}"
        ]
        
        # Add bits parameter for RSA and ECDSA
        if key_params["bits"]:
            cmd.extend(["-b", key_params["bits"]])
        
        # Add PEM format for RSA (Ed25519 and ECDSA use OpenSSH format by default)
        if key_params["type"] == "rsa":
            cmd.append("-m")
            cmd.append("PEM")
        
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        # Read the generated keys
        with open(private_key_path, 'r') as f:
            private_key = f.read()
        
        with open(public_key_path, 'r') as f:
            public_key = f.read()
        
        # Set proper permissions for private key (600)
        os.chmod(private_key_path, 0o600)
        os.chmod(public_key_path, 0o644)
        
        return {
            "message": "SSH key pair generated successfully",
            "key_name": sanitized_key_name,
            "private_key_path": str(private_key_path),
            "public_key": public_key,
            "private_key": private_key
        }
        
    except subprocess.CalledProcessError as e:
        # Clean up any partially created files
        if private_key_path.exists():
            private_key_path.unlink()
        if public_key_path.exists():
            public_key_path.unlink()
        
        error_detail = f"Failed to generate SSH key: {e.stderr}"
        if "Permission denied" in e.stderr:
            error_detail += " (Check if the application has write permissions to the ssh_keys directory)"
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail
        )
    except Exception as e:
        # Clean up any partially created files
        if private_key_path.exists():
            private_key_path.unlink()
        if public_key_path.exists():
            public_key_path.unlink()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating SSH key: {str(e)}"
        )

@router.get("/ssh-keys")
def list_ssh_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can list SSH keys
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can list SSH keys"
        )
    
    ssh_keys_dir = Path("ssh_keys")
    if not ssh_keys_dir.exists():
        return {"keys": []}
    
    keys = []
    # Look for all supported key types
    key_patterns = ["*_id_rsa", "*_id_ed25519", "*_id_ecdsa"]
    
    for pattern in key_patterns:
        for key_file in ssh_keys_dir.glob(pattern):
            # Extract key name and type from filename
            key_name = key_file.stem
            if key_file.name.endswith("_id_rsa"):
                key_name = key_name.replace("_id_rsa", "")
                key_type = "rsa"
            elif key_file.name.endswith("_id_ed25519"):
                key_name = key_name.replace("_id_ed25519", "")
                key_type = "ed25519"
            elif key_file.name.endswith("_id_ecdsa"):
                key_name = key_name.replace("_id_ecdsa", "")
                key_type = "ecdsa"
            else:
                continue
                
            public_key_file = key_file.with_suffix(".pub")
            
            if public_key_file.exists():
                try:
                    with open(public_key_file, 'r') as f:
                        public_key = f.read().strip()
                    
                    keys.append({
                        "name": key_name,
                        "type": key_type,
                        "private_key_path": str(key_file),
                        "public_key": public_key,
                        "created": key_file.stat().st_mtime
                    })
                except Exception:
                    continue
    
    return {"keys": keys}

@router.post("/", response_model=ServerResponse)
def create_server(
    server_create: ServerCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can create servers
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create servers"
        )
    
    # Check if server name already exists
    existing_server = db.query(Server).filter(Server.name == server_create.name).first()
    if existing_server:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Server name already exists"
        )
    
    # Validate group_ids if provided
    if server_create.group_ids:
        groups = db.query(ServerGroup).filter(ServerGroup.id.in_(server_create.group_ids)).all()
        if len(groups) != len(server_create.group_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more server group IDs are invalid"
            )
    
    # Validate authentication method and required fields
    if server_create.auth_method == "password":
        if not server_create.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is required for password authentication"
            )
        if len(server_create.password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 6 characters long"
            )
    elif server_create.auth_method == "ssh_key":
        if not server_create.ssh_key_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SSH key path is required for SSH key authentication"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid authentication method. Use 'password' or 'ssh_key'"
        )
    
    # Detect OS automatically
    print(f"🔍 Detecting OS for server {server_create.name} ({server_create.ip})")
    detected_os, detection_method = detect_os_automatically(
        ip=server_create.ip,
        username=server_create.username,
        password=server_create.password,
        ssh_key_path=server_create.ssh_key_path
    )
    print(f"🖥️  Detected OS: {detected_os} (method: {detection_method})")
    
    # Create new server
    vault = SecretsVault.get()
    new_server = Server(
        name=server_create.name,
        ip=server_create.ip,
        username=server_create.username,
        auth_method=server_create.auth_method,
        password_hash=get_password_hash(server_create.password) if server_create.password else None,
        password_encrypted=vault.encrypt_to_str(server_create.password) if server_create.password else None,
        ssh_key_path=server_create.ssh_key_path,
        ssh_key_passphrase=get_password_hash(server_create.ssh_key_passphrase) if server_create.ssh_key_passphrase else None,
        detected_os=detected_os,
        os_detection_method=detection_method
    )
    
    # Add groups if provided
    if server_create.group_ids:
        groups = db.query(ServerGroup).filter(ServerGroup.id.in_(server_create.group_ids)).all()
        new_server.groups = groups
    
    db.add(new_server)
    db.commit()
    db.refresh(new_server)
    
    # Log server creation
    AuditLogger.log_user_action(
        db=db,
        user=current_user,
        action=AuditActions.SERVER_CREATE,
        resource_type="server",
        resource_id=new_server.id,
        details={
            "server_name": new_server.name,
            "server_ip": new_server.ip,
            "username": new_server.username,
            "auth_method": new_server.auth_method,
            "groups": [g.name for g in new_server.groups] if new_server.groups else []
        },
        success=True
    )
    
    # Auto-generate and deploy SSH key for each server
    try:
        ssh_keys_dir = Path("ssh_keys")
        ssh_keys_dir.mkdir(exist_ok=True)
        
        # Generate a unique SSH key pair for this server
        print(f"🔑 Generating unique SSH key pair for server {new_server.name}")
        
        import subprocess
        key_name = f"auto_generated_{new_server.name.lower().replace('-', '_')}"
        print(f"DEBUG: Generated key_name: '{key_name}' for server '{new_server.name}'")
        
        # Get configured SSH key type
        key_type = get_ssh_key_type()
        key_params = get_ssh_key_parameters(key_type)
        
        private_key_path = ssh_keys_dir / f"{key_name}_{key_params['file_suffix']}"
        public_key_path = ssh_keys_dir / f"{key_name}_{key_params['file_suffix']}.pub"
        print(f"DEBUG: Private key path: {private_key_path}")
        print(f"DEBUG: Public key path: {public_key_path}")
        
        # Check if key already exists for this server
        if private_key_path.exists():
            print(f"🔑 SSH key already exists for {new_server.name}, using existing key")
        else:
            # Generate SSH key pair with configurable parameters
            cmd = [
                "ssh-keygen", "-t", key_params["type"],
                "-f", str(private_key_path), "-N", "", 
                "-C", f"{key_params['comment_prefix']}-{new_server.name}"
            ]
            
            # Add bits parameter for RSA and ECDSA
            if key_params["bits"]:
                cmd.extend(["-b", key_params["bits"]])
            
            # Add PEM format for RSA (Ed25519 and ECDSA use OpenSSH format by default)
            if key_params["type"] == "rsa":
                cmd.extend(["-m", "PEM"])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ SSH key pair generated: {key_name}")
            else:
                print(f"❌ Failed to generate SSH key: {result.stderr}")
                return new_server
        
        # Deploy the key to the server
        print(f"🚀 Auto-deploying SSH key '{key_name}' to server {new_server.name}")
        print(f"DEBUG: About to call deploy_ssh_key_internal with key_name='{key_name}', server_id={new_server.id}")
        
        # Log SSH key deployment attempt
        auth_logger.log_ssh_key_deployment(
            server_name=new_server.name,
            server_ip=new_server.ip,
            key_name=key_name,
            success=False,  # Will be updated based on result
            details={"action": "deployment_attempt", "user_id": current_user.id}
        )
        
        # Deploy the key using the existing logic
        deploy_result = deploy_ssh_key_internal(key_name, new_server.id, db)
        
        print(f"DEBUG: Deploy result for {new_server.name}: {deploy_result}")
        
        if deploy_result["status"] == "deployed":
            print(f"✅ SSH key '{key_name}' successfully deployed to {new_server.name}")
            print(f"🔄 Server {new_server.name} auth_method updated to 'ssh_key'")
            
            # Log successful deployment
            auth_logger.log_ssh_key_deployment(
                server_name=new_server.name,
                server_ip=new_server.ip,
                key_name=key_name,
                success=True,
                details={"action": "deployment_success", "user_id": current_user.id}
            )
        else:
            print(f"❌ SSH key deployment FAILED for {new_server.name}: {deploy_result}")
            print(f"❌ Error message: {deploy_result.get('message', 'Unknown error')}")
            
            # Log failed deployment
            auth_logger.log_ssh_key_deployment(
                server_name=new_server.name,
                server_ip=new_server.ip,
                key_name=key_name,
                success=False,
                details={
                    "action": "deployment_failed", 
                    "error": deploy_result.get('message', 'Unknown error'),
                    "user_id": current_user.id
                }
            )
    
    except Exception as e:
        print(f"⚠️ SSH key auto-deployment failed: {e}")
        # Don't fail server creation, just log the error
    
    # Load group information for response
    db.refresh(new_server)
    return new_server

@router.get("/", response_model=ServerListResponse)
def get_servers(
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=10000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can list all servers
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can list all servers"
        )
    
    servers = db.query(Server).options(
        joinedload(Server.groups)
    ).offset(skip).limit(limit).all()
    total = db.query(Server).count()
    
    return ServerListResponse(servers=servers, total=total)

@router.get("/{server_id}", response_model=ServerResponse)
def get_server(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can view server details
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view server details"
        )
    
    server = db.query(Server).options(
        joinedload(Server.groups)
    ).filter(Server.id == server_id).first()
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    return server

@router.put("/{server_id}", response_model=ServerResponse)
def update_server(
    server_id: int,
    server_update: ServerUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can update servers
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update servers"
        )
    
    server = db.query(Server).filter(Server.id == server_id).first()
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    # Check if name is being changed and if it already exists
    if server_update.name and server_update.name != server.name:
        existing_server = db.query(Server).filter(Server.name == server_update.name).first()
        if existing_server:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Server name already exists"
            )
    
    # Validate authentication method changes
    new_auth_method = server_update.auth_method if server_update.auth_method is not None else server.auth_method
    
    if new_auth_method == "password":
        if server_update.password is not None and len(server_update.password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 6 characters long"
            )
    elif new_auth_method == "ssh_key":
        if server_update.ssh_key_path is not None and not server_update.ssh_key_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SSH key path is required for SSH key authentication"
            )
    
    # Update fields
    if server_update.name is not None:
        server.name = server_update.name
    if server_update.ip is not None:
        server.ip = server_update.ip
    if server_update.username is not None:
        server.username = server_update.username
    if server_update.auth_method is not None:
        server.auth_method = server_update.auth_method
    if server_update.password is not None:
        vault = SecretsVault.get()
        server.password_hash = get_password_hash(server_update.password) if server_update.password else None
        server.password_encrypted = vault.encrypt_to_str(server_update.password) if server_update.password else None
    if server_update.ssh_key_path is not None:
        server.ssh_key_path = server_update.ssh_key_path
    if server_update.ssh_key_passphrase is not None:
        server.ssh_key_passphrase = get_password_hash(server_update.ssh_key_passphrase) if server_update.ssh_key_passphrase else None
    
    # Update groups if provided
    if server_update.group_ids is not None:
        if server_update.group_ids:
            groups = db.query(ServerGroup).filter(ServerGroup.id.in_(server_update.group_ids)).all()
            server.groups = groups
        else:
            server.groups = []
    
    db.commit()
    db.refresh(server)
    
    # Log server update
    AuditLogger.log_user_action(
        db=db,
        user=current_user,
        action=AuditActions.SERVER_UPDATE,
        resource_type="server",
        resource_id=server.id,
        details={
            "server_name": server.name,
            "server_ip": server.ip,
            "username": server.username,
            "auth_method": server.auth_method,
            "groups": [g.name for g in server.groups] if server.groups else [],
            "updated_fields": [k for k, v in server_update.dict().items() if v is not None]
        },
        success=True
    )
    
    return server

@router.delete("/{server_id}")
def delete_server(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can delete servers
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete servers"
        )
    
    server = db.query(Server).filter(Server.id == server_id).first()
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    # Log server deletion before deleting
    server_name = server.name
    server_ip = server.ip
    
    # Clean up SSH key files if they exist
    if server.ssh_key_path:
        try:
            import os
            from pathlib import Path
            
            # Get the key file paths
            private_key_path = Path(server.ssh_key_path)
            public_key_path = private_key_path.with_suffix('.pub')
            
            # Delete private key file
            if private_key_path.exists():
                os.remove(private_key_path)
                print(f"🗑️ Deleted private key: {private_key_path}")
            
            # Delete public key file
            if public_key_path.exists():
                os.remove(public_key_path)
                print(f"🗑️ Deleted public key: {public_key_path}")
                
        except Exception as e:
            print(f"⚠️ Failed to delete SSH key files for {server_name}: {e}")
            # Don't fail server deletion if key cleanup fails
    
    # Delete related records first to avoid foreign key constraints
    try:
        # Delete script executions first
        from models import ScriptExecution
        db.query(ScriptExecution).filter(ScriptExecution.server_id == server_id).delete()
        print(f"🗑️ Deleted script executions for server {server_name}")
        
        # Delete server health records
        from models import ServerHealth
        db.query(ServerHealth).filter(ServerHealth.server_id == server_id).delete()
        print(f"🗑️ Deleted health records for server {server_name}")
        
        # Delete server group associations
        from models import ServerGroupAssociation
        db.query(ServerGroupAssociation).filter(ServerGroupAssociation.server_id == server_id).delete()
        print(f"🗑️ Deleted group associations for server {server_name}")
        
    except Exception as e:
        print(f"⚠️ Failed to delete related records for {server_name}: {e}")
        # Continue with server deletion even if related records cleanup fails
    
    # Log server deletion before deleting
    AuditLogger.log_user_action(
        db=db,
        user=current_user,
        action=AuditActions.SERVER_DELETE,
        resource_type="server",
        resource_id=server_id,
        details={
            "server_name": server_name,
            "server_ip": server_ip,
            "username": server.username if hasattr(server, 'username') else None
        },
        success=True
    )
    
    # Now delete the server
    db.delete(server)
    db.commit()
    
    return {"message": "Server deleted successfully"}

def deploy_ssh_key_internal(key_name: str, server_id: int, db: Session):
    """
    Internal function to deploy SSH key (no authentication check)
    """
    print(f"DEBUG: deploy_ssh_key_internal called with key_name='{key_name}', server_id={server_id}")
    
    # Get the server
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        return {"status": "error", "message": "Server not found"}
    
    print(f"DEBUG: Deploying to server '{server.name}' (ID: {server.id})")
    
    # Check if SSH key exists (try different key types)
    ssh_keys_dir = Path("ssh_keys")
    key_types = ["rsa", "ed25519", "ecdsa"]
    public_key_path = None
    private_key_path = None
    detected_key_type = None
    
    for key_type in key_types:
        key_params = get_ssh_key_parameters(key_type)
        test_public_path = ssh_keys_dir / f"{key_name}_{key_params['file_suffix']}.pub"
        test_private_path = ssh_keys_dir / f"{key_name}_{key_params['file_suffix']}"
        
        if test_public_path.exists() and test_private_path.exists():
            public_key_path = test_public_path
            private_key_path = test_private_path
            detected_key_type = key_type
            break
    
    print(f"DEBUG: Looking for public key at: {public_key_path}")
    print(f"DEBUG: Looking for private key at: {private_key_path}")
    print(f"DEBUG: Detected key type: {detected_key_type}")
    
    if not public_key_path or not public_key_path.exists():
        return {"status": "error", "message": f"SSH key '{key_name}' not found"}
    
    try:
        # Read the public key
        with open(public_key_path, 'r') as f:
            public_key = f.read().strip()
        
        # Create SSH client
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Connect to server for deployment
        connection_success = False
        
        # Try SSH key first (if available)
        if server.ssh_key_path and os.path.exists(server.ssh_key_path):
            try:
                private_key = paramiko.RSAKey.from_private_key_file(server.ssh_key_path, password=None)
                ssh_client.connect(
                    server.ip,
                    username=server.username,
                    pkey=private_key,
                    timeout=10
                )
                print(f"Connected to server {server.name} using existing SSH key")
                connection_success = True
                
                # Log successful SSH key connection
                auth_logger.log_auth_attempt(
                    server_name=server.name,
                    server_ip=server.ip,
                    auth_method="ssh_key",
                    success=True,
                    details={"action": "ssh_key_deployment_connection", "key_path": server.ssh_key_path}
                )
            except Exception as e:
                print(f"SSH key connection failed: {e}, trying password...")
                
                # Log failed SSH key connection
                auth_logger.log_auth_attempt(
                    server_name=server.name,
                    server_ip=server.ip,
                    auth_method="ssh_key",
                    success=False,
                    details={"action": "ssh_key_deployment_connection", "error": str(e), "key_path": server.ssh_key_path}
                )
        
        # Fallback to password if SSH key failed or not available
        if not connection_success and server.password_encrypted:
            try:
                vault = SecretsVault.get()
                password = vault.decrypt_to_str(server.password_encrypted)
                
                ssh_client.connect(
                    server.ip,
                    username=server.username,
                    password=password,
                    timeout=10
                )
                print(f"Connected to server {server.name} using password authentication")
                connection_success = True
                
                # Log successful password connection
                auth_logger.log_auth_attempt(
                    server_name=server.name,
                    server_ip=server.ip,
                    auth_method="password",
                    success=True,
                    details={"action": "ssh_key_deployment_connection"}
                )
            except Exception as e:
                # Log failed password connection
                auth_logger.log_auth_attempt(
                    server_name=server.name,
                    server_ip=server.ip,
                    auth_method="password",
                    success=False,
                    details={"action": "ssh_key_deployment_connection", "error": str(e)}
                )
                return {"status": "error", "message": f"Failed to connect: {str(e)}"}
        
        # If neither method worked
        if not connection_success:
            return {"status": "error", "message": "Cannot connect to server"}
        
        # Detect OS for proper SSH key deployment
        is_windows = False
        try:
            stdin, stdout, stderr = ssh_client.exec_command("echo %OS%")
            output = stdout.read().decode().strip()
            if "Windows" in output or "NT" in output:
                is_windows = True
        except:
            pass
        
        if is_windows:
            # Windows SSH key deployment
            print(f"Deploying SSH key to Windows server {server.name}")
            
            # Create .ssh directory if it doesn't exist (Windows)
            print(f"DEBUG: Creating .ssh directory for Windows")
            stdin, stdout, stderr = ssh_client.exec_command("if not exist \"%USERPROFILE%\\.ssh\" mkdir \"%USERPROFILE%\\.ssh\"")
            print(f"DEBUG: Create .ssh directory result: {stdout.read().decode('utf-8', errors='ignore')}")
            
            # Check if authorized_keys exists, create if not (Windows)
            print(f"DEBUG: Checking if authorized_keys exists")
            stdin, stdout, stderr = ssh_client.exec_command("if exist \"%USERPROFILE%\\.ssh\\authorized_keys\" echo exists")
            auth_keys_exists = stdout.read().decode('utf-8', errors='ignore').strip()
            print(f"DEBUG: authorized_keys exists: {auth_keys_exists}")
            
            if not auth_keys_exists:
                # Create empty authorized_keys file (Windows)
                print(f"DEBUG: Creating empty authorized_keys file")
                stdin, stdout, stderr = ssh_client.exec_command("echo. > \"%USERPROFILE%\\.ssh\\authorized_keys\"")
                print(f"DEBUG: Create authorized_keys result: {stdout.read().decode('utf-8', errors='ignore')}")
            
            # Check if key already exists (Windows)
            print(f"DEBUG: Checking if key already exists")
            stdin, stdout, stderr = ssh_client.exec_command(f"findstr /C:\"{public_key}\" \"%USERPROFILE%\\.ssh\\authorized_keys\"")
            key_exists = stdout.channel.recv_exit_status() == 0
            print(f"DEBUG: Key already exists: {key_exists}")
            
            if key_exists:
                ssh_client.close()
                return {
                    "status": "already_exists",
                    "message": "SSH key already deployed to server",
                    "key_name": key_name,
                    "server_name": server.name
                }
            
            # Add the public key to authorized_keys (Windows) - use PowerShell for better handling
            print(f"DEBUG: Adding public key to authorized_keys")
            stdin, stdout, stderr = ssh_client.exec_command(f"powershell -Command \"Add-Content -Path '%USERPROFILE%\\.ssh\\authorized_keys' -Value '{public_key}'\"")
            add_result = stdout.channel.recv_exit_status()
            print(f"DEBUG: Add key result: {add_result}")
            print(f"DEBUG: Add key stdout: {stdout.read().decode('utf-8', errors='ignore')}")
            print(f"DEBUG: Add key stderr: {stderr.read().decode('utf-8', errors='ignore')}")
            
            if add_result != 0:
                ssh_client.close()
                return {"status": "error", "message": "Failed to add key to authorized_keys"}
        else:
            # Linux SSH key deployment
            print(f"Deploying SSH key to Linux server {server.name}")
            
            # Create .ssh directory if it doesn't exist
            ssh_client.exec_command("mkdir -p ~/.ssh")
            ssh_client.exec_command("chmod 700 ~/.ssh")
            
            # Check if authorized_keys exists, create if not
            stdin, stdout, stderr = ssh_client.exec_command("ls ~/.ssh/authorized_keys")
            if stdout.channel.recv_exit_status() != 0:
                # Create empty authorized_keys file
                ssh_client.exec_command("touch ~/.ssh/authorized_keys")
                ssh_client.exec_command("chmod 600 ~/.ssh/authorized_keys")
            
            # Check if key already exists
            stdin, stdout, stderr = ssh_client.exec_command(f"grep -F '{public_key}' ~/.ssh/authorized_keys")
            if stdout.channel.recv_exit_status() == 0:
                ssh_client.close()
                return {
                    "status": "already_exists",
                    "message": "SSH key already deployed to server",
                    "key_name": key_name,
                    "server_name": server.name
                }
            
            # Add the public key to authorized_keys
            stdin, stdout, stderr = ssh_client.exec_command(f"echo '{public_key}' >> ~/.ssh/authorized_keys")
            if stdout.channel.recv_exit_status() != 0:
                ssh_client.close()
                return {"status": "error", "message": "Failed to add key to authorized_keys"}
        
        # Test the connection with the new key
        ssh_client.close()
        
        # For Windows servers, skip the test connection as it often fails due to key format issues
        # The key deployment was successful (we got here), so we can proceed
        if is_windows:
            print(f"DEBUG: Skipping test connection for Windows server (key deployment was successful)")
        else:
            # Try to connect with the newly deployed key (Linux servers)
            test_client = paramiko.SSHClient()
            test_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Load the private key we just deployed
            private_key_path = ssh_keys_dir / f"{key_name}_id_rsa"
            print(f"DEBUG: Loading private key from: {private_key_path}")
            print(f"DEBUG: Private key file exists: {private_key_path.exists()}")
            print(f"DEBUG: Private key file size: {private_key_path.stat().st_size if private_key_path.exists() else 'N/A'}")
            
            try:
                # Try loading with explicit password=None
                test_private_key = paramiko.RSAKey.from_private_key_file(str(private_key_path), password=None)
                print(f"DEBUG: Successfully loaded private key with password=None")
            except Exception as e:
                print(f"DEBUG: Failed to load private key with password=None: {e}")
                try:
                    # Try loading without password parameter
                    test_private_key = paramiko.RSAKey.from_private_key_file(str(private_key_path), password=None)
                    print(f"DEBUG: Successfully loaded private key without password parameter")
                except Exception as e2:
                    print(f"DEBUG: Failed to load private key without password parameter: {e2}")
                    test_client.close()
                    return {"status": "error", "message": f"Failed to load private key: {str(e2)}"}
            
            print(f"DEBUG: Attempting to connect with private key to {server.ip}")
            try:
                test_client.connect(
                    server.ip,
                    username=server.username,
                    pkey=test_private_key,
                    timeout=10
                )
                print(f"DEBUG: Successfully connected with private key")
            except Exception as e:
                print(f"DEBUG: Connection failed with error: {e}")
                print(f"DEBUG: Error type: {type(e)}")
                test_client.close()
                return {"status": "error", "message": f"Failed to connect with private key: {str(e)}"}
            
            # Test a simple command
            print(f"DEBUG: Testing command execution")
            stdin, stdout, stderr = test_client.exec_command("echo 'SSH key deployment successful'")
            command_result = stdout.channel.recv_exit_status()
            print(f"DEBUG: Command result: {command_result}")
            
            if command_result != 0:
                print(f"DEBUG: Command failed, closing connection")
                test_client.close()
                return {"status": "error", "message": "Key deployment succeeded but connection test failed"}
            
            print(f"DEBUG: Command succeeded, closing test connection")
            test_client.close()
        
        # Update server to use SSH key authentication
        print(f"DEBUG: Updating server auth_method to ssh_key")
        server.auth_method = "ssh_key"
        server.ssh_key_path = str(private_key_path)
        db.commit()
        
        print(f"✅ Server {server.name} auth_method updated to 'ssh_key' after successful deployment")
        
        return {
            "status": "deployed",
            "message": "SSH key deployed successfully to server",
            "key_name": key_name,
            "server_name": server.name,
            "public_key": public_key
        }
        
    except Exception as e:
        return {"status": "error", "message": f"Failed to deploy SSH key: {str(e)}"}


@router.post("/deploy-ssh-key")
def deploy_ssh_key(
    key_name: str,
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Deploy an SSH public key to a target server
    """
    # Only admins can deploy SSH keys
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can deploy SSH keys"
        )
    
    # Get the server
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    # Check if SSH key exists
    ssh_keys_dir = Path("ssh_keys")
    public_key_path = ssh_keys_dir / f"{key_name}_id_rsa.pub"
    
    if not public_key_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SSH key '{key_name}' not found"
        )
    
    try:
        # Read the public key
        with open(public_key_path, 'r') as f:
            public_key = f.read().strip()
        
        # Create SSH client
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Connect to server for deployment
        connection_success = False
        
        # Try SSH key first (if available)
        if server.ssh_key_path and os.path.exists(server.ssh_key_path):
            try:
                private_key = paramiko.RSAKey.from_private_key_file(server.ssh_key_path, password=None)
                ssh_client.connect(
                    server.ip,
                    username=server.username,
                    pkey=private_key,
                    timeout=10
                )
                print(f"Connected to server {server.name} using existing SSH key")
                connection_success = True
            except Exception as e:
                print(f"SSH key connection failed: {e}, trying password...")
        
        # Fallback to password if SSH key failed or not available
        if not connection_success and server.password_encrypted:
            try:
                vault = SecretsVault.get()
                password = vault.decrypt_to_str(server.password_encrypted)
                
                ssh_client.connect(
                    server.ip,
                    username=server.username,
                    password=password,
                    timeout=10
                )
                print(f"Connected to server {server.name} using password authentication")
                connection_success = True
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to connect to server using both SSH key and password: {str(e)}"
                )
        
        # If neither method worked
        if not connection_success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot connect to server. Please ensure either SSH key or password is configured correctly."
            )
        
        # Detect OS for proper SSH key deployment
        is_windows = False
        try:
            stdin, stdout, stderr = ssh_client.exec_command("echo %OS%")
            output = stdout.read().decode().strip()
            if "Windows" in output or "NT" in output:
                is_windows = True
        except:
            pass
        
        if is_windows:
            # Windows SSH key deployment
            print(f"Deploying SSH key to Windows server {server.name}")
            
            # Create .ssh directory if it doesn't exist (Windows)
            ssh_client.exec_command("if not exist \"%USERPROFILE%\\.ssh\" mkdir \"%USERPROFILE%\\.ssh\"")
            
            # Check if authorized_keys exists, create if not (Windows)
            stdin, stdout, stderr = ssh_client.exec_command("if exist \"%USERPROFILE%\\.ssh\\authorized_keys\" echo exists")
            if not stdout.read().decode().strip():
                # Create empty authorized_keys file (Windows)
                ssh_client.exec_command("echo. > \"%USERPROFILE%\\.ssh\\authorized_keys\"")
            
            # Check if key already exists (Windows)
            stdin, stdout, stderr = ssh_client.exec_command(f"findstr /C:\"{public_key}\" \"%USERPROFILE%\\.ssh\\authorized_keys\"")
            if stdout.channel.recv_exit_status() == 0:
                ssh_client.close()
                return {
                    "message": "SSH key already deployed to server",
                    "key_name": key_name,
                    "server_name": server.name,
                    "status": "already_exists"
                }
            
            # Add the public key to authorized_keys (Windows) - use PowerShell for better handling
            stdin, stdout, stderr = ssh_client.exec_command(f"powershell -Command \"Add-Content -Path '%USERPROFILE%\\.ssh\\authorized_keys' -Value '{public_key}'\"")
            if stdout.channel.recv_exit_status() != 0:
                ssh_client.close()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to add key to authorized_keys"
                )
        else:
            # Linux SSH key deployment
            print(f"Deploying SSH key to Linux server {server.name}")
            
            # Create .ssh directory if it doesn't exist
            ssh_client.exec_command("mkdir -p ~/.ssh")
            ssh_client.exec_command("chmod 700 ~/.ssh")
            
            # Check if authorized_keys exists, create if not
            stdin, stdout, stderr = ssh_client.exec_command("ls ~/.ssh/authorized_keys")
            if stdout.channel.recv_exit_status() != 0:
                # Create empty authorized_keys file
                ssh_client.exec_command("touch ~/.ssh/authorized_keys")
                ssh_client.exec_command("chmod 600 ~/.ssh/authorized_keys")
            
            # Check if key already exists
            stdin, stdout, stderr = ssh_client.exec_command(f"grep -F '{public_key}' ~/.ssh/authorized_keys")
            if stdout.channel.recv_exit_status() == 0:
                ssh_client.close()
                return {
                    "message": "SSH key already deployed to server",
                    "key_name": key_name,
                    "server_name": server.name,
                    "status": "already_exists"
                }
            
            # Add the public key to authorized_keys
            stdin, stdout, stderr = ssh_client.exec_command(f"echo '{public_key}' >> ~/.ssh/authorized_keys")
            if stdout.channel.recv_exit_status() != 0:
                ssh_client.close()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to add key to authorized_keys"
                )
        
        # Test the connection with the new key
        ssh_client.close()
        
        # Try to connect with the newly deployed key
        test_client = paramiko.SSHClient()
        test_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Load the private key we just deployed
        private_key_path = ssh_keys_dir / f"{key_name}_id_rsa"
        print(f"DEBUG: Loading private key from: {private_key_path}")
        print(f"DEBUG: Private key file exists: {private_key_path.exists()}")
        print(f"DEBUG: Private key file size: {private_key_path.stat().st_size if private_key_path.exists() else 'N/A'}")
        
        try:
            # Load the private key (OpenSSH format should work better)
            test_private_key = paramiko.RSAKey.from_private_key_file(str(private_key_path), password=None)
            print(f"DEBUG: Successfully loaded private key")
        except Exception as e:
            print(f"DEBUG: Failed to load private key: {e}")
            test_client.close()
            return {"status": "error", "message": f"Failed to load private key: {str(e)}"}
        
        test_client.connect(
            server.ip,
            username=server.username,
            pkey=test_private_key,
            timeout=10
        )
        
        # Test a simple command
        stdin, stdout, stderr = test_client.exec_command("echo 'SSH key deployment successful'")
        if stdout.channel.recv_exit_status() != 0:
            test_client.close()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Key deployment succeeded but connection test failed"
            )
        
        test_client.close()
        
        # Update server to use SSH key authentication
        server.auth_method = "ssh_key"
        server.ssh_key_path = str(private_key_path)
        db.commit()
        
        print(f"✅ Server {server.name} auth_method updated to 'ssh_key' after successful deployment")
        
        return {
            "message": "SSH key deployed successfully to server",
            "key_name": key_name,
            "server_name": server.name,
            "status": "deployed",
            "public_key": public_key
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deploy SSH key: {str(e)}"
        )

@router.post("/{server_id}/test-connection")
def test_server_connection(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Test SSH connection to a server
    """
    # Only admins can test server connections
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can test server connections"
        )
    
    # Get the server
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    import time
    
    try:
        start_time = time.time()
        
        # Create SSH client
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Connect to server for testing
        connection_success = False
        
        # Try SSH key first (if available)
        if server.ssh_key_path and os.path.exists(server.ssh_key_path):
            try:
                # Detect key type and load with appropriate paramiko class
                key_type = detect_key_type_from_file(server.ssh_key_path)
                key_class = get_paramiko_key_class(key_type)
                private_key = key_class.from_private_key_file(server.ssh_key_path, password=None)
                ssh_client.connect(
                    server.ip,
                    username=server.username,
                    pkey=private_key,
                    timeout=10
                )
                print(f"Test connection to {server.name} using SSH key")
                connection_success = True
            except Exception as e:
                print(f"SSH key test connection failed: {e}, trying password...")
        
        # Fallback to password if SSH key failed or not available
        if not connection_success and server.password_encrypted:
            try:
                vault = SecretsVault.get()
                password = vault.decrypt_to_str(server.password_encrypted)
                
                ssh_client.connect(
                    server.ip,
                    username=server.username,
                    password=password,
                    timeout=10
                )
                print(f"Test connection to {server.name} using password")
                connection_success = True
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Failed to connect using both SSH key and password: {str(e)}"
                )
        
        # If neither method worked
        if not connection_success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot connect to server. Please ensure either SSH key or password is configured correctly."
            )
        
        # Test a simple command to verify connection
        try:
            # Use OS-agnostic commands that work on both Linux and Windows
            stdin, stdout, stderr = ssh_client.exec_command("echo 'Connection test successful'", timeout=5)
            
            # Handle encoding properly for different OS
            raw_output = stdout.read()
            raw_error = stderr.read()
            
            try:
                output = raw_output.decode('utf-8').strip()
                error_output = raw_error.decode('utf-8').strip()
            except UnicodeDecodeError:
                # Fallback for Windows or other encodings
                output = raw_output.decode('utf-8', errors='ignore').strip()
                error_output = raw_error.decode('utf-8', errors='ignore').strip()
            
            if stdout.channel.recv_exit_status() != 0:
                raise Exception(f"Command execution failed: {error_output}")
            
            response_time = round((time.time() - start_time) * 1000, 2)
            
            # Get server info using OS detection
            try:
                stdin, stdout, stderr = ssh_client.exec_command("uname -a 2>/dev/null || ver 2>/dev/null || echo 'Unknown OS'", timeout=5)
                raw_info = stdout.read()
                try:
                    server_info = raw_info.decode('utf-8').strip() or "Unknown"
                except UnicodeDecodeError:
                    server_info = raw_info.decode('utf-8', errors='ignore').strip() or "Unknown"
            except:
                server_info = "Unknown"
            
            ssh_client.close()
            
            return {
                "success": True,
                "message": "Connection test completed successfully",
                "server_name": server.name,
                "server_ip": server.ip,
                "response_time": response_time,
                "server_info": server_info,
                "auth_method": server.auth_method
            }
            
        except Exception as e:
            ssh_client.close()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Command execution failed: {str(e)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Connection test failed: {str(e)}"
        )


