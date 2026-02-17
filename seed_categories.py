"""
Seed LiftAway Categories (2025)
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import AsyncSessionLocal
from core.models import Category

async def seed_categories():
    """Seed database with LiftAway service categories"""
    
    categories_data = [
        {"name": "Single Item Removal", "image_url": "https://mybucket6utholiftaway1.innoida.utho.io/categories/single_item.jpg", "is_active": True},
        {"name": "Garden Waste", "image_url": "https://mybucket6utholiftaway1.innoida.utho.io/categories/garden_waste.jpg", "is_active": True},
        {"name": "Multiple Items", "image_url": "https://mybucket6utholiftaway1.innoida.utho.io/categories/multiple_items.jpg", "is_active": True},
        {"name": "Furniture & Appliances", "image_url": "https://mybucket6utholiftaway1.innoida.utho.io/categories/furniture.jpg", "is_active": True},
        {"name": "Full Van Load", "image_url": "https://mybucket6utholiftaway1.innoida.utho.io/categories/full_van.jpg", "is_active": True},
        {"name": "Household Waste", "image_url": "https://mybucket6utholiftaway1.innoida.utho.io/categories/household_waste.jpg", "is_active": True},
        {"name": "Mixed Waste", "image_url": "https://mybucket6utholiftaway1.innoida.utho.io/categories/mixed_waste.jpg", "is_active": True},
        {"name": "One-off Clearance", "image_url": "https://mybucket6utholiftaway1.innoida.utho.io/categories/clearance.jpg", "is_active": True},
        {"name": "Full Property Move", "image_url": "https://mybucket6utholiftaway1.innoida.utho.io/categories/property_move.jpg", "is_active": True},
        {"name": "E-waste", "image_url": "https://mybucket6utholiftaway1.innoida.utho.io/categories/e-waste.jpg", "is_active": True},
    ]
    
    async with AsyncSessionLocal() as db:
        # Check existing categories
        result = await db.execute(select(Category))
        existing = result.scalars().all()
        existing_names = {cat.name for cat in existing}
        
        added = 0
        for data in categories_data:
            if data["name"] not in existing_names:
                category = Category(**data)
                db.add(category)
                added += 1
        
        if added > 0:
            await db.commit()
            print(f"✅ Added {added} new categories")
        else:
            print("✅ All categories already exist")
        
        # Show all categories
        result = await db.execute(select(Category).order_by(Category.id))
        all_categories = result.scalars().all()
        print(f"\n📋 Total categories in database: {len(all_categories)}")
        for cat in all_categories:
            print(f"  - ID {cat.id}: {cat.name}")

if __name__ == "__main__":
    asyncio.run(seed_categories())
