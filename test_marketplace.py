#!/usr/bin/env python3
import sys
sys.path.append('/home/bilal/Desktop/dev/script-manager/backend')

try:
    from routers.marketplace import router
    print("✓ Marketplace router imported successfully")
except Exception as e:
    print(f"✗ Error importing marketplace router: {e}")

try:
    from models import MarketplaceScript
    print("✓ MarketplaceScript model imported successfully")
except Exception as e:
    print(f"✗ Error importing MarketplaceScript model: {e}")
