"""
SSH Key utilities for configurable key types
"""

from sqlalchemy.orm import Session
from models import Settings
from database import SessionLocal

def get_ssh_key_type() -> str:
    """
    Get the configured SSH key type from settings.
    Returns 'rsa' as default if not configured.
    """
    db = SessionLocal()
    try:
        settings = db.query(Settings).first()
        if settings and settings.ssh_key_type:
            return settings.ssh_key_type
        return "rsa"  # Default fallback
    except Exception:
        return "rsa"  # Default fallback
    finally:
        db.close()

def get_ssh_key_parameters(key_type: str) -> dict:
    """
    Get SSH key generation parameters based on key type.
    
    Args:
        key_type: The SSH key type ('rsa', 'ed25519', 'ecdsa')
    
    Returns:
        Dictionary with ssh-keygen parameters
    """
    if key_type == "ed25519":
        return {
            "type": "ed25519",
            "bits": None,  # Ed25519 has fixed key size
            "comment_prefix": "birun",
            "file_suffix": "id_ed25519"
        }
    elif key_type == "ecdsa":
        return {
            "type": "ecdsa",
            "bits": "256",  # ECDSA 256-bit (most common)
            "comment_prefix": "birun",
            "file_suffix": "id_ecdsa"
        }
    else:  # Default to RSA
        return {
            "type": "rsa",
            "bits": "4096",
            "comment_prefix": "birun",
            "file_suffix": "id_rsa"
        }

def get_paramiko_key_class(key_type: str):
    """
    Get the appropriate Paramiko key class for the given key type.
    
    Args:
        key_type: The SSH key type ('rsa', 'ed25519', 'ecdsa')
    
    Returns:
        Paramiko key class
    """
    import paramiko
    
    if key_type == "ed25519":
        return paramiko.Ed25519Key
    elif key_type == "ecdsa":
        return paramiko.ECDSAKey
    else:  # Default to RSA
        return paramiko.RSAKey

def detect_key_type_from_file(file_path: str) -> str:
    """
    Detect SSH key type from file content.
    
    Args:
        file_path: Path to the private key file
    
    Returns:
        Detected key type ('rsa', 'ed25519', 'ecdsa')
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        if "BEGIN OPENSSH PRIVATE KEY" in content:
            # OpenSSH format - try to detect type
            if "ed25519" in content.lower():
                return "ed25519"
            elif "ecdsa" in content.lower():
                return "ecdsa"
            else:
                return "rsa"  # Default for OpenSSH
        elif "BEGIN RSA PRIVATE KEY" in content:
            return "rsa"
        elif "BEGIN EC PRIVATE KEY" in content:
            return "ecdsa"
        else:
            return "rsa"  # Default fallback
    except Exception:
        return "rsa"  # Default fallback
