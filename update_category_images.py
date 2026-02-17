"""
Update Category Image URLs - Match to Category Names
"""
import asyncio
from sqlalchemy import select
from core.database import AsyncSessionLocal
from core.models import Category

async def update_category_images():
    """Update image_url for each category based on its name"""
    
    # Professional waste management icons from Flaticon
    image_mapping = {
        "Household": "https://cdn-icons-png.flaticon.com/512/2917/2917995.png",
        "household": "https://cdn-icons-png.flaticon.com/512/2917/2917995.png",
        "Recyclables": "https://cdn-icons-png.flaticon.com/512/3524/3524388.png",
        "Garden": "https://cdn-icons-png.flaticon.com/512/628/628283.png",
        "C&D": "https://cdn-icons-png.flaticon.com/512/3004/3004458.png",
        "E-Waste": "https://cdn-icons-png.flaticon.com/512/2913/2913133.png",
        "Furniture": "https://cdn-icons-png.flaticon.com/512/1670/1670828.png",
        "Hazardous": "https://cdn-icons-png.flaticon.com/512/3176/3176363.png",
        "Metal": "https://cdn-icons-png.flaticon.com/512/2917/2917242.png",
        "Appliances": "https://cdn-icons-png.flaticon.com/512/3004/3004458.png",
        "Mixed Waste": "https://cdn-icons-png.flaticon.com/512/3524/3524636.png",
    }
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Category).order_by(Category.id))
        categories = result.scalars().all()
        
        if not categories:
            print("No categories found!")
            return
        
        print("UPDATING CATEGORY IMAGE URLs")
        print("=" * 80)
        
        updated = 0
        for cat in categories:
            if cat.name in image_mapping:
                new_url = image_mapping[cat.name]
                cat.image_url = new_url
                updated += 1
                print(f"ID {cat.id:<3} | {cat.name:<20} -> {new_url}")
            else:
                print(f"ID {cat.id:<3} | {cat.name:<20} -> NO MAPPING FOUND")
        
        if updated > 0:
            await db.commit()
            print(f"\n{updated} categories updated successfully!")
        
        # Clear Redis cache
        try:
            from core.redis_client import redis_client
            await redis_client.initialize()
            await redis_client.delete("categories:all")
            print("Redis cache cleared")
            await redis_client.close()
        except:
            pass
        
        print("\n" + "=" * 80)
        print("Images are from Flaticon CDN - No upload needed!")
        print("Restart server: docker-compose restart customer-backend")

if __name__ == "__main__":
    asyncio.run(update_category_images())
