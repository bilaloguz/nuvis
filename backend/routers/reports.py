from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timedelta
import os
import smtplib
from email.message import EmailMessage

from database import get_db
from models import ScriptExecution, User, Script, Server, Settings
from auth import get_current_user

router = APIRouter()


def _render_digest(executions: list[ScriptExecution]) -> tuple[str, str]:
    total = len(executions)
    completed = sum(1 for e in executions if e.status == 'completed')
    failed = sum(1 for e in executions if e.status == 'failed')
    running = sum(1 for e in executions if e.status == 'running')

    # Text
    lines = [
        f"biRun Daily Digest",
        f"Total executions: {total}",
        f"Completed: {completed}",
        f"Failed: {failed}",
        f"Running: {running}",
        "",
        "Recent failures:",
    ]
    for e in executions:
        if e.status == 'failed':
            lines.append(f"- {e.script.name if e.script else e.script_id} on {e.server.name if e.server else e.server_id} at {e.started_at}: {str(e.error)[:160] if e.error else ''}")
    text_body = "\n".join(lines)

    # HTML
    html = [
        "<html><body style='font-family:Arial, sans-serif'>",
        "<h2>biRun Daily Digest</h2>",
        f"<p><strong>Total:</strong> {total} &nbsp; <strong>Completed:</strong> {completed} &nbsp; <strong>Failed:</strong> {failed} &nbsp; <strong>Running:</strong> {running}</p>",
        "<h3>Recent failures</h3>",
        "<table cellpadding='6' cellspacing='0' border='1' style='border-collapse:collapse;border-color:#ddd'>",
        "<thead><tr><th>Script</th><th>Server</th><th>Started</th><th>Error</th></tr></thead><tbody>",
    ]
    for e in executions:
        if e.status == 'failed':
            html.append(
                f"<tr><td>{(e.script.name if e.script else e.script_id)}</td><td>{(e.server.name if e.server else e.server_id)}</td><td>{e.started_at}</td><td>{(str(e.error)[:200] if e.error else '')}</td></tr>"
            )
    html.append("</tbody></table>")
    html.append("</body></html>")
    return text_body, "".join(html)


@router.post("/daily-digest")
def send_daily_digest(
    to: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can send digest")

    since = datetime.utcnow() - timedelta(days=1)
    q = db.query(ScriptExecution).options(
        joinedload(ScriptExecution.script),
        joinedload(ScriptExecution.server),
        joinedload(ScriptExecution.executor),
    ).filter(ScriptExecution.started_at >= since)
    st = db.query(Settings).first()
    if getattr(st, 'digest_only_failed', False):
        q = q.filter(ScriptExecution.status == 'failed')
    executions = q.order_by(ScriptExecution.started_at.desc()).all()

    text_body, html_body = _render_digest(executions)

    # SMTP configuration
    st = db.query(Settings).first()
    smtp_host = getattr(st, 'smtp_host', None)
    smtp_port = int(getattr(st, 'smtp_port', 587) or 587)
    smtp_user = getattr(st, 'smtp_user', None)
    smtp_pass = getattr(st, 'smtp_pass', None)
    from_email = getattr(st, 'from_email', None) or (smtp_user or "no-reply@example.com")
    to_emails = (to or (getattr(st, 'digest_to_emails', '') or '')).split(",")
    to_emails = [x.strip() for x in to_emails if x.strip()]

    if not smtp_host or not smtp_user or not smtp_pass or not to_emails:
        # Return preview instead of sending
        return {
            "sent": False,
            "reason": "SMTP not configured or recipient not provided",
            "preview": {
                "subject": "biRun Daily Digest",
                "to": to_emails,
                "text": text_body[:1000],
                "html": html_body[:2000]
            }
        }

    msg = EmailMessage()
    msg["Subject"] = "biRun Daily Digest"
    msg["From"] = from_email
    msg["To"] = ", ".join(to_emails)
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype='html')

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return {"sent": True, "to": to_emails, "count": len(executions)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {e}")


