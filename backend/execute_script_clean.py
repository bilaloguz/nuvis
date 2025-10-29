@router.post("/{script_id}/execute", response_model=ScriptExecutionResponse)
def execute_script(
    script_id: int,
    execution_create: ScriptExecutionCreate,
    timeout_seconds: int | None = Query(None, ge=0, le=3600, description="Override per-server timeout (0 = no timeout, default script or 60)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only admins can execute scripts
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can execute scripts"
        )
    
    # Verify script exists
    script = db.query(Script).filter(Script.id == script_id).first()
    if script is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Script not found"
        )
    
    # Verify server exists
    server = db.query(Server).filter(Server.id == execution_create.server_id).first()
    if server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    # Check if this is an infinite script
    is_infinite = (timeout_seconds == 0) or (timeout_seconds is None and script.per_server_timeout_seconds == 0)
    
    # Get virtual timeout duration from settings for infinite scripts
    from sqlalchemy.exc import OperationalError
    from sqlalchemy import text
    settings = db.query(Settings).first()
    if not settings:
        settings = Settings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    virtual_timeout_duration = settings.virtual_timeout_duration or 60

    # Create execution record
    execution = ScriptExecution(
        script_id=script.id,
        server_id=server.id,
        executed_by=current_user.id,
        status="running",
        started_at=datetime.now(timezone.utc)
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    # Start background task to mark as long_running after a configurable delay
    import threading
    import time
    # Read configurable delay from settings if available; default to 300s
    try:
        long_running_delay_seconds = getattr(settings, 'long_running_delay_seconds', 300) or 300
    except Exception:
        long_running_delay_seconds = 300

    def mark_long_running(execution_id: int):
        time.sleep(long_running_delay_seconds)
        try:
            # Check if still running
            from database import SessionLocal
            db_session = SessionLocal()
            exec_check = db_session.query(ScriptExecution).filter(ScriptExecution.id == execution_id).first()
            if exec_check and exec_check.status == "running":
                exec_check.status = "long_running"
                db_session.commit()
                print(f"Marked execution {execution_id} as long_running after {long_running_delay_seconds}s")
        except Exception as e:
            print(f"Error marking execution as long_running: {e}")
        finally:
            if 'db_session' in locals():
                db_session.close()
    
    long_running_thread = threading.Thread(target=mark_long_running, args=(execution.id,), daemon=True)
    long_running_thread.start()
    
    # Execute over SSH using the robust SSH connection manager
    try:
        from ssh_script_executor import execute_script_on_server
        from ssh_manager import SSHConnectionError
        
        # Log successful authentication attempt
        auth_logger.log_script_execution_auth(
            script_name=script.name,
            server_name=server.name,
            server_ip=server.ip,
            auth_method_used="ssh_manager",
            success=True,
            details={"user_id": current_user.id}
        )
        
        # Execute the script
        out, err, exit_code = execute_script_on_server(
            script=script,
            server=server,
            execution=execution,
            is_infinite=is_infinite,
            virtual_timeout_duration=virtual_timeout_duration
        )
        
        # Handle script execution results
        if is_infinite:
            # For infinite scripts, keep status as "running" and don't set completed_at
            execution.status = "running"
            execution.output = out
            execution.error = None  # No error for infinite scripts
            # Don't set completed_at - let it stay None
        else:
            # Regular script
            execution.status = "completed" if exit_code == 0 else "failed"
            execution.output = out
            execution.error = err if exit_code != 0 else None
            execution.completed_at = func.now()

        db.commit()
        db.refresh(execution)
        return execution
        
    except SSHConnectionError as e:
        print(f"SSH connection failed for {server.name}: {e}")
        
        # Log failed authentication
        auth_logger.log_script_execution_auth(
            script_name=script.name,
            server_name=server.name,
            server_ip=server.ip,
            auth_method_used="ssh_manager",
            success=False,
            details={"error": str(e), "user_id": current_user.id}
        )
        
        execution.status = "failed"
        execution.error = f"SSH connection failed: {e}"
        execution.completed_at = func.now()
        db.commit()
        db.refresh(execution)
        return execution
        
    except Exception as e:
        execution.status = "failed"
        execution.error = str(e)
        execution.completed_at = func.now()
        db.commit()
        db.refresh(execution)
        return execution


