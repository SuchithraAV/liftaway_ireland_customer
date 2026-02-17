"""
FIXED: Envelope Encryption with AWS KMS

This implementation uses the envelope encryption pattern:
1. Generate a unique data encryption key (DEK) for each record
2. Encrypt data with DEK
3. Encrypt DEK with KMS master key
4. Store encrypted DEK alongside encrypted data

Format: base64(encrypted_dek + encrypted_data)
"""

import boto3
import base64
import os
import json
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
import logging

logger = logging.getLogger(__name__)

# Configuration
USE_KMS = os.getenv("USE_KMS", "false").lower() == "true"
KMS_KEY_ID = os.getenv("KMS_KEY_ID")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Fallback to local keys for development
LOCAL_FIELD_KEY = os.getenv("FIELD_ENCRYPTION_KEY")
LOCAL_DETERMINISTIC_KEY = os.getenv("DETERMINISTIC_ENCRYPTION_KEY")


class EnvelopeEncryption:
    """Proper envelope encryption with KMS"""
    
    def __init__(self):
        if USE_KMS:
            self.kms_client = boto3.client('kms', region_name=AWS_REGION)
            logger.info(f"✅ KMS envelope encryption enabled: {KMS_KEY_ID}")
        else:
            self.kms_client = None
            logger.info("⚠️ Using local encryption (development mode)")
    
    def encrypt_field(self, plaintext: str) -> str:
        """
        Encrypt field using envelope encryption.
        Returns: base64(encrypted_dek_length + encrypted_dek + nonce + ciphertext)
        """
        if not plaintext:
            return plaintext
        
        try:
            if USE_KMS and self.kms_client:
                # Generate data encryption key
                response = self.kms_client.generate_data_key(
                    KeyId=KMS_KEY_ID,
                    KeySpec='AES_256'
                )
                
                plaintext_dek = response['Plaintext']  # 32 bytes
                encrypted_dek = response['CiphertextBlob']  # Encrypted by KMS
                
                # Encrypt data with DEK using AES-GCM
                aesgcm = AESGCM(plaintext_dek)
                nonce = os.urandom(12)
                ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
                
                # Package: [dek_length(2 bytes)][encrypted_dek][nonce(12 bytes)][ciphertext]
                dek_length = len(encrypted_dek).to_bytes(2, 'big')
                envelope = dek_length + encrypted_dek + nonce + ciphertext
                
                return base64.b64encode(envelope).decode('utf-8')
            else:
                # Fallback to local Fernet encryption
                if not LOCAL_FIELD_KEY:
                    raise ValueError("FIELD_ENCRYPTION_KEY not set")
                from cryptography.fernet import Fernet
                f = Fernet(LOCAL_FIELD_KEY.encode())
                return f.encrypt(plaintext.encode()).decode()
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise
    
    def decrypt_field(self, ciphertext: str) -> str:
        """
        Decrypt field using envelope encryption.
        Extracts encrypted DEK, decrypts it with KMS, then decrypts data.
        """
        if not ciphertext:
            return ciphertext
        
        try:
            if USE_KMS and self.kms_client:
                envelope = base64.b64decode(ciphertext.encode('utf-8'))
                
                # Unpack envelope
                dek_length = int.from_bytes(envelope[:2], 'big')
                encrypted_dek = envelope[2:2+dek_length]
                nonce = envelope[2+dek_length:2+dek_length+12]
                encrypted_data = envelope[2+dek_length+12:]
                
                # Decrypt DEK using KMS
                response = self.kms_client.decrypt(
                    CiphertextBlob=encrypted_dek
                )
                plaintext_dek = response['Plaintext']
                
                # Decrypt data using DEK
                aesgcm = AESGCM(plaintext_dek)
                plaintext = aesgcm.decrypt(nonce, encrypted_data, None)
                
                return plaintext.decode('utf-8')
            else:
                # Fallback to local Fernet decryption
                if not LOCAL_FIELD_KEY:
                    raise ValueError("FIELD_ENCRYPTION_KEY not set")
                from cryptography.fernet import Fernet
                f = Fernet(LOCAL_FIELD_KEY.encode())
                return f.decrypt(ciphertext.encode()).decode()
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise
    
    def encrypt_searchable(self, plaintext: str) -> dict:
        """
        For searchable fields, return both encrypted value and search hash.
        
        Returns:
            {
                "encrypted": "base64_encrypted_value",
                "search_hash": "sha256_hash_for_lookup"
            }
        """
        if not plaintext:
            return {"encrypted": plaintext, "search_hash": ""}
        
        import hashlib
        
        # Encrypt the value
        encrypted = self.encrypt_field(plaintext)
        
        # Create deterministic hash for searching
        if USE_KMS and self.kms_client:
            # Use KMS to generate consistent hash key
            hash_key = KMS_KEY_ID.encode()
        else:
            hash_key = LOCAL_DETERMINISTIC_KEY.encode() if LOCAL_DETERMINISTIC_KEY else b"default_hash_key"
        
        search_hash = hashlib.sha256(hash_key + plaintext.encode()).hexdigest()
        
        return {
            "encrypted": encrypted,
            "search_hash": search_hash
        }


# Global instance
envelope_encryption = EnvelopeEncryption()


# Convenience functions
def encrypt_field(plaintext: str) -> str:
    """Encrypt sensitive field"""
    return envelope_encryption.encrypt_field(plaintext)


def decrypt_field(ciphertext: str) -> str:
    """Decrypt sensitive field"""
    return envelope_encryption.decrypt_field(ciphertext)


def encrypt_searchable(plaintext: str) -> dict:
    """
    Encrypt searchable field (email, phone).
    Returns dict with 'encrypted' and 'search_hash' keys.
    """
    return envelope_encryption.encrypt_searchable(plaintext)


def decrypt_searchable(ciphertext: str) -> str:
    """Decrypt searchable field"""
    return envelope_encryption.decrypt_field(ciphertext)
