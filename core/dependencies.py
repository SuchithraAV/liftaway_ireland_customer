from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_db
from core.models import UserRole, Customer, Admin, Driver
from core.utils.security import decode_token
from typing import Optional
from uuid import UUID

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload is None or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    user_id: str = payload.get("sub")
    role_value: str = payload.get("role")
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    user = None
    
    if role_value == UserRole.CUSTOMER.value:
        result = await db.execute(select(Customer).where(Customer.id == UUID(user_id)))
        user = result.scalar_one_or_none()
        
    elif role_value == UserRole.ADMIN.value:
        result = await db.execute(select(Admin).where(Admin.id == UUID(user_id)))
        user = result.scalar_one_or_none()
    
    elif role_value == "driver":  # Handle driver role
        result = await db.execute(select(Driver).where(Driver.id == UUID(user_id)))
        user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return user

async def get_current_customer(current_user = Depends(get_current_user)):
    if not isinstance(current_user, Customer):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized as customer"
        )
    return current_user

async def get_current_admin(current_user = Depends(get_current_user)):
    if not isinstance(current_user, Admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized as admin"
        )
    return current_user

async def get_current_driver(current_user = Depends(get_current_user)):
    if not isinstance(current_user, Driver):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized as driver"
        )
    return current_user