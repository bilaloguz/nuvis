from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
import time
import json
import asyncio
from sqlalchemy import text

from database import get_db, SessionLocal
from auth import get_current_user
from models import (
    Workflow, WorkflowNode, WorkflowEdge, WorkflowRun, WorkflowNodeRun,
    Script, User, Server, ServerGroup, ServerGroupAssociation, ScriptExecution
)
from scheduler import _run_script_on_server
from audit_utils import log_audit
import threading
from rq_queue import get_queue
from tasks import execute_script_job
from rq.job import Job
from rq_queue import get_redis

# WebSocket connection manager for real-time workflow monitoring
class WorkflowConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, List[WebSocket]] = {}
        self.workflow_runs: dict[int, dict] = {}  # Track active workflow runs

    async def connect(self, websocket: WebSocket, workflow_run_id: int):
        await websocket.accept()
        if workflow_run_id not in self.active_connections:
            self.active_connections[workflow_run_id] = []
        self.active_connections[workflow_run_id].append(websocket)

    def disconnect(self, websocket: WebSocket, workflow_run_id: int):
        if workflow_run_id in self.active_connections:
            self.active_connections[workflow_run_id].remove(websocket)
            if not self.active_connections[workflow_run_id]:
                del self.active_connections[workflow_run_id]

    async def send_update(self, workflow_run_id: int, message: dict):
        if workflow_run_id in self.active_connections:
            for connection in self.active_connections[workflow_run_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    # Remove dead connections
                    self.active_connections[workflow_run_id].remove(connection)

    def update_workflow_run(self, workflow_run_id: int, status: str, current_node: Optional[str] = None, progress: Optional[float] = None):
        if workflow_run_id not in self.workflow_runs:
            self.workflow_runs[workflow_run_id] = {}

        self.workflow_runs[workflow_run_id].update({
            'status': status,
            'current_node': current_node,
            'progress': progress,
            'last_updated': datetime.utcnow().isoformat()
        })

manager = WorkflowConnectionManager()

async def send_workflow_update(workflow_run_id: int, message: dict):
    """Helper function to send WebSocket updates"""
    await manager.send_update(workflow_run_id, message)

def _safe_send_update(run_id: int, message: dict):
    """Safely send workflow update, handling cases where no event loop is running"""
    try:
        # Check if there's a running event loop
        loop = asyncio.get_running_loop()
        if loop and not loop.is_closed():
            asyncio.create_task(send_workflow_update(run_id, message))
    except RuntimeError:
        # No running event loop (e.g., called from scheduler)
        pass

def execute_workflow(db: Session, workflow_id: int, triggered_by: Optional[int] = None, context: Optional[dict] = None):
    print(f"DEBUG: execute_workflow called for workflow_id={workflow_id}, triggered_by={triggered_by}")
    from models import Script, Server, ServerGroup, ServerGroupAssociation  # local import to avoid cycles
    wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not wf:
        print(f"DEBUG: Workflow {workflow_id} not found")
        raise HTTPException(status_code=404, detail="Workflow not found")

    run = WorkflowRun(workflow_id=wf.id, triggered_by=triggered_by, status="running", started_at=datetime.now(timezone.utc), context=(context or {}).get("context") if isinstance(context, dict) else None)
    db.add(run)
    db.flush()
    # Make the new run visible to other sessions immediately
    try:
        db.commit()
    except Exception:
        db.rollback()

    # Initialize workflow run tracking
    manager.update_workflow_run(run.id, "running", progress=0.0)

    # Send initial update
    _safe_send_update(run.id, {
        "type": "workflow_started",
        "workflow_run_id": run.id,
        "workflow_name": wf.name,
        "status": "running",
        "progress": 0.0
    })

    def _find_start_nodes_local():
        nodes = db.query(WorkflowNode).filter(WorkflowNode.workflow_id == wf.id).all()
        incoming = {e.target_node_id for e in db.query(WorkflowEdge).filter(WorkflowEdge.workflow_id == wf.id)}
        return [n for n in nodes if n.id not in incoming]

    current_nodes = _find_start_nodes_local()
    if not current_nodes:
        # Fallback: if graph has nodes but no explicit start (all have incoming), start with the earliest node
        all_nodes = db.query(WorkflowNode).filter(WorkflowNode.workflow_id == wf.id).order_by(WorkflowNode.id.asc()).all()
        if all_nodes:
            current_nodes = [all_nodes[0]]
        else:
            run.status = "no_start_nodes"
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            return {"run_id": run.id, "status": run.status}

    total_nodes = len(db.query(WorkflowNode).filter(WorkflowNode.workflow_id == wf.id).all())
    completed_nodes = 0

    while current_nodes:
        node = current_nodes.pop(0)
        print(f"DEBUG: Starting workflow node {node.id} ({node.name}) - script_id={node.script_id}, target_type={node.target_type}, target_id={node.target_id}")
        print(f"DEBUG: Workflow execution - current_nodes count: {len(current_nodes)}")
        nr = WorkflowNodeRun(workflow_run_id=run.id, node_id=node.id, status="running", started_at=datetime.now(timezone.utc))
        db.add(nr)
        db.flush()
        # Make node start visible
        try:
            db.commit()
        except Exception:
            db.rollback()

        # Send node start update
        progress = (completed_nodes / total_nodes) * 100 if total_nodes > 0 else 0
        manager.update_workflow_run(run.id, "running", current_node=node.name, progress=progress)
        _safe_send_update(run.id, {
            "type": "node_started",
            "node_id": node.id,
            "node_name": node.name,
            "progress": progress,
            "current_node": node.name
        })

        status = "completed"
        output = ""
        error = None
        try:
            if node.script_id and node.target_type and node.target_id:
                script = db.query(Script).get(node.script_id)
                if not script:
                    raise Exception("Script not found")
                exec_records = []
                # retry policy from workflow
                max_retries = int(getattr(wf, 'max_retries', 0) or 0)
                retry_interval = int(getattr(wf, 'retry_interval_seconds', 0) or 0)
                attempt = 0
                final_failed = False
                while True:
                    exec_records.clear()
                    final_failed = False
                    if node.target_type == 'server':
                        srv = db.query(Server).get(node.target_id)
                        if not srv:
                            raise Exception("Server not found")
                        q = get_queue("execute")
                        job = q.enqueue(execute_script_job, script.id, srv.id, triggered_by, None)
                        status = 'running'
                        exec_records.append({"server_id": srv.id, "job_id": job.id, "status": "enqueued"})
                        
                        # Wait for job completion
                        print(f"DEBUG: Waiting for job {job.id} to complete for node {node.name}")
                        wait_count = 0
                        max_wait = 120  # Wait up to 60 seconds (120 * 0.5s)
                        while wait_count < max_wait:
                            try:
                                job_result = job.result
                                print(f"DEBUG: Job {job.id} result check {wait_count}: {job_result}")
                                if job_result is not None:
                                    # Job completed
                                    if isinstance(job_result, dict) and job_result.get('execution_id'):
                                        exec_id = job_result['execution_id']
                                        exec_record = db.query(ScriptExecution).filter(ScriptExecution.id == exec_id).first()
                                        if exec_record:
                                            status = 'completed' if exec_record.status == 'completed' else 'failed'
                                            output = exec_record.output or ""
                                            error = exec_record.error
                                            exec_records[0]['execution_id'] = exec_id
                                            exec_records[0]['status'] = exec_record.status
                                            print(f"DEBUG: Job {job.id} completed with status {status}")
                                        else:
                                            status = 'failed'
                                            error = "Execution record not found"
                                            print(f"DEBUG: Job {job.id} - execution record not found for id {exec_id}")
                                    else:
                                        status = 'failed'
                                        error = "Invalid job result"
                                        print(f"DEBUG: Job {job.id} - invalid job result: {job_result}")
                                    break
                                else:
                                    print(f"DEBUG: Job {job.id} still running, waiting...")
                            except Exception as e:
                                print(f"DEBUG: Error checking job {job.id} result: {e}")
                                break
                            wait_count += 1
                            time.sleep(0.5)  # Wait 500ms before checking again
                        
                        if wait_count >= max_wait:
                            print(f"DEBUG: Job {job.id} timed out after {max_wait * 0.5} seconds")
                            status = 'failed'
                            error = "Job execution timed out"
                        
                        final_failed = (status == 'failed')
                    elif node.target_type == 'group':
                        group = db.query(ServerGroup).get(node.target_id)
                        if not group:
                            raise Exception("Group not found")
                        servers = getattr(group, 'servers', [])
                        if not servers:
                            assoc = db.query(ServerGroupAssociation).filter(ServerGroupAssociation.group_id == group.id).all()
                            server_ids = [a.server_id for a in assoc]
                            servers = db.query(Server).filter(Server.id.in_(server_ids)).all() if server_ids else []
                        policy = getattr(wf, 'group_failure_policy', 'any') or 'any'
                        failed_count = 0
                        total_count = len(servers)
                        temp_results = []
                        q = get_queue("execute")
                        for srv in servers:
                            try:
                                job = q.enqueue(execute_script_job, script.id, srv.id, triggered_by, None)
                                temp_results.append((srv, job.id))
                            except Exception:
                                temp_results.append((srv, None))
                        for srv, job_id in temp_results:
                            exec_records.append({"server_id": srv.id, "job_id": job_id, "status": "enqueued" if job_id else "failed"})
                        
                        # Wait for all jobs to complete
                        print(f"DEBUG: Waiting for {len(temp_results)} group jobs to complete for node {node.name}")
                        completed_jobs = 0
                        failed_jobs = 0
                        wait_count = 0
                        max_wait = 120  # Wait up to 60 seconds
                        while completed_jobs + failed_jobs < len(temp_results) and wait_count < max_wait:
                            for i, (srv, job_id) in enumerate(temp_results):
                                if job_id and exec_records[i]['status'] == 'enqueued':
                                    job = q.fetch_job(job_id)
                                    if job and job.result is not None:
                                        # Job completed
                                        print(f"DEBUG: Group job {job_id} result: {job.result}")
                                        if isinstance(job.result, dict) and job.result.get('execution_id'):
                                            exec_id = job.result['execution_id']
                                            exec_record = db.query(ScriptExecution).filter(ScriptExecution.id == exec_id).first()
                                            if exec_record:
                                                exec_records[i]['execution_id'] = exec_id
                                                exec_records[i]['status'] = exec_record.status
                                                if exec_record.status == 'completed':
                                                    completed_jobs += 1
                                                else:
                                                    failed_jobs += 1
                                                print(f"DEBUG: Group job {job_id} completed with status {exec_record.status}")
                                            else:
                                                exec_records[i]['status'] = 'failed'
                                                failed_jobs += 1
                                                print(f"DEBUG: Group job {job_id} - execution record not found for id {exec_id}")
                                        else:
                                            exec_records[i]['status'] = 'failed'
                                            failed_jobs += 1
                                            print(f"DEBUG: Group job {job_id} - invalid job result: {job.result}")
                            wait_count += 1
                            time.sleep(0.5)  # Wait 500ms before checking again
                        
                        if wait_count >= max_wait:
                            print(f"DEBUG: Group jobs timed out after {max_wait * 0.5} seconds")
                            # Mark remaining jobs as failed
                            for i, (srv, job_id) in enumerate(temp_results):
                                if job_id and exec_records[i]['status'] == 'enqueued':
                                    exec_records[i]['status'] = 'failed'
                                    failed_jobs += 1
                        
                        # Determine final status based on policy
                        if policy == 'any' and failed_jobs > 0:
                            status = 'failed'
                            error = f"Failed on {failed_jobs} out of {len(temp_results)} servers"
                        elif policy == 'all' and failed_jobs > 0:
                            status = 'failed'
                            error = f"Failed on {failed_jobs} out of {len(temp_results)} servers"
                        else:
                            status = 'completed'
                            error = None
                        
                        final_failed = (status == 'failed')
                    else:
                        raise Exception('Unsupported target_type')

                    if not final_failed:
                        break
                    if attempt >= max_retries:
                        break
                    attempt += 1
                    if retry_interval > 0:
                        # simple blocking wait between retries (MVP)
                        time.sleep(retry_interval)

                output = json.dumps({"executions": exec_records, "attempts": 1})
            else:
                output = "No-op: missing script or target"
        except Exception as exc:
            status = "failed"
            error = str(exc)

        print(f"DEBUG: Node {node.id} ({node.name}) completed with status: {status}")
        nr.status = status
        nr.output = output
        nr.error = error
        nr.completed_at = datetime.now(timezone.utc)
        # Commit node completion so the monitor can see it
        try:
            db.commit()
        except Exception:
            db.rollback()

        # Update completed nodes count and send completion update
        completed_nodes += 1
        progress = (completed_nodes / total_nodes) * 100 if total_nodes > 0 else 100
        manager.update_workflow_run(run.id, "running", current_node=node.name, progress=progress)
        _safe_send_update(run.id, {
            "type": "node_completed",
            "node_id": node.id,
            "node_name": node.name,
            "status": status,
            "progress": progress,
            "output": output[:500] if output else "",  # Truncate for WebSocket
            "error": error[:500] if error else None
        })

        edges = db.query(WorkflowEdge).filter(WorkflowEdge.workflow_id == wf.id, WorkflowEdge.source_node_id == node.id).all()
        next_node = None
        if status == "completed":
            for e in edges:
                if e.condition == "on_success":
                    next_node = db.query(WorkflowNode).get(e.target_node_id)
                    break
        else:
            for e in edges:
                if e.condition == "on_failure":
                    next_node = db.query(WorkflowNode).get(e.target_node_id)
                    break

        if next_node:
            current_nodes.append(next_node)

    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    db.commit()

    # Send final completion update
    manager.update_workflow_run(run.id, "completed", progress=100.0)
    _safe_send_update(run.id, {
        "type": "workflow_completed",
        "workflow_run_id": run.id,
        "status": "completed",
        "progress": 100.0,
        "completed_at": run.completed_at.isoformat()
    })


    return {"run_id": run.id, "status": run.status}

def _execute_workflow_background(run_id: int, context: Optional[dict] = None, triggered_by: Optional[int] = None):
    """Execute a workflow asynchronously for an existing WorkflowRun (identified by run_id)."""
    print(f"DEBUG: _execute_workflow_background called for run_id={run_id}, triggered_by={triggered_by}")
    sess = None
    try:
        sess = SessionLocal()
        run = sess.query(WorkflowRun).get(run_id)
        if not run:
            print(f"DEBUG: WorkflowRun {run_id} not found")
            return
        wf = sess.query(Workflow).get(run.workflow_id)
        if not wf:
            print(f"DEBUG: Workflow {run.workflow_id} not found for run {run_id}")
            run.status = "failed"
            run.completed_at = datetime.now(timezone.utc)
            sess.commit()
            return
        # Ensure running state visible
        run.status = "running"
        if not run.started_at:
            run.started_at = datetime.now(timezone.utc)
        sess.commit()

        manager.update_workflow_run(run.id, "running", progress=0.0)
        _safe_send_update(run.id, {
            "type": "workflow_started",
            "workflow_run_id": run.id,
            "workflow_name": wf.name,
            "status": "running",
            "progress": 0.0
        })

        def _find_start_nodes_local():
            nodes = sess.query(WorkflowNode).filter(WorkflowNode.workflow_id == wf.id).all()
            incoming = {e.target_node_id for e in sess.query(WorkflowEdge).filter(WorkflowEdge.workflow_id == wf.id)}
            return [n for n in nodes if n.id not in incoming]

        current_nodes = _find_start_nodes_local()
        if not current_nodes:
            all_nodes = sess.query(WorkflowNode).filter(WorkflowNode.workflow_id == wf.id).order_by(WorkflowNode.id.asc()).all()
            if all_nodes:
                current_nodes = [all_nodes[0]]
            else:
                run.status = "no_start_nodes"
                run.completed_at = datetime.now(timezone.utc)
                sess.commit()
                return

        total_nodes = len(sess.query(WorkflowNode).filter(WorkflowNode.workflow_id == wf.id).all())
        completed_nodes = 0

        while current_nodes:
            node = current_nodes.pop(0)
            nr = WorkflowNodeRun(workflow_run_id=run.id, node_id=node.id, status="running", started_at=datetime.now(timezone.utc))
            sess.add(nr)
            sess.flush()
            try:
                sess.commit()
            except Exception:
                sess.rollback()

            progress = (completed_nodes / total_nodes) * 100 if total_nodes > 0 else 0
            manager.update_workflow_run(run.id, "running", current_node=node.name, progress=progress)
            _safe_send_update(run.id, {
                "type": "node_started",
                "node_id": node.id,
                "node_name": node.name,
                "progress": progress,
                "current_node": node.name
            })

            status = "completed"
            output = ""
            error = None
            try:
                if node.script_id and node.target_type and node.target_id:
                    script = sess.query(Script).get(node.script_id)
                    if not script:
                        raise Exception("Script not found")
                    exec_records = []
                    max_retries = int(getattr(wf, 'max_retries', 0) or 0)
                    retry_interval = int(getattr(wf, 'retry_interval_seconds', 0) or 0)
                    attempt = 0
                    final_failed = False
                    while True:
                        exec_records.clear()
                        final_failed = False
                        if node.target_type == 'server':
                            srv = sess.query(Server).get(node.target_id)
                            if not srv:
                                raise Exception("Server not found")
                            
                            # Use RQ job execution instead of direct execution
                            from rq_queue import get_queue
                            from tasks import execute_script_job
                            
                            q = get_queue("execute")
                            job = q.enqueue(execute_script_job, script.id, srv.id, triggered_by, None)
                            status = 'running'
                            exec_records.append({"server_id": srv.id, "job_id": job.id, "status": "enqueued"})
                            
                            # Wait for job completion
                            print(f"DEBUG: Waiting for job {job.id} to complete for node {node.name}")
                            wait_count = 0
                            max_wait = 120  # Wait up to 60 seconds (120 * 0.5s)
                            while wait_count < max_wait:
                                try:
                                    try:
                                        job.refresh()
                                    except Exception:
                                        pass
                                    job_result = job.result
                                    print(f"DEBUG: Job {job.id} result check {wait_count}: {job_result}")
                                    if job_result is not None:
                                        # Job completed
                                        if isinstance(job_result, dict) and job_result.get('execution_id'):
                                            exec_id = job_result['execution_id']
                                            exec_record = sess.query(ScriptExecution).filter(ScriptExecution.id == exec_id).first()
                                            if exec_record:
                                                status = 'completed' if exec_record.status == 'completed' else 'failed'
                                                exec_records[0]['execution_id'] = exec_id
                                                exec_records[0]['status'] = exec_record.status
                                                print(f"DEBUG: Job {job.id} completed with status {status}")
                                            else:
                                                status = 'failed'
                                                print(f"DEBUG: Job {job.id} - execution record not found for id {exec_id}")
                                        else:
                                            status = 'failed'
                                            print(f"DEBUG: Job {job.id} - invalid job result: {job_result}")
                                        break
                                    else:
                                        print(f"DEBUG: Job {job.id} still running, waiting...")
                                except Exception as e:
                                    print(f"DEBUG: Error checking job {job.id} result: {e}")
                                    break
                                wait_count += 1
                                time.sleep(0.5)  # Wait 500ms before checking again
                            
                            if wait_count >= max_wait:
                                print(f"DEBUG: Job {job.id} timed out after {max_wait * 0.5} seconds")
                                status = 'failed'
                            
                            final_failed = (status == 'failed')
                        elif node.target_type == 'group':
                            group = sess.query(ServerGroup).get(node.target_id)
                            if not group:
                                raise Exception("Group not found")
                            servers = getattr(group, 'servers', [])
                            if not servers:
                                assoc = sess.query(ServerGroupAssociation).filter(ServerGroupAssociation.group_id == group.id).all()
                                server_ids = [a.server_id for a in assoc]
                                servers = sess.query(Server).filter(Server.id.in_(server_ids)).all() if server_ids else []

                            policy = getattr(wf, 'group_failure_policy', 'any') or 'any'
                            failed_count = 0
                            total_count = len(servers)

                            # Use RQ job execution for group
                            from rq_queue import get_queue
                            from tasks import execute_script_job
                            
                            q = get_queue("execute")
                            jobs = []
                            for srv in servers:
                                job = q.enqueue(execute_script_job, script.id, srv.id, triggered_by, None)
                                jobs.append((srv, job))
                                exec_records.append({"server_id": srv.id, "job_id": job.id, "status": "enqueued"})
                            
                            # Wait for all jobs to complete
                            print(f"DEBUG: Waiting for {len(jobs)} jobs to complete for node {node.name}")
                            completed_jobs = 0
                            failed_jobs = 0
                            max_wait = 120  # Wait up to 60 seconds (120 * 0.5s)
                            wait_count = 0
                            
                            while wait_count < max_wait and completed_jobs + failed_jobs < len(jobs):
                                for srv, job in jobs:
                                    try:
                                        job.refresh()
                                    except Exception:
                                        pass
                                    if job.result is not None:
                                        if isinstance(job.result, dict) and job.result.get('execution_id'):
                                            exec_id = job.result['execution_id']
                                            exec_record = sess.query(ScriptExecution).filter(ScriptExecution.id == exec_id).first()
                                            if exec_record:
                                                status = exec_record.status
                                                # Update the exec_records with the actual execution_id
                                                for record in exec_records:
                                                    if record['server_id'] == srv.id:
                                                        record['execution_id'] = exec_id
                                                        record['status'] = status
                                                        break
                                                
                                                if status == 'completed':
                                                    completed_jobs += 1
                                                else:
                                                    failed_jobs += 1
                                                print(f"DEBUG: Job {job.id} for server {srv.id} completed with status {status}")
                                            else:
                                                failed_jobs += 1
                                                print(f"DEBUG: Job {job.id} for server {srv.id} - execution record not found")
                                        else:
                                            failed_jobs += 1
                                            print(f"DEBUG: Job {job.id} for server {srv.id} - invalid job result")
                                
                                if completed_jobs + failed_jobs < len(jobs):
                                    print(f"DEBUG: Group jobs still running: {completed_jobs} completed, {failed_jobs} failed, {len(jobs) - completed_jobs - failed_jobs} pending")
                                    wait_count += 1
                                    time.sleep(0.5)  # Wait 500ms before checking again
                            
                            if wait_count >= max_wait:
                                print(f"DEBUG: Group jobs timed out after {max_wait * 0.5} seconds")
                                failed_jobs = len(jobs) - completed_jobs
                            
                            if policy == 'any':
                                final_failed = failed_jobs > 0
                            else:
                                final_failed = failed_jobs == total_count and total_count > 0

                            status = 'failed' if final_failed else 'completed'
                        else:
                            raise Exception('Unsupported target_type')

                        if not final_failed:
                            break
                        if attempt >= max_retries:
                            break
                        attempt += 1
                        if retry_interval > 0:
                            time.sleep(retry_interval)

                    output = json.dumps({"executions": exec_records, "attempts": attempt + 1})
                else:
                    output = "No-op: missing script or target"
            except Exception as exc:
                status = "failed"
                error = str(exc)

            nr.status = status
            nr.output = output
            nr.error = error
            nr.completed_at = datetime.now(timezone.utc)
            try:
                sess.commit()
            except Exception:
                sess.rollback()

            completed_nodes += 1
            progress = (completed_nodes / total_nodes) * 100 if total_nodes > 0 else 100
            manager.update_workflow_run(run.id, "running", current_node=node.name, progress=progress)
            _safe_send_update(run.id, {
                "type": "node_completed",
                "node_id": node.id,
                "node_name": node.name,
                "status": status,
                "progress": progress,
                "output": output[:500] if output else "",
                "error": error[:500] if error else None
            })

            edges = sess.query(WorkflowEdge).filter(WorkflowEdge.workflow_id == wf.id, WorkflowEdge.source_node_id == node.id).all()
            next_node = None
            if status == "completed":
                for e in edges:
                    if e.condition == "on_success":
                        next_node = sess.query(WorkflowNode).get(e.target_node_id)
                        break
            else:
                for e in edges:
                    if e.condition == "on_failure":
                        next_node = sess.query(WorkflowNode).get(e.target_node_id)
                        break
            if next_node:
                current_nodes.append(next_node)

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        sess.commit()

        manager.update_workflow_run(run.id, "completed", progress=100.0)
        _safe_send_update(run.id, {
            "type": "workflow_completed",
            "workflow_run_id": run.id,
            "status": "completed",
            "progress": 100.0,
            "completed_at": run.completed_at.isoformat()
        })
    except Exception:
        try:
            if sess:
                sess.rollback()
        except Exception:
            pass
    finally:
        try:
            if sess:
                sess.close()
        except Exception:
            pass

# === Workflow node run reconciliation (background) ===
import threading as _wf_threading
import json as _wf_json

_wf_watcher_started = False

def _fetch_job_result(job_id: str):
    try:
        conn = get_redis()
        job = Job.fetch(job_id, connection=conn)
        if job.is_finished:
            return True, job.result
        if job.is_failed:
            return True, {"execution_id": None, "status": "failed", "error": str(job.exc_info or "job_failed")}
        return False, None
    except Exception:
        return False, None


def _node_runs_watcher_loop(stop_event: _wf_threading.Event):
    while not stop_event.is_set():
        sess = None
        try:
            sess = SessionLocal()
            running = sess.query(WorkflowNodeRun).filter(WorkflowNodeRun.status == 'running').all()
            for nr in running:
                try:
                    # Expect output like {"executions": [{server_id, job_id, status?, execution_id?}], "attempts": 1}
                    data = None
                    try:
                        data = _wf_json.loads(nr.output or '{}')
                    except Exception:
                        data = None
                    if not data or not isinstance(data, dict):
                        continue
                    items = data.get('executions') or []
                    if not items:
                        continue
                    updated = False
                    # Resolve job results to execution_ids
                    for it in items:
                        if it.get('execution_id') is None and it.get('job_id'):
                            done, res = _fetch_job_result(it['job_id'])
                            if done and isinstance(res, dict) and res.get('execution_id') is not None:
                                it['execution_id'] = res['execution_id']
                                it['status'] = res.get('status') or it.get('status')
                                updated = True
                    if updated:
                        nr.output = _wf_json.dumps(data)
                        sess.flush()
                    # Check completion: all executions have execution_id and are not running
                    all_have_exec = all((it.get('execution_id') is not None) for it in items)
                    if not all_have_exec:
                        continue
                    # Fetch statuses from DB to determine final result
                    exec_ids = [it['execution_id'] for it in items if it.get('execution_id') is not None]
                    if not exec_ids:
                        continue
                    ex_rows = sess.query(ScriptExecution).filter(ScriptExecution.id.in_(exec_ids)).all()
                    if len(ex_rows) != len(exec_ids):
                        continue
                    any_running = any((getattr(r, 'status', '') in ('running', 'long_running')) for r in ex_rows)
                    if any_running:
                        continue
                    any_failed = any((getattr(r, 'status', '') == 'failed') for r in ex_rows)
                    nr.status = 'failed' if any_failed else 'completed'
                    nr.completed_at = datetime.now(timezone.utc)
                    sess.flush()
                except Exception:
                    continue
            sess.commit()
        except Exception:
            try:
                if sess: sess.rollback()
            except Exception:
                pass
        finally:
            try:
                if sess: sess.close()
            except Exception:
                pass
        stop_event.wait(0.5)

_wf_stop_event = _wf_threading.Event()

def start_workflow_watcher():
    global _wf_watcher_started, _wf_stop_event
    if _wf_watcher_started:
        return
    _wf_watcher_started = True
    _wf_stop_event = _wf_threading.Event()
    t = _wf_threading.Thread(target=_node_runs_watcher_loop, args=(_wf_stop_event,), daemon=True)
    t.start()


def stop_workflow_watcher():
    global _wf_stop_event
    try:
        _wf_stop_event.set()
    except Exception:
        pass
# Start watcher on import
start_workflow_watcher()
# === End watcher ===

router = APIRouter(tags=["workflows"], prefix="/workflows")



@router.get("/", response_model=None)
def list_workflows(db: Session = Depends(get_db)):
    try:
        db.rollback()
    except Exception:
        pass
    items = db.query(Workflow).order_by(Workflow.created_at.desc()).all()
    result = []

    def _iso_tzaware(dt):
        if not dt:
            return None
        try:
            # Normalize to UTC and ensure timezone info
            if getattr(dt, 'tzinfo', None) is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                try:
                    dt = dt.astimezone(timezone.utc)
                except Exception:
                    pass
            iso = dt.isoformat()
            # Prefer Z suffix for UTC
            if iso.endswith('+00:00'):
                iso = iso[:-6] + 'Z'
            return iso
        except Exception:
            try:
                return str(dt)
            except Exception:
                return None

    for w in items:
        # Hide drafts with zero nodes from the list to avoid confusion before a valid save
        node_count = db.query(WorkflowNode).filter(WorkflowNode.workflow_id == w.id).count()
        if node_count == 0:
            continue
        
        # Get last run information
        last_run = db.query(WorkflowRun).filter(WorkflowRun.workflow_id == w.id).order_by(WorkflowRun.id.desc()).first()
        last_run_at = None
        if last_run:
            # Use completed_at if available, otherwise started_at
            last_run_at = last_run.completed_at if last_run.completed_at else last_run.started_at

        # Aggregate: run count in last 24 hours and last result
        from datetime import datetime, timedelta, timezone as _tz
        now_utc = datetime.now(_tz.utc)
        since_24h = now_utc - timedelta(hours=24)
        runs_24h = db.query(WorkflowRun).filter(
            WorkflowRun.workflow_id == w.id,
            WorkflowRun.started_at >= since_24h
        ).count()
        last_result = getattr(last_run, 'status', None) if last_run else None
        
        # Calculate next run for scheduled workflows using APScheduler
        next_run_at = None
        if getattr(w, 'trigger_type', None) == 'schedule' and getattr(w, 'schedule_cron', None):
            try:
                from scheduler import get_next_run_time
                next_run_at = get_next_run_time(w.id)
            except Exception:
                # If APScheduler is not available, fall back to croniter
                try:
                    from croniter import croniter
                    from zoneinfo import ZoneInfo
                    from datetime import datetime, timezone
                    
                    tzname = (getattr(w, 'schedule_timezone', None) or 'UTC').strip() or 'UTC'
                    try:
                        tz = ZoneInfo(tzname)
                    except Exception:
                        tz = ZoneInfo('UTC')
                    
                    # Use last run time or current time as base
                    base_time = last_run_at or datetime.now(timezone.utc)
                    if base_time.tzinfo is None:
                        base_time = base_time.replace(tzinfo=timezone.utc)
                    
                    base_local = base_time.astimezone(tz)
                    it = croniter(w.schedule_cron, base_local)
                    next_local = it.get_next(datetime)
                    next_run_at = next_local.astimezone(timezone.utc)
                except Exception:
                    # If cron calculation fails, leave next_run_at as None
                    pass
        
        result.append({
            "id": w.id,
            "name": w.name,
            "description": w.description,
            "created_by": w.created_by,
            "created_at": _iso_tzaware(w.created_at),
            "updated_at": _iso_tzaware(w.updated_at),
            "trigger_type": getattr(w, 'trigger_type', None),
            "schedule_timezone": getattr(w, 'schedule_timezone', None),
            "last_run_at": _iso_tzaware(last_run_at),
            "last_run_id": (last_run.id if last_run else None),
            "next_run_at": _iso_tzaware(next_run_at),
            "runs_24h": runs_24h,
            "last_result": last_result,
        })
    return {"workflows": result}


@router.post("/", response_model=None)
def create_workflow(payload: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Clear any aborted transaction before proceeding
    try:
        db.rollback()
    except Exception:
        pass
    name = payload.get("name")
    description = payload.get("description")
    nodes = payload.get("nodes", [])
    edges = payload.get("edges", [])
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    # Ensure unique name by auto-suffixing if necessary
    base = name.strip() or "Workflow"
    uniq = base
    suffix = 2
    while True:
        try:
            exists = db.query(Workflow).filter(Workflow.name == uniq).first()
        except Exception:
            db.rollback()
            exists = db.query(Workflow).filter(Workflow.name == uniq).first()
        if not exists:
            break
        uniq = f"{base} {suffix}"
        suffix += 1

    try:
        wf = Workflow(name=uniq, description=description, created_by=current_user.id)
        db.add(wf)
        db.flush()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create workflow: {str(e)}")

    node_id_map = {}
    for n in nodes:
        node = WorkflowNode(
            workflow_id=wf.id,
            key=n.get("key") or n.get("id") or f"node_{len(node_id_map)+1}"
        )
        node.name = n.get("name") or node.key
        node.script_id = n.get("script_id")
        node.parameters = n.get("parameters")
        node.position = n.get("position")
        node.target_type = n.get("target_type")
        node.target_id = n.get("target_id")
        db.add(node)
        db.flush()
        node_id_map[node.key] = node.id

    for e in edges:
        src_key = e.get("source") or e.get("from")
        dst_key = e.get("target") or e.get("to")
        cond = e.get("condition") or "on_success"
        if not src_key or not dst_key:
            continue
        edge = WorkflowEdge(
            workflow_id=wf.id,
            source_node_id=node_id_map.get(src_key),
            target_node_id=node_id_map.get(dst_key),
            condition=cond
        )
        db.add(edge)

    db.commit()
    db.refresh(wf)
    log_audit(db, action="workflow_create", resource_type="workflow", resource_id=wf.id, user_id=current_user.id, details={"name": wf.name})
    return {"id": wf.id}


@router.get("/{workflow_id}", response_model=None)
def get_workflow(workflow_id: int, db: Session = Depends(get_db)):
    try:
        db.rollback()
    except Exception:
        pass
    wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    nodes = db.query(WorkflowNode).filter(WorkflowNode.workflow_id == wf.id).all()
    edges = db.query(WorkflowEdge).filter(WorkflowEdge.workflow_id == wf.id).all()
    # map node ids to keys for frontend compatibility
    id_to_key = {n.id: n.key for n in nodes}
    # Derive last_run_at and next_run_at similar to list_workflows
    last_run = db.query(WorkflowRun).filter(WorkflowRun.workflow_id == wf.id).order_by(WorkflowRun.id.desc()).first()
    last_run_at = None
    if last_run:
        last_run_at = last_run.completed_at if last_run.completed_at else last_run.started_at

    next_run_at = None
    if getattr(wf, 'trigger_type', None) == 'schedule' and getattr(wf, 'schedule_cron', None):
        try:
            from scheduler import get_next_run_time
            next_run_at = get_next_run_time(wf.id)
        except Exception:
            try:
                from croniter import croniter
                from zoneinfo import ZoneInfo
                from datetime import datetime, timezone
                tzname = (getattr(wf, 'schedule_timezone', None) or 'UTC').strip() or 'UTC'
                try:
                    tz = ZoneInfo(tzname)
                except Exception:
                    tz = ZoneInfo('UTC')
                base_time = last_run_at or datetime.now(timezone.utc)
                if base_time.tzinfo is None:
                    base_time = base_time.replace(tzinfo=timezone.utc)
                base_local = base_time.astimezone(tz)
                it = croniter(wf.schedule_cron, base_local)
                next_local = it.get_next(datetime)
                next_run_at = next_local.astimezone(timezone.utc)
            except Exception:
                pass

    # Aggregate quick stats
    from datetime import datetime, timedelta, timezone as _tz
    now_utc = datetime.now(_tz.utc)
    since_24h = now_utc - timedelta(hours=24)
    runs_24h = db.query(WorkflowRun).filter(
        WorkflowRun.workflow_id == wf.id,
        WorkflowRun.started_at >= since_24h
    ).count()
    last_result = getattr(last_run, 'status', None) if last_run else None

    return {
        "id": wf.id,
        "name": wf.name,
        "description": wf.description,
        "created_by": wf.created_by,
        "created_at": wf.created_at,
        "updated_at": wf.updated_at,
        "trigger_type": getattr(wf, 'trigger_type', None),
        "schedule_cron": getattr(wf, 'schedule_cron', None),
        "schedule_timezone": getattr(wf, 'schedule_timezone', None),
        "webhook_url": getattr(wf, 'webhook_url', None),
        "webhook_method": getattr(wf, 'webhook_method', None),
        "webhook_payload": getattr(wf, 'webhook_payload', None),
        "max_retries": getattr(wf, 'max_retries', None),
        "retry_interval_seconds": getattr(wf, 'retry_interval_seconds', None),
        "group_failure_policy": getattr(wf, 'group_failure_policy', None),
        "last_run_at": last_run_at,
        "next_run_at": next_run_at,
        "runs_24h": runs_24h,
        "last_result": last_result,
        "nodes": [
            {
                "id": n.id,
                "key": n.key,
                "name": n.name,
                "script_id": n.script_id,
                "target_type": n.target_type,
                "target_id": n.target_id,
                "parameters": n.parameters,
                "position": n.position,
            } for n in nodes
        ],
        "edges": [
            {
                "id": e.id,
                "source": id_to_key.get(e.source_node_id),
                "target": id_to_key.get(e.target_node_id),
                "condition": e.condition,
            } for e in edges
        ],
    }


@router.put("/{workflow_id}", response_model=None)
def update_workflow(workflow_id: int, payload: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # basic fields
    name = payload.get("name")
    description = payload.get("description")
    if name:
        wf.name = name
    if description is not None:
        wf.description = description
    # trigger-related fields
    if "trigger_type" in payload:
        wf.trigger_type = payload.get("trigger_type")
    if "schedule_cron" in payload:
        wf.schedule_cron = payload.get("schedule_cron")
    if "schedule_timezone" in payload:
        wf.schedule_timezone = payload.get("schedule_timezone")
    if "webhook_url" in payload:
        wf.webhook_url = payload.get("webhook_url")
    if "webhook_method" in payload:
        wf.webhook_method = payload.get("webhook_method")
    if "webhook_payload" in payload:
        wf.webhook_payload = payload.get("webhook_payload")
    db.flush()
    
    # Sync schedule changes to APScheduler if trigger_type or schedule fields changed
    if any(field in payload for field in ["trigger_type", "schedule_cron", "schedule_timezone"]):
        from scheduler import sync_schedules
        sync_schedules()

    # Replace nodes/edges if provided
    if "nodes" in payload or "edges" in payload:
        nodes_payload = payload.get("nodes", []) or []
        edges_payload = payload.get("edges", []) or []
        # Server-side validations
        if len(nodes_payload) <= 1:
            raise HTTPException(status_code=400, detail="Add at least two nodes before saving")
        key_set = {n.get("key") or n.get("id") for n in nodes_payload}
        if None in key_set:
            raise HTTPException(status_code=400, detail="All nodes must have a key")
        incoming = {k: 0 for k in key_set}
        outgoing = {k: 0 for k in key_set}
        for e in edges_payload:
            src = e.get("source") or e.get("from")
            dst = e.get("target") or e.get("to")
            if not src or not dst:
                raise HTTPException(status_code=400, detail="Edges must have source and target")
            if src not in key_set or dst not in key_set:
                raise HTTPException(status_code=400, detail="Edges reference non-existent nodes")
            outgoing[src] = outgoing.get(src, 0) + 1
            incoming[dst] = incoming.get(dst, 0) + 1
        unconnected = [k for k in key_set if (incoming.get(k,0)==0 and outgoing.get(k,0)==0)]
        if unconnected:
            raise HTTPException(status_code=400, detail=f"Unconnected nodes: {', '.join(unconnected)}")
        empty_nodes = [ (n.get('name') or n.get('key')) for n in nodes_payload if not (n.get('script_id') and n.get('target_type') and n.get('target_id')) ]
        if empty_nodes:
            raise HTTPException(status_code=400, detail=f"Nodes missing script/target: {', '.join(empty_nodes)}")
        # delete existing
        db.query(WorkflowEdge).filter(WorkflowEdge.workflow_id == wf.id).delete()
        db.query(WorkflowNode).filter(WorkflowNode.workflow_id == wf.id).delete()
        db.flush()

        node_id_map = {}
        for n in nodes_payload:
            node = WorkflowNode(
                workflow_id=wf.id,
                key=n.get("key") or n.get("id") or f"node_{len(node_id_map)+1}"
            )
            node.name = n.get("name") or node.key
            node.script_id = n.get("script_id")
            node.parameters = n.get("parameters")
            node.position = n.get("position")
            node.target_type = n.get("target_type")
            node.target_id = n.get("target_id")
            db.add(node)
            db.flush()
            node_id_map[node.key] = node.id

        for e in edges_payload:
            src_key = e.get("source") or e.get("from")
            dst_key = e.get("target") or e.get("to")
            cond = e.get("condition") or "on_success"
            if not src_key or not dst_key:
                continue
            edge = WorkflowEdge(
                workflow_id=wf.id,
                source_node_id=node_id_map.get(src_key),
                target_node_id=node_id_map.get(dst_key),
                condition=cond
            )
            db.add(edge)

    db.commit()
    log_audit(db, action="workflow_update", resource_type="workflow", resource_id=wf.id, user_id=current_user.id, details={"name": wf.name})
    return {"updated": True}


@router.delete("/{workflow_id}", response_model=None)
def delete_workflow(workflow_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    # Manual cascade to avoid FK issues on some SQLite setups
    run_ids = [r.id for r in db.query(WorkflowRun).filter(WorkflowRun.workflow_id == workflow_id).all()]
    if run_ids:
        db.query(WorkflowNodeRun).filter(WorkflowNodeRun.workflow_run_id.in_(run_ids)).delete(synchronize_session=False)
        db.query(WorkflowRun).filter(WorkflowRun.id.in_(run_ids)).delete(synchronize_session=False)
    db.query(WorkflowEdge).filter(WorkflowEdge.workflow_id == workflow_id).delete(synchronize_session=False)
    db.query(WorkflowNode).filter(WorkflowNode.workflow_id == workflow_id).delete(synchronize_session=False)
    db.query(Workflow).filter(Workflow.id == workflow_id).delete(synchronize_session=False)
    db.commit()
    log_audit(db, action="workflow_delete", resource_type="workflow", resource_id=workflow_id, user_id=current_user.id)
    return {"deleted": True}


def _find_start_nodes(db: Session, workflow_id: int):
    nodes = db.query(WorkflowNode).filter(WorkflowNode.workflow_id == workflow_id).all()
    incoming = {e.target_node_id for e in db.query(WorkflowEdge).filter(WorkflowEdge.workflow_id == workflow_id)}
    return [n for n in nodes if n.id not in incoming]


@router.post("/{workflow_id}/run", response_model=None)
def run_workflow(workflow_id: int, payload: dict = None, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Create run row and return immediately
    wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    run = WorkflowRun(workflow_id=wf.id, triggered_by=current_user.id if current_user else None, status="running", started_at=datetime.now(timezone.utc), context=(payload or {}).get("context") if isinstance(payload, dict) else None)
    db.add(run)
    db.commit()
    db.refresh(run)
    # Start background execution bound to this run_id
    t = threading.Thread(target=_execute_workflow_background, args=(run.id, payload or {}, current_user.id if current_user else None), daemon=True)
    t.start()
    log_audit(db, action="workflow_run", resource_type="workflow", resource_id=workflow_id, user_id=current_user.id if current_user else None, details={"run_id": run.id})
    return {"run_id": run.id, "status": "running"}


@router.api_route("/{workflow_id}/webhook", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], response_model=None)
async def webhook_trigger(workflow_id: int, request: Request, db: Session = Depends(get_db)):
    """Public webhook endpoint to trigger a workflow.
    - Respects configured webhook_method if set; otherwise accepts any method.
    - Attaches incoming request json/body, query params and method to run context.
    """
    wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if (wf.trigger_type or '').lower() != 'webhook':
        raise HTTPException(status_code=400, detail="Workflow is not configured for webhook trigger")
    if wf.webhook_method and wf.webhook_method.upper() != request.method.upper():
        raise HTTPException(status_code=405, detail=f"Method not allowed; expected {wf.webhook_method}")

    # Best-effort parse of JSON body; fall back to raw bytes
    body = None
    try:
        body = await request.json()
    except Exception:
        try:
            body = (await request.body()).decode("utf-8", errors="ignore")
        except Exception:
            body = None

    context = {
        "webhook": {
            "method": request.method,
            "query": dict(request.query_params),
            "body": body,
        }
    }

    result = execute_workflow(db=db, workflow_id=workflow_id, triggered_by=None, context=context)
    log_audit(db, action="workflow_webhook", resource_type="workflow", resource_id=workflow_id, user_id=None, details={"method": request.method, "query": dict(request.query_params)})
    return {"accepted": True, **(result or {})}


@router.get("/{workflow_id}/runs", response_model=None)
def list_workflow_runs(workflow_id: int, db: Session = Depends(get_db)):
    try:
        db.rollback()
    except Exception:
        pass
    wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    runs = db.query(WorkflowRun).filter(WorkflowRun.workflow_id == workflow_id).order_by(WorkflowRun.id.desc()).limit(50).all()
    return {
        "runs": [
            {
                "id": r.id,
                "status": r.status,
                "started_at": r.started_at,
                "completed_at": r.completed_at,
            } for r in runs
        ]
    }


@router.get("/runs/{run_id}", response_model=None)
def get_workflow_run(run_id: int, db: Session = Depends(get_db)):
    try:
        db.rollback()
    except Exception:
        pass
    r = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Run not found")
    node_runs = db.query(WorkflowNodeRun).filter(WorkflowNodeRun.workflow_run_id == r.id).all()
    return {
        "id": r.id,
        "workflow_id": r.workflow_id,
        "status": r.status,
        "started_at": r.started_at,
        "completed_at": r.completed_at,
        "nodes": [
            {
                "id": nr.id,
                "node_id": nr.node_id,
                "status": nr.status,
                "output": nr.output,
                "error": nr.error,
                "started_at": nr.started_at,
                "completed_at": nr.completed_at,
            } for nr in node_runs
        ]
    }

@router.websocket("/ws/workflow-run/{workflow_run_id}")
async def websocket_workflow_monitor(websocket: WebSocket, workflow_run_id: int, db: Session = Depends(get_db)):
    """Workflow monitoring removed: accept then close with info."""
    await websocket.accept()
    try:
        await websocket.send_text(json.dumps({"type": "error", "message": "Workflow monitoring is disabled."}))
    except Exception:
        pass
    try:
        await websocket.close()
    except Exception:
        pass

