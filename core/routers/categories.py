from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from core.database import get_db
from core.models import Category
from core.schemas import CategoryResponse
from core.utils.cache import get_cached, set_cached

router = APIRouter(prefix="/categories", tags=["Categories"])

@router.get("/", response_model=List[CategoryResponse])
async def get_categories(db: AsyncSession = Depends(get_db)):
    '''Get all active categories (cached 1 hour)'''
    cache_key = "categories:all"
    cached = await get_cached(cache_key)
    if cached:
        return cached
    
    result = await db.execute(
        select(Category)
        .where(Category.is_active == True)
        .order_by(Category.name)
    )
    categories = result.scalars().all()
    
    categories_data = [CategoryResponse.model_validate(cat) for cat in categories]
    await set_cached(cache_key, [c.model_dump() for c in categories_data], ttl=3600)
    return categories_data

@router.get("/{category_id}/", response_model=CategoryResponse)
async def get_category(
    category_id: int,
    db: AsyncSession = Depends(get_db)
):
    '''Get a specific category (cached 1 hour)'''
    cache_key = f"category:{category_id}"
    cached = await get_cached(cache_key)
    if cached:
        return cached
    
    result = await db.execute(
        select(Category).where(
            Category.id == category_id,
            Category.is_active == True
        )
    )
    category = result.scalar_one_or_none()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    category_data = CategoryResponse.model_validate(category)
    await set_cached(cache_key, category_data.model_dump(), ttl=3600)
    return category_data