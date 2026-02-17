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
    '''Get current user profile (cached 5 min)'''
    cache_key = f"profile:{current_user.id}"
    cached = await get_cached(cache_key)
    if cached:
        return cached
    
    # Determine role based on the type of user object
    if isinstance(current_user, Customer):
        role = UserRole.CUSTOMER
    elif isinstance(current_user, Admin):
        role = UserRole.ADMIN
    else:
        role = UserRole.CUSTOMER  # fallback
    
    profile_data = UserResponse(
        id=current_user.id,
        email=getattr(current_user, "email", ""),
        full_name=getattr(current_user, "full_name", ""),
        phone_number=getattr(current_user, "phone_number", ""),
        role=role,
        is_active=current_user.is_active,
        is_approved=getattr(current_user, "is_approved", True),
        is_email_verified=getattr(current_user, "is_verified", False),
        date_joined=current_user.date_joined,
        company_id=getattr(current_user, "company_id", None),
        technician_type=getattr(current_user, "technician_type", None),
    )
    
    await set_cached(cache_key, profile_data.model_dump(), ttl=300)
    return profile_data

@router.patch("/", response_model=UserResponse)
async def update_profile(
    profile_data: ProfileUpdate,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    '''Update current user profile'''
    # Check if email is being changed and if it already exists
    if profile_data.email and getattr(current_user, "email", None) != profile_data.email:
        # Check in all user tables but only for models that define an `email` column/attribute
        for model in [Customer, Admin]:
            # Some models (e.g. Admin) may not have an `email` column; skip those
            if not hasattr(model, "email"):
                continue
            existing_user = await db.execute(
                select(model).where(model.email == profile_data.email)
            )
            if existing_user.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Email already registered")
    
    # Update fields
    if profile_data.full_name:
        current_user.full_name = profile_data.full_name
    if profile_data.phone_number and hasattr(current_user, 'phone_number'):
        current_user.phone_number = profile_data.phone_number
    if profile_data.email:
        # Only assign email if the current user model actually supports it
        if hasattr(current_user, 'email'):
            current_user.email = profile_data.email
        else:
            # If the user type has no email field, reject the update explicitly
            raise HTTPException(status_code=400, detail="This account type does not support email updates")
    
    await db.commit()
    await db.refresh(current_user)
    
    # Invalidate cache
    await delete_cached(f"profile:{current_user.id}")
    
    # Return properly serialized response
    if isinstance(current_user, Customer):
        role = UserRole.CUSTOMER
    elif isinstance(current_user, Admin):
        role = UserRole.ADMIN
    else:
        role = UserRole.CUSTOMER
    
    return UserResponse(
        id=current_user.id,
        email=getattr(current_user, "email", ""),
        full_name=getattr(current_user, "full_name", ""),
        phone_number=getattr(current_user, "phone_number", ""),
        role=role,
        is_active=current_user.is_active,
        is_approved=getattr(current_user, "is_approved", True),
        is_email_verified=getattr(current_user, "is_verified", False),
        date_joined=current_user.date_joined,
        company_id=getattr(current_user, "company_id", None),
        technician_type=getattr(current_user, "technician_type", None),
    )

