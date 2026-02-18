from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_db
from core.models import UserRole, Customer, Admin
from core.schemas import UserResponse, ProfileUpdate
from core.dependencies import get_current_user
from core.utils.security import verify_password, get_password_hash
from core.utils.cache import get_cached, set_cached, delete_cached

router = APIRouter(prefix="/profile", tags=["Profile"])

@router.get("/", response_model=UserResponse)
async def get_profile(current_user = Depends(get_current_user)):
    '''Get current user profile'''
    if not isinstance(current_user, Customer):
        raise HTTPException(status_code=403, detail="Only customers can access this endpoint")
    
    from core.utils.field_encryption import decrypt_email, decrypt_phone, decrypt_field
    
    return UserResponse(
        id=current_user.id,
        email=decrypt_email(current_user.email),
        full_name=decrypt_field(current_user.full_name),
        phone_number=decrypt_phone(current_user.phone_number),
        role=UserRole.CUSTOMER,
        is_active=current_user.is_active,
        is_approved=True,
        is_email_verified=current_user.is_verified,
        date_joined=current_user.date_joined,
    )

@router.patch("/", response_model=UserResponse)
async def update_profile(
    profile_data: ProfileUpdate,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    '''Update current user profile'''
    if not isinstance(current_user, Customer):
        raise HTTPException(status_code=403, detail="Only customers can access this endpoint")
    
    from core.utils.field_encryption import encrypt_email, encrypt_phone, encrypt_field, decrypt_email, decrypt_phone, decrypt_field
    
    if profile_data.email:
        encrypted_email = encrypt_email(profile_data.email)
        if current_user.email != encrypted_email:
            existing = await db.execute(select(Customer).where(Customer.email == encrypted_email))
            if existing.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Email already registered")
            current_user.email = encrypted_email
    
    if profile_data.full_name:
        current_user.full_name = encrypt_field(profile_data.full_name)
    if profile_data.phone_number:
        current_user.phone_number = encrypt_phone(profile_data.phone_number)
    
    await db.commit()
    await db.refresh(current_user)
    
    return UserResponse(
        id=current_user.id,
        email=decrypt_email(current_user.email),
        full_name=decrypt_field(current_user.full_name),
        phone_number=decrypt_phone(current_user.phone_number),
        role=UserRole.CUSTOMER,
        is_active=current_user.is_active,
        is_approved=True,
        is_email_verified=current_user.is_verified,
        date_joined=current_user.date_joined,
    )

