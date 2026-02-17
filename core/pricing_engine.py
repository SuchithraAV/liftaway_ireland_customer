"""
LiftAway Pricing Engine with AI Prediction (2025 UK Benchmarks)
"""
from openai import OpenAI
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy import Column, String, Integer, Boolean, DateTime, DECIMAL
from core.database import Base
from sqlalchemy.sql import func

class PricingSlab(Base):
    __tablename__ = "pricing_slabs"
    id = Column(Integer, primary_key=True)
    load_type = Column(String(50), nullable=False)
    weight_min_kg = Column(Integer, nullable=False)
    weight_max_kg = Column(Integer, nullable=False)
    time_min_minutes = Column(Integer, nullable=False)
    time_max_minutes = Column(Integer, nullable=False)
    price_min_gbp = Column(DECIMAL(10, 2), nullable=False)
    price_max_gbp = Column(DECIMAL(10, 2), nullable=False)
    avg_price_gbp = Column(DECIMAL(10, 2), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

import logging

logger = logging.getLogger(__name__)

from config import settings

# OpenAI client
client = OpenAI(api_key=settings.OPENAI_API_KEY)

class PricingEngine:
    """LiftAway production pricing engine for UK removals & waste"""
    
    PLATFORM_FEE_PERCENT = Decimal("20.0")  # 20% platform commission (can be 20-30%)
    DRIVER_PAYOUT_PERCENT = Decimal("80.0")  # 80% to driver (70-80% range)
    MINIMUM_JOB_PRICE = Decimal("40.00")  # Minimum UK job price £40-£50
    
    @staticmethod
    async def calculate_price(
        load_type: str,
        estimated_weight_kg: int,
        estimated_time_minutes: int,
        description: str,
        db: AsyncSession,
        pickup_location: str = "",
        use_ai: bool = True
    ) -> Dict:
        """
        Calculate price using LiftAway 2025 benchmarks + AI prediction
        
        Returns:
            {
                "customer_price": Decimal,
                "driver_price": Decimal,
                "platform_fee": Decimal,
                "ai_predicted_price": Decimal (optional),
                "pricing_slab_id": int
            }
        """
        # 1. Get matching pricing slab from database
        result = await db.execute(
            select(PricingSlab).where(
                PricingSlab.load_type == load_type,
                PricingSlab.weight_min_kg <= estimated_weight_kg,
                PricingSlab.weight_max_kg >= estimated_weight_kg,
                PricingSlab.is_active == True
            )
        )
        slab = result.scalar_one_or_none()
        
        if not slab:
            raise ValueError(f"No pricing slab found for {load_type} with {estimated_weight_kg}kg")
        
        # 2. Base price from slab (use average)
        base_price = slab.avg_price_gbp
        
        # 3. AI Price Prediction (optional enhancement)
        ai_price = None
        if use_ai:
            try:
                ai_price = await PricingEngine._predict_price_with_ai(
                    load_type, estimated_weight_kg, estimated_time_minutes, description, pickup_location
                )
                # Use AI price if within slab range
                if slab.price_min_gbp <= ai_price <= slab.price_max_gbp:
                    base_price = ai_price
                    logger.info(f"Using AI predicted price: £{ai_price}")
            except Exception as e:
                logger.warning(f"AI prediction failed, using slab average: {e}")
        
        # 4. Enforce minimum price
        if base_price < PricingEngine.MINIMUM_JOB_PRICE:
            base_price = PricingEngine.MINIMUM_JOB_PRICE
        
        # 5. Calculate commission split
        customer_price = base_price
        platform_fee = (customer_price * PricingEngine.PLATFORM_FEE_PERCENT / 100).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        driver_price = customer_price - platform_fee
        
        return {
            "customer_price": customer_price,
            "driver_price": driver_price,
            "platform_fee": platform_fee,
            "ai_predicted_price": ai_price,
            "pricing_slab_id": slab.id,
            "price_breakdown": {
                "base_price": float(base_price),
                "driver_gets": float(driver_price),
                "platform_gets": float(platform_fee),
                "driver_percentage": 80.0,
                "platform_percentage": 20.0
            }
        }
    
    @staticmethod
    async def _predict_price_with_ai(
        load_type: str,
        weight_kg: int,
        time_minutes: int,
        description: str,
        pickup_location: str = ""
    ) -> Decimal:
        """
        Use ChatGPT to predict optimal price based on LiftAway 2025 benchmarks
        """
        is_london = "london" in pickup_location.lower() if pickup_location else False
        london_note = "\n⚠️ London location: Add 15-30% to base price" if is_london else ""
        
        prompt = f"""You are a LiftAway UK pricing expert. Based on the following job details, predict the optimal price in GBP:

Load Type: {load_type}
Estimated Weight: {weight_kg} kg
Estimated Time: {time_minutes} minutes
Description: {description}
Location: {pickup_location}{london_note}

LiftAway UK Pricing Benchmarks (2025) - STRICT RANGES:

Household & Furniture Removal:
- Single bulky item (sofa, bed, fridge): £70-£150
- Multiple furniture items / small flat clearance: £150-£300
- Full van load (local): £120-£180
- Full property move (1-2 bed): £300-£1,500

Household Waste & Garden Waste Removal:
- General household waste clearance: £60-£100
- Garden waste clearance: £50-£75
- Mixed waste / room clearance: £80-£200
- One-off clearance visits: £80-£150

Pricing Factors to Consider:
- Volume and number of items
- Item size and weight
- Access difficulty (stairs, lifts, dismantling)
- Distance to disposal facility
- Urgency and same-day service
- Local council disposal and landfill fees
- London prices: +15-30% higher

RULES:
- Minimum job price: £40-£50
- Your price MUST be within the range for the service type
- Consider all pricing factors listed above
- Be competitive but fair

Respond with ONLY a number (e.g., 125.50)"""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.3
        )
        
        price_str = response.choices[0].message.content.strip().replace("£", "").replace(",", "")
        predicted_price = Decimal(price_str).quantize(Decimal('0.01'))
        
        # Enforce minimum
        if predicted_price < PricingEngine.MINIMUM_JOB_PRICE:
            predicted_price = PricingEngine.MINIMUM_JOB_PRICE
        
        return predicted_price
    
    @staticmethod
    def validate_price_consistency(customer_price: Decimal, driver_price: Decimal, platform_fee: Decimal) -> bool:
        """Ensure pricing integrity"""
        return driver_price + platform_fee == customer_price