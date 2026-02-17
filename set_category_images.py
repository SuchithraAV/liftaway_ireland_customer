"""
Set Category Image URLs - Add your URLs here
"""
import asyncio
from sqlalchemy import select
from core.database import AsyncSessionLocal
from core.models import Category

async def set_category_images():
    """Update image_url for each category"""
    
    # ADD YOUR IMAGE URLs HERE
    image_mapping = {
        "Household": "https://www.shutterstock.com/image-vector/illustration-simple-house-isolated-600w-2509940761.jpg",
        
        "Recyclables": "https://www.shutterstock.com/image-photo/top-view-realistic-3d-rendering-260nw-2591323259.jpg",
        "Garden": "https://i.pinimg.com/736x/b3/d7/55/b3d75545361e768c21ec44d439528804.jpg",
        "C&D": "https://www.picsinternational.com/images/blogs/construction-demolition-waste-recycling-plant-in-india.webp",
        "E-Waste": "https://customwrapsindia.com/wp-content/uploads/2022/06/e-waste-management.png",
        "Furniture": "https://www.sustainablejungle.com/wp-content/uploads/2024/09/Image-by-POLYWOOD-recycled-plastic-outdoor-furniture-2.jpg",
        "Hazardous": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/01/Vienna_Convention_road_sign_Aa-32-V1.svg/250px-Vienna_Convention_road_sign_Aa-32-V1.svg.png",
        "Metal": "https://t4.ftcdn.net/jpg/15/57/23/45/360_F_1557234594_toKp87DfSu5StjfG7a1DxhvhFOwNs0Kd.jpg",
        "Appliances": "https://classiclabindia.com/wp-content/uploads/2024/05/basics-of-household-appliances.jpg",
        "Mixed Waste": "https://png.pngtree.com/png-clipart/20250109/original/pngtree-green-recycling-bin-with-mixed-glass-and-metal-waste-for-eco-png-image_19841663.png",
    }
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Category).order_by(Category.id))
        categories = result.scalars().all()
        
        if not categories:
            print("No categories found!")
            return
        
        print("SETTING CATEGORY IMAGE URLs")
        print("=" * 80)
        
        updated = 0
        for cat in categories:
            if cat.name in image_mapping and image_mapping[cat.name]:
                new_url = image_mapping[cat.name]
                cat.image_url = new_url
                updated += 1
                print(f"ID {cat.id:<3} | {cat.name:<20} -> URL SET")
            else:
                print(f"ID {cat.id:<3} | {cat.name:<20} -> NO URL PROVIDED")
        
        if updated > 0:
            await db.commit()
            print(f"\n{updated} categories updated!")
        
        # Clear cache
        try:
            from core.redis_client import redis_client
            await redis_client.initialize()
            await redis_client.delete("categories:all")
            print("Redis cache cleared")
            await redis_client.close()
        except:
            pass
        
        print("\nRestart: docker-compose restart customer-backend")

if __name__ == "__main__":
    asyncio.run(set_category_images())
