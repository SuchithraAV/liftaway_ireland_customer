"""
Chat Message Encryption Utility

Uses AES-256-GCM encryption with SHA-256 key derivation.
Messages are encrypted before storing in the database and decrypted when retrieved.
"""

import hashlib
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Shared secret for key derivation (in production, use environment variable)
ENCRYPTION_SECRET = os.getenv("CHAT_ENCRYPTION_SECRET", "RoadAssistance2024SecretKey!@#$%")


def derive_key(issue_id: str) -> bytes:
    """
    Derive a 256-bit AES key from the issue ID using SHA-256.
    Both customer and driver will derive the same key for the same issue.
    
    Args:
        issue_id: The UUID of the issue as a string
        
    Returns:
        32-byte key suitable for AES-256
    """
    # Combine issue ID with shared secret
    key_material = f"{issue_id}{ENCRYPTION_SECRET}"
    
    # Use SHA-256 to derive a 32-byte (256-bit) key
    key = hashlib.sha256(key_material.encode('utf-8')).digest()
    
    return key


def encrypt_message(plaintext: str, issue_id: str) -> str:
    """
    Encrypt a message using AES-256-GCM.
    
    Args:
        plaintext: The message to encrypt
        issue_id: The issue ID used for key derivation
        
    Returns:
        Base64 encoded string containing: nonce (12 bytes) + ciphertext + tag (16 bytes)
    """
    try:
        # Derive key from issue ID
        key = derive_key(issue_id)
        
        # Create AES-GCM cipher
        aesgcm = AESGCM(key)
        
        # Generate random 12-byte nonce
        nonce = os.urandom(12)
        
        # Encrypt the message
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
        
        # Combine nonce + ciphertext and encode as base64
        encrypted_data = nonce + ciphertext
        encrypted_base64 = base64.b64encode(encrypted_data).decode('utf-8')
        
        return encrypted_base64
        
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        raise ValueError(f"Failed to encrypt message: {e}")


def decrypt_message(encrypted_base64: str, issue_id: str) -> str:
    """
    Decrypt a message using AES-256-GCM.
    
    Args:
        encrypted_base64: Base64 encoded encrypted message (nonce + ciphertext + tag)
        issue_id: The issue ID used for key derivation
        
    Returns:
        Decrypted plaintext message
    """
    try:
        # Derive key from issue ID
        key = derive_key(issue_id)
        
        # Decode base64
        encrypted_data = base64.b64decode(encrypted_base64)
        
        # Extract nonce (first 12 bytes) and ciphertext
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        
        # Create AES-GCM cipher and decrypt
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        
        return plaintext.decode('utf-8')
        
    except Exception as e:
        logger.error(f"Decryption error: {e}")
        # Return original text if decryption fails (might be unencrypted legacy message)
        return encrypted_base64


def is_encrypted(text: str) -> bool:
    """
    Check if a message appears to be encrypted (valid base64 with minimum length).
    
    Args:
        text: The text to check
        
    Returns:
        True if the text appears to be encrypted
    """
    if not text or len(text) < 20:
        return False
    
    try:
        decoded = base64.b64decode(text)
        # Encrypted messages should be at least 12 bytes (nonce) + 16 bytes (tag) + 1 byte (min data)
        return len(decoded) >= 29
    except Exception:
        return False
