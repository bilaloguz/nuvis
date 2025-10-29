from datetime import datetime, timezone
from typing import Optional

from rq import get_current_job
import paramiko

from database import SessionLocal
from models import Script, Server, ScriptExecution, Settings
from ssh_script_executor import execute_script_on_server
from utils_backoff import retry_with_backoff
from utils_logging import get_logger, kv
from rq_queue import semaphore_try_acquire, semaphore_release

SEM_NAME = "global_exec"


def _get_max_concurrency(sess: SessionLocal) -> int:
    try:
        s = sess.query(Settings).first()
        val = int(getattr(s, 'max_concurrent_executions', 4) or 4)
        return max(1, val)
    except Exception:
        return 4


@retry_with_backoff((paramiko.ssh_exception.SSHException, OSError, TimeoutError), retries=5, base=0.3, factor=2.0)
def _exec_once(script_id: int, server_id: int, executed_by: Optional[int], per_server_timeout: Optional[int]):
    sess = SessionLocal()
    try:
        # Acquire global semaphore
        limit = _get_max_concurrency(sess)
        if not semaphore_try_acquire(SEM_NAME, limit, ttl_seconds=3600):
            # Busy: raise to trigger retry/backoff wrapper
            raise TimeoutError("concurrency_limit_reached")

        script = sess.query(Script).get(script_id)
        server = sess.query(Server).get(server_id)
        if not script or not server:
            raise RuntimeError("script_or_server_not_found")
        # Create execution row centrally in the task
        exec_row = ScriptExecution(
            script_id=script.id,
            server_id=server.id,
            executed_by=executed_by,
            parameters_used=None,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        try:
            exec_row.id = None
        except Exception:
            pass
        sess.add(exec_row)
        sess.commit()
        sess.refresh(exec_row)

        # Infinite detection and settings
        is_infinite = (script.per_server_timeout_seconds == 0)
        settings = sess.query(Settings).first()
        if not settings:
            settings = Settings()
            sess.add(settings)
            sess.commit()
            sess.refresh(settings)
        virtual_timeout_duration = settings.virtual_timeout_duration or 60

        # Execute via shared SSH executor. It updates exec_row in-place.
        out, err, exit_code = execute_script_on_server(
            script=script,
            server=server,
            execution=exec_row,
            is_infinite=is_infinite,
            virtual_timeout_duration=virtual_timeout_duration,
        )

        if not exec_row.completed_at and not is_infinite:
            exec_row.status = "completed" if (exit_code == 0) else "failed"
            exec_row.output = exec_row.output or out
            exec_row.error = exec_row.error or (err if exit_code != 0 else None)
            exec_row.completed_at = datetime.now(timezone.utc)
            sess.commit()
            sess.refresh(exec_row)

        sess.expunge(exec_row)
        return exec_row.id, exec_row.status
    finally:
        try:
            # Always release semaphore if it was acquired in this attempt
            semaphore_release(SEM_NAME)
        except Exception:
            pass
        try:
            sess.close()
        except Exception:
            pass


def execute_script_job(script_id: int, server_id: int, executed_by: Optional[int] = None, request_id: Optional[str] = None):
    job = get_current_job() if get_current_job else None
    logger = get_logger(__name__, run_id=None, request_id=request_id or (job.id if job else None))
    logger.info(f"enqueue_execute start {kv(script_id=script_id, server_id=server_id)}")

    try:
        exec_id, status = _exec_once(script_id, server_id, executed_by, None)
        # Re-fetch the execution row to ensure we return the finalized status
        sess = SessionLocal()
        try:
            row = sess.query(ScriptExecution).get(exec_id)
            if row is not None:
                status = row.status
        finally:
            try: sess.close()
            except Exception: pass
        logger.info(f"enqueue_execute done {kv(execution_id=exec_id, status=status)}")
        return {"execution_id": exec_id, "status": status}
    except Exception as e:
        # create failed row if nothing returned
        sess = SessionLocal()
        try:
            se = ScriptExecution(
                script_id=script_id,
                server_id=server_id,
                executed_by=executed_by,
                status="failed",
                error=str(e),
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            sess.add(se)
            sess.commit()
            logger.error(f"enqueue_execute error {kv(error=str(e), execution_id=se.id)}")
            return {"execution_id": se.id, "status": "failed", "error": str(e)}
        finally:
            try: sess.close()
            except Exception: pass
