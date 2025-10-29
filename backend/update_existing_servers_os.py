#!/usr/bin/env python3
"""
Script to update OS detection for existing servers.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from models import Server
from os_detection import detect_os_automatically
from secrets_vault import SecretsVault

def update_servers_os():
    """Update OS detection for all existing servers."""
    db = SessionLocal()
    vault = SecretsVault.get()
    
    try:
        # Get all servers without OS detection
        servers = db.query(Server).filter(
            (Server.detected_os.is_(None)) | (Server.detected_os == '')
        ).all()
        
        print(f"Found {len(servers)} servers without OS detection")
        
        for server in servers:
            print(f"\n🔍 Detecting OS for server: {server.name} ({server.ip})")
            
            # Get password if available
            password = None
            if server.password_encrypted:
                try:
                    password = vault.decrypt_to_str(server.password_encrypted)
                except Exception as e:
                    print(f"  ⚠️  Could not decrypt password: {e}")
            
            # Detect OS
            detected_os, detection_method = detect_os_automatically(
                ip=server.ip,
                username=server.username,
                password=password,
                ssh_key_path=server.ssh_key_path
            )
            
            print(f"  🖥️  Detected OS: {detected_os} (method: {detection_method})")
            
            # Update server record
            server.detected_os = detected_os
            server.os_detection_method = detection_method
            
            db.commit()
            print(f"  ✅ Updated server {server.name}")
        
        print(f"\n🎉 Successfully updated {len(servers)} servers!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_servers_os()
