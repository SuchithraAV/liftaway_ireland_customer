"""
Seed LiftAway UK Pricing Data (2025 Benchmarks)
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from core.database import AsyncSessionLocal
from core.pricing_engine import PricingSlab

async def seed_liftaway_pricing():
    """Seed database with LiftAway UK pricing structure"""
    
    pricing_data = [
        # Household & Furniture Removal
        {"load_type": "single_item", "weight_min_kg": 10, "weight_max_kg": 100, "time_min_minutes": 15, "time_max_minutes": 30, "price_min_gbp": 70, "price_max_gbp": 150, "avg_price_gbp": 110},
        {"load_type": "multiple_items", "weight_min_kg": 100, "weight_max_kg": 300, "time_min_minutes": 30, "time_max_minutes": 60, "price_min_gbp": 150, "price_max_gbp": 300, "avg_price_gbp": 225},
        {"load_type": "full_van_local", "weight_min_kg": 300, "weight_max_kg": 600, "time_min_minutes": 60, "time_max_minutes": 120, "price_min_gbp": 120, "price_max_gbp": 180, "avg_price_gbp": 150},
        {"load_type": "full_property_move", "weight_min_kg": 600, "weight_max_kg": 2000, "time_min_minutes": 120, "time_max_minutes": 480, "price_min_gbp": 300, "price_max_gbp": 1500, "avg_price_gbp": 900},
        
        # Household Waste & Garden Waste
        {"load_type": "household_waste", "weight_min_kg": 50, "weight_max_kg": 200, "time_min_minutes": 20, "time_max_minutes": 45, "price_min_gbp": 60, "price_max_gbp": 100, "avg_price_gbp": 80},
        {"load_type": "garden_waste", "weight_min_kg": 30, "weight_max_kg": 150, "time_min_minutes": 15, "time_max_minutes": 40, "price_min_gbp": 50, "price_max_gbp": 75, "avg_price_gbp": 62},
        {"load_type": "mixed_waste", "weight_min_kg": 100, "weight_max_kg": 400, "time_min_minutes": 30, "time_max_minutes": 90, "price_min_gbp": 80, "price_max_gbp": 200, "avg_price_gbp": 140},
        {"load_type": "one_off_clearance", "weight_min_kg": 150, "weight_max_kg": 500, "time_min_minutes": 45, "time_max_minutes": 120, "price_min_gbp": 80, "price_max_gbp": 150, "avg_price_gbp": 115},
    ]
    
    async with AsyncSessionLocal() as db:
        # Check if data already exists
        result = await db.execute(select(PricingSlab))
        existing = result.scalars().first()
        
        if existing:
            print("✅ Pricing data already exists - skipping seed")
            return
        
        # Clear existing pricing data
        await db.execute(delete(PricingSlab))
        await db.commit()
        
        # Insert new pricing data
        for data in pricing_data:
            slab = PricingSlab(**data)
            db.add(slab)
        
        await db.commit()
        print(f"✅ Seeded {len(pricing_data)} LiftAway pricing slabs")
        print("📋 Load types: single_item, multiple_items, full_van_local, full_property_move,")
        print("              household_waste, garden_waste, mixed_waste, one_off_clearance")

if __name__ == "__main__":
    try:
        asyncio.run(seed_liftaway_pricing())
    except Exception as e:
        print(f"❌ Seeding failed: {e}")
        import sys
        sys.exit(0)  # Don't fail deployment if already seeded
