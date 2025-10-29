from pydantic import BaseModel, EmailStr, validator, Field
from typing import Optional, List
from datetime import datetime, timezone

# User schemas
class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str
    role: Optional[str] = "user"

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None

class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(UserBase):
    id: int
    role: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int

# Server Group schemas (moved before Server schemas)
class ServerGroupBase(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "#6366f1"

class ServerGroupCreate(ServerGroupBase):
    pass

class ServerGroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None

class ServerBrief(BaseModel):
    id: int
    name: str
    ip: str

    class Config:
        from_attributes = True

class ServerGroupResponse(ServerGroupBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    servers: List[ServerBrief] = []

    class Config:
        from_attributes = True

class ServerGroupListResponse(BaseModel):
    groups: List[ServerGroupResponse]
    total: int

# Server schemas
class ServerBase(BaseModel):
    name: str
    ip: str
    username: str
    auth_method: str = "password"
    timezone: str = "UTC"
    detected_os: Optional[str] = None
    os_detection_method: Optional[str] = None

class ServerCreate(ServerBase):
    password: Optional[str] = None
    password_encrypted: Optional[str] = None
    ssh_key_path: Optional[str] = None
    ssh_key_passphrase: Optional[str] = None
    group_ids: Optional[List[int]] = []  # List of group IDs instead of single group_id

class ServerUpdate(BaseModel):
    name: Optional[str] = None
    ip: Optional[str] = None
    username: Optional[str] = None
    auth_method: Optional[str] = None
    timezone: Optional[str] = None
    password: Optional[str] = None
    password_encrypted: Optional[str] = None
    ssh_key_path: Optional[str] = None
    ssh_key_passphrase: Optional[str] = None
    group_ids: Optional[List[int]] = []  # List of group IDs instead of single group_id

class ServerResponse(ServerBase):
    id: int
    groups: List[ServerGroupResponse] = []  # List of groups instead of single group
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Server List Response (add back)
class ServerListResponse(BaseModel):
    servers: List[ServerResponse]
    total: int

# Script schemas
class ScriptBase(BaseModel):
    name: str
    description: Optional[str] = None
    content: str
    script_type: str = "bash"
    category: str = "general"
    parameters: Optional[str] = None  # JSON string
    # Optional execution settings (None -> use defaults)
    concurrency_limit: Optional[int] = None
    continue_on_error: Optional[bool] = None
    per_server_timeout_seconds: Optional[int] = None

class ScriptCreate(ScriptBase):
    pass

class ScriptUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    script_type: Optional[str] = None
    category: Optional[str] = None
    parameters: Optional[str] = None
    concurrency_limit: Optional[int] = None
    continue_on_error: Optional[bool] = None
    per_server_timeout_seconds: Optional[int] = None

class ScriptResponse(ScriptBase):
    id: int
    created_by: int
    creator: Optional[UserResponse] = None  # Will contain user info from relationship
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ScriptListResponse(BaseModel):
    scripts: List[ScriptResponse]
    total: int

# Script Execution schemas
class ScriptExecutionBase(BaseModel):
    # script_id can be null for historical rows after script deletion
    script_id: Optional[int] = None
    server_id: int
    parameters_used: Optional[str] = None

class ScriptExecutionCreate(ScriptExecutionBase):
    pass

class ScriptExecutionResponse(ScriptExecutionBase):
    id: int
    executed_by: Optional[int] = None
    status: str
    output: Optional[str] = None
    error: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @validator('started_at', 'completed_at', pre=False, always=True)
    def _ensure_timezone(cls, v):
        if v is None:
            return v
        if isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

class ScriptExecutionListResponse(BaseModel):
    executions: List[ScriptExecutionResponse]
    total: int

# Schedule schemas
class ScheduleBase(BaseModel):
    name: str
    script_id: int
    target_type: str  # 'server' or 'group'
    target_id: int
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    timezone: Optional[str] = "UTC"
    enabled: Optional[bool] = True

class ScheduleCreate(ScheduleBase):
    pass

class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    script_id: Optional[int] = None
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    timezone: Optional[str] = None
    enabled: Optional[bool] = None

class ScheduleResponse(ScheduleBase):
    id: int
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    created_by: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ScheduleListResponse(BaseModel):
    schedules: List[ScheduleResponse]
    total: int

# Settings schemas
class SettingsBase(BaseModel):
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_pass: Optional[str] = None
    from_email: Optional[str] = None
    digest_to_emails: Optional[str] = None
    digest_only_failed: Optional[bool] = False
    ssh_key_type: Optional[str] = "rsa"  # "rsa", "ed25519", "ecdsa"
    virtual_timeout_duration: Optional[int] = 60  # Duration to capture output from infinite scripts
    long_running_delay_seconds: Optional[int] = 300  # After this delay, mark infinite as long_running
    schedule_trigger_tolerance_seconds: Optional[int] = 30  # Tolerance for scheduler firing
    access_token_expire_minutes: Optional[int] = 30  # JWT expiry minutes
    max_concurrent_executions: Optional[int] = Field(default=4)

class SettingsUpdate(SettingsBase):
    pass

class SettingsResponse(SettingsBase):
    id: int
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# Audit Log Schemas
class AuditLogBase(BaseModel):
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True

class AuditLogCreate(AuditLogBase):
    user_id: Optional[int] = None

class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True
    created_at: datetime
    user: Optional[UserResponse] = None

    class Config:
        from_attributes = True

class AuditLogListResponse(BaseModel):
    logs: List[AuditLogResponse]
    total: int
    page: int
    size: int

# Marketplace Script Schemas
class MarketplaceScriptBase(BaseModel):
    name: str
    description: Optional[str] = None
    content: str
    script_type: str
    category: Optional[str] = None
    tags: Optional[str] = None  # JSON array of tags
    parameters: Optional[str] = None  # JSON schema for parameters
    version: str = "1.0.0"
    compatibility_notes: Optional[str] = None

class MarketplaceScriptCreate(MarketplaceScriptBase):
    is_public: bool = True

class MarketplaceScriptUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    script_type: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    parameters: Optional[str] = None
    version: Optional[str] = None
    compatibility_notes: Optional[str] = None
    is_public: Optional[bool] = None

class MarketplaceScriptResponse(MarketplaceScriptBase):
    id: int
    author_id: int
    author_username: str
    is_public: bool
    is_verified: bool
    download_count: int
    rating_average: float
    rating_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    author: Optional[UserResponse] = None

    class Config:
        from_attributes = True

class MarketplaceScriptListResponse(BaseModel):
    scripts: List[MarketplaceScriptResponse]
    total: int
    page: int
    size: int


# Import/Export Schemas
class ScriptImportRequest(BaseModel):
    marketplace_script_id: int
    new_name: Optional[str] = None  # Allow renaming on import

class ScriptExportRequest(BaseModel):
    script_id: int
    is_public: bool = True
    description: Optional[str] = None
    tags: Optional[str] = None

# Server Health Schemas
class ServerHealthBase(BaseModel):
    uptime_seconds: Optional[int] = None
    load_1min: Optional[float] = None
    load_5min: Optional[float] = None
    load_15min: Optional[float] = None
    disk_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    cpu_usage: Optional[float] = None
    network_interfaces: Optional[dict] = None
    status: str = "unknown"

class ServerHealthResponse(ServerHealthBase):
    id: int
    server_id: int
    last_checked: datetime
    created_at: datetime

    class Config:
        from_attributes = True

class ServerHealthListResponse(BaseModel):
    health_records: List[ServerHealthResponse]
    total: int

class ServerHealthSummary(BaseModel):
    server_id: int
    server_name: str
    status: str
    uptime_seconds: Optional[int] = None
    load_1min: Optional[float] = None
    disk_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    last_checked: Optional[datetime] = None
