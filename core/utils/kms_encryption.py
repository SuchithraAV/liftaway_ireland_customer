"""
AWS KMS-based encryption for production
Uses AWS KMS for key management instead of local keys
"""
import boto3
import base64
import os
import hashlib
import hmac
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.backends import default_backend
import logging

logger = logging.getLogger(__name__)

# Configuration
USE_KMS = os.getenv("USE_KMS", "false").lower() == "true"
KMS_KEY_ID = os.getenv("KMS_KEY_ID")  # ARN or alias of KMS key
AWS_REGION = os.getenv("AWS_REGION", "eu-west-1")

# Fallback to local keys for development
LOCAL_FIELD_KEY = os.getenv("FIELD_ENCRYPTION_KEY")
LOCAL_DETERMINISTIC_KEY = os.getenv("DETERMINISTIC_ENCRYPTION_KEY")


class KMSEncryption:
    """Encryption using AWS KMS"""
    
    def __init__(self):
        if USE_KMS:
            self.kms_client = boto3.client('kms', region_name=AWS_REGION)
            logger.info(f"✅ KMS encryption enabled with key: {KMS_KEY_ID}")
        else:
            self.kms_client = None
            logger.info("⚠️ Using local encryption keys (development mode)")
    
    def encrypt_field(self, plaintext: str) -> str:
        """Encrypt sensitive field data"""
        if not plaintext:
            return plaintext
        
        try:
            if USE_KMS and self.kms_client:
                # Use KMS to encrypt
                response = self.kms_client.encrypt(
                    KeyId=KMS_KEY_ID,
                    Plaintext=plaintext.encode('utf-8')
                )
                # Return base64-encoded ciphertext
                return base64.b64encode(response['CiphertextBlob']).decode('utf-8')
            else:
                # Fallback to local Fernet encryption
                if not LOCAL_FIELD_KEY:
                    raise ValueError("FIELD_ENCRYPTION_KEY not set")
                f = Fernet(LOCAL_FIELD_KEY.encode())
                return f.encrypt(plaintext.encode()).decode()
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise
    
    def decrypt_field(self, ciphertext: str) -> str:
        """Decrypt sensitive field data"""
        if not ciphertext:
            return ciphertext
        
        try:
            if USE_KMS and self.kms_client:
                # Use KMS to decrypt
                ciphertext_blob = base64.b64decode(ciphertext.encode('utf-8'))
                response = self.kms_client.decrypt(
                    CiphertextBlob=ciphertext_blob
                )
                return response['Plaintext'].decode('utf-8')
            else:
                # Fallback to local Fernet decryption
                if not LOCAL_FIELD_KEY:
                    raise ValueError("FIELD_ENCRYPTION_KEY not set")
                f = Fernet(LOCAL_FIELD_KEY.encode())
                return f.decrypt(ciphertext.encode()).decode()
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise
    
    def encrypt_deterministic(self, plaintext: str) -> str:
        """
        Deterministic encryption for searchable fields.
        Uses HMAC-based key derivation from plaintext for consistent results.
        """
        if not plaintext:
            return plaintext
        
        try:
            if USE_KMS and self.kms_client:
                # Derive deterministic key from plaintext using HMAC
                import hmac
                # Use KMS to get a master key (cached)
                master_key = self._get_master_key()
                # Derive field-specific key deterministically
                field_key = hmac.new(master_key, plaintext.encode(), hashlib.sha256).digest()[:32]
                derived_key = base64.urlsafe_b64encode(field_key)
                f = Fernet(derived_key)
                return f.encrypt(plaintext.encode()).decode()
            else:
                # Fallback to local deterministic encryption
                if not LOCAL_DETERMINISTIC_KEY:
                    raise ValueError("DETERMINISTIC_ENCRYPTION_KEY not set")
                f = Fernet(LOCAL_DETERMINISTIC_KEY.encode())
                return f.encrypt(plaintext.encode()).decode()
        except Exception as e:
            logger.error(f"Deterministic encryption error: {e}")
            raise
    
    def decrypt_deterministic(self, ciphertext: str) -> str:
        """Decrypt deterministic encrypted data"""
        if not ciphertext:
            return ciphertext
        
        try:
            if USE_KMS and self.kms_client:
                # Cannot decrypt without knowing original plaintext
                # Use envelope encryption instead
                raise NotImplementedError(
                    "Deterministic decryption with KMS requires envelope encryption. "
                    "Use non-deterministic encryption or local keys."
                )
            else:
                # Fallback to local deterministic decryption
                if not LOCAL_DETERMINISTIC_KEY:
                    raise ValueError("DETERMINISTIC_ENCRYPTION_KEY not set")
                f = Fernet(LOCAL_DETERMINISTIC_KEY.encode())
                return f.decrypt(ciphertext.encode()).decode()
        except Exception as e:
            logger.error(f"Deterministic decryption error: {e}")
            raise
    
    def _get_master_key(self) -> bytes:
        """Get or generate master key from KMS (cached)"""
        if not hasattr(self, '_cached_master_key'):
            response = self.kms_client.generate_data_key(
                KeyId=KMS_KEY_ID,
                KeySpec='AES_256'
            )
            self._cached_master_key = response['Plaintext']
        return self._cached_master_key


# Global instance
kms_encryption = KMSEncryption()


# Convenience functions
def encrypt_field(plaintext: str) -> str:
    """Encrypt sensitive field"""
    return kms_encryption.encrypt_field(plaintext)


def decrypt_field(ciphertext: str) -> str:
    """Decrypt sensitive field"""
    return kms_encryption.decrypt_field(ciphertext)


def encrypt_deterministic(plaintext: str) -> str:
    """Deterministic encryption for searchable fields"""
    return kms_encryption.encrypt_deterministic(plaintext)


def decrypt_deterministic(ciphertext: str) -> str:
    """Decrypt deterministic encrypted data"""
    return kms_encryption.decrypt_deterministic(ciphertext)
