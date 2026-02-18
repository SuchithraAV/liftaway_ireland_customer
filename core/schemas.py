from pydantic import BaseModel, EmailStr, Field, validator, model_serializer
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal
from core.models import UserRole, IssueStatus, IssuePaymentStatus

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    phone_number: str

class UserCreate(UserBase):
    password: str
    role: UserRole = UserRole.CUSTOMER
    company_id: Optional[int] = None
    technician_type: Optional[str] = "individual"

class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    phone_number: str
    role: UserRole
    is_approved: bool
    is_active: bool
    is_email_verified: bool = False
    date_joined: datetime
    
    class Config:
        from_attributes = True

# Company Schemas
class CompanyBase(BaseModel):
    name: str
    address: Optional[str] = None
    contact_number: Optional[str] = None
    email: Optional[EmailStr] = None
    lat: Optional[float] = None
    lng: Optional[float] = None

class CompanyCreate(CompanyBase):
    pass

class CompanyResponse(CompanyBase):
    id: int
    owner_id: Optional[UUID]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    contact_number: Optional[str] = None
    email: Optional[EmailStr] = None

class CompanyLocationUpdate(BaseModel):
    lat: float
    lng: float

class CompanyRegistration(BaseModel):
    # User fields
    email: EmailStr
    password: str
    full_name: str
    phone_number: str
    
    # Company fields
    company_name: str
    company_address: Optional[str] = None
    company_contact_number: Optional[str] = None
    company_email: Optional[EmailStr] = None
    lat: Optional[float] = None
    lng: Optional[float] = None

class CompanyRegistrationResponse(BaseModel):
    user: UserResponse
    company: CompanyResponse

# Auth Schemas
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: UserResponse
    dashboard_url: str

class TokenData(BaseModel):
    user_id: Optional[str] = None



# Profile Schemas
class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None

# Email Verification Schemas
class VerifyOTP(BaseModel):
    otp: str

class EmailVerify(BaseModel):
    email: EmailStr
    otp: str

class ResendOTP(BaseModel):
    email: EmailStr

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str

# OAuth Schemas
class GoogleLoginRequest(BaseModel):
    token: str
    role: UserRole = UserRole.CUSTOMER

class AppleLoginRequest(BaseModel):
    token: str
    role: UserRole = UserRole.CUSTOMER

class SocialLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: UserResponse
    is_new_user: bool
    dashboard_url: str

# Category Schemas
class CategoryResponse(BaseModel):
    id: int
    name: str
    image_url: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# Waste Pickup Schemas
class IssueCreate(BaseModel):
    category_id: int
    description: str
    pickup_location: str
    images: List[str] = Field(..., min_items=1, max_items=5)  # Min 1, Max 5 images
    amount: Decimal
    scheduled_date: Optional[date] = None
    
    @validator('images')
    def validate_images(cls, v):
        if not v or len(v) < 1:
            raise ValueError('At least 1 image is required')
        if len(v) > 5:
            raise ValueError('Maximum 5 images allowed')
        return v

class IssueResponse(BaseModel):
    id: UUID
    customer_id: UUID
    category_id: int
    category_name: Optional[str] = None
    description: str
    pickup_location: str
    images: List[str]
    assigned_driver_id: Optional[UUID] = None
    assigned_driver_name: Optional[str] = None
    assigned_driver_phone: Optional[str] = None
    driver_lat: Optional[float] = None
    driver_lng: Optional[float] = None
    status: str
    otp_code: Optional[str] = None  # Hide OTP in list view
    payment_amount: Decimal
    negotiated_price: Optional[Decimal] = None
    negotiated_status: str = "none"
    payment_status: str
    scheduled_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class NegotiateRequest(BaseModel):
    amount: Decimal

class IssueOTPResponse(BaseModel):
    status: str
    otp_code: str
    
class DriverIssueResponse(BaseModel):
    id: UUID
    category_name: str
    customer_name: str
    pickup_location: str
    created_at: datetime
    distance: Optional[float] = None
    payment_amount: Decimal
    status: str
    
    class Config:
        from_attributes = True

class IssueStatusUpdate(BaseModel):
    status: IssueStatus
    otp_code: Optional[str] = None
    
    @validator('otp_code')
    def validate_otp_for_completion(cls, v, values):
        if values.get('status') == IssueStatus.COMPLETED and not v:
            raise ValueError('OTP code is required when changing status to completed')
        return v

class DriverEarningsResponse(BaseModel):
    date: date
    jobs_done: int
    amount: Decimal
    
    class Config:
        from_attributes = True

class IssueRatingCreate(BaseModel):
    issue_id: UUID
    rating: int = Field(..., ge=1, le=5)
    comments: Optional[str] = None

class IssueRatingResponse(BaseModel):
    id: int
    issue_id: UUID
    customer_id: UUID
    driver_id: UUID
    rating: int
    comments: Optional[str]
    created_at: datetime
    customer_name: Optional[str] = None
    driver_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class StripePaymentIntentCreate(BaseModel):
    issue_id: UUID

class StripePaymentIntentResponse(BaseModel):
    client_secret: str
    payment_intent_id: str
    amount: int

class StripeConnectAccountCreate(BaseModel):
    email: str
    country: str = "US"

class StripeConnectAccountResponse(BaseModel):
    account_id: str
    onboarding_url: str

class StripePaymentVerify(BaseModel):
    payment_intent_id: str
    issue_id: UUID


# Chat Schemas
class ChatMessageCreate(BaseModel):
    encrypted_text: str

class ChatMessageResponse(BaseModel):
    id: UUID
    issue_id: UUID
    sender_id: UUID
    sender_type: str  # "customer" or "driver"
    text: str  # Decrypted message text (encryption is server-side)
    created_at: datetime
    
    class Config:
        from_attributes = True

class ChatHistoryResponse(BaseModel):
    issue_id: UUID
    messages: List[ChatMessageResponse]
    is_chat_active: bool  # False if issue is completed
    
    class Config:
        from_attributes = True

class ChatStatusResponse(BaseModel):
    issue_id: UUID
    is_chat_active: bool
    issue_status: str
    message: str


# Notification schema
class NotificationResponse(BaseModel):
    id: UUID
    user_id: UUID
    user_type: str
    title: str
    message: str
    data: Optional[dict] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Draft Issue Schemas (for React → Flutter flow)
class IssueDraftResponse(BaseModel):
    draft_id: str
    estimated_price: float
    expires_in_seconds: int = 1800

class IssueDraftDataResponse(BaseModel):
    draft_id: str
    category_id: int
    category_name: Optional[str] = None
    description: str
    pickup_location: str
    quantity: Optional[int] = None
    urgency: Optional[str] = None
    vehicle_size: Optional[str] = None
    postcode: Optional[str] = None
    access_difficulty: Optional[str] = None
    volume_load: Optional[str] = None
    estimated_price: float
    created_at: str