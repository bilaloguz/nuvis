from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user")  # "admin" or "user"
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    audit_logs = relationship("AuditLog", back_populates="user")
    created_scripts = relationship("Script", back_populates="creator")
    created_workflows = relationship("Workflow", back_populates="creator")
    created_schedules = relationship("Schedule", back_populates="creator")

class Server(Base):
    __tablename__ = "servers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    ip = Column(String, nullable=False)
    username = Column(String, nullable=False)
    auth_method = Column(String, default="password")  # "password" or "ssh_key"
    password_hash = Column(String, nullable=True)
    password_encrypted = Column(Text, nullable=True)
    ssh_key_path = Column(String, nullable=True)
    ssh_key_passphrase = Column(String, nullable=True)
    detected_os = Column(String(50), nullable=True)  # "linux", "windows", "macos", "freebsd", "unknown"
    os_detection_method = Column(String(20), nullable=True)  # "ssh_connect", "port_scan", "manual", "unknown"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    groups = relationship("ServerGroup", secondary="server_group_associations", back_populates="servers")
    health_records = relationship("ServerHealth", back_populates="server")

class ServerGroup(Base):
    __tablename__ = "server_groups"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String, default="#007bff")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    servers = relationship("Server", secondary="server_group_associations", back_populates="groups")

class ServerGroupAssociation(Base):
    __tablename__ = "server_group_associations"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("server_groups.id"), nullable=False)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False)

class Script(Base):
    __tablename__ = "scripts"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    # Optional metadata/organization fields
    category = Column(String, nullable=True)
    parameters = Column(Text, nullable=True)
    script_type = Column(String, default="bash")  # "bash", "python", "powershell"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Execution settings
    concurrency_limit = Column(Integer, default=5)
    continue_on_error = Column(Boolean, default=True)
    per_server_timeout_seconds = Column(Integer, default=60)
    
    # Relationships
    executions = relationship("ScriptExecution", back_populates="script")
    creator = relationship("User", back_populates="created_scripts")

class ScriptExecution(Base):
    __tablename__ = "script_executions"
    
    id = Column(Integer, primary_key=True, index=True)
    script_id = Column(Integer, ForeignKey("scripts.id"), nullable=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False)
    executed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String, default="running")  # "running", "completed", "failed", "long_running"
    output = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    parameters_used = Column(Text, nullable=True)
    
    # Relationships
    script = relationship("Script", back_populates="executions")
    server = relationship("Server")
    executor = relationship("User")

class MarketplaceScript(Base):
    __tablename__ = "marketplace_scripts"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=True)
    script_type = Column(String, default="shell")  # "shell", "powershell", "python", etc.
    content = Column(Text, nullable=False)
    parameters = Column(Text, nullable=True)  # JSON string for parameters
    tags = Column(Text, nullable=True)  # JSON array of tags
    author = Column(String, nullable=True)
    version = Column(String, default="1.0.0")
    downloads = Column(Integer, default=0)
    rating = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Settings(Base):
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True, index=True)
    smtp_host = Column(String, nullable=True)
    smtp_port = Column(Integer, nullable=True)
    smtp_user = Column(String, nullable=True)
    smtp_pass = Column(String, nullable=True)
    from_email = Column(String, nullable=True)
    digest_to_emails = Column(String, nullable=True)
    digest_only_failed = Column(Integer, default=0)
    ssh_key_type = Column(String, default="rsa")  # "rsa", "ed25519", "ecdsa"
    virtual_timeout_duration = Column(Integer, default=60)  # Duration to capture output from infinite scripts
    long_running_delay_seconds = Column(Integer, default=300)  # Delay before marking execution as long_running
    schedule_trigger_tolerance_seconds = Column(Integer, default=30)  # Tolerance to fire schedules near their time
    access_token_expire_minutes = Column(Integer, default=30)  # JWT access token expiry
    max_concurrent_executions = Column(Integer, default=8)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Schedule(Base):
    __tablename__ = "schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    script_id = Column(Integer, ForeignKey("scripts.id"), nullable=False)
    target_type = Column(String, nullable=False)  # "server" or "group"
    target_id = Column(Integer, nullable=False)
    cron_expression = Column(String, nullable=True)
    interval_seconds = Column(Integer, nullable=True)
    timezone = Column(String, default="UTC")
    enabled = Column(Boolean, default=True)
    # Track scheduling
    next_run_at = Column(DateTime, nullable=True)
    last_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    script = relationship("Script")
    creator = relationship("User", back_populates="created_schedules")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=True)
    resource_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    success = Column(Boolean, default=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")


class ServerHealth(Base):
    __tablename__ = "server_health"
    
    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False)
    status = Column(String, default="unknown")  # "healthy", "warning", "critical", "unknown"
    cpu_usage = Column(Float, nullable=True)
    memory_usage = Column(Float, nullable=True)
    disk_usage = Column(Float, nullable=True)
    load_1min = Column(Float, nullable=True)
    load_5min = Column(Float, nullable=True)
    load_15min = Column(Float, nullable=True)
    uptime_seconds = Column(Integer, nullable=True)
    network_interfaces = Column(Text, nullable=True)  # JSON data
    last_checked = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    server = relationship("Server", back_populates="health_records")

