"""
Seed UK Waste Removal Pricing Data
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import AsyncSessionLocal
from core.waste_models import PricingSlab

async def seed_pricing_slabs():
    """Seed database with UK waste removal pricing structure"""
    
    pricing_data = [
        # Minimum Load
        {"load_type": "minimum", "weight_min_kg": 70, "weight_max_kg": 100, "time_min_minutes": 5, "time_max_minutes": 10, "price_min_gbp": 35, "price_max_gbp": 90, "avg_price_gbp": 62},
        {"load_type": "minimum", "weight_min_kg": 150, "weight_max_kg": 200, "time_min_minutes": 15, "time_max_minutes": 15, "price_min_gbp": 80, "price_max_gbp": 120, "avg_price_gbp": 100},
        {"load_type": "minimum", "weight_min_kg": 250, "weight_max_kg": 300, "time_min_minutes": 20, "time_max_minutes": 20, "price_min_gbp": 90, "price_max_gbp": 100, "avg_price_gbp": 95},
        
        # Quarter Load
        {"load_type": "quarter", "weight_min_kg": 375, "weight_max_kg": 400, "time_min_minutes": 15, "time_max_minutes": 25, "price_min_gbp": 60, "price_max_gbp": 180, "avg_price_gbp": 120},
        {"load_type": "quarter", "weight_min_kg": 450, "weight_max_kg": 500, "time_min_minutes": 30, "time_max_minutes": 30, "price_min_gbp": 120, "price_max_gbp": 120, "avg_price_gbp": 120},
        {"load_type": "quarter", "weight_min_kg": 550, "weight_max_kg": 600, "time_min_minutes": 35, "time_max_minutes": 35, "price_min_gbp": 140, "price_max_gbp": 240, "avg_price_gbp": 190},
        {"load_type": "quarter", "weight_min_kg": 650, "weight_max_kg": 700, "time_min_minutes": 40, "time_max_minutes": 40, "price_min_gbp": 150, "price_max_gbp": 160, "avg_price_gbp": 155},
        
        # Half Load
        {"load_type": "half", "weight_min_kg": 750, "weight_max_kg": 850, "time_min_minutes": 30, "time_max_minutes": 45, "price_min_gbp": 90, "price_max_gbp": 260, "avg_price_gbp": 173},
        {"load_type": "half", "weight_min_kg": 900, "weight_max_kg": 950, "time_min_minutes": 45, "time_max_minutes": 45, "price_min_gbp": 200, "price_max_gbp": 200, "avg_price_gbp": 200},
        {"load_type": "half", "weight_min_kg": 950, "weight_max_kg": 1000, "time_min_minutes": 50, "time_max_minutes": 50, "price_min_gbp": 200, "price_max_gbp": 480, "avg_price_gbp": 300},
        
        # Three Quarter Load
        {"load_type": "three_quarter", "weight_min_kg": 1000, "weight_max_kg": 1000, "time_min_minutes": 45, "time_max_minutes": 60, "price_min_gbp": 140, "price_max_gbp": 260, "avg_price_gbp": 221},
        {"load_type": "three_quarter", "weight_min_kg": 1000, "weight_max_kg": 1000, "time_min_minutes": 60, "time_max_minutes": 60, "price_min_gbp": 280, "price_max_gbp": 320, "avg_price_gbp": 300},
        
        # Full Load
        {"load_type": "full", "weight_min_kg": 1000, "weight_max_kg": 1500, "time_min_minutes": 60, "time_max_minutes": 90, "price_min_gbp": 220, "price_max_gbp": 520, "avg_price_gbp": 343},
        {"load_type": "full", "weight_min_kg": 1500, "weight_max_kg": 2000, "time_min_minutes": 90, "time_max_minutes": 120, "price_min_gbp": 400, "price_max_gbp": 600, "avg_price_gbp": 500},
    ]
    
    async with AsyncSessionLocal() as db:
        for data in pricing_data:
            slab = PricingSlab(**data)
            db.add(slab)
        
        await db.commit()
        print(f"✅ Seeded {len(pricing_data)} pricing slabs")

if __name__ == "__main__":
    asyncio.run(seed_pricing_slabs())