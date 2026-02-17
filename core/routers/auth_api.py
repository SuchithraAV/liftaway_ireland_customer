from fastapi import APIRouter, HTTPException, Depends, Form, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_db
from core.models import Driver, Admin, DriverDocument, DriverBankDetail, DriverVehicle
from core.utils.security import get_password_hash, create_access_token, create_refresh_token
from core.utils.s3_upload import upload_file_to_s3, get_full_url
from core.utils.twilio_service import twilio_service
from core.utils.field_encryption import encrypt_phone, encrypt_email, encrypt_field, encrypt_bank_account, encrypt_govt_id
from core.dependencies import get_current_driver_any_status
from core.services.stripe_connect import stripe_connect_service
from pydantic import BaseModel, Field
from datetime import datetime, timedelta, timezone
import secrets
import string
import logging
import uuid
from typing import Optional, List

router = APIRouter()
logger = logging.getLogger(__name__)

# Schemas
class PersonalDetails(BaseModel):
    full_name: str
    phone_number: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$')
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    dob: str = Field(..., description="Date of birth in YYYY-MM-DD format", examples=["1990-05-15"])
    address: str

class IdentityVerification(BaseModel):
    govt_id_type: str
    govt_id_number: str
    govt_id_photo_url: str
    selfie_photo_url: str

class ProfessionalDetails(BaseModel):
    years_of_experience: int
    license_number: str
    license_category: str
    license_expiry_date: str = Field(..., description="License expiry date in YYYY-MM-DD format", examples=["2030-12-31"])


class VehicleDetails(BaseModel):
    vehicle_type: str
    vehicle_number: str
    vehicle_model: str
    vehicle_capacity: str
    rc_book_photo: str
    pollution_certificate_photo: str

class ServiceAreaDetails(BaseModel):
    pincodes: str
    preferred_shift: str

class BankDetails(BaseModel):
    account_number: str
    sort_code: str
    holder_name: str
    upi_id: str

class DocumentUpload(BaseModel):
    driver_photo: str
    license_front: str
    license_back: str
    vehicle_photo: str

class DriverRegisterRequest(BaseModel):
    personal_details: PersonalDetails
    identity_verification: IdentityVerification
    professional_details: ProfessionalDetails
    vehicle_details: VehicleDetails
    service_area_details: ServiceAreaDetails
    bank_details: BankDetails
    document_upload: DocumentUpload

class AdminRegisterRequest(BaseModel):
    phone_number: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$')
    password: str = Field(..., min_length=6)

class VerifyOTPRequest(BaseModel):
    phone_number: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$')
    otp: str = Field(..., pattern=r'^\d{6}$')

class LoginRequest(BaseModel):
    phone_number: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$')

class ResendOTPRequest(BaseModel):
    phone_number: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$')

def generate_otp() -> str:
    """Generate 6-digit OTP"""
    return ''.join(secrets.choice(string.digits) for _ in range(6))

async def send_sms_otp(phone_number: str, otp_code: str) -> bool:
    """Send SMS OTP via Twilio - DEPRECATED: Use twilio_service directly"""
    if twilio_service:
        result = twilio_service.send_otp(phone_number)
        return result["success"]
    logger.warning(f"Twilio not configured - OTP {otp_code} for {phone_number} not sent")
    return False

