from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_db
from core.models import UserRole, Customer, Admin
from core.utils.field_encryption import encrypt_email, decrypt_email, encrypt_phone, decrypt_phone, encrypt_field, decrypt_field, encrypt_address, decrypt_address
from core.schemas import (
    UserCreate,
    UserResponse,
    LoginResponse,
    Token,
    EmailVerify,
    ResendOTP,
    VerifyOTP,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from core.utils.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from core.dependencies import get_current_user
from core.utils.email import (
    send_verification_email,
    send_password_reset_email,
    generate_otp,
    get_otp_expiry,
)
from pydantic import BaseModel
from datetime import datetime
from fastapi.responses import RedirectResponse
from config import settings
import httpx
import logging
from uuid import uuid4

# Create logger for this module
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: str
    password: str


# ============================================================================
# CUSTOMER REGISTRATION & LOGIN
# ============================================================================

@router.post("/register/customer", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def register_customer(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    '''Register new customer and send OTP'''
    logger.info(f"🔐 Customer registration attempt for email: {user_data.email}")
    
    # Check if email exists (search with encrypted email)
    encrypted_email = encrypt_email(user_data.email)
    result = await db.execute(select(Customer).where(Customer.email == encrypted_email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    hashed_password = get_password_hash(user_data.password)
    otp = generate_otp()
    otp_expiry = get_otp_expiry()
    
    new_customer = Customer(
        email=encrypt_email(user_data.email),
        password=hashed_password,
        full_name=encrypt_field(user_data.full_name),
        phone_number=encrypt_phone(user_data.phone_number),
        email_otp=otp,
        otp_expires_at=otp_expiry,
        is_active=True,
        is_email_verified=False
    )
    
    db.add(new_customer)
    await db.commit()
    await db.refresh(new_customer)
    
    # Send OTP email
    email_sent = send_verification_email(new_customer.email, otp, new_customer.full_name)
    if not email_sent:
        logger.error(f"Failed to send OTP email to {new_customer.email}")
    
    # Generate tokens
    access_token = create_access_token(data={"sub": str(new_customer.id), "role": UserRole.CUSTOMER.value})
    refresh_token = create_refresh_token(data={"sub": str(new_customer.id), "role": UserRole.CUSTOMER.value})
    
    user_response = UserResponse(
        id=new_customer.id,
        email=decrypt_email(new_customer.email),
        full_name=decrypt_field(new_customer.full_name),
        phone_number=decrypt_phone(new_customer.phone_number),
        role=UserRole.CUSTOMER,
        is_active=new_customer.is_active,
        is_approved=True,
        is_email_verified=new_customer.is_email_verified,
        date_joined=new_customer.date_joined,
    )
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_response,
        dashboard_url="/dashboard/customer"
    )


@router.post("/login/customer", response_model=LoginResponse)
async def login_customer(login_data: LoginRequest, db: AsyncSession = Depends(get_db)):
    '''Login as customer'''
    logger.info(f"🔐 Customer login attempt for email: {login_data.email}")
    # Encrypt email for search
    encrypted_email = encrypt_email(login_data.email)
    result = await db.execute(select(Customer).where(Customer.email == encrypted_email))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(login_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )
        
    access_token = create_access_token(
        data={"sub": str(user.id), "role": UserRole.CUSTOMER.value}
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.id), "role": UserRole.CUSTOMER.value}
    )

    user_response = UserResponse(
        id=user.id,
        email=decrypt_email(user.email),
        full_name=decrypt_field(user.full_name),
        phone_number=decrypt_phone(user.phone_number),
        role=UserRole.CUSTOMER,
        is_active=user.is_active,
        is_approved=True,
        is_email_verified=user.is_email_verified,
        date_joined=user.date_joined,
    )
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_response,
        dashboard_url="/dashboard/customer"
    )


# ============================================================================
# TOKEN MANAGEMENT
# ============================================================================

@router.post("/refresh/", response_model=Token)
async def refresh_token(refresh_token: str, db: AsyncSession = Depends(get_db)):
    """Refresh access token using refresh token."""
    payload = decode_token(refresh_token)

    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user_id = payload.get("sub")
    role_value = payload.get("role")

    if not user_id or not role_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Load the appropriate user table based on role
    model_map = {
        UserRole.CUSTOMER.value: Customer,
        UserRole.ADMIN.value: Admin,
    }

    model = model_map.get(role_value)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unsupported role in token",
        )

    result = await db.execute(select(model).where(model.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    new_access_token = create_access_token(
        data={"sub": str(user.id), "role": role_value}
    )
    new_refresh_token = create_refresh_token(
        data={"sub": str(user.id), "role": role_value}
    )

    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
    )



# ============================================================================
# EMAIL VERIFICATION
# ============================================================================

@router.post("/verify/")
async def verify_otp(
    verify_data: VerifyOTP,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    '''Verify OTP using access token'''
    if current_user.is_email_verified:
        raise HTTPException(status_code=400, detail="User already verified")
    
    if not current_user.email_otp or current_user.email_otp != verify_data.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    if current_user.otp_expires_at and datetime.utcnow() > current_user.otp_expires_at:
        raise HTTPException(status_code=400, detail="OTP expired")
    
    # Verify user
    current_user.is_email_verified = True
    current_user.email_otp = None
    current_user.otp_expires_at = None
    await db.commit()
    
    return {"message": "Email verified successfully", "is_email_verified": True}


@router.post("/resend-otp/")
async def resend_otp(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    '''Resend OTP to current user'''
    if current_user.is_email_verified:
        raise HTTPException(status_code=400, detail="User already verified")
    
    # Generate new OTP
    otp = generate_otp()
    otp_expiry = get_otp_expiry()
    
    current_user.email_otp = otp
    current_user.otp_expires_at = otp_expiry
    await db.commit()
    
    # Send email
    email_sent = send_verification_email(current_user.email, otp, current_user.full_name)
    
    return {
        "message": "OTP generated successfully" if email_sent else "OTP generated but email not sent",
        "email": current_user.email,
        "otp": otp if not email_sent else None,  # Include OTP in response if email failed
        "email_sent": email_sent
    }


# ============================================================================
# PASSWORD RESET
# ============================================================================

@router.post("/forgot-password/")
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    '''Send OTP for password reset'''
    encrypted_email = encrypt_email(request.email)
    result = await db.execute(select(Customer).where(Customer.email == encrypted_email))
    user = result.scalar_one_or_none()
    
    if not user:
        # Don't reveal if user exists
        return {"message": "If email exists, OTP will be sent"}
    
    # Generate OTP
    otp = generate_otp()
    otp_expiry = get_otp_expiry()
    
    user.email_otp = otp
    user.otp_expires_at = otp_expiry
    await db.commit()
    
    # Send email
    email_sent = send_password_reset_email(user.email, otp, user.full_name)
    
    return {
        "message": "OTP generated successfully" if email_sent else "OTP generated but email not sent",
        "email_sent": email_sent,
        "otp": otp if not email_sent else None  # Include OTP if email failed for testing
    }


@router.post("/reset-password/")
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    '''Reset password using OTP'''
    encrypted_email = encrypt_email(request.email)
    result = await db.execute(select(Customer).where(Customer.email == encrypted_email))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.email_otp or user.email_otp != request.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    if user.otp_expires_at and datetime.utcnow() > user.otp_expires_at:
        raise HTTPException(status_code=400, detail="OTP expired")
    
    # Reset password
    user.password = get_password_hash(request.new_password)
    user.email_otp = None
    user.otp_expires_at = None
    await db.commit()
    
    return {"message": "Password reset successfully"}


# ============================================================================
# USER PROFILE
# ============================================================================

@router.get("/me/", response_model=UserResponse)
async def get_current_user_info(current_user=Depends(get_current_user)):
    """Get current user information."""
    # Determine role based on the type of user object
    if isinstance(current_user, Customer):
        role = UserRole.CUSTOMER
    elif isinstance(current_user, Admin):
        role = UserRole.ADMIN
    else:
        role = UserRole.CUSTOMER  # fallback
    
    return UserResponse(
        id=current_user.id,
        email=decrypt_email(current_user.email) if current_user.email else "",
        full_name=decrypt_field(current_user.full_name) if current_user.full_name else "",
        phone_number=decrypt_phone(getattr(current_user, "phone_number", "")) if getattr(current_user, "phone_number", "") else "",
        role=role,
        is_active=current_user.is_active,
        is_approved=getattr(current_user, "is_approved", True),
        is_email_verified=getattr(current_user, "is_email_verified", False),
        date_joined=current_user.date_joined,
        company_id=getattr(current_user, "company_id", None),
        technician_type=getattr(current_user, "technician_type", None),
    )


# ============================================================================
# GOOGLE OAUTH
# ============================================================================

@router.get("/google/")
async def google_login():
    """Redirect to Google OAuth"""
    google_auth_url = (
        f"https://accounts.google.com/o/oauth2/auth?"
        f"client_id={settings.GOOGLE_CLIENT_ID}&"
        f"redirect_uri={settings.GOOGLE_REDIRECT_URI}&"
        f"scope=openid email profile&"
        f"response_type=code&"
        f"access_type=offline"
    )
    return RedirectResponse(url=google_auth_url)

@router.get("/google/callback")
async def google_callback(code: str, db: AsyncSession = Depends(get_db)):
    """Handle Google OAuth callback"""
    # Exchange code for token
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
    }
    
    async with httpx.AsyncClient() as client:
        token_response = await client.post(token_url, data=token_data)
        token_json = token_response.json()
        
        if "access_token" not in token_json:
            raise HTTPException(status_code=400, detail="Failed to get access token")
        
        # Get user info from Google
        user_info_url = f"https://www.googleapis.com/oauth2/v2/userinfo?access_token={token_json['access_token']}"
        user_response = await client.get(user_info_url)
        user_data = user_response.json()
    
    # Check if user exists
    encrypted_email = encrypt_email(user_data["email"])
    result = await db.execute(select(Customer).where(Customer.email == encrypted_email))
    customer = result.scalar_one_or_none()
    
    if not customer:
        # Create new customer
        customer = Customer(
            id=uuid4(),
            email=encrypt_email(user_data["email"]),
            full_name=encrypt_field(user_data["name"]),
            phone_number=encrypt_phone(""),  # Will need to be updated later
            password="google_oauth",  # Placeholder
            is_email_verified=True
        )
        db.add(customer)
        await db.commit()
        await db.refresh(customer)
    
    # Create JWT token
    access_token = create_access_token(data={"sub": str(customer.id), "role": "customer"})
    
    # Return success page with token
    return f"""
    <html>
        <head><title>Login Success</title></head>
        <body>
            <h2>Login Successful!</h2>
            <p>Welcome, {customer.full_name}!</p>
            <p>Your access token: <code>{access_token}</code></p>
            <script>
                // Store token in localStorage for testing
                localStorage.setItem('access_token', '{access_token}');
                // Redirect after 3 seconds
                setTimeout(() => window.close(), 3000);
            </script>
        </body>
    </html>
    """

