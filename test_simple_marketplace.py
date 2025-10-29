#!/usr/bin/env python3
import sys
sys.path.append('/home/bilal/Desktop/dev/script-manager/backend')

from database import get_db
from models import MarketplaceScript
from sqlalchemy.orm import Session

# Test database connection and table
db = next(get_db())
try:
    count = db.query(MarketplaceScript).count()
    print(f"✓ Marketplace table exists, count: {count}")
except Exception as e:
    print(f"✗ Error querying marketplace table: {e}")

# Test creating a simple script
try:
    script = MarketplaceScript(
        name="test-script",
        description="Test script",
        content="echo 'hello'",
        script_type="shell"
    )
    db.add(script)
    db.commit()
    print("✓ Successfully created test script")
    
    # Clean up
    db.delete(script)
    db.commit()
    print("✓ Cleaned up test script")
except Exception as e:
    print(f"✗ Error creating script: {e}")
finally:
    db.close()
