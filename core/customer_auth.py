from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_db
from core.models import Customer
from core.utils.security import get_password_hash, create_access_token, create_refresh_token
from core.utils.twilio_service import twilio_service
from core.utils.field_encryption import encrypt_phone, decrypt_phone, encrypt_email, decrypt_email, encrypt_field, decrypt_field, encrypt_address, decrypt_address
from datetime import datetime, timedelta, timezone
import logging
import re
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from uuid import UUID

router = APIRouter()
logger = logging.getLogger(__name__)

class CustomerRegistration(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone_number: str = Field(..., description="Phone number in E.164 format")
    address: str = Field(..., min_length=10, max_length=500)
    password: str = Field(..., min_length=6)
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        if not re.match(r'^\+[1-9]\d{1,14}$', v):
            raise ValueError('Phone number must be in E.164 format (e.g., +919059658735)')
        return v

class LoginRequest(BaseModel):
    phone_number: str = Field(..., description="Phone number in E.164 format")
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        if not re.match(r'^\+[1-9]\d{1,14}$', v):
            raise ValueError('Phone number must be in E.164 format (e.g., +919059658735)')
        return v

class OTPVerificationRequest(BaseModel):
    phone_number: str = Field(..., description="Phone number in E.164 format")
    otp_code: str = Field(..., min_length=4, max_length=10, description="OTP code")
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        if not re.match(r'^\+[1-9]\d{1,14}$', v):
            raise ValueError('Phone number must be in E.164 format (e.g., +919059658735)')
        return v
    
    @validator('otp_code')
    def validate_otp_code(cls, v):
        if not v.isdigit():
            raise ValueError('OTP code must contain only digits')
        return v

class RegisterOTPVerification(BaseModel):
    phone_number: str = Field(..., description="Phone number in E.164 format")
    otp_code: str = Field(..., min_length=4, max_length=10, description="OTP code")
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        if not re.match(r'^\+[1-9]\d{1,14}$', v):
            raise ValueError('Phone number must be in E.164 format (e.g., +919059658735)')
        return v
    
    @validator('otp_code')
    def validate_otp_code(cls, v):
        if not v.isdigit():
            raise ValueError('OTP code must contain only digits')
        return v

class LoginOTPVerification(BaseModel):
    phone_number: str = Field(..., description="Phone number in E.164 format")
    otp_code: str = Field(..., min_length=4, max_length=10, description="OTP code")
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        if not re.match(r'^\+[1-9]\d{1,14}$', v):
            raise ValueError('Phone number must be in E.164 format (e.g., +919059658735)')
        return v
    
    @validator('otp_code')
    def validate_otp_code(cls, v):
        if not v.isdigit():
            raise ValueError('OTP code must contain only digits')
        return v

class ResendOTP(BaseModel):
    phone_number: str = Field(..., description="Phone number in E.164 format")
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        if not re.match(r'^\+[1-9]\d{1,14}$', v):
            raise ValueError('Phone number must be in E.164 format (e.g., +919059658735)')
        return v

class EmailPasswordLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)

