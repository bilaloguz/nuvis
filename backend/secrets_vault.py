import os
from typing import Optional
from cryptography.fernet import Fernet


class SecretsVault:
    """Simple Fernet-based vault for encrypting/decrypting secrets at rest.

    Key management:
      - Loads key from VAULT_KEY_PATH env or defaults to 'vault.key' in CWD
      - If the key file does not exist, it is created with a new key
    """

    _instance: Optional["SecretsVault"] = None

    def __init__(self, key_path: str):
        self.key_path = key_path
        if not os.path.exists(self.key_path):
            key = Fernet.generate_key()
            with open(self.key_path, "wb") as f:
                f.write(key)
        with open(self.key_path, "rb") as f:
            key = f.read()
        self.fernet = Fernet(key)

    @classmethod
    def get(cls) -> "SecretsVault":
        if cls._instance is None:
            key_path = os.environ.get("VAULT_KEY_PATH", "vault.key")
            cls._instance = SecretsVault(key_path)
        return cls._instance

    def encrypt_to_str(self, plaintext: str) -> str:
        if plaintext is None:
            return ""
        token = self.fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt_to_str(self, token_str: str) -> str:
        if not token_str:
            return ""
        plaintext = self.fernet.decrypt(token_str.encode("utf-8"))
        return plaintext.decode("utf-8")