#!/usr/bin/env python3
import requests
import json

# Login credentials
username = "r00t"
password = "235711"
base_url = "http://localhost:8000"

# Get token
print("Getting authentication token...")
login_response = requests.post(f"{base_url}/api/auth/login", 
                             json={"username": username, "password": password})

if login_response.status_code == 200:
    token = login_response.json()["access_token"]
    print(f"✓ Token obtained: {token[:20]}...")
    
    # Populate marketplace
    print("Populating marketplace...")
    headers = {"Authorization": f"Bearer {token}"}
    populate_response = requests.post(f"{base_url}/api/marketplace/populate", headers=headers)
    
    if populate_response.status_code == 200:
        result = populate_response.json()
        print(f"✓ {result['message']}")
    else:
        print(f"✗ Failed to populate marketplace: {populate_response.text}")
        
    # List marketplace scripts
    print("Listing marketplace scripts...")
    scripts_response = requests.get(f"{base_url}/api/marketplace/scripts", headers=headers)
    
    if scripts_response.status_code == 200:
        scripts_data = scripts_response.json()
        print(f"✓ Found {scripts_data['total']} scripts in marketplace:")
        for script in scripts_data['scripts']:
            print(f"  - {script['name']} ({script['category']})")
    else:
        print(f"✗ Failed to list scripts: {scripts_response.text}")
        
else:
    print(f"✗ Login failed: {login_response.text}")
