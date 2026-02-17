from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime, date
from uuid import UUID

# Customer Registration Schema
class CustomerRegistration(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone_number: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$')
    address: str = Field(..., min_length=10, max_length=500)
    password: str = Field(..., min_length=6)

# Driver Registration Schema
class DriverRegistration(BaseModel):
    # Personal Details
    full_name: str = Field(..., min_length=2, max_length=100)
    phone_number: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$')
    email: EmailStr
    date_of_birth: date
    address: str = Field(..., min_length=10, max_length=500)
    password: str = Field(..., min_length=6)
    
    # Identity Verification
    govt_id_type: str = Field(..., pattern=r'^(aadhaar|pan|passport|voter_id|driving_license)$')
    govt_id_number: str = Field(..., min_length=5, max_length=50)
    
    # Professional Details
    years_of_experience: int = Field(..., ge=0, le=50)
    license_number: str = Field(..., min_length=5, max_length=50)
    license_category: str = Field(..., pattern=r'^(LMV|HMV|MCWG|MCWOG|PSV)$')
    license_expiry_date: date
    previous_company: Optional[str] = Field(None, max_length=100)
    
    # Vehicle Details
    vehicle_type: str = Field(..., pattern=r'^(truck|van|auto|e-cart)$')
    vehicle_number_plate: str = Field(..., min_length=5, max_length=20)
    vehicle_model: str = Field(..., min_length=2, max_length=50)
    vehicle_capacity: str = Field(..., min_length=1, max_length=50)
    
    # Service Area Details
    pincodes: str = Field(..., min_length=5)  # Comma separated pincodes
    preferred_shift: str = Field(..., pattern=r'^(morning|evening|full_day|custom)$')
    
    # Bank/Payment Details (UK format)
    bank_account_number: str = Field(..., min_length=8, max_length=30)
    sort_code: str = Field(..., pattern=r'^\d{2}-\d{2}-\d{2}$')  # UK Sort Code format
    account_holder_name: str = Field(..., min_length=2, max_length=100)
    
    @validator('license_expiry_date')
    def validate_license_expiry(cls, v):
        if v <= date.today():
            raise ValueError('License expiry date must be in the future')
        return v
    
    @validator('date_of_birth')
    def validate_age(cls, v):
        today = date.today()
        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
        if age < 18:
            raise ValueError('Driver must be at least 18 years old')
        if age > 70:
            raise ValueError('Driver must be under 70 years old')
        return v

# Admin Registration Schema
class AdminRegistration(BaseModel):
    phone_number: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$')
    password: str = Field(..., min_length=6)

# Login Schema
class LoginRequest(BaseModel):
    phone_number: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$')

# OTP Verification Schema
class OTPVerification(BaseModel):
    phone_number: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$')
    otp_code: str = Field(..., pattern=r'^\d{6}$')
    user_type: str = Field(..., pattern=r'^(customer|driver|admin)$')
    action_type: str = Field(..., pattern=r'^(registration|login)$')

# Resend OTP Schema
class ResendOTP(BaseModel):
    phone_number: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$')
    user_type: str = Field(..., pattern=r'^(customer|driver|admin)$')
    action_type: str = Field(..., pattern=r'^(registration|login)$')

# Response Schemas
class CustomerResponse(BaseModel):
    id: UUID
    full_name: str
    email: str
    phone_number: str
    address: str
    is_active: bool
    is_verified: bool
    date_joined: datetime
    
    class Config:
        from_attributes = True

class DriverResponse(BaseModel):
    id: UUID
    full_name: str
    phone_number: str
    email: str
    date_of_birth: date
    address: str
    govt_id_type: str
    govt_id_number: str
    years_of_experience: int
    license_number: str
    license_category: str
    license_expiry_date: date
    previous_company: Optional[str]
    vehicle_type: str
    vehicle_number_plate: str
    vehicle_model: str
    vehicle_capacity: str
    pincodes: str
    preferred_shift: str
    bank_account_number: str
    sort_code: str
    account_holder_name: str
    is_active: bool
    is_approved: bool
    is_verified: bool
    date_joined: datetime
    
    class Config:
        from_attributes = True

class AdminResponse(BaseModel):
    id: UUID
    phone_number: str
    is_active: bool
    is_verified: bool
    date_joined: datetime
    
    class Config:
        from_attributes = True

class AuthResponse(BaseModel):
    success: bool
    message: str
    user_id: Optional[UUID] = None
    phone_number: Optional[str] = None

class OTPResponse(BaseModel):
    success: bool
    message: str
    phone_number: str

class VerificationResponse(BaseModel):
    success: bool
    message: str
    user_type: str
    action_type: str
    user_data: Optional[dict] = None