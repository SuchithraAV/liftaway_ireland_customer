"""
Encrypted Field Mixins for SQLAlchemy Models

Provides transparent encryption/decryption for sensitive fields.
Usage: Add properties to existing models without breaking functionality.
"""

from sqlalchemy import Column, String, event
from sqlalchemy.ext.hybrid import hybrid_property
from core.utils.field_encryption import (
    encrypt_field, decrypt_field, 
    encrypt_phone, decrypt_phone,
    encrypt_email, decrypt_email,
    encrypt_address, decrypt_address,
    encrypt_bank_account, decrypt_bank_account,
    encrypt_govt_id, decrypt_govt_id,
    hash_for_lookup, is_encrypted
)
import logging

logger = logging.getLogger(__name__)


def create_encrypted_property(column_name: str, encrypt_func, decrypt_func):
    """
    Factory to create encrypted property for a model field.
    
    Args:
        column_name: Name of the database column (with _encrypted suffix)
        encrypt_func: Function to encrypt value
        decrypt_func: Function to decrypt value
    
    Returns:
        hybrid_property for transparent encryption
    """
    
    def getter(self):
        encrypted_value = getattr(self, column_name, None)
        if not encrypted_value:
            return encrypted_value
        
        # Check if already decrypted (cached)
        cache_key = f"_{column_name}_decrypted"
        if hasattr(self, cache_key):
            return getattr(self, cache_key)
        
        try:
            decrypted = decrypt_func(encrypted_value)
            setattr(self, cache_key, decrypted)
            return decrypted
        except Exception as e:
            logger.error(f"Decryption failed for {column_name}: {e}")
            return encrypted_value
    
    def setter(self, value):
        if not value:
            setattr(self, column_name, value)
            return
        
        # Encrypt and store
        try:
            # Skip encryption if already encrypted
            if is_encrypted(value):
                encrypted = value
            else:
                encrypted = encrypt_func(value)
            
            setattr(self, column_name, encrypted)
            # Cache decrypted value
            setattr(self, f"_{column_name}_decrypted", value)
        except Exception as e:
            logger.error(f"Encryption failed for {column_name}: {e}")
            setattr(self, column_name, value)
    
    return hybrid_property(getter, setter)


# Mixin classes for different entity types

class EncryptedCustomerMixin:
    """Mixin for Customer model with encrypted fields"""
    
    # Store encrypted values in these columns
    phone_number_encrypted = Column(String(500), nullable=True)
    address_encrypted = Column(String(1000), nullable=True)
    
    @hybrid_property
    def phone_number_secure(self):
        if not self.phone_number_encrypted:
            return self.phone_number_encrypted
        try:
            return decrypt_phone(self.phone_number_encrypted)
        except:
            return self.phone_number_encrypted
    
    @phone_number_secure.setter
    def phone_number_secure(self, value):
        if value and not is_encrypted(value):
            self.phone_number_encrypted = encrypt_phone(value)
        else:
            self.phone_number_encrypted = value
    
    @hybrid_property
    def address_secure(self):
        if not self.address_encrypted:
            return self.address_encrypted
        try:
            return decrypt_address(self.address_encrypted)
        except:
            return self.address_encrypted
    
    @address_secure.setter
    def address_secure(self, value):
        if value and not is_encrypted(value):
            self.address_encrypted = encrypt_address(value)
        else:
            self.address_encrypted = value


class EncryptedDriverMixin:
    """Mixin for Driver model with encrypted fields"""
    
    phone_number_encrypted = Column(String(500), nullable=True)
    address_encrypted = Column(String(1000), nullable=True)
    
    @hybrid_property
    def phone_number_secure(self):
        if not self.phone_number_encrypted:
            return self.phone_number_encrypted
        try:
            return decrypt_phone(self.phone_number_encrypted)
        except:
            return self.phone_number_encrypted
    
    @phone_number_secure.setter
    def phone_number_secure(self, value):
        if value and not is_encrypted(value):
            self.phone_number_encrypted = encrypt_phone(value)
        else:
            self.phone_number_encrypted = value
    
    @hybrid_property
    def address_secure(self):
        if not self.address_encrypted:
            return self.address_encrypted
        try:
            return decrypt_address(self.address_encrypted)
        except:
            return self.address_encrypted
    
    @address_secure.setter
    def address_secure(self, value):
        if value and not is_encrypted(value):
            self.address_encrypted = encrypt_address(value)
        else:
            self.address_encrypted = value


class EncryptedBankDetailMixin:
    """Mixin for DriverBankDetail model"""
    
    bank_account_number_encrypted = Column(String(500), nullable=True)
    bank_ifsc_encrypted = Column(String(500), nullable=True)
    account_holder_name_encrypted = Column(String(500), nullable=True)
    upi_id_encrypted = Column(String(500), nullable=True)
    
    @hybrid_property
    def bank_account_number_secure(self):
        if not self.bank_account_number_encrypted:
            return self.bank_account_number_encrypted
        try:
            return decrypt_bank_account(self.bank_account_number_encrypted)
        except:
            return self.bank_account_number_encrypted
    
    @bank_account_number_secure.setter
    def bank_account_number_secure(self, value):
        if value and not is_encrypted(value):
            self.bank_account_number_encrypted = encrypt_bank_account(value)
        else:
            self.bank_account_number_encrypted = value


class EncryptedDocumentMixin:
    """Mixin for DriverDocument model"""
    
    govt_id_number_encrypted = Column(String(500), nullable=True)
    license_number_encrypted = Column(String(500), nullable=True)
    
    @hybrid_property
    def govt_id_number_secure(self):
        if not self.govt_id_number_encrypted:
            return self.govt_id_number_encrypted
        try:
            return decrypt_govt_id(self.govt_id_number_encrypted)
        except:
            return self.govt_id_number_encrypted
    
    @govt_id_number_secure.setter
    def govt_id_number_secure(self, value):
        if value and not is_encrypted(value):
            self.govt_id_number_encrypted = encrypt_govt_id(value)
        else:
            self.govt_id_number_encrypted = value
    
    @hybrid_property
    def license_number_secure(self):
        if not self.license_number_encrypted:
            return self.license_number_encrypted
        try:
            return decrypt_govt_id(self.license_number_encrypted)
        except:
            return self.license_number_encrypted
    
    @license_number_secure.setter
    def license_number_secure(self, value):
        if value and not is_encrypted(value):
            self.license_number_encrypted = encrypt_govt_id(value)
        else:
            self.license_number_encrypted = value
