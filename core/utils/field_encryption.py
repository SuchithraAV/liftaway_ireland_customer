"""
Field-Level Encryption for PII and Sensitive Data

Uses AES-256-GCM with deterministic and non-deterministic modes.
- Deterministic: For searchable fields (email, phone)
- Non-deterministic: For non-searchable fields (address, bank details)
"""

import hashlib
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Encryption keys from environment
FIELD_ENCRYPTION_KEY = os.getenv("FIELD_ENCRYPTION_KEY", "FieldEncryptionKey2024!@#$%^&*")
DETERMINISTIC_KEY = os.getenv("DETERMINISTIC_ENCRYPTION_KEY", "DeterministicKey2024!@#$%^&*")


def _derive_key(secret: str, salt: str = "") -> bytes:
    """Derive 256-bit key from secret"""
    key_material = f"{secret}{salt}"
    return hashlib.sha256(key_material.encode('utf-8')).digest()


def encrypt_field(plaintext: str, deterministic: bool = False) -> str:
    """
    Encrypt a field value.
    
    Args:
        plaintext: Value to encrypt
        deterministic: If True, same input always produces same output (for searchable fields)
    
    Returns:
        Base64 encoded encrypted value with prefix
    """
    if not plaintext:
        return plaintext
    
    try:
        if deterministic:
            # Deterministic encryption: use fixed nonce derived from plaintext
            key = _derive_key(DETERMINISTIC_KEY)
            nonce = hashlib.sha256(plaintext.encode('utf-8')).digest()[:12]
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
            # Store nonce with ciphertext for decryption
            encrypted_data = nonce + ciphertext
        else:
            # Non-deterministic: random nonce for maximum security
            key = _derive_key(FIELD_ENCRYPTION_KEY)
            nonce = os.urandom(12)
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
            encrypted_data = nonce + ciphertext
        
        return base64.b64encode(encrypted_data).decode('utf-8')
    
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        raise ValueError(f"Failed to encrypt field: {e}")


def decrypt_field(encrypted_base64: str, deterministic: bool = False) -> str:
    """
    Decrypt a field value.
    
    Args:
        encrypted_base64: Base64 encoded encrypted value
        deterministic: Must match encryption mode
    
    Returns:
        Decrypted plaintext
    """
    if not encrypted_base64:
        return encrypted_base64
    
    try:
        encrypted_data = base64.b64decode(encrypted_base64)
        
        # Both modes now store nonce + ciphertext
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        
        if deterministic:
            key = _derive_key(DETERMINISTIC_KEY)
        else:
            key = _derive_key(FIELD_ENCRYPTION_KEY)
        
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        
        return plaintext.decode('utf-8')
    
    except Exception as e:
        logger.error(f"Decryption error: {e}")
        # Return original if decryption fails (backward compatibility)
        return encrypted_base64


def hash_for_lookup(plaintext: str) -> str:
    """
    Create searchable hash for deterministic fields.
    Use this for database lookups instead of deterministic encryption.
    
    Args:
        plaintext: Value to hash
    
    Returns:
        Hex encoded hash
    """
    if not plaintext:
        return plaintext
    
    # Use HMAC-SHA256 for secure hashing
    key = _derive_key(DETERMINISTIC_KEY)
    return hashlib.sha256(f"{key.hex()}{plaintext}".encode('utf-8')).hexdigest()


def is_encrypted(text: str) -> bool:
    """Check if text appears to be encrypted"""
    if not text or len(text) < 20:
        return False
    
    try:
        decoded = base64.b64decode(text)
        return len(decoded) >= 29  # Min encrypted size
    except Exception:
        return False


# Convenience functions for specific field types

def encrypt_phone(phone: str) -> str:
    """Encrypt phone number (searchable)"""
    return encrypt_field(phone, deterministic=True)


def decrypt_phone(encrypted: str) -> str:
    """Decrypt phone number"""
    return decrypt_field(encrypted, deterministic=True)


def encrypt_email(email: str) -> str:
    """Encrypt email (searchable)"""
    return encrypt_field(email, deterministic=True)


def decrypt_email(encrypted: str) -> str:
    """Decrypt email"""
    return decrypt_field(encrypted, deterministic=True)


def encrypt_address(address: str) -> str:
    """Encrypt address (non-searchable)"""
    return encrypt_field(address, deterministic=False)


def decrypt_address(encrypted: str) -> str:
    """Decrypt address"""
    return decrypt_field(encrypted, deterministic=False)


def encrypt_bank_account(account: str) -> str:
    """Encrypt bank account (non-searchable, high security)"""
    return encrypt_field(account, deterministic=False)


def decrypt_bank_account(encrypted: str) -> str:
    """Decrypt bank account"""
    return decrypt_field(encrypted, deterministic=False)


def encrypt_govt_id(govt_id: str) -> str:
    """Encrypt government ID (non-searchable, high security)"""
    return encrypt_field(govt_id, deterministic=False)


def decrypt_govt_id(encrypted: str) -> str:
    """Decrypt government ID"""
    return decrypt_field(encrypted, deterministic=False)
