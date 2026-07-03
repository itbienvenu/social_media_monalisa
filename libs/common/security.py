import base64
import os
import hashlib

def encrypt_token(token: str, key: str = None) -> str:
    """
    Encrypts a token using a pure Python XOR cipher with SHA256 hashed key.
    """
    if not token:
        return ""
    if key is None:
        key = os.getenv("ENCRYPTION_KEY", "default-secret-key-12345")
    
    key_hash = hashlib.sha256(key.encode()).digest()
    token_bytes = token.encode()
    encrypted_bytes = bytes(b ^ key_hash[i % len(key_hash)] for i, b in enumerate(token_bytes))
    return base64.b64encode(encrypted_bytes).decode()

def decrypt_token(encrypted_token: str, key: str = None) -> str:
    """
    Decrypts a token using a pure Python XOR cipher with SHA256 hashed key.
    """
    if not encrypted_token:
        return ""
    if key is None:
        key = os.getenv("ENCRYPTION_KEY", "default-secret-key-12345")
        
    key_hash = hashlib.sha256(key.encode()).digest()
    encrypted_bytes = base64.b64decode(encrypted_token.encode())
    decrypted_bytes = bytes(b ^ key_hash[i % len(key_hash)] for i, b in enumerate(encrypted_bytes))
    return decrypted_bytes.decode()