class Workflow(Base):
    __tablename__ = "workflows"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Trigger settings
    trigger_type = Column(String, default='user')  # user | schedule | webhook
    schedule_cron = Column(String, nullable=True)
    schedule_timezone = Column(String, nullable=True)
    webhook_url = Column(String, nullable=True)
    webhook_method = Column(String, nullable=True)
    webhook_payload = Column(Text, nullable=True)

    # Retry policy (per node)
    max_retries = Column(Integer, nullable=True, default=3)
    retry_interval_seconds = Column(Integer, nullable=True, default=60)
    
    # Group failure policy
    group_failure_policy = Column(String, nullable=True, default='any')  # 'any' or 'all'

    # Relationships
    nodes = relationship("WorkflowNode", back_populates="workflow", cascade="all, delete-orphan")
    edges = relationship("WorkflowEdge", back_populates="workflow", cascade="all, delete-orphan")
    runs = relationship("WorkflowRun", back_populates="workflow", cascade="all, delete-orphan")
    creator = relationship("User", back_populates="created_workflows")

class WorkflowNode(Base):
    __tablename__ = "workflow_nodes"
    
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False)
    key = Column(String, nullable=False)  # Unique key for the node within the workflow
    name = Column(String, nullable=False)
    script_id = Column(Integer, ForeignKey("scripts.id"), nullable=True)
    target_type = Column(String, nullable=True)  # "server" or "group"
    target_id = Column(Integer, nullable=True)
    parameters = Column(Text, nullable=True)  # JSON string for node parameters
    position = Column(Text, nullable=True)  # JSON string for node position on canvas
    
    # Relationships
    workflow = relationship("Workflow", back_populates="nodes")
    script = relationship("Script")

class WorkflowEdge(Base):
    __tablename__ = "workflow_edges"
    
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False)
    source_node_id = Column(Integer, nullable=False)
    target_node_id = Column(Integer, nullable=False)
    condition = Column(String, default="on_success")  # "on_success" or "on_failure"
    
    # Relationships
    workflow = relationship("Workflow", back_populates="edges")

class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False)
    triggered_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String, default="running")  # "running", "completed", "failed"
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    context = Column(Text, nullable=True)  # JSON context data
    
    # Relationships
    workflow = relationship("Workflow", back_populates="runs")
    triggerer = relationship("User")
    node_runs = relationship("WorkflowNodeRun", back_populates="workflow_run", cascade="all, delete-orphan")

class WorkflowNodeRun(Base):
    __tablename__ = "workflow_node_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    workflow_run_id = Column(Integer, ForeignKey("workflow_runs.id"), nullable=False)
    node_id = Column(Integer, nullable=False)
    status = Column(String, default="running")  # "running", "completed", "failed"
    output = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    workflow_run = relationship("WorkflowRun", back_populates="node_runs")

