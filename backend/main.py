from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
from models import Base
from routers import auth, users, servers, server_groups, terminal, scripts, schedules, reports, settings as settings_router, audit, marketplace, health, notifications
from routers import workflows
from scheduler import start_scheduler, stop_scheduler
import logging
import subprocess
import os

# Suppress paramiko transport debug logs
logging.getLogger("paramiko.transport").setLevel(logging.WARNING)

app = FastAPI(title="biRun API", version=".1")

origins = ["*", "http://192.168.11.149:8000", "http://192.168.11.149:3000", "http://192.168.11.149:9753", "http://192.168.11.149:3001", "http://192.168.11.149:4000", "http://192.168.11.149:8080"]

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(servers.router, prefix="/api/servers", tags=["servers"])
app.include_router(server_groups.router, prefix="/api/server-groups", tags=["server-groups"])
app.include_router(scripts.router, prefix="/api/scripts", tags=["scripts"])
app.include_router(terminal.router, prefix="/api", tags=["terminal"])
app.include_router(schedules.router, prefix="/api/schedules", tags=["schedules"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(marketplace.router, prefix="/api/marketplace", tags=["marketplace"])
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(workflows.router, prefix="/api", tags=["workflows"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])

# Create database tables
Base.metadata.create_all(bind=engine)

@app.get("/")
def read_root():
    return {"message": "biRun API"}


@app.on_event("startup")
def on_startup():
    # Run Alembic migrations on startup (best-effort)
    try:
        print("DEBUG: Running Alembic migrations...")
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print("DEBUG: Alembic migrations completed successfully")
        else:
            print(f"DEBUG: Alembic migration failed: {result.stderr}")
    except Exception as e:
        print(f"DEBUG: Failed to run Alembic migrations: {e}")
        # Continue startup even if migrations fail
    
    try:
        print("DEBUG: Starting scheduler...")
        start_scheduler()
        print("DEBUG: Scheduler started successfully")
    except Exception as e:
        print(f"DEBUG: Failed to start scheduler: {e}")
        pass


@app.on_event("shutdown")
def on_shutdown():
    try:
        stop_scheduler()
    except Exception:
        pass
