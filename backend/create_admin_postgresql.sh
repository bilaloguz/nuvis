python3 - <<'PY'
import os
from datetime import datetime
from passlib.hash import bcrypt
from database import SessionLocal
from models import User, Base
from database import engine

# Ensure tables exist
Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    if db.query(User).filter(User.username=='admin').first():
        print("Admin user already exists.")
    else:
        u = User(
            username='r00t',
            email='r00t@example.com',
            password_hash=bcrypt.hash('235711'),
            role='admin',
            created_at=datetime.utcnow()
        )
        db.add(u)
        db.commit()
        print("Admin user created: admin / Admin123!")
finally:
    db.close()
PY