@router.post("/api/auth/register/customer/")
async def register_customer(customer_data: CustomerRegistration, db: AsyncSession = Depends(get_db)):
    """Register new customer and send OTP via Twilio Verify"""
    encrypted_phone = encrypt_phone(customer_data.phone_number)
    encrypted_email = encrypt_email(customer_data.email)
    
    result = await db.execute(select(Customer).where(Customer.phone_number == encrypted_phone))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone number already registered")
    
    result = await db.execute(select(Customer).where(Customer.email == encrypted_email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    
    hashed_password = get_password_hash(customer_data.password)
    
    customer = Customer(
        full_name=encrypt_field(customer_data.full_name),
        email=encrypted_email,
        phone_number=encrypted_phone,
        address=encrypt_address(customer_data.address),
        password=hashed_password,
        is_verified=False
    )
    
    try:
        db.add(customer)
        logger.info(f"Added customer to session: {customer.phone_number}")
        
        await db.flush()  # Flush to get the ID
        logger.info(f"Flushed customer - ID: {customer.id}")
        
        await db.commit()
        logger.info(f"Committed customer to database: {customer.id}")
        
        await db.refresh(customer)
        logger.info(f"Refreshed customer from database: {customer.id}")
    except Exception as e:
        logger.error(f"Database error during registration: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")
    
    # Send OTP via Twilio Verify
    otp_sent = False
    otp_error = None
    if twilio_service:
        try:
            otp_result = twilio_service.send_otp(customer_data.phone_number)
            if otp_result["success"]:
                otp_sent = True
                logger.info(f"✅ OTP sent successfully to {customer_data.phone_number}")
            else:
                otp_error = otp_result.get('error')
                error_code = otp_result.get('error_code')
                logger.error(f"❌ OTP send failed: {otp_error} (Code: {error_code})")
                
                # Handle specific Twilio errors
                if error_code == 20429:
                    otp_error = "Rate limit exceeded. Please try again in 10 minutes or use a different phone number."
                elif error_code == 60410:
                    otp_error = "Phone number not verified. For trial accounts, verify your number at https://console.twilio.com"
        except Exception as e:
            otp_error = str(e)
            logger.error(f"❌ Error sending OTP: {otp_error}")
    else:
        otp_error = "SMS service not configured"
        logger.warning("⚠️ Twilio service not initialized")
    
    return {
        "success": True,
        "message": "Customer registered successfully. OTP sent to mobile number." if otp_sent else f"Customer registered but OTP failed: {otp_error}",
        "otp_sent": otp_sent,
        "otp_error": otp_error if not otp_sent else None,
        "user_id": str(customer.id),
        "phone_number": customer_data.phone_number,
        "user_data": {
            "id": str(customer.id),
            "full_name": customer_data.full_name,
            "email": customer_data.email,
            "phone_number": customer_data.phone_number,
            "address": customer_data.address,
            "is_verified": False,
            "is_active": customer.is_active
        }
    }

@router.post("/api/auth/login/customer/")
async def customer_login(login_data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Customer login - sends OTP via Twilio Verify"""
    encrypted_phone = encrypt_phone(login_data.phone_number)
    result = await db.execute(select(Customer).where(Customer.phone_number == encrypted_phone))
    customer = result.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found with this phone number")
    
    # Send OTP via Twilio Verify (non-blocking)
    otp_sent = False
    try:
        if twilio_service:
            otp_result = twilio_service.send_otp(login_data.phone_number)
            if otp_result["success"]:
                otp_sent = True
            else:
                logger.warning(f"OTP send failed: {otp_result.get('error')}")
        else:
            logger.warning("Twilio service not initialized")
    except Exception as e:
        logger.error(f"Error sending OTP: {str(e)}")
    
    return {
        "success": True,
        "message": "OTP sent to mobile number for login" if otp_sent else "OTP service unavailable - use password login",
        "otp_sent": otp_sent,
        "phone_number": login_data.phone_number
    }

@router.post("/api/auth/login/customer/email/")
async def customer_email_login(login_data: EmailPasswordLogin, db: AsyncSession = Depends(get_db)):
    """Customer login with email and password"""
    from core.utils.security import verify_password
    
    encrypted_email = encrypt_email(login_data.email)
    result = await db.execute(select(Customer).where(Customer.email == encrypted_email))
    customer = result.scalar_one_or_none()
    
    if not customer or not verify_password(login_data.password, customer.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    
    if not customer.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")
    
    # Generate tokens
    access_token = create_access_token(data={"sub": str(customer.id), "role": "customer"})
    refresh_token = create_refresh_token(data={"sub": str(customer.id), "role": "customer"})
    
    return {
        "success": True,
        "message": "Login successful",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_data": {
            "id": str(customer.id),
            "full_name": decrypt_field(customer.full_name),
            "email": decrypt_email(customer.email),
            "phone_number": decrypt_phone(customer.phone_number),
            "address": decrypt_address(customer.address),
            "is_verified": customer.is_verified,
            "is_active": customer.is_active
        }
    }

@router.post("/api/auth/verify-register-otp/")
async def verify_register_otp(otp_data: RegisterOTPVerification, db: AsyncSession = Depends(get_db)):
    """Verify registration OTP and return access tokens for immediate dashboard access"""
    encrypted_phone = encrypt_phone(otp_data.phone_number)
    result = await db.execute(select(Customer).where(Customer.phone_number == encrypted_phone))
    customer = result.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found with this phone number")
    
    # Verify OTP via Twilio Verify
    if not twilio_service:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="SMS service not configured")
    
    verify_result = twilio_service.verify_otp(otp_data.phone_number, otp_data.otp_code)
    
    if not verify_result["success"]:
        error_code = verify_result.get("error_code")
        if error_code == 60202:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many verification attempts. Please request a new OTP.")
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")
    
    # Mark as verified
    customer.is_verified = True
    await db.commit()
    await db.refresh(customer)
    
    # Generate tokens for immediate dashboard access
    access_token = create_access_token(data={"sub": str(customer.id), "role": "customer"})
    refresh_token = create_refresh_token(data={"sub": str(customer.id), "role": "customer"})
    
    return {
        "success": True,
        "message": "Registration completed successfully. Welcome to your dashboard!",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_data": {
            "id": str(customer.id),
            "full_name": decrypt_field(customer.full_name),
            "email": decrypt_email(customer.email),
            "phone_number": decrypt_phone(customer.phone_number),
            "address": decrypt_address(customer.address),
            "is_verified": customer.is_verified,
            "is_active": customer.is_active
        }
    }

@router.post("/api/auth/verify-login-otp/")
async def verify_login_otp(otp_data: LoginOTPVerification, db: AsyncSession = Depends(get_db)):
    """Verify login OTP using Twilio Verify and return tokens"""
    encrypted_phone = encrypt_phone(otp_data.phone_number)
    result = await db.execute(select(Customer).where(Customer.phone_number == encrypted_phone))
    customer = result.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found with this phone number")
    
    # Verify OTP via Twilio Verify
    verify_result = twilio_service.verify_otp(otp_data.phone_number, otp_data.otp_code)
    
    if not verify_result["success"]:
        error_code = verify_result.get("error_code")
        if error_code == 60202:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many verification attempts. Please request a new OTP.")
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")
    
    # Generate tokens
    access_token = create_access_token(data={"sub": str(customer.id), "role": "customer"})
    refresh_token = create_refresh_token(data={"sub": str(customer.id), "role": "customer"})
    
    return {
        "success": True,
        "message": "Login successful",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user_data": {
            "id": str(customer.id),
            "full_name": decrypt_field(customer.full_name),
            "email": decrypt_email(customer.email),
            "phone_number": decrypt_phone(customer.phone_number),
            "address": decrypt_address(customer.address),
            "is_verified": customer.is_verified,
            "is_active": customer.is_active
        }
    }

@router.post("/api/auth/resend-otp/")
async def resend_otp(resend_data: ResendOTP, db: AsyncSession = Depends(get_db)):
    """Resend OTP via Twilio Verify"""
    encrypted_phone = encrypt_phone(resend_data.phone_number)
    result = await db.execute(select(Customer).where(Customer.phone_number == encrypted_phone))
    customer = result.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found with this phone number")
    
    # Send OTP via Twilio Verify
    otp_result = twilio_service.send_otp(resend_data.phone_number)
    
    if not otp_result["success"]:
        error_code = otp_result.get("error_code")
        if error_code == 60200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone number format")
        elif error_code == 60203:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many OTP requests. Please try again later.")
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send OTP. Please try again.")
    
    return {
        "success": True,
        "message": "New OTP sent to mobile number",
        "phone_number": resend_data.phone_number
    }
