"""
Update waste categories to new set:
Household, Recyclables, Garden, C&D, E-Waste, Furniture, Hazardous, Metal, Appliances, Mixed Waste
"""
import asyncio
from sqlalchemy import select, delete, update
from core.database import AsyncSessionLocal
from core.models import Category, Issue

async def update_categories():
    async with AsyncSessionLocal() as db:
        # Delete all issues first (they reference categories)
        await db.execute(delete(Issue))
        await db.commit()
        print("✅ Deleted all issues")
        
        # Delete existing categories
        await db.execute(delete(Category))
        await db.commit()
        print("✅ Deleted old categories")
        
        # New waste categories (only name and image_url - no description field in model)
        new_categories = [
            {"name": "Household", "image_url": "https://via.placeholder.com/150"},
            {"name": "Recyclables", "image_url": "https://via.placeholder.com/150"},
            {"name": "Garden", "image_url": "https://via.placeholder.com/150"},
            {"name": "C&D", "image_url": "https://via.placeholder.com/150"},
            {"name": "E-Waste", "image_url": "https://via.placeholder.com/150"},
            {"name": "Furniture", "image_url": "https://via.placeholder.com/150"},
            {"name": "Hazardous", "image_url": "https://via.placeholder.com/150"},
            {"name": "Metal", "image_url": "https://via.placeholder.com/150"},
            {"name": "Appliances", "image_url": "https://via.placeholder.com/150"},
            {"name": "Mixed Waste", "image_url": "https://via.placeholder.com/150"},
        ]
        
        # Insert new categories
        for cat_data in new_categories:
            category = Category(**cat_data)
            db.add(category)
        
        await db.commit()
        print(f"✅ Created {len(new_categories)} new waste categories")
        
        # Verify
        result = await db.execute(select(Category))
        categories = result.scalars().all()
        print("\n📋 Current categories:")
        for cat in categories:
            print(f"  ID {cat.id}: {cat.name}")

if __name__ == "__main__":
    asyncio.run(update_categories())
