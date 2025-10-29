#!/usr/bin/env python3
"""
Migration script to add audit_logs table
Run this script to add the new audit logging table to your database.
"""

import sqlite3
import os

def migrate_database():
    db_path = "script_manager.db"
    
    if not os.path.exists(db_path):
        print(f"Database file {db_path} not found!")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if audit_logs table already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_logs'")
        if cursor.fetchone():
            print("audit_logs table already exists!")
            return
        
        # Create audit_logs table
        cursor.execute("""
            CREATE TABLE audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action VARCHAR NOT NULL,
                resource_type VARCHAR,
                resource_id INTEGER,
                details TEXT,
                ip_address VARCHAR,
                user_agent TEXT,
                success BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        # Create indexes for better performance
        cursor.execute("CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id)")
        cursor.execute("CREATE INDEX idx_audit_logs_action ON audit_logs(action)")
        cursor.execute("CREATE INDEX idx_audit_logs_resource_type ON audit_logs(resource_type)")
        cursor.execute("CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at)")
        cursor.execute("CREATE INDEX idx_audit_logs_success ON audit_logs(success)")
        
        conn.commit()
        print("✅ audit_logs table created successfully!")
        print("✅ Indexes created for better performance!")
        
    except Exception as e:
        print(f"❌ Error creating audit_logs table: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("🔧 Migrating database to add audit_logs table...")
    migrate_database()
    print("✅ Migration completed!")
