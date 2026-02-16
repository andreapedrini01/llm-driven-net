#!/usr/bin/env python3
"""
Secrets Manager for LLM Integration Module

Provides secure secrets management with support for:
- Environment variables
- File-based secrets (Docker secrets)
- AWS Secrets Manager (optional)
- Azure Key Vault (optional)
"""

import os
import json
import base64
from pathlib import Path
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class SecretsManager:
    """Manages application secrets from multiple sources"""
    
    def __init__(self, secrets_dir: str = "/run/secrets"):
        self.secrets_dir = Path(secrets_dir)
        self._cache: Dict[str, str] = {}
        
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get secret from multiple sources in priority order:
        1. Environment variable
        2. Docker secrets file
        3. Encrypted secrets file
        4. Default value
        """
        # Check cache first
        if key in self._cache:
            return self._cache[key]
            
        # 1. Check environment variable
        value = os.getenv(key)
        if value:
            self._cache[key] = value
            return value
            
        # 2. Check Docker secrets
        secret_file = self.secrets_dir / key.lower()
        if secret_file.exists():
            value = secret_file.read_text().strip()
            self._cache[key] = value
            return value
            
        # 3. Check encrypted secrets file
        encrypted_file = Path("config/secrets.enc")
        if encrypted_file.exists():
            value = self._get_from_encrypted_file(key, encrypted_file)
            if value:
                self._cache[key] = value
                return value
                
        return default
        
    def _get_from_encrypted_file(self, key: str, file_path: Path) -> Optional[str]:
        """Get secret from encrypted JSON file"""
        try:
            encryption_key = os.getenv("SECRETS_ENCRYPTION_KEY")
            if not encryption_key:
                return None
                
            fernet = Fernet(encryption_key.encode())
            encrypted_data = file_path.read_bytes()
            decrypted_data = fernet.decrypt(encrypted_data)
            secrets = json.loads(decrypted_data)
            
            return secrets.get(key)
        except Exception:
            return None
            
    def set_secret(self, key: str, value: str):
        """Set secret in cache (for testing)"""
        self._cache[key] = value
        
    def clear_cache(self):
        """Clear secrets cache"""
        self._cache.clear()


class SecretsEncryptor:
    """Utility for encrypting/decrypting secrets files"""
    
    @staticmethod
    def generate_key(password: str, salt: Optional[bytes] = None) -> tuple[bytes, bytes]:
        """Generate encryption key from password"""
        if salt is None:
            salt = os.urandom(16)
            
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt
        
    @staticmethod
    def encrypt_secrets(secrets: Dict[str, Any], password: str) -> bytes:
        """Encrypt secrets dictionary"""
        key, salt = SecretsEncryptor.generate_key(password)
        fernet = Fernet(key)
        
        data = json.dumps(secrets).encode()
        encrypted = fernet.encrypt(data)
        
        # Prepend salt to encrypted data
        return salt + encrypted
        
    @staticmethod
    def decrypt_secrets(encrypted_data: bytes, password: str) -> Dict[str, Any]:
        """Decrypt secrets"""
        # Extract salt from first 16 bytes
        salt = encrypted_data[:16]
        encrypted = encrypted_data[16:]
        
        key, _ = SecretsEncryptor.generate_key(password, salt)
        fernet = Fernet(key)
        
        decrypted = fernet.decrypt(encrypted)
        return json.loads(decrypted)


def create_secrets_file(output_path: str = "config/secrets.enc"):
    """Interactive tool to create encrypted secrets file"""
    import getpass
    
    print("=== Secrets File Creator ===\n")
    
    secrets = {}
    
    # Collect secrets
    print("Enter secrets (press Enter with empty value to finish):\n")
    
    secret_keys = [
        "OPENAI_API_KEY",
        "JWT_SECRET_KEY",
        "ADMIN_PASSWORD",
        "OPERATOR_PASSWORD",
        "VIEWER_PASSWORD",
        "SMTP_PASSWORD",
        "SLACK_WEBHOOK_URL",
    ]
    
    for key in secret_keys:
        value = getpass.getpass(f"{key}: ")
        if value:
            secrets[key] = value
            
    if not secrets:
        print("No secrets provided. Exiting.")
        return
        
    # Get encryption password
    password = getpass.getpass("\nEncryption password: ")
    password_confirm = getpass.getpass("Confirm password: ")
    
    if password != password_confirm:
        print("Passwords don't match. Exiting.")
        return
        
    # Encrypt and save
    encrypted = SecretsEncryptor.encrypt_secrets(secrets, password)
    
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encrypted)
    
    print(f"\n✓ Secrets file created: {output_path}")
    print(f"✓ Set SECRETS_ENCRYPTION_KEY environment variable to use it")


def generate_jwt_secret() -> str:
    """Generate a secure JWT secret key"""
    import secrets
    return secrets.token_urlsafe(32)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "create":
        create_secrets_file()
    elif len(sys.argv) > 1 and sys.argv[1] == "generate-jwt":
        print(f"JWT Secret: {generate_jwt_secret()}")
    else:
        print("Usage:")
        print("  python secrets_manager.py create          # Create encrypted secrets file")
        print("  python secrets_manager.py generate-jwt    # Generate JWT secret key")