# Driver Registration with File Upload
@router.post("/api/auth/register/driver/upload")
async def register_driver_with_upload(
    # Personal Details
    full_name: Optional[str] = Form(None),
    phone_number: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    dob: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    
    # Identity Verification
    govt_id_type: Optional[str] = Form(None),
    govt_id_number: Optional[str] = Form(None),
    
    # Professional Details
    years_of_experience: Optional[int] = Form(None),
    license_number: Optional[str] = Form(None),
    license_category: Optional[str] = Form(None),
    license_expiry_date: Optional[str] = Form(None),

    
    # Vehicle Details
    vehicle_type: Optional[str] = Form(None),
    vehicle_number: Optional[str] = Form(None),
    vehicle_model: Optional[str] = Form(None),
    vehicle_capacity: Optional[str] = Form(None),
    
    # Service Area
    pincodes: Optional[str] = Form(None),
    preferred_shift: Optional[str] = Form(None),
    
    # Bank Details
    account_number: Optional[str] = Form(None),
    sort_code: Optional[str] = Form(None),
    holder_name: Optional[str] = Form(None),
    upi_id: Optional[str] = Form(None),
    
    # Files
    driver_photo: Optional[UploadFile] = File(None),
    license_front: Optional[UploadFile] = File(None),
    license_back: Optional[UploadFile] = File(None),
    govt_id_photo: Optional[UploadFile] = File(None),
    selfie_photo: Optional[UploadFile] = File(None),
    vehicle_photo: Optional[UploadFile] = File(None),
    rc_book_photo: Optional[UploadFile] = File(None),
    pollution_certificate_photo: Optional[UploadFile] = File(None),
    
    db: AsyncSession = Depends(get_db)
):
    """Register driver with file uploads (multipart/form-data)"""
    try:
        # Check if phone number exists
        if phone_number:
            encrypted_phone = encrypt_phone(phone_number)
            result = await db.execute(select(Driver).where(Driver.phone_number == encrypted_phone))
            if result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Phone number already registered")
        
        # Check if email exists
        if email:
            encrypted_email = encrypt_email(email)
            result = await db.execute(select(Driver).where(Driver.email == encrypted_email))
            if result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Email already registered")
            
        # Generate driver ID
        driver_id = uuid.uuid4()
            
        # Upload files to S3
        driver_photo_path = await upload_file_to_s3(driver_photo, str(driver_id), "driver_photo") if driver_photo else None
        license_front_path = await upload_file_to_s3(license_front, str(driver_id), "license_front") if license_front else None
        license_back_path = await upload_file_to_s3(license_back, str(driver_id), "license_back") if license_back else None
        govt_id_photo_path = await upload_file_to_s3(govt_id_photo, str(driver_id), "govt_id_photo") if govt_id_photo else None
        selfie_photo_path = await upload_file_to_s3(selfie_photo, str(driver_id), "selfie_photo") if selfie_photo else None
        vehicle_photo_path = await upload_file_to_s3(vehicle_photo, str(driver_id), "vehicle_photo") if vehicle_photo else None
        rc_book_photo_path = await upload_file_to_s3(rc_book_photo, str(driver_id), "rc_book_photo") if rc_book_photo else None
        pollution_cert_path = await upload_file_to_s3(pollution_certificate_photo, str(driver_id), "pollution_certificate") if pollution_certificate_photo else None
        
        # Generate OTP and expiry
        otp = generate_otp()
        expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        # Parse dates
        dob_date = None
        license_expiry_date_obj = None
        try:
            if dob:
                dob_date = datetime.strptime(dob, "%Y-%m-%d").date()
            if license_expiry_date:
                license_expiry_date_obj = datetime.strptime(license_expiry_date, "%Y-%m-%d").date()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid date format. Use YYYY-MM-DD. Error: {str(e)}")
            
        # Create driver
        driver = Driver(
            id=driver_id,
            full_name=encrypt_field(full_name) if full_name else None,
            phone_number=encrypt_phone(phone_number) if phone_number else None,
            email=encrypt_email(email) if email else None,
            dob=dob_date,
            address=encrypt_field(address) if address else None,
            password=get_password_hash("temp_password"),
            years_experience=years_of_experience,

            service_pincodes=pincodes,
            preferred_shift=preferred_shift,
            phone_otp=otp,
            otp_expires_at=expiry,
            is_verified="pending"
        )
        
        db.add(driver)
        await db.flush()
        
        # Create related records
        doc = DriverDocument(
            driver_id=driver.id,
            govt_id_type=govt_id_type,
            govt_id_number=encrypt_govt_id(govt_id_number) if govt_id_number else None,
            id_photo_url=get_full_url(govt_id_photo_path) if govt_id_photo_path else None,
            selfie_photo_url=get_full_url(selfie_photo_path) if selfie_photo_path else None,
            license_number=encrypt_field(license_number) if license_number else None,
            license_category=license_category,
            license_expiry_date=license_expiry_date_obj,
            license_front_url=get_full_url(license_front_path) if license_front_path else None,
            license_back_url=get_full_url(license_back_path) if license_back_path else None,
            driver_photo_url=get_full_url(driver_photo_path) if driver_photo_path else None
        )

        bank = DriverBankDetail(
            driver_id=driver.id,
            bank_account_number=encrypt_bank_account(account_number) if account_number else None,
            bank_ifsc=encrypt_field(sort_code) if sort_code else None,
            account_holder_name=encrypt_field(holder_name) if holder_name else None,
            upi_id=encrypt_field(upi_id) if upi_id else None
        )

        vehicle = DriverVehicle(
            driver_id=driver.id,
            vehicle_type=vehicle_type,
            vehicle_number_plate=encrypt_field(vehicle_number) if vehicle_number else None,
            vehicle_model=vehicle_model,
            vehicle_capacity=vehicle_capacity,
            vehicle_photo_url=get_full_url(vehicle_photo_path) if vehicle_photo_path else None,
            rc_book_pic_url=get_full_url(rc_book_photo_path) if rc_book_photo_path else None,
            pollution_cert_pic_url=get_full_url(pollution_cert_path) if pollution_cert_path else None
        )
        
        db.add_all([doc, bank, vehicle])
        await db.commit()
        await db.refresh(driver)
        
        # Create Stripe Connect Account
        try:
            stripe_resp = stripe_connect_service.create_custom_account(
                driver=driver,
                bank_detail=bank,
                document=doc,
                country="IE",
                ip_address="127.0.0.1",
                raise_on_error=True
            )

            if not stripe_resp.get("stripe_account_id"):
                raise Exception("Stripe did not return account ID")

            driver.stripe_account_id = stripe_resp["stripe_account_id"]
            driver.stripe_payouts_enabled = bool(stripe_resp.get("payouts_enabled", False))

            reqs = stripe_resp.get("requirements", {}) or {}
            driver.stripe_requirements_due = bool(reqs.get("currently_due") or reqs.get("errors"))

            driver.stripe_verification_status = (
                "verified" if driver.stripe_payouts_enabled else "pending"
            )

            await db.commit()
            await db.refresh(driver)

            logger.info(f"Stripe account created for driver: {driver.stripe_account_id}")

        except Exception as e:
            logger.exception(f"Stripe Account Creation Failed: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Stripe account creation failed: {str(e)}"
            )

        
        # Send OTP
        await send_sms_otp(phone_number, otp)
        
        return {
            "success": True,
            "message": "Driver registered successfully. OTP sent to phone number.",
            "driver_id": str(driver.id),
            "stripe_account_id": driver.stripe_account_id,
            "phone_number": phone_number,
            "is_verified": False,
            "uploaded_files": {
                "driver_photo": get_full_url(driver_photo_path) if driver_photo_path else None,
                "license_front": get_full_url(license_front_path) if license_front_path else None,
                "license_back": get_full_url(license_back_path) if license_back_path else None,
                "govt_id_photo": get_full_url(govt_id_photo_path) if govt_id_photo_path else None,
                "selfie_photo": get_full_url(selfie_photo_path) if selfie_photo_path else None,
                "vehicle_photo": get_full_url(vehicle_photo_path) if vehicle_photo_path else None,
                "rc_book_photo": get_full_url(rc_book_photo_path) if rc_book_photo_path else None,
                "pollution_certificate": get_full_url(pollution_cert_path) if pollution_cert_path else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Driver registration with upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

# Driver Registration
@router.post("/api/auth/register/driver")
async def register_driver(
    request: DriverRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Register driver with complete details"""
    try:
        pd = request.personal_details
        
        # Check if phone number exists
        encrypted_phone = encrypt_phone(pd.phone_number)
        result = await db.execute(select(Driver).where(Driver.phone_number == encrypted_phone))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Phone number already registered")
        
        # Check if email exists
        encrypted_email = encrypt_email(pd.email)
        result = await db.execute(select(Driver).where(Driver.email == encrypted_email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Generate OTP and expiry
        otp = generate_otp()
        expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        # Parse dates - handle both string and already-parsed date objects
        try:
            if isinstance(pd.dob, str):
                dob = datetime.strptime(pd.dob, "%Y-%m-%d").date()
            else:
                dob = pd.dob
            
            if isinstance(request.professional_details.license_expiry_date, str):
                license_expiry = datetime.strptime(request.professional_details.license_expiry_date, "%Y-%m-%d").date()
            else:
                license_expiry = request.professional_details.license_expiry_date
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid date format. Use YYYY-MM-DD. Error: {str(e)}")
        
        # Create driver (personal + auth fields only). Other details will be stored
        # in separate tables: driver_documents, driver_bank_details, driver_vehicle.
        driver = Driver(
            full_name=encrypt_field(pd.full_name),
            phone_number=encrypt_phone(pd.phone_number),
            email=encrypt_email(pd.email),
            dob=dob,
            address=encrypt_field(pd.address) if pd.address else None,
            password=get_password_hash("temp_password"),
            years_experience=request.professional_details.years_of_experience,
            service_pincodes=request.service_area_details.pincodes,
            preferred_shift=request.service_area_details.preferred_shift,
            phone_otp=otp,
            otp_expires_at=expiry,
            is_verified="pending"
        )

        # Add driver and flush to get driver.id for related tables
        db.add(driver)
        await db.flush()

        # Create related rows in separate tables
        try:
            doc = DriverDocument(
                driver_id=driver.id,
                govt_id_type=request.identity_verification.govt_id_type,
                govt_id_number=encrypt_govt_id(request.identity_verification.govt_id_number),
                id_photo_url=request.identity_verification.govt_id_photo_url,
                selfie_photo_url=request.identity_verification.selfie_photo_url,
                license_number=encrypt_field(request.professional_details.license_number),
                license_category=request.professional_details.license_category,
                license_expiry_date=license_expiry,
                license_front_url=request.document_upload.license_front,
                license_back_url=request.document_upload.license_back,
                driver_photo_url=request.document_upload.driver_photo
            )

            bank = DriverBankDetail(
                driver_id=driver.id,
                bank_account_number=encrypt_bank_account(request.bank_details.account_number),
                bank_ifsc=encrypt_field(request.bank_details.sort_code),
                account_holder_name=encrypt_field(request.bank_details.holder_name),
                upi_id=encrypt_field(request.bank_details.upi_id)
            )

            vehicle = DriverVehicle(
                driver_id=driver.id,
                vehicle_type=request.vehicle_details.vehicle_type,
                vehicle_number_plate=encrypt_field(request.vehicle_details.vehicle_number),
                vehicle_model=request.vehicle_details.vehicle_model,
                vehicle_capacity=request.vehicle_details.vehicle_capacity,
                vehicle_photo_url=request.document_upload.vehicle_photo,
                rc_book_pic_url=request.vehicle_details.rc_book_photo,
                pollution_cert_pic_url=request.vehicle_details.pollution_certificate_photo
            )

            db.add_all([doc, bank, vehicle])
        except Exception:
            # If building related objects fails, rollback and re-raise
            await db.rollback()
            raise

        # Commit everything together and refresh driver
        await db.commit()
        await db.refresh(driver)
        
        # Create Stripe Connect Account
        stripe_error = None
        try:
            stripe_account = stripe_connect_service.create_custom_account(
                driver=driver,
                bank_detail=bank,
                document=doc,
                country="IE",  # Default to IE for now, could be dynamic based on address
                ip_address="127.0.0.1"  # In prod, get from request.client.host
            )
            
            # Update driver with Stripe ID
            driver.stripe_account_id = stripe_account["stripe_account_id"]
            driver.stripe_verification_status = stripe_account["status"]
            driver.stripe_payouts_enabled = stripe_account["payouts_enabled"]
            
            await db.commit()
            logger.info(f"Created Stripe account {driver.stripe_account_id} for driver {driver.id}")
            
        except Exception as e:
            stripe_error = str(e)
            logger.error(f"Failed to create Stripe account for driver {driver.id}: {e}")
            # Don't fail registration if Stripe fails, can be retried later
            # But we should probably log it clearly
        
        # Send OTP
        await send_sms_otp(phone_number, otp)
        
        return {
            "success": True,
            "message": "Driver registered successfully. OTP sent to phone number.",
            "driver_id": str(driver.id),
            "stripe_account_id": driver.stripe_account_id,
            "stripe_error": stripe_error,
            "phone_number": phone_number,
            "is_verified": False,
            "uploaded_files": {
                "driver_photo": get_full_url(driver_photo_path),
                "license_front": get_full_url(license_front_path),
                "license_back": get_full_url(license_back_path),
                "govt_id_photo": get_full_url(govt_id_photo_path),
                "selfie_photo": get_full_url(selfie_photo_path),
                "vehicle_photo": get_full_url(vehicle_photo_path),
                "rc_book_photo": get_full_url(rc_book_photo_path),
                "pollution_certificate": get_full_url(pollution_cert_path)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Driver registration with upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

# Admin Registration
@router.post("/api/auth/register/admin")
async def register_admin(
    request: AdminRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Register admin"""
    try:
        # Check if phone number exists
        encrypted_phone = encrypt_phone(request.phone_number)
        result = await db.execute(select(Admin).where(Admin.phone_number == encrypted_phone))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Phone number already registered")
        
        # Generate OTP and expiry
        otp = generate_otp()
        expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        # Create admin
        admin = Admin(
            phone_number=encrypted_phone,
            password=get_password_hash(request.password),
            mobile_otp=otp,
            otp_expires_at=expiry,
            is_verified=False
        )
        
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        
        # Send OTP
        await send_sms_otp(request.phone_number, otp)
        
        return {
            "success": True,
            "message": "Admin registered successfully. OTP sent to phone number.",
            "phone_number": request.phone_number,
            "is_verified": False
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin registration error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

# Verify Driver Registration OTP
@router.post("/api/auth/verify-registration/driver")
async def verify_driver_registration(
    request: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db)
):
    """Verify driver registration OTP and return access tokens for immediate dashboard access"""
    try:
        encrypted_phone = encrypt_phone(request.phone_number)
        result = await db.execute(select(Driver).where(Driver.phone_number == encrypted_phone))
        driver = result.scalar_one_or_none()
        
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        
        # Verify OTP via Twilio Verify
        if twilio_service:
            verify_result = twilio_service.verify_otp(request.phone_number, request.otp)
            if not verify_result["success"]:
                raise HTTPException(status_code=400, detail=verify_result.get("error", "Invalid or expired OTP"))
        else:
            raise HTTPException(status_code=503, detail="SMS service not configured")
        
        # Verify driver
        driver.is_verified = "verified"
        driver.phone_otp = None
        driver.otp_expires_at = None
        
        await db.commit()
        await db.refresh(driver)
        
        # Generate tokens for immediate dashboard access
        token_data = {"sub": str(driver.id), "phone": driver.phone_number, "role": "driver"}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        return {
            "success": True,
            "message": "Registration completed successfully. Welcome to your dashboard!",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "driver": {
                "driver_id": str(driver.id),
                "full_name": driver.full_name,
                "phone_number": driver.phone_number,
                "email": driver.email,
                "is_verified": driver.is_verified,
                "approval_status": driver.approval_status
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Driver registration verification error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")

# Verify Admin Registration OTP
@router.post("/api/auth/verify-registration/admin")
async def verify_admin_registration(
    request: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db)
):
    """Verify admin registration OTP and return access tokens for immediate dashboard access"""
    try:
        encrypted_phone = encrypt_phone(request.phone_number)
        result = await db.execute(select(Admin).where(Admin.phone_number == encrypted_phone))
        admin = result.scalar_one_or_none()
        
        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")
        
        # Verify OTP via Twilio Verify
        if twilio_service:
            verify_result = twilio_service.verify_otp(request.phone_number, request.otp)
            if not verify_result["success"]:
                raise HTTPException(status_code=400, detail=verify_result.get("error", "Invalid or expired OTP"))
        else:
            raise HTTPException(status_code=503, detail="SMS service not configured")
        
        # Verify admin
        admin.is_verified = True
        admin.mobile_otp = None
        admin.otp_expires_at = None
        
        await db.commit()
        await db.refresh(admin)
        
        # Generate tokens for immediate dashboard access
        token_data = {"sub": str(admin.id), "phone": admin.phone_number, "role": "admin"}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        return {
            "success": True,
            "message": "Registration completed successfully. Welcome to your dashboard!",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "admin": {
                "admin_id": str(admin.id),
                "phone_number": admin.phone_number,
                "is_verified": admin.is_verified,
                "is_active": admin.is_active
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin registration verification error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")

# Verify Driver OTP (legacy endpoint)
@router.post("/api/auth/verify/driver")
async def verify_driver_otp(
    request: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db)
):
    """Verify driver OTP"""
    try:
        encrypted_phone = encrypt_phone(request.phone_number)
        result = await db.execute(select(Driver).where(Driver.phone_number == encrypted_phone))
        driver = result.scalar_one_or_none()
        
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        
        if not driver.phone_otp or driver.phone_otp != request.otp:
            raise HTTPException(status_code=400, detail="Invalid OTP")
        
        if not driver.otp_expires_at or driver.otp_expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="OTP expired")
        
        # Verify driver
        driver.is_verified = "verified"
        driver.phone_otp = None
        driver.otp_expires_at = None
        
        await db.commit()
        
        return {
            "success": True,
            "message": "Driver OTP verified successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Driver OTP verification error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")

# Verify Admin OTP (legacy endpoint)
@router.post("/api/auth/verify/admin")
async def verify_admin_otp(
    request: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db)
):
    """Verify admin OTP"""
    try:
        encrypted_phone = encrypt_phone(request.phone_number)
        result = await db.execute(select(Admin).where(Admin.phone_number == encrypted_phone))
        admin = result.scalar_one_or_none()
        
        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")
        
        if not admin.mobile_otp or admin.mobile_otp != request.otp:
            raise HTTPException(status_code=400, detail="Invalid OTP")
        
        if not admin.otp_expires_at or admin.otp_expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="OTP expired")
        
        # Verify admin
        admin.is_verified = True
        admin.mobile_otp = None
        admin.otp_expires_at = None
        
        await db.commit()
        
        return {
            "success": True,
            "message": "Admin OTP verified successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin OTP verification error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")

# Driver Login
@router.post("/api/auth/login/driver")
async def driver_login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Driver login - sends OTP via Twilio"""
    try:
        encrypted_phone = encrypt_phone(request.phone_number)
        result = await db.execute(select(Driver).where(Driver.phone_number == encrypted_phone))
        driver = result.scalar_one_or_none()
        
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        
        if not driver.is_verified:
            raise HTTPException(status_code=400, detail="Driver not verified")
        
        if driver.approval_status != "approved":
            raise HTTPException(status_code=403, detail="Driver not approved yet")
        
        # Send OTP via Twilio Verify
        if twilio_service:
            twilio_result = twilio_service.send_otp(request.phone_number)
            if not twilio_result["success"]:
                raise HTTPException(status_code=400, detail=twilio_result.get("error", "Failed to send OTP"))
        else:
            # Fallback for local testing
            otp = generate_otp()
            expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
            driver.phone_otp = otp
            driver.otp_expires_at = expiry
            await db.commit()
        
        return {
            "success": True,
            "message": "OTP sent to phone number."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Driver login error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

# Admin Login
@router.post("/api/auth/login/admin")
async def admin_login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Admin login - sends OTP via Twilio"""
    try:
        encrypted_phone = encrypt_phone(request.phone_number)
        result = await db.execute(select(Admin).where(Admin.phone_number == encrypted_phone))
        admin = result.scalar_one_or_none()
        
        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")
        
        if not admin.is_verified:
            raise HTTPException(status_code=400, detail="Admin not verified")
        
        # Send OTP via Twilio Verify
        if twilio_service:
            twilio_result = twilio_service.send_otp(request.phone_number)
            if not twilio_result["success"]:
                raise HTTPException(status_code=400, detail=twilio_result.get("error", "Failed to send OTP"))
        else:
            # Fallback for local testing
            otp = generate_otp()
            expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
            admin.mobile_otp = otp
            admin.otp_expires_at = expiry
            await db.commit()
        
        return {
            "success": True,
            "message": "OTP sent to phone number."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin login error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

# Driver Verify Login
@router.post("/api/auth/verify-login/driver")
async def verify_driver_login(
    request: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db)
):
    """Verify driver login OTP via Twilio Verify and return tokens"""
    try:
        encrypted_phone = encrypt_phone(request.phone_number)
        result = await db.execute(select(Driver).where(Driver.phone_number == encrypted_phone))
        driver = result.scalar_one_or_none()
        
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        
        # Verify OTP via Twilio Verify
        if twilio_service:
            verify_result = twilio_service.verify_otp(request.phone_number, request.otp)
            if not verify_result["success"]:
                raise HTTPException(status_code=400, detail=verify_result.get("error", "Invalid or expired OTP"))
        else:
            # Fallback to database OTP for local testing
            if not driver.phone_otp or driver.phone_otp != request.otp:
                raise HTTPException(status_code=400, detail="Invalid OTP")
            
            if not driver.otp_expires_at or driver.otp_expires_at < datetime.now(timezone.utc):
                raise HTTPException(status_code=400, detail="OTP expired")
        
        # Generate tokens
        token_data = {"sub": str(driver.id), "phone": driver.phone_number, "role": "driver"}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        # Clear OTP
        driver.phone_otp = None
        driver.otp_expires_at = None
        
        await db.commit()
        
        return {
            "success": True,
            "message": "Login successful",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "driver": {
                "driver_id": str(driver.id),
                "full_name": driver.full_name,
                "phone_number": driver.phone_number
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Driver login verification error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Login verification failed: {str(e)}")

# Admin Verify Login
@router.post("/api/auth/verify-login/admin")
async def verify_admin_login(
    request: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db)
):
    """Verify admin login OTP via Twilio Verify and return tokens"""
    try:
        encrypted_phone = encrypt_phone(request.phone_number)
        result = await db.execute(select(Admin).where(Admin.phone_number == encrypted_phone))
        admin = result.scalar_one_or_none()
        
        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")
        
        # Verify OTP via Twilio Verify
        if twilio_service:
            verify_result = twilio_service.verify_otp(request.phone_number, request.otp)
            if not verify_result["success"]:
                raise HTTPException(status_code=400, detail=verify_result.get("error", "Invalid or expired OTP"))
        else:
            # Fallback to database OTP for local testing
            if not admin.mobile_otp or admin.mobile_otp != request.otp:
                raise HTTPException(status_code=400, detail="Invalid OTP")
            
            if not admin.otp_expires_at or admin.otp_expires_at < datetime.now(timezone.utc):
                raise HTTPException(status_code=400, detail="OTP expired")
        
        # Generate tokens
        token_data = {"sub": str(admin.id), "phone": admin.phone_number, "role": "admin"}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        # Clear OTP
        admin.mobile_otp = None
        admin.otp_expires_at = None
        
        await db.commit()
        
        return {
            "success": True,
            "message": "Login successful",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "admin": {
                "admin_id": str(admin.id),
                "phone_number": admin.phone_number
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin login verification error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Login verification failed: {str(e)}")

# Resend OTP endpoints
@router.post("/api/auth/resend-otp/driver")
async def resend_driver_otp(
    request: ResendOTPRequest,
    db: AsyncSession = Depends(get_db)
):
    """Resend OTP for driver"""
    try:
        encrypted_phone = encrypt_phone(request.phone_number)
        result = await db.execute(select(Driver).where(Driver.phone_number == encrypted_phone))
        driver = result.scalar_one_or_none()
        
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        
        # Generate new OTP
        otp = generate_otp()
        expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        driver.phone_otp = otp
        driver.otp_expires_at = expiry
        
        await db.commit()
        await send_sms_otp(request.phone_number, otp)
        
        return {
            "success": True,
            "message": "OTP resent to phone number."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resend driver OTP error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to resend OTP: {str(e)}")

@router.post("/api/auth/resend-otp/admin")
async def resend_admin_otp(
    request: ResendOTPRequest,
    db: AsyncSession = Depends(get_db)
):
    """Resend OTP for admin"""
    try:
        encrypted_phone = encrypt_phone(request.phone_number)
        result = await db.execute(select(Admin).where(Admin.phone_number == encrypted_phone))
        admin = result.scalar_one_or_none()
        
        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")
        
        # Generate new OTP
        otp = generate_otp()
        expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        admin.mobile_otp = otp
        admin.otp_expires_at = expiry
        
        await db.commit()
        await send_sms_otp(request.phone_number, otp)
        
        return {
            "success": True,
            "message": "OTP resent to phone number."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resend admin OTP error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to resend OTP: {str(e)}")


# Response schemas for driver documents
class DocumentInfo(BaseModel):
    govt_id_type: Optional[str] = None
    govt_id_number: Optional[str] = None
    id_photo_url: Optional[str] = None
    selfie_photo_url: Optional[str] = None
    license_number: Optional[str] = None
    license_category: Optional[str] = None
    license_expiry_date: Optional[str] = None
    license_front_url: Optional[str] = None
    license_back_url: Optional[str] = None
    driver_photo_url: Optional[str] = None

class BankInfo(BaseModel):
    bank_account_number: Optional[str] = None
    bank_ifsc: Optional[str] = None
    account_holder_name: Optional[str] = None
    upi_id: Optional[str] = None

class VehicleInfo(BaseModel):
    vehicle_type: Optional[str] = None
    vehicle_number_plate: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_capacity: Optional[str] = None
    vehicle_photo_url: Optional[str] = None
    rc_book_pic_url: Optional[str] = None
    pollution_cert_pic_url: Optional[str] = None

class DriverDocumentsResponse(BaseModel):
    success: bool
    driver_id: str
    documents: Optional[DocumentInfo] = None
    bank_details: Optional[BankInfo] = None
    vehicle: Optional[VehicleInfo] = None


@router.get("/api/driver/documents")
async def get_driver_documents(
    current_driver: Driver = Depends(get_current_driver_any_status),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all uploaded documents for the authenticated driver.
    Returns documents, bank details, and vehicle info.
    """
    try:
        driver_id = current_driver.id
        
        # Fetch documents
        doc_result = await db.execute(
            select(DriverDocument).where(DriverDocument.driver_id == driver_id)
        )
        driver_doc = doc_result.scalar_one_or_none()
        
        # Fetch bank details
        bank_result = await db.execute(
            select(DriverBankDetail).where(DriverBankDetail.driver_id == driver_id)
        )
        bank_detail = bank_result.scalar_one_or_none()
        
        # Fetch vehicle info
        vehicle_result = await db.execute(
            select(DriverVehicle).where(DriverVehicle.driver_id == driver_id)
        )
        vehicle = vehicle_result.scalar_one_or_none()
        
        # Build response
        documents = None
        if driver_doc:
            documents = DocumentInfo(
                govt_id_type=driver_doc.govt_id_type,
                govt_id_number=driver_doc.govt_id_number,
                id_photo_url=get_full_url(driver_doc.id_photo_url) if driver_doc.id_photo_url else None,
                selfie_photo_url=get_full_url(driver_doc.selfie_photo_url) if driver_doc.selfie_photo_url else None,
                license_number=driver_doc.license_number,
                license_category=driver_doc.license_category,
                license_expiry_date=str(driver_doc.license_expiry_date) if driver_doc.license_expiry_date else None,
                license_front_url=get_full_url(driver_doc.license_front_url) if driver_doc.license_front_url else None,
                license_back_url=get_full_url(driver_doc.license_back_url) if driver_doc.license_back_url else None,
                driver_photo_url=get_full_url(driver_doc.driver_photo_url) if driver_doc.driver_photo_url else None
            )
        
        bank_info = None
        if bank_detail:
            bank_info = BankInfo(
                bank_account_number=bank_detail.bank_account_number,
                bank_ifsc=bank_detail.bank_ifsc,
                account_holder_name=bank_detail.account_holder_name,
                upi_id=bank_detail.upi_id
            )
        
        vehicle_info = None
        if vehicle:
            vehicle_info = VehicleInfo(
                vehicle_type=vehicle.vehicle_type,
                vehicle_number_plate=vehicle.vehicle_number_plate,
                vehicle_model=vehicle.vehicle_model,
                vehicle_capacity=vehicle.vehicle_capacity,
                vehicle_photo_url=get_full_url(vehicle.vehicle_photo_url) if vehicle.vehicle_photo_url else None,
                rc_book_pic_url=get_full_url(vehicle.rc_book_pic_url) if vehicle.rc_book_pic_url else None,
                pollution_cert_pic_url=get_full_url(vehicle.pollution_cert_pic_url) if vehicle.pollution_cert_pic_url else None
            )
        
        return DriverDocumentsResponse(
            success=True,
            driver_id=str(driver_id),
            documents=documents,
            bank_details=bank_info,
            vehicle=vehicle_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get driver documents error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch documents: {str(e)}")
