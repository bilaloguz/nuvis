from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import Schedule
from schemas import ScheduleCreate, ScheduleUpdate, ScheduleResponse, ScheduleListResponse
from auth import get_current_user
from audit_utils import log_audit
from croniter import croniter
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except Exception:  # Python <3.9 fallback not provided; default UTC
    ZoneInfo = None

router = APIRouter()

@router.post("/", response_model=ScheduleResponse)
def create_schedule(payload: ScheduleCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # Default timezone to user's local if not provided
    # Frontend sends the browser tz; fallback to Europe/Istanbul if configured via header; else UTC
    browser_tz = None
    try:
        from fastapi import Request  # type: ignore
    except Exception:
        Request = None

    schedule = Schedule(
        name=payload.name,
        script_id=payload.script_id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        cron_expression=payload.cron_expression,
        interval_seconds=payload.interval_seconds,
        timezone=(payload.timezone or ((browser_tz or None) or "Europe/Istanbul")),
        enabled=True if payload.enabled is None else payload.enabled,
        created_by=current_user.id
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    # Initialize next_run_at in UTC immediately
    try:
        from datetime import datetime, timezone
        from scheduler import _compute_next_run
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        schedule.next_run_at = _compute_next_run(schedule, now)
        db.commit()
        db.refresh(schedule)
    except Exception:
        pass
    
    log_audit(db, action="schedule_create", resource_type="schedule", resource_id=schedule.id, user_id=current_user.id, details={"name": schedule.name})
    
    # Sync schedules to APScheduler
    try:
        from scheduler import sync_schedules
        sync_schedules()
    except Exception as e:
        print(f"WARN: Failed to sync schedules after create: {e}")
    
    return schedule

@router.get("/", response_model=ScheduleListResponse)
def list_schedules(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    q = db.query(Schedule).order_by(Schedule.created_at.desc())
    items = q.all()
    return {"schedules": items, "total": len(items)}

@router.get("/{schedule_id}", response_model=ScheduleResponse)
def get_schedule(schedule_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return schedule

@router.put("/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(schedule_id: int, payload: ScheduleUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    
    # Track if schedule timing fields changed
    timing_changed = False
    for field, value in payload.dict(exclude_unset=True).items():
        if field in ['cron_expression', 'interval_seconds', 'timezone', 'enabled']:
            timing_changed = True
        setattr(schedule, field, value)
    
    # Recalculate next_run_at if timing fields changed
    if timing_changed:
        from datetime import datetime, timezone
        from scheduler import _compute_next_run
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        schedule.next_run_at = _compute_next_run(schedule, now)
    
    db.commit()
    db.refresh(schedule)
    log_audit(db, action="schedule_update", resource_type="schedule", resource_id=schedule.id, user_id=current_user.id, details={"name": schedule.name})
    
    # Sync schedules to APScheduler
    try:
        from scheduler import sync_schedules
        sync_schedules()
    except Exception as e:
        print(f"WARN: Failed to sync schedules after update: {e}")
    
    return schedule

@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    
    schedule_name = schedule.name
    db.delete(schedule)
    db.commit()
    
    log_audit(db, action="schedule_delete", resource_type="schedule", resource_id=schedule_id, user_id=current_user.id, details={"name": schedule_name})
    
    # Sync schedules to APScheduler
    try:
        from scheduler import sync_schedules
        sync_schedules()
    except Exception as e:
        print(f"WARN: Failed to sync schedules after delete: {e}")
    
    return {"detail": "deleted"}

@router.get("/cron/preview")
def preview_cron(
    expr: str = Query(..., description="Cron expression"),
    tz: str = Query("UTC", description="Timezone (IANA)"),
    count: int = Query(5, ge=1, le=10),
    current_user=Depends(get_current_user)
):
    # Normalize expression: trim and collapse spaces; allow 4 fields by appending '*'
    expr_raw = (expr or "").strip()
    expr_norm = " ".join(expr_raw.split())
    parts = expr_norm.split(" ") if expr_norm else []
    if len(parts) == 4:
        parts.append("*")
        expr_norm = " ".join(parts)
    if len(parts) != 5 or any(p == "" for p in parts):
        raise HTTPException(status_code=400, detail=f"Invalid cron expression: expected 5 fields, got {len(parts) or 0}")

    tzinfo = None
    if ZoneInfo is not None:
        try:
            tzinfo = ZoneInfo(tz)
        except Exception:
            tzinfo = ZoneInfo("UTC")
    # Base time in specified tz (aware if possible)
    now = datetime.now(tzinfo) if tzinfo else datetime.utcnow()
    try:
        it = croniter(expr_norm, now)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid cron expression: {e}")
    runs = []
    for _ in range(count):
        dt = it.get_next(datetime)
        if tzinfo and dt.tzinfo is None:
            dt = dt.replace(tzinfo=tzinfo)
        runs.append(dt.isoformat())
    return {"next": runs, "now": now.isoformat(), "tz": tz, "expr": expr_norm}
