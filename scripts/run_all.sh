#!/usr/bin/env bash
set -euo pipefail

# Run everything for biRun (dev): Redis, PostgreSQL, backend, frontend, RQ workers
# - Uses tmux if available for managed panes/sessions
# - Otherwise runs processes in background with logs under scripts/logs and pids in scripts/pids

PROJECT_ROOT="/home/bilal/Desktop/dev/script-manager"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
LOG_DIR="$PROJECT_ROOT/scripts/logs"
PID_DIR="$PROJECT_ROOT/scripts/pids"
ENV_FILE="$PROJECT_ROOT/.env"
VENV_DIR="$BACKEND_DIR/venv"

mkdir -p "$LOG_DIR" "$PID_DIR"

# Load env if present
if [[ -f "$ENV_FILE" ]]; then
  set -a; source "$ENV_FILE"; set +a
fi

: "${DATABASE_URL:=}"
: "${REDIS_URL:=redis://localhost:6379/0}"
: "${PORT:=8000}"

command_exists() { command -v "$1" >/dev/null 2>&1; }

start_service() {
  local name="$1"; shift
  local cmd="$*"
  local log="$LOG_DIR/${name}.log"
  echo "[run] starting $name -> $cmd"
  nohup bash -lc "$cmd" > "$log" 2>&1 &
  echo $! > "$PID_DIR/${name}.pid"
}

kill_if_running() {
  local name="$1"
  if [[ -f "$PID_DIR/${name}.pid" ]]; then
    local pid; pid=$(cat "$PID_DIR/${name}.pid" || true)
    if [[ -n "${pid}" ]] && ps -p "$pid" >/dev/null 2>&1; then
      echo "[run] stopping $name (pid $pid)"
      kill "$pid" || true
    fi
    rm -f "$PID_DIR/${name}.pid"
  fi
}

# Ensure system services are up
if command_exists systemctl; then
  echo "[run] ensuring redis-server is running"
  sudo systemctl restart redis-server || true
  echo "[run] ensuring postgresql is running"
  sudo systemctl restart postgresql || true
fi

# Backend
# Run backend without --reload so the scheduler runs in the main process and logs are captured
BACKEND_CMD="cd $BACKEND_DIR && source $VENV_DIR/bin/activate && PYTHONUNBUFFERED=1 uvicorn main:app --host 0.0.0.0 --port $PORT"
# Frontend (ensure deps, run on HOST:0.0.0.0 PORT:3000, avoid auto-opening browser)
FRONTEND_CMD="cd $FRONTEND_DIR && ([ -d node_modules ] || npm ci --no-audit --no-fund) && HOST=0.0.0.0 PORT=9753 BROWSER=none npm start"
# Workers (8)
WORKER_CMD="cd $BACKEND_DIR && source $VENV_DIR/bin/activate && export DATABASE_URL=\"${DATABASE_URL}\" REDIS_URL=\"${REDIS_URL}\" PYTHONPATH=\"$BACKEND_DIR\"; rq worker execute default"

if command_exists tmux; then
  SESSION="sm-dev"
  echo "[run] using tmux session: $SESSION"
  tmux has-session -t "$SESSION" 2>/dev/null && tmux kill-session -t "$SESSION" || true
  tmux new-session -d -s "$SESSION" -n backend "$BACKEND_CMD"
  tmux new-window -t "$SESSION" -n frontend "$FRONTEND_CMD"
  for i in $(seq 1 8); do
    tmux new-window -t "$SESSION" -n worker-$i "$WORKER_CMD"
  done
  echo "[run] attach with: tmux attach -t $SESSION"
  exit 0
fi

# Fallback: background processes
kill_if_running backend || true
kill_if_running frontend || true
for i in $(seq 1 8); do kill_if_running worker-$i || true; done

start_service backend "$BACKEND_CMD"
start_service frontend "$FRONTEND_CMD"
for i in $(seq 1 8); do start_service worker-$i "$WORKER_CMD"; done

echo "[run] started. Logs: $LOG_DIR; PIDs: $PID_DIR"
echo "[run] stop with: pkill -f 'uvicorn main:app' && pkill -f 'rq worker' && (command -v systemctl >/dev/null && sudo systemctl stop redis-server || true)"
