#!/usr/bin/env python3
import sys
sys.path.append('/home/bilal/Desktop/dev/script-manager/backend')

from database import engine
from sqlalchemy import text

# Drop the table and recreate it with correct schema
with engine.connect() as conn:
    # Drop table if exists
    conn.execute(text("DROP TABLE IF EXISTS marketplace_scripts CASCADE"))
    conn.commit()
    
    # Create table with correct schema
    conn.execute(text("""
        CREATE TABLE marketplace_scripts (
            id SERIAL PRIMARY KEY,
            name VARCHAR UNIQUE NOT NULL,
            description TEXT,
            category VARCHAR,
            script_type VARCHAR DEFAULT 'shell',
            content TEXT NOT NULL,
            parameters TEXT,
            tags TEXT,
            author VARCHAR,
            version VARCHAR DEFAULT '1.0.0',
            downloads INTEGER DEFAULT 0,
            rating FLOAT DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conn.commit()
    print("✓ Table recreated with correct schema")
