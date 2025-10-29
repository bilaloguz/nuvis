#!/usr/bin/env bash
set -euo pipefail

# Single-shot installer for biRun (Ubuntu/Debian-like systems)
# - Installs system deps, PostgreSQL (on port 5433), Redis
# - Creates DB/user, Python venv, installs backend deps
# - Applies Alembic migrations, writes .env
# - Prints next-step commands (start backend & RQ workers)

PROJECT_ROOT="/home/bilal/Desktop/dev/script-manager"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
DATA_DIR="$PROJECT_ROOT/data"
ENV_FILE="$PROJECT_ROOT/.env"
VENV_DIR="$BACKEND_DIR/venv"

# Configurable defaults
DB_USER="sm"
DB_PASS="ChangeMe123!"
DB_NAME="script_manager"
DB_HOST="localhost"
DB_PORT="5433"   # We detected Postgres running on 5433 on this machine
REDIS_URL="redis://localhost:6379/0"

# Helpers
log() { echo "[install] $*"; }
require_root() { if [[ $EUID -ne 0 ]]; then echo "This script must be run as root (use sudo)."; exit 1; fi }

require_root

log "Updating apt and installing system packages..."
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3-full python3-venv python3-pip build-essential pkg-config \
  libpq-dev redis-server postgresql postgresql-contrib git curl ca-certificates

log "Installing Node.js LTS (via NodeSource) for frontend build..."
if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs
else
  log "Node.js already installed: $(node -v)"
fi

log "Ensuring Redis is enabled and started..."
systemctl enable redis-server
systemctl restart redis-server

log "Configuring PostgreSQL to listen on $DB_PORT if needed..."
# Detect current port; if not $DB_PORT, update config
PG_CONF=$(find /etc/postgresql -name postgresql.conf | head -n1 || true)
if [[ -n "$PG_CONF" ]]; then
  CURRENT_PORT=$(sudo -u postgres psql -tAc "show port;" 2>/dev/null || echo "")
  if [[ "$CURRENT_PORT" != "$DB_PORT" ]]; then
    sed -i "s/^#\?port\s*=.*/port = $DB_PORT/" "$PG_CONF"
    systemctl restart postgresql
  fi
else
  log "WARN: Could not locate postgresql.conf; skipping port check"
fi

log "Creating Postgres role and database (if not exist)..."
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO
\$do\$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DB_USER}'
   ) THEN
      CREATE ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASS}' CREATEDB;
   END IF;
END
\$do\$;

DO
\$do\$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_database WHERE datname = '${DB_NAME}'
   ) THEN
      CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};
   END IF;
END
\$do\$;
SQL

log "Ensuring pg_hba permits local TCP auth..."
PG_HBA=$(find /etc/postgresql -name pg_hba.conf | head -n1 || true)
if [[ -n "$PG_HBA" ]]; then
  if ! grep -E "^host\s+all\s+all\s+127\.0\.0\.1/32\s+" "$PG_HBA" >/dev/null; then
    echo "host    all             all             127.0.0.1/32            scram-sha-256" >> "$PG_HBA"
    systemctl restart postgresql
  fi
fi

mkdir -p "$DATA_DIR"

log "Writing .env with DATABASE_URL and REDIS_URL..."
DATABASE_URL="postgresql://$DB_USER:$DB_PASS@$DB_HOST:$DB_PORT/$DB_NAME"
if [[ -f "$ENV_FILE" ]]; then
  sed -i "/^DATABASE_URL=/d" "$ENV_FILE" || true
  sed -i "/^REDIS_URL=/d" "$ENV_FILE" || true
fi
echo "DATABASE_URL=$DATABASE_URL" >> "$ENV_FILE"
echo "REDIS_URL=$REDIS_URL" >> "$ENV_FILE"

log "Creating Python venv and installing backend dependencies..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip wheel setuptools
# Prefer binary psycopg to avoid local build issues
pip install "psycopg2-binary==2.9.9" "alembic==1.13.2"
# Install backend requirements if present
if [[ -f "$BACKEND_DIR/requirements.txt" ]]; then
  pip install -r "$BACKEND_DIR/requirements.txt"
fi

log "Exporting env for migration run..."
export DATABASE_URL
export REDIS_URL
export PYTHONPATH="$BACKEND_DIR"

log "Applying Alembic migrations..."
cd "$BACKEND_DIR"
python -m alembic upgrade head

if [[ -d "$FRONTEND_DIR" && -f "$FRONTEND_DIR/package.json" ]]; then
  log "Installing frontend dependencies and building (this may take a while)..."
  cd "$FRONTEND_DIR"
  if [[ -f package-lock.json ]]; then
    npm ci --no-audit --no-fund
  else
    npm install --no-audit --no-fund
  fi
  npm run build
fi

log "Installation complete. Next steps:"
echo ""; echo "=========================================================="
echo "Backend (dev):"
echo "  cd $BACKEND_DIR && source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "Frontend (dev):"
echo "  cd $FRONTEND_DIR && npm start"
echo ""
echo "Start RQ workers (8 workers, 2 queues: execute default):"
echo "  cd $BACKEND_DIR && source venv/bin/activate && export REDIS_URL=$REDIS_URL PYTHONPATH=$BACKEND_DIR; for i in \$(seq 1 8); do RQ_WORKER_NAME=sm-\$i nohup ./venv/bin/rq worker execute default > worker_\$i.log 2>&1 & done"
echo ""
echo "Check workers:"
echo "  cd $BACKEND_DIR && ./venv/bin/rq info --url $REDIS_URL"
echo "=========================================================="
