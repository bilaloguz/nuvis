#!/usr/bin/env python3
"""
Admin User Creation Script for biRun

This script creates the first admin user for the biRun application.
Run this script before starting the application for the first time.

Usage:
    python create_admin.py
"""

import sys
import os
import getpass
from pathlib import Path

# Add the backend directory to the Python path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

try:
    from database import engine, SessionLocal
    from models import User, Base
    from auth import get_password_hash
    from schemas import UserCreate
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure you're running this script from the project root directory.")
    sys.exit(1)

def create_admin_user():
    """Create the first admin user interactively."""
    
    print("=" * 50)
    print("biRun - Admin User Creation")
    print("=" * 50)
    print()
    
    # Check if database exists and create tables if needed
    try:
        Base.metadata.create_all(bind=engine)
        print("✓ Database initialized successfully")
    except Exception as e:
        print(f"✗ Error initializing database: {e}")
        return False
    
    # Check if any users already exist
    db = SessionLocal()
    try:
        existing_users = db.query(User).count()
        if existing_users > 0:
            print(f"⚠  Database already contains {existing_users} user(s)")
            response = input("Do you want to create another admin user? (y/N): ").strip().lower()
            if response not in ['y', 'yes']:
                print("Admin creation cancelled.")
                return True
    except Exception as e:
        print(f"✗ Error checking existing users: {e}")
        db.close()
        return False
    
    print()
    print("Please provide the admin user details:")
    print()
    
    # Get admin user information
    try:
        username = input("Username: ").strip()
        if not username:
            print("✗ Username cannot be empty")
            return False
        
        email = input("Email: ").strip()
        if not email or '@' not in email:
            print("✗ Please provide a valid email address")
            return False
        
        # Check if username or email already exists
        existing_user = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            print(f"✗ User with username '{username}' or email '{email}' already exists")
            return False
        
        # Get password securely
        while True:
            password = getpass.getpass("Password: ")
            if len(password) < 6:
                print("✗ Password must be at least 6 characters long")
                continue
            
            confirm_password = getpass.getpass("Confirm Password: ")
            if password != confirm_password:
                print("✗ Passwords do not match")
                continue
            
            break
        
        # Create admin user
        hashed_password = get_password_hash(password)
        admin_user = User(
            username=username,
            email=email,
            password_hash=hashed_password,
            role="admin"
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        print()
        print("=" * 50)
        print("✓ Admin user created successfully!")
        print("=" * 50)
        print(f"Username: {admin_user.username}")
        print(f"Email: {admin_user.email}")
        print(f"Role: {admin_user.role}")
        print(f"User ID: {admin_user.id}")
        print()
        print("You can now login to the application with these credentials.")
        print("=" * 50)
        
        return True
        
    except KeyboardInterrupt:
        print("\n\n✗ Admin creation cancelled by user")
        return False
    except Exception as e:
        print(f"✗ Error creating admin user: {e}")
        return False
    finally:
        db.close()

def main():
    """Main function to run the admin creation script."""
    
    print("biRun - First Time Setup")
    print("This script will create the first admin user for your application.")
    print()
    
    # Check if we're in the right directory
    if not os.path.exists("backend"):
        print("✗ Error: 'backend' directory not found.")
        print("Please run this script from the project root directory.")
        sys.exit(1)
    
    if not os.path.exists("backend/database.py"):
        print("✗ Error: Database configuration not found.")
        print("Please ensure the backend is properly set up.")
        sys.exit(1)
    
    try:
        success = create_admin_user()
        if success:
            print("\n✓ Setup completed successfully!")
            print("You can now start the application and login with your admin account.")
        else:
            print("\n✗ Setup failed. Please check the error messages above.")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
