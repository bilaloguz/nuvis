from fastapi import Depends, HTTPException, Request
from typing import List

# Simple in-memory allowlist for admin IPs; can be moved to DB/Settings later
ADMIN_IP_ALLOWLIST: List[str] = [
    "127.0.0.1",
    "::1",
    "192.168.11.149",
    "192.168.10.225",
    "192.168.0.0/16",  # Allow all 192.168.x.x IPs
    "10.0.0.0/8",      # Allow all 10.x.x.x IPs
    "172.16.0.0/12",   # Allow all 172.16-31.x.x IPs
]

def admin_ip_guard(request: Request):
    client_ip = request.client.host if request.client else None
    if not client_ip:
        raise HTTPException(status_code=403, detail="Could not determine client IP")
    
    # Allow localhost and private network ranges
    if (client_ip in ADMIN_IP_ALLOWLIST or 
        client_ip.startswith("192.168.") or 
        client_ip.startswith("10.") or 
        client_ip.startswith("172.")):
        return True
    
    raise HTTPException(status_code=403, detail="Admin access restricted by IP allowlist")


