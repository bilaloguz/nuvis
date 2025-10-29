from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from pathlib import Path
from urllib.parse import quote_plus

# Get the current directory (backend directory)
current_dir = Path(__file__).parent
# Prefer DATABASE_URL env var (e.g., postgresql+psycopg2://user:pass@host:5432/db)
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
if not SQLALCHEMY_DATABASE_URL:
    # Default to local Postgres if POSTGRES_* env vars present, else fallback to SQLite
    pg_user = os.getenv("POSTGRES_USER")
    pg_pass = os.getenv("POSTGRES_PASSWORD")
    pg_host = os.getenv("POSTGRES_HOST", "localhost")
    pg_port = os.getenv("POSTGRES_PORT", "5432")
    pg_db = os.getenv("POSTGRES_DB")
    if pg_user and pg_pass and pg_db:
        SQLALCHEMY_DATABASE_URL = f"postgresql+psycopg2://{quote_plus(pg_user)}:{quote_plus(pg_pass)}@{pg_host}:{pg_port}/{pg_db}"
    else:
        SQLALCHEMY_DATABASE_URL = f"sqlite:///{current_dir}/script_manager.db"

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 30},
        pool_pre_ping=True,
        pool_reset_on_return="rollback",
    )
else:
    # Postgres or other DBs
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,
        pool_reset_on_return="rollback",
    )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            db.rollback()
        except Exception:
            pass
        db.close()

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    # Configure SQLite for better concurrency
    try:
        with engine.connect() as conn:
            try:
                conn.execute(text("PRAGMA journal_mode=WAL"))
                conn.execute(text("PRAGMA synchronous=NORMAL"))
            except Exception:
                pass
    except Exception:
        pass
